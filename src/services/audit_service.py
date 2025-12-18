"""
Audit Service for Phase 9.

Provides audit trail querying using EventStoreRepository as source of truth.

Phase 9 P9-25: Enhance Audit Trail with Event Store Integration.
Reference: docs/phase9-async-scale-mvp.md Section 11
"""

import logging
from datetime import datetime
from typing import Optional

from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.event_store_repository import (
    EventFilter,
    EventStoreRepository,
)
from src.repository.base import PaginatedResult

logger = logging.getLogger(__name__)


class AuditServiceError(Exception):
    """Raised when audit service operations fail."""

    pass


class AuditService:
    """
    Service for querying audit trails from event store.
    
    Phase 9 P9-25: Uses EventStoreRepository as source of truth for audit.
    All events are immutable and append-only, ensuring audit trail integrity.
    """
    
    async def get_audit_trail_for_exception(
        self,
        exception_id: str,
        tenant_id: str,
        event_type: Optional[str] = None,
        start_timestamp: Optional[datetime] = None,
        end_timestamp: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[dict]:
        """
        Get audit trail for a specific exception.
        
        Phase 9 P9-25: Queries EventStoreRepository for all events related to an exception.
        Events are immutable and append-only, ensuring audit trail integrity.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier (required for isolation)
            event_type: Optional filter by event type
            start_timestamp: Optional filter events after this timestamp
            end_timestamp: Optional filter events before this timestamp
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with audit events (as dictionaries)
            
        Raises:
            AuditServiceError: If query fails
            ValueError: If parameters are invalid
        """
        if not exception_id or not exception_id.strip():
            raise ValueError("exception_id is required")
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        try:
            async with get_db_session_context() as session:
                event_repo = EventStoreRepository(session)
                
                # Build filter
                event_filter = EventFilter(
                    event_type=event_type,
                    exception_id=exception_id,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                )
                
                # Query events
                result = await event_repo.get_events_by_exception(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    filters=event_filter,
                    page=page,
                    page_size=page_size,
                )
                
                # Convert EventLog objects to dictionaries for API response
                audit_events = [
                    self._event_log_to_audit_entry(event_log)
                    for event_log in result.items
                ]
                
                return PaginatedResult(
                    items=audit_events,
                    total=result.total,
                    page=result.page,
                    page_size=result.page_size,
                    total_pages=result.total_pages,
                )
        except Exception as e:
            logger.error(
                f"Failed to get audit trail for exception {exception_id}: {e}",
                exc_info=True,
            )
            raise AuditServiceError(f"Failed to query audit trail: {e}") from e
    
    async def get_audit_trail_for_tenant(
        self,
        tenant_id: str,
        event_type: Optional[str] = None,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        start_timestamp: Optional[datetime] = None,
        end_timestamp: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[dict]:
        """
        Get audit trail for a tenant with pagination.
        
        Phase 9 P9-25: Queries EventStoreRepository for all events for a tenant.
        Supports filtering and pagination for large result sets.
        
        Args:
            tenant_id: Tenant identifier (required)
            event_type: Optional filter by event type
            exception_id: Optional filter by exception ID
            correlation_id: Optional filter by correlation ID
            start_timestamp: Optional filter events after this timestamp
            end_timestamp: Optional filter events before this timestamp
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with audit events (as dictionaries)
            
        Raises:
            AuditServiceError: If query fails
            ValueError: If parameters are invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        try:
            async with get_db_session_context() as session:
                event_repo = EventStoreRepository(session)
                
                # Build filter
                event_filter = EventFilter(
                    event_type=event_type,
                    exception_id=exception_id,
                    correlation_id=correlation_id,
                    start_timestamp=start_timestamp,
                    end_timestamp=end_timestamp,
                )
                
                # Query events
                result = await event_repo.get_events_by_tenant(
                    tenant_id=tenant_id,
                    filters=event_filter,
                    page=page,
                    page_size=page_size,
                )
                
                # Convert EventLog objects to dictionaries for API response
                audit_events = [
                    self._event_log_to_audit_entry(event_log)
                    for event_log in result.items
                ]
                
                return PaginatedResult(
                    items=audit_events,
                    total=result.total,
                    page=result.page,
                    page_size=result.page_size,
                    total_pages=result.total_pages,
                )
        except Exception as e:
            logger.error(
                f"Failed to get audit trail for tenant {tenant_id}: {e}",
                exc_info=True,
            )
            raise AuditServiceError(f"Failed to query audit trail: {e}") from e
    
    def _event_log_to_audit_entry(self, event_log) -> dict:
        """
        Convert EventLog to audit entry dictionary.
        
        Phase 9 P9-25: Converts database EventLog to API-friendly format.
        
        Args:
            event_log: EventLog instance from database
            
        Returns:
            Dictionary representation of audit entry
        """
        return {
            "event_id": event_log.event_id,
            "event_type": event_log.event_type,
            "tenant_id": event_log.tenant_id,
            "exception_id": event_log.exception_id,
            "correlation_id": event_log.correlation_id,
            "timestamp": event_log.timestamp.isoformat() if event_log.timestamp else None,
            "payload": event_log.payload,
            "metadata": event_log.metadata or {},
            "version": event_log.version,
        }


def get_audit_service() -> AuditService:
    """
    Get the global audit service instance.
    
    Returns:
        AuditService instance
    """
    return AuditService()


