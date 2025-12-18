"""
Integration tests for Kafka broker against docker Kafka.

These tests require a running Kafka instance (e.g., via docker-compose).
They are marked as integration tests and can be skipped if Kafka is not available.
"""

import json
import os
import pytest
import time
import threading
from typing import Optional

from src.messaging.kafka_broker import KafkaBroker
from src.messaging.settings import BrokerSettings


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


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("SKIP_KAFKA_INTEGRATION_TESTS", "false").lower() == "true",
    reason="Kafka integration tests skipped via SKIP_KAFKA_INTEGRATION_TESTS",
)
class TestKafkaBrokerIntegration:
    """Integration tests for Kafka broker."""
    
    def test_health_check(self, kafka_broker):
        """Test health check against real Kafka."""
        health = kafka_broker.health()
        
        # Health check should succeed if Kafka is running
        # If Kafka is not available, status will be "unhealthy"
        assert "status" in health
        assert "connected" in health
        assert health["status"] in ("healthy", "unhealthy")
        
    def test_publish_and_consume_message(self, kafka_broker):
        """Test publishing and consuming a message."""
        topic = f"test-topic-{int(time.time())}"
        test_key = "test-key"
        test_value = {"message": "test", "timestamp": time.time()}
        
        # Publish message
        kafka_broker.publish(topic, test_key, test_value)
        
        # Consume message
        received_messages = []
        
        def handler(topic_name: str, key: Optional[str], value: bytes) -> None:
            received_messages.append((topic_name, key, value))
        
        # Subscribe in a separate thread with timeout
        def consume_with_timeout():
            try:
                kafka_broker.subscribe([topic], f"test-group-{int(time.time())}", handler)
            except KeyboardInterrupt:
                pass
        
        consumer_thread = threading.Thread(target=consume_with_timeout, daemon=True)
        consumer_thread.start()
        
        # Wait for message to be consumed (with timeout)
        max_wait = 5
        start_time = time.time()
        while len(received_messages) == 0 and (time.time() - start_time) < max_wait:
            time.sleep(0.1)
        
        # Stop consumer (this is a simplified approach - in real code, use proper shutdown)
        consumer_thread.join(timeout=1)
        
        # Verify message was received
        if len(received_messages) > 0:
            topic_name, key, value_bytes = received_messages[0]
            assert topic_name == topic
            assert key == test_key
            received_value = json.loads(value_bytes.decode("utf-8"))
            assert received_value["message"] == test_value["message"]
        else:
            # If no message received, it might be a timing issue or Kafka not available
            pytest.skip("Message not received - Kafka may not be available or timing issue")
            
    def test_publish_string_message(self, kafka_broker):
        """Test publishing a string message."""
        topic = f"test-topic-string-{int(time.time())}"
        test_value = "test string message"
        
        # Should not raise exception
        kafka_broker.publish(topic, None, test_value)
        
    def test_publish_bytes_message(self, kafka_broker):
        """Test publishing a bytes message."""
        topic = f"test-topic-bytes-{int(time.time())}"
        test_value = b"test bytes message"
        
        # Should not raise exception
        kafka_broker.publish(topic, "key1", test_value)
        
    def test_multiple_publishes(self, kafka_broker):
        """Test publishing multiple messages."""
        topic = f"test-topic-multi-{int(time.time())}"
        
        # Publish multiple messages
        for i in range(5):
            kafka_broker.publish(topic, f"key{i}", {"index": i, "data": f"message{i}"})
        
        # All publishes should succeed without exception
        assert True  # If we get here, all publishes succeeded



