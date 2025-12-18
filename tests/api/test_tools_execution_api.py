"""
Tests for Tool Execution API endpoints (P8-6).

Tests verify:
- POST /api/tools/{tool_id}/execute
- GET /api/tools/executions (with filters and pagination)
- GET /api/tools/executions/{execution_id}
- Tenant access validation
- Scope validation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from uuid import uuid4

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.api.middleware import get_rate_limiter
from src.infrastructure.db.models import ActorType, ToolExecutionStatus

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
    # SQLite requires each statement to be executed separately
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tenant (tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL)"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_definition (tool_id INTEGER PRIMARY KEY AUTOINCREMENT, tenant_id TEXT, name TEXT NOT NULL, type TEXT NOT NULL, config TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_definition_tenant_id ON tool_definition(tenant_id)"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS exception (exception_id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, domain TEXT, exception_type TEXT, severity TEXT, status TEXT, source_system TEXT, entity TEXT, amount REAL, sla_deadline TIMESTAMP WITH TIME ZONE, owner TEXT, current_playbook_id INTEGER, current_step INTEGER, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE)"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tool_execution (id TEXT PRIMARY KEY, tenant_id TEXT NOT NULL, tool_id INTEGER NOT NULL, exception_id TEXT, status TEXT NOT NULL, requested_by_actor_type TEXT NOT NULL, requested_by_actor_id TEXT NOT NULL, input_payload TEXT NOT NULL, output_payload TEXT, error_message TEXT, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE, FOREIGN KEY (tool_id) REFERENCES tool_definition(tool_id) ON DELETE CASCADE, FOREIGN KEY (exception_id) REFERENCES exception(exception_id) ON DELETE SET NULL)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_execution_tenant_id ON tool_execution(tenant_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_execution_tool_id ON tool_execution(tool_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tool_execution_exception_id ON tool_execution(exception_id)"))
        await conn.execute(text("CREATE TABLE IF NOT EXISTS exception_event (event_id TEXT PRIMARY KEY, exception_id TEXT NOT NULL, tenant_id TEXT NOT NULL, event_type TEXT NOT NULL, actor_type TEXT NOT NULL, actor_id TEXT NOT NULL, payload TEXT NOT NULL, created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL, FOREIGN KEY (exception_id) REFERENCES exception(exception_id) ON DELETE CASCADE, FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exception_event_exception_id ON exception_event(exception_id)"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exception_event_tenant_id ON exception_event(tenant_id)"))
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS exception_event;"))
        await conn.execute(text("DROP TABLE IF EXISTS tool_execution;"))
        await conn.execute(text("DROP TABLE IF EXISTS exception;"))
        await conn.execute(text("DROP TABLE IF EXISTS tool_definition;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db_session: AsyncSession):
    """Set up test data in the database."""
    import json
    
    # Create tenants
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_001', 'Tenant One', 'active')")
    )
    await test_db_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('TENANT_002', 'Tenant Two', 'active')")
    )
    
    # Create tool definitions
    tool_config = json.dumps({
        "description": "Test HTTP tool",
        "inputSchema": {"type": "object", "properties": {"param": {"type": "string"}}},
        "outputSchema": {"type": "object"},
        "authType": "none",
        "endpointConfig": {
            "url": "https://api.example.com/tool",
            "method": "POST",
            "headers": {},
            "timeout_seconds": 30.0,
        },
        "tenantScope": "tenant",
    })
    
    await test_db_session.execute(
        text(
            "INSERT INTO tool_definition (tenant_id, name, type, config) "
            "VALUES ('TENANT_001', 'test_tool', 'http', :config)"
        ),
        {"config": tool_config},
    )
    
    await test_db_session.execute(
        text(
            "INSERT INTO tool_definition (tenant_id, name, type, config) "
            "VALUES (NULL, 'global_tool', 'http', :config)"
        ),
        {"config": tool_config},
    )
    
    # Create exception for linking
    await test_db_session.execute(
        text(
            "INSERT INTO exception (exception_id, tenant_id, domain, exception_type, severity, status) "
            "VALUES ('EXC_001', 'TENANT_001', 'finance', 'PaymentFailure', 'high', 'open')"
        )
    )
    
    await test_db_session.commit()


class TestToolExecutionAPI:
    """Tests for tool execution API endpoints."""

    @pytest.mark.asyncio
    async def test_execute_tool_success(self, test_db_session, setup_test_data):
        """Test successful tool execution."""
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
            # Mock the provider to avoid actual HTTP calls
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success", "data": "test_data"}
                
                response = client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value"},
                        "actorType": "user",
                        "actorId": "user123",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 202
                data = response.json()
                assert data["executionId"] is not None
                assert data["status"] == "accepted"
                assert "message" in data
                assert isinstance(data["executionId"], str)
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_execute_tool_with_exception_id(self, test_db_session, setup_test_data):
        """Test tool execution with exception ID."""
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
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success"}
                
                response = client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value"},
                        "exceptionId": "EXC_001",
                        "actorType": "agent",
                        "actorId": "ResolutionAgent",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 202
                data = response.json()
                assert data["status"] == "accepted"
                assert "executionId" in data
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self, test_db_session, setup_test_data):
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
            response = client.post(
                "/api/tools/999/execute",
                json={
                    "payload": {"param": "value"},
                    "actorType": "user",
                    "actorId": "user123",
                },
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_execute_tool_unauthorized(self, test_db_session, setup_test_data):
        """Test error when authentication is missing."""
        response = client.post(
            "/api/tools/1/execute",
            json={
                "payload": {"param": "value"},
                "actorType": "user",
                "actorId": "user123",
            },
        )
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_execute_tool_invalid_actor_type(self, test_db_session, setup_test_data):
        """Test error when actor type is invalid."""
        response = client.post(
            "/api/tools/1/execute",
            json={
                "payload": {"param": "value"},
                "actorType": "invalid",
                "actorId": "user123",
            },
            headers={"X-API-Key": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "actor_type" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_executions(self, test_db_session, setup_test_data):
        """Test listing tool executions."""
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
            # First create an execution
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success"}
                
                # Create execution
                client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value1"},
                        "actorType": "user",
                        "actorId": "user123",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
                
                # Create another execution
                client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value2"},
                        "actorType": "agent",
                        "actorId": "Agent1",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
            
            # List executions
            response = client.get(
                "/api/tools/executions",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "pageSize" in data
            assert "totalPages" in data
            assert len(data["items"]) >= 2
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_executions_with_filters(self, test_db_session, setup_test_data):
        """Test listing executions with filters."""
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
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success"}
                
                # Create executions
                client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value"},
                        "actorType": "user",
                        "actorId": "user123",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
            
            # Filter by tool_id
            response = client.get(
                "/api/tools/executions?tool_id=1",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert all(item["toolId"] == 1 for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_executions_with_pagination(self, test_db_session, setup_test_data):
        """Test listing executions with pagination."""
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
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success"}
                
                # Create multiple executions
                for i in range(5):
                    client.post(
                        "/api/tools/1/execute",
                        json={
                            "payload": {"param": f"value{i}"},
                            "actorType": "user",
                            "actorId": "user123",
                        },
                        headers={"X-API-Key": DEFAULT_API_KEY},
                    )
            
            # Get first page
            response = client.get(
                "/api/tools/executions?page=1&page_size=2",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["page"] == 1
            assert data["pageSize"] == 2
            assert len(data["items"]) <= 2
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_executions_invalid_status(self, test_db_session, setup_test_data):
        """Test error when status filter is invalid."""
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
                "/api/tools/executions?status=invalid",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
            assert "status" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_execution(self, test_db_session, setup_test_data):
        """Test getting a single execution by ID."""
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
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success"}
                
                # Create execution
                create_response = client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value"},
                        "actorType": "user",
                        "actorId": "user123",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
                
                assert create_response.status_code == 202
                execution_id = create_response.json()["executionId"]
                assert create_response.json()["status"] == "accepted"
                
                # Get execution (query endpoint still returns full details)
                response = client.get(
                    f"/api/tools/executions/{execution_id}",
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["executionId"] == execution_id
                assert data["toolId"] == 1
                assert data["tenantId"] == "TENANT_001"
                assert data["status"] == "requested"  # Should be in requested state initially
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_execution_not_found(self, test_db_session, setup_test_data):
        """Test error when execution is not found."""
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
            fake_id = str(uuid4())
            response = client.get(
                f"/api/tools/executions/{fake_id}",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_execution_invalid_uuid(self, test_db_session, setup_test_data):
        """Test error when execution ID is not a valid UUID."""
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
                "/api/tools/executions/invalid-id",
                headers={"X-API-Key": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
            assert "uuid" in response.json()["detail"].lower()
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_executions_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenants can only see their own executions."""
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
        
        # Register API key for TENANT_002
        auth = get_api_key_auth()
        auth.register_api_key("test_api_key_tenant_002", "TENANT_002", Role.ADMIN)
        
        try:
            with patch("src.tools.provider.HttpToolProvider.execute") as mock_execute:
                mock_execute.return_value = {"result": "success"}
                
                # Create execution for TENANT_001
                client.post(
                    "/api/tools/1/execute",
                    json={
                        "payload": {"param": "value"},
                        "actorType": "user",
                        "actorId": "user123",
                    },
                    headers={"X-API-Key": DEFAULT_API_KEY},
                )
            
            # TENANT_002 should not see TENANT_001's executions
            response = client.get(
                "/api/tools/executions",
                headers={"X-API-Key": "test_api_key_tenant_002"},
            )
            
            assert response.status_code == 200
            data = response.json()
            # TENANT_002 should have no executions (or only their own if any)
            assert all(item["tenantId"] == "TENANT_002" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

