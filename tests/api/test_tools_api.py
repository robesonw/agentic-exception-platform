"""
Tests for Tool API endpoints (P6-25).

Tests verify:
- Creating tenant-scoped vs global tools
- Listing tools filtered by scope and tenant
- Isolation between tenants
- Global tools are accessible to all tenants
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

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
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS tenant (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tool_definition (
                tool_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT,
                name TEXT NOT NULL,
                type TEXT NOT NULL,
                config TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_tool_definition_tenant_id ON tool_definition(tenant_id);
            """
            )
        )
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS tool_definition;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db_session: AsyncSession):
    """Set up test data in the database."""
    from sqlalchemy import text
    import json
    
    # Create tenants
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_001', 'Tenant One', 'active')")
    )
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_002', 'Tenant Two', 'active')")
    )
    
    # Create global tools (tenant_id is NULL)
    now = datetime.now(timezone.utc)
    global_tools_data = [
        ("Global Webhook Tool", "webhook", {"endpoint": "https://api.example.com/webhook", "method": "POST"}, now),
        ("Global REST Tool", "rest", {"endpoint": "https://api.example.com/rest", "method": "GET"}, now),
    ]
    
    for tool_data in global_tools_data:
        await test_db_session.execute(
            text(
                """
            INSERT INTO tool_definition (tenant_id, name, type, config, created_at)
            VALUES (NULL, :name, :type, :config, :created_at)
            """
            ),
            {
                "name": tool_data[0],
                "type": tool_data[1],
                "config": json.dumps(tool_data[2]),
                "created_at": tool_data[3],
            },
        )
    
    # Create tenant-scoped tools for TENANT_001
    tenant1_tools_data = [
        ("TENANT_001", "Tenant 1 Custom Tool", "webhook", {"endpoint": "https://tenant1.example.com/tool"}, now),
        ("TENANT_001", "Tenant 1 Email Tool", "email", {"smtp": "smtp.tenant1.com"}, now),
    ]
    
    for tool_data in tenant1_tools_data:
        await test_db_session.execute(
            text(
                """
            INSERT INTO tool_definition (tenant_id, name, type, config, created_at)
            VALUES (:tenant_id, :name, :type, :config, :created_at)
            """
            ),
            {
                "tenant_id": tool_data[0],
                "name": tool_data[1],
                "type": tool_data[2],
                "config": json.dumps(tool_data[3]),
                "created_at": tool_data[4],
            },
        )
    
    # Create tenant-scoped tools for TENANT_002
    await test_db_session.execute(
        text(
            """
        INSERT INTO tool_definition (tenant_id, name, type, config, created_at)
        VALUES ('TENANT_002', 'Tenant 2 Custom Tool', 'webhook', :config, :created_at)
        """
        ),
        {
            "config": json.dumps({"endpoint": "https://tenant2.example.com/tool"}),
            "created_at": now,
        },
    )
    
    await test_db_session.commit()


class TestToolAPI:
    """Tests for Tool API endpoints."""

    @pytest.mark.asyncio
    async def test_list_tools_scope_tenant(self, test_db_session, setup_test_data):
        """Test listing tools with scope='tenant'."""
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
                "/api/tools?tenant_id=TENANT_001&scope=tenant",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 tenant-scoped tools for TENANT_001
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_scope_global(self, test_db_session, setup_test_data):
        """Test listing tools with scope='global'."""
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
                "/api/tools?scope=global",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 global tools
            assert all(item["tenantId"] is None for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_scope_all(self, test_db_session, setup_test_data):
        """Test listing tools with scope='all'."""
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
                "/api/tools?tenant_id=TENANT_001&scope=all",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should get global tools (2) + tenant-scoped tools for TENANT_001 (2) = 4
            assert data["total"] == 4
            # Verify mix of global and tenant-scoped
            tenant_ids = [item["tenantId"] for item in data["items"]]
            assert None in tenant_ids  # Has global tools
            assert "TENANT_001" in tenant_ids  # Has tenant-scoped tools
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_filter_by_name(self, test_db_session, setup_test_data):
        """Test filtering tools by name."""
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
                "/api/tools?tenant_id=TENANT_001&scope=all&name=Custom",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1  # 1 tool with "Custom" in name
            assert "Custom" in data["items"][0]["name"]
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_filter_by_type(self, test_db_session, setup_test_data):
        """Test filtering tools by type."""
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
                "/api/tools?tenant_id=TENANT_001&scope=all&type=webhook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 2  # At least 2 webhook tools (1 global + 1 tenant-scoped)
            assert all(item["type"] == "webhook" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_tool_global(self, test_db_session, setup_test_data):
        """Test retrieving a global tool."""
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
            # Get global tool ID from listing
            list_response = client.get(
                "/api/tools?scope=global",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            assert list_response.status_code == 200
            tools = list_response.json()["items"]
            global_tool_id = tools[0]["toolId"]
            
            # Get the specific global tool (no tenant_id required)
            response = client.get(
                f"/api/tools/{global_tool_id}",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["toolId"] == global_tool_id
            assert data["tenantId"] is None  # Global tool
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_tool_tenant_scoped(self, test_db_session, setup_test_data):
        """Test retrieving a tenant-scoped tool."""
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
            # Get tenant-scoped tool ID from listing
            list_response = client.get(
                "/api/tools?tenant_id=TENANT_001&scope=tenant",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            assert list_response.status_code == 200
            tools = list_response.json()["items"]
            tenant_tool_id = tools[0]["toolId"]
            
            # Get the specific tenant-scoped tool (tenant_id required)
            response = client.get(
                f"/api/tools/{tenant_tool_id}?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["toolId"] == tenant_tool_id
            assert data["tenantId"] == "TENANT_001"
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_tool_tenant_scoped_missing_tenant_id(self, test_db_session, setup_test_data):
        """Test that tenant_id is required for tenant-scoped tools."""
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
            # Get tenant-scoped tool ID
            list_response = client.get(
                "/api/tools?tenant_id=TENANT_001&scope=tenant",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            assert list_response.status_code == 200
            tools = list_response.json()["items"]
            tenant_tool_id = tools[0]["toolId"]
            
            # Try to get without tenant_id (should fail)
            response = client.get(
                f"/api/tools/{tenant_tool_id}",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            # Should return 400 because tenant_id is required for tenant-scoped tools
            assert response.status_code == 400
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_global_tool(self, test_db_session, setup_test_data):
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
                "/api/tools",  # No tenant_id = global tool
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={
                    "name": "New Global Tool",
                    "type": "rest",
                    "config": {"endpoint": "https://api.example.com/new", "method": "POST"},
                },
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "New Global Tool"
            assert data["type"] == "rest"
            assert data["tenantId"] is None  # Global tool
            assert "toolId" in data
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_tenant_scoped_tool(self, test_db_session, setup_test_data):
        """Test creating a tenant-scoped tool."""
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
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={
                    "name": "New Tenant Tool",
                    "type": "webhook",
                    "config": {"endpoint": "https://tenant1.example.com/new", "method": "POST"},
                },
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "New Tenant Tool"
            assert data["type"] == "webhook"
            assert data["tenantId"] == "TENANT_001"  # Tenant-scoped tool
            assert "toolId" in data
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced."""
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
            # TENANT_001 should only see their own tenant-scoped tools
            response = client.get(
                "/api/tools?tenant_id=TENANT_001&scope=tenant",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
            
            # TENANT_001 should NOT see TENANT_002's tenant-scoped tools
            # But should see global tools when scope=all
            response = client.get(
                "/api/tools?tenant_id=TENANT_001&scope=all",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should have global tools + TENANT_001's tools, but NOT TENANT_002's tools
            tenant_ids = [item["tenantId"] for item in data["items"]]
            assert "TENANT_002" not in tenant_ids  # Should not see TENANT_002's tools
            assert None in tenant_ids or "TENANT_001" in tenant_ids  # Should see global or own tools
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_global_tools_accessible_to_all_tenants(self, test_db_session, setup_test_data):
        """Test that global tools are accessible to all tenants."""
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
            # TENANT_001 should see global tools
            response = client.get(
                "/api/tools?tenant_id=TENANT_001&scope=all",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            global_tools = [item for item in data["items"] if item["tenantId"] is None]
            assert len(global_tools) == 2  # 2 global tools
            
            # TENANT_002 should also see the same global tools
            response = client.get(
                "/api/tools?tenant_id=TENANT_002&scope=all",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            global_tools = [item for item in data["items"] if item["tenantId"] is None]
            assert len(global_tools) == 2  # Same 2 global tools
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_tools_scope_tenant_missing_tenant_id(self, test_db_session, setup_test_data):
        """Test that scope='tenant' requires tenant_id."""
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
                "/api/tools?scope=tenant",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_tool_not_found(self, test_db_session, setup_test_data):
        """Test that non-existent tool returns 404."""
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
                "/api/tools/999",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

