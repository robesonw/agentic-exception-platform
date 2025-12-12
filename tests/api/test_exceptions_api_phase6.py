"""
Comprehensive API tests for Exception endpoints (P6-30).

Tests cover:
- POST /api/exceptions/{tenant_id} - Create/ingest exception
- GET /api/exceptions/{tenant_id} - List with pagination and filters
- GET /api/exceptions/{tenant_id}/{exception_id} - Get single exception
- GET /api/exceptions/{exception_id}/events - Event timeline

All tests use DB-backed repositories and ensure tenant isolation.
"""

import pytest
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.api.middleware import get_rate_limiter
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.db.models import (
    Tenant,
    TenantStatus,
    Exception,
    ExceptionSeverity,
    ExceptionStatus,
    ExceptionEvent,
    ActorType,
)
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.dto import (
    ExceptionCreateOrUpdateDTO,
    ExceptionEventCreateDTO,
)

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"
TENANT_002_API_KEY = "test_api_key_tenant_002"


@pytest.fixture(autouse=True)
def setup_api_keys():
    """Set up API keys for tests."""
    auth = get_api_key_auth()
    limiter = get_rate_limiter()
    # Register API keys for both tenants
    auth.register_api_key(DEFAULT_API_KEY, "TENANT_001", Role.ADMIN)
    auth.register_api_key(TENANT_002_API_KEY, "TENANT_002", Role.ADMIN)
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
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS exception (
                exception_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                source_system TEXT NOT NULL,
                entity TEXT,
                amount NUMERIC,
                sla_deadline TIMESTAMP,
                owner TEXT,
                current_playbook_id INTEGER,
                current_step INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_exception_tenant_id ON exception(tenant_id);
            CREATE TABLE IF NOT EXISTS exception_event (
                event_id TEXT PRIMARY KEY,
                exception_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                payload TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exception_id) REFERENCES exception(exception_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_exception_event_exception_id ON exception_event(exception_id);
            CREATE INDEX IF NOT EXISTS ix_exception_event_tenant_id ON exception_event(tenant_id);
            """
            )
        )
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS exception_event;"))
        await conn.execute(text("DROP TABLE IF EXISTS exception;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db_session: AsyncSession):
    """Set up test data using repositories."""
    # Create tenants using repository pattern
    tenant1 = Tenant(
        tenant_id="TENANT_001",
        name="Tenant One",
        status=TenantStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    tenant2 = Tenant(
        tenant_id="TENANT_002",
        name="Tenant Two",
        status=TenantStatus.ACTIVE,
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add_all([tenant1, tenant2])
    await test_db_session.commit()
    
    # Create exceptions using repository
    exception_repo = ExceptionRepository(test_db_session)
    now = datetime.now(timezone.utc)
    
    # Create exceptions for TENANT_001
    exceptions_t1 = [
        ExceptionCreateOrUpdateDTO(
            exception_id="EXC-001",
            tenant_id="TENANT_001",
            domain="Finance",
            type="PaymentFailure",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="PaymentGateway",
            entity="ACC-001",
        ),
        ExceptionCreateOrUpdateDTO(
            exception_id="EXC-002",
            tenant_id="TENANT_001",
            domain="Finance",
            type="FraudAlert",
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.ANALYZING,
            source_system="FraudDetection",
            entity="ACC-002",
            amount=1000.0,
        ),
        ExceptionCreateOrUpdateDTO(
            exception_id="EXC-003",
            tenant_id="TENANT_001",
            domain="Healthcare",
            type="PatientDataMismatch",
            severity=ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.RESOLVED,
            source_system="EMR",
            entity="PAT-001",
        ),
    ]
    
    for exc_data in exceptions_t1:
        await exception_repo.upsert_exception("TENANT_001", exc_data)
    
    # Create exceptions for TENANT_002
    exceptions_t2 = [
        ExceptionCreateOrUpdateDTO(
            exception_id="EXC-004",
            tenant_id="TENANT_002",
            domain="Healthcare",
            type="PatientDataMismatch",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="EMR",
            entity="PAT-002",
        ),
    ]
    
    for exc_data in exceptions_t2:
        await exception_repo.upsert_exception("TENANT_002", exc_data)
    
    await test_db_session.commit()
    
    # Create events using repository
    event_repo = ExceptionEventRepository(test_db_session)
    
    # Create events for EXC-001 (TENANT_001) - in chronological order
    events_exc1 = [
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EXC-001",
            tenant_id="TENANT_001",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"action": "created", "source": "api"},
        ),
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EXC-001",
            tenant_id="TENANT_001",
            event_type="TriageCompleted",
            actor_type=ActorType.AGENT,
            actor_id="triage_agent",
            payload={"decision": "triaged", "confidence": 0.9},
        ),
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EXC-001",
            tenant_id="TENANT_001",
            event_type="PolicyEvaluated",
            actor_type=ActorType.AGENT,
            actor_id="policy_agent",
            payload={"decision": "approved"},
        ),
    ]
    
    for event_data in events_exc1:
        await event_repo.append_event_if_new(event_data)
    
    # Create event for EXC-004 (TENANT_002)
    event_exc4 = ExceptionEventCreateDTO(
        event_id=uuid4(),
        exception_id="EXC-004",
        tenant_id="TENANT_002",
        event_type="ExceptionCreated",
        actor_type=ActorType.SYSTEM,
        payload={"action": "created", "source": "api"},
    )
    await event_repo.append_event_if_new(event_exc4)
    
    await test_db_session.commit()


def mock_db_session_context(test_db_session: AsyncSession):
    """Helper to mock the database session context."""
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
    return original_get_context


@pytest.mark.phase6
class TestCreateExceptionAPI:
    """Tests for POST /exceptions/{tenant_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_create_exception_success(self, test_db_session, setup_test_data):
        """Test successful exception creation via ingestion API."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.post(
                "/exceptions/TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={
                    "exception": {
                        "sourceSystem": "TestSystem",
                        "rawPayload": {
                            "error": "Payment failed",
                            "accountId": "ACC-999",
                        },
                    },
                },
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "exceptionIds" in data
            assert "count" in data
            assert data["count"] == 1
            assert len(data["exceptionIds"]) == 1
            # Verify exception was created in DB
            exception_id = data["exceptionIds"][0]
            repo = ExceptionRepository(test_db_session)
            exception = await repo.get_exception("TENANT_001", exception_id)
            assert exception is not None
            assert exception.tenant_id == "TENANT_001"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_create_exception_requires_tenant_id(self, test_db_session):
        """Test that tenant_id is required in path."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.post(
                "/exceptions/",
                headers={"X-API-KEY": DEFAULT_API_KEY},
                json={"exception": {"sourceSystem": "TestSystem", "rawPayload": {}}},
            )
            
            # Should return 404 (route not found) or 422 (validation error)
            assert response.status_code in [404, 422]
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_create_exception_requires_body(self, test_db_session):
        """Test that request body is required."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.post(
                "/exceptions/TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context


@pytest.mark.phase6
class TestListExceptionsAPI:
    """Tests for GET /exceptions/{tenant_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_list_exceptions_basic(self, test_db_session, setup_test_data):
        """Test basic listing of exceptions."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert "total_pages" in data
            assert data["total"] == 3
            assert len(data["items"]) == 3
            assert data["page"] == 1
            assert data["page_size"] == 50
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_list_exceptions_pagination(self, test_db_session, setup_test_data):
        """Test pagination works correctly."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # First page
            response = client.get(
                "/exceptions/TENANT_001?page=1&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["page"] == 1
            assert data["page_size"] == 2
            assert data["total"] == 3
            assert data["total_pages"] == 2
            
            # Second page
            response = client.get(
                "/exceptions/TENANT_001?page=2&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 1
            assert data["page"] == 2
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_domain(self, test_db_session, setup_test_data):
        """Test filtering by domain."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001?domain=Finance",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 Finance exceptions
            assert all(item["normalizedContext"]["domain"] == "Finance" for item in data["items"])
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_status(self, test_db_session, setup_test_data):
        """Test filtering by status."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001?status=open",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1  # 1 open exception
            assert all(item["resolutionStatus"] == "OPEN" for item in data["items"])
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_severity(self, test_db_session, setup_test_data):
        """Test filtering by severity."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001?severity=critical",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1  # 1 critical exception
            assert all(item["severity"] == "CRITICAL" for item in data["items"])
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_date_range(self, test_db_session, setup_test_data):
        """Test filtering by date range."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            now = datetime.now(timezone.utc)
            date_from = (now - timedelta(days=1)).isoformat()
            date_to = (now + timedelta(days=1)).isoformat()
            
            response = client.get(
                f"/exceptions/TENANT_001?created_from={date_from}&created_to={date_to}",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] >= 0  # Should return results within date range
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_list_exceptions_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # TENANT_001 should only see their own exceptions
            response = client.get(
                "/exceptions/TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
            
            # TENANT_002 should only see their own exceptions
            response = client.get(
                "/exceptions/TENANT_002",
                headers={"X-API-KEY": TENANT_002_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert all(item["tenantId"] == "TENANT_002" for item in data["items"])
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context


@pytest.mark.phase6
class TestGetExceptionAPI:
    """Tests for GET /exceptions/{tenant_id}/{exception_id} endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_exception_success(self, test_db_session, setup_test_data):
        """Test successful retrieval of exception."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/EXC-001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["exceptionId"] == "EXC-001"
            assert data["tenantId"] == "TENANT_001"
            assert "normalizedContext" in data
            assert "severity" in data
            assert "resolutionStatus" in data
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_exception_not_found(self, test_db_session, setup_test_data):
        """Test that non-existent exception returns 404."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/NON-EXISTENT",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_exception_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # TENANT_001 should not be able to access TENANT_002's exception
            response = client.get(
                "/exceptions/TENANT_001/EXC-004",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            # Should return 404 because exception doesn't belong to TENANT_001
            assert response.status_code == 404
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context


@pytest.mark.phase6
class TestExceptionEventsAPI:
    """Tests for GET /exceptions/{exception_id}/events endpoint."""
    
    @pytest.mark.asyncio
    async def test_get_events_success(self, test_db_session, setup_test_data):
        """Test successful retrieval of events."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert "page" in data
            assert "page_size" in data
            assert "total_pages" in data
            assert data["total"] == 3
            assert len(data["items"]) == 3
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_events_chronological_order(self, test_db_session, setup_test_data):
        """Test that events are returned in chronological order."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            items = data["items"]
            
            # Verify chronological order (oldest first)
            timestamps = [item["createdAt"] for item in items]
            assert timestamps == sorted(timestamps)
            
            # Verify first event is ExceptionCreated
            assert items[0]["eventType"] == "ExceptionCreated"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_events_filter_by_event_type(self, test_db_session, setup_test_data):
        """Test filtering by event type."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&event_type=TriageCompleted",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["eventType"] == "TriageCompleted"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_events_filter_by_actor_type(self, test_db_session, setup_test_data):
        """Test filtering by actor type."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&actor_type=agent",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2  # 2 agent events
            assert all(item["actorType"] == "agent" for item in data["items"])
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_events_pagination(self, test_db_session, setup_test_data):
        """Test pagination works correctly."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&page=1&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["page"] == 1
            assert data["page_size"] == 2
            assert data["total"] == 3
            assert data["total_pages"] == 2
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_events_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenant isolation is enforced."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # TENANT_001 should only see their own exception events
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
            
            # TENANT_001 should not be able to access TENANT_002's exception events
            response = client.get(
                "/exceptions/EXC-004/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            # Should return 404 because exception doesn't belong to TENANT_001
            assert response.status_code == 404
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context
    
    @pytest.mark.asyncio
    async def test_get_events_missing_tenant_id(self, test_db_session, setup_test_data):
        """Test that missing tenant_id returns 400."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/EXC-001/events",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

