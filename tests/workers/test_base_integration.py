"""
Integration tests for Agent Worker lifecycle.

These tests verify worker lifecycle management and message processing.
"""

import asyncio
import json
import pytest
import threading
import time
from datetime import datetime, timezone

from src.events.schema import CanonicalEvent
from src.messaging.broker import Broker
from src.workers.base import AgentWorker


class SimpleMockBroker(Broker):
    """Simple mock broker for integration tests."""
    
    def __init__(self):
        self.subscribed = False
        self.subscribe_topics = []
        self.subscribe_group_id = None
        
    def publish(self, topic: str, key: str | None, value: bytes | str | dict) -> None:
        """Mock publish."""
        pass
        
    def subscribe(self, topics: list[str], group_id: str, handler: callable) -> None:
        """Mock subscribe."""
        self.subscribed = True
        self.subscribe_topics = topics
        self.subscribe_group_id = group_id
        
    def health(self) -> dict:
        """Mock health."""
        return {"status": "healthy", "connected": True}
        
    def close(self) -> None:
        """Mock close."""
        pass


class TestWorker(AgentWorker):
    """Test worker implementation."""
    
    def __init__(self, broker: Broker, topics: list[str], group_id: str):
        """Initialize test worker."""
        super().__init__(broker, topics, group_id, worker_name="TestWorker")
        self.processed_events = []
        self.processing_errors = []
        self.should_fail = False
        
    async def process_event(self, event: CanonicalEvent) -> None:
        """Process event."""
        if self.should_fail:
            raise Exception("Processing failed")
        self.processed_events.append(event)
        # Simulate some processing time
        await asyncio.sleep(0.01)


class TestAgentWorkerIntegration:
    """Integration tests for worker lifecycle."""
    
    @pytest.mark.asyncio
    async def test_worker_processes_events(self):
        """Test worker processes events correctly."""
        from src.messaging.kafka_broker import KafkaBroker
        from src.messaging.settings import BrokerSettings
        
        # Skip if Kafka not available
        try:
            settings = BrokerSettings()
            broker = KafkaBroker(settings=settings)
        except Exception:
            pytest.skip("Kafka not available for integration test")
        
        worker = TestWorker(
            broker=broker,
            topics=["test-worker-topic"],
            group_id="test-worker-group",
        )
        
        # Create test event
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Simulate message handling
        event_json = event.to_json()
        worker._handle_message("test-worker-topic", "key1", event_json.encode("utf-8"))
        
        # Verify event was processed
        assert len(worker.processed_events) == 1
        assert worker.processed_events[0].event_id == event.event_id
        
        # Cleanup
        broker.close()
        
    def test_worker_lifecycle_with_mock_broker(self):
        """Test worker lifecycle with mock broker."""
        broker = SimpleMockBroker()
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        # Verify initial state
        assert worker._running is False
        health = worker.health()
        assert health.status == "unhealthy"
        assert health.is_running is False
        
        # Start worker in background thread
        worker_thread = threading.Thread(target=worker.run, daemon=True)
        worker_thread.start()
        
        # Wait a bit for startup
        time.sleep(0.2)
        
        # Verify worker started
        assert worker._running is True
        assert broker.subscribed is True
        
        # Check health
        health = worker.health()
        assert health.is_running is True
        
        # Shutdown
        worker.shutdown(timeout=2.0)
        worker_thread.join(timeout=2.0)
        
        # Verify shutdown
        assert worker._running is False
        
    def test_worker_handles_multiple_events(self):
        """Test worker handles multiple events."""
        broker = SimpleMockBroker()
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        # Create multiple events
        events = [
            CanonicalEvent.create(
                event_type="TestEvent",
                tenant_id="tenant_001",
                payload={"index": i},
            )
            for i in range(5)
        ]
        
        # Process all events
        for event in events:
            event_json = event.to_json()
            worker._handle_message("test-topic", f"key{i}", event_json.encode("utf-8"))
        
        # Verify all events were processed
        assert len(worker.processed_events) == 5
        assert worker._messages_processed == 5
        assert worker._errors_count == 0
        
    def test_worker_error_handling(self):
        """Test worker error handling."""
        broker = SimpleMockBroker()
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
        )
        
        # Make worker fail
        worker.should_fail = True
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        # Process event (should handle error gracefully)
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify error was recorded but worker continues
        assert worker._errors_count == 1
        assert worker._last_error is not None
        assert worker._running is False  # Worker not started, so False is expected

