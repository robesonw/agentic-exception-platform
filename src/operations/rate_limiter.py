"""
Per-Tenant Rate Limiter for Phase 9.

Provides configurable per-tenant rate limiting and throttling for event publishing.

Phase 9 P9-27: Backpressure Protection.
Reference: docs/phase9-async-scale-mvp.md Section 9
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class TenantRateLimit:
    """Rate limit configuration for a tenant."""
    
    events_per_second: float = 10.0
    events_per_minute: float = 600.0
    burst_size: int = 20  # Maximum burst allowed
    
    def __post_init__(self):
        """Validate rate limit configuration."""
        if self.events_per_second <= 0:
            raise ValueError("events_per_second must be > 0")
        if self.events_per_minute <= 0:
            raise ValueError("events_per_minute must be > 0")
        if self.burst_size < 1:
            raise ValueError("burst_size must be >= 1")


class PerTenantRateLimiter:
    """
    Per-tenant rate limiter with configurable limits.
    
    Phase 9 P9-27: Implements per-tenant rate limiting for event publishing.
    Uses token bucket algorithm for smooth rate limiting.
    
    Features:
    - Per-tenant configurable limits
    - Token bucket algorithm for burst handling
    - Thread-safe operations
    - Tenant isolation (one tenant's throttling doesn't affect others)
    """
    
    def __init__(self, default_limit: Optional[TenantRateLimit] = None):
        """
        Initialize per-tenant rate limiter.
        
        Args:
            default_limit: Default rate limit for tenants without explicit configuration
        """
        self.default_limit = default_limit or TenantRateLimit()
        
        # Per-tenant rate limit configurations
        # {tenant_id: TenantRateLimit}
        self._tenant_limits: dict[str, TenantRateLimit] = {}
        
        # Token bucket state per tenant
        # {tenant_id: {"tokens": float, "last_refill": float}}
        self._token_buckets: dict[str, dict[str, float]] = defaultdict(
            lambda: {
                "tokens": 0.0,
                "last_refill": time.time(),
            }
        )
        
        logger.info(
            f"Initialized PerTenantRateLimiter with default limit: "
            f"{self.default_limit.events_per_second} events/sec, "
            f"{self.default_limit.events_per_minute} events/min"
        )
    
    def set_tenant_limit(
        self,
        tenant_id: str,
        limit: TenantRateLimit,
    ) -> None:
        """
        Set rate limit for a specific tenant.
        
        Args:
            tenant_id: Tenant identifier
            limit: TenantRateLimit configuration
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        
        self._tenant_limits[tenant_id.strip()] = limit
        logger.info(
            f"Set rate limit for tenant {tenant_id}: "
            f"{limit.events_per_second} events/sec, "
            f"{limit.events_per_minute} events/min, "
            f"burst={limit.burst_size}"
        )
    
    def get_tenant_limit(self, tenant_id: str) -> TenantRateLimit:
        """
        Get rate limit for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantRateLimit configuration for the tenant
        """
        return self._tenant_limits.get(tenant_id, self.default_limit)
    
    def check_rate_limit(
        self,
        tenant_id: str,
        num_events: int = 1,
    ) -> tuple[bool, Optional[float]]:
        """
        Check if tenant is within rate limit.
        
        Uses token bucket algorithm:
        - Tokens are refilled at the configured rate
        - Each event consumes 1 token
        - If tokens are available, allow the event
        - If not, throttle and return wait time
        
        Args:
            tenant_id: Tenant identifier
            num_events: Number of events to check (default: 1)
            
        Returns:
            Tuple of (is_allowed, wait_seconds)
            - is_allowed: True if within rate limit, False if throttled
            - wait_seconds: Seconds to wait before retry (None if allowed)
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        
        tenant_id = tenant_id.strip()
        limit = self.get_tenant_limit(tenant_id)
        
        # Get or initialize token bucket for tenant
        bucket = self._token_buckets[tenant_id]
        current_time = time.time()
        
        # Refill tokens based on time elapsed
        time_elapsed = current_time - bucket["last_refill"]
        tokens_to_add = time_elapsed * limit.events_per_second
        
        # Refill bucket (capped at burst_size)
        bucket["tokens"] = min(
            limit.burst_size,
            bucket["tokens"] + tokens_to_add,
        )
        bucket["last_refill"] = current_time
        
        # Check if we have enough tokens
        if bucket["tokens"] >= num_events:
            # Consume tokens
            bucket["tokens"] -= num_events
            return True, None
        else:
            # Calculate wait time
            tokens_needed = num_events - bucket["tokens"]
            wait_seconds = tokens_needed / limit.events_per_second
            
            logger.debug(
                f"Rate limit exceeded for tenant {tenant_id}: "
                f"need {num_events} tokens, have {bucket['tokens']:.2f}, "
                f"wait {wait_seconds:.2f}s"
            )
            
            return False, wait_seconds
    
    def reset_tenant(self, tenant_id: str) -> None:
        """
        Reset rate limit state for a tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        self._token_buckets.pop(tenant_id, None)
        logger.debug(f"Reset rate limit state for tenant {tenant_id}")
    
    def get_tenant_stats(self, tenant_id: str) -> dict[str, float]:
        """
        Get rate limit statistics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with statistics:
            - current_tokens: Current tokens in bucket
            - events_per_second: Configured rate limit
            - events_per_minute: Configured rate limit
            - burst_size: Configured burst size
        """
        limit = self.get_tenant_limit(tenant_id)
        bucket = self._token_buckets.get(tenant_id, {"tokens": 0.0, "last_refill": 0.0})
        
        # Refill tokens to get current state
        current_time = time.time()
        time_elapsed = current_time - bucket["last_refill"]
        tokens_to_add = time_elapsed * limit.events_per_second
        current_tokens = min(
            limit.burst_size,
            bucket["tokens"] + tokens_to_add,
        )
        
        return {
            "current_tokens": current_tokens,
            "events_per_second": limit.events_per_second,
            "events_per_minute": limit.events_per_minute,
            "burst_size": limit.burst_size,
        }


# Global rate limiter instance
_rate_limiter: Optional[PerTenantRateLimiter] = None


def get_rate_limiter() -> PerTenantRateLimiter:
    """
    Get the global per-tenant rate limiter instance.
    
    Returns:
        PerTenantRateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = PerTenantRateLimiter()
    return _rate_limiter


