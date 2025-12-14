#!/usr/bin/env python3
"""Check tenant IDs in database."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.db.models import Tenant, Exception

async def check():
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Get all tenants
        tenants_result = await session.execute(select(Tenant.tenant_id))
        tenant_ids = [t[0] for t in tenants_result.fetchall()]
        print(f"Tenants in DB: {tenant_ids}")
        
        # Get sample exceptions
        excs_result = await session.execute(
            select(Exception.tenant_id, Exception.exception_id).limit(10)
        )
        print("\nSample exceptions:")
        for row in excs_result.fetchall():
            print(f"  {row[0]}: {row[1]}")
        
        # Count per tenant
        for tid in tenant_ids:
            count_result = await session.execute(
                select(Exception).where(Exception.tenant_id == tid)
            )
            count = len(count_result.fetchall())
            print(f"\n{tid}: {count} exceptions")

if __name__ == "__main__":
    asyncio.run(check())

