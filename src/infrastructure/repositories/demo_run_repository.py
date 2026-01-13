"""
Demo Run Repository - Database access for demo run tracking.

Provides CRUD operations for the demo_run table with overlap prevention
and status management.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DemoRun, DemoRunMode, DemoRunStatus

logger = logging.getLogger(__name__)


class DemoRunConflictError(Exception):
    """Error when trying to start a run while another is active."""
    
    def __init__(self, active_run_id: UUID, message: str = None):
        self.active_run_id = active_run_id
        super().__init__(message or f"A demo run is already active: {active_run_id}. Stop it first.")


class DemoRunRepository:
    """
    Repository for demo run tracking.
    
    Enforces single active run rule (overlap prevention) and provides
    status management for burst, scheduled, and continuous runs.
    """
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def get_active_run(self) -> Optional[DemoRun]:
        """
        Get the currently active (running) demo run if any.
        
        Returns:
            Active DemoRun or None.
        """
        result = await self.session.execute(
            select(DemoRun)
            .where(DemoRun.status == DemoRunStatus.RUNNING)
            .order_by(DemoRun.started_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()
    
    async def get_by_id(self, run_id: UUID) -> Optional[DemoRun]:
        """Get a demo run by ID."""
        result = await self.session.execute(
            select(DemoRun).where(DemoRun.run_id == run_id)
        )
        return result.scalar_one_or_none()
    
    async def list_runs(
        self,
        limit: int = 50,
        status: Optional[DemoRunStatus] = None,
        mode: Optional[DemoRunMode] = None,
    ) -> list[DemoRun]:
        """
        List demo runs with optional filters.
        
        Args:
            limit: Maximum number of runs to return.
            status: Filter by status.
            mode: Filter by mode.
            
        Returns:
            List of DemoRun instances.
        """
        query = select(DemoRun).order_by(DemoRun.created_at.desc()).limit(limit)
        
        if status:
            query = query.where(DemoRun.status == status)
        if mode:
            query = query.where(DemoRun.mode == mode)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())
    
    async def create_run(
        self,
        mode: DemoRunMode,
        scenario_ids: list[str],
        tenant_keys: list[str],
        frequency_seconds: Optional[int] = None,
        duration_seconds: Optional[int] = None,
        burst_count: Optional[int] = None,
        intensity_multiplier: float = 1.0,
        created_by: Optional[str] = None,
    ) -> DemoRun:
        """
        Create a new demo run (checks for active runs first).
        
        Args:
            mode: Run mode (burst, scheduled, continuous).
            scenario_ids: List of scenario IDs to run.
            tenant_keys: Target tenant keys (empty = all demo tenants).
            frequency_seconds: Generation frequency.
            duration_seconds: Scheduled run duration.
            burst_count: Number of exceptions for burst mode.
            intensity_multiplier: Intensity multiplier.
            created_by: User/system creating the run.
            
        Returns:
            Created DemoRun instance.
            
        Raises:
            DemoRunConflictError: If another run is already active.
        """
        # Check for active run
        active = await self.get_active_run()
        if active:
            raise DemoRunConflictError(active.run_id)
        
        now = datetime.now(timezone.utc)
        ends_at = None
        
        # Calculate ends_at for scheduled runs
        if mode == DemoRunMode.SCHEDULED and duration_seconds:
            from datetime import timedelta
            ends_at = now + timedelta(seconds=duration_seconds)
        
        run = DemoRun(
            run_id=uuid4(),
            status=DemoRunStatus.PENDING,
            mode=mode,
            scenario_ids=scenario_ids,
            tenant_keys=tenant_keys,
            frequency_seconds=frequency_seconds,
            duration_seconds=duration_seconds,
            burst_count=burst_count,
            intensity_multiplier=intensity_multiplier,
            ends_at=ends_at,
            created_at=now,
            created_by=created_by,
        )
        
        self.session.add(run)
        await self.session.flush()
        
        logger.info(f"Created demo run {run.run_id}: mode={mode.value}, scenarios={len(scenario_ids)}")
        
        return run
    
    async def start_run(self, run_id: UUID) -> DemoRun:
        """
        Mark a run as started (transition from pending to running).
        
        Args:
            run_id: Run ID to start.
            
        Returns:
            Updated DemoRun.
            
        Raises:
            ValueError: If run not found or not in pending status.
            DemoRunConflictError: If another run is already active.
        """
        run = await self.get_by_id(run_id)
        if not run:
            raise ValueError(f"Demo run not found: {run_id}")
        
        if run.status != DemoRunStatus.PENDING:
            raise ValueError(f"Cannot start run in {run.status.value} status")
        
        # Check for active run (shouldn't happen but double-check)
        active = await self.get_active_run()
        if active and active.run_id != run_id:
            raise DemoRunConflictError(active.run_id)
        
        now = datetime.now(timezone.utc)
        run.status = DemoRunStatus.RUNNING
        run.started_at = now
        
        # Recalculate ends_at for scheduled runs
        if run.mode == DemoRunMode.SCHEDULED and run.duration_seconds:
            from datetime import timedelta
            run.ends_at = now + timedelta(seconds=run.duration_seconds)
        
        await self.session.flush()
        
        logger.info(f"Started demo run {run_id}")
        
        return run
    
    async def update_progress(
        self,
        run_id: UUID,
        generated_count: Optional[int] = None,
        increment_count: int = 0,
    ) -> DemoRun:
        """
        Update run progress.
        
        Args:
            run_id: Run ID.
            generated_count: Set total count (if provided).
            increment_count: Increment count by this amount.
            
        Returns:
            Updated DemoRun.
        """
        run = await self.get_by_id(run_id)
        if not run:
            raise ValueError(f"Demo run not found: {run_id}")
        
        if generated_count is not None:
            run.generated_count = generated_count
        elif increment_count > 0:
            run.generated_count = (run.generated_count or 0) + increment_count
        
        run.last_tick_at = datetime.now(timezone.utc)
        
        await self.session.flush()
        
        return run
    
    async def complete_run(
        self,
        run_id: UUID,
        status: DemoRunStatus = DemoRunStatus.COMPLETED,
        error: Optional[str] = None,
    ) -> DemoRun:
        """
        Mark a run as completed, cancelled, or failed.
        
        Args:
            run_id: Run ID.
            status: Final status.
            error: Error message for failed runs.
            
        Returns:
            Updated DemoRun.
        """
        run = await self.get_by_id(run_id)
        if not run:
            raise ValueError(f"Demo run not found: {run_id}")
        
        run.status = status
        run.completed_at = datetime.now(timezone.utc)
        
        if error:
            run.error = error
        
        await self.session.flush()
        
        logger.info(f"Completed demo run {run_id}: status={status.value}, generated={run.generated_count}")
        
        return run
    
    async def stop_active_run(self) -> Optional[DemoRun]:
        """
        Stop the currently active run if any.
        
        Returns:
            Stopped DemoRun or None if no active run.
        """
        active = await self.get_active_run()
        if not active:
            return None
        
        return await self.complete_run(
            active.run_id,
            status=DemoRunStatus.CANCELLED,
        )
    
    async def check_scheduled_expiry(self, run_id: UUID) -> bool:
        """
        Check if a scheduled run has expired and should be stopped.
        
        Args:
            run_id: Run ID.
            
        Returns:
            True if run expired and was stopped.
        """
        run = await self.get_by_id(run_id)
        if not run:
            return False
        
        if run.status != DemoRunStatus.RUNNING:
            return False
        
        if run.mode != DemoRunMode.SCHEDULED:
            return False
        
        if not run.ends_at:
            return False
        
        now = datetime.now(timezone.utc)
        if now >= run.ends_at:
            await self.complete_run(run_id, DemoRunStatus.COMPLETED)
            logger.info(f"Scheduled demo run {run_id} expired and was stopped")
            return True
        
        return False
    
    def run_to_dict(self, run: DemoRun) -> dict:
        """Convert DemoRun to dict for API response."""
        return {
            "run_id": str(run.run_id),
            "status": run.status.value,
            "mode": run.mode.value,
            "scenario_ids": run.scenario_ids or [],
            "tenant_keys": run.tenant_keys or [],
            "frequency_seconds": run.frequency_seconds,
            "duration_seconds": run.duration_seconds,
            "burst_count": run.burst_count,
            "intensity_multiplier": run.intensity_multiplier,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "ends_at": run.ends_at.isoformat() if run.ends_at else None,
            "completed_at": run.completed_at.isoformat() if run.completed_at else None,
            "generated_count": run.generated_count or 0,
            "last_tick_at": run.last_tick_at.isoformat() if run.last_tick_at else None,
            "error": run.error,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "created_by": run.created_by,
        }
