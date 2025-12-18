"""
Dead Letter Queue Repository for Phase 9.

Provides CRUD operations for dead letter events with tenant isolation.
Reference: docs/phase9-async-scale-mvp.md Section 7.2
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DeadLetterEvent
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


class DeadLetterEventRepository(AbstractBaseRepository[DeadLetterEvent]):
    """
    Repository for dead letter event management.
    
    Provides:
    - Create DLQ entry
    - Get DLQ entry by event_id (with tenant isolation)
    - List DLQ entries with filtering (with tenant isolation)
    - Query DLQ entries by various criteria
    
    All operations enforce tenant isolation.
    """

    async def create_dlq_entry(
        self,
        event_id: str,
        event_type: str,
        tenant_id: str,
        original_topic: str,
        failure_reason: str,
        retry_count: int,
        worker_type: str,
        payload: dict,
        exception_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> DeadLetterEvent:
        """
        Create a new dead letter event entry.
        
        Args:
            event_id: Original event identifier
            event_type: Type of the original event
            tenant_id: Tenant identifier
            original_topic: Original topic where event was published
            failure_reason: Reason for failure
            retry_count: Number of retry attempts made
            worker_type: Worker type that failed
            payload: Original event payload
            exception_id: Optional exception identifier
            metadata: Optional event metadata
            
        Returns:
            Created DeadLetterEvent instance
            
        Raises:
            ValueError: If required fields are invalid
        """
        if not event_id or not tenant_id:
            raise ValueError("event_id and tenant_id are required")
        
        # Create new DLQ entry
        dlq_entry = DeadLetterEvent(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            exception_id=exception_id,
            original_topic=original_topic,
            failure_reason=failure_reason,
            retry_count=retry_count,
            worker_type=worker_type,
            payload=payload,
            event_metadata=metadata or {},
            failed_at=datetime.now(timezone.utc),
        )
        
        self.session.add(dlq_entry)
        await self.session.flush()
        await self.session.refresh(dlq_entry)
        
        logger.info(
            f"Created DLQ entry: event_id={event_id}, tenant_id={tenant_id}, "
            f"retry_count={retry_count}, worker_type={worker_type}"
        )
        return dlq_entry

    async def get_dlq_entry(
        self, event_id: str, tenant_id: str
    ) -> Optional[DeadLetterEvent]:
        """
        Get a DLQ entry by event_id with tenant isolation.
        
        Args:
            event_id: Event identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            DeadLetterEvent instance or None if not found or access denied
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(DeadLetterEvent)
            .where(DeadLetterEvent.event_id == event_id)
            .where(DeadLetterEvent.tenant_id == tenant_id)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_dlq_entries(
        self,
        tenant_id: str,
        event_type: Optional[str] = None,
        worker_type: Optional[str] = None,
        exception_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
        order_by: str = "failed_at",
        order_desc: bool = True,
    ) -> PaginatedResult[DeadLetterEvent]:
        """
        List DLQ entries with filtering and pagination.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            event_type: Optional filter by event type
            worker_type: Optional filter by worker type
            exception_id: Optional filter by exception identifier
            limit: Maximum number of results
            offset: Number of results to skip
            order_by: Field to order by (default: "failed_at")
            order_desc: If True, order descending (default: True)
            
        Returns:
            PaginatedResult with DLQ entries
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Build query with tenant isolation
        query = select(DeadLetterEvent).where(DeadLetterEvent.tenant_id == tenant_id)
        
        # Apply filters
        if event_type:
            query = query.where(DeadLetterEvent.event_type == event_type)
        if worker_type:
            query = query.where(DeadLetterEvent.worker_type == worker_type)
        if exception_id:
            query = query.where(DeadLetterEvent.exception_id == exception_id)
        
        # Apply ordering
        order_column = getattr(DeadLetterEvent, order_by, DeadLetterEvent.failed_at)
        if order_desc:
            query = query.order_by(desc(order_column))
        else:
            query = query.order_by(order_column)
        
        # Get total count
        count_query = select(func.count()).select_from(
            query.subquery()
        )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        query = query.limit(limit).offset(offset)
        
        # Execute query
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        
        return PaginatedResult(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_dlq_entries_by_exception(
        self,
        exception_id: str,
        tenant_id: str,
        limit: int = 100,
    ) -> list[DeadLetterEvent]:
        """
        Get all DLQ entries for a specific exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier (required for isolation)
            limit: Maximum number of results
            
        Returns:
            List of DeadLetterEvent instances
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(DeadLetterEvent)
            .where(DeadLetterEvent.exception_id == exception_id)
            .where(DeadLetterEvent.tenant_id == tenant_id)
            .order_by(desc(DeadLetterEvent.failed_at))
            .limit(limit)
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

