"""
Streaming ingestion mode for Phase 3.

Supports optional streaming ingestion via Kafka or MQ stubs.
Both batch (REST) and streaming modes are supported.

Matches specification from phase3-mvp-issues.md P3-17.
"""

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from typing import Protocol

from src.agents.intake import IntakeAgent
from src.models.exception_record import ExceptionRecord

logger = logging.getLogger(__name__)


@dataclass
class StreamingMessage:
    """
    Message schema for exception messages in streaming ingestion.
    
    Consistent with ExceptionRecord input format.
    """

    tenant_id: str
    source_system: str
    raw_payload: dict[str, Any]
    exception_type: Optional[str] = None
    severity: Optional[str] = None
    timestamp: Optional[str] = None
    normalized_context: Optional[dict[str, Any]] = None
    metadata: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "tenantId": self.tenant_id,
            "sourceSystem": self.source_system,
            "rawPayload": self.raw_payload,
            "exceptionType": self.exception_type,
            "severity": self.severity,
            "timestamp": self.timestamp or datetime.now(timezone.utc).isoformat(),
            "normalizedContext": self.normalized_context or {},
            "metadata": self.metadata or {},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StreamingMessage":
        """Create message from dictionary."""
        return cls(
            tenant_id=data.get("tenantId") or data.get("tenant_id", ""),
            source_system=data.get("sourceSystem") or data.get("source_system", ""),
            raw_payload=data.get("rawPayload") or data.get("raw_payload", {}),
            exception_type=data.get("exceptionType") or data.get("exception_type"),
            severity=data.get("severity"),
            timestamp=data.get("timestamp"),
            normalized_context=data.get("normalizedContext") or data.get("normalized_context"),
            metadata=data.get("metadata"),
        )


class StreamingIngestionBackend(Protocol):
    """
    Protocol for streaming ingestion backends.
    
    Implementations should provide:
    - start(): Start consuming messages
    - stop(): Stop consuming messages
    - Message callback mechanism
    """

    async def start(self) -> None:
        """Start the streaming backend."""
        ...

    async def stop(self) -> None:
        """Stop the streaming backend."""
        ...

    def set_message_handler(self, handler: Callable[[StreamingMessage], None]) -> None:
        """Set handler for incoming messages."""
        ...


class StubIngestionBackend:
    """
    Stub streaming backend for testing.
    
    Uses an in-memory queue to simulate message streaming.
    """

    def __init__(self):
        """Initialize stub backend."""
        self._message_queue: asyncio.Queue[StreamingMessage] = asyncio.Queue()
        self._message_handler: Optional[Callable[[StreamingMessage], None]] = None
        self._running = False
        self._consumer_task: Optional[asyncio.Task] = None
        self._backpressure_controller: Optional[Any] = None

    async def start(self) -> None:
        """Start consuming messages from queue."""
        if self._running:
            logger.warning("Stub backend already running")
            return
        
        self._running = True
        self._consumer_task = asyncio.create_task(self._consume_messages())
        logger.info("Stub ingestion backend started")

    async def stop(self) -> None:
        """Stop consuming messages."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("Stub ingestion backend stopped")

    def set_message_handler(self, handler: Callable[[StreamingMessage], None]) -> None:
        """Set handler for incoming messages."""
        self._message_handler = handler

    async def _consume_messages(self) -> None:
        """Consume messages from queue and call handler."""
        while self._running:
            try:
                # Phase 3: Check backpressure before consuming
                if self._backpressure_controller and not self._backpressure_controller.should_consume():
                    # Pause consumption
                    await asyncio.sleep(0.5)
                    continue
                
                # Wait for message with timeout to allow checking _running flag
                message = await asyncio.wait_for(self._message_queue.get(), timeout=1.0)
                
                if self._message_handler:
                    # Call handler (may be async or sync)
                    if asyncio.iscoroutinefunction(self._message_handler):
                        await self._message_handler(message)
                    else:
                        self._message_handler(message)
                
                self._message_queue.task_done()
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error consuming message: {e}")
    
    def set_backpressure_controller(self, controller: Any) -> None:
        """
        Set backpressure controller for rate limiting.
        
        Args:
            controller: BackpressureController instance
        """
        self._backpressure_controller = controller
    
    def get_backpressure_controller(self) -> Optional[Any]:
        """Get backpressure controller."""
        return self._backpressure_controller

    async def push_message(self, message: StreamingMessage) -> None:
        """
        Push a message into the queue (for testing).
        
        Args:
            message: Message to push
        """
        await self._message_queue.put(message)
        logger.debug(f"Pushed message to stub backend queue: {message.tenant_id}")


class KafkaIngestionBackend:
    """
    Kafka streaming backend (stub implementation).
    
    Phase 3 MVP: Placeholder interface. Full implementation would use aiokafka.
    """

    def __init__(
        self,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
        **kwargs: Any,
    ):
        """
        Initialize Kafka backend.
        
        Args:
            bootstrap_servers: Kafka bootstrap servers (comma-separated)
            topic: Kafka topic to consume from
            group_id: Consumer group ID
            **kwargs: Additional Kafka consumer configuration
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self.kwargs = kwargs
        self._message_handler: Optional[Callable[[StreamingMessage], None]] = None
        self._running = False
        self._backpressure_controller: Optional[Any] = None
        logger.info(
            f"Kafka backend initialized: servers={bootstrap_servers}, "
            f"topic={topic}, group_id={group_id}"
        )

    async def start(self) -> None:
        """
        Start Kafka consumer.
        
        Phase 3 MVP: Stub implementation that logs but doesn't actually connect.
        Full implementation would:
        1. Create aiokafka.AIOKafkaConsumer
        2. Start consuming from topic
        3. Parse messages and call handler
        """
        if self._running:
            logger.warning("Kafka backend already running")
            return
        
        self._running = True
        logger.info(f"Kafka backend started (stub) - would connect to {self.bootstrap_servers}")
        # TODO: Phase 3+ - Implement actual Kafka consumer
        # from aiokafka import AIOKafkaConsumer
        # self.consumer = AIOKafkaConsumer(
        #     self.topic,
        #     bootstrap_servers=self.bootstrap_servers,
        #     group_id=self.group_id,
        #     **self.kwargs
        # )
        # await self.consumer.start()
        # asyncio.create_task(self._consume_kafka_messages())

    async def stop(self) -> None:
        """Stop Kafka consumer."""
        self._running = False
        logger.info("Kafka backend stopped (stub)")
        # TODO: Phase 3+ - Implement actual Kafka consumer stop
        # if hasattr(self, 'consumer'):
        #     await self.consumer.stop()

    def set_message_handler(self, handler: Callable[[StreamingMessage], None]) -> None:
        """Set handler for incoming messages."""
        self._message_handler = handler

    # TODO: Phase 3+ - Implement actual Kafka message consumption
    # async def _consume_kafka_messages(self) -> None:
    #     """Consume messages from Kafka and call handler."""
    #     async for msg in self.consumer:
    #         try:
    #             message_data = json.loads(msg.value.decode('utf-8'))
    #             message = StreamingMessage.from_dict(message_data)
    #             if self._message_handler:
    #                 if asyncio.iscoroutinefunction(self._message_handler):
    #                     await self._message_handler(message)
    #                 else:
    #                     self._message_handler(message)
    #         except Exception as e:
    #             logger.error(f"Error processing Kafka message: {e}")


class StreamingIngestionService:
    """
    Service for streaming ingestion.
    
    Handles message normalization and routing to orchestrator.
    """

    def __init__(
        self,
        backend: StreamingIngestionBackend,
        intake_agent: Optional[IntakeAgent] = None,
        orchestrator_callback: Optional[Callable[[dict[str, Any]], None]] = None,
        backpressure_controller: Optional[Any] = None,
    ):
        """
        Initialize streaming ingestion service.
        
        Args:
            backend: Streaming ingestion backend (Kafka, stub, etc.)
            intake_agent: Optional IntakeAgent for normalization
            orchestrator_callback: Optional callback to pass normalized exceptions to orchestrator
            backpressure_controller: Optional backpressure controller for rate limiting
        """
        self.backend = backend
        self.intake_agent = intake_agent
        self.orchestrator_callback = orchestrator_callback
        self.backpressure_controller = backpressure_controller
        self._processing_queue: Optional[asyncio.Queue[dict[str, Any]]] = None
        self._processor_task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self) -> None:
        """Start streaming ingestion service."""
        if self._running:
            logger.warning("Streaming ingestion service already running")
            return
        
        # Set message handler
        self.backend.set_message_handler(self._handle_message)
        
        # Create processing queue if orchestrator callback is not provided
        if not self.orchestrator_callback:
            self._processing_queue = asyncio.Queue()
            self._processor_task = asyncio.create_task(self._process_queue())
        
        # Start backend
        await self.backend.start()
        
        self._running = True
        logger.info("Streaming ingestion service started")

    async def stop(self) -> None:
        """Stop streaming ingestion service."""
        self._running = False
        
        # Stop backend
        await self.backend.stop()
        
        # Stop processor task
        if self._processor_task:
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Streaming ingestion service stopped")

    async def _handle_message(self, message: StreamingMessage) -> None:
        """
        Handle incoming streaming message.
        
        Args:
            message: Streaming message
        """
        try:
            # Phase 3: Check backpressure before processing
            if self.backpressure_controller:
                # Check rate limit per tenant
                if not self.backpressure_controller.check_rate_limit(message.tenant_id):
                    logger.warning(
                        f"Rate limit exceeded for tenant {message.tenant_id}, "
                        f"dropping message"
                    )
                    return
                
                # Check if should drop low-priority messages
                if self.backpressure_controller.should_drop_low_priority():
                    # In MVP, we don't have priority in StreamingMessage, so skip for now
                    # Future: check message.priority and drop if low
                    pass
                
                # Apply adaptive delay if needed
                delay = self.backpressure_controller.get_adaptive_delay()
                if delay > 0:
                    await asyncio.sleep(delay)
            
            # Convert message to raw exception format
            raw_exception = message.to_dict()
            
            # Normalize via IntakeAgent if available
            if self.intake_agent:
                try:
                    normalized, decision = await self.intake_agent.process(
                        raw_exception=raw_exception,
                        tenant_id=message.tenant_id,
                    )
                    # Use normalized exception
                    exception_dict = normalized.model_dump()
                except Exception as e:
                    logger.error(f"Failed to normalize exception: {e}")
                    # Fallback: use raw exception
                    exception_dict = raw_exception
            else:
                # No intake agent - use raw exception
                exception_dict = raw_exception
            
            # Pass to orchestrator callback or queue
            if self.orchestrator_callback:
                # Direct callback
                if asyncio.iscoroutinefunction(self.orchestrator_callback):
                    await self.orchestrator_callback(exception_dict)
                else:
                    self.orchestrator_callback(exception_dict)
            elif self._processing_queue:
                # Queue for processing
                # Phase 3: Update queue depth before enqueueing
                if self.backpressure_controller:
                    queue_depth = self._processing_queue.qsize()
                    self.backpressure_controller.update_queue_depth(queue_depth + 1)
                
                await self._processing_queue.put(exception_dict)
            
            logger.debug(f"Processed streaming message for tenant {message.tenant_id}")
            
        except Exception as e:
            logger.error(f"Error handling streaming message: {e}")

    async def _process_queue(self) -> None:
        """Process queued exceptions (if no orchestrator callback provided)."""
        while self._running:
            try:
                # Phase 3: Check backpressure before consuming
                if self.backpressure_controller and not self.backpressure_controller.should_consume():
                    # Pause consumption
                    await asyncio.sleep(0.5)
                    continue
                
                exception_dict = await asyncio.wait_for(self._processing_queue.get(), timeout=1.0)
                
                # Phase 3: Update queue depth after dequeueing
                if self.backpressure_controller:
                    queue_depth = self._processing_queue.qsize()
                    self.backpressure_controller.update_queue_depth(queue_depth)
                
                # In MVP, just log that we received it
                # In production, would pass to orchestrator
                logger.info(f"Received exception from streaming queue: {exception_dict.get('exceptionId', 'unknown')}")
                self._processing_queue.task_done()
            except asyncio.TimeoutError:
                # Update queue depth on timeout
                if self.backpressure_controller and self._processing_queue:
                    queue_depth = self._processing_queue.qsize()
                    self.backpressure_controller.update_queue_depth(queue_depth)
                continue
            except Exception as e:
                logger.error(f"Error processing queued exception: {e}")

    def get_processing_queue(self) -> Optional[asyncio.Queue[dict[str, Any]]]:
        """
        Get the processing queue (for testing/monitoring).
        
        Returns:
            Processing queue or None if using direct callback
        """
        return self._processing_queue


def create_streaming_backend(
    backend_type: str,
    **config: Any,
) -> StreamingIngestionBackend:
    """
    Factory function to create streaming backend.
    
    Args:
        backend_type: Backend type ("kafka" or "stub")
        **config: Backend-specific configuration
        
    Returns:
        StreamingIngestionBackend instance
        
    Raises:
        ValueError: If backend_type is invalid
    """
    if backend_type.lower() == "kafka":
        return KafkaIngestionBackend(**config)
    elif backend_type.lower() == "stub":
        return StubIngestionBackend()
    else:
        raise ValueError(f"Unknown streaming backend type: {backend_type}")


def load_streaming_config() -> dict[str, Any]:
    """
    Load streaming configuration from environment or config file.
    
    Returns:
        Configuration dictionary with:
        {
            "enabled": bool,
            "backend": str,
            "kafka": {
                "bootstrap_servers": str,
                "topic": str,
                "group_id": str,
                ...
            }
        }
    """
    import os
    
    config = {
        "enabled": os.getenv("STREAMING_ENABLED", "false").lower() == "true",
        "backend": os.getenv("STREAMING_BACKEND", "stub"),
        "kafka": {
            "bootstrap_servers": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"),
            "topic": os.getenv("KAFKA_TOPIC", "exceptions"),
            "group_id": os.getenv("KAFKA_GROUP_ID", "exception-processor"),
        },
    }
    
    return config

