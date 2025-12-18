"""
Message broker abstraction layer for Phase 9.

Provides pluggable message broker interface supporting Kafka, Azure Event Hubs,
AWS MSK, and RabbitMQ (fallback).
"""

from src.messaging.broker import Broker
from src.messaging.kafka_broker import KafkaBroker
from src.messaging.event_store import EventStore, InMemoryEventStore, DatabaseEventStore
from src.messaging.event_publisher import EventPublisherService
from src.messaging.partitioning import (
    get_partition_key,
    get_partition_key_hash,
    get_partition_number,
)
from src.messaging.retry_policy import RetryPolicy, RetryPolicyRegistry
from src.messaging.retry_scheduler import RetryScheduler, RetrySchedulerError
from src.messaging.topic_naming import TopicNamingStrategy
from src.messaging.settings import get_broker_settings

__all__ = [
    "Broker",
    "KafkaBroker",
    "EventStore",
    "InMemoryEventStore",
    "DatabaseEventStore",
    "EventPublisherService",
    "get_partition_key",
    "get_partition_key_hash",
    "get_partition_number",
    "RetryPolicy",
    "RetryPolicyRegistry",
    "RetryScheduler",
    "RetrySchedulerError",
    "TopicNamingStrategy",
    "get_broker",
]


def get_broker() -> Broker:
    """
    Get broker instance (factory function).
    
    Phase 9 P9-26: Factory function for creating broker instances.
    Currently returns KafkaBroker, but can be extended to support other brokers.
    
    Returns:
        Broker instance
    """
    settings = get_broker_settings()
    return KafkaBroker(settings=settings)

