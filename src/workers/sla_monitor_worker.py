"""
SLA Monitor Worker for Phase 9.

Periodically monitors exceptions for SLA deadlines and emits:
- SLAImminent events when threshold is reached (configurable, e.g., 80% of SLA)
- SLAExpired events when SLA is breached

Phase 9 P9-22: SLA monitoring and alerts.
Reference: docs/phase9-async-scale-mvp.md Section 4.2, Section 10.1
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.events.types import SLAImminent, SLAExpired
from src.infrastructure.db.models import Exception as ExceptionModel, ExceptionStatus, Tenant, TenantStatus
from src.infrastructure.db.session import get_db_session_context
from src.messaging.event_publisher import EventPublisherService
from src.repository.exceptions_repository import ExceptionRepository
from src.infrastructure.repositories.tenant_repository import TenantRepository

logger = logging.getLogger(__name__)


class SLAMonitorWorker:
    """
    Worker that monitors exceptions for SLA deadlines.
    
    Runs periodically to:
    - Check exceptions with SLA deadlines
    - Emit SLAImminent events when threshold is reached
    - Emit SLAExpired events when SLA is breached
    
    Threshold is configurable per tenant (default: 0.8 = 80%).
    """
    
    def __init__(
        self,
        event_publisher: EventPublisherService,
        check_interval_seconds: int = 60,
        default_threshold_percentage: float = 0.8,
        tenant_thresholds: Optional[dict[str, float]] = None,
    ):
        """
        Initialize SLA monitor worker.
        
        Args:
            event_publisher: EventPublisherService for emitting SLA events
            check_interval_seconds: Interval between SLA checks (default: 60 seconds)
            default_threshold_percentage: Default threshold percentage for SLAImminent (default: 0.8 = 80%)
            tenant_thresholds: Optional dict mapping tenant_id to threshold percentage
        """
        self.event_publisher = event_publisher
        self.check_interval_seconds = check_interval_seconds
        self.default_threshold_percentage = default_threshold_percentage
        self.tenant_thresholds = tenant_thresholds or {}
        
        # Worker state
        self._running = False
        
        # Track which exceptions have already emitted SLAImminent to avoid duplicates
        # Key: "{tenant_id}:{exception_id}"
        self._emitted_imminent: set[str] = set()
        self._emitted_expired: set[str] = set()
        
        logger.info(
            f"Initialized SLAMonitorWorker: check_interval={check_interval_seconds}s, "
            f"default_threshold={default_threshold_percentage}"
        )
    
    def get_threshold_for_tenant(self, tenant_id: str) -> float:
        """
        Get SLA threshold percentage for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Threshold percentage (0.0 to 1.0)
        """
        return self.tenant_thresholds.get(tenant_id, self.default_threshold_percentage)
    
    async def _load_tenant_thresholds(self, session: AsyncSession) -> dict[str, float]:
        """
        Load tenant-specific SLA thresholds from database.
        
        Phase 9 P9-22: Threshold configurable per tenant.
        For MVP, we use a simple approach: check tenant metadata or use defaults.
        In production, this would read from tenant configuration table.
        
        Args:
            session: Database session
            
        Returns:
            Dict mapping tenant_id to threshold percentage
        """
        thresholds: dict[str, float] = {}
        
        try:
            # For MVP, we'll use the tenant_thresholds dict passed to constructor
            # In production, we'd query a tenant_config table or tenant metadata
            tenant_repo = TenantRepository(session)
            
            # Get all active tenants
            query = select(Tenant).where(Tenant.status == TenantStatus.ACTIVE)
            result = await session.execute(query)
            tenants = result.scalars().all()
            
            # For each tenant, use configured threshold or default
            for tenant in tenants:
                thresholds[tenant.tenant_id] = self.tenant_thresholds.get(
                    tenant.tenant_id,
                    self.default_threshold_percentage,
                )
        except Exception as e:
            logger.warning(f"Error loading tenant thresholds: {e}, using defaults")
            # Return empty dict, will use defaults
        
        return thresholds
    
    async def _check_sla_deadlines(self) -> None:
        """
        Check all exceptions with SLA deadlines and emit events as needed.
        
        This method:
        1. Finds exceptions with SLA deadlines that haven't expired yet
        2. Checks if threshold is reached (SLAImminent)
        3. Checks if SLA is breached (SLAExpired)
        4. Emits appropriate events
        """
        try:
            async with get_db_session_context() as session:
                # Load tenant thresholds
                tenant_thresholds = await self._load_tenant_thresholds(session)
                
                now = datetime.now(timezone.utc)
                
                # Query exceptions with SLA deadlines
                # We need to check:
                # 1. Exceptions approaching threshold (SLAImminent)
                # 2. Exceptions past deadline (SLAExpired)
                
                # Get exceptions with SLA deadlines that are not yet expired
                # (for SLAImminent check)
                query_imminent = select(ExceptionModel).where(
                    and_(
                        ExceptionModel.sla_deadline.isnot(None),
                        ExceptionModel.sla_deadline > now,  # Not yet expired
                        ExceptionModel.status.in_([ExceptionStatus.OPEN, ExceptionStatus.ANALYZING]),
                    )
                )
                
                result_imminent = await session.execute(query_imminent)
                exceptions_imminent = result_imminent.scalars().all()
                
                # Check each exception for SLAImminent
                for exception in exceptions_imminent:
                    threshold = tenant_thresholds.get(
                        exception.tenant_id,
                        self.default_threshold_percentage,
                    )
                    await self._check_sla_imminent(exception, now, threshold)
                
                # Get exceptions with SLA deadlines that have expired
                # (for SLAExpired check)
                query_expired = select(ExceptionModel).where(
                    and_(
                        ExceptionModel.sla_deadline.isnot(None),
                        ExceptionModel.sla_deadline <= now,  # Expired
                        ExceptionModel.status.in_([ExceptionStatus.OPEN, ExceptionStatus.ANALYZING]),
                    )
                )
                
                result_expired = await session.execute(query_expired)
                exceptions_expired = result_expired.scalars().all()
                
                # Check each exception for SLAExpired
                for exception in exceptions_expired:
                    await self._check_sla_expired(exception, now)
        
        except Exception as e:
            logger.error(f"Error checking SLA deadlines: {e}", exc_info=True)
    
    async def _check_sla_imminent(
        self,
        exception: ExceptionModel,
        now: datetime,
        threshold: float,
    ) -> None:
        """
        Check if exception has reached SLAImminent threshold and emit event if needed.
        
        Args:
            exception: Exception instance with SLA deadline
            now: Current timestamp
            threshold: Threshold percentage for this tenant
        """
        if not exception.sla_deadline:
            return
        
        # Calculate time remaining
        time_remaining = (exception.sla_deadline - now).total_seconds()
        
        if time_remaining <= 0:
            # Already expired, skip
            return
        
        # Calculate total SLA duration (from created_at to sla_deadline)
        if not exception.created_at:
            logger.warning(f"Exception {exception.exception_id} has no created_at, skipping SLA check")
            return
        
        total_sla_duration = (exception.sla_deadline - exception.created_at).total_seconds()
        if total_sla_duration <= 0:
            logger.warning(f"Exception {exception.exception_id} has invalid SLA duration, skipping")
            return
        
        # Calculate percentage of SLA elapsed
        elapsed = (now - exception.created_at).total_seconds()
        percentage_elapsed = elapsed / total_sla_duration
        
        # Check if threshold is reached
        if percentage_elapsed >= threshold:
            # Check if we've already emitted SLAImminent for this exception
            exception_key = f"{exception.tenant_id}:{exception.exception_id}"
            if exception_key not in self._emitted_imminent:
                # Emit SLAImminent event
                await self._emit_sla_imminent(exception, time_remaining, threshold)
                self._emitted_imminent.add(exception_key)
    
    async def _check_sla_expired(self, exception: Exception, now: datetime) -> None:
        """
        Check if exception has breached SLA deadline and emit event if needed.
        
        Args:
            exception: Exception instance with SLA deadline
            now: Current timestamp
        """
        if not exception.sla_deadline:
            return
        
        # Calculate breach duration
        breach_duration = (now - exception.sla_deadline).total_seconds()
        
        if breach_duration < 0:
            # Not yet expired
            return
        
        # Check if we've already emitted SLAExpired for this exception
        exception_key = f"{exception.tenant_id}:{exception.exception_id}"
        if exception_key not in self._emitted_expired:
            # Emit SLAExpired event
            await self._emit_sla_expired(exception, breach_duration)
            self._emitted_expired.add(exception_key)
    
    async def _emit_sla_imminent(
        self,
        exception: ExceptionModel,
        time_remaining_seconds: float,
        threshold_percentage: float,
    ) -> None:
        """
        Emit SLAImminent event.
        
        Args:
            exception: Exception instance
            time_remaining_seconds: Time remaining until SLA deadline
            threshold_percentage: Threshold percentage that triggered this event
        """
        try:
            sla_imminent_event = SLAImminent.create(
                tenant_id=exception.tenant_id,
                exception_id=exception.exception_id,
                sla_deadline=exception.sla_deadline,
                time_remaining_seconds=time_remaining_seconds,
                threshold_percentage=threshold_percentage,
                correlation_id=exception.exception_id,  # Phase 9 P9-21: correlation_id = exception_id
            )
            
            await self.event_publisher.publish_event(
                topic="sla",
                event=sla_imminent_event.model_dump(by_alias=True),
            )
            
            logger.info(
                f"Emitted SLAImminent event: exception_id={exception.exception_id}, "
                f"tenant_id={exception.tenant_id}, time_remaining={time_remaining_seconds:.1f}s, "
                f"threshold={threshold_percentage}"
            )
        except Exception as e:
            logger.error(
                f"Failed to emit SLAImminent event for exception {exception.exception_id}: {e}",
                exc_info=True,
            )
    
    async def _emit_sla_expired(
        self,
        exception: ExceptionModel,
        breach_duration_seconds: float,
    ) -> None:
        """
        Emit SLAExpired event.
        
        Args:
            exception: Exception instance
            breach_duration_seconds: Duration since SLA deadline breach
        """
        try:
            sla_expired_event = SLAExpired.create(
                tenant_id=exception.tenant_id,
                exception_id=exception.exception_id,
                sla_deadline=exception.sla_deadline,
                breach_duration_seconds=breach_duration_seconds,
                correlation_id=exception.exception_id,  # Phase 9 P9-21: correlation_id = exception_id
            )
            
            await self.event_publisher.publish_event(
                topic="sla",
                event=sla_expired_event.model_dump(by_alias=True),
            )
            
            logger.warning(
                f"Emitted SLAExpired event: exception_id={exception.exception_id}, "
                f"tenant_id={exception.tenant_id}, breach_duration={breach_duration_seconds:.1f}s"
            )
        except Exception as e:
            logger.error(
                f"Failed to emit SLAExpired event for exception {exception.exception_id}: {e}",
                exc_info=True,
            )
    
    async def run_periodic(self) -> None:
        """
        Run periodic SLA checks.
        
        This method runs in a loop, checking SLA deadlines at the configured interval.
        """
        logger.info("Starting SLA monitor periodic checks")
        
        while self._running:
            try:
                await self._check_sla_deadlines()
            except Exception as e:
                logger.error(f"Error in SLA monitor periodic check: {e}", exc_info=True)
            
            # Wait for next check interval
            await asyncio.sleep(self.check_interval_seconds)
    
    def run(self) -> None:
        """
        Start the SLA monitor worker.
        
        Overrides base class run() to use periodic checks instead of message broker subscription.
        """
        if self._running:
            logger.warning("SLAMonitorWorker is already running")
            return
        
        logger.info("Starting SLAMonitorWorker")
        self._running = True
        
        # Run periodic checks in async context
        try:
            asyncio.run(self.run_periodic())
        except KeyboardInterrupt:
            logger.info("SLAMonitorWorker received interrupt signal")
            self.shutdown()
        except Exception as e:
            logger.error(f"SLAMonitorWorker error: {e}", exc_info=True)
            self.shutdown()
    
    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Shutdown the SLA monitor worker.
        
        Args:
            timeout: Maximum time to wait for shutdown (seconds)
        """
        if not self._running:
            logger.warning("SLAMonitorWorker is not running")
            return
        
        logger.info("Shutting down SLAMonitorWorker...")
        self._running = False
        
        logger.info("SLAMonitorWorker stopped")

