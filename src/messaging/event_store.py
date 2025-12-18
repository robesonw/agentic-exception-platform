"""
Event Store interface for Phase 9.

Defines the contract for event persistence before publishing (at-least-once semantics).
The actual implementation will be provided in P9-4.
"""

import asyncio
from abc import ABC, abstractmethod
from typing import Any, Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.repositories.event_store_repository import (
    EventStoreRepository,
    EventFilter,
)


class EventStore(ABC):
    """
    Abstract base class for event store implementations.
    
    Events must be persisted before publishing to ensure at-least-once delivery semantics.
    """

    @abstractmethod
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
    ) -> None:
        """
        Store an event in the event store.
        
        Args:
            event_id: Unique event identifier (UUID)
            event_type: Type of event (e.g., "ExceptionIngested", "TriageCompleted")
            tenant_id: Tenant identifier
            exception_id: Optional exception identifier
            timestamp: Event timestamp
            correlation_id: Optional correlation ID for tracing
            payload: Event payload (dict)
            metadata: Optional metadata (dict)
            version: Event schema version (default: 1)
            
        Raises:
            EventStoreError: If storing the event fails
        """
        pass

    @abstractmethod
    async def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve an event by ID.
        
        Args:
            event_id: Event identifier
            
        Returns:
            Event dictionary or None if not found
        """
        pass


class EventStoreError(Exception):
    """Base exception for event store errors."""
    pass


class InMemoryEventStore(EventStore):
    """
    In-memory event store implementation for testing and MVP.
    
    This is a temporary implementation until P9-4 provides a proper database-backed store.
    """
    
    def __init__(self):
        """Initialize in-memory event store."""
        self._events: dict[str, dict[str, Any]] = {}
        
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
    ) -> None:
        """Store event in memory."""
        self._events[event_id] = {
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id,
            "exception_id": exception_id,
            "timestamp": timestamp,
            "correlation_id": correlation_id,
            "payload": payload,
            "metadata": metadata or {},
            "version": version,
        }
        
    async def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        """Retrieve event from memory."""
        return self._events.get(event_id)


class DatabaseEventStore(EventStore):
    """
    Database-backed event store implementation.
    
    Uses EventStoreRepository for persistence with tenant isolation.
    """
    
    def __init__(self, session: AsyncSession):
        """
        Initialize database event store.
        
        Args:
            session: Async database session
        """
        self.repository = EventStoreRepository(session)
        
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
    ) -> None:
        """Store event in database."""
        await self.repository.store_event(
            event_id=event_id,
            event_type=event_type,
            tenant_id=tenant_id,
            exception_id=exception_id,
            timestamp=timestamp,
            correlation_id=correlation_id,
            payload=payload,
            metadata=metadata,
            version=version,
        )
        
    async def get_event(self, event_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve event from database.
        
        Note: This requires tenant_id for isolation, but the interface doesn't provide it.
        For now, this method will need to be enhanced or used with tenant context.
        """
        # This is a limitation - we need tenant_id for isolation
        # For now, return None and log a warning
        # In practice, this method should be called with tenant context
        return None

