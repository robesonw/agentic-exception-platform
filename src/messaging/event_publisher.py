"""
Event Publisher Service for Phase 9.

Publishes canonical events to message broker with at-least-once delivery guarantees.
Events are persisted to EventStore before publishing to ensure durability.

Phase 9 P9-27: Added per-tenant rate limiting and backpressure protection.
"""

import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.messaging.broker import Broker, BrokerPublishError
from src.messaging.event_store import EventStore, EventStoreError, InMemoryEventStore
from src.messaging.partitioning import get_partition_key
from src.operations.rate_limiter import get_rate_limiter

logger = logging.getLogger(__name__)


class EventPublisherError(Exception):
    """Base exception for event publisher errors."""
    pass


class EventPublishFailedError(EventPublisherError):
    """Raised when event publishing fails after retries."""
    pass


class EventPublisherService:
    """
    Event Publisher Service.
    
    Ensures events are persisted before publishing (at-least-once semantics).
    Handles event serialization, partition key generation, and retry logic.
    """

    def __init__(
        self,
        broker: Broker,
        event_store: Optional[EventStore] = None,
        max_retries: int = 3,
        enable_rate_limiting: bool = True,
    ):
        """
        Initialize event publisher service.
        
        Phase 9 P9-27: Added rate limiting support.
        
        Args:
            broker: Message broker instance (e.g., KafkaBroker)
            event_store: Optional event store instance. If None, uses InMemoryEventStore.
            max_retries: Maximum number of retry attempts for publish failures
            enable_rate_limiting: Enable per-tenant rate limiting (default: True)
        """
        self.broker = broker
        self.event_store = event_store or InMemoryEventStore()
        self.max_retries = max_retries
        # Disable rate limiting by default for MVP/testing
        # Can be enabled via environment variable RATE_LIMIT_ENABLED=true
        rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "false").lower() == "true"
        self.enable_rate_limiting = enable_rate_limiting and rate_limit_enabled
        self.rate_limiter = get_rate_limiter() if self.enable_rate_limiting else None

    async def publish_event(
        self,
        topic: str,
        event: dict[str, Any],
        partition_key: Optional[str] = None,
    ) -> str:
        """
        Publish a canonical event to a topic.
        
        This method ensures at-least-once delivery by:
        1. Storing the event in EventStore first
        2. Then publishing to the message broker
        3. Retrying on transient failures
        
        Args:
            topic: Topic name to publish to
            event: Canonical event dictionary with fields:
                   - event_id (optional, will be generated if missing)
                   - event_type (required)
                   - tenant_id (required)
                   - exception_id (optional)
                   - timestamp (optional, will be set to now if missing)
                   - correlation_id (optional)
                   - payload (required)
                   - metadata (optional)
                   - version (optional, defaults to 1)
            partition_key: Optional partition key. If None, will be generated from
                          tenant_id and exception_id if available.
                          
        Returns:
            Event ID (UUID string)
            
        Raises:
            EventPublishFailedError: If publishing fails after retries
            EventStoreError: If storing the event fails
        """
        # Validate and normalize event
        normalized_event = self._normalize_event(event)
        event_id = normalized_event["event_id"]
        
        # Phase 9 P9-23: Validate tenant_id before publishing
        tenant_id = normalized_event.get("tenant_id")
        if not tenant_id or not tenant_id.strip():
            raise ValueError(
                f"Event {event_id} missing required tenant_id. "
                "All events must include tenant_id for tenant isolation."
            )
        
        tenant_id = tenant_id.strip()
        
        # Phase 9 P9-27: Check rate limit before publishing
        if self.enable_rate_limiting and self.rate_limiter:
            is_allowed, wait_seconds = self.rate_limiter.check_rate_limit(tenant_id)
            if not is_allowed:
                # Rate limit exceeded - emit backpressure event and raise exception
                limit = self.rate_limiter.get_tenant_limit(tenant_id)
                await self._emit_backpressure_event(
                    tenant_id=tenant_id,
                    rate_limit_type="events_per_second",
                    current_rate=limit.events_per_second + 1,  # Estimate current rate
                    limit=limit.events_per_second,
                    wait_seconds=wait_seconds or 0.0,
                    exception_id=normalized_event.get("exception_id"),
                    correlation_id=normalized_event.get("correlation_id"),
                )
                raise EventPublishFailedError(
                    f"Rate limit exceeded for tenant {tenant_id}. "
                    f"Wait {wait_seconds:.2f}s before retry."
                )
        
        # Generate partition key if not provided
        if partition_key is None:
            partition_key = self._generate_partition_key(
                tenant_id,
                normalized_event.get("exception_id"),
            )
        
        # Step 1: Store event in EventStore FIRST (at-least-once guarantee)
        # For ExceptionIngested events, exception_id doesn't exist yet (created by IntakeWorker)
        # So we store with exception_id=None and it will be updated later
        exception_id_for_store = normalized_event.get("exception_id")
        if normalized_event["event_type"] == "ExceptionIngested":
            exception_id_for_store = None
        
        try:
            await self.event_store.store_event(
                event_id=normalized_event["event_id"],
                event_type=normalized_event["event_type"],
                tenant_id=normalized_event["tenant_id"],
                exception_id=exception_id_for_store,
                timestamp=normalized_event["timestamp"],
                correlation_id=normalized_event.get("correlation_id"),
                payload=normalized_event["payload"],
                metadata=normalized_event.get("metadata"),
                version=normalized_event.get("version", 1),
            )
            logger.debug(f"Event {event_id} stored in EventStore")
        except EventStoreError as e:
            logger.error(f"Failed to store event {event_id} in EventStore: {e}")
            raise EventPublishFailedError(f"Event store failed: {e}") from e
        
        # Step 2: Publish to broker (with retry logic)
        try:
            self._publish_with_retry(topic, partition_key, normalized_event)
            logger.info(
                f"Event {event_id} (type={normalized_event['event_type']}) "
                f"published to topic={topic}, partition_key={partition_key}"
            )
        except BrokerPublishError as e:
            logger.error(
                f"Failed to publish event {event_id} to broker after retries: {e}"
            )
            # Event is already stored, so we can retry publishing later
            raise EventPublishFailedError(
                f"Event {event_id} stored but publish failed: {e}"
            ) from e
        
        return event_id

    def _normalize_event(self, event: dict[str, Any]) -> dict[str, Any]:
        """
        Normalize and validate event structure.
        
        Args:
            event: Raw event dictionary
            
        Returns:
            Normalized event dictionary
        """
        # Generate event_id if missing
        if "event_id" not in event:
            event["event_id"] = str(uuid.uuid4())
        
        # Validate required fields
        if "event_type" not in event:
            raise ValueError("event_type is required")
        if "tenant_id" not in event:
            raise ValueError("tenant_id is required")
        if "payload" not in event:
            raise ValueError("payload is required")
        
        # Set timestamp if missing
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc)
        elif isinstance(event["timestamp"], str):
            # Parse ISO format string
            event["timestamp"] = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
        
        # Ensure timestamp is timezone-aware
        if event["timestamp"].tzinfo is None:
            event["timestamp"] = event["timestamp"].replace(tzinfo=timezone.utc)
        
        # Set default version if missing
        if "version" not in event:
            event["version"] = 1
        
        return event

    def _generate_partition_key(
        self,
        tenant_id: Optional[str],
        exception_id: Optional[str],
    ) -> Optional[str]:
        """
        Generate partition key from tenant_id and exception_id.
        
        Uses partitioning module for consistent key generation.
        Format: "{tenant_id}:{exception_id}" when both are available.
        Returns None if tenant_id is not available.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Partition key string or None
            
        Note:
            Ordering is guaranteed per (tenant_id, exception_id) only.
            Events for the same exception are processed in order.
            Events for different exceptions may be processed in parallel.
        """
        if not tenant_id:
            return None
        
        return get_partition_key(tenant_id, exception_id)

    def _publish_with_retry(
        self,
        topic: str,
        partition_key: Optional[str],
        event: dict[str, Any],
    ) -> None:
        """
        Publish event to broker with retry logic.
        
        Args:
            topic: Topic name
            partition_key: Partition key
            event: Normalized event dictionary
            
        Raises:
            BrokerPublishError: If publishing fails after retries
        """
        # Serialize event to JSON
        serialized_event = json.dumps(event, default=self._json_serializer)
        
        # Publish with retry (broker handles retries internally, but we can add
        # additional retry logic here if needed)
        try:
            self.broker.publish(topic, partition_key, serialized_event)
        except BrokerPublishError:
            # Re-raise broker errors as-is (they already include retry logic)
            raise

    def _json_serializer(self, obj: Any) -> str:
        """
        Custom JSON serializer for datetime and other types.
        
        Args:
            obj: Object to serialize
            
        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")
    
    async def _emit_backpressure_event(
        self,
        tenant_id: str,
        rate_limit_type: str,
        current_rate: float,
        limit: float,
        wait_seconds: float,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit BackpressureDetected event when rate limit is exceeded.
        
        Phase 9 P9-27: Emits backpressure events for monitoring.
        
        Args:
            tenant_id: Tenant identifier
            rate_limit_type: Type of rate limit
            current_rate: Current rate
            limit: Configured limit
            wait_seconds: Estimated wait time
            exception_id: Optional exception identifier
            correlation_id: Optional correlation ID
        """
        try:
            from src.events.types import BackpressureDetected
            
            backpressure_event = BackpressureDetected.create(
                tenant_id=tenant_id,
                rate_limit_type=rate_limit_type,
                current_rate=current_rate,
                limit=limit,
                wait_seconds=wait_seconds,
                exception_id=exception_id,
                correlation_id=correlation_id,
            )
            
            # Publish backpressure event (bypass rate limiting to avoid recursion)
            backpressure_dict = backpressure_event.model_dump()
            topic = "backpressure"  # Use dedicated topic for backpressure events
            
            # Store event first
            await self.event_store.store_event(
                event_id=backpressure_event.event_id,
                event_type=backpressure_event.event_type,
                tenant_id=tenant_id,
                exception_id=exception_id,
                timestamp=backpressure_event.timestamp,
                correlation_id=correlation_id,
                payload=backpressure_event.payload,
                metadata=backpressure_event.metadata,
                version=backpressure_event.version,
            )
            
            # Publish to broker (bypass rate limiting)
            partition_key = self._generate_partition_key(tenant_id, exception_id)
            serialized_event = json.dumps(backpressure_dict, default=self._json_serializer)
            self.broker.publish(topic, partition_key, serialized_event)
            
            logger.warning(
                f"Backpressure detected for tenant {tenant_id}: "
                f"rate_limit_type={rate_limit_type}, current_rate={current_rate}, "
                f"limit={limit}, wait_seconds={wait_seconds:.2f}"
            )
        except Exception as e:
            # Don't fail event publishing if backpressure event emission fails
            logger.error(
                f"Failed to emit backpressure event for tenant {tenant_id}: {e}",
                exc_info=True,
            )

