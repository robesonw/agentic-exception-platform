"""
Smoke test for demo data seeding.

Verifies that seeding runs successfully and key tables are populated.
"""

import pytest
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from src.demo.seeder import DemoDataSeeder
from src.infrastructure.db.models import (
    Exception,
    ExceptionEvent,
    Playbook,
    PlaybookStep,
    Tenant,
    ToolDefinition,
    ToolExecution,
)
from src.infrastructure.db.session import get_session_factory


@pytest.mark.asyncio
async def test_seed_single_tenant_smoke():
    """Test seeding a single tenant with small count."""
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        seeder = DemoDataSeeder(session, seed=42)
        tenant_id = "TENANT_TEST_001"
        domain = "CapitalMarketsTrading"
        
        # Reset if exists
        try:
            await seeder.reset_tenant_data(tenant_id)
        except Exception:
            pass  # Ignore if tenant doesn't exist
        
        # Seed tenant
        await seeder.seed_tenant(
            tenant_id=tenant_id,
            tenant_name="Test Tenant",
            domain=domain,
        )
        
        # Seed small number of exceptions
        exception_ids = await seeder.seed_exceptions(
            tenant_id=tenant_id,
            domain=domain,
            count=10,
        )
        
        await session.commit()
        
        # Verify tenant exists
        tenant = await session.execute(
            select(Tenant).where(Tenant.tenant_id == tenant_id)
        )
        tenant_obj = tenant.scalar_one_or_none()
        assert tenant_obj is not None, "Tenant should exist"
        
        # Verify exceptions exist
        exceptions = await session.execute(
            select(Exception).where(Exception.tenant_id == tenant_id)
        )
        exception_list = list(exceptions.scalars().all())
        assert len(exception_list) == 10, f"Expected 10 exceptions, got {len(exception_list)}"
        
        # Verify events exist
        events_count = await session.execute(
            select(func.count(ExceptionEvent.event_id)).where(
                ExceptionEvent.tenant_id == tenant_id
            )
        )
        event_count = events_count.scalar()
        assert event_count > 0, "Should have events"
        assert event_count >= 10, f"Expected at least 10 events, got {event_count}"
        
        # Verify playbooks exist
        playbooks = await session.execute(
            select(Playbook).where(Playbook.tenant_id == tenant_id)
        )
        playbook_list = list(playbooks.scalars().all())
        assert len(playbook_list) > 0, "Should have playbooks"
        
        # Verify playbook steps exist
        if playbook_list:
            playbook_id = playbook_list[0].playbook_id
            steps = await session.execute(
                select(PlaybookStep).where(PlaybookStep.playbook_id == playbook_id)
            )
            step_list = list(steps.scalars().all())
            assert len(step_list) > 0, "Playbook should have steps"
        
        # Verify tools exist
        tools = await session.execute(
            select(ToolDefinition).where(
                (ToolDefinition.tenant_id == tenant_id) | (ToolDefinition.tenant_id.is_(None))
            )
        )
        tool_list = list(tools.scalars().all())
        assert len(tool_list) > 0, "Should have tools"
        
        # Verify tool executions exist (if any exceptions had tool steps)
        executions = await session.execute(
            select(ToolExecution).where(ToolExecution.tenant_id == tenant_id)
        )
        execution_list = list(executions.scalars().all())
        # May be 0 if no exceptions had call_tool steps
        # Just verify query works
        assert execution_list is not None
        
        # Cleanup
        await seeder.reset_tenant_data(tenant_id)
        await session.commit()


@pytest.mark.asyncio
async def test_seed_reset_works():
    """Test that reset properly clears tenant data."""
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        seeder = DemoDataSeeder(session, seed=42)
        tenant_id = "TENANT_TEST_RESET"
        domain = "CapitalMarketsTrading"
        
        # Seed some data
        await seeder.seed_tenant(
            tenant_id=tenant_id,
            tenant_name="Test Reset Tenant",
            domain=domain,
        )
        await seeder.seed_exceptions(tenant_id=tenant_id, domain=domain, count=5)
        await session.commit()
        
        # Verify data exists
        exceptions = await session.execute(
            select(Exception).where(Exception.tenant_id == tenant_id)
        )
        assert len(list(exceptions.scalars().all())) == 5
        
        # Reset
        await seeder.reset_tenant_data(tenant_id)
        await session.commit()
        
        # Verify data is gone
        exceptions_after = await session.execute(
            select(Exception).where(Exception.tenant_id == tenant_id)
        )
        assert len(list(exceptions_after.scalars().all())) == 0
        
        events_after = await session.execute(
            select(ExceptionEvent).where(ExceptionEvent.tenant_id == tenant_id)
        )
        assert len(list(events_after.scalars().all())) == 0









