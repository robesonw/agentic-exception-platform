"""
Event Processing Repository for Phase 9.

Provides idempotency tracking for event processing by workers.
Reference: docs/phase9-async-scale-mvp.md Section 6.1
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import EventProcessing, EventProcessingStatus

logger = logging.getLogger(__name__)


class EventProcessingRepository:
    """
    Repository for event processing idempotency tracking.
    
    Provides:
    - Check if event has been processed
    - Mark event as processing
    - Mark event as completed
    - Mark event as failed
    - Query processing status
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize event processing repository.
        
        Args:
            session: Async database session
        """
        self.session = session

    async def is_processed(
        self, event_id: str, worker_type: str
    ) -> bool:
        """
        Check if event has already been processed by worker.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type (e.g., "IntakeWorker", "TriageWorker")
            
        Returns:
            True if event is already processed (completed), False otherwise
        """
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
            .where(EventProcessing.status == EventProcessingStatus.COMPLETED)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def is_processing(
        self, event_id: str, worker_type: str
    ) -> bool:
        """
        Check if event is currently being processed.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            
        Returns:
            True if event is currently processing, False otherwise
        """
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
            .where(EventProcessing.status == EventProcessingStatus.PROCESSING)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def get_processing_status(
        self, event_id: str, worker_type: str
    ) -> Optional[EventProcessingStatus]:
        """
        Get current processing status for event.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            
        Returns:
            EventProcessingStatus or None if not found
        """
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
        )
        
        result = await self.session.execute(query)
        processing = result.scalar_one_or_none()
        return processing.status if processing else None

    async def mark_processing(
        self,
        event_id: str,
        worker_type: str,
        tenant_id: str,
        exception_id: Optional[str] = None,
    ) -> EventProcessing:
        """
        Mark event as being processed.
        
        If a record already exists, updates it to PROCESSING status.
        Otherwise, creates a new record.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            tenant_id: Tenant identifier
            exception_id: Optional exception identifier
            
        Returns:
            EventProcessing instance
        """
        # Check if record exists
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
        )
        
        result = await self.session.execute(query)
        processing = result.scalar_one_or_none()
        
        if processing:
            # Update existing record
            processing.status = EventProcessingStatus.PROCESSING
            processing.processed_at = datetime.now(timezone.utc)
            processing.error_message = None
            if exception_id:
                processing.exception_id = exception_id
        else:
            # Create new record
            processing = EventProcessing(
                event_id=event_id,
                worker_type=worker_type,
                tenant_id=tenant_id,
                exception_id=exception_id,
                status=EventProcessingStatus.PROCESSING,
            )
            self.session.add(processing)
        
        await self.session.flush()
        await self.session.refresh(processing)
        
        logger.debug(
            f"Marked event {event_id} as processing by {worker_type}"
        )
        return processing

    async def mark_completed(
        self,
        event_id: str,
        worker_type: str,
    ) -> Optional[EventProcessing]:
        """
        Mark event as completed.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            
        Returns:
            EventProcessing instance or None if not found
        """
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
        )
        
        result = await self.session.execute(query)
        processing = result.scalar_one_or_none()
        
        if processing:
            processing.status = EventProcessingStatus.COMPLETED
            processing.processed_at = datetime.now(timezone.utc)
            processing.error_message = None
            
            await self.session.flush()
            await self.session.refresh(processing)
            
            logger.debug(
                f"Marked event {event_id} as completed by {worker_type}"
            )
            return processing
        else:
            logger.warning(
                f"Attempted to mark event {event_id} as completed by {worker_type}, "
                f"but no processing record found"
            )
            return None

    async def mark_failed(
        self,
        event_id: str,
        worker_type: str,
        error_message: Optional[str] = None,
    ) -> Optional[EventProcessing]:
        """
        Mark event processing as failed.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            error_message: Optional error message
            
        Returns:
            EventProcessing instance or None if not found
        """
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
        )
        
        result = await self.session.execute(query)
        processing = result.scalar_one_or_none()
        
        if processing:
            processing.status = EventProcessingStatus.FAILED
            processing.processed_at = datetime.now(timezone.utc)
            processing.error_message = error_message
            
            await self.session.flush()
            await self.session.refresh(processing)
            
            logger.debug(
                f"Marked event {event_id} as failed by {worker_type}: {error_message}"
            )
            return processing
        else:
            logger.warning(
                f"Attempted to mark event {event_id} as failed by {worker_type}, "
                f"but no processing record found"
            )
            return None

    async def get_processing_record(
        self, event_id: str, worker_type: str
    ) -> Optional[EventProcessing]:
        """
        Get processing record for event and worker.
        
        Args:
            event_id: Event identifier
            worker_type: Worker type
            
        Returns:
            EventProcessing instance or None if not found
        """
        query = (
            select(EventProcessing)
            .where(EventProcessing.event_id == event_id)
            .where(EventProcessing.worker_type == worker_type)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

