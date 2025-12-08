"""
Unit tests for LLM routing metrics and observability (LR-11).

Tests Prometheus metrics collection for provider selection, fallback events, and routing latency.
"""

import pytest
import time
from unittest.mock import patch

# Try to import prometheus_client for testing
try:
    from prometheus_client import REGISTRY, Counter, Histogram
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    pytest.skip("prometheus_client not available", allow_module_level=True)

from src.llm.metrics import (
    LLM_FALLBACK_EVENTS,
    LLM_PROVIDER_SELECTION,
    LLM_ROUTING_LATENCY,
    record_fallback_event,
    record_provider_selection,
    routing_latency_timer,
)


@pytest.fixture(autouse=True)
def reset_metrics():
    """Reset Prometheus metrics before each test."""
    # Clear all metrics from registry
    for collector in list(REGISTRY._collector_to_names.keys()):
        REGISTRY.unregister(collector)
    
    # Re-register our metrics
    from src.llm.metrics import (
        LLM_FALLBACK_EVENTS,
        LLM_PROVIDER_SELECTION,
        LLM_ROUTING_LATENCY,
    )
    REGISTRY.register(LLM_PROVIDER_SELECTION)
    REGISTRY.register(LLM_FALLBACK_EVENTS)
    REGISTRY.register(LLM_ROUTING_LATENCY)


class TestProviderSelectionMetrics:
    """Test cases for provider selection metrics."""
    
    def test_record_provider_selection(self):
        """Test that record_provider_selection increments counter with correct labels."""
        record_provider_selection(
            tenant_id="TENANT_001",
            domain="Finance",
            provider="openrouter",
            model="gpt-4.1-mini"
        )
        
        # Get metric sample
        samples = list(LLM_PROVIDER_SELECTION.collect()[0].samples)
        
        # Find the sample with matching labels
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
            and s.labels.get("provider") == "openrouter"
            and s.labels.get("model") == "gpt-4.1-mini"
        ]
        
        assert len(matching_samples) == 1
        assert matching_samples[0].value == 1.0
    
    def test_record_provider_selection_multiple_times(self):
        """Test that multiple calls increment the counter."""
        record_provider_selection(
            tenant_id="TENANT_001",
            domain="Finance",
            provider="openrouter",
            model="gpt-4.1-mini"
        )
        record_provider_selection(
            tenant_id="TENANT_001",
            domain="Finance",
            provider="openrouter",
            model="gpt-4.1-mini"
        )
        
        # Get metric sample
        samples = list(LLM_PROVIDER_SELECTION.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
            and s.labels.get("provider") == "openrouter"
            and s.labels.get("model") == "gpt-4.1-mini"
        ]
        
        assert len(matching_samples) == 1
        assert matching_samples[0].value == 2.0
    
    def test_record_provider_selection_with_none_values(self):
        """Test that None values are normalized to 'unknown'."""
        record_provider_selection(
            tenant_id=None,
            domain=None,
            provider="dummy",
            model="dummy-model"
        )
        
        # Get metric sample
        samples = list(LLM_PROVIDER_SELECTION.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "unknown"
            and s.labels.get("domain") == "unknown"
            and s.labels.get("provider") == "dummy"
            and s.labels.get("model") == "dummy-model"
        ]
        
        assert len(matching_samples) == 1
        assert matching_samples[0].value == 1.0
    
    def test_record_provider_selection_different_labels(self):
        """Test that different label combinations create separate metrics."""
        record_provider_selection(
            tenant_id="TENANT_001",
            domain="Finance",
            provider="openrouter",
            model="gpt-4.1-mini"
        )
        record_provider_selection(
            tenant_id="TENANT_002",
            domain="Healthcare",
            provider="openai",
            model="gpt-4"
        )
        
        # Get metric samples
        samples = list(LLM_PROVIDER_SELECTION.collect()[0].samples)
        
        # Check first sample
        sample1 = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
        ]
        assert len(sample1) == 1
        assert sample1[0].value == 1.0
        
        # Check second sample
        sample2 = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_002"
            and s.labels.get("domain") == "Healthcare"
        ]
        assert len(sample2) == 1
        assert sample2[0].value == 1.0


class TestFallbackEventMetrics:
    """Test cases for fallback event metrics."""
    
    def test_record_fallback_event(self):
        """Test that record_fallback_event increments counter with correct labels."""
        record_fallback_event(
            tenant_id="TENANT_001",
            domain="Finance",
            from_provider="openrouter",
            to_provider="openai"
        )
        
        # Get metric sample
        samples = list(LLM_FALLBACK_EVENTS.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
            and s.labels.get("from_provider") == "openrouter"
            and s.labels.get("to_provider") == "openai"
        ]
        
        assert len(matching_samples) == 1
        assert matching_samples[0].value == 1.0
    
    def test_record_fallback_event_multiple_times(self):
        """Test that multiple fallback events increment the counter."""
        record_fallback_event(
            tenant_id="TENANT_001",
            domain="Finance",
            from_provider="openrouter",
            to_provider="openai"
        )
        record_fallback_event(
            tenant_id="TENANT_001",
            domain="Finance",
            from_provider="openrouter",
            to_provider="openai"
        )
        
        # Get metric sample
        samples = list(LLM_FALLBACK_EVENTS.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
            and s.labels.get("from_provider") == "openrouter"
            and s.labels.get("to_provider") == "openai"
        ]
        
        assert len(matching_samples) == 1
        assert matching_samples[0].value == 2.0
    
    def test_record_fallback_event_with_none_values(self):
        """Test that None values are normalized to 'unknown'."""
        record_fallback_event(
            tenant_id=None,
            domain=None,
            from_provider="openrouter",
            to_provider="dummy"
        )
        
        # Get metric sample
        samples = list(LLM_FALLBACK_EVENTS.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "unknown"
            and s.labels.get("domain") == "unknown"
            and s.labels.get("from_provider") == "openrouter"
            and s.labels.get("to_provider") == "dummy"
        ]
        
        assert len(matching_samples) == 1
        assert matching_samples[0].value == 1.0


class TestRoutingLatencyMetrics:
    """Test cases for routing latency metrics."""
    
    def test_routing_latency_timer(self):
        """Test that routing_latency_timer records latency."""
        with routing_latency_timer(tenant_id="TENANT_001", domain="Finance"):
            time.sleep(0.01)  # Sleep for 10ms
        
        # Get metric sample
        samples = list(LLM_ROUTING_LATENCY.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
            and s.name.endswith("_bucket")  # Histogram buckets
        ]
        
        # Should have at least one bucket sample
        assert len(matching_samples) > 0
    
    def test_routing_latency_timer_with_none_values(self):
        """Test that None values are normalized to 'unknown'."""
        with routing_latency_timer(tenant_id=None, domain=None):
            time.sleep(0.01)
        
        # Get metric sample
        samples = list(LLM_ROUTING_LATENCY.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "unknown"
            and s.labels.get("domain") == "unknown"
        ]
        
        # Should have at least one sample
        assert len(matching_samples) > 0
    
    def test_routing_latency_timer_exception_handling(self):
        """Test that routing_latency_timer still records latency even if exception occurs."""
        try:
            with routing_latency_timer(tenant_id="TENANT_001", domain="Finance"):
                time.sleep(0.01)
                raise ValueError("Test exception")
        except ValueError:
            pass
        
        # Get metric sample - should still be recorded
        samples = list(LLM_ROUTING_LATENCY.collect()[0].samples)
        matching_samples = [
            s for s in samples
            if s.labels.get("tenant_id") == "TENANT_001"
            and s.labels.get("domain") == "Finance"
        ]
        
        # Should have at least one sample
        assert len(matching_samples) > 0


class TestMetricsWithoutPrometheus:
    """Test that metrics functions work gracefully when Prometheus is not available."""
    
    @patch("src.llm.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_provider_selection_without_prometheus(self):
        """Test that record_provider_selection doesn't fail when Prometheus is unavailable."""
        # Should not raise an exception
        record_provider_selection(
            tenant_id="TENANT_001",
            domain="Finance",
            provider="openrouter",
            model="gpt-4.1-mini"
        )
    
    @patch("src.llm.metrics.PROMETHEUS_AVAILABLE", False)
    def test_record_fallback_event_without_prometheus(self):
        """Test that record_fallback_event doesn't fail when Prometheus is unavailable."""
        # Should not raise an exception
        record_fallback_event(
            tenant_id="TENANT_001",
            domain="Finance",
            from_provider="openrouter",
            to_provider="openai"
        )
    
    @patch("src.llm.metrics.PROMETHEUS_AVAILABLE", False)
    def test_routing_latency_timer_without_prometheus(self):
        """Test that routing_latency_timer doesn't fail when Prometheus is unavailable."""
        # Should not raise an exception
        with routing_latency_timer(tenant_id="TENANT_001", domain="Finance"):
            time.sleep(0.01)

