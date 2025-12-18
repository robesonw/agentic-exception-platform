"""
Trace Service for Phase 9.

Provides trace querying capabilities for distributed tracing.
Phase 9 P9-21: Trace query helper for "all events for exception".

Reference: docs/phase9-async-scale-mvp.md Section 10.2
"""

import logging
from typing import Any, Optional

from src.infrastructure.repositories.event_store_repository import (
    EventStoreRepository,
    EventFilter,
)
from src.repository.base import PaginatedResult
from src.infrastructure.db.models import EventLog

logger = logging.getLogger(__name__)


class TraceService:
    """
    Service for querying event traces.
    
    Provides:
    - Get all events for an exception (trace)
    - Query events by correlation_id
    - Visualize event flow across workers
    """
    
    def __init__(self, event_store_repository: EventStoreRepository):
        """
        Initialize trace service.
        
        Args:
            event_store_repository: EventStoreRepository for querying events
        """
        self.event_store_repository = event_store_repository
    
    async def get_trace_for_exception(
        self,
        exception_id: str,
        tenant_id: str,
        event_type: Optional[str] = None,
        start_timestamp: Optional[Any] = None,
        end_timestamp: Optional[Any] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[EventLog]:
        """
        Get all events for an exception (trace).
        
        Phase 9 P9-21: Trace query helper that returns all events related to an exception.
        Since correlation_id = exception_id, this returns the complete event flow trace.
        
        Args:
            exception_id: Exception identifier (used as correlation_id for tracing)
            tenant_id: Tenant identifier
            event_type: Optional filter by event type
            start_timestamp: Optional start timestamp filter
            end_timestamp: Optional end timestamp filter
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 100, larger for traces)
            
        Returns:
            PaginatedResult with events ordered by timestamp (oldest first for trace flow)
            
        Raises:
            ValueError: If tenant_id or exception_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not exception_id or not exception_id.strip():
            raise ValueError("exception_id is required")
        
        # Build filter
        filters = EventFilter(
            event_type=event_type,
            correlation_id=exception_id,  # Query by correlation_id (which equals exception_id)
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        
        # Get events by exception (this queries both exception_id and correlation_id)
        result = await self.event_store_repository.get_events_by_exception(
            exception_id=exception_id,
            tenant_id=tenant_id,
            filters=filters,
            page=page,
            page_size=page_size,
        )
        
        logger.info(
            f"Retrieved trace for exception {exception_id}: {result.total} events "
            f"(page {page}/{result.total_pages})"
        )
        
        return result
    
    async def get_trace_by_correlation_id(
        self,
        correlation_id: str,
        tenant_id: str,
        event_type: Optional[str] = None,
        start_timestamp: Optional[Any] = None,
        end_timestamp: Optional[Any] = None,
        page: int = 1,
        page_size: int = 100,
    ) -> PaginatedResult[EventLog]:
        """
        Get all events for a correlation ID (trace).
        
        Phase 9 P9-21: Query events by correlation_id for distributed tracing.
        
        Args:
            correlation_id: Correlation ID (typically equals exception_id)
            tenant_id: Tenant identifier
            event_type: Optional filter by event type
            start_timestamp: Optional start timestamp filter
            end_timestamp: Optional end timestamp filter
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 100)
            
        Returns:
            PaginatedResult with events ordered by timestamp
            
        Raises:
            ValueError: If tenant_id or correlation_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not correlation_id or not correlation_id.strip():
            raise ValueError("correlation_id is required")
        
        # Build filter
        filters = EventFilter(
            event_type=event_type,
            correlation_id=correlation_id,
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
        )
        
        # Get events by tenant with correlation_id filter
        result = await self.event_store_repository.get_events_by_tenant(
            tenant_id=tenant_id,
            filters=filters,
            page=page,
            page_size=page_size,
        )
        
        logger.info(
            f"Retrieved trace for correlation_id {correlation_id}: {result.total} events "
            f"(page {page}/{result.total_pages})"
        )
        
        return result
    
    async def get_trace_summary(
        self,
        exception_id: str,
        tenant_id: str,
    ) -> dict[str, Any]:
        """
        Get trace summary for an exception.
        
        Returns a summary of the event trace including:
        - Total event count
        - Event types and counts
        - First and last event timestamps
        - Worker types involved
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with trace summary
        """
        # Get all events (no pagination for summary)
        result = await self.get_trace_for_exception(
            exception_id=exception_id,
            tenant_id=tenant_id,
            page=1,
            page_size=1000,  # Large page size to get all events for summary
        )
        
        # Build summary
        event_types: dict[str, int] = {}
        worker_types: set[str] = set()
        timestamps: list[Any] = []
        
        for event in result.items:
            # Count event types
            event_types[event.event_type] = event_types.get(event.event_type, 0) + 1
            
            # Extract worker type from metadata if available
            if event.metadata and isinstance(event.metadata, dict):
                worker_type = event.metadata.get("worker_type")
                if worker_type:
                    worker_types.add(worker_type)
            
            # Collect timestamps
            if event.timestamp:
                timestamps.append(event.timestamp)
        
        return {
            "exception_id": exception_id,
            "tenant_id": tenant_id,
            "total_events": result.total,
            "event_types": event_types,
            "worker_types": sorted(list(worker_types)),
            "first_event_timestamp": min(timestamps) if timestamps else None,
            "last_event_timestamp": max(timestamps) if timestamps else None,
            "duration_seconds": (
                (max(timestamps) - min(timestamps)).total_seconds()
                if timestamps and len(timestamps) > 1
                else None
            ),
        }


