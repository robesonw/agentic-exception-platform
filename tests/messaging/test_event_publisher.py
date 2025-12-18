"""
Unit tests for Event Publisher Service.
"""

import json
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, call

from src.messaging.broker import Broker, BrokerPublishError
from src.messaging.event_publisher import (
    EventPublisherService,
    EventPublishFailedError,
)
from src.messaging.event_store import EventStore, EventStoreError, InMemoryEventStore


class MockBroker(Broker):
    """Mock broker for testing."""
    
    def __init__(self):
        self.published_messages = []
        
    def publish(self, topic: str, key: str | None, value: bytes | str | dict) -> None:
        """Mock publish."""
        self.published_messages.append((topic, key, value))
        
    def subscribe(self, topics: list[str], group_id: str, handler: callable) -> None:
        """Mock subscribe."""
        pass
        
    def health(self) -> dict:
        """Mock health."""
        return {"status": "healthy", "connected": True}
        
    def close(self) -> None:
        """Mock close."""
        pass


class MockEventStore(EventStore):
    """Mock event store for testing."""
    
    def __init__(self):
        self.stored_events = []
        self.should_fail = False
        
    async def store_event(
        self,
        event_id: str,
        event_type: str,
        tenant_id: str,
        exception_id: str | None,
        timestamp: datetime,
        correlation_id: str | None,
        payload: dict,
        metadata: dict | None = None,
        version: int = 1,
    ) -> None:
        """Mock store event."""
        if self.should_fail:
            raise EventStoreError("Store failed")
        self.stored_events.append({
            "event_id": event_id,
            "event_type": event_type,
            "tenant_id": tenant_id,
            "exception_id": exception_id,
            "timestamp": timestamp,
            "correlation_id": correlation_id,
            "payload": payload,
            "metadata": metadata,
            "version": version,
        })
        
    async def get_event(self, event_id: str) -> dict | None:
        """Mock get event."""
        for event in self.stored_events:
            if event["event_id"] == event_id:
                return event
        return None


class TestEventPublisherService:
    """Test Event Publisher Service."""
    
    @pytest.mark.asyncio
    async def test_publish_event_success(self):
        """Test successful event publishing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
            "payload": {"data": "test"},
        }
        
        event_id = await publisher.publish_event("test-topic", event)
        
        # Verify event was stored
        assert len(event_store.stored_events) == 1
        stored_event = event_store.stored_events[0]
        assert stored_event["event_type"] == "ExceptionIngested"
        assert stored_event["tenant_id"] == "tenant_001"
        assert stored_event["exception_id"] == "exc_001"
        assert stored_event["payload"] == {"data": "test"}
        assert stored_event["event_id"] == event_id
        
        # Verify event was published
        assert len(broker.published_messages) == 1
        topic, partition_key, value = broker.published_messages[0]
        assert topic == "test-topic"
        assert partition_key == "tenant_001:exc_001"
        
        # Verify published value is JSON
        published_event = json.loads(value)
        assert published_event["event_type"] == "ExceptionIngested"
        assert published_event["tenant_id"] == "tenant_001"
        
    @pytest.mark.asyncio
    async def test_publish_event_generates_event_id(self):
        """Test event ID is generated if missing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "TriageCompleted",
            "tenant_id": "tenant_001",
            "payload": {"result": "test"},
        }
        
        event_id = await publisher.publish_event("test-topic", event)
        
        # Verify event ID was generated
        assert event_id is not None
        assert len(event_id) > 0
        assert event_store.stored_events[0]["event_id"] == event_id
        
    def test_publish_event_generates_timestamp(self):
        """Test timestamp is generated if missing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "PolicyEvaluationCompleted",
            "tenant_id": "tenant_001",
            "payload": {"result": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify timestamp was generated
        stored_event = event_store.stored_events[0]
        assert stored_event["timestamp"] is not None
        assert isinstance(stored_event["timestamp"], datetime)
        
    def test_publish_event_partition_key_generation(self):
        """Test partition key generation from tenant_id and exception_id."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
            "payload": {"data": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify partition key was generated
        _, partition_key, _ = broker.published_messages[0]
        assert partition_key == "tenant_001:exc_001"
        
    def test_publish_event_partition_key_tenant_only(self):
        """Test partition key with tenant_id only."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify partition key is tenant_id only
        _, partition_key, _ = broker.published_messages[0]
        assert partition_key == "tenant_001"
        
    def test_publish_event_custom_partition_key(self):
        """Test custom partition key is used when provided."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
            "payload": {"data": "test"},
        }
        
        publisher.publish_event("test-topic", event, partition_key="custom-key")
        
        # Verify custom partition key was used
        _, partition_key, _ = broker.published_messages[0]
        assert partition_key == "custom-key"
        
    def test_publish_event_store_failure(self):
        """Test publish fails when event store fails."""
        broker = MockBroker()
        event_store = MockEventStore()
        event_store.should_fail = True
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        with pytest.raises(EventPublishFailedError, match="Event store failed"):
            await publisher.publish_event("test-topic", event)
        
        # Verify event was NOT published
        assert len(broker.published_messages) == 0
        
    def test_publish_event_broker_failure(self):
        """Test publish fails when broker fails."""
        broker = MockBroker()
        
        def failing_publish(topic: str, key: str | None, value: bytes | str | dict) -> None:
            raise BrokerPublishError("Broker failed")
        
        broker.publish = failing_publish
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        with pytest.raises(EventPublishFailedError, match="stored but publish failed"):
            await publisher.publish_event("test-topic", event)
        
        # Verify event WAS stored (at-least-once guarantee)
        assert len(event_store.stored_events) == 1
        
    def test_publish_event_validation_missing_event_type(self):
        """Test validation fails when event_type is missing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        with pytest.raises(ValueError, match="event_type is required"):
            await publisher.publish_event("test-topic", event)
            
    def test_publish_event_validation_missing_tenant_id(self):
        """Test validation fails when tenant_id is missing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "payload": {"data": "test"},
        }
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await publisher.publish_event("test-topic", event)
            
    def test_publish_event_validation_missing_payload(self):
        """Test validation fails when payload is missing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
        }
        
        with pytest.raises(ValueError, match="payload is required"):
            await publisher.publish_event("test-topic", event)
            
    def test_publish_event_json_serialization(self):
        """Test event is properly JSON serialized."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        timestamp = datetime.now(timezone.utc)
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "timestamp": timestamp,
            "payload": {"data": "test", "nested": {"key": "value"}},
            "metadata": {"source": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify published value is valid JSON
        _, _, value = broker.published_messages[0]
        published_event = json.loads(value)
        
        assert published_event["event_type"] == "ExceptionIngested"
        assert published_event["tenant_id"] == "tenant_001"
        assert published_event["payload"] == {"data": "test", "nested": {"key": "value"}}
        assert published_event["metadata"] == {"source": "test"}
        # Timestamp should be ISO format string
        assert isinstance(published_event["timestamp"], str)
        
    def test_publish_event_with_correlation_id(self):
        """Test event with correlation_id."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "TriageCompleted",
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
            "correlation_id": "corr_123",
            "payload": {"result": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify correlation_id was stored
        stored_event = event_store.stored_events[0]
        assert stored_event["correlation_id"] == "corr_123"
        
    def test_publish_event_with_version(self):
        """Test event with version."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
            "version": 2,
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify version was stored
        stored_event = event_store.stored_events[0]
        assert stored_event["version"] == 2
        
    def test_publish_event_default_version(self):
        """Test event gets default version if missing."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        # Verify default version was set
        stored_event = event_store.stored_events[0]
        assert stored_event["version"] == 1


class TestEventPublisherRetry:
    """Test retry logic in event publisher."""
    
    def test_publish_event_retries_on_broker_failure(self):
        """Test publisher retries on broker failures (broker handles retries)."""
        broker = MockBroker()
        call_count = [0]
        
        def failing_publish(topic: str, key: str | None, value: bytes | str | dict) -> None:
            call_count[0] += 1
            if call_count[0] < 2:
                raise BrokerPublishError("Transient error")
            # Succeed on second call
        
        broker.publish = failing_publish
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        # Should succeed after retry
        await publisher.publish_event("test-topic", event)
        
        # Verify event was stored and published
        assert len(event_store.stored_events) == 1
        assert len(broker.published_messages) == 1


class TestEventPublisherPartitionKey:
    """Test partition key generation."""
    
    def test_partition_key_tenant_and_exception(self):
        """Test partition key with both tenant_id and exception_id."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
            "payload": {"data": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        _, partition_key, _ = broker.published_messages[0]
        assert partition_key == "tenant_001:exc_001"
        
    def test_partition_key_tenant_only(self):
        """Test partition key with tenant_id only."""
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        event = {
            "event_type": "ExceptionIngested",
            "tenant_id": "tenant_001",
            "payload": {"data": "test"},
        }
        
        await publisher.publish_event("test-topic", event)
        
        _, partition_key, _ = broker.published_messages[0]
        assert partition_key == "tenant_001"
        
    def test_partition_key_none_when_no_tenant(self):
        """Test partition key is None when tenant_id is missing."""
        # This shouldn't happen in practice due to validation,
        # but test the logic anyway
        broker = MockBroker()
        event_store = MockEventStore()
        publisher = EventPublisherService(broker, event_store)
        
        # Bypass validation by calling internal method
        partition_key = publisher._generate_partition_key(None, None)
        assert partition_key is None

