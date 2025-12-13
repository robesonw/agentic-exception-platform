"""
API tests for Playbook Recalculation endpoint (P7-8).

Tests cover:
- POST /api/exceptions/{exception_id}/playbook/recalculate
- Recalculation when no playbook was previously assigned
- Recalculation when the same playbook is selected again (idempotent)
- Tenant isolation enforcement
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
)
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.dto import ExceptionCreateOrUpdateDTO

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
    # SQLite requires separate execute calls for each statement
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
    """Set up test data with exceptions and playbooks."""
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
    
    # Create exception for TENANT_001 without playbook
    exception1 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-001",
        tenant_id="TENANT_001",
        domain="Finance",
        type="PaymentFailure",
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        source_system="PaymentGateway",
        entity="ACC-001",
        current_playbook_id=None,
        current_step=None,
    )
    await exception_repo.upsert_exception("TENANT_001", exception1)
    
    # Create exception for TENANT_001 with existing playbook
    exception2 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-002",
        tenant_id="TENANT_001",
        domain="Finance",
        type="PaymentFailure",
        severity=ExceptionSeverity.HIGH,
        status=ExceptionStatus.OPEN,
        source_system="PaymentGateway",
        entity="ACC-002",
        current_playbook_id=1,  # Will be created below
        current_step=2,
    )
    await exception_repo.upsert_exception("TENANT_001", exception2)
    
    # Create exception for TENANT_002
    exception3 = ExceptionCreateOrUpdateDTO(
        exception_id="EXC-003",
        tenant_id="TENANT_002",
        domain="Healthcare",
        type="PatientDataMismatch",
        severity=ExceptionSeverity.MEDIUM,
        status=ExceptionStatus.OPEN,
        source_system="EMR",
        entity="PAT-001",
        current_playbook_id=None,
        current_step=None,
    )
    await exception_repo.upsert_exception("TENANT_002", exception3)
    
    await test_db_session.commit()
    
    # Create playbooks for TENANT_001
    playbook1 = Playbook(
        tenant_id="TENANT_001",
        name="PaymentFailurePlaybook",
        version=1,
        conditions=json.dumps({
            "domain": "Finance",
            "exception_type": "PaymentFailure",
            "severity": "HIGH",
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
    test_db_session.add_all([step1, step2])
    
    # Create another playbook for TENANT_001 (lower priority)
    playbook2 = Playbook(
        tenant_id="TENANT_001",
        name="GenericFinancePlaybook",
        version=1,
        conditions=json.dumps({
            "domain": "Finance",
            "priority": 5,
        }),
        created_at=datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
    )
    test_db_session.add(playbook2)
    
    # Create playbook for TENANT_002
    playbook3 = Playbook(
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
    test_db_session.add(playbook3)
    
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


class TestPlaybookRecalculationAPI:
    """Tests for POST /exceptions/{exception_id}/playbook/recalculate endpoint."""

    @pytest.mark.asyncio
    async def test_recalculate_when_no_playbook_assigned(self, test_db_session, setup_test_data):
        """Test recalculation when no playbook was previously assigned."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.post(
                "/exceptions/TENANT_001/EXC-001/playbook/recalculate",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["exceptionId"] == "EXC-001"
            assert data["currentPlaybookId"] == 1  # Should match PaymentFailurePlaybook
            assert data["currentStep"] == 1
            assert data["playbookName"] == "PaymentFailurePlaybook"
            assert data["playbookVersion"] == 1
            assert data["reasoning"] is not None
            
            # Verify exception was updated in database
            exception_repo = ExceptionRepository(test_db_session)
            updated_exception = await exception_repo.get_exception("TENANT_001", "EXC-001")
            assert updated_exception.current_playbook_id == 1
            assert updated_exception.current_step == 1
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_recalculate_when_same_playbook_selected_idempotent(self, test_db_session, setup_test_data):
        """Test that recalculation is idempotent when same playbook is selected."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # First recalculation
            response1 = client.post(
                "/exceptions/TENANT_001/EXC-002/playbook/recalculate",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response1.status_code == 200
            data1 = response1.json()
            first_playbook_id = data1["currentPlaybookId"]
            first_step = data1["currentStep"]
            
            # Second recalculation (should result in same playbook)
            response2 = client.post(
                "/exceptions/TENANT_001/EXC-002/playbook/recalculate",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response2.status_code == 200
            data2 = response2.json()
            assert data2["currentPlaybookId"] == first_playbook_id
            assert data2["currentStep"] == first_step  # Should reset to 1
            
            # Verify exception was updated
            exception_repo = ExceptionRepository(test_db_session)
            updated_exception = await exception_repo.get_exception("TENANT_001", "EXC-002")
            assert updated_exception.current_playbook_id == first_playbook_id
            assert updated_exception.current_step == 1  # Should reset to first step
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_recalculate_tenant_isolation(self, test_db_session, setup_test_data):
        """Test that tenants cannot recalculate playbooks for other tenants' exceptions."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            # TENANT_001 should not be able to recalculate TENANT_002's exception
            response = client.post(
                "/exceptions/TENANT_001/EXC-003/playbook/recalculate",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
            
            # TENANT_002 should be able to recalculate their own exception
            response2 = client.post(
                "/exceptions/TENANT_002/EXC-003/playbook/recalculate",
                headers={"X-API-KEY": TENANT_002_API_KEY},
            )
            
            assert response2.status_code == 200
            data = response2.json()
            assert data["exceptionId"] == "EXC-003"
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_recalculate_nonexistent_exception(self, test_db_session, setup_test_data):
        """Test recalculation for non-existent exception."""
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.post(
                "/exceptions/TENANT_001/NONEXISTENT/playbook/recalculate",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context

    @pytest.mark.asyncio
    async def test_recalculate_missing_tenant_id(self, test_db_session, setup_test_data):
        """Test that missing tenant_id in path returns 404."""
        response = client.post(
            "/exceptions//EXC-001/playbook/recalculate",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 404  # Path not found

    @pytest.mark.asyncio
    async def test_recalculate_when_no_playbook_matches(self, test_db_session, setup_test_data):
        """Test recalculation when no playbook matches the exception."""
        import json
        
        # Create exception that won't match any playbook
        exception_repo = ExceptionRepository(test_db_session)
        exception_no_match = ExceptionCreateOrUpdateDTO(
            exception_id="EXC-NO-MATCH",
            tenant_id="TENANT_001",
            domain="UnknownDomain",
            type="UnknownType",
            severity=ExceptionSeverity.LOW,
            status=ExceptionStatus.OPEN,
            source_system="UnknownSystem",
            entity="UNK-001",
            current_playbook_id=None,
            current_step=None,
        )
        await exception_repo.upsert_exception("TENANT_001", exception_no_match)
        await test_db_session.commit()
        
        original_get_context = mock_db_session_context(test_db_session)
        
        try:
            response = client.post(
                "/exceptions/TENANT_001/EXC-NO-MATCH/playbook/recalculate",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["exceptionId"] == "EXC-NO-MATCH"
            assert data["currentPlaybookId"] is None
            assert data["currentStep"] is None
            assert data["playbookName"] is None
            assert data["playbookVersion"] is None
            assert data["reasoning"] is not None  # Should have reasoning even if no match
        finally:
            import src.infrastructure.db.session as session_module
            session_module.get_db_session_context = original_get_context


