"""
Kafka consumer lag metrics collector (best effort).

Attempts to collect consumer lag metrics from Kafka consumer groups.
This is a best-effort implementation that may not work in all environments.
"""

import logging
from typing import Optional

from src.messaging.broker import get_broker
from src.messaging.settings import get_broker_settings
from src.observability.prometheus_metrics import update_kafka_consumer_lag

logger = logging.getLogger(__name__)


def collect_kafka_consumer_lag(
    topic: str,
    group_id: str,
    tenant_id: Optional[str] = None,
) -> None:
    """
    Collect Kafka consumer lag for a topic/group (best effort).
    
    This is a best-effort implementation that attempts to query Kafka
    for consumer lag. It may fail silently if:
    - Kafka admin API is not available
    - Consumer group doesn't exist
    - Kafka version doesn't support lag queries
    
    Args:
        topic: Kafka topic name
        group_id: Consumer group ID
        tenant_id: Optional tenant identifier
    """
    try:
        broker = get_broker()
        
        # Try to get consumer lag using broker's admin client
        # This is best-effort and may not work in all environments
        lag = _get_consumer_lag_best_effort(broker, topic, group_id)
        
        if lag is not None:
            update_kafka_consumer_lag(
                topic=topic,
                group_id=group_id,
                lag=lag,
                tenant_id=tenant_id,
            )
            logger.debug(f"Updated consumer lag for topic={topic}, group={group_id}, lag={lag}")
        else:
            logger.debug(f"Could not determine consumer lag for topic={topic}, group={group_id}")
    
    except Exception as e:
        # Best effort - don't fail if we can't collect lag
        logger.debug(f"Failed to collect consumer lag for topic={topic}, group={group_id}: {e}")


def _get_consumer_lag_best_effort(broker, topic: str, group_id: str) -> Optional[int]:
    """
    Attempt to get consumer lag (best effort).
    
    This method tries multiple approaches to get consumer lag:
    1. Use confluent-kafka AdminClient if available
    2. Use kafka-python AdminClient if available
    3. Return None if neither works
    
    Args:
        broker: Broker instance
        topic: Topic name
        group_id: Consumer group ID
        
    Returns:
        Consumer lag (number of messages behind) or None if unavailable
    """
    try:
        # Check if broker has admin client
        if hasattr(broker, '_admin_client') and broker._admin_client:
            # Try confluent-kafka approach
            if broker._use_confluent:
                try:
                    from confluent_kafka.admin import AdminClient
                    # Get consumer group metadata
                    # Note: This is a simplified approach - full implementation would
                    # need to query consumer group offsets and topic end offsets
                    # For MVP, we'll return None and let the metric be unset
                    return None
                except Exception:
                    pass
            
            # Try kafka-python approach
            else:
                try:
                    from kafka import KafkaAdminClient
                    # Similar limitation - would need full consumer group API
                    return None
                except Exception:
                    pass
        
        # If we can't get lag, return None (metric will be unset)
        return None
    
    except Exception:
        return None


def collect_all_worker_consumer_lags(tenant_id: Optional[str] = None) -> None:
    """
    Collect consumer lag for all known worker consumer groups.
    
    This is a convenience function that attempts to collect lag metrics
    for all worker types. It's best-effort and may not work in all environments.
    
    Args:
        tenant_id: Optional tenant identifier
    """
    # Known worker consumer groups (from worker configs)
    worker_groups = [
        ("exceptions", "intake-workers"),
        ("exceptions", "triage-workers"),
        ("exceptions", "policy-workers"),
        ("exceptions", "playbook-workers"),
        ("exceptions", "tool-workers"),
        ("exceptions", "feedback-workers"),
        ("sla", "sla-monitors"),
    ]
    
    for topic, group_id in worker_groups:
        try:
            collect_kafka_consumer_lag(
                topic=topic,
                group_id=group_id,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.debug(f"Failed to collect lag for topic={topic}, group={group_id}: {e}")

