"""
Tests for database session management and connection pool.

Tests Phase 6 P6-3: Database connection pool, session factory, and health checks.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from src.infrastructure.db.session import (
    check_database_connection,
    close_engine,
    get_db_session,
    get_db_session_context,
    get_engine,
    get_session_factory,
    initialize_database,
)


@pytest.fixture
def mock_database_url(monkeypatch):
    """Set a mock database URL for testing."""
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/testdb")


@pytest.fixture
def reset_engine():
    """Reset the global engine between tests."""
    yield
    # Cleanup: close engine if it exists
    import src.infrastructure.db.session as session_module
    if session_module._engine is not None:
        # Reset globals
        session_module._engine = None
        session_module._SessionLocal = None


class TestDatabaseSettings:
    """Test database settings loading."""
    
    def test_get_database_url_from_env(self, monkeypatch):
        """Test getting database URL from DATABASE_URL environment variable."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://user:pass@host:5432/db")
        
        from src.infrastructure.db.settings import get_database_url
        
        url = get_database_url()
        assert url == "postgresql+asyncpg://user:pass@host:5432/db"
    
    def test_get_database_url_from_components(self, monkeypatch):
        """Test constructing database URL from individual components."""
        monkeypatch.delenv("DATABASE_URL", raising=False)
        monkeypatch.setenv("DB_USER", "testuser")
        monkeypatch.setenv("DB_PASSWORD", "testpass")
        monkeypatch.setenv("DB_HOST", "testhost")
        monkeypatch.setenv("DB_PORT", "5433")
        monkeypatch.setenv("DB_NAME", "testdb")
        
        from src.infrastructure.db.settings import get_database_url
        
        url = get_database_url()
        assert url == "postgresql+asyncpg://testuser:testpass@testhost:5433/testdb"
    
    def test_convert_sync_to_async_url(self, monkeypatch):
        """Test converting sync postgresql:// URL to async format."""
        monkeypatch.setenv("DATABASE_URL", "postgresql://user:pass@host:5432/db")
        
        from src.infrastructure.db.settings import get_database_url
        
        url = get_database_url()
        assert url == "postgresql+asyncpg://user:pass@host:5432/db"
    
    def test_pool_settings_from_env(self, monkeypatch):
        """Test reading pool settings from environment variables."""
        monkeypatch.setenv("DB_POOL_SIZE", "10")
        monkeypatch.setenv("DB_MAX_OVERFLOW", "20")
        monkeypatch.setenv("DB_POOL_TIMEOUT", "60")
        monkeypatch.setenv("DB_ECHO", "true")
        
        from src.infrastructure.db.settings import (
            get_db_echo,
            get_db_max_overflow,
            get_db_pool_size,
            get_db_pool_timeout,
        )
        
        assert get_db_pool_size() == 10
        assert get_db_max_overflow() == 20
        assert get_db_pool_timeout() == 60
        assert get_db_echo() is True


class TestEngineCreation:
    """Test async engine creation."""
    
    @pytest.mark.asyncio
    async def test_get_engine_creates_engine(self, mock_database_url, reset_engine):
        """Test that get_engine creates an async engine."""
        engine = get_engine()
        
        assert engine is not None
        assert isinstance(engine, AsyncEngine)
        assert engine.url.database == "testdb"
    
    @pytest.mark.asyncio
    async def test_get_engine_singleton(self, mock_database_url, reset_engine):
        """Test that get_engine returns the same engine instance."""
        engine1 = get_engine()
        engine2 = get_engine()
        
        assert engine1 is engine2
    
    @pytest.mark.asyncio
    async def test_close_engine(self, mock_database_url, reset_engine):
        """Test closing the engine."""
        engine = get_engine()
        assert engine is not None
        
        await close_engine()
        
        # Engine should be None after closing
        import src.infrastructure.db.session as session_module
        assert session_module._engine is None


class TestSessionFactory:
    """Test session factory creation."""
    
    @pytest.mark.asyncio
    async def test_get_session_factory(self, mock_database_url, reset_engine):
        """Test getting session factory."""
        factory = get_session_factory()
        
        assert factory is not None
        assert factory.kw.get("class_") == AsyncSession
    
    @pytest.mark.asyncio
    async def test_get_db_session_generator(self, mock_database_url, reset_engine):
        """Test get_db_session FastAPI dependency."""
        session_gen = get_db_session()
        
        # Should be an async generator
        assert hasattr(session_gen, "__aiter__")
        
        # Consume the generator (simulating FastAPI usage)
        session = await session_gen.__anext__()
        assert isinstance(session, AsyncSession)
        
        # Cleanup
        try:
            await session_gen.__anext__()
        except StopAsyncIteration:
            pass
    
    @pytest.mark.asyncio
    async def test_get_db_session_context(self, mock_database_url, reset_engine):
        """Test get_db_session_context context manager."""
        async with get_db_session_context() as session:
            assert isinstance(session, AsyncSession)


class TestConnectionRetry:
    """Test connection retry logic."""
    
    @pytest.mark.asyncio
    async def test_check_database_connection_success(self, mock_database_url, reset_engine):
        """Test successful database connection check."""
        with patch("src.infrastructure.db.session.get_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            
            mock_conn.execute = AsyncMock(return_value=mock_result)
            mock_engine.connect = AsyncMock(return_value=mock_conn.__aenter__())
            mock_get_engine.return_value = mock_engine
            
            result = await check_database_connection(retries=1, initial_delay=0.1)
            
            assert result is True
            mock_conn.execute.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_database_connection_failure(self, mock_database_url, reset_engine):
        """Test database connection check with failures."""
        with patch("src.infrastructure.db.session.get_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.connect = AsyncMock(side_effect=Exception("Connection failed"))
            mock_get_engine.return_value = mock_engine
            
            result = await check_database_connection(retries=2, initial_delay=0.1)
            
            assert result is False
    
    @pytest.mark.asyncio
    async def test_check_database_connection_retry_with_backoff(self, mock_database_url, reset_engine):
        """Test connection retry with exponential backoff."""
        call_count = 0
        
        async def mock_connect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Connection failed")
            # Success on second attempt
            mock_conn = AsyncMock()
            mock_result = MagicMock()
            mock_result.scalar.return_value = 1
            mock_conn.execute = AsyncMock(return_value=mock_result)
            return mock_conn.__aenter__()
        
        with patch("src.infrastructure.db.session.get_engine") as mock_get_engine:
            mock_engine = AsyncMock()
            mock_engine.connect = AsyncMock(side_effect=mock_connect)
            mock_get_engine.return_value = mock_engine
            
            result = await check_database_connection(retries=3, initial_delay=0.1)
            
            assert result is True
            assert call_count == 2


class TestDatabaseInitialization:
    """Test database initialization."""
    
    @pytest.mark.asyncio
    async def test_initialize_database_success(self, mock_database_url, reset_engine):
        """Test successful database initialization."""
        with patch("src.infrastructure.db.session.check_database_connection") as mock_check:
            mock_check.return_value = True
            
            result = await initialize_database()
            
            assert result is True
            mock_check.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_database_failure(self, mock_database_url, reset_engine):
        """Test database initialization failure."""
        with patch("src.infrastructure.db.session.check_database_connection") as mock_check:
            mock_check.return_value = False
            
            result = await initialize_database()
            
            assert result is False


class TestHealthCheckEndpoint:
    """Test database health check endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_check_db_success(self, mock_database_url, reset_engine):
        """Test successful database health check endpoint."""
        from httpx import AsyncClient
        
        with patch("src.infrastructure.db.session.check_database_connection") as mock_check:
            mock_check.return_value = True
            
            from src.api.main import app
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/db")
            
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            assert response.json()["database"] == "connected"
    
    @pytest.mark.asyncio
    async def test_health_check_db_failure(self, mock_database_url, reset_engine):
        """Test database health check endpoint when DB is unavailable."""
        from httpx import AsyncClient
        
        with patch("src.infrastructure.db.session.check_database_connection") as mock_check:
            mock_check.return_value = False
            
            from src.api.main import app
            
            async with AsyncClient(app=app, base_url="http://test") as client:
                response = await client.get("/health/db")
            
            assert response.status_code == 503
            assert response.json()["status"] == "unhealthy"
            assert response.json()["database"] == "disconnected"

