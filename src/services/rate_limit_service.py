"""
Rate Limit Service for Phase 10 (P10-15 to P10-17).

Provides rate limiting functionality:
- Check if request is within rate limits
- Increment usage counters
- Get current usage vs limits
- Sliding window rate limiting

Reference: docs/phase10-ops-governance-mvp.md Section 9
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from src.infrastructure.db.models import (
    RateLimitConfig,
    RateLimitUsage,
)

logger = logging.getLogger(__name__)


# Default rate limits if no config exists for tenant
DEFAULT_RATE_LIMITS = {
    "api_requests": {"limit": 1000, "window_seconds": 60},
    "events_ingested": {"limit": 500, "window_seconds": 60},
    "tool_executions": {"limit": 100, "window_seconds": 60},
    "report_generations": {"limit": 10, "window_seconds": 86400},  # 10 per day
}


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""
    allowed: bool
    limit: int
    current: int
    remaining: int
    reset_at: datetime
    retry_after_seconds: Optional[int] = None


@dataclass
class RateLimitStatus:
    """Current rate limit status for a tenant."""
    tenant_id: str
    limit_type: str
    limit: int
    current: int
    remaining: int
    window_seconds: int
    reset_at: datetime
    enabled: bool


class RateLimitService:
    """
    Service for managing rate limits.

    Provides:
    - Rate limit checking
    - Usage tracking
    - Configuration management
    """

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session."""
        self.session = session

    async def check_rate_limit(
        self,
        tenant_id: str,
        limit_type: str,
        increment: int = 1,
    ) -> RateLimitResult:
        """
        Check if a request is within rate limits and increment usage.

        Args:
            tenant_id: Tenant identifier
            limit_type: Type of rate limit to check
            increment: Amount to increment (default 1)

        Returns:
            RateLimitResult with allowed status and limit info
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        # Get rate limit config for this tenant/type
        config = await self._get_config(tenant_id, limit_type)

        if not config:
            # Use defaults
            defaults = DEFAULT_RATE_LIMITS.get(limit_type, {"limit": 100, "window_seconds": 60})
            limit_value = defaults["limit"]
            window_seconds = defaults["window_seconds"]
            enabled = True
        else:
            limit_value = config.limit_value
            window_seconds = config.window_seconds
            enabled = config.enabled

        # If rate limiting is disabled, always allow
        if not enabled:
            return RateLimitResult(
                allowed=True,
                limit=limit_value,
                current=0,
                remaining=limit_value,
                reset_at=datetime.now(timezone.utc) + timedelta(seconds=window_seconds),
            )

        # Calculate current window start
        now = datetime.now(timezone.utc)
        window_start = self._calculate_window_start(now, window_seconds)
        reset_at = window_start + timedelta(seconds=window_seconds)

        # Get or create usage record
        current_count = await self._get_or_create_usage(
            tenant_id, limit_type, window_start
        )

        # Check if within limit
        if current_count + increment > limit_value:
            # Rate limit exceeded
            retry_after = int((reset_at - now).total_seconds())
            return RateLimitResult(
                allowed=False,
                limit=limit_value,
                current=current_count,
                remaining=0,
                reset_at=reset_at,
                retry_after_seconds=max(1, retry_after),
            )

        # Increment usage
        new_count = await self._increment_usage(
            tenant_id, limit_type, window_start, increment
        )

        return RateLimitResult(
            allowed=True,
            limit=limit_value,
            current=new_count,
            remaining=max(0, limit_value - new_count),
            reset_at=reset_at,
        )

    async def get_rate_limit_status(
        self,
        tenant_id: str,
        limit_type: Optional[str] = None,
    ) -> list[RateLimitStatus]:
        """
        Get current rate limit status for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit_type: Optional specific type (all types if None)

        Returns:
            List of RateLimitStatus for each limit type
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        statuses = []
        types_to_check = [limit_type] if limit_type else list(DEFAULT_RATE_LIMITS.keys())

        now = datetime.now(timezone.utc)

        for lt in types_to_check:
            config = await self._get_config(tenant_id, lt)

            if not config:
                defaults = DEFAULT_RATE_LIMITS.get(lt, {"limit": 100, "window_seconds": 60})
                limit_value = defaults["limit"]
                window_seconds = defaults["window_seconds"]
                enabled = True
            else:
                limit_value = config.limit_value
                window_seconds = config.window_seconds
                enabled = config.enabled

            window_start = self._calculate_window_start(now, window_seconds)
            reset_at = window_start + timedelta(seconds=window_seconds)

            current_count = await self._get_usage(tenant_id, lt, window_start)

            statuses.append(RateLimitStatus(
                tenant_id=tenant_id,
                limit_type=lt,
                limit=limit_value,
                current=current_count,
                remaining=max(0, limit_value - current_count),
                window_seconds=window_seconds,
                reset_at=reset_at,
                enabled=enabled,
            ))

        return statuses

    async def get_tenant_config(
        self,
        tenant_id: str,
    ) -> list[RateLimitConfig]:
        """
        Get all rate limit configurations for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            List of RateLimitConfig
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        query = (
            select(RateLimitConfig)
            .where(RateLimitConfig.tenant_id == tenant_id)
            .order_by(RateLimitConfig.limit_type)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_tenant_config(
        self,
        tenant_id: str,
        limit_type: str,
        limit_value: int,
        window_seconds: int = 60,
        enabled: bool = True,
    ) -> RateLimitConfig:
        """
        Update or create rate limit configuration for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit_type: Type of rate limit
            limit_value: Maximum allowed per window
            window_seconds: Time window in seconds
            enabled: Whether this limit is enabled

        Returns:
            Updated or created RateLimitConfig
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        # Try to find existing config
        query = (
            select(RateLimitConfig)
            .where(RateLimitConfig.tenant_id == tenant_id)
            .where(RateLimitConfig.limit_type == limit_type)
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            existing.limit_value = limit_value
            existing.window_seconds = window_seconds
            existing.enabled = enabled
            await self.session.flush()
            await self.session.refresh(existing)
            logger.info(
                f"Updated rate limit config: tenant_id={tenant_id}, "
                f"limit_type={limit_type}, limit_value={limit_value}"
            )
            return existing
        else:
            config = RateLimitConfig(
                tenant_id=tenant_id,
                limit_type=limit_type,
                limit_value=limit_value,
                window_seconds=window_seconds,
                enabled=enabled,
            )
            self.session.add(config)
            await self.session.flush()
            await self.session.refresh(config)
            logger.info(
                f"Created rate limit config: tenant_id={tenant_id}, "
                f"limit_type={limit_type}, limit_value={limit_value}"
            )
            return config

    async def delete_tenant_config(
        self,
        tenant_id: str,
        limit_type: Optional[str] = None,
    ) -> int:
        """
        Delete rate limit configuration for a tenant.

        Args:
            tenant_id: Tenant identifier
            limit_type: Specific type to delete (all types if None)

        Returns:
            Number of configs deleted
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        from sqlalchemy import delete

        stmt = delete(RateLimitConfig).where(RateLimitConfig.tenant_id == tenant_id)
        if limit_type:
            stmt = stmt.where(RateLimitConfig.limit_type == limit_type)

        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted = result.rowcount
        logger.info(f"Deleted {deleted} rate limit configs for tenant {tenant_id}")
        return deleted

    def _calculate_window_start(
        self,
        now: datetime,
        window_seconds: int,
    ) -> datetime:
        """Calculate the start of the current time window."""
        # Round down to nearest window boundary
        epoch = datetime(1970, 1, 1, tzinfo=timezone.utc)
        seconds_since_epoch = int((now - epoch).total_seconds())
        window_start_seconds = (seconds_since_epoch // window_seconds) * window_seconds
        return epoch + timedelta(seconds=window_start_seconds)

    async def _get_config(
        self,
        tenant_id: str,
        limit_type: str,
    ) -> Optional[RateLimitConfig]:
        """Get rate limit config for a tenant/type."""
        query = (
            select(RateLimitConfig)
            .where(RateLimitConfig.tenant_id == tenant_id)
            .where(RateLimitConfig.limit_type == limit_type)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def _get_usage(
        self,
        tenant_id: str,
        limit_type: str,
        window_start: datetime,
    ) -> int:
        """Get current usage for a window."""
        query = (
            select(RateLimitUsage.current_count)
            .where(RateLimitUsage.tenant_id == tenant_id)
            .where(RateLimitUsage.limit_type == limit_type)
            .where(RateLimitUsage.window_start == window_start)
        )
        result = await self.session.execute(query)
        row = result.scalar_one_or_none()
        return row if row is not None else 0

    async def _get_or_create_usage(
        self,
        tenant_id: str,
        limit_type: str,
        window_start: datetime,
    ) -> int:
        """Get or create usage record, returning current count."""
        # Try to get existing
        current = await self._get_usage(tenant_id, limit_type, window_start)
        if current > 0:
            return current

        # Create new record with count 0
        usage = RateLimitUsage(
            tenant_id=tenant_id,
            limit_type=limit_type,
            window_start=window_start,
            current_count=0,
        )
        self.session.add(usage)
        try:
            await self.session.flush()
        except Exception:
            # Another request may have created it - get the count
            await self.session.rollback()
            return await self._get_usage(tenant_id, limit_type, window_start)
        return 0

    async def _increment_usage(
        self,
        tenant_id: str,
        limit_type: str,
        window_start: datetime,
        increment: int,
    ) -> int:
        """Increment usage counter and return new count."""
        stmt = (
            update(RateLimitUsage)
            .where(RateLimitUsage.tenant_id == tenant_id)
            .where(RateLimitUsage.limit_type == limit_type)
            .where(RateLimitUsage.window_start == window_start)
            .values(current_count=RateLimitUsage.current_count + increment)
            .returning(RateLimitUsage.current_count)
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        row = result.fetchone()
        return row[0] if row else increment


# Singleton instance
_rate_limit_service: Optional[RateLimitService] = None


def get_rate_limit_service(session: AsyncSession) -> RateLimitService:
    """Get the rate limit service."""
    return RateLimitService(session)
