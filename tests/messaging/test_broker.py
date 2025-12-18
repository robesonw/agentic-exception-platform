"""
Unit tests for broker abstraction interface.
"""

import pytest
from unittest.mock import Mock, patch

from src.messaging.broker import (
    Broker,
    BrokerConnectionError,
    BrokerError,
    BrokerPublishError,
    BrokerSubscribeError,
)


class MockBroker(Broker):
    """Mock broker implementation for testing the interface."""
    
    def __init__(self):
        self.published_messages = []
        self.subscribed_topics = []
        self.subscribed_group_id = None
        self.handler = None
        self.health_status = {"status": "healthy", "connected": True}
        self.closed = False
        
    def publish(self, topic: str, key: str | None, value: bytes | str | dict) -> None:
        """Mock publish implementation."""
        self.published_messages.append((topic, key, value))
        
    def subscribe(
        self,
        topics: list[str],
        group_id: str,
        handler: callable,
    ) -> None:
        """Mock subscribe implementation."""
        self.subscribed_topics = topics
        self.subscribed_group_id = group_id
        self.handler = handler
        
    def health(self) -> dict:
        """Mock health implementation."""
        return self.health_status
        
    def close(self) -> None:
        """Mock close implementation."""
        self.closed = True


class TestBrokerInterface:
    """Test broker interface contract."""
    
    def test_publish_with_string_value(self):
        """Test publishing a string value."""
        broker = MockBroker()
        broker.publish("test-topic", "key1", "test message")
        
        assert len(broker.published_messages) == 1
        assert broker.published_messages[0] == ("test-topic", "key1", "test message")
        
    def test_publish_with_bytes_value(self):
        """Test publishing a bytes value."""
        broker = MockBroker()
        broker.publish("test-topic", None, b"test bytes")
        
        assert len(broker.published_messages) == 1
        assert broker.published_messages[0] == ("test-topic", None, b"test bytes")
        
    def test_publish_with_dict_value(self):
        """Test publishing a dict value."""
        broker = MockBroker()
        value = {"key": "value", "number": 42}
        broker.publish("test-topic", "key1", value)
        
        assert len(broker.published_messages) == 1
        assert broker.published_messages[0][2] == value
        
    def test_subscribe(self):
        """Test subscribing to topics."""
        broker = MockBroker()
        
        def handler(topic: str, key: str | None, value: bytes) -> None:
            pass
            
        broker.subscribe(["topic1", "topic2"], "group1", handler)
        
        assert broker.subscribed_topics == ["topic1", "topic2"]
        assert broker.subscribed_group_id == "group1"
        assert broker.handler == handler
        
    def test_health(self):
        """Test health check."""
        broker = MockBroker()
        health = broker.health()
        
        assert health["status"] == "healthy"
        assert health["connected"] is True
        
    def test_close(self):
        """Test closing broker connections."""
        broker = MockBroker()
        broker.close()
        
        assert broker.closed is True


class TestBrokerExceptions:
    """Test broker exception hierarchy."""
    
    def test_broker_error_base(self):
        """Test BrokerError is base exception."""
        error = BrokerError("test error")
        assert isinstance(error, Exception)
        assert str(error) == "test error"
        
    def test_broker_connection_error(self):
        """Test BrokerConnectionError."""
        error = BrokerConnectionError("connection failed")
        assert isinstance(error, BrokerError)
        assert str(error) == "connection failed"
        
    def test_broker_publish_error(self):
        """Test BrokerPublishError."""
        error = BrokerPublishError("publish failed")
        assert isinstance(error, BrokerError)
        assert str(error) == "publish failed"
        
    def test_broker_subscribe_error(self):
        """Test BrokerSubscribeError."""
        error = BrokerSubscribeError("subscribe failed")
        assert isinstance(error, BrokerError)
        assert str(error) == "subscribe failed"



