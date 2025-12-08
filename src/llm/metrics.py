"""
LLM Routing Metrics and Observability for Phase 5.

Provides Prometheus metrics for tracking:
- Provider selection per domain/tenant
- Model selection
- Fallback events
- Routing decision latency

Reference: docs/phase5-llm-routing.md Section 2 (Design Principles)
"""

import contextlib
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import Prometheus client, but make it optional
try:
    from prometheus_client import Counter, Histogram
    
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning(
        "prometheus_client not available. LLM routing metrics will be disabled. "
        "Install with: pip install prometheus-client"
    )
    
    # Create dummy classes for when Prometheus is not available
    class Counter:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def inc(self, value=1):
            pass
    
    class Histogram:
        def __init__(self, *args, **kwargs):
            pass
        def labels(self, **kwargs):
            return self
        def observe(self, value):
            pass
        @contextlib.contextmanager
        def time(self):
            yield


if PROMETHEUS_AVAILABLE:
    # LLM Provider Selection Counter
    # Tracks which provider/model combinations are selected per tenant/domain
    LLM_PROVIDER_SELECTION = Counter(
        "llm_provider_selection_total",
        "Count of LLM provider selections",
        ["tenant_id", "domain", "provider", "model"],
    )
    
    # LLM Fallback Events Counter
    # Tracks when fallback occurs from one provider to another
    LLM_FALLBACK_EVENTS = Counter(
        "llm_fallback_events_total",
        "Count of LLM fallback events",
        ["tenant_id", "domain", "from_provider", "to_provider"],
    )
    
    # LLM Routing Decision Latency Histogram
    # Tracks how long it takes to resolve provider + model selection
    LLM_ROUTING_LATENCY = Histogram(
        "llm_routing_decision_seconds",
        "Latency for resolving LLM provider + model",
        ["tenant_id", "domain"],
        buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    )
else:
    # Dummy metrics when Prometheus is not available
    LLM_PROVIDER_SELECTION = Counter()
    LLM_FALLBACK_EVENTS = Counter()
    LLM_ROUTING_LATENCY = Histogram()


def record_provider_selection(
    tenant_id: Optional[str],
    domain: Optional[str],
    provider: str,
    model: str,
) -> None:
    """
    Record a provider selection event.
    
    Increments the LLM_PROVIDER_SELECTION counter with the given labels.
    
    Args:
        tenant_id: Optional tenant ID (use "unknown" if None)
        domain: Optional domain name (use "unknown" if None)
        provider: Provider name (e.g., "openrouter", "openai", "dummy")
        model: Model identifier (e.g., "gpt-4.1-mini", "gpt-4")
    
    Example:
        record_provider_selection(
            tenant_id="TENANT_001",
            domain="Finance",
            provider="openrouter",
            model="gpt-4.1-mini"
        )
    """
    if not PROMETHEUS_AVAILABLE:
        return
    
    # Normalize None values to "unknown" for Prometheus labels
    tenant_label = tenant_id or "unknown"
    domain_label = domain or "unknown"
    
    # Normalize provider and model (lowercase, strip)
    provider_label = provider.lower().strip() if provider else "unknown"
    model_label = model.lower().strip() if model else "unknown"
    
    try:
        LLM_PROVIDER_SELECTION.labels(
            tenant_id=tenant_label,
            domain=domain_label,
            provider=provider_label,
            model=model_label,
        ).inc()
        
        logger.debug(
            f"Recorded provider selection: tenant_id={tenant_label}, "
            f"domain={domain_label}, provider={provider_label}, model={model_label}"
        )
    except Exception as e:
        # Don't fail if metrics recording fails
        logger.warning(f"Failed to record provider selection metric: {e}")


def record_fallback_event(
    tenant_id: Optional[str],
    domain: Optional[str],
    from_provider: str,
    to_provider: str,
) -> None:
    """
    Record a fallback event (provider A failed, provider B attempted).
    
    Increments the LLM_FALLBACK_EVENTS counter with the given labels.
    
    Args:
        tenant_id: Optional tenant ID (use "unknown" if None)
        domain: Optional domain name (use "unknown" if None)
        from_provider: Provider that failed (e.g., "openrouter")
        to_provider: Provider being attempted next (e.g., "openai")
    
    Example:
        record_fallback_event(
            tenant_id="TENANT_001",
            domain="Finance",
            from_provider="openrouter",
            to_provider="openai"
        )
    """
    if not PROMETHEUS_AVAILABLE:
        return
    
    # Normalize None values to "unknown" for Prometheus labels
    tenant_label = tenant_id or "unknown"
    domain_label = domain or "unknown"
    
    # Normalize provider names (lowercase, strip)
    from_provider_label = from_provider.lower().strip() if from_provider else "unknown"
    to_provider_label = to_provider.lower().strip() if to_provider else "unknown"
    
    try:
        LLM_FALLBACK_EVENTS.labels(
            tenant_id=tenant_label,
            domain=domain_label,
            from_provider=from_provider_label,
            to_provider=to_provider_label,
        ).inc()
        
        logger.debug(
            f"Recorded fallback event: tenant_id={tenant_label}, "
            f"domain={domain_label}, from_provider={from_provider_label}, "
            f"to_provider={to_provider_label}"
        )
    except Exception as e:
        # Don't fail if metrics recording fails
        logger.warning(f"Failed to record fallback event metric: {e}")


@contextlib.contextmanager
def routing_latency_timer(
    tenant_id: Optional[str],
    domain: Optional[str],
):
    """
    Context manager for measuring routing decision latency.
    
    Measures the time taken to resolve provider + model selection.
    
    Args:
        tenant_id: Optional tenant ID (use "unknown" if None)
        domain: Optional domain name (use "unknown" if None)
    
    Returns:
        Context manager that records latency when exited
    
    Example:
        with routing_latency_timer(tenant_id="TENANT_001", domain="Finance"):
            # Routing decision logic here
            provider = resolve_provider(...)
    """
    if not PROMETHEUS_AVAILABLE:
        yield
        return
    
    # Normalize None values to "unknown" for Prometheus labels
    tenant_label = tenant_id or "unknown"
    domain_label = domain or "unknown"
    
    start_time = time.time()
    
    try:
        yield
    finally:
        elapsed = time.time() - start_time
        
        try:
            LLM_ROUTING_LATENCY.labels(
                tenant_id=tenant_label,
                domain=domain_label,
            ).observe(elapsed)
            
            logger.debug(
                f"Recorded routing latency: tenant_id={tenant_label}, "
                f"domain={domain_label}, latency={elapsed:.4f}s"
            )
        except Exception as e:
            # Don't fail if metrics recording fails
            logger.warning(f"Failed to record routing latency metric: {e}")

