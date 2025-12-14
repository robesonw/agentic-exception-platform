#!/usr/bin/env python3
"""
Quick verification script for demo data.
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import select, func
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.db.models import (
    Exception,
    ExceptionEvent,
    Playbook,
    PlaybookStep,
    ToolDefinition,
    ToolExecution,
    Tenant,
)

async def verify():
    session_factory = get_session_factory()
    async with session_factory() as session:
        # Count exceptions
        exc_result = await session.execute(select(func.count(Exception.exception_id)))
        exc_count = exc_result.scalar()
        
        # Count events
        events_result = await session.execute(select(func.count(ExceptionEvent.event_id)))
        events_count = events_result.scalar()
        
        # Count playbooks
        playbooks_result = await session.execute(select(func.count(Playbook.playbook_id)))
        playbooks_count = playbooks_result.scalar()
        
        # Count playbook steps
        steps_result = await session.execute(select(func.count(PlaybookStep.step_id)))
        steps_count = steps_result.scalar()
        
        # Count tools
        tools_result = await session.execute(select(func.count(ToolDefinition.tool_id)))
        tools_count = tools_result.scalar()
        
        # Count tool executions
        exec_result = await session.execute(select(func.count(ToolExecution.id)))
        exec_count = exec_result.scalar()
        
        # Count tenants
        tenants_result = await session.execute(select(func.count(Tenant.tenant_id)))
        tenants_count = tenants_result.scalar()
        
        print("=" * 60)
        print("DEMO DATA VERIFICATION")
        print("=" * 60)
        print(f"[OK] Tenants: {tenants_count}")
        print(f"[OK] Exceptions: {exc_count}")
        print(f"[OK] Events: {events_count}")
        print(f"[OK] Playbooks: {playbooks_count}")
        print(f"[OK] Playbook Steps: {steps_count}")
        print(f"[OK] Tools: {tools_count}")
        print(f"[OK] Tool Executions: {exec_count}")
        print("=" * 60)
        
        # Check per tenant
        for tenant_id in ["TENANT_FINANCE_001", "TENANT_HEALTH_001"]:
            exc_tenant = await session.execute(
                select(func.count(Exception.exception_id)).where(Exception.tenant_id == tenant_id)
            )
            events_tenant = await session.execute(
                select(func.count(ExceptionEvent.event_id)).where(ExceptionEvent.tenant_id == tenant_id)
            )
            print(f"\n{tenant_id}:")
            print(f"  - Exceptions: {exc_tenant.scalar()}")
            print(f"  - Events: {events_tenant.scalar()}")
        
        print("\n[OK] Verification complete!")
        return exc_count >= 1000

if __name__ == "__main__":
    success = asyncio.run(verify())
    sys.exit(0 if success else 1)

