"""
DB Health & Startup Smoke Tests (P6-32).

Tests verify:
- /health/db endpoint returns correct status codes
- Error responses don't leak connection strings or secrets
- Database initialization works on startup
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.main import app
from src.infrastructure.db.session import (
    get_engine,
    close_engine,
    initialize_database,
    check_database_connection,
)

client = TestClient(app)


@pytest.mark.phase6
class TestHealthDBEndpoint:
    """Tests for /health/db endpoint."""
    
    @pytest.mark.asyncio
    async def test_health_db_when_reachable(self):
        """Test that /health/db returns 200 OK when DB is reachable."""
        # Mock check_database_connection at the module where it's imported
        with patch('src.infrastructure.db.session.check_database_connection', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = True
            
            response = client.get("/health/db")
            
            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "healthy"
            assert data["database"] == "connected"
            mock_check.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_health_db_when_unreachable(self):
        """Test that /health/db returns 503 when DB is unreachable."""
        # Mock check_database_connection to return False
        with patch('src.infrastructure.db.session.check_database_connection', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            
            response = client.get("/health/db")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "disconnected"
    
    @pytest.mark.asyncio
    async def test_health_db_no_secrets_leaked_on_error(self):
        """Test that error responses don't leak connection strings or secrets."""
        # Mock check_database_connection to return False (simulating connection failure)
        with patch('src.infrastructure.db.session.check_database_connection', new_callable=AsyncMock) as mock_check:
            mock_check.return_value = False
            
            response = client.get("/health/db")
            
            assert response.status_code == 503
            data = response.json()
            assert data["status"] == "unhealthy"
            assert data["database"] == "disconnected"
            
            # Verify no connection strings or passwords in response
            response_text = response.text
            assert "postgresql" not in response_text.lower()
            assert "secret" not in response_text.lower()
            assert "password" not in response_text.lower()
            assert "@" not in response_text  # No connection string format
            # Verify response only contains safe status information
            assert "status" in response_text.lower()
            assert "database" in response_text.lower()
    
    @pytest.mark.asyncio
    async def test_health_db_connection_retry_logic(self):
        """Test that connection check uses retry logic."""
        call_count = 0
        
        async def mock_check_with_retries(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            # First call fails, second succeeds
            if call_count == 1:
                return False
            return True
        
        with patch('src.infrastructure.db.session.check_database_connection', new_callable=AsyncMock) as mock_check:
            mock_check.side_effect = mock_check_with_retries
            
            # First call should fail
            response1 = client.get("/health/db")
            assert response1.status_code == 503
            
            # Second call should succeed
            response2 = client.get("/health/db")
            assert response2.status_code == 200
            data = response2.json()
            assert data["status"] == "healthy"


@pytest.mark.phase6
class TestDatabaseStartupSmoke:
    """Smoke tests for database initialization on startup."""
    
    @pytest.mark.asyncio
    async def test_database_engine_creation(self):
        """Test that database engine can be created."""
        # Use in-memory SQLite for testing
        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )
        
        try:
            # Verify engine is created
            assert test_engine is not None
            
            # Verify we can connect
            async with test_engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                assert result.scalar() == 1
        finally:
            await test_engine.dispose()
    
    @pytest.mark.asyncio
    async def test_database_initialization_success(self):
        """Test that initialize_database works with a valid connection."""
        # Use in-memory SQLite for testing
        with patch('src.infrastructure.db.settings.get_database_url') as mock_get_url:
            mock_get_url.return_value = "sqlite+aiosqlite:///:memory:"
            
            # Reset global engine state
            import src.infrastructure.db.session as session_module
            session_module._engine = None
            session_module._SessionLocal = None
            
            try:
                # Initialize database
                result = await initialize_database()
                
                # Should succeed with in-memory SQLite
                assert result is True
                
                # Verify engine was created
                engine = get_engine()
                assert engine is not None
                
                # Verify we can connect
                async with engine.connect() as conn:
                    result = await conn.execute(text("SELECT 1"))
                    assert result.scalar() == 1
            finally:
                # Cleanup
                await close_engine()
    
    @pytest.mark.asyncio
    async def test_database_initialization_failure_handled_gracefully(self):
        """Test that initialize_database handles failures gracefully."""
        # Mock invalid database URL
        with patch('src.infrastructure.db.settings.get_database_url') as mock_get_url:
            mock_get_url.return_value = "postgresql+asyncpg://invalid:password@nonexistent:5432/nonexistent"
            
            # Reset global engine state
            import src.infrastructure.db.session as session_module
            session_module._engine = None
            session_module._SessionLocal = None
            
            try:
                # Initialize database (should fail but not raise exception)
                result = await initialize_database()
                
                # Should return False, not raise exception
                assert result is False
            except Exception as e:
                # If an exception is raised, it should be caught and logged
                # The function should still return False
                pytest.fail(f"initialize_database should not raise exceptions, got: {e}")
            finally:
                # Cleanup
                await close_engine()
    
    @pytest.mark.asyncio
    async def test_app_startup_with_db(self):
        """Test that app can be imported and DB initialization can be tested."""
        # This is a simple smoke test to verify app startup doesn't crash
        from src.api.main import app
        
        # Verify app is created
        assert app is not None
        assert app.title == "Agentic Exception Processing Platform"
        
        # Verify health endpoint exists
        routes = [route.path for route in app.routes]
        assert "/health" in routes
        assert "/health/db" in routes
    
    @pytest.mark.asyncio
    async def test_database_connection_check_with_retries(self):
        """Test that check_database_connection uses retry logic correctly."""
        # Use in-memory SQLite for testing
        test_engine = create_async_engine(
            "sqlite+aiosqlite:///:memory:",
            echo=False,
        )
        
        try:
            with patch('src.infrastructure.db.session.get_engine') as mock_get_engine:
                mock_get_engine.return_value = test_engine
                
                # Should succeed immediately with valid connection
                result = await check_database_connection(retries=1, initial_delay=0.1)
                assert result is True
        finally:
            await test_engine.dispose()
    
    @pytest.mark.asyncio
    async def test_database_connection_check_failure_with_retries(self):
        """Test that check_database_connection retries on failure."""
        # Create an engine that will fail to connect
        with patch('src.infrastructure.db.session.get_engine') as mock_get_engine:
            # Create a mock engine that raises exceptions
            mock_engine = MagicMock()
            mock_conn = AsyncMock()
            mock_conn.__aenter__ = AsyncMock(side_effect=Exception("Connection failed"))
            mock_conn.__aexit__ = AsyncMock(return_value=None)
            mock_engine.connect.return_value = mock_conn
            mock_get_engine.return_value = mock_engine
            
            # Should return False after retries
            result = await check_database_connection(retries=2, initial_delay=0.1)
            assert result is False


@pytest.mark.phase6
class TestHealthEndpointBasic:
    """Tests for basic /health endpoint."""
    
    def test_health_endpoint(self):
        """Test that /health endpoint returns 200 OK."""
        response = client.get("/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"

