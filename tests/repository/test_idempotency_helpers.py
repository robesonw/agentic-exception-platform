"""
Tests for idempotency helpers in repositories.

Tests Phase 6 P6-5: Idempotent writes and event deduplication.
"""

from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infrastructure.db.models import ActorType, ExceptionSeverity, ExceptionStatus
from src.repository.dto import ExceptionCreateOrUpdateDTO, ExceptionEventDTO
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository

# Import models for testing
from src.infrastructure.db.models import Exception, ExceptionEvent

# Create test base
TestBase = declarative_base()


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite test engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables (using actual models)
    async with engine.begin() as conn:
        # We need to create the tables for Exception and ExceptionEvent
        # For SQLite, we'll create simplified versions
        await conn.run_sync(TestBase.metadata.create_all)
        
        # Create Exception table manually for SQLite compatibility
        await conn.execute(
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
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exception_event (
                event_id TEXT PRIMARY KEY,
                exception_id TEXT NOT NULL,
                tenant_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                actor_type TEXT NOT NULL,
                actor_id TEXT,
                payload TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    
    yield engine
    
    # Cleanup
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test session."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


class TestExceptionRepositoryIdempotency:
    """Test idempotency of ExceptionRepository.upsert_exception."""

    @pytest.mark.asyncio
    async def test_upsert_exception_creates_new(self, test_session):
        """Test that upsert_exception creates a new exception when it doesn't exist."""
        repo = ExceptionRepository(test_session)
        
        exception_data = ExceptionCreateOrUpdateDTO(
            exception_id="EX-001",
            tenant_id="tenant_1",
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        
        result = await repo.upsert_exception("tenant_1", exception_data)
        
        assert result is not None
        assert result.exception_id == "EX-001"
        assert result.tenant_id == "tenant_1"
        assert result.domain == "TestDomain"
        
        # Verify it was actually created in DB
        query = select(Exception).where(Exception.exception_id == "EX-001")
        db_result = await test_session.execute(query)
        db_exception = db_result.scalar_one_or_none()
        
        assert db_exception is not None
        assert db_exception.exception_id == "EX-001"

    @pytest.mark.asyncio
    async def test_upsert_exception_idempotent_create(self, test_session):
        """Test that calling upsert_exception twice with same data doesn't create duplicates."""
        repo = ExceptionRepository(test_session)
        
        exception_data = ExceptionCreateOrUpdateDTO(
            exception_id="EX-002",
            tenant_id="tenant_1",
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        
        # First call - should create
        result1 = await repo.upsert_exception("tenant_1", exception_data)
        await test_session.commit()
        
        # Second call with same data - should update, not create duplicate
        result2 = await repo.upsert_exception("tenant_1", exception_data)
        await test_session.commit()
        
        # Verify only one row exists
        query = select(Exception).where(Exception.exception_id == "EX-002")
        db_result = await test_session.execute(query)
        all_exceptions = db_result.scalars().all()
        
        assert len(all_exceptions) == 1
        assert result1.exception_id == result2.exception_id
        assert result1.tenant_id == result2.tenant_id

    @pytest.mark.asyncio
    async def test_upsert_exception_updates_existing(self, test_session):
        """Test that upsert_exception updates existing exception."""
        repo = ExceptionRepository(test_session)
        
        # Create initial exception
        initial_data = ExceptionCreateOrUpdateDTO(
            exception_id="EX-003",
            tenant_id="tenant_1",
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.LOW,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        
        result1 = await repo.upsert_exception("tenant_1", initial_data)
        await test_session.commit()
        initial_id = result1.exception_id
        
        # Update with new data
        updated_data = ExceptionCreateOrUpdateDTO(
            exception_id="EX-003",
            tenant_id="tenant_1",
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.CRITICAL,  # Changed
            status=ExceptionStatus.RESOLVED,  # Changed
            source_system="TestSystem",
        )
        
        result2 = await repo.upsert_exception("tenant_1", updated_data)
        await test_session.commit()
        
        # Verify it's the same row (same exception_id)
        assert result2.exception_id == initial_id
        assert result2.severity == ExceptionSeverity.CRITICAL
        assert result2.status == ExceptionStatus.RESOLVED
        
        # Verify only one row exists
        query = select(Exception).where(Exception.exception_id == "EX-003")
        db_result = await test_session.execute(query)
        all_exceptions = db_result.scalars().all()
        
        assert len(all_exceptions) == 1

    @pytest.mark.asyncio
    async def test_upsert_exception_tenant_isolation(self, test_session):
        """Test that upsert_exception respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        # Create exception for tenant_1
        exception_data = ExceptionCreateOrUpdateDTO(
            exception_id="EX-004",
            tenant_id="tenant_1",
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        
        result1 = await repo.upsert_exception("tenant_1", exception_data)
        await test_session.commit()
        
        # Try to create same exception_id for tenant_2 (should create separate row)
        exception_data_tenant2 = ExceptionCreateOrUpdateDTO(
            exception_id="EX-004",  # Same ID
            tenant_id="tenant_2",  # Different tenant
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        
        result2 = await repo.upsert_exception("tenant_2", exception_data_tenant2)
        await test_session.commit()
        
        # Verify both exist (different tenants can have same exception_id)
        query = select(Exception).where(Exception.exception_id == "EX-004")
        db_result = await test_session.execute(query)
        all_exceptions = db_result.scalars().all()
        
        assert len(all_exceptions) == 2
        assert {ex.tenant_id for ex in all_exceptions} == {"tenant_1", "tenant_2"}

    @pytest.mark.asyncio
    async def test_upsert_exception_raises_on_tenant_mismatch(self, test_session):
        """Test that upsert_exception raises error if tenant_id doesn't match."""
        repo = ExceptionRepository(test_session)
        
        exception_data = ExceptionCreateOrUpdateDTO(
            exception_id="EX-005",
            tenant_id="tenant_1",
            domain="TestDomain",
            type="TestType",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        
        with pytest.raises(ValueError, match="tenant_id parameter.*must match"):
            await repo.upsert_exception("tenant_2", exception_data)


class TestExceptionEventRepositoryIdempotency:
    """Test idempotency of ExceptionEventRepository methods."""

    @pytest.mark.asyncio
    async def test_event_exists_returns_false_for_new_event(self, test_session):
        """Test that event_exists returns False for non-existent event."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        exists = await repo.event_exists("tenant_1", event_id)
        
        assert exists is False

    @pytest.mark.asyncio
    async def test_event_exists_returns_true_for_existing_event(self, test_session):
        """Test that event_exists returns True for existing event."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        event_data = ExceptionEventDTO(
            event_id=event_id,
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.AGENT,
            payload={"test": "data"},
        )
        
        # Insert event
        inserted = await repo.append_event_if_new(event_data)
        await test_session.commit()
        
        assert inserted is True
        
        # Check if it exists
        exists = await repo.event_exists("tenant_1", event_id)
        
        assert exists is True

    @pytest.mark.asyncio
    async def test_append_event_if_new_creates_new_event(self, test_session):
        """Test that append_event_if_new creates a new event when it doesn't exist."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        event_data = ExceptionEventDTO(
            event_id=event_id,
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.AGENT,
            payload={"test": "data"},
        )
        
        inserted = await repo.append_event_if_new(event_data)
        await test_session.commit()
        
        assert inserted is True
        
        # Verify it was created
        query = select(ExceptionEvent).where(ExceptionEvent.event_id == event_id)
        db_result = await test_session.execute(query)
        db_event = db_result.scalar_one_or_none()
        
        assert db_event is not None
        assert db_event.event_id == event_id

    @pytest.mark.asyncio
    async def test_append_event_if_new_idempotent(self, test_session):
        """Test that calling append_event_if_new twice with same event_id doesn't create duplicates."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        event_data = ExceptionEventDTO(
            event_id=event_id,
            exception_id="EX-002",
            tenant_id="tenant_1",
            event_type="TriageCompleted",
            actor_type=ActorType.AGENT,
            payload={"decision": "high_severity"},
        )
        
        # First call - should insert
        inserted1 = await repo.append_event_if_new(event_data)
        await test_session.commit()
        
        assert inserted1 is True
        
        # Second call with same event_id - should not insert
        inserted2 = await repo.append_event_if_new(event_data)
        await test_session.commit()
        
        assert inserted2 is False
        
        # Verify only one row exists
        query = select(ExceptionEvent).where(ExceptionEvent.event_id == event_id)
        db_result = await test_session.execute(query)
        all_events = db_result.scalars().all()
        
        assert len(all_events) == 1

    @pytest.mark.asyncio
    async def test_append_event_if_new_tenant_isolation(self, test_session):
        """Test that append_event_if_new respects tenant isolation."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        
        # Create event for tenant_1
        event_data_tenant1 = ExceptionEventDTO(
            event_id=event_id,
            exception_id="EX-003",
            tenant_id="tenant_1",
            event_type="PolicyEvaluated",
            actor_type=ActorType.AGENT,
            payload={"policy": "approved"},
        )
        
        inserted1 = await repo.append_event_if_new(event_data_tenant1)
        await test_session.commit()
        
        assert inserted1 is True
        
        # Try to create same event_id for tenant_2 (should fail due to UUID uniqueness)
        # Actually, since event_id is UUID primary key, it can't be duplicated across tenants
        # But event_exists should check tenant_id, so let's test that
        exists_tenant1 = await repo.event_exists("tenant_1", event_id)
        exists_tenant2 = await repo.event_exists("tenant_2", event_id)
        
        # event_exists checks tenant_id, so tenant_2 shouldn't see tenant_1's event
        # However, since event_id is a UUID primary key, it's globally unique
        # The tenant check in event_exists ensures we only return True if both match
        assert exists_tenant1 is True
        # Note: In a real implementation, event_id would be globally unique,
        # so exists_tenant2 would also be True. But our implementation
        # filters by tenant_id, so it should return False if tenant doesn't match
        # Let's verify the behavior matches our implementation
        assert exists_tenant2 is False  # Our implementation filters by tenant

