"""
Playbook step repository for playbook step management.

Phase 6 P6-14: PlaybookStepRepository with CRUD operations and step ordering.

Note: Playbook steps are tenant-specific via their parent playbook, so this
repository enforces strict tenant isolation by verifying the parent playbook
belongs to the tenant.
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import Playbook, PlaybookStep
from src.repository.base import AbstractBaseRepository
from src.repository.dto import PlaybookStepCreateDTO

logger = logging.getLogger(__name__)


class PlaybookStepRepository(AbstractBaseRepository[PlaybookStep]):
    """
    Repository for playbook step management.
    
    Provides:
    - Get steps for a playbook with tenant isolation
    - Create new step (with automatic step_order assignment)
    - Update step ordering
    - Tenant isolation enforcement via parent playbook
    
    All operations enforce strict tenant isolation by verifying the parent
    playbook belongs to the tenant before allowing any step operations.
    """

    async def _verify_playbook_tenant(
        self,
        playbook_id: int,
        tenant_id: str,
    ) -> Optional[Playbook]:
        """
        Verify that a playbook exists and belongs to the tenant.
        
        Args:
            playbook_id: Playbook identifier
            tenant_id: Tenant identifier
            
        Returns:
            Playbook instance if found and belongs to tenant, None otherwise
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_id < 1
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if playbook_id < 1:
            raise ValueError("playbook_id must be >= 1")
        
        query = select(Playbook).where(
            Playbook.playbook_id == playbook_id,
            Playbook.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_steps(
        self,
        playbook_id: int,
        tenant_id: str,
    ) -> list[PlaybookStep]:
        """
        Get all steps for a playbook with tenant isolation.
        
        Steps are returned ordered by step_order (ascending).
        
        Args:
            playbook_id: Playbook identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            List of PlaybookStep instances, ordered by step_order
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_id < 1
            ValueError: If playbook does not exist or does not belong to tenant
        """
        # Verify playbook belongs to tenant
        playbook = await self._verify_playbook_tenant(playbook_id, tenant_id)
        if playbook is None:
            raise ValueError(
                f"Playbook not found or does not belong to tenant: playbook_id={playbook_id}, tenant_id={tenant_id}"
            )
        
        query = (
            select(PlaybookStep)
            .where(PlaybookStep.playbook_id == playbook_id)
            .order_by(PlaybookStep.step_order.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_step(
        self,
        playbook_id: int,
        step_data: PlaybookStepCreateDTO,
        tenant_id: str,
    ) -> PlaybookStep:
        """
        Create a new playbook step.
        
        The step_order is automatically assigned as the next available order number
        (highest existing step_order + 1, or 1 if no steps exist).
        
        Args:
            playbook_id: Playbook identifier
            step_data: PlaybookStepCreateDTO with step details
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Created PlaybookStep instance
            
        Raises:
            ValueError: If tenant_id is None/empty, playbook_id < 1, or step_data is invalid
            ValueError: If playbook does not exist or does not belong to tenant
        """
        # Verify playbook belongs to tenant
        playbook = await self._verify_playbook_tenant(playbook_id, tenant_id)
        if playbook is None:
            raise ValueError(
                f"Playbook not found or does not belong to tenant: playbook_id={playbook_id}, tenant_id={tenant_id}"
            )
        
        # Get existing steps to determine next step_order
        existing_steps = await self.get_steps(playbook_id, tenant_id)
        next_order = len(existing_steps) + 1 if existing_steps else 1
        
        # Create new step
        step = PlaybookStep(
            playbook_id=playbook_id,
            step_order=next_order,
            name=step_data.name,
            action_type=step_data.action_type,
            params=step_data.params,
        )
        
        self.session.add(step)
        await self.session.flush()
        await self.session.refresh(step)
        
        logger.info(
            f"Created playbook step: step_id={step.step_id}, playbook_id={playbook_id}, "
            f"step_order={next_order}, tenant_id={tenant_id}"
        )
        return step

    async def update_step_order(
        self,
        playbook_id: int,
        ordered_step_ids: list[int],
        tenant_id: str,
    ) -> list[PlaybookStep]:
        """
        Update the order of steps for a playbook.
        
        Reorders steps based on the provided list of step_ids. The order in the list
        determines the new step_order values (1, 2, 3, ...).
        
        Args:
            playbook_id: Playbook identifier
            ordered_step_ids: List of step_ids in the desired order
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            List of updated PlaybookStep instances, ordered by new step_order
            
        Raises:
            ValueError: If tenant_id is None/empty, playbook_id < 1, or ordered_step_ids is empty
            ValueError: If playbook does not exist or does not belong to tenant
            ValueError: If any step_id in ordered_step_ids does not belong to the playbook
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if playbook_id < 1:
            raise ValueError("playbook_id must be >= 1")
        if not ordered_step_ids:
            raise ValueError("ordered_step_ids cannot be empty")
        
        # Verify playbook belongs to tenant
        playbook = await self._verify_playbook_tenant(playbook_id, tenant_id)
        if playbook is None:
            raise ValueError(
                f"Playbook not found or does not belong to tenant: playbook_id={playbook_id}, tenant_id={tenant_id}"
            )
        
        # Get all steps for the playbook
        all_steps = await self.get_steps(playbook_id, tenant_id)
        step_dict = {step.step_id: step for step in all_steps}
        
        # Verify all step_ids belong to this playbook
        invalid_step_ids = [sid for sid in ordered_step_ids if sid not in step_dict]
        if invalid_step_ids:
            raise ValueError(
                f"Step IDs do not belong to playbook: {invalid_step_ids}, playbook_id={playbook_id}"
            )
        
        # Verify all steps are included (no missing steps)
        provided_step_ids = set(ordered_step_ids)
        all_step_ids = set(step_dict.keys())
        missing_step_ids = all_step_ids - provided_step_ids
        if missing_step_ids:
            raise ValueError(
                f"All steps must be included in reordering. Missing step IDs: {missing_step_ids}"
            )
        
        # Update step_order for each step
        updated_steps = []
        for new_order, step_id in enumerate(ordered_step_ids, start=1):
            step = step_dict[step_id]
            step.step_order = new_order
            updated_steps.append(step)
        
        await self.session.flush()
        
        # Refresh all updated steps
        for step in updated_steps:
            await self.session.refresh(step)
        
        logger.info(
            f"Updated step order for playbook: playbook_id={playbook_id}, "
            f"tenant_id={tenant_id}, {len(updated_steps)} steps reordered"
        )
        
        # Return steps in new order
        return updated_steps

    # AbstractBaseRepository implementations
    # Note: These methods enforce tenant isolation via parent playbook

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[PlaybookStep]:
        """
        Get playbook step by ID with tenant isolation.
        
        Verifies the step belongs to a playbook that belongs to the tenant.
        
        Args:
            id: Playbook step database ID (as string)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            PlaybookStep instance or None if not found or tenant mismatch
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            step_id = int(id)
        except (ValueError, TypeError):
            return None
        
        # Get step and verify it belongs to a playbook owned by the tenant
        query = select(PlaybookStep).where(PlaybookStep.step_id == step_id)
        result = await self.session.execute(query)
        step = result.scalar_one_or_none()
        
        if step is None:
            return None
        
        # Verify parent playbook belongs to tenant
        playbook = await self._verify_playbook_tenant(step.playbook_id, tenant_id)
        if playbook is None:
            return None  # Step belongs to a playbook that doesn't belong to tenant
        
        return step

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ):
        """
        List playbook steps for a tenant with pagination.
        
        This method is less efficient than get_steps() because it must join
        with playbooks to filter by tenant. Use get_steps() when you know the playbook_id.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (playbook_id can be passed here)
            
        Returns:
            PaginatedResult with playbook steps
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        from src.repository.base import PaginatedResult
        
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Join with playbook to filter by tenant_id
        query = (
            select(PlaybookStep)
            .join(Playbook, PlaybookStep.playbook_id == Playbook.playbook_id)
            .where(Playbook.tenant_id == tenant_id)
        )
        
        # Apply playbook_id filter if provided
        if "playbook_id" in filters:
            playbook_id = filters["playbook_id"]
            if playbook_id:
                query = query.where(PlaybookStep.playbook_id == playbook_id)
        
        # Order by playbook_id, then step_order
        query = query.order_by(PlaybookStep.playbook_id.asc(), PlaybookStep.step_order.asc())
        
        # Execute paginated query
        return await self._execute_paginated(query, page, page_size)


