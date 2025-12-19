"""
Dead Letter Queue Repository for Phase 9 and Phase 10.

Provides CRUD operations for dead letter events with tenant isolation.

Phase 9: Basic DLQ storage and listing.
Phase 10 P10-4: Enhanced with retry, discard, batch operations, and stats.

Reference: docs/phase9-async-scale-mvp.md Section 7.2
Reference: docs/phase10-ops-governance-mvp.md Section 5.3
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DeadLetterEvent, DLQStatus
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


@dataclass
class DLQStats:
    """DLQ statistics summary."""
    tenant_id: str
    total: int
    pending: int
    retrying: int
    discarded: int
    succeeded: int
    by_event_type: dict[str, int]
    by_worker_type: dict[str, int]


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

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[DeadLetterEvent]:
        """
        Get a DLQ entry by ID with tenant isolation.

        Required by AbstractBaseRepository.
        Delegates to get_dlq_entry for event_id based lookup.

        Args:
            id: Event identifier (event_id)
            tenant_id: Tenant identifier (required for isolation)

        Returns:
            DeadLetterEvent instance or None if not found
        """
        return await self.get_dlq_entry(id, tenant_id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[DeadLetterEvent]:
        """
        List DLQ entries for a tenant with pagination.

        Required by AbstractBaseRepository.

        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed)
            page_size: Number of items per page
            **filters: Additional filter criteria (event_type, worker_type, etc.)

        Returns:
            PaginatedResult with DLQ entries
        """
        offset = (page - 1) * page_size
        return await self.list_dlq_entries(
            tenant_id=tenant_id,
            event_type=filters.get("event_type"),
            worker_type=filters.get("worker_type"),
            exception_id=filters.get("exception_id"),
            limit=page_size,
            offset=offset,
        )

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

    # =========================================================================
    # Phase 10 P10-4: DLQ Management Methods
    # =========================================================================

    async def get_dlq_entry_by_id(
        self, dlq_id: int, tenant_id: str
    ) -> Optional[DeadLetterEvent]:
        """
        Get a DLQ entry by primary key ID with tenant isolation.

        Args:
            dlq_id: DLQ entry primary key
            tenant_id: Tenant identifier (required for isolation)

        Returns:
            DeadLetterEvent instance or None if not found
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(DeadLetterEvent)
            .where(DeadLetterEvent.id == dlq_id)
            .where(DeadLetterEvent.tenant_id == tenant_id)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_status(
        self,
        dlq_id: int,
        tenant_id: str,
        new_status: str,
        actor: Optional[str] = None,
    ) -> Optional[DeadLetterEvent]:
        """
        Update the status of a DLQ entry.

        Args:
            dlq_id: DLQ entry primary key
            tenant_id: Tenant identifier
            new_status: New status value
            actor: Optional actor who made the change

        Returns:
            Updated DeadLetterEvent or None if not found
        """
        entry = await self.get_dlq_entry_by_id(dlq_id, tenant_id)
        if not entry:
            return None

        now = datetime.now(timezone.utc)
        entry.status = new_status

        if new_status == DLQStatus.RETRYING.value:
            entry.retried_at = now
            entry.retry_count += 1
        elif new_status == DLQStatus.DISCARDED.value:
            entry.discarded_at = now
            entry.discarded_by = actor

        await self.session.flush()
        await self.session.refresh(entry)

        logger.info(
            f"Updated DLQ entry status: id={dlq_id}, tenant_id={tenant_id}, "
            f"new_status={new_status}"
        )
        return entry

    async def mark_retrying(
        self, dlq_id: int, tenant_id: str
    ) -> Optional[DeadLetterEvent]:
        """Mark a DLQ entry as retrying."""
        return await self.update_status(dlq_id, tenant_id, DLQStatus.RETRYING.value)

    async def mark_succeeded(
        self, dlq_id: int, tenant_id: str
    ) -> Optional[DeadLetterEvent]:
        """Mark a DLQ entry as succeeded (retry was successful)."""
        return await self.update_status(dlq_id, tenant_id, DLQStatus.SUCCEEDED.value)

    async def mark_discarded(
        self, dlq_id: int, tenant_id: str, actor: Optional[str] = None
    ) -> Optional[DeadLetterEvent]:
        """Mark a DLQ entry as discarded."""
        return await self.update_status(
            dlq_id, tenant_id, DLQStatus.DISCARDED.value, actor
        )

    async def batch_update_status(
        self,
        dlq_ids: list[int],
        tenant_id: str,
        new_status: str,
        actor: Optional[str] = None,
    ) -> int:
        """
        Update status for multiple DLQ entries at once.

        Args:
            dlq_ids: List of DLQ entry primary keys
            tenant_id: Tenant identifier
            new_status: New status value
            actor: Optional actor who made the change

        Returns:
            Number of rows updated
        """
        if not dlq_ids:
            return 0

        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        now = datetime.now(timezone.utc)

        values = {"status": new_status, "updated_at": now}

        if new_status == DLQStatus.RETRYING.value:
            values["retried_at"] = now
        elif new_status == DLQStatus.DISCARDED.value:
            values["discarded_at"] = now
            values["discarded_by"] = actor

        stmt = (
            update(DeadLetterEvent)
            .where(DeadLetterEvent.id.in_(dlq_ids))
            .where(DeadLetterEvent.tenant_id == tenant_id)
            .values(**values)
        )

        result = await self.session.execute(stmt)
        await self.session.flush()

        logger.info(
            f"Batch updated DLQ entries: count={result.rowcount}, "
            f"tenant_id={tenant_id}, new_status={new_status}"
        )
        return result.rowcount

    async def get_stats(self, tenant_id: str) -> DLQStats:
        """
        Get DLQ statistics for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            DLQStats with counts and breakdowns
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        # Get status counts
        status_query = (
            select(
                DeadLetterEvent.status,
                func.count(DeadLetterEvent.id).label("count")
            )
            .where(DeadLetterEvent.tenant_id == tenant_id)
            .group_by(DeadLetterEvent.status)
        )

        result = await self.session.execute(status_query)
        status_counts = {row[0]: row[1] for row in result.fetchall()}

        # Get event type counts
        type_query = (
            select(
                DeadLetterEvent.event_type,
                func.count(DeadLetterEvent.id).label("count")
            )
            .where(DeadLetterEvent.tenant_id == tenant_id)
            .group_by(DeadLetterEvent.event_type)
        )

        result = await self.session.execute(type_query)
        type_counts = {row[0]: row[1] for row in result.fetchall()}

        # Get worker type counts
        worker_query = (
            select(
                DeadLetterEvent.worker_type,
                func.count(DeadLetterEvent.id).label("count")
            )
            .where(DeadLetterEvent.tenant_id == tenant_id)
            .group_by(DeadLetterEvent.worker_type)
        )

        result = await self.session.execute(worker_query)
        worker_counts = {row[0]: row[1] for row in result.fetchall()}

        total = sum(status_counts.values())

        return DLQStats(
            tenant_id=tenant_id,
            total=total,
            pending=status_counts.get(DLQStatus.PENDING.value, 0),
            retrying=status_counts.get(DLQStatus.RETRYING.value, 0),
            discarded=status_counts.get(DLQStatus.DISCARDED.value, 0),
            succeeded=status_counts.get(DLQStatus.SUCCEEDED.value, 0),
            by_event_type=type_counts,
            by_worker_type=worker_counts,
        )

    async def list_dlq_entries_with_status(
        self,
        tenant_id: str,
        status_filter: Optional[str] = None,
        event_type: Optional[str] = None,
        worker_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResult[DeadLetterEvent]:
        """
        List DLQ entries with status filtering.

        Args:
            tenant_id: Tenant identifier (required for isolation)
            status_filter: Optional filter by status
            event_type: Optional filter by event type
            worker_type: Optional filter by worker type
            limit: Maximum number of results
            offset: Number of results to skip

        Returns:
            PaginatedResult with DLQ entries
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(DeadLetterEvent).where(DeadLetterEvent.tenant_id == tenant_id)

        if status_filter:
            query = query.where(DeadLetterEvent.status == status_filter)
        if event_type:
            query = query.where(DeadLetterEvent.event_type == event_type)
        if worker_type:
            query = query.where(DeadLetterEvent.worker_type == worker_type)

        query = query.order_by(desc(DeadLetterEvent.failed_at))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        query = query.limit(limit).offset(offset)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return PaginatedResult(
            items=items,
            total=total,
            limit=limit,
            offset=offset,
        )

