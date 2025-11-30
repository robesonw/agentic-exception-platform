"""
Incremental Decision Streaming for Phase 3.

Streams stage-by-stage updates as each agent completes processing.
Exposes updates via pub/sub registry for SSE/WebSocket streaming.

Matches specification from phase3-mvp-issues.md P3-18.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from src.models.agent_contracts import AgentDecision

logger = logging.getLogger(__name__)


@dataclass
class StageCompletedEvent:
    """
    Event emitted when a stage completes processing.
    
    Includes:
    - exception_id: Exception identifier
    - tenant_id: Tenant identifier
    - stage_name: Name of the completed stage (intake, triage, policy, resolution, feedback)
    - timestamp: When the stage completed
    - decision_summary: Summary of the agent decision
    - decision: Full agent decision (optional, may be large)
    """

    exception_id: str
    tenant_id: str
    stage_name: str
    timestamp: str
    decision_summary: dict[str, Any]
    decision: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)

    @classmethod
    def from_decision(
        cls,
        exception_id: str,
        tenant_id: str,
        stage_name: str,
        decision: AgentDecision,
    ) -> "StageCompletedEvent":
        """
        Create event from agent decision.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            stage_name: Stage name
            decision: Agent decision
            
        Returns:
            StageCompletedEvent instance
        """
        # Extract summary from decision
        decision_dict = decision.model_dump() if hasattr(decision, "model_dump") else decision
        
        decision_summary = {
            "decision": decision_dict.get("decision", ""),
            "confidence": decision_dict.get("confidence", 0.0),
            "evidence_count": len(decision_dict.get("evidence", [])),
        }
        
        return cls(
            exception_id=exception_id,
            tenant_id=tenant_id,
            stage_name=stage_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            decision_summary=decision_summary,
            decision=decision_dict,  # Include full decision for detailed views
        )


class EventBus:
    """
    Simple event bus for orchestrator events.
    
    Phase 3 MVP: In-memory pub/sub registry keyed by tenant_id and exception_id.
    """

    def __init__(self):
        """Initialize event bus."""
        # Key: (tenant_id, exception_id) -> list of subscribers (async queues)
        self._subscribers: dict[tuple[str, str], list[asyncio.Queue[StageCompletedEvent]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(
        self,
        tenant_id: str,
        exception_id: Optional[str] = None,
    ) -> asyncio.Queue[StageCompletedEvent]:
        """
        Subscribe to events for a tenant and optionally a specific exception.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Optional exception identifier (None = all exceptions for tenant)
            
        Returns:
            Async queue that will receive events
        """
        # Use "*" as wildcard for exception_id if not provided
        key = (tenant_id, exception_id or "*")
        
        async with self._lock:
            if key not in self._subscribers:
                self._subscribers[key] = []
            
            queue: asyncio.Queue[StageCompletedEvent] = asyncio.Queue()
            self._subscribers[key].append(queue)
            
            logger.debug(f"Subscribed to events: tenant={tenant_id}, exception={exception_id or 'all'}")
            return queue

    async def unsubscribe(
        self,
        tenant_id: str,
        exception_id: Optional[str],
        queue: asyncio.Queue[StageCompletedEvent],
    ) -> None:
        """
        Unsubscribe from events.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Optional exception identifier
            queue: Queue to remove from subscribers
        """
        key = (tenant_id, exception_id or "*")
        
        async with self._lock:
            if key in self._subscribers:
                try:
                    self._subscribers[key].remove(queue)
                    if not self._subscribers[key]:
                        del self._subscribers[key]
                except ValueError:
                    pass  # Queue not in list
        
        logger.debug(f"Unsubscribed from events: tenant={tenant_id}, exception={exception_id or 'all'}")

    async def publish(self, event: StageCompletedEvent) -> None:
        """
        Publish a stage completion event.
        
        Args:
            event: Stage completion event
        """
        async with self._lock:
            # Publish to specific exception subscribers
            specific_key = (event.tenant_id, event.exception_id)
            if specific_key in self._subscribers:
                for queue in self._subscribers[specific_key]:
                    try:
                        await queue.put(event)
                    except Exception as e:
                        logger.warning(f"Failed to publish to subscriber: {e}")
            
            # Publish to wildcard subscribers (all exceptions for tenant)
            wildcard_key = (event.tenant_id, "*")
            if wildcard_key in self._subscribers:
                for queue in self._subscribers[wildcard_key]:
                    try:
                        await queue.put(event)
                    except Exception as e:
                        logger.warning(f"Failed to publish to wildcard subscriber: {e}")
        
        logger.debug(
            f"Published event: tenant={event.tenant_id}, "
            f"exception={event.exception_id}, stage={event.stage_name}"
        )


# Global event bus instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """
    Get the global event bus instance.
    
    Returns:
        EventBus instance
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


class DecisionStreamService:
    """
    Service for streaming decision updates.
    
    Subscribes to orchestrator events and provides streaming interface.
    """

    def __init__(self, event_bus: Optional[EventBus] = None):
        """
        Initialize decision stream service.
        
        Args:
            event_bus: Optional event bus instance (uses global if not provided)
        """
        self.event_bus = event_bus or get_event_bus()

    async def subscribe_to_exception(
        self,
        tenant_id: str,
        exception_id: str,
    ) -> asyncio.Queue[StageCompletedEvent]:
        """
        Subscribe to events for a specific exception.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Async queue that will receive events
        """
        return await self.event_bus.subscribe(tenant_id, exception_id)

    async def subscribe_to_tenant(
        self,
        tenant_id: str,
    ) -> asyncio.Queue[StageCompletedEvent]:
        """
        Subscribe to events for all exceptions in a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Async queue that will receive events
        """
        return await self.event_bus.subscribe(tenant_id, None)

    async def unsubscribe(
        self,
        tenant_id: str,
        exception_id: Optional[str],
        queue: asyncio.Queue[StageCompletedEvent],
    ) -> None:
        """
        Unsubscribe from events.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Optional exception identifier
            queue: Queue to unsubscribe
        """
        await self.event_bus.unsubscribe(tenant_id, exception_id, queue)


# Global decision stream service instance
_decision_stream_service: Optional[DecisionStreamService] = None


def get_decision_stream_service() -> DecisionStreamService:
    """
    Get the global decision stream service instance.
    
    Returns:
        DecisionStreamService instance
    """
    global _decision_stream_service
    if _decision_stream_service is None:
        _decision_stream_service = DecisionStreamService()
    return _decision_stream_service


def emit_stage_completed(
    exception_id: str,
    tenant_id: str,
    stage_name: str,
    decision: AgentDecision,
    event_bus: Optional[EventBus] = None,
) -> None:
    """
    Emit a stage completed event.
    
    This function should be called by the orchestrator when a stage completes.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        stage_name: Stage name
        decision: Agent decision
        event_bus: Optional event bus instance (uses global if not provided)
    """
    bus = event_bus or get_event_bus()
    
    # Create event
    event = StageCompletedEvent.from_decision(
        exception_id=exception_id,
        tenant_id=tenant_id,
        stage_name=stage_name,
        decision=decision,
    )
    
    # Publish asynchronously (fire and forget)
    asyncio.create_task(bus.publish(event))

