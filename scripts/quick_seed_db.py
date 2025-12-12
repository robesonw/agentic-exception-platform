#!/usr/bin/env python3
"""
Quick script to seed the database directly (without API).

This is useful when the API is not running but you want to populate the database.
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.models import (
    ActorType,
    Exception as ExceptionModel,
    ExceptionEvent,
    ExceptionSeverity,
    ExceptionStatus,
    Tenant,
    TenantStatus,
)
from src.infrastructure.db.session import get_db_session_context
from src.repository.dto import ExceptionCreateOrUpdateDTO, ExceptionEventCreateDTO
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository


async def seed_tenants(session):
    """Create sample tenants."""
    tenants_data = [
        {
            "tenant_id": "TENANT_FINANCE_001",
            "name": "Finance Corp",
            "status": TenantStatus.ACTIVE,
        },
        {
            "tenant_id": "TENANT_HEALTHCARE_001",
            "name": "Healthcare Inc",
            "status": TenantStatus.ACTIVE,
        },
    ]
    
    for tenant_data in tenants_data:
        result = await session.execute(
            select(Tenant).where(Tenant.tenant_id == tenant_data["tenant_id"])
        )
        existing = result.scalar_one_or_none()
        
        if existing is None:
            tenant = Tenant(**tenant_data)
            session.add(tenant)
            print(f"  Created tenant: {tenant_data['tenant_id']}")
        else:
            print(f"  Tenant already exists: {tenant_data['tenant_id']}")


async def seed_exceptions(session):
    """Create sample exceptions."""
    from sqlalchemy import select
    
    repo = ExceptionRepository(session)
    event_repo = ExceptionEventRepository(session)
    
    # Finance tenant exceptions
    finance_exceptions = [
        {
            "exception_id": "FIN-EXC-001",
            "domain": "Finance",
            "type": "PaymentFailure",
            "severity": ExceptionSeverity.HIGH,
            "status": ExceptionStatus.OPEN,
            "source_system": "PaymentGateway",
            "raw_payload": {"transaction_id": "TXN-123", "amount": 1000.00, "error": "Insufficient funds"},
        },
        {
            "exception_id": "FIN-EXC-002",
            "domain": "Finance",
            "type": "FraudAlert",
            "severity": ExceptionSeverity.CRITICAL,
            "status": ExceptionStatus.OPEN,
            "source_system": "FraudDetection",
            "raw_payload": {"transaction_id": "TXN-456", "risk_score": 0.95},
        },
        {
            "exception_id": "FIN-EXC-003",
            "domain": "Finance",
            "type": "ReconciliationMismatch",
            "severity": ExceptionSeverity.MEDIUM,
            "status": ExceptionStatus.OPEN,
            "source_system": "AccountingSystem",
            "raw_payload": {"account": "ACC-789", "difference": 50.00},
        },
    ]
    
    # Healthcare tenant exceptions
    healthcare_exceptions = [
        {
            "exception_id": "HC-EXC-001",
            "domain": "Healthcare",
            "type": "PatientDataMismatch",
            "severity": ExceptionSeverity.HIGH,
            "status": ExceptionStatus.OPEN,
            "source_system": "EMR",
            "raw_payload": {"patient_id": "PAT-001", "field": "date_of_birth"},
        },
        {
            "exception_id": "HC-EXC-002",
            "domain": "Healthcare",
            "type": "MedicationError",
            "severity": ExceptionSeverity.CRITICAL,
            "status": ExceptionStatus.OPEN,
            "source_system": "PharmacySystem",
            "raw_payload": {"medication": "Aspirin", "dose": "500mg", "allergy": True},
        },
    ]
    
    all_exceptions = []
    for exc_data in finance_exceptions:
        exc_data["tenant_id"] = "TENANT_FINANCE_001"
        all_exceptions.append(exc_data)
    
    for exc_data in healthcare_exceptions:
        exc_data["tenant_id"] = "TENANT_HEALTHCARE_001"
        all_exceptions.append(exc_data)
    
    for exc_data in all_exceptions:
        tenant_id = exc_data.pop("tenant_id")
        exception_id = exc_data["exception_id"]
        
        # Check if exception exists
        existing = await repo.get_exception(tenant_id, exception_id)
        if existing:
            print(f"  Exception already exists: {exception_id}")
            continue
        
        # Create exception (tenant_id is included in DTO)
        exc_data["tenant_id"] = tenant_id
        dto = ExceptionCreateOrUpdateDTO(**exc_data)
        await repo.upsert_exception(tenant_id, dto)
        
        # Create initial event
        event_dto = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="ExceptionCreated",
            actor_type=ActorType.SYSTEM,
            payload={"source_system": exc_data["source_system"], "raw_payload": exc_data["raw_payload"]},
        )
        await event_repo.append_event_if_new(event_dto)
        
        print(f"  Created exception: {exception_id} for tenant {tenant_id}")


async def main():
    """Main seeding function."""
    print("=" * 70)
    print("Quick Database Seeding")
    print("=" * 70)
    
    # Check DATABASE_URL
    if not os.getenv("DATABASE_URL"):
        print("\n[ERROR] DATABASE_URL is not set!")
        print("Set it with:")
        print('  $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"')
        return 1
    
    try:
        async with get_db_session_context() as session:
            print("\n1. Seeding tenants...")
            await seed_tenants(session)
            
            print("\n2. Seeding exceptions...")
            await seed_exceptions(session)
            
            await session.commit()
            print("\n[SUCCESS] Database seeded successfully!")
            
    except Exception as e:
        import traceback
        print(f"\n[ERROR] Seeding failed: {e}")
        print(f"Traceback:\n{traceback.format_exc()}")
        return 1
    
    print("\n" + "=" * 70)
    print("Next Steps")
    print("=" * 70)
    print("1. Start the API server:")
    print("   uvicorn src.api.main:app --reload")
    print("\n2. View data in UI:")
    print("   - Start UI: cd ui && npm run dev")
    print("   - Navigate to http://localhost:5173")
    print("   - Login with tenant: TENANT_FINANCE_001")
    print("=" * 70)
    
    return 0


if __name__ == "__main__":
    from sqlalchemy import select
    sys.exit(asyncio.run(main()))

