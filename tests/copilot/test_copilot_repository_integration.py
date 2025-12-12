"""
Tests for Co-Pilot repository integration (P6-21).

Tests verify that Co-Pilot uses real database data via repositories:
- Similar-cases retrieval
- SLA at-risk retrieval
- Entity-based queries
- Tenant isolation
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.copilot.retrieval import (
    get_exception_by_id,
    get_exception_timeline,
    get_exceptions_by_entity,
    get_imminent_sla_breaches,
    get_recent_exceptions,
    get_similar_exceptions,
)
from src.infrastructure.db.models import (
    ActorType,
    Exception as ExceptionModel,
    ExceptionEvent,
    ExceptionSeverity,
    ExceptionStatus,
    Tenant,
    TenantStatus,
)

# Create test base
TestBase = declarative_base()


# Define minimal models for SQLite testing
class TestTenant(TestBase):
    __tablename__ = "tenant"
    tenant_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    status = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


class TestException(TestBase):
    __tablename__ = "exception"
    exception_id = Column(String, primary_key=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    domain = Column(String, nullable=False)
    type = Column(String, nullable=False)
    severity = Column(String, nullable=False)
    status = Column(String, nullable=False)
    source_system = Column(String, nullable=False)
    entity = Column(String, nullable=True)
    amount = Column(Numeric, nullable=True)
    sla_deadline = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


class TestExceptionEvent(TestBase):
    __tablename__ = "exception_event"
    event_id = Column(String, primary_key=True)
    exception_id = Column(String, ForeignKey("exception.exception_id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)
    actor_type = Column(String, nullable=False)
    actor_id = Column(String, nullable=True)
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite test engine."""
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
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS exception_event;"))
        await conn.execute(text("DROP TABLE IF EXISTS exception;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create an async session for tests."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def setup_tenants(test_session: AsyncSession):
    """Set up sample tenants for testing."""
    from sqlalchemy import text
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('tenant_001', 'Finance Tenant', 'active')")
    )
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name, status) VALUES ('tenant_002', 'Healthcare Tenant', 'active')")
    )
    await test_session.commit()


@pytest.fixture
async def setup_exceptions(test_session: AsyncSession, setup_tenants):
    """Set up sample exceptions for testing."""
    from sqlalchemy import text
    from datetime import datetime, timezone, timedelta
    
    now = datetime.now(timezone.utc)
    soon = now + timedelta(minutes=30)  # SLA deadline in 30 minutes
    
    # Tenant 001 exceptions
    exceptions_data = [
        ("EXC-001", "tenant_001", "Finance", "PaymentFailure", "high", "open", "PaymentGateway", "ACC-001", None, None, now),
        ("EXC-002", "tenant_001", "Finance", "PaymentFailure", "high", "open", "PaymentGateway", "ACC-001", None, soon, now),
        ("EXC-003", "tenant_001", "Finance", "FraudAlert", "critical", "open", "FraudDetection", "ACC-002", 1000.0, None, now),
        ("EXC-004", "tenant_001", "Finance", "ReconciliationMismatch", "medium", "analyzing", "AccountingSystem", "ACC-003", 50.0, None, now),
        ("EXC-005", "tenant_001", "Finance", "PaymentFailure", "high", "open", "PaymentGateway", "ACC-004", None, None, now),
    ]
    
    for exc_data in exceptions_data:
        await test_session.execute(
            text(
                """
            INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status, 
                                  source_system, entity, amount, sla_deadline, created_at)
            VALUES (:exception_id, :tenant_id, :domain, :type, :severity, :status,
                    :source_system, :entity, :amount, :sla_deadline, :created_at)
            """
            ),
            {
                "exception_id": exc_data[0],
                "tenant_id": exc_data[1],
                "domain": exc_data[2],
                "type": exc_data[3],
                "severity": exc_data[4],
                "status": exc_data[5],
                "source_system": exc_data[6],
                "entity": exc_data[7],
                "amount": exc_data[8],
                "sla_deadline": exc_data[9],
                "created_at": exc_data[10],
            },
        )
    
    # Tenant 002 exceptions
    await test_session.execute(
        text(
            """
        INSERT INTO exception (exception_id, tenant_id, domain, type, severity, status, 
                              source_system, entity, amount, sla_deadline, created_at)
        VALUES ('HC-EXC-001', 'tenant_002', 'Healthcare', 'PatientDataMismatch', 'high', 'open',
                'EMR', 'PAT-001', NULL, NULL, :created_at)
        """
        ),
        {"created_at": now},
    )
    
    await test_session.commit()


@pytest.fixture
async def setup_events(test_session: AsyncSession, setup_exceptions):
    """Set up sample events for testing."""
    from sqlalchemy import text
    from datetime import datetime, timezone
    
    now = datetime.now(timezone.utc)
    
    events_data = [
        ("EVT-001", "EXC-001", "tenant_001", "ExceptionCreated", "system", None, {"action": "created"}),
        ("EVT-002", "EXC-001", "tenant_001", "TriageCompleted", "agent", "triage_agent", {"decision": "triaged"}),
        ("EVT-003", "EXC-002", "tenant_001", "ExceptionCreated", "system", None, {"action": "created"}),
    ]
    
    for event_data in events_data:
        import json
        await test_session.execute(
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
                "created_at": now,
            },
        )
    
    await test_session.commit()


class TestCopilotRepositoryIntegration:
    """Test Co-Pilot repository integration."""

    @pytest.mark.asyncio
    async def test_get_exception_by_id(self, test_session: AsyncSession, setup_exceptions):
        """Test retrieving exception by ID using repository."""
        exception = await get_exception_by_id(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            exception_id="EXC-001",
        )
        
        assert exception is not None
        assert exception["exceptionId"] == "EXC-001"
        assert exception["tenantId"] == "tenant_001"
        assert exception["normalizedContext"]["domain"] == "Finance"
        
        # Should return None for non-existent exception
        not_found = await get_exception_by_id(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            exception_id="NON-EXISTENT",
        )
        assert not_found is None

    @pytest.mark.asyncio
    async def test_get_recent_exceptions(self, test_session: AsyncSession, setup_exceptions):
        """Test retrieving recent exceptions using repository."""
        exceptions = await get_recent_exceptions(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            limit=5,
        )
        
        assert len(exceptions) == 5
        assert all(exc["tenantId"] == "tenant_001" for exc in exceptions)
        assert all(exc["normalizedContext"]["domain"] == "Finance" for exc in exceptions)
        
        # Should be ordered by timestamp (newest first)
        timestamps = [exc["timestamp"] for exc in exceptions]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_get_similar_exceptions(self, test_session: AsyncSession, setup_exceptions):
        """Test finding similar exceptions using repository."""
        # Find similar PaymentFailure exceptions
        similar = await get_similar_exceptions(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            exception_type="PaymentFailure",
            limit=10,
        )
        
        assert len(similar) == 3  # EXC-001, EXC-002, EXC-005
        assert all(exc["exceptionType"] == "PaymentFailure" for exc in similar)
        assert all(exc["tenantId"] == "tenant_001" for exc in similar)
        
        # Find similar by domain only
        similar_domain = await get_similar_exceptions(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            limit=10,
        )
        
        assert len(similar_domain) == 5  # All Finance exceptions

    @pytest.mark.asyncio
    async def test_get_exceptions_by_entity(self, test_session: AsyncSession, setup_exceptions):
        """Test retrieving exceptions by entity using repository."""
        exceptions = await get_exceptions_by_entity(
            session=test_session,
            tenant_id="tenant_001",
            entity="ACC-001",
            limit=50,
        )
        
        assert len(exceptions) == 2  # EXC-001, EXC-002
        assert all(exc["normalizedContext"]["entity"] == "ACC-001" for exc in exceptions)
        assert all(exc["tenantId"] == "tenant_001" for exc in exceptions)

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches(self, test_session: AsyncSession, setup_exceptions):
        """Test retrieving imminent SLA breaches using repository."""
        breaches = await get_imminent_sla_breaches(
            session=test_session,
            tenant_id="tenant_001",
            within_minutes=60,
            limit=100,
        )
        
        # EXC-002 has SLA deadline in 30 minutes
        assert len(breaches) >= 1
        assert any(exc["exceptionId"] == "EXC-002" for exc in breaches)
        assert all(exc["tenantId"] == "tenant_001" for exc in breaches)

    @pytest.mark.asyncio
    async def test_get_exception_timeline(self, test_session: AsyncSession, setup_exceptions, setup_events):
        """Test retrieving exception timeline using repository."""
        timeline = await get_exception_timeline(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            exception_id="EXC-001",
        )
        
        assert timeline is not None
        assert timeline["exceptionId"] == "EXC-001"
        assert timeline["tenantId"] == "tenant_001"
        assert "eventTimeline" in timeline
        assert len(timeline["eventTimeline"]) == 2  # EVT-001, EVT-002

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, test_session: AsyncSession, setup_exceptions):
        """Test that tenant isolation is enforced in all repository calls."""
        # Tenant 001 should only see their own exceptions
        tenant1_exceptions = await get_recent_exceptions(
            session=test_session,
            tenant_id="tenant_001",
            domain=None,
            limit=100,
        )
        assert all(exc["tenantId"] == "tenant_001" for exc in tenant1_exceptions)
        assert len(tenant1_exceptions) == 5
        
        # Tenant 002 should only see their own exceptions
        tenant2_exceptions = await get_recent_exceptions(
            session=test_session,
            tenant_id="tenant_002",
            domain=None,
            limit=100,
        )
        assert all(exc["tenantId"] == "tenant_002" for exc in tenant2_exceptions)
        assert len(tenant2_exceptions) == 1
        
        # Tenant 001 should not be able to retrieve tenant_002's exceptions
        tenant2_exception = await get_exception_by_id(
            session=test_session,
            tenant_id="tenant_001",
            domain=None,
            exception_id="HC-EXC-001",
        )
        assert tenant2_exception is None  # Should return None due to tenant isolation

    @pytest.mark.asyncio
    async def test_similar_exceptions_tenant_isolation(self, test_session: AsyncSession, setup_exceptions):
        """Test tenant isolation in similar exceptions retrieval."""
        # Tenant 001 should only see their own similar exceptions
        similar = await get_similar_exceptions(
            session=test_session,
            tenant_id="tenant_001",
            domain="Finance",
            exception_type="PaymentFailure",
            limit=10,
        )
        assert all(exc["tenantId"] == "tenant_001" for exc in similar)
        
        # Tenant 002 should not see tenant_001's exceptions
        similar_tenant2 = await get_similar_exceptions(
            session=test_session,
            tenant_id="tenant_002",
            domain="Finance",
            exception_type="PaymentFailure",
            limit=10,
        )
        assert len(similar_tenant2) == 0  # No PaymentFailure exceptions for tenant_002

    @pytest.mark.asyncio
    async def test_entity_queries_tenant_isolation(self, test_session: AsyncSession, setup_exceptions):
        """Test tenant isolation in entity-based queries."""
        # Tenant 001 should only see their own entity exceptions
        exceptions = await get_exceptions_by_entity(
            session=test_session,
            tenant_id="tenant_001",
            entity="ACC-001",
            limit=50,
        )
        assert all(exc["tenantId"] == "tenant_001" for exc in exceptions)
        assert all(exc["normalizedContext"]["entity"] == "ACC-001" for exc in exceptions)
        
        # Tenant 002 should not see tenant_001's entity exceptions
        tenant2_exceptions = await get_exceptions_by_entity(
            session=test_session,
            tenant_id="tenant_002",
            entity="ACC-001",
            limit=50,
        )
        assert len(tenant2_exceptions) == 0  # No ACC-001 exceptions for tenant_002

    @pytest.mark.asyncio
    async def test_sla_breaches_tenant_isolation(self, test_session: AsyncSession, setup_exceptions):
        """Test tenant isolation in SLA breach queries."""
        # Tenant 001 should only see their own SLA breaches
        breaches = await get_imminent_sla_breaches(
            session=test_session,
            tenant_id="tenant_001",
            within_minutes=60,
            limit=100,
        )
        assert all(exc["tenantId"] == "tenant_001" for exc in breaches)
        
        # Tenant 002 should not see tenant_001's SLA breaches
        tenant2_breaches = await get_imminent_sla_breaches(
            session=test_session,
            tenant_id="tenant_002",
            within_minutes=60,
            limit=100,
        )
        # Tenant 002 has no exceptions with SLA deadlines
        assert len(tenant2_breaches) == 0


