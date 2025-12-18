"""
Tests for per-tenant rate limiter (P9-27).

Tests verify:
- Per-tenant rate limiting
- Tenant isolation (one tenant's throttling doesn't affect others)
- Configurable limits per tenant
- Backpressure event emission
"""

import pytest
import time
from unittest.mock import AsyncMock, MagicMock, patch

from src.operations.rate_limiter import (
    PerTenantRateLimiter,
    TenantRateLimit,
    get_rate_limiter,
)


class TestTenantRateLimit:
    """Tests for TenantRateLimit configuration."""

    def test_valid_configuration(self):
        """Test valid rate limit configuration."""
        limit = TenantRateLimit(
            events_per_second=10.0,
            events_per_minute=600.0,
            burst_size=20,
        )
        assert limit.events_per_second == 10.0
        assert limit.events_per_minute == 600.0
        assert limit.burst_size == 20

    def test_invalid_events_per_second(self):
        """Test that invalid events_per_second raises ValueError."""
        with pytest.raises(ValueError, match="events_per_second must be > 0"):
            TenantRateLimit(events_per_second=0)

    def test_invalid_events_per_minute(self):
        """Test that invalid events_per_minute raises ValueError."""
        with pytest.raises(ValueError, match="events_per_minute must be > 0"):
            TenantRateLimit(events_per_minute=0)

    def test_invalid_burst_size(self):
        """Test that invalid burst_size raises ValueError."""
        with pytest.raises(ValueError, match="burst_size must be >= 1"):
            TenantRateLimit(burst_size=0)


class TestPerTenantRateLimiter:
    """Tests for PerTenantRateLimiter."""

    def test_default_limit(self):
        """Test that default limit is used when tenant has no explicit limit."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=5.0)
        )
        limit = limiter.get_tenant_limit("TENANT_001")
        assert limit.events_per_second == 5.0

    def test_set_tenant_limit(self):
        """Test setting rate limit for a specific tenant."""
        limiter = PerTenantRateLimiter()
        custom_limit = TenantRateLimit(
            events_per_second=20.0,
            events_per_minute=1200.0,
            burst_size=50,
        )
        limiter.set_tenant_limit("TENANT_001", custom_limit)
        
        limit = limiter.get_tenant_limit("TENANT_001")
        assert limit.events_per_second == 20.0
        assert limit.events_per_minute == 1200.0
        assert limit.burst_size == 50

    def test_check_rate_limit_allowed(self):
        """Test that events within rate limit are allowed."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=10.0, burst_size=20)
        )
        
        # First event should be allowed
        is_allowed, wait_seconds = limiter.check_rate_limit("TENANT_001")
        assert is_allowed is True
        assert wait_seconds is None

    def test_check_rate_limit_throttled(self):
        """Test that events exceeding rate limit are throttled."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=1.0, burst_size=2)
        )
        
        # Consume burst tokens
        limiter.check_rate_limit("TENANT_001")
        limiter.check_rate_limit("TENANT_001")
        
        # Next event should be throttled
        is_allowed, wait_seconds = limiter.check_rate_limit("TENANT_001")
        assert is_allowed is False
        assert wait_seconds is not None
        assert wait_seconds > 0

    def test_tenant_isolation(self):
        """Test that one tenant's throttling doesn't affect others."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=1.0, burst_size=1)
        )
        
        # Tenant 1 exhausts its limit
        limiter.check_rate_limit("TENANT_001")
        is_allowed_1, _ = limiter.check_rate_limit("TENANT_001")
        assert is_allowed_1 is False  # Throttled
        
        # Tenant 2 should still be allowed (isolated)
        is_allowed_2, _ = limiter.check_rate_limit("TENANT_002")
        assert is_allowed_2 is True  # Not throttled

    def test_token_refill(self):
        """Test that tokens are refilled over time."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=10.0, burst_size=10)
        )
        
        # Consume all tokens
        for _ in range(10):
            limiter.check_rate_limit("TENANT_001")
        
        # Should be throttled
        is_allowed, _ = limiter.check_rate_limit("TENANT_001")
        assert is_allowed is False
        
        # Wait for token refill (0.2 seconds should refill 2 tokens at 10/sec)
        time.sleep(0.2)
        
        # Should be allowed again (at least 1 token refilled)
        is_allowed, _ = limiter.check_rate_limit("TENANT_001")
        assert is_allowed is True

    def test_reset_tenant(self):
        """Test resetting rate limit state for a tenant."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=1.0, burst_size=1)
        )
        
        # Exhaust limit
        limiter.check_rate_limit("TENANT_001")
        is_allowed, _ = limiter.check_rate_limit("TENANT_001")
        assert is_allowed is False
        
        # Reset tenant
        limiter.reset_tenant("TENANT_001")
        
        # Should be allowed again
        is_allowed, _ = limiter.check_rate_limit("TENANT_001")
        assert is_allowed is True

    def test_get_tenant_stats(self):
        """Test getting rate limit statistics for a tenant."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(
                events_per_second=10.0,
                events_per_minute=600.0,
                burst_size=20,
            )
        )
        
        stats = limiter.get_tenant_stats("TENANT_001")
        assert "current_tokens" in stats
        assert "events_per_second" in stats
        assert "events_per_minute" in stats
        assert "burst_size" in stats
        assert stats["events_per_second"] == 10.0
        assert stats["events_per_minute"] == 600.0
        assert stats["burst_size"] == 20

    def test_multiple_events_check(self):
        """Test checking rate limit for multiple events at once."""
        limiter = PerTenantRateLimiter(
            default_limit=TenantRateLimit(events_per_second=10.0, burst_size=20)
        )
        
        # Check for 5 events
        is_allowed, wait_seconds = limiter.check_rate_limit("TENANT_001", num_events=5)
        assert is_allowed is True
        assert wait_seconds is None
        
        # Check stats - should have consumed 5 tokens
        stats = limiter.get_tenant_stats("TENANT_001")
        assert stats["current_tokens"] <= 15  # 20 - 5 = 15


class TestRateLimiterIntegration:
    """Integration tests for rate limiter with event publisher."""

    @pytest.mark.asyncio
    async def test_event_publisher_rate_limiting(self):
        """Test that event publisher respects rate limits."""
        from src.messaging.event_publisher import EventPublisherService
        from src.messaging.broker import Broker
        
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
        
        # First event should succeed
        with patch("src.messaging.event_publisher.get_rate_limiter", return_value=limiter):
            event_id_1 = await publisher.publish_event("test-topic", event)
            assert event_id_1 is not None
        
        # Second event should be throttled
        with pytest.raises(Exception) as exc_info:
            await publisher.publish_event("test-topic", event)
        assert "Rate limit exceeded" in str(exc_info.value)


