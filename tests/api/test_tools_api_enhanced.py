"""
Tests for enhanced Tool API endpoints (P8-8).

Tests verify:
- GET /api/tools with scope and status filters
- POST /api/tools with schema validation enforcement
- POST /api/tools with tenant scope rules enforcement
- Tenant isolation + global tool visibility
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
    # Register API key for TENANT_002
    auth.register_api_key("test_api_key_tenant_002", "TENANT_002", Role.ADMIN)
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
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_002', 'Tenant Two', 'active')")
    )
    
    # Create global tool
    global_tool_config = json.dumps({
        "description": "Global HTTP tool",
        "inputSchema": {"type": "object", "properties": {"param": {"type": "string"}}},
        "outputSchema": {"type": "object"},
        "authType": "none",
        "endpointConfig": {"url": "https://api.example.com/global", "method": "POST"},
        "tenantScope": "global",
    })
    await test_db_session.execute(
        text(
            "INSERT INTO tool_definition (tenant_id, name, type, config) "
            "VALUES (NULL, 'global_tool', 'http', :config)"
        ),
        {"config": global_tool_config},
    )
    
    # Create tenant-scoped tool for TENANT_001
    tenant_tool_config = json.dumps({
        "description": "Tenant HTTP tool",
        "inputSchema": {"type": "object", "properties": {"param": {"type": "string"}}},
        "outputSchema": {"type": "object"},
        "authType": "none",
        "endpointConfig": {"url": "https://api.example.com/tenant", "method": "POST"},
        "tenantScope": "tenant",
    })
    await test_db_session.execute(
        text(
            "INSERT INTO tool_definition (tenant_id, name, type, config) "
            "VALUES ('TENANT_001', 'tenant_tool', 'http', :config)"
        ),
        {"config": tenant_tool_config},
    )
    
    # Create another tenant-scoped tool for TENANT_001
    await test_db_session.execute(
        text(
            "INSERT INTO tool_definition (tenant_id, name, type, config) "
            "VALUES ('TENANT_001', 'tenant_tool_2', 'http', :config)"
        ),
        {"config": tenant_tool_config},
    )
    
    # Disable one tool for TENANT_001
    await test_db_session.execute(
        text(
            "INSERT INTO tool_enablement (tenant_id, tool_id, enabled) "
            "VALUES ('TENANT_001', 2, 0)"
        )
    )
    
    await test_db_session.commit()


class TestEnhancedToolsAPI:
    """Tests for enhanced tool API endpoints."""

    @pytest.mark.asyncio
    async def test_list_tools_scope_global(self, test_db_session, setup_test_data):
        """Test listing only global tools."""
        from unittest.mock import patch
        
        class MockContext:
            def __init__(self, session):
                self.session = session
            
            async def __aenter__(self):
                return self.session
            
            async def __aexit__(self, *args):
                pass
        
        with patch("src.infrastructure.db.session.get_db_session_context") as mock_get_context:
            mock_get_context.return_value = MockContext(test_db_session)
            
            response = client.get(
                "/api/tools?scope=global",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["items"][0]["name"] == "global_tool"
            assert data["items"][0]["tenantId"] is None

    @pytest.mark.asyncio
    async def test_list_tools_scope_tenant(self, test_db_session, setup_test_data):
        """Test listing only tenant-scoped tools."""
        from unittest.mock import patch
        
        class MockContext:
            def __init__(self, session):
                self.session = session
            
            async def __aenter__(self):
                return self.session
            
            async def __aexit__(self, *args):
                pass
        
        with patch("src.infrastructure.db.session.get_db_session_context") as mock_get_context:
            mock_get_context.return_value = MockContext(test_db_session)
            
            response = client.get(
                "/api/tools?scope=tenant&tenant_id=TENANT_001",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])

    @pytest.mark.asyncio
    async def test_list_tools_scope_all(self, test_db_session, setup_test_data):
        """Test listing all tools (global + tenant-scoped)."""
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
                "/api/tools?scope=all",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should have global tool + 2 tenant-scoped tools
            assert len(data["items"]) == 3
            # Check that global tool is included
            global_tools = [item for item in data["items"] if item["tenantId"] is None]
            assert len(global_tools) == 1
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_status_enabled(self, test_db_session, setup_test_data):
        """Test listing only enabled tools."""
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
                "/api/tools?scope=all&status=enabled",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should have global tool (enabled by default) + 1 enabled tenant tool
            assert len(data["items"]) == 2
            assert all(item.get("enabled", True) is True for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_status_disabled(self, test_db_session, setup_test_data):
        """Test listing only disabled tools."""
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
                "/api/tools?scope=all&status=disabled",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should have 1 disabled tool (tool_id=2)
            assert len(data["items"]) == 1
            assert data["items"][0]["toolId"] == 2
            assert data["items"][0]["enabled"] is False
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_status_requires_auth(self, test_db_session, setup_test_data):
        """Test that status filter requires authentication."""
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
            response = client.get("/api/tools?status=enabled")
            
            assert response.status_code == 401
            assert "authentication required" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tool_phase8_schema_validation(self, test_db_session, setup_test_data):
        """Test that Phase 8 schema validation is enforced."""
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
            # Missing required fields
            response = client.post(
                "/api/tools?tenant_id=TENANT_001",
                json={
                    "name": "test_tool",
                    "type": "http",
                    "description": "Test tool",
                    # Missing inputSchema, outputSchema, authType, endpointConfig
                },
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
            assert "schema validation" in response.json()["detail"].lower() or "required" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tool_http_missing_endpoint_config(self, test_db_session, setup_test_data):
        """Test that HTTP tools require endpoint_config."""
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
            response = client.post(
                "/api/tools?tenant_id=TENANT_001",
                json={
                    "name": "test_tool",
                    "type": "http",
                    "description": "Test tool",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object"},
                    "authType": "none",
                    "tenantScope": "tenant",
                    # Missing endpointConfig
                },
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
            assert "endpoint_config" in response.json()["detail"].lower() or "endpointConfig" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tool_global_scope(self, test_db_session, setup_test_data):
        """Test creating a global tool."""
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
            response = client.post(
                "/api/tools",
                json={
                    "name": "new_global_tool",
                    "type": "http",
                    "description": "New global tool",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object"},
                    "authType": "none",
                    "endpointConfig": {"url": "https://api.example.com/new", "method": "POST"},
                    "tenantScope": "global",
                },
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "new_global_tool"
            assert data["tenantId"] is None  # Global tool
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tool_tenant_scope_requires_auth(self, test_db_session, setup_test_data):
        """Test that tenant-scoped tools require authentication."""
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
            response = client.post(
                "/api/tools",
                json={
                    "name": "test_tool",
                    "type": "http",
                    "description": "Test tool",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object"},
                    "authType": "none",
                    "endpointConfig": {"url": "https://api.example.com/test", "method": "POST"},
                    "tenantScope": "tenant",
                },
            )
            
            assert response.status_code == 401
            assert "authentication required" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tool_tenant_scope_enforces_tenant_id(self, test_db_session, setup_test_data):
        """Test that tenant-scoped tools enforce tenant ID matching."""
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
            # Try to create tool for different tenant
            response = client.post(
                "/api/tools?tenant_id=TENANT_002",
                json={
                    "name": "test_tool",
                    "type": "http",
                    "description": "Test tool",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object"},
                    "authType": "none",
                    "endpointConfig": {"url": "https://api.example.com/test", "method": "POST"},
                    "tenantScope": "tenant",
                },
                headers={"X-API-Key": DEFAULT_API_KEY},  # Authenticated as TENANT_001
            )
            
            assert response.status_code == 403
            assert "tenant id mismatch" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tool_global_ignores_tenant_id(self, test_db_session, setup_test_data):
        """Test that global tools ignore tenant_id query parameter."""
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
            response = client.post(
                "/api/tools?tenant_id=TENANT_001",
                json={
                    "name": "new_global_tool_2",
                    "type": "http",
                    "description": "New global tool",
                    "inputSchema": {"type": "object"},
                    "outputSchema": {"type": "object"},
                    "authType": "none",
                    "endpointConfig": {"url": "https://api.example.com/new2", "method": "POST"},
                    "tenantScope": "global",
                },
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["tenantId"] is None  # Should be global despite tenant_id in query
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenants can only see their own tenant-scoped tools."""
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
            # TENANT_002 should only see global tools (no tenant-scoped tools for them)
            response = client.get(
                "/api/tools?scope=tenant&tenant_id=TENANT_002",
                headers={"X-API-Key": "test_api_key_tenant_002"},
            )
            
            assert response.status_code == 200
            data = response.json()
            # TENANT_002 has no tenant-scoped tools
            assert len(data["items"]) == 0
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_global_visibility(self, test_db_session, setup_test_data):
        """Test that global tools are visible to all tenants."""
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
            # TENANT_002 should see global tools
            response = client.get(
                "/api/tools?scope=all",
                headers={"X-API-Key": "test_api_key_tenant_002"},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should see global tool
            global_tools = [item for item in data["items"] if item["tenantId"] is None]
            assert len(global_tools) == 1
            assert global_tools[0]["name"] == "global_tool"
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_tool_includes_enabled_status(self, test_db_session, setup_test_data):
        """Test that GET /api/tools/{tool_id} includes enabled status."""
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
            # Get disabled tool
            response = client.get(
                "/api/tools/2",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is False
            
            # Get enabled tool
            response = client.get(
                "/api/tools/3",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["enabled"] is True
        finally:
            session_module.get_db_session_context = original_get_context

