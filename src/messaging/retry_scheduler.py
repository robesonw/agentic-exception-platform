"""
Retry Scheduler for Phase 9.

DB-driven retry mechanism with exponential backoff.
Tracks retry attempts in event_processing table and re-publishes events after delay.

Reference: docs/phase9-async-scale-mvp.md Section 7.3
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from src.events.schema import CanonicalEvent
from src.events.types import DeadLettered, RetryScheduled
from src.infrastructure.repositories.dead_letter_repository import (
    DeadLetterEventRepository,
)
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.messaging.retry_policy import RetryPolicyRegistry
from src.observability.prometheus_metrics import record_retry, record_dlq, update_dlq_size

logger = logging.getLogger(__name__)


class RetrySchedulerError(Exception):
    """Raised when retry scheduler operations fail."""

    pass


class RetryScheduler:
    """
    DB-driven retry scheduler with exponential backoff.
    
    Responsibilities:
    - Track retry attempts in event_processing table
    - Schedule retries with exponential backoff delays
    - Emit RetryScheduled events
    - Re-publish events to broker after delay
    """
    
    def __init__(
        self,
        event_processing_repo: EventProcessingRepository,
        event_publisher: EventPublisherService,
        broker: Broker,
        retry_policy_registry: Optional[RetryPolicyRegistry] = None,
        dlq_repository: Optional[DeadLetterEventRepository] = None,
    ):
        """
        Initialize retry scheduler.
        
        Args:
            event_processing_repo: EventProcessingRepository for tracking retry attempts
            event_publisher: EventPublisherService for re-publishing events
            broker: Broker for publishing events
            retry_policy_registry: Optional RetryPolicyRegistry (creates default if None)
            dlq_repository: Optional DeadLetterEventRepository for DLQ persistence
        """
        self.event_processing_repo = event_processing_repo
        self.event_publisher = event_publisher
        self.broker = broker
        self.retry_policy_registry = retry_policy_registry or RetryPolicyRegistry()
        self.dlq_repository = dlq_repository
        
        # Background task for processing scheduled retries
        self._retry_task: Optional[asyncio.Task] = None
        self._running = False
        
        logger.info("Initialized RetryScheduler")
    
    async def schedule_retry(
        self,
        event: CanonicalEvent,
        worker_type: str,
        error_message: str,
    ) -> bool:
        """
        Schedule a retry for a failed event.
        
        Args:
            event: CanonicalEvent that failed
            worker_type: Worker type that failed to process the event
            error_message: Error message from the failure
            
        Returns:
            True if retry was scheduled, False if max retries exceeded
        """
        event_type = event.event_type
        event_id = event.event_id
        tenant_id = event.tenant_id
        
        # Get retry policy for event type
        max_retries = self.retry_policy_registry.get_max_retries(event_type)
        
        # Get current retry count from event_processing record
        retry_count = await self._get_retry_count(event_id, worker_type)
        
        # Check if max retries exceeded
        if retry_count >= max_retries:
            logger.warning(
                f"Max retries ({max_retries}) exceeded for event {event_id} "
                f"(worker: {worker_type}), moving to DLQ"
            )
            
            # Move to Dead Letter Queue
            await self._move_to_dlq(
                event=event,
                worker_type=worker_type,
                retry_count=retry_count,
                error_message=error_message,
            )
            
            return False
        
        # Calculate next retry attempt number
        next_attempt = retry_count + 1
        
        # Calculate delay using exponential backoff
        delay_seconds = self.retry_policy_registry.calculate_delay(
            event_type, next_attempt
        )
        
        # Calculate retry time
        retry_time = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
        
        # Mark event as failed and update retry metadata
        try:
            await self.event_processing_repo.mark_failed(
                event_id=event_id,
                worker_type=worker_type,
                tenant_id=tenant_id,
                exception_id=event.exception_id,
                error_message=f"{error_message} (retry {next_attempt}/{max_retries})",
            )
        except Exception as e:
            logger.error(
                f"Failed to mark event as failed for retry scheduling: {e}",
                exc_info=True,
            )
            raise RetrySchedulerError(f"Failed to mark event as failed: {e}") from e
        
        # Record retry metric
        record_retry(
            worker_type=worker_type,
            event_type=event_type,
            tenant_id=tenant_id,
            retry_attempt=next_attempt,
        )
        
        # Store retry metadata in event_processing (via metadata field if available)
        # For now, we'll track retry count via error_message pattern or separate tracking
        
        # Emit RetryScheduled event
        try:
            await self._emit_retry_scheduled_event(
                event=event,
                worker_type=worker_type,
                retry_count=next_attempt,
                delay_seconds=delay_seconds,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(
                f"Failed to emit RetryScheduled event: {e}",
                exc_info=True,
            )
            # Don't fail the retry scheduling if event emission fails
        
        # Schedule re-publish after delay
        try:
            await self._schedule_republish(event, worker_type, delay_seconds)
        except Exception as e:
            logger.error(
                f"Failed to schedule event re-publish: {e}",
                exc_info=True,
            )
            raise RetrySchedulerError(f"Failed to schedule event re-publish: {e}") from e
        
        logger.info(
            f"Scheduled retry {next_attempt}/{max_retries} for event {event_id} "
            f"(worker: {worker_type}, delay: {delay_seconds}s)"
        )
        
        return True
    
    async def _get_retry_count(
        self, event_id: str, worker_type: str
    ) -> int:
        """
        Get current retry count for an event.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            
        Returns:
            Current retry count (0 if not found)
        """
        # Get processing record to extract retry count
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
        )
        
        result = await self.event_processing_repo.session.execute(query)
        processing = result.scalar_one_or_none()
        
        if not processing:
            return 0
        
        # Extract retry count from error_message if available
        # Format: "error message (retry X/max)"
        if processing.error_message:
            import re
            match = re.search(r'\(retry (\d+)/', processing.error_message)
            if match:
                return int(match.group(1))
        
        # If status is failed but no retry count in error message, assume 1
        if processing.status.value == "failed":
            return 1
        
        return 0
    
    async def _emit_retry_scheduled_event(
        self,
        event: CanonicalEvent,
        worker_type: str,
        retry_count: int,
        delay_seconds: float,
        error_message: str,
    ) -> None:
        """
        Emit RetryScheduled event.
        
        Args:
            event: Original event that failed
            worker_type: Worker type that failed
            retry_count: Current retry attempt number
            delay_seconds: Delay before retry
            error_message: Error message from failure
        """
        retry_scheduled_event = RetryScheduled.create(
            tenant_id=event.tenant_id,
            retry_reason=f"Worker {worker_type} failed: {error_message}",
            retry_count=retry_count,
            retry_delay_seconds=delay_seconds,
            original_event_id=event.event_id,
            exception_id=event.exception_id,
            correlation_id=event.correlation_id,
        )
        
        # Publish RetryScheduled event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=retry_scheduled_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted RetryScheduled event: original_event_id={event.event_id}, "
            f"retry_count={retry_count}, delay={delay_seconds}s"
        )
    
    async def _schedule_republish(
        self,
        event: CanonicalEvent,
        worker_type: str,
        delay_seconds: float,
    ) -> None:
        """
        Schedule event re-publish after delay.
        
        Args:
            event: Event to re-publish
            worker_type: Worker type that should process it
            delay_seconds: Delay before re-publish
        """
        # For MVP, we'll use asyncio.sleep and re-publish directly
        # In production, we'd use a proper job scheduler (e.g., Celery, APScheduler)
        
        async def _republish_after_delay():
            """Re-publish event after delay."""
            try:
                await asyncio.sleep(delay_seconds)
                
                logger.info(
                    f"Re-publishing event {event.event_id} after {delay_seconds}s delay "
                    f"(worker: {worker_type})"
                )
                
                # Re-publish event to broker
                await self.event_publisher.publish_event(
                    topic="exceptions",
                    event=event.model_dump(by_alias=True),
                )
                
                logger.info(
                    f"Re-published event {event.event_id} for retry "
                    f"(worker: {worker_type})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to re-publish event {event.event_id} after delay: {e}",
                    exc_info=True,
                )
        
        # Schedule background task
        asyncio.create_task(_republish_after_delay())
    
    async def start(self) -> None:
        """Start retry scheduler background tasks."""
        if self._running:
            logger.warning("RetryScheduler is already running")
            return
        
        self._running = True
        logger.info("RetryScheduler started")
    
    async def stop(self) -> None:
        """Stop retry scheduler background tasks."""
        if not self._running:
            return
        
        self._running = False
        
        # Cancel background tasks
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass
        
        logger.info("RetryScheduler stopped")
    
    async def _move_to_dlq(
        self,
        event: CanonicalEvent,
        worker_type: str,
        retry_count: int,
        error_message: str,
    ) -> None:
        """
        Move failed event to Dead Letter Queue.
        
        Args:
            event: CanonicalEvent that failed
            worker_type: Worker type that failed
            retry_count: Number of retry attempts made
            error_message: Final error message
        """
        if not self.dlq_repository:
            logger.warning(
                f"DLQ repository not configured, cannot persist DLQ entry for event {event.event_id}"
            )
            # Still emit DeadLettered event even if repository is not configured
        else:
            try:
                # Persist DLQ entry
                await self.dlq_repository.create_dlq_entry(
                    event_id=event.event_id,
                    event_type=event.event_type,
                    tenant_id=event.tenant_id,
                    original_topic="exceptions",  # Default topic, could be extracted from metadata
                    failure_reason=error_message,
                    retry_count=retry_count,
                    worker_type=worker_type,
                    payload=event.payload,
                    exception_id=event.exception_id,
                    metadata=event.metadata,
                )
                
                # Record DLQ counter
                try:
                    record_dlq(
                        worker_type=worker_type,
                        event_type=event.event_type,
                        tenant_id=event.tenant_id,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to record DLQ counter: {e}",
                        exc_info=True,
                    )
                
                # Update DLQ size metric
                # Get current DLQ size for this tenant/event_type/worker_type
                try:
                    dlq_result = await self.dlq_repository.list_dlq_entries(
                        tenant_id=event.tenant_id,
                        event_type=event.event_type,
                        worker_type=worker_type,
                        limit=1,
                        offset=0,
                    )
                    dlq_size = dlq_result.total
                    update_dlq_size(
                        tenant_id=event.tenant_id,
                        event_type=event.event_type,
                        worker_type=worker_type,
                        size=dlq_size,
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to update DLQ size metric: {e}",
                        exc_info=True,
                    )
                    # Don't fail DLQ persistence if metrics update fails
                
                logger.info(
                    f"Persisted DLQ entry for event {event.event_id} "
                    f"(tenant: {event.tenant_id}, retry_count: {retry_count})"
                )
            except Exception as e:
                logger.error(
                    f"Failed to persist DLQ entry for event {event.event_id}: {e}",
                    exc_info=True,
                )
                # Continue to emit DeadLettered event even if persistence failed
        
        # Emit DeadLettered event
        try:
            await self._emit_dead_lettered_event(
                event=event,
                worker_type=worker_type,
                retry_count=retry_count,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(
                f"Failed to emit DeadLettered event for event {event.event_id}: {e}",
                exc_info=True,
            )
    
    async def _emit_dead_lettered_event(
        self,
        event: CanonicalEvent,
        worker_type: str,
        retry_count: int,
        error_message: str,
    ) -> None:
        """
        Emit DeadLettered event.
        
        Args:
            event: Original event that failed
            worker_type: Worker type that failed
            retry_count: Number of retry attempts made
            error_message: Final error message
        """
        dead_lettered_event = DeadLettered.create(
            tenant_id=event.tenant_id,
            original_event_id=event.event_id,
            original_event_type=event.event_type,
            failure_reason=error_message,
            retry_count=retry_count,
            original_topic="exceptions",  # Default topic
            exception_id=event.exception_id,
            correlation_id=event.correlation_id,
        )
        
        # Publish DeadLettered event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=dead_lettered_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted DeadLettered event: original_event_id={event.event_id}, "
            f"retry_count={retry_count}"
        )

