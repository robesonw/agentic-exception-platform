"""
Tests for Tool Enablement Admin API endpoints (P8-7).

Tests verify:
- PUT /api/tools/{tool_id}/enablement
- GET /api/tools/{tool_id}/enablement
- DELETE /api/tools/{tool_id}/enablement
- Tenant access validation
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import json

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.api.middleware import get_rate_limiter

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up API keys for tests."""
    auth = get_api_key_auth()
    limiter = get_rate_limiter()
    # Ensure DEFAULT_API_KEY is registered to TENANT_001
    auth.register_api_key(DEFAULT_API_KEY, "TENANT_001", Role.ADMIN)
    yield
    # Reset rate limiter after each test
    limiter._request_timestamps.clear()


@pytest.fixture
async def test_db_session():
    """Create a test database session."""
    # Use in-memory SQLite for testing
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables manually for SQLite compatibility
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tenant (tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL);"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_definition (tool_id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, name TEXT NOT NULL, type TEXT NOT NULL, config TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_definition_tenant_id ON tool_definition(tenant_id);"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_enablement (tenant_id TEXT NOT NULL, tool_id INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, PRIMARY KEY (tenant_id, tool_id), FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE, FOREIGN KEY (tool_id) REFERENCES tool_definition(tool_id) ON DELETE CASCADE);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_enablement_tenant_id ON tool_enablement(tenant_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_enablement_tool_id ON tool_enablement(tool_id);"))
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tool_enablement;"))
        await conn.execute(text("DROP TABLE IF EXISTS tool_definition;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db_session: AsyncSession):
    """Set up test data in the database."""
    # Create tenants
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_001', 'Tenant One', 'active')")
    )
    
    # Create tool definitions
    tool_config = json.dumps({
        "description": "Test HTTP tool",
        "inputSchema": {"type": "object"},
        "outputSchema": {"type": "object"},
        "authType": "none",
        "endpointConfig": {"url": "https://api.example.com/tool", "method": "POST"},
        "tenantScope": "tenant",
    })
    
    await test_db_session.execute(
        text(
            "INSERT INTO tool_definition (tenant_id, name, type, config) "
            "VALUES ('TENANT_001', 'test_tool', 'http', :config)"
        ),
        {"config": tool_config},
    )
    
    await test_db_session.commit()


class TestToolEnablementAPI:
    """Tests for tool enablement API endpoints."""

    @pytest.mark.asyncio
    async def test_set_enablement_enable(self, test_db_session, setup_test_data):
        """Test enabling a tool."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/api/tools/1/enablement",
                json={"enabled": True},
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["tenantId"] == "TENANT_001"
            assert data["toolId"] == 1
            assert data["enabled"] is True
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_set_enablement_disable(self, test_db_session, setup_test_data):
        """Test disabling a tool."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/api/tools/1/enablement",
                json={"enabled": False},
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_set_enablement_tool_not_found(self, test_db_session, setup_test_data):
        """Test error when tool is not found."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.put(
                "/api/tools/999/enablement",
                json={"enabled": True},
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_enablement_default(self, test_db_session, setup_test_data):
        """Test getting enablement when no record exists (defaults to enabled)."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            response = client.get(
                "/api/tools/1/enablement",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True  # Default
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_enablement_after_set(self, test_db_session, setup_test_data):
        """Test getting enablement after setting it."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            # Set to disabled
            client.put(
                "/api/tools/1/enablement",
                json={"enabled": False},
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            # Get enablement
            response = client.get(
                "/api/tools/1/enablement",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_delete_enablement(self, test_db_session, setup_test_data):
        """Test deleting enablement record."""
        import src.infrastructure.db.session as session_module
        original_get_context = session_module.get_db_session_context
        
        async def mock_get_context():
            class MockContext:
                async def __aenter__(self):
                    return test_db_session
                
                async def __aexit__(self, *args):
                    pass
            
            return MockContext()
        
        session_module.get_db_session_context = mock_get_context
        
        try:
            # Set to disabled
            client.put(
                "/api/tools/1/enablement",
                json={"enabled": False},
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            # Delete enablement
            response = client.delete(
                "/api/tools/1/enablement",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            assert "deleted" in response.json()["message"].lower()
            
            # Should default to enabled after deletion
            get_response = client.get(
                "/api/tools/1/enablement",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            assert get_response.json()["enabled"] is True
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_set_enablement_unauthorized(self, test_db_session, setup_test_data):
        """Test error when authentication is missing."""
        response = client.put(
            "/api/tools/1/enablement",
            json={"enabled": True},
        )
        
        assert response.status_code == 401


