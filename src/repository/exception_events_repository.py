"""
Exception event repository with append-only log.

Phase 6 P6-5: Idempotent event insertion for safe replay.
Phase 6 P6-8: Full append-only event log operations.

This repository enforces append-only semantics: no updates or deletes are allowed.
All events are immutable once written. This design supports:
- Safe event replay
- Audit trail integrity
- Future Kafka migration (Phase 9)
"""

import logging
from datetime import datetime
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import ActorType, ExceptionEvent
from src.repository.base import AbstractBaseRepository, PaginatedResult
from src.repository.dto import EventFilter, ExceptionEventCreateDTO, ExceptionEventDTO

logger = logging.getLogger(__name__)


class ExceptionEventRepository(AbstractBaseRepository[ExceptionEvent]):
    """
    Repository for exception event operations with append-only log.
    
    This repository enforces append-only semantics:
    - No update() or delete() methods are provided
    - Events are immutable once written
    - All operations respect tenant isolation
    
    Provides:
    - Idempotent event insertion (P6-5)
    - Append-only event log operations (P6-8)
    - Event retrieval for timeline views
    - Tenant-scoped event queries
    
    This repository is heavily used by:
    - Agents (for logging decisions and actions)
    - UI (for displaying event timelines)
    - Co-Pilot (for contextual event history)
    """

    async def event_exists(self, tenant_id: str, event_id: UUID) -> bool:
        """
        Check if an event already exists for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            event_id: Event identifier (UUID)
            
        Returns:
            True if event exists, False otherwise
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(ExceptionEvent).where(ExceptionEvent.event_id == event_id)
        query = self._tenant_filter(query, tenant_id, ExceptionEvent.tenant_id)
        
        result = await self.session.execute(query)
        event = result.scalar_one_or_none()
        
        return event is not None

    async def append_event_if_new(self, event: ExceptionEventDTO) -> bool:
        """
        Append event only if it doesn't already exist (idempotent).
        
        If event_exists(...) is True, do nothing and return False.
        If not, insert the new event row and return True.
        
        This method is idempotent: multiple calls with the same event_id
        will not create duplicates. Safe for replay scenarios.
        
        Args:
            event: Exception event data
            
        Returns:
            True if event was inserted, False if it already existed
        """
        # Check if event already exists
        exists = await self.event_exists(event.tenant_id, event.event_id)
        
        if exists:
            logger.debug(
                f"Event {event.event_id} already exists for tenant {event.tenant_id}, "
                "skipping insertion"
            )
            return False
        
        # Insert new event
        logger.debug(
            f"Inserting new event {event.event_id} for exception {event.exception_id} "
            f"and tenant {event.tenant_id}"
        )
        
        new_event = ExceptionEvent(
            event_id=event.event_id,
            exception_id=event.exception_id,
            tenant_id=event.tenant_id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            payload=event.payload,
        )
        
        self.session.add(new_event)
        await self.session.flush()
        
        return True

    async def get_by_id(self, id: str, tenant_id: str) -> ExceptionEvent | None:
        """
        Get event by ID with tenant isolation.
        
        Args:
            id: Event identifier (UUID as string)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            ExceptionEvent instance or None if not found
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            event_id = UUID(id)
        except (ValueError, TypeError):
            return None
        
        query = select(ExceptionEvent).where(ExceptionEvent.event_id == event_id)
        query = self._tenant_filter(query, tenant_id, ExceptionEvent.tenant_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[ExceptionEvent]:
        """
        List events for a tenant with pagination.
        
        This method is kept for backward compatibility. For new code, use
        get_events_for_tenant or get_events_for_exception.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (legacy format)
            
        Returns:
            PaginatedResult with events and pagination metadata
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(ExceptionEvent)
        query = self._tenant_filter(query, tenant_id, ExceptionEvent.tenant_id)
        
        # Apply legacy filters
        if "exception_id" in filters:
            query = query.where(ExceptionEvent.exception_id == filters["exception_id"])
        if "event_type" in filters:
            query = query.where(ExceptionEvent.event_type == filters["event_type"])
        if "created_from" in filters or "created_to" in filters:
            if "created_from" in filters:
                query = query.where(ExceptionEvent.created_at >= filters["created_from"])
            if "created_to" in filters:
                query = query.where(ExceptionEvent.created_at <= filters["created_to"])
        
        # Order by created_at descending (newest first)
        query = query.order_by(ExceptionEvent.created_at.desc())
        
        return await self._execute_paginated(query, page, page_size)

    # ============================================================================
    # Append-Only Event Log Operations (P6-8)
    # ============================================================================

    async def append_event(
        self,
        tenant_id: str,
        event: ExceptionEventCreateDTO,
    ) -> ExceptionEvent:
        """
        Append a new event to the append-only log.
        
        This method enforces append-only semantics: events are immutable once written.
        No updates or deletes are allowed. The event_id provided by the caller (UUID)
        is used as the primary key.
        
        Args:
            tenant_id: Tenant identifier (must match event.tenant_id)
            event: Event data to append
            
        Returns:
            Created ExceptionEvent instance
            
        Raises:
            ValueError: If tenant_id doesn't match event.tenant_id
            ValueError: If event with same event_id already exists
        """
        if tenant_id != event.tenant_id:
            raise ValueError(
                f"tenant_id parameter ({tenant_id}) must match "
                f"event.tenant_id ({event.tenant_id})"
            )
        
        # Check if event already exists (idempotency check)
        exists = await self.event_exists(tenant_id, event.event_id)
        if exists:
            raise ValueError(
                f"Event {event.event_id} already exists for tenant {tenant_id}. "
                "Use append_event_if_new for idempotent insertion."
            )
        
        logger.debug(
            f"Appending new event {event.event_id} for exception {event.exception_id} "
            f"and tenant {tenant_id}"
        )
        
        new_event = ExceptionEvent(
            event_id=event.event_id,
            exception_id=event.exception_id,
            tenant_id=event.tenant_id,
            event_type=event.event_type,
            actor_type=event.actor_type,
            actor_id=event.actor_id,
            payload=event.payload,
        )
        
        self.session.add(new_event)
        await self.session.flush()
        await self.session.refresh(new_event)
        
        return new_event

    async def get_events_for_exception(
        self,
        tenant_id: str,
        exception_id: str,
        filters: Optional[EventFilter] = None,
    ) -> list[ExceptionEvent]:
        """
        Get events for a specific exception (event timeline).
        
        This method is used by UI to display exception timelines and by agents
        to retrieve event history. All events are returned in chronological order
        (created_at ASC) by default.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            exception_id: Exception identifier
            filters: Optional filter criteria (event_types, actor_type, date range)
            
        Returns:
            List of ExceptionEvent instances, ordered by created_at ASC (oldest first)
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(ExceptionEvent)
        query = self._tenant_filter(query, tenant_id, ExceptionEvent.tenant_id)
        query = query.where(ExceptionEvent.exception_id == exception_id)
        
        # Apply filters if provided
        if filters:
            if filters.event_types:
                query = query.where(ExceptionEvent.event_type.in_(filters.event_types))
            if filters.actor_type is not None:
                query = query.where(ExceptionEvent.actor_type == filters.actor_type)
            if filters.created_from is not None:
                query = query.where(ExceptionEvent.created_at >= filters.created_from)
            if filters.created_to is not None:
                query = query.where(ExceptionEvent.created_at <= filters.created_to)
        
        # Order by created_at ASC (chronological order, oldest first)
        query = query.order_by(ExceptionEvent.created_at.asc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_events_for_tenant(
        self,
        tenant_id: str,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> list[ExceptionEvent]:
        """
        Get events across all exceptions for a tenant.
        
        This method is used for tenant-wide event queries and audit trails.
        Events are returned in reverse chronological order (created_at DESC, newest first).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            date_from: Optional start date filter (created_at >= date_from)
            date_to: Optional end date filter (created_at <= date_to)
            
        Returns:
            List of ExceptionEvent instances, ordered by created_at DESC (newest first)
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(ExceptionEvent)
        query = self._tenant_filter(query, tenant_id, ExceptionEvent.tenant_id)
        
        # Apply date range filters if provided
        if date_from is not None:
            query = query.where(ExceptionEvent.created_at >= date_from)
        if date_to is not None:
            query = query.where(ExceptionEvent.created_at <= date_to)
        
        # Order by created_at DESC (newest first)
        query = query.order_by(ExceptionEvent.created_at.desc())
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

