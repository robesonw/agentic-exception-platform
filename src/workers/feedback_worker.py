"""
FeedbackWorker for Phase 9.

Subscribes to completion events (e.g., PlaybookCompleted, ExceptionResolved),
computes metrics, and emits FeedbackCaptured events.

Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.events.schema import CanonicalEvent
from src.events.types import FeedbackCaptured
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.exception_record import ResolutionStatus
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.base import AgentWorker

logger = logging.getLogger(__name__)


class FeedbackWorker(AgentWorker):
    """
    Worker that processes completion events and captures feedback.
    
    Responsibilities:
    - Subscribe to completion events (PlaybookCompleted, ExceptionResolved, etc.)
    - Compute metrics from completion events
    - Emit FeedbackCaptured events with metrics
    - Ensure idempotency (via base worker)
    - Enforce tenant isolation
    """
    
    # Supported completion event types
    COMPLETION_EVENT_TYPES = [
        "PlaybookCompleted",
        "ExceptionResolved",
        "ToolExecutionCompleted",  # Can also trigger feedback for tool-based resolutions
    ]
    
    def __init__(
        self,
        broker: Broker,
        topics: list[str],
        group_id: str,
        event_publisher: EventPublisherService,
        exception_repository: ExceptionRepository,
        event_processing_repo: Optional[EventProcessingRepository] = None,
    ):
        """
        Initialize FeedbackWorker.
        
        Args:
            broker: Message broker instance
            topics: List of topic names (should include "exceptions" or similar)
            group_id: Consumer group ID
            event_publisher: EventPublisherService for emitting events
            exception_repository: ExceptionRepository for retrieving exception data
            event_processing_repo: Optional EventProcessingRepository for idempotency
        """
        super().__init__(
            broker=broker,
            topics=topics,
            group_id=group_id,
            worker_name="FeedbackWorker",
            event_processing_repo=event_processing_repo,
        )
        
        self.event_publisher = event_publisher
        self.exception_repository = exception_repository
        
        logger.info(
            f"Initialized FeedbackWorker: topics={topics}, group_id={group_id}"
        )
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process completion event and capture feedback.
        
        Args:
            event: CanonicalEvent (should be a completion event type)
            
        Raises:
            ValueError: If event is not a supported completion event type
            Exception: If feedback capture fails
        """
        # Validate event type
        if event.event_type not in self.COMPLETION_EVENT_TYPES:
            raise ValueError(
                f"FeedbackWorker expects completion events ({', '.join(self.COMPLETION_EVENT_TYPES)}), "
                f"got {event.event_type}"
            )
        
        tenant_id = event.tenant_id
        exception_id = event.exception_id
        
        logger.info(
            f"FeedbackWorker processing {event.event_type}: "
            f"tenant_id={tenant_id}, exception_id={exception_id}"
        )
        
        # Get exception from database to determine resolution status
        try:
            exception_db = await self.exception_repository.get_by_id(
                exception_id, tenant_id
            )
            if not exception_db:
                logger.warning(
                    f"Exception {exception_id} not found for tenant {tenant_id}, "
                    f"skipping feedback capture"
                )
                return
        except Exception as e:
            logger.error(
                f"FeedbackWorker failed to get exception from database: {e}",
                exc_info=True,
            )
            raise
        
        # Compute metrics from completion event
        try:
            metrics = await self._compute_metrics(event, exception_db)
        except Exception as e:
            logger.error(
                f"FeedbackWorker failed to compute metrics: {e}",
                exc_info=True,
            )
            raise
        
        # Determine feedback type based on resolution status
        resolution_status = None
        if exception_db.status:
            try:
                resolution_status = ResolutionStatus(exception_db.status.value.upper())
            except (ValueError, AttributeError):
                pass
        
        feedback_type = self._determine_feedback_type(event, resolution_status)
        
        # Build feedback data with metrics
        feedback_data = {
            "event_type": event.event_type,
            "resolution_status": resolution_status.value if resolution_status else None,
            "metrics": metrics,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Emit FeedbackCaptured event
        try:
            await self._emit_feedback_captured_event(
                tenant_id=tenant_id,
                exception_id=exception_id,
                feedback_type=feedback_type,
                feedback_data=feedback_data,
                correlation_id=event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"FeedbackWorker failed to emit FeedbackCaptured event: {e}",
                exc_info=True,
            )
            raise
        
        logger.info(
            f"FeedbackWorker completed processing: exception_id={exception_id}, "
            f"feedback_type={feedback_type}"
        )
    
    async def _compute_metrics(
        self, event: CanonicalEvent, exception_db: Any
    ) -> dict[str, Any]:
        """
        Compute metrics from completion event.
        
        Args:
            event: Completion event
            exception_db: Exception database model
            
        Returns:
            Dictionary of computed metrics
        """
        metrics: dict[str, Any] = {}
        
        # Extract event-specific metrics
        payload = event.payload
        
        if event.event_type == "PlaybookCompleted":
            # Extract playbook metrics
            metrics["playbook_id"] = payload.get("playbook_id")
            metrics["total_steps"] = payload.get("total_steps")
            metrics["completed_steps"] = payload.get("completed_steps")
            metrics["execution_time_seconds"] = payload.get("execution_time_seconds")
            
        elif event.event_type == "ExceptionResolved":
            # Extract resolution metrics
            metrics["resolution_method"] = payload.get("resolution_method")
            metrics["resolution_time_seconds"] = payload.get("resolution_time_seconds")
            metrics["auto_resolved"] = payload.get("auto_resolved", False)
            
        elif event.event_type == "ToolExecutionCompleted":
            # Extract tool execution metrics
            metrics["tool_id"] = payload.get("tool_id")
            metrics["execution_id"] = payload.get("execution_id")
            metrics["execution_status"] = payload.get("status")
            metrics["execution_time_seconds"] = payload.get("execution_time_seconds")
        
        # Add common metrics from exception
        if exception_db:
            metrics["exception_type"] = exception_db.type
            metrics["severity"] = exception_db.severity.value if exception_db.severity else None
            metrics["source_system"] = exception_db.source_system
            
            # Compute time-based metrics if timestamps are available
            if exception_db.created_at and exception_db.updated_at:
                try:
                    time_diff = (exception_db.updated_at - exception_db.created_at).total_seconds()
                    metrics["total_processing_time_seconds"] = time_diff
                except Exception:
                    pass
        
        return metrics
    
    def _determine_feedback_type(
        self, event: CanonicalEvent, resolution_status: Optional[ResolutionStatus]
    ) -> str:
        """
        Determine feedback type based on event and resolution status.
        
        Args:
            event: Completion event
            resolution_status: Exception resolution status
            
        Returns:
            Feedback type string
        """
        # If exception is resolved, it's positive feedback
        if resolution_status == ResolutionStatus.RESOLVED:
            return "positive"
        
        # If exception is escalated, it's negative feedback
        if resolution_status == ResolutionStatus.ESCALATED:
            return "negative"
        
        # Default based on event type
        if event.event_type == "PlaybookCompleted":
            # Check if playbook completed successfully
            payload = event.payload
            if payload.get("status") == "success":
                return "positive"
            return "negative"
        
        if event.event_type == "ToolExecutionCompleted":
            # Check if tool execution succeeded
            payload = event.payload
            if payload.get("status") == "success":
                return "positive"
            return "negative"
        
        # Default to neutral
        return "neutral"
    
    async def _emit_feedback_captured_event(
        self,
        tenant_id: str,
        exception_id: str,
        feedback_type: str,
        feedback_data: dict[str, Any],
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit FeedbackCaptured event.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            feedback_type: Type of feedback (positive, negative, neutral)
            feedback_data: Feedback data including metrics
            correlation_id: Optional correlation ID
        """
        # Create FeedbackCaptured event
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception_id
        
        feedback_captured_event = FeedbackCaptured.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            feedback_type=feedback_type,
            feedback_data=feedback_data,
            captured_by="FeedbackWorker",
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=feedback_captured_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted FeedbackCaptured event: exception_id={exception_id}, "
            f"feedback_type={feedback_type}"
        )

