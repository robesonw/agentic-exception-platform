"""
Integration tests for per-tenant rate limiting (P9-27).

Tests verify:
- Tenant isolation (one tenant throttled, others unaffected)
- Backpressure event emission
- Event publisher throttling
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.messaging.event_publisher import EventPublisherService
from src.messaging.broker import Broker
from src.operations.rate_limiter import PerTenantRateLimiter, TenantRateLimit


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with event publisher."""

    @pytest.mark.asyncio
    async def test_tenant_isolation_throttling(self):
        """Test that one tenant's throttling doesn't affect others."""
        # Create mock broker
        mock_broker = MagicMock(spec=Broker)
        
        # Create rate limiter with very low limit
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=1.0, burst_size=1)
        )
        
        # Create event publisher with rate limiting enabled
        publisher = EventPublisherService(
            broker=mock_broker,
            enable_rate_limiting=True,
        )
        publisher.rate_limiter = limiter
        
        # Mock event store
        mock_event_store = AsyncMock()
        publisher.event_store = mock_event_store
        
        # Tenant 1: First event should succeed
        event_1 = {
            "event_type": "TestEvent",
            "tenant_id": "TENANT_001",
            "payload": {"test": "data"},
        }
        
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            event_id_1 = await publisher.publish_event("test-topic", event_1)
            assert event_id_1 is not None
        
        # Tenant 1: Second event should be throttled
        with pytest.raises(Exception) as exc_info:
            await publisher.publish_event("test-topic", event_1)
        assert "Rate limit exceeded" in str(exc_info.value)
        
        # Tenant 2: Should still be allowed (isolated from Tenant 1)
        event_2 = {
            "event_type": "TestEvent",
            "tenant_id": "TENANT_002",
            "payload": {"test": "data"},
        }
        
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            event_id_2 = await publisher.publish_event("test-topic", event_2)
            assert event_id_2 is not None  # Tenant 2 not affected by Tenant 1's throttling

    @pytest.mark.asyncio
    async def test_backpressure_event_emission(self):
        """Test that backpressure events are emitted when throttling occurs."""
        # Create mock broker
        mock_broker = MagicMock(spec=Broker)
        
        # Create rate limiter with very low limit
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=1.0, burst_size=1)
        )
        
        # Create event publisher with rate limiting enabled
        publisher = EventPublisherService(
            broker=mock_broker,
            enable_rate_limiting=True,
        )
        publisher.rate_limiter = limiter
        
        # Mock event store
        mock_event_store = AsyncMock()
        publisher.event_store = mock_event_store
        
        tenant_id = "TENANT_001"
        event = {
            "event_type": "TestEvent",
            "tenant_id": tenant_id,
            "payload": {"test": "data"},
        }
        
        # First event succeeds
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            await publisher.publish_event("test-topic", event)
        
        # Second event should trigger backpressure event
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            with pytest.raises(Exception):
                await publisher.publish_event("test-topic", event)
        
        # Verify backpressure event was published
        # Check that broker.publish was called for backpressure event
        publish_calls = mock_broker.publish.call_args_list
        assert len(publish_calls) >= 1
        
        # Check that backpressure event was published to "backpressure" topic
        backpressure_calls = [
            call for call in publish_calls
            if len(call[0]) > 0 and call[0][0] == "backpressure"
        ]
        assert len(backpressure_calls) > 0, "Backpressure event should be published"

    @pytest.mark.asyncio
    async def test_configurable_limits_per_tenant(self):
        """Test that different tenants can have different rate limits."""
        # Create mock broker
        mock_broker = MagicMock(spec=Broker)
        
        # Create rate limiter
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=1.0, burst_size=1)
        )
        
        # Set custom limit for Tenant 1 (higher limit)
        limiter.set_tenant_limit(
            "TENANT_001",
            TenantRateLimit(events_per_second=10.0, burst_size=10),
        )
        
        # Create event publisher
        publisher = EventPublisherService(
            broker=mock_broker,
            enable_rate_limiting=True,
        )
        publisher.rate_limiter = limiter
        
        # Mock event store
        mock_event_store = AsyncMock()
        publisher.event_store = mock_event_store
        
        # Tenant 1: Should be able to publish multiple events (higher limit)
        event_1 = {
            "event_type": "TestEvent",
            "tenant_id": "TENANT_001",
            "payload": {"test": "data"},
        }
        
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            # Publish multiple events for Tenant 1
            for _ in range(5):
                event_id = await publisher.publish_event("test-topic", event_1)
                assert event_id is not None
        
        # Tenant 2: Should be throttled after 1 event (default limit)
        event_2 = {
            "event_type": "TestEvent",
            "tenant_id": "TENANT_002",
            "payload": {"test": "data"},
        }
        
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            # First event succeeds
            await publisher.publish_event("test-topic", event_2)
            
            # Second event should be throttled
            with pytest.raises(Exception) as exc_info:
                await publisher.publish_event("test-topic", event_2)
            assert "Rate limit exceeded" in str(exc_info.value)


