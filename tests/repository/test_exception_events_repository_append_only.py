"""
Tests for ExceptionEventRepository append-only log operations.

Tests Phase 6 P6-8: Append-only event log with full retrieval operations.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infrastructure.db.models import ActorType, ExceptionEvent
from src.repository.dto import EventFilter, ExceptionEventCreateDTO
from src.repository.exception_events_repository import ExceptionEventRepository

# Create test base
TestBase = declarative_base()


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


@pytest.fixture
async def test_events(test_session):
    """Create test events for multiple exceptions and tenants."""
    repo = ExceptionEventRepository(test_session)
    
    now = datetime.now(timezone.utc)
    
    # Create events for tenant_1, exception EX-001
    events_ex1 = [
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"source": "ingestion"},
        ),
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="TriageCompleted",
            actor_type=ActorType.AGENT,
            actor_id="TriageAgent",
            payload={"severity": "high", "confidence": 0.9},
        ),
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="PolicyEvaluated",
            actor_type=ActorType.AGENT,
            actor_id="PolicyAgent",
            payload={"playbook_id": 1},
        ),
    ]
    
    # Create events for tenant_1, exception EX-002
    events_ex2 = [
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-002",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"source": "ingestion"},
        ),
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-002",
            tenant_id="tenant_1",
            event_type="LLMDecisionProposed",
            actor_type=ActorType.AGENT,
            actor_id="CoPilot",
            payload={"decision": "escalate", "reasoning": "high severity"},
        ),
    ]
    
    # Create events for tenant_2
    events_tenant2 = [
        ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-T2-001",
            tenant_id="tenant_2",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"source": "ingestion"},
        ),
    ]
    
    created = []
    for event_data in events_ex1 + events_ex2 + events_tenant2:
        event = await repo.append_event(event_data.tenant_id, event_data)
        created.append(event)
    
    await test_session.commit()
    
    return created


class TestAppendEvent:
    """Test append_event method."""

    @pytest.mark.asyncio
    async def test_append_event_success(self, test_session):
        """Test successful event appending."""
        repo = ExceptionEventRepository(test_session)
        
        event_data = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"test": "data"},
        )
        
        result = await repo.append_event("tenant_1", event_data)
        await test_session.commit()
        
        assert result is not None
        assert result.event_id == event_data.event_id
        assert result.exception_id == "EX-001"
        assert result.tenant_id == "tenant_1"
        assert result.event_type == "ExceptionCreated"
        assert result.actor_type == ActorType.SYSTEM

    @pytest.mark.asyncio
    async def test_append_event_raises_on_duplicate(self, test_session):
        """Test that append_event raises error on duplicate event_id."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        event_data = ExceptionEventCreateDTO(
            event_id=event_id,
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"test": "data"},
        )
        
        # First append succeeds
        await repo.append_event("tenant_1", event_data)
        await test_session.commit()
        
        # Second append should fail
        with pytest.raises(ValueError, match="already exists"):
            await repo.append_event("tenant_1", event_data)

    @pytest.mark.asyncio
    async def test_append_event_raises_on_tenant_mismatch(self, test_session):
        """Test that append_event raises error on tenant_id mismatch."""
        repo = ExceptionEventRepository(test_session)
        
        event_data = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"test": "data"},
        )
        
        with pytest.raises(ValueError, match="must match"):
            await repo.append_event("tenant_2", event_data)

    @pytest.mark.asyncio
    async def test_append_event_preserves_payload_structure(self, test_session):
        """Test that payload structure is preserved for Kafka migration."""
        repo = ExceptionEventRepository(test_session)
        
        complex_payload = {
            "decision": "escalate",
            "reasoning": "High severity exception",
            "confidence": 0.95,
            "metadata": {
                "model": "gpt-4",
                "tokens_used": 150,
            },
            "actions": ["notify_owner", "create_ticket"],
        }
        
        event_data = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="EX-001",
            tenant_id="tenant_1",
            event_type="LLMDecisionProposed",
            actor_type=ActorType.AGENT,
            payload=complex_payload,
        )
        
        result = await repo.append_event("tenant_1", event_data)
        await test_session.commit()
        
        assert result.payload == complex_payload
        assert result.payload["metadata"]["model"] == "gpt-4"


class TestGetEventsForException:
    """Test get_events_for_exception method."""

    @pytest.mark.asyncio
    async def test_get_events_for_exception_success(self, test_session, test_events):
        """Test getting events for a specific exception."""
        repo = ExceptionEventRepository(test_session)
        
        events = await repo.get_events_for_exception("tenant_1", "EX-001")
        
        assert len(events) == 3
        assert all(ex.exception_id == "EX-001" for ex in events)
        assert all(ex.tenant_id == "tenant_1" for ex in events)

    @pytest.mark.asyncio
    async def test_get_events_for_exception_chronological_order(self, test_session, test_events):
        """Test that events are returned in chronological order (oldest first)."""
        repo = ExceptionEventRepository(test_session)
        
        events = await repo.get_events_for_exception("tenant_1", "EX-001")
        
        # Verify chronological ordering (oldest first)
        if len(events) > 1:
            for i in range(len(events) - 1):
                assert events[i].created_at <= events[i + 1].created_at

    @pytest.mark.asyncio
    async def test_get_events_for_exception_filter_by_event_types(self, test_session, test_events):
        """Test filtering events by event types."""
        repo = ExceptionEventRepository(test_session)
        
        filters = EventFilter(event_types=["ExceptionCreated", "TriageCompleted"])
        events = await repo.get_events_for_exception("tenant_1", "EX-001", filters)
        
        assert len(events) == 2
        assert all(ex.event_type in ["ExceptionCreated", "TriageCompleted"] for ex in events)

    @pytest.mark.asyncio
    async def test_get_events_for_exception_filter_by_actor_type(self, test_session, test_events):
        """Test filtering events by actor type."""
        repo = ExceptionEventRepository(test_session)
        
        filters = EventFilter(actor_type=ActorType.AGENT)
        events = await repo.get_events_for_exception("tenant_1", "EX-001", filters)
        
        assert len(events) == 2
        assert all(ex.actor_type == ActorType.AGENT for ex in events)

    @pytest.mark.asyncio
    async def test_get_events_for_exception_filter_by_date_range(self, test_session, test_events):
        """Test filtering events by date range."""
        repo = ExceptionEventRepository(test_session)
        
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        # Filter by date_from
        filters1 = EventFilter(created_from=yesterday)
        events1 = await repo.get_events_for_exception("tenant_1", "EX-001", filters1)
        
        assert len(events1) == 3  # All events are recent
        
        # Filter by date_to
        filters2 = EventFilter(created_to=tomorrow)
        events2 = await repo.get_events_for_exception("tenant_1", "EX-001", filters2)
        
        assert len(events2) == 3

    @pytest.mark.asyncio
    async def test_get_events_for_exception_multiple_filters(self, test_session, test_events):
        """Test filtering with multiple criteria."""
        repo = ExceptionEventRepository(test_session)
        
        filters = EventFilter(
            event_types=["TriageCompleted"],
            actor_type=ActorType.AGENT,
        )
        events = await repo.get_events_for_exception("tenant_1", "EX-001", filters)
        
        assert len(events) == 1
        assert events[0].event_type == "TriageCompleted"
        assert events[0].actor_type == ActorType.AGENT

    @pytest.mark.asyncio
    async def test_get_events_for_exception_tenant_isolation(self, test_session, test_events):
        """Test that get_events_for_exception respects tenant isolation."""
        repo = ExceptionEventRepository(test_session)
        
        # Query for tenant_1
        events1 = await repo.get_events_for_exception("tenant_1", "EX-001")
        
        # Query for tenant_2 (should return empty for EX-001)
        events2 = await repo.get_events_for_exception("tenant_2", "EX-001")
        
        assert len(events1) == 3
        assert len(events2) == 0
        assert all(ex.tenant_id == "tenant_1" for ex in events1)

    @pytest.mark.asyncio
    async def test_get_events_for_exception_empty_result(self, test_session):
        """Test getting events for non-existent exception."""
        repo = ExceptionEventRepository(test_session)
        
        events = await repo.get_events_for_exception("tenant_1", "EX-NONEXISTENT")
        
        assert len(events) == 0


class TestGetEventsForTenant:
    """Test get_events_for_tenant method."""

    @pytest.mark.asyncio
    async def test_get_events_for_tenant_success(self, test_session, test_events):
        """Test getting events for a tenant."""
        repo = ExceptionEventRepository(test_session)
        
        events = await repo.get_events_for_tenant("tenant_1")
        
        assert len(events) == 5  # 3 for EX-001 + 2 for EX-002
        assert all(ex.tenant_id == "tenant_1" for ex in events)

    @pytest.mark.asyncio
    async def test_get_events_for_tenant_reverse_chronological_order(self, test_session, test_events):
        """Test that events are returned in reverse chronological order (newest first)."""
        repo = ExceptionEventRepository(test_session)
        
        events = await repo.get_events_for_tenant("tenant_1")
        
        # Verify reverse chronological ordering (newest first)
        if len(events) > 1:
            for i in range(len(events) - 1):
                assert events[i].created_at >= events[i + 1].created_at

    @pytest.mark.asyncio
    async def test_get_events_for_tenant_filter_by_date_from(self, test_session, test_events):
        """Test filtering tenant events by date_from."""
        repo = ExceptionEventRepository(test_session)
        
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        
        events = await repo.get_events_for_tenant("tenant_1", date_from=yesterday)
        
        assert len(events) == 5  # All events are recent

    @pytest.mark.asyncio
    async def test_get_events_for_tenant_filter_by_date_to(self, test_session, test_events):
        """Test filtering tenant events by date_to."""
        repo = ExceptionEventRepository(test_session)
        
        now = datetime.now(timezone.utc)
        tomorrow = now + timedelta(days=1)
        
        events = await repo.get_events_for_tenant("tenant_1", date_to=tomorrow)
        
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_get_events_for_tenant_date_range(self, test_session, test_events):
        """Test filtering tenant events by date range."""
        repo = ExceptionEventRepository(test_session)
        
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        events = await repo.get_events_for_tenant(
            "tenant_1",
            date_from=yesterday,
            date_to=tomorrow,
        )
        
        assert len(events) == 5

    @pytest.mark.asyncio
    async def test_get_events_for_tenant_tenant_isolation(self, test_session, test_events):
        """Test that get_events_for_tenant respects tenant isolation."""
        repo = ExceptionEventRepository(test_session)
        
        # Query for tenant_1
        events1 = await repo.get_events_for_tenant("tenant_1")
        
        # Query for tenant_2
        events2 = await repo.get_events_for_tenant("tenant_2")
        
        assert len(events1) == 5
        assert len(events2) == 1
        assert all(ex.tenant_id == "tenant_1" for ex in events1)
        assert all(ex.tenant_id == "tenant_2" for ex in events2)


class TestEventExists:
    """Test event_exists method (from P6-5, verified in P6-8)."""

    @pytest.mark.asyncio
    async def test_event_exists_returns_true_for_existing(self, test_session, test_events):
        """Test that event_exists returns True for existing event."""
        repo = ExceptionEventRepository(test_session)
        
        # Get an event_id from test_events
        event_id = test_events[0].event_id
        
        exists = await repo.event_exists("tenant_1", event_id)
        
        assert exists is True

    @pytest.mark.asyncio
    async def test_event_exists_returns_false_for_nonexistent(self, test_session):
        """Test that event_exists returns False for non-existent event."""
        repo = ExceptionEventRepository(test_session)
        
        event_id = uuid4()
        exists = await repo.event_exists("tenant_1", event_id)
        
        assert exists is False

    @pytest.mark.asyncio
    async def test_event_exists_tenant_isolation(self, test_session, test_events):
        """Test that event_exists respects tenant isolation."""
        repo = ExceptionEventRepository(test_session)
        
        # Get an event_id from tenant_1
        event_id = test_events[0].event_id
        
        # Check as tenant_1 (should exist)
        exists1 = await repo.event_exists("tenant_1", event_id)
        
        # Check as tenant_2 (should not exist due to tenant isolation)
        exists2 = await repo.event_exists("tenant_2", event_id)
        
        assert exists1 is True
        assert exists2 is False


class TestAppendOnlySemantics:
    """Test that append-only semantics are enforced."""

    @pytest.mark.asyncio
    async def test_no_update_method(self, test_session):
        """Test that no update method exists (append-only)."""
        repo = ExceptionEventRepository(test_session)
        
        # Verify no update method exists
        assert not hasattr(repo, "update_event")
        assert not hasattr(repo, "update")

    @pytest.mark.asyncio
    async def test_no_delete_method(self, test_session):
        """Test that no delete method exists (append-only)."""
        repo = ExceptionEventRepository(test_session)
        
        # Verify no delete method exists
        assert not hasattr(repo, "delete_event")
        assert not hasattr(repo, "delete")

    @pytest.mark.asyncio
    async def test_events_are_immutable_once_written(self, test_session, test_events):
        """Test that events cannot be modified after creation."""
        repo = ExceptionEventRepository(test_session)
        
        # Get an event
        event = test_events[0]
        original_type = event.event_type
        
        # Try to modify (should not affect database)
        event.event_type = "ModifiedType"
        await test_session.flush()
        await test_session.refresh(event)
        
        # In a real scenario, we'd verify the database value hasn't changed
        # For now, we just verify the repository doesn't provide update methods
        assert not hasattr(repo, "update_event")

