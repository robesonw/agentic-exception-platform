"""
Diagnostic script to check API server database connection and test persistence.

This script helps diagnose why data isn't appearing in PostgreSQL.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.session import check_database_connection, get_db_session_context, get_engine
from src.infrastructure.db.settings import get_database_settings
from src.repository.dto import ExceptionCreateOrUpdateDTO
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.infrastructure.db.models import ExceptionSeverity, ExceptionStatus, ActorType, Tenant, TenantStatus
from sqlalchemy import select
from uuid import uuid4


async def check_environment():
    """Check if DATABASE_URL is set."""
    print("\n" + "=" * 70)
    print("1. Environment Check")
    print("=" * 70)
    
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        # Mask password
        safe_url = database_url.split("@")[0].split(":")[0] + ":***@" + "@".join(database_url.split("@")[1:]) if "@" in database_url else database_url
        print(f"[OK] DATABASE_URL is set: {safe_url}")
        return True
    else:
        print("[FAILED] DATABASE_URL is not set!")
        print("\nSet it with:")
        print('  $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"')
        return False


async def check_database_connection_direct():
    """Check database connection directly."""
    print("\n" + "=" * 70)
    print("2. Direct Database Connection Check")
    print("=" * 70)
    
    try:
        is_connected = await check_database_connection(retries=3, initial_delay=1.0)
        if is_connected:
            print("[OK] Database connection successful")
            return True
        else:
            print("[FAILED] Database connection failed")
            return False
    except Exception as e:
        print(f"[FAILED] Database connection error: {e}")
        return False


async def check_settings():
    """Check database settings."""
    print("\n" + "=" * 70)
    print("3. Database Settings Check")
    print("=" * 70)
    
    try:
        settings = get_database_settings()
        # Mask password in URL
        safe_url = str(settings.database_url).split("@")[0].split(":")[0] + ":***@" + "@".join(str(settings.database_url).split("@")[1:]) if "@" in str(settings.database_url) else str(settings.database_url)
        print(f"[OK] Database URL: {safe_url}")
        print(f"[OK] Pool size: {settings.pool_size}")
        print(f"[OK] Max overflow: {settings.max_overflow}")
        return True
    except Exception as e:
        print(f"[FAILED] Error getting settings: {e}")
        return False


async def test_direct_persistence():
    """Test direct persistence to database."""
    print("\n" + "=" * 70)
    print("4. Direct Persistence Test")
    print("=" * 70)
    
    try:
        async with get_db_session_context() as session:
            # Create tenant
            tenant_id = "DIAG_TEST_TENANT"
            result = await session.execute(
                select(Tenant).where(Tenant.tenant_id == tenant_id)
            )
            existing_tenant = result.scalar_one_or_none()
            
            if existing_tenant is None:
                # Use raw SQL to avoid enum conversion issues
                from sqlalchemy import text
                await session.execute(
                    text(
                        "INSERT INTO tenant (tenant_id, name, status) "
                        "VALUES (:tenant_id, :name, :status) "
                        "ON CONFLICT (tenant_id) DO NOTHING"
                    ),
                    {
                        "tenant_id": tenant_id,
                        "name": "Diagnostic Test Tenant",
                        "status": "active",  # Use lowercase string directly
                    },
                )
                await session.flush()
                print(f"[OK] Created test tenant: {tenant_id}")
            
            # Create exception
            repo = ExceptionRepository(session)
            exception_data = ExceptionCreateOrUpdateDTO(
                exception_id="DIAG-TEST-001",
                tenant_id=tenant_id,
                domain="Finance",
                type="TestException",
                severity=ExceptionSeverity.HIGH,
                status=ExceptionStatus.OPEN,
                source_system="DiagnosticTest",
            )
            
            await repo.upsert_exception(tenant_id, exception_data)
            await session.flush()
            print(f"[OK] Created test exception: DIAG-TEST-001")
            
            # Verify it exists
            retrieved = await repo.get_exception(tenant_id, "DIAG-TEST-001")
            if retrieved:
                print(f"[OK] Retrieved exception from database: {retrieved.exception_id}")
            else:
                print("[FAILED] Exception not found after creation")
                return False
            
            # Create event
            event_repo = ExceptionEventRepository(session)
            from src.repository.dto import ExceptionEventCreateDTO
            
            event_data = ExceptionEventCreateDTO(
                event_id=uuid4(),
                exception_id="DIAG-TEST-001",
                tenant_id=tenant_id,
                event_type="TestEvent",
                actor_type=ActorType.SYSTEM,
                payload={"test": "diagnostic"},
            )
            
            await event_repo.append_event_if_new(event_data)
            await session.flush()
            print(f"[OK] Created test event")
            
            # Verify event exists
            events = await event_repo.get_events_for_exception(tenant_id, "DIAG-TEST-001")
            if events:
                print(f"[OK] Retrieved event from database: {len(events)} event(s)")
            else:
                print("[FAILED] Event not found after creation")
                return False
            
            return True
            
    except Exception as e:
        import traceback
        print(f"[FAILED] Direct persistence test failed: {e}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return False


async def check_existing_data():
    """Check if any data exists in database."""
    print("\n" + "=" * 70)
    print("5. Existing Data Check")
    print("=" * 70)
    
    try:
        engine = get_engine()
        async with engine.begin() as conn:
            # Count tenants
            result = await conn.execute(select(Tenant))
            tenants = result.scalars().all()
            print(f"[INFO] Found {len(tenants)} tenant(s) in database")
            for tenant in tenants[:5]:
                try:
                    status_val = tenant.status.value if hasattr(tenant.status, 'value') else str(tenant.status)
                    print(f"  - {tenant.tenant_id}: {tenant.name} ({status_val})")
                except AttributeError:
                    print(f"  - {tenant.tenant_id}: {tenant.name} (status: {tenant.status})")
            
            # Count exceptions (use full module path to avoid conflict with built-in Exception)
            from src.infrastructure.db.models import Exception as ExceptionModel
            result = await conn.execute(select(ExceptionModel))
            exceptions = result.scalars().all()
            print(f"[INFO] Found {len(exceptions)} exception(s) in database")
            for exc in exceptions[:5]:
                try:
                    severity_val = exc.severity.value if hasattr(exc.severity, 'value') else str(exc.severity)
                    status_val = exc.status.value if hasattr(exc.status, 'value') else str(exc.status)
                    print(f"  - {exc.exception_id}: {exc.tenant_id}, {exc.domain}, severity={severity_val}, status={status_val}")
                except AttributeError as e:
                    print(f"  - {exc.exception_id}: {exc.tenant_id}, {exc.domain} (error accessing attributes: {e})")
            
            # Count events
            from src.infrastructure.db.models import ExceptionEvent
            result = await conn.execute(select(ExceptionEvent))
            events = result.scalars().all()
            print(f"[INFO] Found {len(events)} event(s) in database")
            for event in events[:5]:
                try:
                    actor_val = event.actor_type.value if hasattr(event.actor_type, 'value') else str(event.actor_type)
                    print(f"  - {event.event_id}: {event.exception_id}, {event.event_type}, actor={actor_val}")
                except AttributeError:
                    print(f"  - {event.event_id}: {event.exception_id}, {event.event_type}")
            
            return True
    except Exception as db_error:
        print(f"[FAILED] Error checking existing data: {db_error}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all diagnostic checks."""
    print("=" * 70)
    print("API Server Database Connection Diagnostic")
    print("=" * 70)
    
    results = []
    
    results.append(("Environment", await check_environment()))
    results.append(("Database Connection", await check_database_connection_direct()))
    results.append(("Database Settings", await check_settings()))
    results.append(("Direct Persistence", await test_direct_persistence()))
    results.append(("Existing Data", await check_existing_data()))
    
    print("\n" + "=" * 70)
    print("Diagnostic Summary")
    print("=" * 70)
    
    for name, result in results:
        status = "[OK]" if result else "[FAILED]"
        print(f"{status} {name}")
    
    all_ok = all(result for _, result in results)
    
    if not all_ok:
        print("\n" + "=" * 70)
        print("Troubleshooting Steps")
        print("=" * 70)
        print("1. Set DATABASE_URL environment variable:")
        print('   $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"')
        print("\n2. Restart the API server:")
        print("   uvicorn src.api.main:app --reload")
        print("\n3. Verify PostgreSQL is running:")
        print("   .\\scripts\\docker_db.ps1 status")
        print("\n4. Check API server logs for database errors")
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

