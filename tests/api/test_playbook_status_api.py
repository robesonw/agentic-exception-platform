"""
API tests for Playbook Status endpoint (P7-9).

Tests cover:
- GET /exceptions/{tenant_id}/{exception_id}/playbook
- Exception with an active playbook
- Exception with a completed playbook
- Exception with no playbook
- Correct status derivation from events
- Tenant isolation and error responses
"""

import pytest
from datetime import datetime, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.api.middleware import get_rate_limiter
from src.infrastructure.db.models import (
    Tenant,
    TenantStatus,
    Exception,
    ExceptionSeverity,
    ExceptionStatus,
    Playbook,
    PlaybookStep,
    ExceptionEvent,
    ActorType,
)
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.dto import ExceptionCreateOrUpdateDTO, ExceptionEventCreateDTO

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
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tenant (tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT NOT NULL, created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP);"))
        await conn.execute(
            text(
                """
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
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exception_tenant_id ON exception(tenant_id);"))
        await conn.execute(
            text(
                """
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
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exception_event_exception_id ON exception_event(exception_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_exception_event_tenant_id ON exception_event(tenant_id);"))
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS playbook (
                playbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                conditions TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_playbook_tenant_id ON playbook(tenant_id);"))
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS playbook_step (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                playbook_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                params TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (playbook_id) REFERENCES playbook(playbook_id) ON DELETE CASCADE
            );
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_playbook_step_playbook_id ON playbook_step(playbook_id);"))
    
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        yield session
    
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS playbook_step;"))
        await conn.execute(text("DROP TABLE IF EXISTS playbook;"))
        await conn.execute(text("DROP TABLE IF EXISTS exception_event;"))
        await conn.execute(text("DROP TABLE IF EXISTS exception;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def setup_test_data(test_db_session: AsyncSession):
    """Set up test data with exceptions, playbooks, and events."""
    import json
    
    # Create tenants
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
    
    # Exception with active playbook (step 2 of 3)
    exception1 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-001",
        tenant_id="TENANT_001",
        domain="Finance",
        type="PaymentFailure",
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        source_system="PaymentGateway",
        entity="ACC-001",
        current_playbook_id=1,
        current_step=2,
    )
    await exception_repo.upsert_exception("TENANT_001", exception1)
    
    # Exception with completed playbook
    exception2 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-002",
        tenant_id="TENANT_001",
        domain="Finance",
        type="PaymentFailure",
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        source_system="PaymentGateway",
        entity="ACC-002",
        current_playbook_id=1,
        current_step=None,  # Completed
    )
    await exception_repo.upsert_exception("TENANT_001", exception2)
    
    # Exception with no playbook
    exception3 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-003",
        tenant_id="TENANT_001",
        domain="Finance",
        type="PaymentFailure",
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        source_system="PaymentGateway",
        entity="ACC-003",
        current_playbook_id=None,
        current_step=None,
    )
    await exception_repo.upsert_exception("TENANT_001", exception3)
    
    # Exception for TENANT_002
    exception4 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-004",
        tenant_id="TENANT_002",
        domain="Healthcare",
        type="PatientDataMismatch",
        severity=ExceptionSeverity.MEDIUM,
        status=ExceptionStatus.OPEN,
        source_system="EMR",
        entity="PAT-001",
        current_playbook_id=2,
        current_step=1,
    )
    await exception_repo.upsert_exception("TENANT_002", exception4)
    
    await test_db_session.commit()
    
    # Create playbooks
    playbook1 = Playbook(
        tenant_id="TENANT_001",
        name="PaymentFailurePlaybook",
        version=1,
        conditions=json.dumps({
            "domain": "Finance",
            "exception_type": "PaymentFailure",
            "priority": 10,
        }),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(playbook1)
    await test_db_session.flush()
    await test_db_session.refresh(playbook1)
    
    # Create steps for playbook1
    step1 = PlaybookStep(
        playbook_id=playbook1.playbook_id,
        step_order=1,
        name="Notify Team",
        action_type="notify",
        params=json.dumps({"message": "Payment failure detected"}),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    step2 = PlaybookStep(
        playbook_id=playbook1.playbook_id,
        step_order=2,
        name="Assign Owner",
        action_type="assign_owner",
        params=json.dumps({"queue": "Payments"}),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    step3 = PlaybookStep(
        playbook_id=playbook1.playbook_id,
        step_order=3,
        name="Escalate",
        action_type="escalate",
        params=json.dumps({"level": "manager"}),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add_all([step1, step2, step3])
    
    # Create playbook for TENANT_002
    playbook2 = Playbook(
        tenant_id="TENANT_002",
        name="PatientDataMismatchPlaybook",
        version=1,
        conditions=json.dumps({
            "domain": "Healthcare",
            "exception_type": "PatientDataMismatch",
            "priority": 10,
        }),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(playbook2)
    await test_db_session.flush()
    await test_db_session.refresh(playbook2)
    
    step4 = PlaybookStep(
        playbook_id=playbook2.playbook_id,
        step_order=1,
        name="Validate Data",
        action_type="validate",
        params=json.dumps({}),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(step4)
    
    await test_db_session.commit()
    
    # Create events for EXC-001 (active playbook, step 2)
    event_repo = ExceptionEventRepository(test_db_session)
    
    # PlaybookStarted event
    event1 = ExceptionEventCreateDTO(
        event_id=uuid4(),
        exception_id="EXC-001",
        tenant_id="TENANT_001",
        event_type="PlaybookStarted",
        actor_type=ActorType.AGENT,
        actor_id="ResolutionAgent",
        payload={
            "playbook_id": 1,
            "playbook_name": "PaymentFailurePlaybook",
            "playbook_version": 1,
            "total_steps": 3,
        },
    )
    await event_repo.append_event("TENANT_001", event1)
    
    # PlaybookStepCompleted for step 1
    event2 = ExceptionEventCreateDTO(
        event_id=uuid4(),
        exception_id="EXC-001",
        tenant_id="TENANT_001",
        event_type="PlaybookStepCompleted",
        actor_type=ActorType.AGENT,
        actor_id="ResolutionAgent",
        payload={
            "playbook_id": 1,
            "step_id": step1.step_id,
            "step_order": 1,
            "step_name": "Notify Team",
            "action_type": "notify",
            "is_last_step": False,
        },
    )
    await event_repo.append_event("TENANT_001", event2)
    
    # Create events for EXC-002 (completed playbook)
    event3 = ExceptionEventCreateDTO(
        event_id=uuid4(),
        exception_id="EXC-002",
        tenant_id="TENANT_001",
        event_type="PlaybookStarted",
        actor_type=ActorType.AGENT,
        actor_id="ResolutionAgent",
        payload={
            "playbook_id": 1,
            "playbook_name": "PaymentFailurePlaybook",
            "playbook_version": 1,
            "total_steps": 3,
        },
    )
    await event_repo.append_event("TENANT_001", event3)
    
    # All steps completed
    for step_order, step in [(1, step1), (2, step2), (3, step3)]:
        event = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EXC-002",
            tenant_id="TENANT_001",
            event_type="PlaybookStepCompleted",
            actor_type=ActorType.AGENT,
            actor_id="ResolutionAgent",
            payload={
                "playbook_id": 1,
                "step_id": step.step_id,
                "step_order": step_order,
                "step_name": step.name,
                "action_type": step.action_type,
                "is_last_step": (step_order == 3),
            },
        )
        await event_repo.append_event("TENANT_001", event)
    
    # PlaybookCompleted event
    event4 = ExceptionEventCreateDTO(
        event_id=uuid4(),
        exception_id="EXC-002",
        tenant_id="TENANT_001",
        event_type="PlaybookCompleted",
        actor_type=ActorType.AGENT,
        actor_id="ResolutionAgent",
        payload={
            "playbook_id": 1,
            "total_steps": 3,
        },
    )
    await event_repo.append_event("TENANT_001", event4)
    
    await test_db_session.commit()


def mock_db_session_context(test_db_session: AsyncSession):
    """Helper to mock the database session context."""
    import src.infrastructure.db.session as session_module
    from contextlib import asynccontextmanager
    
    original_get_context = session_module.get_db_session_context
    
    @asynccontextmanager
    async def mock_get_context():
        yield test_db_session
    
    session_module.get_db_session_context = mock_get_context
    return original_get_context


class TestPlaybookStatusAPI:
    """Tests for GET /exceptions/{tenant_id}/{exception_id}/playbook endpoint."""

    @pytest.mark.asyncio
    async def test_get_status_active_playbook(self, test_db_session, setup_test_data):
        """Test getting status for exception with active playbook."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/EXC-001/playbook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["exceptionId"] == "EXC-001"
            assert data["playbookId"] == 1
            assert data["playbookName"] == "PaymentFailurePlaybook"
            assert data["playbookVersion"] == 1
            assert data["currentStep"] == 2
            assert len(data["steps"]) == 3
            
            # Check step statuses
            steps = {s["stepOrder"]: s for s in data["steps"]}
            assert steps[1]["status"] == "completed"  # Step 1 completed
            assert steps[2]["status"] == "pending"  # Step 2 is current (pending)
            assert steps[3]["status"] == "pending"  # Step 3 not started
            
            assert steps[1]["name"] == "Notify Team"
            assert steps[1]["actionType"] == "notify"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_status_completed_playbook(self, test_db_session, setup_test_data):
        """Test getting status for exception with completed playbook."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/EXC-002/playbook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["exceptionId"] == "EXC-002"
            assert data["playbookId"] == 1
            assert data["currentStep"] is None  # Completed
            assert len(data["steps"]) == 3
            
            # All steps should be completed
            for step in data["steps"]:
                assert step["status"] == "completed"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_status_no_playbook(self, test_db_session, setup_test_data):
        """Test getting status for exception with no playbook."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/EXC-003/playbook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["exceptionId"] == "EXC-003"
            assert data["playbookId"] is None
            assert data["playbookName"] is None
            assert data["playbookVersion"] is None
            assert data["currentStep"] is None
            assert len(data["steps"]) == 0
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_status_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenants cannot access other tenants' playbook status."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # TENANT_001 should not be able to access TENANT_002's exception
            response = client.get(
                "/exceptions/TENANT_001/EXC-004/playbook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            
            # TENANT_002 should be able to access their own exception
            response2 = client.get(
                "/exceptions/TENANT_002/EXC-004/playbook",
                headers={"X-API-KEY": TENANT_002_API_KEY},
            )
            
            assert response2.status_code == 200
            data = response2.json()
            assert data["exceptionId"] == "EXC-004"
            assert data["playbookId"] == 2
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_status_nonexistent_exception(self, test_db_session, setup_test_data):
        """Test getting status for non-existent exception."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/NONEXISTENT/playbook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_get_status_conditions_included(self, test_db_session, setup_test_data):
        """Test that playbook conditions are included in response."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.get(
                "/exceptions/TENANT_001/EXC-001/playbook",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "conditions" in data
            assert data["conditions"] is not None
            assert "domain" in data["conditions"]
            assert data["conditions"]["domain"] == "Finance"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context












