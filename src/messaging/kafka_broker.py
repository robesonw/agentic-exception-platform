"""
Kafka message broker implementation.

Uses confluent-kafka (preferred) or kafka-python as the underlying client library.
"""

import json
import logging
import time
from typing import Any, Callable, Optional

from src.messaging.broker import (
    Broker,
    BrokerConnectionError,
    BrokerError,
    BrokerPublishError,
    BrokerSubscribeError,
)
from src.messaging.settings import get_broker_settings

logger = logging.getLogger(__name__)

# Try to import confluent-kafka first (preferred), fallback to kafka-python
try:
    from confluent_kafka import Consumer, Producer
    from confluent_kafka.admin import AdminClient
    from confluent_kafka.error import KafkaError as ConfluentKafkaError, KafkaException

    CONFLUENT_KAFKA_AVAILABLE = True
except ImportError:
    CONFLUENT_KAFKA_AVAILABLE = False
    ConfluentKafkaError = None
    KafkaException = None
    
try:
    from kafka import KafkaConsumer, KafkaProducer
    from kafka.errors import KafkaError as KafkaPythonError

    KAFKA_PYTHON_AVAILABLE = True
except ImportError:
    KAFKA_PYTHON_AVAILABLE = False
    KafkaPythonError = None


class KafkaBroker(Broker):
    """
    Kafka message broker implementation.
    
    Supports both confluent-kafka (preferred) and kafka-python libraries.
    Implements retry logic with exponential backoff for transient errors.
    """

    def __init__(self, settings: Optional[Any] = None):
        """
        Initialize Kafka broker.
        
        Args:
            settings: Optional BrokerSettings instance. If None, loads from environment.
        """
        if not CONFLUENT_KAFKA_AVAILABLE and not KAFKA_PYTHON_AVAILABLE:
            raise ImportError(
                "Neither confluent-kafka nor kafka-python is installed. "
                "Please install one: pip install confluent-kafka or pip install kafka-python"
            )

        self.settings = settings or get_broker_settings()
        self._producer: Optional[Any] = None
        self._consumer: Optional[Any] = None
        self._admin_client: Optional[Any] = None
        self._use_confluent = CONFLUENT_KAFKA_AVAILABLE

    def _get_producer_config(self) -> dict[str, Any]:
        """Build producer configuration dictionary."""
        config = {
            "bootstrap.servers": self.settings.kafka_bootstrap_servers,
            "retries": self.settings.kafka_producer_retries,
        }

        if self._use_confluent:
            # confluent-kafka configuration
            config.update({
                "retry.backoff.ms": self.settings.kafka_producer_retry_backoff_ms,
                "acks": "all",  # Wait for all replicas
                "enable.idempotence": True,  # Prevent duplicate messages
            })
            
            # Security settings
            if self.settings.kafka_security_protocol != "PLAINTEXT":
                config["security.protocol"] = self.settings.kafka_security_protocol
                
            if self.settings.kafka_sasl_mechanism:
                config["sasl.mechanism"] = self.settings.kafka_sasl_mechanism
                if self.settings.kafka_sasl_username:
                    config["sasl.username"] = self.settings.kafka_sasl_username
                if self.settings.kafka_sasl_password:
                    config["sasl.password"] = self.settings.kafka_sasl_password
                    
            if self.settings.kafka_ssl_cafile:
                config["ssl.ca.location"] = self.settings.kafka_ssl_cafile
            if self.settings.kafka_ssl_certfile:
                config["ssl.certificate.location"] = self.settings.kafka_ssl_certfile
            if self.settings.kafka_ssl_keyfile:
                config["ssl.key.location"] = self.settings.kafka_ssl_keyfile
            # Phase 9 P9-24: Additional TLS configuration options
            if self.settings.kafka_ssl_keyfile_password:
                config["ssl.key.password"] = self.settings.kafka_ssl_keyfile_password
            if not self.settings.kafka_ssl_check_hostname:
                config["ssl.endpoint.identification.algorithm"] = "none"
            if self.settings.kafka_ssl_crlfile:
                config["ssl.crl.location"] = self.settings.kafka_ssl_crlfile
            if self.settings.kafka_ssl_ciphers:
                config["ssl.cipher.suites"] = self.settings.kafka_ssl_ciphers
        else:
            # kafka-python configuration
            config.update({
                "retry_backoff_ms": self.settings.kafka_producer_retry_backoff_ms,
                "acks": "all",
            })
            
            # Security settings for kafka-python
            if self.settings.kafka_security_protocol != "PLAINTEXT":
                config["security_protocol"] = self.settings.kafka_security_protocol
                
            if self.settings.kafka_sasl_mechanism:
                config["sasl_mechanism"] = self.settings.kafka_sasl_mechanism
                if self.settings.kafka_sasl_username:
                    config["sasl_plain_username"] = self.settings.kafka_sasl_username
                if self.settings.kafka_sasl_password:
                    config["sasl_plain_password"] = self.settings.kafka_sasl_password

        return config

    def _get_consumer_config(self, group_id: str) -> dict[str, Any]:
        """Build consumer configuration dictionary."""
        config = {
            "bootstrap.servers": self.settings.kafka_bootstrap_servers,
            "group.id": group_id,
        }

        if self._use_confluent:
            # confluent-kafka configuration
            # Note: max.poll.records is not a valid confluent-kafka Consumer config property
            # It's handled internally by confluent-kafka
            config.update({
                "auto.offset.reset": self.settings.kafka_consumer_auto_offset_reset,
                "enable.auto.commit": self.settings.kafka_consumer_enable_auto_commit,
                # "max.poll.records" is not supported in confluent-kafka Consumer config
            })
            
            # Security settings
            if self.settings.kafka_security_protocol != "PLAINTEXT":
                config["security.protocol"] = self.settings.kafka_security_protocol
                
            if self.settings.kafka_sasl_mechanism:
                config["sasl.mechanism"] = self.settings.kafka_sasl_mechanism
                if self.settings.kafka_sasl_username:
                    config["sasl.username"] = self.settings.kafka_sasl_username
                if self.settings.kafka_sasl_password:
                    config["sasl.password"] = self.settings.kafka_sasl_password
                    
            if self.settings.kafka_ssl_cafile:
                config["ssl.ca.location"] = self.settings.kafka_ssl_cafile
            if self.settings.kafka_ssl_certfile:
                config["ssl.certificate.location"] = self.settings.kafka_ssl_certfile
            if self.settings.kafka_ssl_keyfile:
                config["ssl.key.location"] = self.settings.kafka_ssl_keyfile
        else:
            # kafka-python configuration
            config.update({
                "auto_offset_reset": self.settings.kafka_consumer_auto_offset_reset,
                "enable_auto_commit": self.settings.kafka_consumer_enable_auto_commit,
                "max_poll_records": self.settings.kafka_consumer_max_poll_records,
            })
            
            # Security settings for kafka-python
            if self.settings.kafka_security_protocol != "PLAINTEXT":
                config["security_protocol"] = self.settings.kafka_security_protocol
                
            if self.settings.kafka_sasl_mechanism:
                config["sasl_mechanism"] = self.settings.kafka_sasl_mechanism
                if self.settings.kafka_sasl_username:
                    config["sasl_plain_username"] = self.settings.kafka_sasl_username
                if self.settings.kafka_sasl_password:
                    config["sasl_plain_password"] = self.settings.kafka_sasl_password

        return config

    def _get_producer(self) -> Any:
        """Get or create producer instance."""
        if self._producer is None:
            config = self._get_producer_config()
            if self._use_confluent:
                self._producer = Producer(config)
            else:
                # Convert config keys for kafka-python
                kafka_python_config = {
                    k.replace(".", "_"): v for k, v in config.items()
                }
                self._producer = KafkaProducer(**kafka_python_config)
        return self._producer

    def _serialize_value(self, value: bytes | str | dict[str, Any]) -> bytes:
        """Serialize message value to bytes."""
        if isinstance(value, bytes):
            return value
        elif isinstance(value, str):
            return value.encode("utf-8")
        elif isinstance(value, dict):
            return json.dumps(value).encode("utf-8")
        else:
            raise ValueError(f"Unsupported value type: {type(value)}")

    def _publish_with_retry(
        self,
        topic: str,
        key: Optional[str],
        value: bytes,
        max_retries: int = 3,
        initial_backoff_ms: int = 100,
    ) -> None:
        """
        Publish message with retry logic and exponential backoff.
        
        Args:
            topic: Topic name
            key: Partition key
            value: Serialized message value
            max_retries: Maximum number of retry attempts
            initial_backoff_ms: Initial backoff delay in milliseconds
        """
        producer = self._get_producer()
        backoff_ms = initial_backoff_ms
        
        for attempt in range(max_retries + 1):
            try:
                if self._use_confluent:
                    # confluent-kafka: use callback-based delivery report
                    delivery_future = producer.produce(
                        topic,
                        value,
                        key=key.encode("utf-8") if key else None,
                        callback=self._delivery_callback,
                    )
                    # Poll to trigger delivery callbacks
                    producer.poll(0)
                    # Flush to ensure message is sent (blocking)
                    producer.flush(timeout=10)
                else:
                    # kafka-python: synchronous send
                    future = producer.send(
                        topic,
                        value=value,
                        key=key.encode("utf-8") if key else None,
                    )
                    # Wait for send to complete
                    record_metadata = future.get(timeout=10)
                    logger.debug(
                        f"Message sent to topic={record_metadata.topic}, "
                        f"partition={record_metadata.partition}, "
                        f"offset={record_metadata.offset}"
                    )
                
                # Success - return
                return
                
            except Exception as e:
                is_transient = self._is_transient_error(e)
                
                if attempt < max_retries and is_transient:
                    logger.warning(
                        f"Transient error publishing to {topic} (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {backoff_ms}ms..."
                    )
                    time.sleep(backoff_ms / 1000.0)
                    backoff_ms *= 2  # Exponential backoff
                else:
                    error_msg = f"Failed to publish to {topic} after {attempt + 1} attempts: {e}"
                    logger.error(error_msg)
                    raise BrokerPublishError(error_msg) from e

    def _delivery_callback(self, err: Optional[Any], msg: Any) -> None:
        """Callback for confluent-kafka message delivery reports."""
        if err is not None:
            logger.error(f"Message delivery failed: {err}")
            raise BrokerPublishError(f"Message delivery failed: {err}")

    def _is_transient_error(self, error: Exception) -> bool:
        """
        Determine if an error is transient and should be retried.
        
        Args:
            error: The exception to check
            
        Returns:
            True if error is transient, False otherwise
        """
        if self._use_confluent and KafkaException is not None and ConfluentKafkaError is not None:
            if isinstance(error, KafkaException):
                kafka_error = error.args[0] if error.args else None
                if isinstance(kafka_error, ConfluentKafkaError):
                    # Retry on network errors, broker errors, and timeouts
                    return kafka_error.code() in (
                        ConfluentKafkaError._TRANSPORT,
                        ConfluentKafkaError._ALL_BROKERS_DOWN,
                        ConfluentKafkaError._TIMED_OUT,
                        ConfluentKafkaError._NETWORK_EXCEPTION,
                    )
        elif not self._use_confluent and KafkaPythonError is not None:
            # kafka-python: check error types
            from kafka.errors import (
                BrokerNotAvailableError,
                NetworkError,
                RequestTimedOutError,
            )
            
            if isinstance(error, (NetworkError, BrokerNotAvailableError, RequestTimedOutError)):
                return True
        
        # Check for connection-related errors
        error_str = str(error).lower()
        transient_keywords = ["timeout", "connection", "network", "unavailable", "retry"]
        return any(keyword in error_str for keyword in transient_keywords)

    def publish(
        self,
        topic: str,
        key: Optional[str],
        value: bytes | str | dict[str, Any],
    ) -> None:
        """Publish a message to a topic."""
        try:
            serialized_value = self._serialize_value(value)
            self._publish_with_retry(topic, key, serialized_value)
            logger.debug(f"Published message to topic={topic}, key={key}")
        except BrokerPublishError:
            raise
        except Exception as e:
            raise BrokerPublishError(f"Unexpected error publishing to {topic}: {e}") from e

    def subscribe(
        self,
        topics: list[str],
        group_id: str,
        handler: Callable[[str, Optional[str], bytes], None],
    ) -> None:
        """
        Subscribe to topics and process messages with handler.
        
        Note: This is a blocking call. For async usage, run in a separate thread.
        """
        try:
            config = self._get_consumer_config(group_id)
            
            if self._use_confluent:
                consumer = Consumer(config)
            else:
                # Convert config keys for kafka-python
                kafka_python_config = {
                    k.replace(".", "_"): v for k, v in config.items()
                }
                consumer = KafkaConsumer(*topics, **kafka_python_config)
            
            self._consumer = consumer
            
            logger.info(f"Subscribed to topics={topics}, group_id={group_id}")
            
            if self._use_confluent:
                consumer.subscribe(topics)
                
                try:
                    while True:
                        msg = consumer.poll(timeout=1.0)
                        if msg is None:
                            continue
                        if msg.error():
                            if ConfluentKafkaError is not None and msg.error().code() == ConfluentKafkaError._PARTITION_EOF:
                                # End of partition - continue
                                continue
                            else:
                                logger.error(f"Consumer error: {msg.error()}")
                                raise BrokerSubscribeError(f"Consumer error: {msg.error()}")
                        
                        # Extract message data
                        topic_name = msg.topic()
                        key_str = msg.key().decode("utf-8") if msg.key() else None
                        value_bytes = msg.value()
                        
                        # Call handler
                        try:
                            handler(topic_name, key_str, value_bytes)
                        except Exception as e:
                            logger.error(f"Handler error processing message: {e}", exc_info=True)
                            # Continue processing other messages
                except KeyboardInterrupt:
                    logger.info("Consumer interrupted, closing...")
                finally:
                    consumer.close()
            else:
                # kafka-python
                try:
                    for msg in consumer:
                        topic_name = msg.topic
                        key_str = msg.key.decode("utf-8") if msg.key else None
                        value_bytes = msg.value
                        
                        # Call handler
                        try:
                            handler(topic_name, key_str, value_bytes)
                        except Exception as e:
                            logger.error(f"Handler error processing message: {e}", exc_info=True)
                            # Continue processing other messages
                except KeyboardInterrupt:
                    logger.info("Consumer interrupted, closing...")
                finally:
                    consumer.close()
                    
        except Exception as e:
            error_msg = f"Failed to subscribe to topics {topics}: {e}"
            logger.error(error_msg, exc_info=True)
            raise BrokerSubscribeError(error_msg) from e

    def health(self) -> dict[str, Any]:
        """
        Check broker health and connection status.
        
        Returns:
            Dictionary with health information
        """
        try:
            # Try to create admin client and list topics to verify connection
            if self._admin_client is None:
                config = {"bootstrap.servers": self.settings.kafka_bootstrap_servers}
                
                if self.settings.kafka_security_protocol != "PLAINTEXT":
                    config["security.protocol"] = self.settings.kafka_security_protocol
                    
                if self.settings.kafka_sasl_mechanism:
                    config["sasl.mechanism"] = self.settings.kafka_sasl_mechanism
                    if self.settings.kafka_sasl_username:
                        config["sasl.username"] = self.settings.kafka_sasl_username
                    if self.settings.kafka_sasl_password:
                        config["sasl.password"] = self.settings.kafka_sasl_password
                
                if self._use_confluent:
                    self._admin_client = AdminClient(config)
                else:
                    # For kafka-python, we'll use a simple producer test
                    pass
            
            # Test connection by attempting to list metadata
            if self._use_confluent:
                metadata = self._admin_client.list_topics(timeout=5)
                connected = metadata is not None
            else:
                # For kafka-python, create a test producer
                try:
                    test_producer = KafkaProducer(
                        bootstrap_servers=self.settings.kafka_bootstrap_servers.split(","),
                        request_timeout_ms=5000,
                    )
                    # Get cluster metadata
                    test_producer.bootstrap_connected()
                    connected = True
                    test_producer.close()
                except Exception:
                    connected = False
            
            if connected:
                return {
                    "status": "healthy",
                    "connected": True,
                    "details": {
                        "bootstrap_servers": self.settings.kafka_bootstrap_servers,
                        "library": "confluent-kafka" if self._use_confluent else "kafka-python",
                    },
                }
            else:
                return {
                    "status": "unhealthy",
                    "connected": False,
                    "details": {"error": "Failed to connect to broker"},
                }
                
        except Exception as e:
            logger.error(f"Health check failed: {e}", exc_info=True)
            return {
                "status": "unhealthy",
                "connected": False,
                "details": {"error": str(e)},
            }

    def close(self) -> None:
        """Close broker connections and clean up resources."""
        try:
            if self._producer:
                if self._use_confluent:
                    self._producer.flush(timeout=10)
                else:
                    self._producer.close()
                self._producer = None
                
            if self._consumer:
                if self._use_confluent:
                    self._consumer.close()
                else:
                    self._consumer.close()
                self._consumer = None
                
            self._admin_client = None
            logger.info("Broker connections closed")
        except Exception as e:
            logger.warning(f"Error closing broker connections: {e}")

