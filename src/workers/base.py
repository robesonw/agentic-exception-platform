"""
Agent Worker Base Framework for Phase 9.

Provides base class for event-driven agent workers that subscribe to message broker
topics and process canonical events asynchronously.
"""

import asyncio
import json
import logging
import os
import signal
import threading
import time
from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Callable, Optional

from src.events.schema import CanonicalEvent
from src.events.types import DeadLettered
from src.messaging.broker import Broker, BrokerSubscribeError
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.observability.prometheus_metrics import (
    get_metrics,
    record_event_processed,
    record_event_failure,
)

logger = logging.getLogger(__name__)

# Supported schema version (currently version 1)
# Events with version > SUPPORTED_SCHEMA_VERSION will be rejected unless ALLOW_FUTURE_SCHEMA=true
SUPPORTED_SCHEMA_VERSION = 1


class WorkerError(Exception):
    """Base exception for worker errors."""
    pass


class SchemaVersionError(WorkerError):
    """Raised when event schema version is incompatible."""
    pass


class WorkerHealth:
    """Worker health status."""
    
    def __init__(
        self,
        status: str,
        is_running: bool,
        messages_processed: int = 0,
        errors_count: int = 0,
        last_error: Optional[str] = None,
    ):
        """
        Initialize worker health.
        
        Args:
            status: Health status ("healthy", "unhealthy", "degraded")
            is_running: Whether worker is currently running
            messages_processed: Number of messages processed
            errors_count: Number of errors encountered
            last_error: Last error message (if any)
        """
        self.status = status
        self.is_running = is_running
        self.messages_processed = messages_processed
        self.errors_count = errors_count
        self.last_error = last_error


class AgentWorker(ABC):
    """
    Base class for agent workers.
    
    Workers subscribe to message broker topics, deserialize events, check idempotency,
    and process events via the abstract process_event method.
    
    Workers are stateless and can scale horizontally.
    """

    def __init__(
        self,
        broker: Broker,
        topics: list[str],
        group_id: str,
        worker_name: Optional[str] = None,
        event_processing_repo: Optional[EventProcessingRepository] = None,
        concurrency: int = 1,
    ):
        """
        Initialize agent worker.
        
        Phase 9 P9-26: Added concurrency parameter for parallel event processing.
        
        Args:
            broker: Message broker instance
            topics: List of topic names to subscribe to
            group_id: Consumer group ID (for load balancing)
            worker_name: Optional worker name (defaults to class name)
            event_processing_repo: Optional EventProcessingRepository for idempotency tracking
            concurrency: Number of parallel event processors (default: 1)
        """
        self.broker = broker
        self.topics = topics
        self.group_id = group_id
        self.worker_name = worker_name or self.__class__.__name__
        self.event_processing_repo = event_processing_repo
        self.concurrency = max(1, concurrency)  # Ensure concurrency >= 1
        
        # Worker state
        self._running = False
        self._shutdown_event = threading.Event()
        self._consumer_thread: Optional[threading.Thread] = None
        self._thread_event_loop: Optional[asyncio.AbstractEventLoop] = None  # Persistent event loop for this worker thread
        
        # Phase 9 P9-26: Thread pool for concurrent event processing
        self._executor: Optional[ThreadPoolExecutor] = None
        self._active_futures: set[Future] = set()
        self._futures_lock = threading.Lock()
        
        # Statistics
        self._messages_processed = 0
        self._errors_count = 0
        self._last_error: Optional[str] = None
        
        # Legacy idempotency hooks (for backward compatibility, deprecated)
        self._idempotency_check: Optional[Callable[[str], bool]] = None
        self._mark_processing: Optional[Callable[[str], None]] = None
        self._mark_completed: Optional[Callable[[str], None]] = None
        
        # Phase 9 P9-23: Tenant isolation
        # If worker is tenant-scoped, store expected tenant_id
        self._expected_tenant_id: Optional[str] = None
        
        logger.info(
            f"Initialized {self.worker_name} worker: topics={topics}, group_id={group_id}, "
            f"concurrency={self.concurrency}"
        )

    @abstractmethod
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process a canonical event.
        
        This is the main method that subclasses must implement to handle event processing.
        
        Args:
            event: CanonicalEvent instance to process
            
        Raises:
            Exception: If event processing fails (will be caught and logged)
        """
        pass

    def set_idempotency_hooks(
        self,
        check: Optional[Callable[[str], bool]] = None,
        mark_processing: Optional[Callable[[str], None]] = None,
        mark_completed: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Set idempotency checking hooks (stub for P9-12).
        
        Args:
            check: Function to check if event_id has already been processed
            mark_processing: Function to mark event as being processed
            mark_completed: Function to mark event as completed
        """
        self._idempotency_check = check
        self._mark_processing = mark_processing
        self._mark_completed = mark_completed

    def _deserialize_event(self, value: bytes) -> CanonicalEvent:
        """
        Deserialize and validate event from message broker.
        
        Phase 9: Validates schema version compatibility.
        Rejects unknown event versions unless ALLOW_FUTURE_SCHEMA=true.
        
        Args:
            value: Raw message bytes from broker
            
        Returns:
            CanonicalEvent instance
            
        Raises:
            WorkerError: If deserialization or validation fails
            SchemaVersionError: If event schema version is incompatible
        """
        try:
            # Parse JSON
            event_dict = json.loads(value.decode("utf-8"))
            
            # Validate and create CanonicalEvent
            event = CanonicalEvent(**event_dict)
            
            # Validate schema version
            self._validate_schema_version(event)
            
            return event
        except SchemaVersionError:
            # Re-raise schema version errors (will be handled by caller)
            raise
        except json.JSONDecodeError as e:
            raise WorkerError(f"Failed to parse event JSON: {e}") from e
        except Exception as e:
            raise WorkerError(f"Failed to validate event: {e}") from e
    
    def _validate_schema_version(self, event: CanonicalEvent) -> None:
        """
        Validate event schema version compatibility.
        
        Phase 9: Rejects events with version > SUPPORTED_SCHEMA_VERSION unless
        ALLOW_FUTURE_SCHEMA=true. Emits DeadLettered event for incompatible schemas.
        
        Args:
            event: CanonicalEvent to validate
            
        Raises:
            SchemaVersionError: If schema version is incompatible
        """
        event_version = event.version or 1  # Default to version 1 if not specified
        
        # Check if version is supported
        if event_version > SUPPORTED_SCHEMA_VERSION:
            # Check if future schemas are allowed
            allow_future_schema = os.getenv("ALLOW_FUTURE_SCHEMA", "false").lower() == "true"
            
            if not allow_future_schema:
                # Schema version is incompatible - emit DeadLettered event
                logger.warning(
                    f"{self.worker_name} rejecting event with incompatible schema version: "
                    f"event_id={event.event_id}, event_type={event.event_type}, "
                    f"version={event_version}, supported_version={SUPPORTED_SCHEMA_VERSION}"
                )
                
                # Emit DeadLettered event synchronously (broker.publish is sync)
                try:
                    self._emit_schema_incompatible_dead_letter(event, event_version)
                except Exception as e:
                    logger.error(
                        f"{self.worker_name} failed to emit DeadLettered event: {e}",
                        exc_info=True,
                    )
                
                raise SchemaVersionError(
                    f"Event schema version {event_version} is not supported "
                    f"(supported: {SUPPORTED_SCHEMA_VERSION}). "
                    f"Set ALLOW_FUTURE_SCHEMA=true to allow future schema versions."
                )
            else:
                # Future schemas allowed - log warning but allow processing
                logger.warning(
                    f"{self.worker_name} processing event with future schema version "
                    f"(ALLOW_FUTURE_SCHEMA=true): event_id={event.event_id}, "
                    f"version={event_version}, supported_version={SUPPORTED_SCHEMA_VERSION}"
                )
    
    def _emit_schema_incompatible_dead_letter(
        self, event: CanonicalEvent, event_version: int
    ) -> None:
        """
        Emit DeadLettered event for schema incompatibility.
        
        Args:
            event: Original event with incompatible schema
            event_version: Version of the incompatible event
        """
        try:
            # Determine original topic from metadata or use default
            original_topic = "exceptions"  # Default topic
            if event.metadata and "original_topic" in event.metadata:
                original_topic = event.metadata["original_topic"]
            
            # Create DeadLettered event
            dead_lettered_event = DeadLettered.create(
                tenant_id=event.tenant_id,
                original_event_id=event.event_id,
                original_event_type=event.event_type,
                failure_reason=f"schema_incompatible: event version {event_version} > supported version {SUPPORTED_SCHEMA_VERSION}",
                retry_count=0,  # Schema incompatibility is not retryable
                exception_id=event.exception_id,
                correlation_id=event.correlation_id,
                metadata={
                    **(event.metadata or {}),
                    "schema_version": event_version,
                    "supported_version": SUPPORTED_SCHEMA_VERSION,
                    "original_topic": original_topic,
                },
            )
            
            # Publish DeadLettered event directly via broker
            # Note: We use broker directly instead of EventPublisherService to avoid
            # circular dependencies and because this is a base worker class
            event_json = dead_lettered_event.model_dump_json()
            self.broker.publish(
                topic="exceptions",  # DeadLettered events go to exceptions topic
                partition_key=event.tenant_id,  # Partition by tenant
                value=event_json.encode("utf-8"),
            )
            
            logger.info(
                f"{self.worker_name} emitted DeadLettered event for schema incompatibility: "
                f"original_event_id={event.event_id}, version={event_version}"
            )
        except Exception as e:
            logger.error(
                f"{self.worker_name} failed to emit DeadLettered event for schema incompatibility: {e}",
                exc_info=True,
            )

    def _check_idempotency(self, event_id: str) -> bool:
        """
        Check if event has already been processed (idempotency check).
        
        Args:
            event_id: Event identifier
            
        Returns:
            True if event already processed, False otherwise
        """
        # Use repository if available
        if self.event_processing_repo:
            try:
                # Use asyncio.run to call async method from sync context
                return asyncio.run(
                    self.event_processing_repo.is_processed(event_id, self.worker_name)
                )
            except Exception as e:
                logger.error(
                    f"{self.worker_name} error checking idempotency for {event_id}: {e}",
                    exc_info=True,
                )
                # On error, allow processing (fail open)
                return False
        
        # Fallback to legacy hook
        if self._idempotency_check:
            return self._idempotency_check(event_id)
        
        # Default: no idempotency check
        return False

    def _mark_event_processing(self, event: CanonicalEvent) -> None:
        """
        Mark event as being processed.
        
        Args:
            event: CanonicalEvent instance
        """
        # Use repository if available
        if self.event_processing_repo:
            try:
                asyncio.run(
                    self.event_processing_repo.mark_processing(
                        event_id=event.event_id,
                        worker_type=self.worker_name,
                        tenant_id=event.tenant_id,
                        exception_id=event.exception_id,
                    )
                )
                return
            except Exception as e:
                logger.error(
                    f"{self.worker_name} error marking event {event.event_id} as processing: {e}",
                    exc_info=True,
                )
                # Continue processing even if marking fails
        
        # Fallback to legacy hook
        if self._mark_processing:
            self._mark_processing(event.event_id)

    def _mark_event_completed(self, event_id: str) -> None:
        """
        Mark event as completed.
        
        Args:
            event_id: Event identifier
        """
        # Use repository if available
        if self.event_processing_repo:
            try:
                asyncio.run(
                    self.event_processing_repo.mark_completed(event_id, self.worker_name)
                )
                return
            except Exception as e:
                logger.error(
                    f"{self.worker_name} error marking event {event_id} as completed: {e}",
                    exc_info=True,
                )
                # Continue even if marking fails
        
        # Fallback to legacy hook
        if self._mark_completed:
            self._mark_completed(event_id)

    def _mark_event_failed(self, event_id: str, error_message: Optional[str] = None) -> None:
        """
        Mark event processing as failed.
        
        Args:
            event_id: Event identifier
            error_message: Optional error message
        """
        # Use repository if available
        if self.event_processing_repo:
            try:
                asyncio.run(
                    self.event_processing_repo.mark_failed(
                        event_id, self.worker_name, error_message
                    )
                )
                return
            except Exception as e:
                logger.error(
                    f"{self.worker_name} error marking event {event_id} as failed: {e}",
                    exc_info=True,
                )
                # Continue even if marking fails

    def _handle_message(
        self, topic: str, key: Optional[str], value: bytes
    ) -> None:
        """
        Handle incoming message from broker.
        
        Phase 9 P9-23: Enforces tenant isolation by validating tenant_id before processing.
        Phase 9 P9-26: Supports concurrent event processing via thread pool.
        Option A (MVP): Shared topics + strict tenant validation.
        
        Args:
            topic: Topic name
            key: Partition key
            value: Message value (bytes)
        """
        # Phase 9 P9-26: If concurrency > 1, submit to thread pool
        if self.concurrency > 1:
            if self._executor is None:
                logger.warning(
                    f"{self.worker_name} executor not initialized, processing synchronously"
                )
                self._process_message_sync(topic, key, value)
            else:
                # Submit to thread pool for concurrent processing
                with self._futures_lock:
                    # Clean up completed futures
                    self._active_futures = {f for f in self._active_futures if not f.done()}
                    
                    # Wait if we're at concurrency limit
                    while len(self._active_futures) >= self.concurrency:
                        # Wait for at least one future to complete (synchronous wait)
                        import concurrent.futures
                        done, not_done = concurrent.futures.wait(
                            self._active_futures,
                            return_when=concurrent.futures.FIRST_COMPLETED,
                            timeout=1.0,  # 1 second timeout
                        )
                        # Remove completed futures
                        self._active_futures = {f for f in self._active_futures if not f.done()}
                    
                    # Submit new task
                    future = self._executor.submit(self._process_message_sync, topic, key, value)
                    self._active_futures.add(future)
        else:
            # Sequential processing (concurrency = 1)
            self._process_message_sync(topic, key, value)
    
    def _process_message_sync(
        self, topic: str, key: Optional[str], value: bytes
    ) -> None:
        """
        Process a message synchronously (internal method).
        
        Phase 9 P9-26: Extracted from _handle_message for concurrent processing.
        
        Args:
            topic: Topic name
            key: Partition key
            value: Message value (bytes)
        """
        try:
            # Deserialize and validate event (includes schema version validation)
            try:
                event = self._deserialize_event(value)
            except SchemaVersionError as e:
                # Schema version error already emitted DeadLettered event
                logger.warning(
                    f"{self.worker_name} rejected event due to schema incompatibility: {e}"
                )
                self._errors_count += 1
                self._last_error = str(e)
                return
            
            logger.info(
                f"{self.worker_name} received event: event_id={event.event_id}, "
                f"event_type={event.event_type}, topic={topic}, tenant_id={event.tenant_id}"
            )
            
            # Phase 9 P9-23: Validate tenant_id for tenant isolation
            if not self._validate_tenant(event):
                logger.warning(
                    f"{self.worker_name} rejected cross-tenant event: event_id={event.event_id}, "
                    f"tenant_id={event.tenant_id}, topic={topic}"
                )
                return
            
            # Check idempotency
            if self._check_idempotency(event.event_id):
                logger.info(
                    f"{self.worker_name} skipping duplicate event: event_id={event.event_id}"
                )
                return
            
            # Mark as processing
            self._mark_event_processing(event)
            
            # Increment events in processing metric
            metrics = get_metrics()
            metrics.increment_events_in_processing(
                worker_type=self.worker_name,
                tenant_id=event.tenant_id,
            )
            
            # Process event (async method called from sync context)
            # Use the persistent event loop created in the consumer thread
            start_time = time.time()
            try:
                # Get the persistent event loop for this thread
                # This was created in _start_consumer and ensures database connections work
                loop = getattr(self, '_thread_event_loop', None)
                if loop is None or loop.is_closed():
                    # Fallback: try to get current event loop
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_closed():
                            raise RuntimeError("Event loop is closed")
                    except RuntimeError:
                        # Create new event loop as last resort
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        logger.warning(
                            f"{self.worker_name} created new event loop in message handler - "
                            "this may cause database connection issues"
                        )
                
                # Run the async function in the thread's persistent event loop
                loop.run_until_complete(self.process_event(event))
                
                # Calculate latency
                latency_seconds = time.time() - start_time
                
                # Record successful processing
                record_event_processed(
                    worker_type=self.worker_name,
                    event_type=event.event_type,
                    tenant_id=event.tenant_id,
                    status="success",
                    latency_seconds=latency_seconds,
                )
                
                self._messages_processed += 1
                self._mark_event_completed(event.event_id)
                
                logger.info(
                    f"{self.worker_name} successfully processed event: event_id={event.event_id}, "
                    f"event_type={event.event_type}, tenant_id={event.tenant_id}"
                )
            except Exception as e:
                # Calculate latency even for failures
                latency_seconds = time.time() - start_time
                
                self._errors_count += 1
                self._last_error = str(e)
                error_msg = str(e)
                
                # Determine error type
                error_type = "processing_error"
                if "validation" in error_msg.lower():
                    error_type = "validation_error"
                elif "timeout" in error_msg.lower():
                    error_type = "timeout"
                elif "database" in error_msg.lower() or "db" in error_msg.lower():
                    error_type = "database_error"
                
                # Record failure
                record_event_failure(
                    worker_type=self.worker_name,
                    event_type=event.event_type,
                    tenant_id=event.tenant_id,
                    error_type=error_type,
                )
                
                logger.error(
                    f"{self.worker_name} error processing event {event.event_id}: {e}",
                    exc_info=True,
                )
                # Mark as failed
                self._mark_event_failed(event.event_id, error_msg)
                # Don't re-raise - continue processing other messages
            finally:
                # Decrement events in processing metric
                metrics.decrement_events_in_processing(
                    worker_type=self.worker_name,
                    tenant_id=event.tenant_id,
                )
                
        except WorkerError as e:
            self._errors_count += 1
            self._last_error = str(e)
            logger.error(f"{self.worker_name} error handling message: {e}", exc_info=True)
        except Exception as e:
            self._errors_count += 1
            self._last_error = str(e)
            logger.error(
                f"{self.worker_name} unexpected error handling message: {e}",
                exc_info=True,
            )
    
    def set_expected_tenant(self, tenant_id: str) -> None:
        """
        Set expected tenant ID for tenant-scoped workers.
        
        Phase 9 P9-23: For tenant-scoped workers, this enforces that only events
        from the specified tenant are processed.
        
        Args:
            tenant_id: Expected tenant identifier
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        self._expected_tenant_id = tenant_id.strip()
        logger.info(f"{self.worker_name} configured for tenant: {tenant_id}")
    
    def _validate_tenant(self, event: CanonicalEvent) -> bool:
        """
        Validate tenant_id for tenant isolation.
        
        Phase 9 P9-23: Option A (MVP) - Shared topics + strict tenant validation.
        
        Validates:
        1. Event has a valid tenant_id
        2. If worker is tenant-scoped, tenant_id matches expected tenant
        3. Tenant_id format is valid (non-empty string)
        
        Args:
            event: CanonicalEvent to validate
            
        Returns:
            True if tenant validation passes, False otherwise
        """
        # Check if event has tenant_id
        if not event.tenant_id or not event.tenant_id.strip():
            logger.error(
                f"{self.worker_name} rejected event with missing tenant_id: "
                f"event_id={event.event_id}, event_type={event.event_type}"
            )
            return False
        
        # If worker is tenant-scoped, validate tenant_id matches
        if self._expected_tenant_id is not None:
            if event.tenant_id.strip() != self._expected_tenant_id:
                logger.warning(
                    f"{self.worker_name} rejected cross-tenant event: "
                    f"event_id={event.event_id}, event_tenant_id={event.tenant_id}, "
                    f"expected_tenant_id={self._expected_tenant_id}"
                )
                return False
        
        # Tenant validation passed
        return True

    def _run_consumer(self) -> None:
        """
        Run consumer in a separate thread with persistent event loop.
        
        Creates a persistent event loop for this thread to handle async operations.
        This ensures all database connections are created in the correct event loop.
        """
        logger.info(f"{self.worker_name} starting consumer thread")
        
        # Create a persistent event loop for this thread
        # This ensures all async operations (including database) use the same loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._thread_event_loop = loop
        
        try:
            # Initialize database engine in this thread's event loop
            # This ensures all database connections are created in the correct loop
            loop.run_until_complete(self._initialize_thread_database())
            
            # Subscribe to topics and process messages
            self.broker.subscribe(
                topics=self.topics,
                group_id=self.group_id,
                handler=self._handle_message,
            )
        except BrokerSubscribeError as e:
            logger.error(f"{self.worker_name} subscription error: {e}", exc_info=True)
            self._running = False
        except Exception as e:
            logger.error(
                f"{self.worker_name} unexpected error in consumer: {e}", exc_info=True
            )
            self._running = False
        finally:
            # Clean up event loop when thread exits
            try:
                if loop and not loop.is_closed():
                    # Cancel all pending tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    # Wait for tasks to complete cancellation
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                    loop.close()
            except Exception:
                pass
    
    async def _initialize_thread_database(self) -> None:
        """
        Initialize database engine in the current thread's event loop.
        
        This ensures all database connections are created in the correct event loop.
        """
        try:
            from src.infrastructure.db.session import get_engine
            from sqlalchemy import text
            # Force engine creation in this thread's event loop
            engine = get_engine()
            # Test connection to ensure it works in this loop
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            logger.debug(f"{self.worker_name} database engine initialized in thread event loop")
        except Exception as e:
            logger.warning(
                f"{self.worker_name} database initialization warning: {e}",
                exc_info=True,
            )
            # Don't fail - engine might already be created

    def run(self) -> None:
        """
        Start the worker.
        
        Phase 9 P9-26: Initializes thread pool executor for concurrent processing.
        
        This method blocks until shutdown is called.
        """
        if self._running:
            logger.warning(f"{self.worker_name} is already running")
            return
        
        logger.info(f"{self.worker_name} starting worker (concurrency={self.concurrency})")
        self._running = True
        self._shutdown_event.clear()
        
        # Phase 9 P9-26: Initialize thread pool executor for concurrent processing
        if self.concurrency > 1:
            self._executor = ThreadPoolExecutor(
                max_workers=self.concurrency,
                thread_name_prefix=f"{self.worker_name}-worker",
            )
            logger.info(
                f"{self.worker_name} initialized thread pool with {self.concurrency} workers"
            )
        
        # Start consumer in a separate thread
        self._consumer_thread = threading.Thread(
            target=self._run_consumer, daemon=False, name=f"{self.worker_name}-consumer"
        )
        self._consumer_thread.start()
        
        # Wait for shutdown signal
        try:
            self._shutdown_event.wait()
        except KeyboardInterrupt:
            logger.info(f"{self.worker_name} received interrupt signal")
            self.shutdown()

    def shutdown(self, timeout: float = 10.0) -> None:
        """
        Shutdown the worker gracefully.
        
        Phase 9 P9-26: Shuts down thread pool executor and waits for active tasks.
        
        Args:
            timeout: Maximum time to wait for shutdown (seconds)
        """
        if not self._running:
            logger.warning(f"{self.worker_name} is not running")
            return
        
        logger.info(f"{self.worker_name} shutting down...")
        self._running = False
        self._shutdown_event.set()
        
        # Phase 9 P9-26: Shutdown thread pool executor
        if self._executor:
            logger.info(f"{self.worker_name} shutting down thread pool executor...")
            # Wait for active futures to complete
            with self._futures_lock:
                active_futures = list(self._active_futures)
            
            if active_futures:
                logger.info(
                    f"{self.worker_name} waiting for {len(active_futures)} active tasks to complete..."
                )
                # Wait for all futures with timeout
                import concurrent.futures
                done, not_done = concurrent.futures.wait(
                    active_futures, timeout=timeout, return_when=concurrent.futures.ALL_COMPLETED
                )
                if not_done:
                    logger.warning(
                        f"{self.worker_name} {len(not_done)} tasks did not complete within timeout"
                    )
            
            self._executor.shutdown(wait=True, timeout=timeout)
            self._executor = None
        
        # Wait for consumer thread to finish
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=timeout)
            if self._consumer_thread.is_alive():
                logger.warning(
                    f"{self.worker_name} consumer thread did not stop within timeout"
                )
        
        # Close broker connections
        try:
            self.broker.close()
        except Exception as e:
            logger.warning(f"{self.worker_name} error closing broker: {e}")
        
        logger.info(
            f"{self.worker_name} shutdown complete. "
            f"Processed {self._messages_processed} messages, "
            f"{self._errors_count} errors"
        )

    def health(self) -> WorkerHealth:
        """
        Get worker health status.
        
        Returns:
            WorkerHealth instance with status and metrics
        """
        # Determine health status
        if not self._running:
            status = "unhealthy"
        elif self._errors_count > 0 and self._messages_processed == 0:
            status = "unhealthy"
        elif self._errors_count > self._messages_processed * 0.1:  # >10% error rate
            status = "degraded"
        else:
            status = "healthy"
        
        return WorkerHealth(
            status=status,
            is_running=self._running,
            messages_processed=self._messages_processed,
            errors_count=self._errors_count,
            last_error=self._last_error,
        )

    def get_stats(self) -> dict[str, Any]:
        """
        Get worker statistics.
        
        Returns:
            Dictionary with worker statistics
        """
        return {
            "worker_name": self.worker_name,
            "topics": self.topics,
            "group_id": self.group_id,
            "is_running": self._running,
            "messages_processed": self._messages_processed,
            "errors_count": self._errors_count,
            "last_error": self._last_error,
        }

