"""
Tests for Playbook API endpoints (P6-24).

Tests verify:
- Basic CRUD operations
- Multi-tenant isolation (tenant A cannot see tenant B's playbooks)
- Filtering by name and version
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
            CREATE TABLE IF NOT EXISTS playbook (
                playbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                conditions TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE,
                UNIQUE (tenant_id, name, version)
            );
            CREATE INDEX IF NOT EXISTS ix_playbook_tenant_id ON playbook(tenant_id);
            """
            )
        )
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS playbook;"))
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
    
    # Create playbooks for TENANT_001
    now = datetime.now(timezone.utc)
    playbooks_data = [
        ("TENANT_001", "Payment Failure Playbook", 1, {"type": "PaymentFailure"}, now),
        ("TENANT_001", "Payment Failure Playbook", 2, {"type": "PaymentFailure", "severity": "high"}, now),
        ("TENANT_001", "Fraud Detection Playbook", 1, {"type": "FraudAlert"}, now),
    ]
    
    for pb_data in playbooks_data:
        await test_db_session.execute(
            text(
                """
            INSERT INTO playbook (tenant_id, name, version, conditions, created_at)
            VALUES (:tenant_id, :name, :version, :conditions, :created_at)
            """
            ),
            {
                "tenant_id": pb_data[0],
                "name": pb_data[1],
                "version": pb_data[2],
                "conditions": json.dumps(pb_data[3]),
                "created_at": pb_data[4],
            },
        )
    
    # Create playbooks for TENANT_002
    await test_db_session.execute(
        text(
            """
        INSERT INTO playbook (tenant_id, name, version, conditions, created_at)
        VALUES ('TENANT_002', 'Healthcare Playbook', 1, :conditions, :created_at)
        """
        ),
        {
            "conditions": json.dumps({"type": "PatientDataMismatch"}),
            "created_at": now,
        },
    )
    
    await test_db_session.commit()


class TestPlaybookAPI:
    """Tests for Playbook API endpoints."""

    @pytest.mark.asyncio
    async def test_list_playbooks_basic(self, test_db_session, setup_test_data):
        """Test basic listing of playbooks."""
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
                "/api/playbooks?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["total"] == 3
            assert len(data["items"]) == 3
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_playbooks_filter_by_name(self, test_db_session, setup_test_data):
        """Test filtering playbooks by name."""
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
                "/api/playbooks?tenant_id=TENANT_001&name=Payment",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 Payment Failure Playbooks
            assert all("Payment" in item["name"] for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_list_playbooks_filter_by_version(self, test_db_session, setup_test_data):
        """Test filtering playbooks by version."""
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
                "/api/playbooks?tenant_id=TENANT_001&version=1",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 playbooks with version 1
            assert all(item["version"] == 1 for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_playbook_by_id(self, test_db_session, setup_test_data):
        """Test retrieving a single playbook by ID."""
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
            # First, get the playbook ID from listing
            list_response = client.get(
                "/api/playbooks?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            assert list_response.status_code == 200
            playbooks = list_response.json()["items"]
            playbook_id = playbooks[0]["playbookId"]
            
            # Get the specific playbook
            response = client.get(
                f"/api/playbooks/{playbook_id}?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["playbookId"] == playbook_id
            assert data["tenantId"] == "TENANT_001"
            assert "name" in data
            assert "version" in data
            assert "conditions" in data
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_playbook_not_found(self, test_db_session, setup_test_data):
        """Test retrieving non-existent playbook returns 404."""
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
                "/api/playbooks/999?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_playbook(self, test_db_session, setup_test_data):
        """Test creating a new playbook."""
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
                "/api/playbooks?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={
                    "name": "New Test Playbook",
                    "version": 1,
                    "conditions": {"type": "TestException", "severity": "medium"},
                },
            )
            
            assert response.status_code == 201
            data = response.json()
            assert data["name"] == "New Test Playbook"
            assert data["version"] == 1
            assert data["tenantId"] == "TENANT_001"
            assert "playbookId" in data
            assert data["conditions"] == {"type": "TestException", "severity": "medium"}
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_create_playbook_invalid_data(self, test_db_session, setup_test_data):
        """Test creating playbook with invalid data returns 400."""
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
                "/api/playbooks?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"name": "Test"},
            )
            
            assert response.status_code == 422  # Validation error
            
            # Invalid version (must be >= 1)
            response = client.post(
                "/api/playbooks?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={
                    "name": "Test",
                    "version": 0,
                    "conditions": {},
                },
            )
            
            assert response.status_code == 422  # Validation error
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_tenant_isolation_list(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced in list endpoint."""
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
            # TENANT_001 should only see their own playbooks
            response = client.get(
                "/api/playbooks?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
            
            # TENANT_002 should only see their own playbooks
            response = client.get(
                "/api/playbooks?tenant_id=TENANT_002",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert all(item["tenantId"] == "TENANT_002" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_tenant_isolation_get(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced in get endpoint."""
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
            # Get TENANT_002's playbook ID
            list_response = client.get(
                "/api/playbooks?tenant_id=TENANT_002",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            assert list_response.status_code == 200
            playbooks = list_response.json()["items"]
            tenant2_playbook_id = playbooks[0]["playbookId"]
            
            # TENANT_001 should not be able to access TENANT_002's playbook
            response = client.get(
                f"/api/playbooks/{tenant2_playbook_id}?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            # Should return 404 because playbook doesn't belong to TENANT_001
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_missing_tenant_id(self, test_db_session, setup_test_data):
        """Test that missing tenant_id returns 400."""
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
            # List endpoint
            response = client.get(
                "/api/playbooks",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
            
            # Get endpoint
            response = client.get(
                "/api/playbooks/1",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
            
            # Create endpoint
            response = client.post(
                "/api/playbooks",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={
                    "name": "Test",
                    "version": 1,
                    "conditions": {},
                },
            )
            
            assert response.status_code == 400
        finally:
            session_module.get_db_session_context = original_get_context

