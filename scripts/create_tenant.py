#!/usr/bin/env python3
"""Create a tenant in the database."""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import text
from src.infrastructure.db.session import get_session_factory

async def create_tenant(tenant_id: str, tenant_name: str):
    """Create a tenant in the database."""
    session_factory = get_session_factory()
    async with session_factory() as session:
        await session.execute(
            text("""
                INSERT INTO tenant (tenant_id, name, status, created_at)
                VALUES (:tenant_id, :tenant_name, 'active', NOW())
                ON CONFLICT (tenant_id) DO NOTHING
            """),
            {"tenant_id": tenant_id, "tenant_name": tenant_name}
        )
        await session.commit()
        print(f"Tenant {tenant_id} created successfully")

if __name__ == "__main__":
    tenant_id = sys.argv[1] if len(sys.argv) > 1 else "TENANT_001"
    tenant_name = sys.argv[2] if len(sys.argv) > 2 else "Test Tenant"
    asyncio.run(create_tenant(tenant_id, tenant_name))

