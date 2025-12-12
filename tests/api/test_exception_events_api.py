"""
Tests for Exception Events API endpoint (P6-23).

Tests verify:
- Correct chronological ordering
- Filtering by event_type, actor_type, date_from/date_to
- Tenant isolation
- Pagination
"""

import pytest

pytestmark = pytest.mark.phase6
from datetime import datetime, timedelta, timezone
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
                sla_deadline TIMESTAMP WITH TIME ZONE,
                owner TEXT,
                current_playbook_id INTEGER,
                current_step INTEGER,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
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
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
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
    
    # Create exceptions
    now = datetime.now(timezone.utc)
    await test_db_session.execute(
        text(
            """
        INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status,
                              source_system, entity, amount, sla_deadline, created_at)
        VALUES ('EXC-001', 'TENANT_001', 'Finance', 'PaymentFailure', 'high', 'open',
                'PaymentGateway', 'ACC-001', NULL, NULL, :created_at)
        """
        ),
        {"created_at": now},
    )
    
    await test_db_session.execute(
        text(
            """
        INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status,
                              source_system, entity, amount, sla_deadline, created_at)
        VALUES ('EXC-002', 'TENANT_002', 'Healthcare', 'PatientDataMismatch', 'high', 'open',
                'EMR', 'PAT-001', NULL, NULL, :created_at)
        """
        ),
        {"created_at": now},
    )
    
    # Create events for EXC-001 (TENANT_001) - in chronological order
    events_data = [
        ("EVT-001", "EXC-001", "TENANT_001", "ExceptionCreated", "system", None, {"action": "created"}, now - timedelta(hours=4)),
        ("EVT-002", "EXC-001", "TENANT_001", "TriageCompleted", "agent", "triage_agent", {"decision": "triaged"}, now - timedelta(hours=3)),
        ("EVT-003", "EXC-001", "TENANT_001", "PolicyEvaluated", "agent", "policy_agent", {"decision": "approved"}, now - timedelta(hours=2)),
        ("EVT-004", "EXC-001", "TENANT_001", "ResolutionSuggested", "agent", "resolution_agent", {"action": "suggested"}, now - timedelta(hours=1)),
        ("EVT-005", "EXC-001", "TENANT_001", "ResolutionApproved", "user", "user_123", {"action": "approved"}, now),
    ]
    
    for event_data in events_data:
        await test_db_session.execute(
            text(
                """
            INSERT INTO exception_event (event_id, exception_id, tenant_id, event_type,
                                       actor_type, actor_id, payload, created_at)
            VALUES (:event_id, :exception_id, :tenant_id, :event_type,
                    :actor_type, :actor_id, :payload, :created_at)
            """
            ),
            {
                "event_id": event_data[0],
                "exception_id": event_data[1],
                "tenant_id": event_data[2],
                "event_type": event_data[3],
                "actor_type": event_data[4],
                "actor_id": event_data[5],
                "payload": json.dumps(event_data[6]),
                "created_at": event_data[7],
            },
        )
    
    # Create events for EXC-002 (TENANT_002)
    await test_db_session.execute(
        text(
            """
        INSERT INTO exception_event (event_id, exception_id, tenant_id, event_type,
                                   actor_type, actor_id, payload, created_at)
        VALUES ('EVT-006', 'EXC-002', 'TENANT_002', 'ExceptionCreated', 'system', NULL,
                :payload, :created_at)
        """
        ),
        {
            "payload": json.dumps({"action": "created"}),
            "created_at": now,
        },
    )
    
    await test_db_session.commit()


class TestExceptionEventsAPI:
    """Tests for GET /exceptions/{exception_id}/events endpoint."""

    @pytest.mark.asyncio
    async def test_get_events_basic(self, test_db_session, setup_test_data):
        """Test basic retrieval of events."""
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
            assert data["total"] == 5
            assert len(data["items"]) == 5
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_chronological_ordering(self, test_db_session, setup_test_data):
        """Test that events are returned in chronological order (oldest first)."""
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
                "/exceptions/EXC-001/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            items = data["items"]
            
            # Verify chronological order (oldest first)
            timestamps = [item["createdAt"] for item in items]
            assert timestamps == sorted(timestamps)
            
            # Verify first event is ExceptionCreated (oldest)
            assert items[0]["eventType"] == "ExceptionCreated"
            # Verify last event is ResolutionApproved (newest)
            assert items[-1]["eventType"] == "ResolutionApproved"
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_filter_by_event_type(self, test_db_session, setup_test_data):
        """Test filtering by event type."""
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
            # Filter by single event type
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&event_type=ExceptionCreated",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1
            assert data["items"][0]["eventType"] == "ExceptionCreated"
            
            # Filter by multiple event types (comma-separated)
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&event_type=TriageCompleted,PolicyEvaluated",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 2
            event_types = [item["eventType"] for item in data["items"]]
            assert "TriageCompleted" in event_types
            assert "PolicyEvaluated" in event_types
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_filter_by_actor_type(self, test_db_session, setup_test_data):
        """Test filtering by actor type."""
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
            # Filter by agent actor type
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&actor_type=agent",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 3  # 3 agent events
            assert all(item["actorType"] == "agent" for item in data["items"])
            
            # Filter by system actor type
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&actor_type=system",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 1  # 1 system event
            assert all(item["actorType"] == "system" for item in data["items"])
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_filter_by_date_range(self, test_db_session, setup_test_data):
        """Test filtering by date range."""
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
            from datetime import datetime, timezone, timedelta
            now = datetime.now(timezone.utc)
            
            # Filter by date_from (should get events from last 2 hours)
            date_from = (now - timedelta(hours=2)).isoformat()
            response = client.get(
                f"/exceptions/EXC-001/events?tenant_id=TENANT_001&date_from={date_from}",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should get events from last 2 hours (EVT-004 and EVT-005)
            assert data["total"] >= 2
            
            # Filter by date_to (should get events up to 3 hours ago)
            date_to = (now - timedelta(hours=3)).isoformat()
            response = client.get(
                f"/exceptions/EXC-001/events?tenant_id=TENANT_001&date_to={date_to}",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            # Should get events up to 3 hours ago (EVT-001 and EVT-002)
            assert data["total"] >= 2
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_pagination(self, test_db_session, setup_test_data):
        """Test pagination works correctly."""
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
            # First page
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&page=1&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["page"] == 1
            assert data["page_size"] == 2
            assert data["total"] == 5
            assert data["total_pages"] == 3
            
            # Second page
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&page=2&page_size=2",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["page"] == 2
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_tenant_isolation(self, test_db_session, setup_test_data):
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
            # TENANT_001 should only see their own exception events
            response = client.get(
                "/exceptions/EXC-001/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 5
            assert all(item["tenantId"] == "TENANT_001" for item in data["items"])
            
            # TENANT_001 should not be able to access TENANT_002's exception events
            response = client.get(
                "/exceptions/EXC-002/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            # Should return 404 because exception doesn't belong to TENANT_001
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_missing_tenant_id(self, test_db_session, setup_test_data):
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
            response = client.get(
                "/exceptions/EXC-001/events",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_invalid_actor_type(self, test_db_session, setup_test_data):
        """Test that invalid actor_type returns 400."""
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
                "/exceptions/EXC-001/events?tenant_id=TENANT_001&actor_type=invalid",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 400
        finally:
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_events_nonexistent_exception(self, test_db_session, setup_test_data):
        """Test that non-existent exception returns 404."""
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
                "/exceptions/NON-EXISTENT/events?tenant_id=TENANT_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
        finally:
            session_module.get_db_session_context = original_get_context

