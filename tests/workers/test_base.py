"""
Unit tests for Agent Worker base framework.
"""

import json
import pytest
import threading
import time
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from src.events.schema import CanonicalEvent
from src.messaging.broker import Broker, BrokerSubscribeError
from src.workers.base import AgentWorker, WorkerError, WorkerHealth


class MockBroker(Broker):
    """Mock broker for testing."""
    
    def __init__(self):
        self.published_messages = []
        self.subscribed = False
        self.subscribe_topics = []
        self.subscribe_group_id = None
        self.subscribe_handler = None
        self.should_fail_subscribe = False
        
    def publish(self, topic: str, key: str | None, value: bytes | str | dict) -> None:
        """Mock publish."""
        self.published_messages.append((topic, key, value))
        
    def subscribe(self, topics: list[str], group_id: str, handler: callable) -> None:
        """Mock subscribe."""
        if self.should_fail_subscribe:
            raise BrokerSubscribeError("Subscription failed")
        self.subscribed = True
        self.subscribe_topics = topics
        self.subscribe_group_id = group_id
        self.subscribe_handler = handler
        # Simulate message delivery
        if handler:
            test_event = CanonicalEvent.create(
                event_type="TestEvent",
                tenant_id="tenant_001",
                payload={"data": "test"},
            )
            handler("test-topic", "key1", test_event.to_json().encode("utf-8"))
        
    def health(self) -> dict:
        """Mock health."""
        return {"status": "healthy", "connected": True}
        
    def close(self) -> None:
        """Mock close."""
        pass


class TestAgentWorker(AgentWorker):
    """Test implementation of AgentWorker."""
    
    def __init__(self, broker: Broker, topics: list[str], group_id: str):
        """Initialize test worker."""
        super().__init__(broker, topics, group_id, worker_name="TestWorker")
        self.processed_events = []
        self.should_fail = False
        
    async def process_event(self, event: CanonicalEvent) -> None:
        """Process event."""
        if self.should_fail:
            raise Exception("Processing failed")
        self.processed_events.append(event)


class TestAgentWorkerBase:
    """Test AgentWorker base class."""
    
    def test_worker_initialization(self):
        """Test worker initialization."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        assert worker.topics == ["test-topic"]
        assert worker.group_id == "test-group"
        assert worker.worker_name == "TestWorker"
        assert worker._running is False
        assert worker._messages_processed == 0
        assert worker._errors_count == 0
        
    def test_worker_custom_name(self):
        """Test worker with custom name."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker.worker_name = "CustomWorker"
        
        assert worker.worker_name == "CustomWorker"
        
    def test_deserialize_event(self):
        """Test event deserialization."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        deserialized = worker._deserialize_event(event_json.encode("utf-8"))
        
        assert deserialized.event_type == "TestEvent"
        assert deserialized.tenant_id == "tenant_001"
        assert deserialized.payload == {"data": "test"}
        
    def test_deserialize_event_invalid_json(self):
        """Test deserialization with invalid JSON."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        with pytest.raises(WorkerError, match="Failed to parse event JSON"):
            worker._deserialize_event(b"invalid json")
            
    def test_deserialize_event_invalid_schema(self):
        """Test deserialization with invalid event schema."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        invalid_event = {"invalid": "data"}
        
        with pytest.raises(WorkerError, match="Failed to validate event"):
            worker._deserialize_event(json.dumps(invalid_event).encode("utf-8"))
            
    def test_idempotency_check_default(self):
        """Test default idempotency check (returns False)."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        # Default: no idempotency check
        assert worker._check_idempotency("event_001") is False
        
    def test_idempotency_check_with_hook(self):
        """Test idempotency check with hook."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        processed_events = set()
        
        def check(event_id: str) -> bool:
            return event_id in processed_events
        
        worker.set_idempotency_hooks(check=check)
        
        # First check: not processed
        assert worker._check_idempotency("event_001") is False
        
        # Mark as processed
        processed_events.add("event_001")
        
        # Second check: already processed
        assert worker._check_idempotency("event_001") is True
        
    def test_idempotency_hooks(self):
        """Test idempotency hooks (mark_processing, mark_completed)."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        processing_events = set()
        completed_events = set()
        
        def mark_processing(event_id: str) -> None:
            processing_events.add(event_id)
            
        def mark_completed(event_id: str) -> None:
            completed_events.add(event_id)
        
        worker.set_idempotency_hooks(
            mark_processing=mark_processing,
            mark_completed=mark_completed,
        )
        
        worker._mark_event_processing("event_001")
        assert "event_001" in processing_events
        
        worker._mark_event_completed("event_001")
        assert "event_001" in completed_events
        
    def test_handle_message_success(self):
        """Test successful message handling."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        # Handle message (sync call to async process_event)
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify event was processed
        assert len(worker.processed_events) == 1
        assert worker.processed_events[0].event_id == event.event_id
        assert worker._messages_processed == 1
        assert worker._errors_count == 0
        
    def test_handle_message_processing_failure(self):
        """Test message handling with processing failure."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker.should_fail = True
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        # Handle message (should catch exception)
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify error was recorded
        assert worker._errors_count == 1
        assert worker._last_error is not None
        assert "Processing failed" in worker._last_error
        
    def test_handle_message_idempotency_skip(self):
        """Test message handling skips duplicate events."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        processed_events = set()
        
        def check(event_id: str) -> bool:
            return event_id in processed_events
        
        worker.set_idempotency_hooks(check=check)
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        # Mark as already processed
        processed_events.add(event.event_id)
        
        # Handle message (should skip)
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify event was NOT processed
        assert len(worker.processed_events) == 0
        assert worker._messages_processed == 0
        
    def test_health_healthy(self):
        """Test health check when worker is healthy."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker._running = True
        worker._messages_processed = 10
        worker._errors_count = 0
        
        health = worker.health()
        
        assert health.status == "healthy"
        assert health.is_running is True
        assert health.messages_processed == 10
        assert health.errors_count == 0
        
    def test_health_unhealthy_not_running(self):
        """Test health check when worker is not running."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker._running = False
        
        health = worker.health()
        
        assert health.status == "unhealthy"
        assert health.is_running is False
        
    def test_health_degraded_high_error_rate(self):
        """Test health check when error rate is high."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker._running = True
        worker._messages_processed = 10
        worker._errors_count = 2  # 20% error rate (>10%)
        
        health = worker.health()
        
        assert health.status == "degraded"
        
    def test_get_stats(self):
        """Test getting worker statistics."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker._running = True
        worker._messages_processed = 5
        worker._errors_count = 1
        
        stats = worker.get_stats()
        
        assert stats["worker_name"] == "TestWorker"
        assert stats["topics"] == ["test-topic"]
        assert stats["group_id"] == "test-group"
        assert stats["is_running"] is True
        assert stats["messages_processed"] == 5
        assert stats["errors_count"] == 1


class TestAgentWorkerLifecycle:
    """Test worker lifecycle management."""
    
    def test_run_subscribes_to_broker(self):
        """Test run() subscribes to broker."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        # Run in a separate thread with timeout
        def run_with_timeout():
            worker.run()
        
        thread = threading.Thread(target=run_with_timeout, daemon=True)
        thread.start()
        
        # Wait a bit for subscription
        time.sleep(0.1)
        
        # Shutdown
        worker.shutdown()
        thread.join(timeout=1.0)
        
        # Verify subscription was called
        assert broker.subscribed is True
        assert broker.subscribe_topics == ["test-topic"]
        assert broker.subscribe_group_id == "test-group"
        
    def test_shutdown_gracefully(self):
        """Test graceful shutdown."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        worker._running = True
        worker._consumer_thread = threading.Thread(target=lambda: None, daemon=True)
        worker._consumer_thread.start()
        
        # Shutdown
        worker.shutdown()
        
        assert worker._running is False
        
    def test_shutdown_when_not_running(self):
        """Test shutdown when worker is not running."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        # Should not raise exception
        worker.shutdown()
        
    def test_run_already_running(self):
        """Test run() when already running."""
        broker = MockBroker()
        worker = TestAgentWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        worker._running = True
        
        # Should log warning and return
        worker.run()
        
        # Verify it didn't start another consumer
        assert worker._running is True



