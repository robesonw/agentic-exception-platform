"""
Prometheus-style metrics for Phase 9 event processing.

Tracks:
- Events/sec per agent worker type
- Processing latency per event type
- Failure rates per worker type
- Retry counts
- DLQ sizes
- Kafka consumer lag (best effort)

Phase 9 P9-20: Event processing metrics for observability.
"""

import logging
import os
import time
from typing import Optional

try:
    from prometheus_client import Counter, Histogram, Gauge, generate_latest, REGISTRY
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Create dummy classes for when prometheus_client is not available
    class Counter:
        def __init__(self, *args, **kwargs):
            pass
        def inc(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
    
    class Histogram:
        def __init__(self, *args, **kwargs):
            pass
        def observe(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
        def time(self, *args, **kwargs):
            return self
    
    class Gauge:
        def __init__(self, *args, **kwargs):
            pass
        def set(self, *args, **kwargs):
            pass
        def inc(self, *args, **kwargs):
            pass
        def dec(self, *args, **kwargs):
            pass
        def labels(self, *args, **kwargs):
            return self
    
    def generate_latest():
        return b"# Prometheus metrics not available\n"
    
    REGISTRY = None

logger = logging.getLogger(__name__)


class EventProcessingMetrics:
    """
    Prometheus metrics for event processing.
    
    Tracks:
    - Events processed per second per worker type
    - Processing latency per event type (seconds and milliseconds)
    - Failure rates per worker type
    - Retry counts
    - DLQ sizes
    - Kafka consumer lag (best effort)
    
    Note: tenant_id is included in labels only if METRICS_INCLUDE_TENANT_ID=true
    to avoid cardinality explosion with many tenants.
    """
    
    def __init__(self, include_tenant_id: Optional[bool] = None):
        """
        Initialize Prometheus metrics.
        
        Args:
            include_tenant_id: If True, include tenant_id in labels. If None, reads from
                            METRICS_INCLUDE_TENANT_ID env var (default: False for safety)
        """
        if not PROMETHEUS_AVAILABLE:
            logger.warning("prometheus_client not available, metrics will be no-ops")
        
        # Determine if tenant_id should be included in labels
        if include_tenant_id is None:
            include_tenant_id = os.getenv("METRICS_INCLUDE_TENANT_ID", "false").lower() == "true"
        self.include_tenant_id = include_tenant_id
        
        # Build label lists based on whether tenant_id is included
        # Base labels: worker_type, event_type
        # Optional: tenant_id (only if include_tenant_id=True)
        base_labels = ["worker_type", "event_type"]
        if self.include_tenant_id:
            base_labels.append("tenant_id")
        
        worker_labels = ["worker_type"]
        if self.include_tenant_id:
            worker_labels.append("tenant_id")
        
        topic_group_labels = ["topic", "group_id"]
        if self.include_tenant_id:
            topic_group_labels.append("tenant_id")
        
        # Events processed counter (by worker + event_type)
        self.events_processed = Counter(
            "sentinai_events_processed_total",
            "Total number of events processed",
            base_labels + ["status"],
        )
        
        # Processing latency histogram (seconds)
        self.processing_latency_seconds = Histogram(
            "sentinai_event_processing_latency_seconds",
            "Event processing latency in seconds",
            base_labels,
            buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0],
        )
        
        # Processing latency histogram (milliseconds) - for finer granularity
        self.processing_latency_ms = Histogram(
            "sentinai_event_processing_latency_ms",
            "Event processing latency in milliseconds",
            worker_labels,  # Only worker_type (and tenant_id if enabled) for lower cardinality
            buckets=[1, 5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000, 30000, 60000],
        )
        
        # Failures counter (consolidated)
        self.failures_total = Counter(
            "sentinai_failures_total",
            "Total number of event processing failures",
            base_labels + ["error_type"],
        )
        
        # Retries counter (consolidated)
        self.retries_total = Counter(
            "sentinai_retries_total",
            "Total number of event retries",
            base_labels + ["retry_attempt"],
        )
        
        # DLQ counter (consolidated)
        self.dlq_total = Counter(
            "sentinai_dlq_total",
            "Total number of events moved to dead letter queue",
            base_labels,
        )
        
        # DLQ size gauge (current size)
        dlq_size_labels = ["event_type", "worker_type"]
        if self.include_tenant_id:
            dlq_size_labels.append("tenant_id")
        self.dlq_size = Gauge(
            "sentinai_dlq_size",
            "Current number of events in dead letter queue",
            dlq_size_labels,
        )
        
        # Events in processing gauge
        self.events_in_processing = Gauge(
            "sentinai_events_in_processing",
            "Number of events currently being processed",
            worker_labels,
        )
        
        # Kafka consumer lag gauge (best effort)
        self.kafka_consumer_lag = Gauge(
            "sentinai_kafka_consumer_lag",
            "Kafka consumer lag (messages behind) per topic and consumer group",
            topic_group_labels,
        )
        
        # Legacy metrics (for backward compatibility)
        # These will be deprecated but kept for now
        self.failures = self.failures_total
        self.retries = self.retries_total
        self.processing_latency = self.processing_latency_seconds
        
        logger.info(
            f"Initialized Prometheus metrics for event processing "
            f"(include_tenant_id={self.include_tenant_id})"
        )
    
    def _get_labels(self, worker_type: str, event_type: str, tenant_id: str) -> dict[str, str]:
        """Get labels dict based on include_tenant_id setting."""
        labels = {
            "worker_type": worker_type,
            "event_type": event_type,
        }
        if self.include_tenant_id:
            labels["tenant_id"] = tenant_id
        return labels
    
    def _get_worker_labels(self, worker_type: str, tenant_id: str) -> dict[str, str]:
        """Get worker-only labels dict."""
        labels = {"worker_type": worker_type}
        if self.include_tenant_id:
            labels["tenant_id"] = tenant_id
        return labels
    
    def record_event_processed(
        self,
        worker_type: str,
        event_type: str,
        tenant_id: str,
        status: str = "success",
        latency_seconds: Optional[float] = None,
    ) -> None:
        """
        Record a successfully processed event.
        
        Args:
            worker_type: Type of worker (e.g., "IntakeWorker", "TriageWorker")
            event_type: Type of event (e.g., "ExceptionIngested", "TriageCompleted")
            tenant_id: Tenant identifier
            status: Processing status ("success", "failed")
            latency_seconds: Optional processing latency in seconds
        """
        labels = self._get_labels(worker_type, event_type, tenant_id)
        labels["status"] = status
        self.events_processed.labels(**labels).inc()
        
        if latency_seconds is not None:
            # Record in seconds histogram
            self.processing_latency_seconds.labels(**self._get_labels(worker_type, event_type, tenant_id)).observe(latency_seconds)
            
            # Record in milliseconds histogram (worker-level only for lower cardinality)
            latency_ms = latency_seconds * 1000
            worker_labels = self._get_worker_labels(worker_type, tenant_id)
            self.processing_latency_ms.labels(**worker_labels).observe(latency_ms)
    
    def record_event_failure(
        self,
        worker_type: str,
        event_type: str,
        tenant_id: str,
        error_type: str = "unknown",
    ) -> None:
        """
        Record a failed event processing.
        
        Args:
            worker_type: Type of worker
            event_type: Type of event
            tenant_id: Tenant identifier
            error_type: Type of error (e.g., "validation_error", "processing_error", "timeout")
        """
        labels = self._get_labels(worker_type, event_type, tenant_id)
        labels["error_type"] = error_type
        self.failures_total.labels(**labels).inc()
        
        # Also record as processed with status="failed"
        self.record_event_processed(
            worker_type=worker_type,
            event_type=event_type,
            tenant_id=tenant_id,
            status="failed",
        )
    
    def record_retry(
        self,
        worker_type: str,
        event_type: str,
        tenant_id: str,
        retry_attempt: int,
    ) -> None:
        """
        Record an event retry.
        
        Args:
            worker_type: Type of worker
            event_type: Type of event
            tenant_id: Tenant identifier
            retry_attempt: Retry attempt number (1, 2, 3, ...)
        """
        labels = self._get_labels(worker_type, event_type, tenant_id)
        labels["retry_attempt"] = str(retry_attempt)
        self.retries_total.labels(**labels).inc()
    
    def record_dlq(
        self,
        worker_type: str,
        event_type: str,
        tenant_id: str,
    ) -> None:
        """
        Record an event moved to DLQ.
        
        Args:
            worker_type: Type of worker
            event_type: Type of event
            tenant_id: Tenant identifier
        """
        labels = self._get_labels(worker_type, event_type, tenant_id)
        self.dlq_total.labels(**labels).inc()
    
    def update_dlq_size(
        self,
        tenant_id: str,
        event_type: str,
        worker_type: str,
        size: int,
    ) -> None:
        """
        Update DLQ size gauge.
        
        Args:
            tenant_id: Tenant identifier
            event_type: Type of event
            worker_type: Type of worker
            size: Current DLQ size
        """
        labels = {"event_type": event_type, "worker_type": worker_type}
        if self.include_tenant_id:
            labels["tenant_id"] = tenant_id
        self.dlq_size.labels(**labels).set(size)
    
    def increment_events_in_processing(
        self,
        worker_type: str,
        tenant_id: str,
    ) -> None:
        """
        Increment events in processing gauge.
        
        Args:
            worker_type: Type of worker
            tenant_id: Tenant identifier
        """
        labels = self._get_worker_labels(worker_type, tenant_id)
        self.events_in_processing.labels(**labels).inc()
    
    def decrement_events_in_processing(
        self,
        worker_type: str,
        tenant_id: str,
    ) -> None:
        """
        Decrement events in processing gauge.
        
        Args:
            worker_type: Type of worker
            tenant_id: Tenant identifier
        """
        labels = self._get_worker_labels(worker_type, tenant_id)
        self.events_in_processing.labels(**labels).dec()
    
    def update_kafka_consumer_lag(
        self,
        topic: str,
        group_id: str,
        lag: int,
        tenant_id: Optional[str] = None,
    ) -> None:
        """
        Update Kafka consumer lag gauge (best effort).
        
        Args:
            topic: Kafka topic name
            group_id: Consumer group ID
            lag: Consumer lag (number of messages behind)
            tenant_id: Optional tenant identifier (only used if include_tenant_id=True)
        """
        labels = {"topic": topic, "group_id": group_id}
        if self.include_tenant_id and tenant_id:
            labels["tenant_id"] = tenant_id
        self.kafka_consumer_lag.labels(**labels).set(lag)
    
    def get_metrics(self) -> bytes:
        """
        Get Prometheus metrics in text format.
        
        Returns:
            Metrics in Prometheus text format
        """
        if not PROMETHEUS_AVAILABLE:
            return b"# Prometheus metrics not available\n"
        return generate_latest(REGISTRY)


# Global metrics instance
_metrics_instance: Optional[EventProcessingMetrics] = None


def get_metrics() -> EventProcessingMetrics:
    """
    Get the global EventProcessingMetrics instance.
    
    Returns:
        EventProcessingMetrics instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = EventProcessingMetrics()
    return _metrics_instance


def record_event_processed(
    worker_type: str,
    event_type: str,
    tenant_id: str,
    status: str = "success",
    latency_seconds: Optional[float] = None,
) -> None:
    """Convenience function to record a processed event."""
    get_metrics().record_event_processed(
        worker_type=worker_type,
        event_type=event_type,
        tenant_id=tenant_id,
        status=status,
        latency_seconds=latency_seconds,
    )


def record_event_failure(
    worker_type: str,
    event_type: str,
    tenant_id: str,
    error_type: str = "unknown",
) -> None:
    """Convenience function to record a failed event."""
    get_metrics().record_event_failure(
        worker_type=worker_type,
        event_type=event_type,
        tenant_id=tenant_id,
        error_type=error_type,
    )


def record_retry(
    worker_type: str,
    event_type: str,
    tenant_id: str,
    retry_attempt: int,
) -> None:
    """Convenience function to record a retry."""
    get_metrics().record_retry(
        worker_type=worker_type,
        event_type=event_type,
        tenant_id=tenant_id,
        retry_attempt=retry_attempt,
    )


def update_dlq_size(
    tenant_id: str,
    event_type: str,
    worker_type: str,
    size: int,
) -> None:
    """Convenience function to update DLQ size."""
    get_metrics().update_dlq_size(
        tenant_id=tenant_id,
        event_type=event_type,
        worker_type=worker_type,
        size=size,
    )


def record_dlq(
    worker_type: str,
    event_type: str,
    tenant_id: str,
) -> None:
    """Convenience function to record an event moved to DLQ."""
    get_metrics().record_dlq(
        worker_type=worker_type,
        event_type=event_type,
        tenant_id=tenant_id,
    )


def update_kafka_consumer_lag(
    topic: str,
    group_id: str,
    lag: int,
    tenant_id: Optional[str] = None,
) -> None:
    """Convenience function to update Kafka consumer lag."""
    get_metrics().update_kafka_consumer_lag(
        topic=topic,
        group_id=group_id,
        lag=lag,
        tenant_id=tenant_id,
    )



