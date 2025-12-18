"""
Unit tests for Kafka broker implementation.
"""

import json
import pytest
from unittest.mock import Mock, MagicMock, patch, call
from typing import Any

from src.messaging.broker import BrokerPublishError, BrokerSubscribeError
from src.messaging.kafka_broker import KafkaBroker
from src.messaging.settings import BrokerSettings


class TestKafkaBrokerInitialization:
    """Test Kafka broker initialization."""
    
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    def test_init_with_confluent_kafka(self, mock_producer_class):
        """Test initialization with confluent-kafka available."""
        broker = KafkaBroker()
        assert broker._use_confluent is True
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", False)
    @patch("src.messaging.kafka_broker.KAFKA_PYTHON_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.KafkaProducer")
    def test_init_with_kafka_python(self, mock_producer_class):
        """Test initialization with kafka-python available."""
        broker = KafkaBroker()
        assert broker._use_confluent is False
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", False)
    @patch("src.messaging.kafka_broker.KAFKA_PYTHON_AVAILABLE", False)
    def test_init_without_kafka_libraries(self):
        """Test initialization fails when no Kafka library is available."""
        with pytest.raises(ImportError, match="Neither confluent-kafka nor kafka-python is installed"):
            KafkaBroker()


class TestKafkaBrokerPublish:
    """Test Kafka broker publish functionality."""
    
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    def test_publish_string_value_confluent(self, mock_producer_class):
        """Test publishing string value with confluent-kafka."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        broker = KafkaBroker()
        broker.publish("test-topic", "key1", "test message")
        
        # Verify producer was created
        mock_producer_class.assert_called_once()
        
        # Verify produce was called
        assert mock_producer.produce.called
        call_args = mock_producer.produce.call_args
        assert call_args[0][0] == "test-topic"  # topic
        assert call_args[0][1] == b"test message"  # value (serialized)
        assert call_args[1]["key"] == b"key1"  # key
        
        # Verify flush was called
        mock_producer.flush.assert_called_once()
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    def test_publish_dict_value_confluent(self, mock_producer_class):
        """Test publishing dict value with confluent-kafka."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        broker = KafkaBroker()
        value = {"key": "value", "number": 42}
        broker.publish("test-topic", None, value)
        
        # Verify produce was called with JSON-serialized value
        call_args = mock_producer.produce.call_args
        assert call_args[0][0] == "test-topic"
        assert json.loads(call_args[0][1].decode("utf-8")) == value
        assert call_args[1]["key"] is None
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    def test_publish_with_retry_on_transient_error(self, mock_producer_class):
        """Test publish retries on transient errors."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        # First call fails with transient error, second succeeds
        from confluent_kafka.error import KafkaException, KafkaError as ConfluentKafkaError
        
        mock_error = Mock()
        mock_error.code.return_value = ConfluentKafkaError._TIMED_OUT
        
        mock_producer.produce.side_effect = [
            KafkaException(mock_error),
            None,  # Success on retry
        ]
        
        broker = KafkaBroker()
        broker.publish("test-topic", "key1", "test message")
        
        # Verify produce was called twice (retry)
        assert mock_producer.produce.call_count == 2
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    @patch("time.sleep")
    def test_publish_exponential_backoff(self, mock_sleep, mock_producer_class):
        """Test exponential backoff on retries."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        from confluent_kafka.error import KafkaException, KafkaError as ConfluentKafkaError
        
        mock_error = Mock()
        mock_error.code.return_value = ConfluentKafkaError._TIMED_OUT
        
        # Fail twice, succeed on third attempt
        mock_producer.produce.side_effect = [
            KafkaException(mock_error),
            KafkaException(mock_error),
            None,
        ]
        
        broker = KafkaBroker()
        broker.publish("test-topic", "key1", "test message")
        
        # Verify sleep was called with increasing backoff
        assert mock_sleep.call_count == 2
        # First backoff: 100ms, second: 200ms
        assert mock_sleep.call_args_list[0][0][0] == pytest.approx(0.1, rel=0.1)
        assert mock_sleep.call_args_list[1][0][0] == pytest.approx(0.2, rel=0.1)
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    def test_publish_fails_after_max_retries(self, mock_producer_class):
        """Test publish raises error after max retries."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        from confluent_kafka.error import KafkaException, KafkaError as ConfluentKafkaError
        
        mock_error = Mock()
        mock_error.code.return_value = ConfluentKafkaError._TIMED_OUT
        
        # Always fail
        from confluent_kafka.error import KafkaException, KafkaError as ConfluentKafkaError
        
        mock_error = Mock()
        mock_error.code.return_value = ConfluentKafkaError._TIMED_OUT
        mock_producer.produce.side_effect = KafkaException(mock_error)
        
        broker = KafkaBroker()
        
        with pytest.raises(BrokerPublishError, match="Failed to publish"):
            broker.publish("test-topic", "key1", "test message")
            
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", False)
    @patch("src.messaging.kafka_broker.KAFKA_PYTHON_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.KafkaProducer")
    def test_publish_with_kafka_python(self, mock_producer_class):
        """Test publishing with kafka-python."""
        mock_producer = Mock()
        mock_future = Mock()
        mock_future.get.return_value = Mock(partition=0, offset=123, topic="test-topic")
        mock_producer.send.return_value = mock_future
        mock_producer_class.return_value = mock_producer
        
        broker = KafkaBroker()
        broker.publish("test-topic", "key1", "test message")
        
        # Verify send was called
        mock_producer.send.assert_called_once()
        call_args = mock_producer.send.call_args
        assert call_args[0][0] == "test-topic"
        assert call_args[1]["value"] == b"test message"
        assert call_args[1]["key"] == b"key1"


class TestKafkaBrokerSubscribe:
    """Test Kafka broker subscribe functionality."""
    
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Consumer")
    def test_subscribe_confluent(self, mock_consumer_class):
        """Test subscribing with confluent-kafka."""
        mock_consumer = Mock()
        mock_consumer_class.return_value = mock_consumer
        
        # Mock message
        mock_msg = Mock()
        mock_msg.error.return_value = None
        mock_msg.topic.return_value = "test-topic"
        mock_msg.key.return_value = b"key1"
        mock_msg.value.return_value = b"test value"
        
        # First poll returns message, second returns None (to break loop)
        mock_consumer.poll.side_effect = [mock_msg, None, KeyboardInterrupt()]
        
        handler_calls = []
        def handler(topic: str, key: str | None, value: bytes) -> None:
            handler_calls.append((topic, key, value))
        
        broker = KafkaBroker()
        
        # Use threading to interrupt the blocking subscribe
        import threading
        def interrupt_after_delay():
            import time
            time.sleep(0.1)
            # Simulate KeyboardInterrupt by raising it in the main thread
            import signal
            import os
            os.kill(os.getpid(), signal.SIGINT)
        
        # For testing, we'll just verify the setup
        try:
            broker.subscribe(["test-topic"], "group1", handler)
        except KeyboardInterrupt:
            pass
        
        # Verify consumer was created and subscribed
        mock_consumer_class.assert_called_once()
        mock_consumer.subscribe.assert_called_once_with(["test-topic"])
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", False)
    @patch("src.messaging.kafka_broker.KAFKA_PYTHON_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.KafkaConsumer")
    def test_subscribe_kafka_python(self, mock_consumer_class):
        """Test subscribing with kafka-python."""
        mock_consumer = Mock()
        
        # Mock message object
        mock_msg = Mock()
        mock_msg.topic = "test-topic"
        mock_msg.key = b"key1"
        mock_msg.value = b"test value"
        
        # Consumer is iterable
        mock_consumer.__iter__.return_value = iter([mock_msg, KeyboardInterrupt()])
        mock_consumer_class.return_value = mock_consumer
        
        handler_calls = []
        def handler(topic: str, key: str | None, value: bytes) -> None:
            handler_calls.append((topic, key, value))
        
        broker = KafkaBroker()
        
        try:
            broker.subscribe(["test-topic"], "group1", handler)
        except KeyboardInterrupt:
            pass
        
        # Verify consumer was created
        mock_consumer_class.assert_called_once()


class TestKafkaBrokerHealth:
    """Test Kafka broker health check."""
    
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.AdminClient")
    def test_health_healthy_confluent(self, mock_admin_class):
        """Test health check when broker is healthy (confluent-kafka)."""
        mock_admin = Mock()
        mock_metadata = Mock()
        mock_admin.list_topics.return_value = mock_metadata
        mock_admin_class.return_value = mock_admin
        
        broker = KafkaBroker()
        health = broker.health()
        
        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert "bootstrap_servers" in health["details"]
        assert health["details"]["library"] == "confluent-kafka"
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", False)
    @patch("src.messaging.kafka_broker.KAFKA_PYTHON_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.KafkaProducer")
    def test_health_healthy_kafka_python(self, mock_producer_class):
        """Test health check when broker is healthy (kafka-python)."""
        mock_producer = Mock()
        mock_producer.bootstrap_connected.return_value = True
        mock_producer_class.return_value = mock_producer
        
        broker = KafkaBroker()
        health = broker.health()
        
        assert health["status"] == "healthy"
        assert health["connected"] is True
        assert health["details"]["library"] == "kafka-python"
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.AdminClient")
    def test_health_unhealthy_confluent(self, mock_admin_class):
        """Test health check when broker is unhealthy (confluent-kafka)."""
        mock_admin = Mock()
        mock_admin.list_topics.side_effect = Exception("Connection failed")
        mock_admin_class.return_value = mock_admin
        
        broker = KafkaBroker()
        health = broker.health()
        
        assert health["status"] == "unhealthy"
        assert health["connected"] is False
        assert "error" in health["details"]


class TestKafkaBrokerClose:
    """Test Kafka broker close functionality."""
    
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    @patch("src.messaging.kafka_broker.Consumer")
    def test_close_confluent(self, mock_consumer_class, mock_producer_class):
        """Test closing connections (confluent-kafka)."""
        mock_producer = Mock()
        mock_consumer = Mock()
        mock_producer_class.return_value = mock_producer
        mock_consumer_class.return_value = mock_consumer
        
        broker = KafkaBroker()
        broker._producer = mock_producer
        broker._consumer = mock_consumer
        broker.close()
        
        mock_producer.flush.assert_called_once()
        mock_consumer.close.assert_called_once()
        assert broker._producer is None
        assert broker._consumer is None
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", False)
    @patch("src.messaging.kafka_broker.KAFKA_PYTHON_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.KafkaProducer")
    @patch("src.messaging.kafka_broker.KafkaConsumer")
    def test_close_kafka_python(self, mock_consumer_class, mock_producer_class):
        """Test closing connections (kafka-python)."""
        mock_producer = Mock()
        mock_consumer = Mock()
        mock_producer_class.return_value = mock_producer
        mock_consumer_class.return_value = mock_consumer
        
        broker = KafkaBroker()
        broker._producer = mock_producer
        broker._consumer = mock_consumer
        broker.close()
        
        mock_producer.close.assert_called_once()
        mock_consumer.close.assert_called_once()
        assert broker._producer is None
        assert broker._consumer is None


class TestKafkaBrokerConfiguration:
    """Test Kafka broker configuration."""
    
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Producer")
    def test_producer_config_includes_retry_settings(self, mock_producer_class):
        """Test producer config includes retry and backoff settings."""
        mock_producer = Mock()
        mock_producer_class.return_value = mock_producer
        
        settings = BrokerSettings()
        settings.kafka_producer_retries = 5
        settings.kafka_producer_retry_backoff_ms = 200
        
        broker = KafkaBroker(settings=settings)
        config = broker._get_producer_config()
        
        assert config["retries"] == 5
        assert config["retry.backoff.ms"] == 200
        
    @patch("src.messaging.kafka_broker.CONFLUENT_KAFKA_AVAILABLE", True)
    @patch("src.messaging.kafka_broker.Consumer")
    def test_consumer_config_includes_group_settings(self, mock_consumer_class):
        """Test consumer config includes group and offset settings."""
        mock_consumer = Mock()
        mock_consumer_class.return_value = mock_consumer
        
        settings = BrokerSettings()
        settings.kafka_consumer_auto_offset_reset = "latest"
        settings.kafka_consumer_enable_auto_commit = False
        
        broker = KafkaBroker(settings=settings)
        config = broker._get_consumer_config("test-group")
        
        assert config["group.id"] == "test-group"
        assert config["auto.offset.reset"] == "latest"
        assert config["enable.auto.commit"] is False

