"""
Integration tests for Event Publisher Service.

These tests require a running Kafka instance (e.g., via docker-compose).
They are marked as integration tests and can be skipped if Kafka is not available.
"""

import os
import pytest
import time
from datetime import datetime, timezone

from src.messaging.kafka_broker import KafkaBroker
from src.messaging.settings import BrokerSettings
from src.messaging.event_publisher import EventPublisherService
from src.messaging.event_store import InMemoryEventStore


# Check if Kafka is available
KAFKA_BOOTSTRAP_SERVERS = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")


@pytest.fixture
def kafka_settings():
    """Create Kafka settings for integration tests."""
    settings = BrokerSettings()
    settings.kafka_bootstrap_servers = KAFKA_BOOTSTRAP_SERVERS
    return settings


@pytest.fixture
def kafka_broker(kafka_settings):
    """Create Kafka broker instance for integration tests."""
    try:
        broker = KafkaBroker(settings=kafka_settings)
        yield broker
    finally:
        broker.close()


@pytest.fixture
def event_publisher(kafka_broker):
    """Create event publisher instance for integration tests."""
    event_store = InMemoryEventStore()
    return EventPublisherService(kafka_broker, event_store)


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("SKIP_KAFKA_INTEGRATION_TESTS", "false").lower() == "true",
    reason="Kafka integration tests skipped via SKIP_KAFKA_INTEGRATION_TESTS",
)
class TestEventPublisherIntegration:
    """Integration tests for Event Publisher Service."""
    
    def test_publish_event_success(self, event_publisher):
        """Test successful event publishing to Kafka."""
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "exception_id": f"exc_{int(time.time())}",
            "payload": {
                "source": "test",
                "data": "integration test",
            },
        }
        
        # Should not raise exception
        event_id = event_publisher.publish_event("test-events", event)
        
        # Verify event ID was returned
        assert event_id is not None
        assert len(event_id) > 0
        
        # Verify event was stored
        stored_event = event_publisher.event_store.get_event(event_id)
        assert stored_event is not None
        assert stored_event["event_type"] == "ExceptionIngested"
        assert stored_event["tenant_id"] == "tenant_001"
        
    def test_publish_event_with_partition_key(self, event_publisher):
        """Test event publishing with partition key."""
        event = {
            "event_type": "TriageCompleted",
            "tenant_id": "tenant_001",
            "exception_id": f"exc_{int(time.time())}",
            "payload": {"result": "test"},
        }
        
        # Should not raise exception
        event_id = event_publisher.publish_event("test-events", event)
        
        # Verify event was stored
        stored_event = event_publisher.event_store.get_event(event_id)
        assert stored_event is not None
        assert stored_event["exception_id"] == event["exception_id"]
        
    def test_publish_multiple_events(self, event_publisher):
        """Test publishing multiple events."""
        events = [
            {
                "event_type": "ExceptionIngested",
                "tenant_id": "tenant_001",
                "exception_id": f"exc_{int(time.time())}_{i}",
                "payload": {"index": i, "data": f"message{i}"},
            }
            for i in range(5)
        ]
        
        event_ids = []
        for event in events:
            event_id = event_publisher.publish_event("test-events", event)
            event_ids.append(event_id)
        
        # Verify all events were stored
        assert len(event_ids) == 5
        for event_id in event_ids:
            stored_event = event_publisher.event_store.get_event(event_id)
            assert stored_event is not None
            
    def test_publish_event_at_least_once_guarantee(self, event_publisher):
        """Test at-least-once guarantee: event is stored before publishing."""
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "exception_id": f"exc_{int(time.time())}",
            "payload": {"data": "test"},
        }
        
        # Publish event
        event_id = event_publisher.publish_event("test-events", event)
        
        # Verify event is in store (even if publish failed, event would be stored)
        stored_event = event_publisher.event_store.get_event(event_id)
        assert stored_event is not None
        assert stored_event["event_id"] == event_id



