"""
Comprehensive verification script for PostgreSQL integration.

Verifies:
✔ All tables created
✔ Inserts succeed
✔ API reads/writes from PostgreSQL
✔ Idempotency works (duplicate events blocked)
"""

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    ActorType,
    Exception,
    ExceptionEvent,
    ExceptionSeverity,
    ExceptionStatus,
    Tenant,
    TenantStatus,
)
from src.infrastructure.db.session import get_db_session_context, get_engine
from src.repository.dto import (
    ExceptionCreateDTO,
    ExceptionEventCreateDTO,
    ExceptionUpdateDTO,
    EventFilter,
)
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository


async def verify_tables_exist():
    """Verify all Phase 6 tables exist."""
    print("\n" + "=" * 70)
    print("1. Verifying Tables Exist")
    print("=" * 70)
    
    engine = get_engine()
    async with engine.begin() as conn:
        # Check if tables exist
        result = await conn.execute(
            select(1).select_from(
                select(Exception).subquery()
            )
        )
        print("[OK] exception table exists")
        
        result = await conn.execute(
            select(1).select_from(
                select(ExceptionEvent).subquery()
            )
        )
        print("[OK] exception_event table exists")
    
    print("[SUCCESS] All required tables exist")


async def create_test_tenant(session: AsyncSession, tenant_id: str):
    """Create a test tenant if it doesn't exist."""
    from sqlalchemy import select
    
    result = await session.execute(select(Tenant).where(Tenant.tenant_id == tenant_id))
    existing = result.scalar_one_or_none()
    
    if existing is None:
        tenant = Tenant(
            tenant_id=tenant_id,
            name=f"Test Tenant {tenant_id}",
            status=TenantStatus.ACTIVE,  # Use enum directly, SQLAlchemy will convert
        )
        session.add(tenant)
        await session.flush()
        print(f"[OK] Created test tenant: {tenant_id}")
    else:
        print(f"[OK] Test tenant already exists: {tenant_id}")


async def test_repository_inserts():
    """Test that repository inserts work."""
    print("\n" + "=" * 70)
    print("2. Testing Repository Inserts")
    print("=" * 70)
    
    async with get_db_session_context() as session:
        # Create test tenant first (required for foreign key)
        await create_test_tenant(session, "test_tenant")
        await session.commit()
        repo = ExceptionRepository(session)
        
        # Create test exception
        exception_data = ExceptionCreateDTO(
            exception_id="TEST-EX-001",
            tenant_id="test_tenant",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
            entity="TEST-ENTITY-001",
        )
        
        exception = await repo.create_exception("test_tenant", exception_data)
        await session.commit()
        
        print(f"[OK] Created exception: {exception.exception_id}")
        
        # Verify it exists
        retrieved = await repo.get_exception("test_tenant", "TEST-EX-001")
        assert retrieved is not None, "Exception should exist after creation"
        assert retrieved.exception_id == "TEST-EX-001"
        assert retrieved.tenant_id == "test_tenant"
        print(f"[OK] Retrieved exception: {retrieved.exception_id}")
        
        # Test event repository
        event_repo = ExceptionEventRepository(session)
        
        event_data = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="TEST-EX-001",
            tenant_id="test_tenant",
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"test": "data"},
        )
        
        event = await event_repo.append_event("test_tenant", event_data)
        await session.commit()
        
        print(f"[OK] Created event: {event.event_id}")
        
        # Verify event exists
        events = await event_repo.get_events_for_exception("test_tenant", "TEST-EX-001")
        assert len(events) == 1, "Event should exist after creation"
        print(f"[OK] Retrieved event: {events[0].event_id}")
    
    print("[SUCCESS] Repository inserts work correctly")


async def test_idempotency():
    """Test that idempotency works (duplicate events blocked)."""
    print("\n" + "=" * 70)
    print("3. Testing Idempotency")
    print("=" * 70)
    
    async with get_db_session_context() as session:
        # Create test tenant first
        await create_test_tenant(session, "test_tenant")
        await session.commit()
        event_repo = ExceptionEventRepository(session)
        
        # Create an event
        event_id = uuid4()
        event_data = ExceptionEventCreateDTO(
            event_id=event_id,
            exception_id="TEST-EX-002",
            tenant_id="test_tenant",
            event_type="TestEvent",
            actor_type=ActorType.SYSTEM,
            payload={"test": "idempotency"},
        )
        
        # First insert should succeed
        event1 = await event_repo.append_event("test_tenant", event_data)
        await session.commit()
        print(f"[OK] First insert succeeded: {event1.event_id}")
        
        # Check that event_exists returns True
        exists = await event_repo.event_exists("test_tenant", event_id)
        assert exists is True, "event_exists should return True for existing event"
        print(f"[OK] event_exists returns True for existing event")
        
        # Second insert with same event_id should fail
        try:
            await event_repo.append_event("test_tenant", event_data)
            await session.commit()
            assert False, "Second insert should have raised ValueError"
        except ValueError as e:
            assert "already exists" in str(e).lower()
            print(f"[OK] Duplicate insert correctly blocked: {e}")
        
        # Test append_event_if_new (idempotent version)
        event_data2 = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id="TEST-EX-002",
            tenant_id="test_tenant",
            event_type="TestEvent2",
            actor_type=ActorType.SYSTEM,
            payload={"test": "idempotency2"},
        )
        
        # First call should insert
        inserted1 = await event_repo.append_event_if_new(event_data2)
        await session.commit()
        assert inserted1 is True, "First append_event_if_new should return True"
        print(f"[OK] append_event_if_new first call inserted: {inserted1}")
        
        # Second call should not insert
        inserted2 = await event_repo.append_event_if_new(event_data2)
        await session.commit()
        assert inserted2 is False, "Second append_event_if_new should return False"
        print(f"[OK] append_event_if_new second call did not insert: {inserted2}")
        
        # Verify only one event exists
        events = await event_repo.get_events_for_exception("test_tenant", "TEST-EX-002")
        event_types = [e.event_type for e in events]
        assert event_types.count("TestEvent2") == 1, "Should have exactly one TestEvent2"
        print(f"[OK] Only one TestEvent2 exists (idempotency verified)")
    
    print("[SUCCESS] Idempotency works correctly")


async def test_api_read_write():
    """Test that API can read/write from PostgreSQL."""
    print("\n" + "=" * 70)
    print("4. Testing API Read/Write (via Repository)")
    print("=" * 70)
    
    async with get_db_session_context() as session:
        # Create test tenant first
        await create_test_tenant(session, "api_test_tenant")
        await session.commit()
        repo = ExceptionRepository(session)
        
        # Create multiple exceptions
        exceptions = []
        for i in range(3):
            exception_data = ExceptionCreateDTO(
                exception_id=f"API-TEST-{i:03d}",
                tenant_id="api_test_tenant",
                domain="Finance",
                type="TradeException",
                severity=ExceptionSeverity.HIGH if i % 2 == 0 else ExceptionSeverity.MEDIUM,
                status=ExceptionStatus.OPEN,
                source_system="APITestSystem",
            )
            exc = await repo.create_exception("api_test_tenant", exception_data)
            exceptions.append(exc)
        
        await session.commit()
        print(f"[OK] Created {len(exceptions)} exceptions via repository")
        
        # Test list query
        filters = ExceptionFilter(domain="Finance")
        result = await repo.list_exceptions("api_test_tenant", filters, page=1, page_size=10)
        
        assert result.total >= 3, f"Should have at least 3 exceptions, got {result.total}"
        print(f"[OK] List query returned {result.total} exceptions")
        
        # Test get by ID
        retrieved = await repo.get_exception("api_test_tenant", "API-TEST-000")
        assert retrieved is not None, "Should retrieve exception by ID"
        assert retrieved.exception_id == "API-TEST-000"
        print(f"[OK] Retrieved exception by ID: {retrieved.exception_id}")
        
        # Test update
        updates = ExceptionUpdateDTO(status=ExceptionStatus.RESOLVED, owner="test_user")
        updated = await repo.update_exception("api_test_tenant", "API-TEST-000", updates)
        await session.commit()
        
        assert updated is not None, "Update should succeed"
        assert updated.status == ExceptionStatus.RESOLVED
        assert updated.owner == "test_user"
        print(f"[OK] Updated exception: status={updated.status}, owner={updated.owner}")
        
        # Test Co-Pilot query helpers
        similar = await repo.find_similar_exceptions("api_test_tenant", domain="Finance", limit=10)
        assert len(similar) >= 1, "Should find similar exceptions"
        print(f"[OK] Co-Pilot query found {len(similar)} similar exceptions")
        
        # Test event timeline
        event_repo = ExceptionEventRepository(session)
        for i, exc in enumerate(exceptions):
            event_data = ExceptionEventCreateDTO(
                event_id=uuid4(),
                exception_id=exc.exception_id,
                tenant_id="api_test_tenant",
                event_type="ExceptionCreated",
                actor_type=ActorType.SYSTEM,
                payload={"index": i},
            )
            await event_repo.append_event("api_test_tenant", event_data)
        
        await session.commit()
        
        events = await event_repo.get_events_for_exception("api_test_tenant", "API-TEST-000")
        assert len(events) == 1, "Should have one event for exception"
        print(f"[OK] Retrieved {len(events)} events for exception")
    
    print("[SUCCESS] API read/write operations work correctly")


async def test_tenant_isolation():
    """Test that tenant isolation is enforced."""
    print("\n" + "=" * 70)
    print("5. Testing Tenant Isolation")
    print("=" * 70)
    
    async with get_db_session_context() as session:
        # Create test tenants first
        await create_test_tenant(session, "tenant_1")
        await create_test_tenant(session, "tenant_2")
        await session.commit()
        repo = ExceptionRepository(session)
        
        # Create exception for tenant_1
        exc1_data = ExceptionCreateDTO(
            exception_id="ISOLATION-TEST-001",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="TestSystem",
        )
        exc1 = await repo.create_exception("tenant_1", exc1_data)
        await session.commit()
        print(f"[OK] Created exception for tenant_1: {exc1.exception_id}")
        
        # Try to retrieve as tenant_2 (should return None)
        retrieved = await repo.get_exception("tenant_2", "ISOLATION-TEST-001")
        assert retrieved is None, "tenant_2 should not see tenant_1's exception"
        print(f"[OK] Tenant isolation verified: tenant_2 cannot see tenant_1's exception")
        
        # List for tenant_1 should return the exception
        result1 = await repo.list_exceptions("tenant_1", ExceptionFilter(), page=1, page_size=10)
        assert any(ex.exception_id == "ISOLATION-TEST-001" for ex in result1.items)
        print(f"[OK] tenant_1 can see its own exception")
        
        # List for tenant_2 should not return the exception
        result2 = await repo.list_exceptions("tenant_2", ExceptionFilter(), page=1, page_size=10)
        assert not any(ex.exception_id == "ISOLATION-TEST-001" for ex in result2.items)
        print(f"[OK] tenant_2 cannot see tenant_1's exception in list")
    
    print("[SUCCESS] Tenant isolation is enforced correctly")


async def verify_data_in_database():
    """Verify data actually exists in PostgreSQL."""
    print("\n" + "=" * 70)
    print("6. Verifying Data in Database")
    print("=" * 70)
    
    engine = get_engine()
    async with engine.begin() as conn:
        # Count exceptions
        result = await conn.execute(select(Exception))
        exceptions = result.scalars().all()
        print(f"[OK] Found {len(exceptions)} exceptions in database")
        
        # Count events
        result = await conn.execute(select(ExceptionEvent))
        events = result.scalars().all()
        print(f"[OK] Found {len(events)} events in database")
        
        # Show sample data
        if exceptions:
            sample = exceptions[0]
            print(f"[OK] Sample exception: {sample.exception_id} (tenant: {sample.tenant_id}, status: {sample.status})")
        
        if events:
            sample = events[0]
            print(f"[OK] Sample event: {sample.event_id} (type: {sample.event_type}, exception: {sample.exception_id})")
    
    print("[SUCCESS] Data verified in database")


async def main():
    """Run all verification tests."""
    print("=" * 70)
    print("PostgreSQL Integration Verification")
    print("=" * 70)
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("\n[WARNING] DATABASE_URL not set. Using defaults.")
        print("Set it with: $env:DATABASE_URL = 'postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai'")
    
    try:
        await verify_tables_exist()
        await test_repository_inserts()
        await test_idempotency()
        await test_api_read_write()
        await test_tenant_isolation()
        await verify_data_in_database()
        
        print("\n" + "=" * 70)
        print("[SUCCESS] All Verification Tests Passed!")
        print("=" * 70)
        print("\nSummary:")
        print("  ✔ All tables created")
        print("  ✔ Inserts succeed")
        print("  ✔ API reads/writes from PostgreSQL")
        print("  ✔ Idempotency works (duplicate events blocked)")
        print("  ✔ Tenant isolation enforced")
        print("  ✔ Data verified in database")
        
    except BaseException as e:
        print(f"\n[FAILED] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

