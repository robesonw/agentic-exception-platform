"""
Usage Metering Service for Phase 10 (P10-18 to P10-20).

Provides usage metering functionality:
- Record usage metrics
- Get usage summaries
- Get detailed usage by resource
- Export usage for billing

Reference: docs/phase10-ops-governance-mvp.md Section 10
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import UsageMetric

logger = logging.getLogger(__name__)


@dataclass
class UsageSummary:
    """Summary of usage for a tenant."""
    tenant_id: str
    period: str  # day, week, month
    period_start: datetime
    period_end: datetime
    totals: dict[str, int]  # metric_type -> total count
    by_resource: dict[str, dict[str, int]]  # metric_type -> resource_id -> count


@dataclass
class UsageDetail:
    """Detailed usage record."""
    metric_type: str
    resource_id: Optional[str]
    period_start: datetime
    period_end: datetime
    count: int
    bytes_value: Optional[int]


@dataclass
class UsageExport:
    """Usage export for billing."""
    tenant_id: str
    period: str
    period_start: datetime
    period_end: datetime
    metrics: list[dict]
    totals: dict[str, int]
    generated_at: datetime


class UsageMeteringService:
    """
    Service for tracking and reporting usage metrics.

    Provides:
    - Recording usage events
    - Getting usage summaries
    - Detailed usage reports
    - Export for billing
    """

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session."""
        self.session = session

    async def record_usage(
        self,
        tenant_id: str,
        metric_type: str,
        count: int = 1,
        resource_id: Optional[str] = None,
        bytes_value: Optional[int] = None,
        timestamp: Optional[datetime] = None,
    ) -> UsageMetric:
        """
        Record a usage metric.

        Args:
            tenant_id: Tenant identifier
            metric_type: Type of metric (api_calls, exceptions, etc.)
            count: Count to add (default 1)
            resource_id: Optional resource identifier
            bytes_value: Optional byte count for storage metrics
            timestamp: Optional timestamp (defaults to now)

        Returns:
            Created or updated UsageMetric
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        # Calculate period boundaries (minute granularity)
        period_start = timestamp.replace(second=0, microsecond=0)
        period_end = period_start + timedelta(minutes=1)

        # Try to find existing record for this period
        query = (
            select(UsageMetric)
            .where(UsageMetric.tenant_id == tenant_id)
            .where(UsageMetric.metric_type == metric_type)
            .where(UsageMetric.period_start == period_start)
            .where(UsageMetric.period_type == "minute")
        )
        if resource_id:
            query = query.where(UsageMetric.resource_id == resource_id)
        else:
            query = query.where(UsageMetric.resource_id.is_(None))

        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()

        if existing:
            # Update existing record
            existing.count += count
            if bytes_value:
                existing.bytes_value = (existing.bytes_value or 0) + bytes_value
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        else:
            # Create new record
            metric = UsageMetric(
                tenant_id=tenant_id,
                metric_type=metric_type,
                resource_id=resource_id,
                period_start=period_start,
                period_end=period_end,
                period_type="minute",
                count=count,
                bytes_value=bytes_value,
            )
            self.session.add(metric)
            await self.session.flush()
            await self.session.refresh(metric)
            return metric

    async def get_usage_summary(
        self,
        tenant_id: str,
        period: str = "day",
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> UsageSummary:
        """
        Get usage summary for a tenant.

        Args:
            tenant_id: Tenant identifier
            period: Summary period (day, week, month)
            from_date: Start date (defaults based on period)
            to_date: End date (defaults to now)

        Returns:
            UsageSummary with totals and breakdown
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        now = datetime.now(timezone.utc)
        to_date = to_date or now

        # Calculate from_date based on period
        if from_date is None:
            if period == "day":
                from_date = to_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                from_date = to_date - timedelta(days=7)
                from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "month":
                from_date = to_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                from_date = to_date - timedelta(days=1)

        # Get totals by metric type
        totals_query = (
            select(
                UsageMetric.metric_type,
                func.sum(UsageMetric.count).label("total"),
            )
            .where(UsageMetric.tenant_id == tenant_id)
            .where(UsageMetric.period_start >= from_date)
            .where(UsageMetric.period_end <= to_date)
            .group_by(UsageMetric.metric_type)
        )
        totals_result = await self.session.execute(totals_query)
        totals = {row.metric_type: int(row.total) for row in totals_result.fetchall()}

        # Get breakdown by resource
        resource_query = (
            select(
                UsageMetric.metric_type,
                UsageMetric.resource_id,
                func.sum(UsageMetric.count).label("total"),
            )
            .where(UsageMetric.tenant_id == tenant_id)
            .where(UsageMetric.period_start >= from_date)
            .where(UsageMetric.period_end <= to_date)
            .where(UsageMetric.resource_id.isnot(None))
            .group_by(UsageMetric.metric_type, UsageMetric.resource_id)
        )
        resource_result = await self.session.execute(resource_query)
        by_resource: dict[str, dict[str, int]] = {}
        for row in resource_result.fetchall():
            if row.metric_type not in by_resource:
                by_resource[row.metric_type] = {}
            by_resource[row.metric_type][row.resource_id] = int(row.total)

        return UsageSummary(
            tenant_id=tenant_id,
            period=period,
            period_start=from_date,
            period_end=to_date,
            totals=totals,
            by_resource=by_resource,
        )

    async def get_usage_details(
        self,
        tenant_id: str,
        metric_type: str,
        from_date: datetime,
        to_date: datetime,
        resource_id: Optional[str] = None,
    ) -> list[UsageDetail]:
        """
        Get detailed usage records.

        Args:
            tenant_id: Tenant identifier
            metric_type: Type of metric
            from_date: Start date
            to_date: End date
            resource_id: Optional filter by resource

        Returns:
            List of UsageDetail records
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        query = (
            select(UsageMetric)
            .where(UsageMetric.tenant_id == tenant_id)
            .where(UsageMetric.metric_type == metric_type)
            .where(UsageMetric.period_start >= from_date)
            .where(UsageMetric.period_end <= to_date)
            .order_by(UsageMetric.period_start)
        )

        if resource_id:
            query = query.where(UsageMetric.resource_id == resource_id)

        result = await self.session.execute(query)
        metrics = result.scalars().all()

        return [
            UsageDetail(
                metric_type=m.metric_type,
                resource_id=m.resource_id,
                period_start=m.period_start,
                period_end=m.period_end,
                count=m.count,
                bytes_value=m.bytes_value,
            )
            for m in metrics
        ]

    async def export_usage(
        self,
        tenant_id: str,
        period: str = "month",
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
    ) -> UsageExport:
        """
        Export usage for billing.

        Args:
            tenant_id: Tenant identifier
            period: Export period (day, week, month)
            from_date: Start date
            to_date: End date

        Returns:
            UsageExport with detailed breakdown
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        now = datetime.now(timezone.utc)
        to_date = to_date or now

        # Calculate from_date based on period
        if from_date is None:
            if period == "day":
                from_date = to_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                from_date = to_date - timedelta(days=7)
                from_date = from_date.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "month":
                from_date = to_date.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            else:
                from_date = to_date - timedelta(days=1)

        # Get all metrics for the period grouped by type and resource
        query = (
            select(
                UsageMetric.metric_type,
                UsageMetric.resource_id,
                func.sum(UsageMetric.count).label("total_count"),
                func.sum(UsageMetric.bytes_value).label("total_bytes"),
            )
            .where(UsageMetric.tenant_id == tenant_id)
            .where(UsageMetric.period_start >= from_date)
            .where(UsageMetric.period_end <= to_date)
            .group_by(UsageMetric.metric_type, UsageMetric.resource_id)
            .order_by(UsageMetric.metric_type, UsageMetric.resource_id)
        )

        result = await self.session.execute(query)
        rows = result.fetchall()

        metrics = []
        totals: dict[str, int] = {}

        for row in rows:
            metric_type = row.metric_type
            resource_id = row.resource_id
            count = int(row.total_count) if row.total_count else 0
            bytes_val = int(row.total_bytes) if row.total_bytes else None

            metrics.append({
                "metric_type": metric_type,
                "resource_id": resource_id,
                "count": count,
                "bytes_value": bytes_val,
            })

            # Aggregate totals
            if metric_type not in totals:
                totals[metric_type] = 0
            totals[metric_type] += count

        return UsageExport(
            tenant_id=tenant_id,
            period=period,
            period_start=from_date,
            period_end=to_date,
            metrics=metrics,
            totals=totals,
            generated_at=now,
        )

    async def rollup_metrics(
        self,
        from_period_type: str = "minute",
        to_period_type: str = "hour",
        older_than: Optional[datetime] = None,
    ) -> int:
        """
        Roll up metrics from one period type to another.

        Args:
            from_period_type: Source period type (e.g., "minute")
            to_period_type: Target period type (e.g., "hour")
            older_than: Only roll up records older than this

        Returns:
            Number of records rolled up
        """
        # This is a placeholder for a more complex rollup implementation
        # In production, this would aggregate minute-level data into hourly/daily
        logger.info(
            f"Rolling up metrics from {from_period_type} to {to_period_type}"
        )
        return 0


# Singleton instance
_usage_metering_service: Optional[UsageMeteringService] = None


def get_usage_metering_service(session: AsyncSession) -> UsageMeteringService:
    """Get the usage metering service."""
    return UsageMeteringService(session)
