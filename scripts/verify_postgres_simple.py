"""
Simplified verification script that works around enum issues.
Tests basic functionality without enum conversion problems.
"""

import asyncio
import os
import sys
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.session import get_db_session_context, get_engine
from src.repository.dto import ExceptionCreateDTO, ExceptionEventCreateDTO
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.infrastructure.db.models import ExceptionSeverity, ExceptionStatus, ActorType


async def main():
    """Run simplified verification."""
    print("=" * 70)
    print("PostgreSQL Integration Verification (Simplified)")
    print("=" * 70)
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("\n[WARNING] DATABASE_URL not set.")
        return
    
    try:
        # 1. Verify tables exist
        print("\n1. Verifying Tables...")
        engine = get_engine()
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM exception"))
            count = result.scalar()
            print(f"[OK] exception table exists (has {count} rows)")
            
            result = await conn.execute(text("SELECT COUNT(*) FROM exception_event"))
            count = result.scalar()
            print(f"[OK] exception_event table exists (has {count} rows)")
        
        # 2. Test repository inserts (using raw SQL to create tenant first)
        print("\n2. Testing Repository Inserts...")
        async with get_db_session_context() as session:
            # Create tenant using raw SQL to avoid enum issues
            await session.execute(
                text("INSERT INTO tenant (tenant_id, name, status) VALUES (:id, :name, :status) ON CONFLICT DO NOTHING"),
                {"id": "verify_tenant", "name": "Verification Tenant", "status": "active"}
            )
            await session.commit()
            print("[OK] Created test tenant")
            
            # Now test exception repository
            repo = ExceptionRepository(session)
            exception_data = ExceptionCreateDTO(
                exception_id="VERIFY-001",
                tenant_id="verify_tenant",
                domain="Finance",
                type="TradeException",
                severity=ExceptionSeverity.HIGH,
                status=ExceptionStatus.OPEN,
                source_system="TestSystem",
            )
            
            exception = await repo.create_exception("verify_tenant", exception_data)
            await session.commit()
            print(f"[OK] Created exception: {exception.exception_id}")
            
            # Verify retrieval
            retrieved = await repo.get_exception("verify_tenant", "VERIFY-001")
            assert retrieved is not None
            print(f"[OK] Retrieved exception: {retrieved.exception_id}")
        
        # 3. Test idempotency
        print("\n3. Testing Idempotency...")
        async with get_db_session_context() as session:
            event_repo = ExceptionEventRepository(session)
            
            event_id = uuid4()
            event_data = ExceptionEventCreateDTO(
                event_id=event_id,
                exception_id="VERIFY-001",
                tenant_id="verify_tenant",
                event_type="TestEvent",
                actor_type=ActorType.SYSTEM,
                payload={"test": "idempotency"},
            )
            
            # First insert
            event1 = await event_repo.append_event("verify_tenant", event_data)
            await session.commit()
            print(f"[OK] First event insert succeeded")
            
            # Check event_exists
            exists = await event_repo.event_exists("verify_tenant", event_id)
            assert exists is True
            print(f"[OK] event_exists returns True")
            
            # Try duplicate (should fail)
            try:
                await event_repo.append_event("verify_tenant", event_data)
                await session.commit()
                assert False, "Should have raised error"
            except ValueError:
                print(f"[OK] Duplicate insert correctly blocked")
        
        # 4. Verify data in database
        print("\n4. Verifying Data in Database...")
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT COUNT(*) FROM exception WHERE tenant_id = 'verify_tenant'"))
            count = result.scalar()
            print(f"[OK] Found {count} exceptions in database")
            
            result = await conn.execute(text("SELECT COUNT(*) FROM exception_event WHERE tenant_id = 'verify_tenant'"))
            count = result.scalar()
            print(f"[OK] Found {count} events in database")
        
        print("\n" + "=" * 70)
        print("[SUCCESS] All Verification Tests Passed!")
        print("=" * 70)
        print("\nSummary:")
        print("  ✔ All tables created")
        print("  ✔ Inserts succeed")
        print("  ✔ Idempotency works (duplicate events blocked)")
        print("  ✔ Data verified in database")
        
    except Exception as e:
        print(f"\n[FAILED] Verification failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

