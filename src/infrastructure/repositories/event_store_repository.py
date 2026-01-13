"""
Event Store Repository for Phase 9.

Provides database-backed event storage with tenant isolation and querying capabilities.
Reference: docs/phase9-async-scale-mvp.md Section 7.1
"""

import json
import logging
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import EventLog
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


def _serialize_datetime(obj: Any) -> Any:
    """
    Recursively serialize datetime objects to ISO format strings.
    
    Args:
        obj: Object that may contain datetime objects
        
    Returns:
        Object with datetime objects converted to ISO strings
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: _serialize_datetime(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [_serialize_datetime(item) for item in obj]
    else:
        return obj


class EventFilter:
    """Filter criteria for event queries."""
    
    def __init__(
        self,
        event_type: Optional[str] = None,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_timestamp: Optional[datetime] = None,
        end_timestamp: Optional[datetime] = None,
        version: Optional[int] = None,
    ):
        """
        Initialize event filter.
        
        Args:
            event_type: Filter by event type
            exception_id: Filter by exception ID
            correlation_id: Filter by correlation ID
            start_timestamp: Filter events after this timestamp
            end_timestamp: Filter events before this timestamp
            version: Filter by event version
        """
        self.event_type = event_type
        self.exception_id = exception_id
        self.correlation_id = correlation_id
        self.start_timestamp = start_timestamp
        self.end_timestamp = end_timestamp
        self.version = version


class EventStoreRepository(AbstractBaseRepository[EventLog]):
    """
    Repository for event log management.
    
    Provides:
    - Store events (append-only)
    - Get events by exception ID
    - Get events by tenant ID
    - Query with filtering and pagination
    
    All operations enforce tenant isolation.
    """

    async def store_event(
        self,
        event_id: str,
        event_type: str,
        tenant_id: str,
        exception_id: Optional[str],
        timestamp: datetime,
        correlation_id: Optional[str],
        payload: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
        version: int = 1,
    ) -> EventLog:
        """
        Store an event in the event log (append-only).
        
        Args:
            event_id: Unique event identifier (UUID string)
            event_type: Type of event
            tenant_id: Tenant identifier
            exception_id: Optional exception identifier
            timestamp: Event timestamp
            correlation_id: Optional correlation ID
            payload: Event payload (dict)
            metadata: Optional metadata (dict)
            version: Event schema version (default: 1)
            
        Returns:
            Created EventLog instance
            
        Raises:
            ValueError: If required fields are missing
        """
        if not event_id or not event_id.strip():
            raise ValueError("event_id is required")
        if not event_type or not event_type.strip():
            raise ValueError("event_type is required")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        # Serialize datetime objects in payload and metadata to ISO strings
        # This is required because JSONB columns can't store datetime objects directly
        serialized_payload = _serialize_datetime(payload) if payload else {}
        serialized_metadata = _serialize_datetime(metadata) if metadata else {}
        
        # Create new event log entry
        event_log = EventLog(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            exception_id=exception_id,
            timestamp=timestamp,
            correlation_id=correlation_id,
            payload=serialized_payload,
            event_metadata=serialized_metadata,
            version=version,
        )
        
        self.session.add(event_log)
        await self.session.flush()
        await self.session.refresh(event_log)
        
        logger.debug(
            f"Stored event: event_id={event_id}, event_type={event_type}, "
            f"tenant_id={tenant_id}, exception_id={exception_id}"
        )
        return event_log

    async def get_event(self, event_id: str, tenant_id: str) -> Optional[EventLog]:
        """
        Get an event by ID with tenant isolation.
        
        Args:
            event_id: Event identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            EventLog instance or None if not found or access denied
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(EventLog)
            .where(EventLog.event_id == event_id)
            .where(EventLog.tenant_id == tenant_id)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_events_by_exception(
        self,
        exception_id: str,
        tenant_id: str,
        filters: Optional[EventFilter] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[EventLog]:
        """
        Get events for a specific exception with filtering and pagination.
        
        Phase 9 P9-21: Trace query helper - returns all events for an exception.
        This can be used to trace the full event flow for an exception.
        
        Args:
            exception_id: Exception identifier (also used as correlation_id for tracing)
            tenant_id: Tenant identifier (required for isolation)
            filters: Optional EventFilter for filtering events
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with events and pagination metadata
            
        Raises:
            ValueError: If tenant_id is empty or pagination parameters invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if not exception_id or not exception_id.strip():
            raise ValueError("exception_id is required")
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        # Phase 9 P9-21: Query by both exception_id and correlation_id for complete trace
        # Since correlation_id = exception_id, we can query by either
        # This ensures we get all events in the trace even if exception_id is missing in some events
        query = (
            select(EventLog)
            .where(
                (EventLog.exception_id == exception_id) | (EventLog.correlation_id == exception_id)
            )
            .where(EventLog.tenant_id == tenant_id)
        )
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            if filters.event_type is not None:
                conditions.append(EventLog.event_type == filters.event_type)
            
            # Don't apply correlation_id filter when querying by exception_id
            # The base query already handles correlation_id via OR condition
            # Adding AND correlation_id would exclude events with mismatched correlation_id
            # even when exception_id matches (which is the primary identifier)
            # if filters.correlation_id is not None:
            #     conditions.append(EventLog.correlation_id == filters.correlation_id)
            
            if filters.start_timestamp is not None:
                conditions.append(EventLog.timestamp >= filters.start_timestamp)
            
            if filters.end_timestamp is not None:
                conditions.append(EventLog.timestamp <= filters.end_timestamp)
            
            if filters.version is not None:
                conditions.append(EventLog.version == filters.version)
            
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by timestamp descending (newest first)
        query = query.order_by(desc(EventLog.timestamp))
        
        # Execute paginated query
        return await self._execute_paginated(query, page=page, page_size=page_size)

    async def get_events_by_tenant(
        self,
        tenant_id: str,
        filters: Optional[EventFilter] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[EventLog]:
        """
        Get events for a specific tenant with filtering and pagination.
        
        Args:
            tenant_id: Tenant identifier (required)
            filters: Optional EventFilter for filtering events
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with events and pagination metadata
            
        Raises:
            ValueError: If tenant_id is empty or pagination parameters invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        # Start with base query - filter by tenant_id
        query = select(EventLog).where(EventLog.tenant_id == tenant_id)
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            if filters.event_type is not None:
                conditions.append(EventLog.event_type == filters.event_type)
            
            if filters.correlation_id is not None:
                conditions.append(EventLog.correlation_id == filters.correlation_id)
            
            if filters.exception_id is not None:
                conditions.append(EventLog.exception_id == filters.exception_id)
            
            if filters.start_timestamp is not None:
                conditions.append(EventLog.timestamp >= filters.start_timestamp)
            
            if filters.end_timestamp is not None:
                conditions.append(EventLog.timestamp <= filters.end_timestamp)
            
            if filters.version is not None:
                conditions.append(EventLog.version == filters.version)
            
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by timestamp descending (newest first)
        query = query.order_by(desc(EventLog.timestamp))
        
        # Execute paginated query
        return await self._execute_paginated(query, page=page, page_size=page_size)

    # AbstractBaseRepository implementations

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[EventLog]:
        """
        Get event by ID with tenant context.
        
        Args:
            id: Event ID (event_id string)
            tenant_id: Tenant identifier (required by interface)
            
        Returns:
            EventLog instance or None if not found or access denied
        """
        return await self.get_event(id, tenant_id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[EventLog]:
        """
        List events for a tenant with pagination and filtering.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (converted to EventFilter)
            
        Returns:
            PaginatedResult with events
        """
        # Convert filters to EventFilter if provided
        event_filter = None
        if filters:
            event_filter = EventFilter(**filters)
        
        return await self.get_events_by_tenant(
            tenant_id=tenant_id, filters=event_filter, page=page, page_size=page_size
        )

