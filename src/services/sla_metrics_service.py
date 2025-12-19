"""
SLA Metrics Service for Phase 10.

Computes SLA compliance rates, breach counts, at-risk exceptions,
and resolution time metrics by tenant.

Reference: docs/phase10-ops-governance-mvp.md Section 5.2
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import func, select, text, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TimePeriod(str, Enum):
    """Supported time periods for SLA metrics."""
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

    def to_timedelta(self) -> timedelta:
        if self == TimePeriod.DAY:
            return timedelta(days=1)
        elif self == TimePeriod.WEEK:
            return timedelta(weeks=1)
        elif self == TimePeriod.MONTH:
            return timedelta(days=30)
        return timedelta(days=1)


@dataclass
class SLAComplianceRate:
    """SLA compliance rate for a tenant/period."""
    tenant_id: str
    period: str
    compliance_rate_percent: float
    total_exceptions: int
    met_sla_count: int
    breached_sla_count: int
    in_progress_count: int
    calculated_at: datetime


@dataclass
class SLABreach:
    """A single SLA breach record."""
    exception_id: str
    tenant_id: str
    severity: str
    sla_deadline: datetime
    breached_at: datetime
    breach_duration_hours: float
    current_status: str


@dataclass
class AtRiskException:
    """An exception approaching SLA deadline."""
    exception_id: str
    tenant_id: str
    severity: str
    sla_deadline: datetime
    time_remaining_hours: float
    percent_elapsed: float
    current_status: str


@dataclass
class ResolutionTime:
    """Resolution time metrics by severity."""
    tenant_id: str
    severity: str
    avg_resolution_hours: float
    min_resolution_hours: float
    max_resolution_hours: float
    sample_count: int
    period: str
    calculated_at: datetime


class SLAMetricsService:
    """
    Service to compute SLA compliance and breach metrics.

    Queries the exception and exception_event tables to calculate
    SLA-related metrics per tenant.
    """

    # Default SLA at-risk threshold (80% of SLA window elapsed)
    AT_RISK_THRESHOLD_PERCENT = 80.0

    def __init__(self, session: AsyncSession):
        """
        Initialize the SLA metrics service.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get_compliance_rate(
        self,
        tenant_id: str,
        period: TimePeriod = TimePeriod.DAY,
    ) -> SLAComplianceRate:
        """
        Calculate SLA compliance rate for a tenant.

        Args:
            tenant_id: Tenant identifier.
            period: Time period for calculation.

        Returns:
            SLAComplianceRate with compliance statistics.
        """
        now = datetime.utcnow()
        start_time = now - period.to_timedelta()

        query = text("""
            SELECT
                COUNT(*) as total_exceptions,
                SUM(CASE
                    WHEN status = 'resolved' AND (resolved_at IS NULL OR resolved_at <= sla_deadline)
                    THEN 1 ELSE 0
                END) as met_sla_count,
                SUM(CASE
                    WHEN sla_deadline < :now AND status != 'resolved'
                    THEN 1
                    WHEN status = 'resolved' AND resolved_at > sla_deadline
                    THEN 1
                    ELSE 0
                END) as breached_sla_count,
                SUM(CASE
                    WHEN status NOT IN ('resolved', 'escalated') AND sla_deadline >= :now
                    THEN 1 ELSE 0
                END) as in_progress_count
            FROM exception
            WHERE tenant_id = :tenant_id
              AND created_at >= :start_time
              AND sla_deadline IS NOT NULL
        """)

        try:
            result = await self.session.execute(
                query,
                {
                    "tenant_id": tenant_id,
                    "start_time": start_time,
                    "now": now,
                }
            )
            row = result.fetchone()

            if not row or row[0] == 0:
                return SLAComplianceRate(
                    tenant_id=tenant_id,
                    period=period.value,
                    compliance_rate_percent=100.0,
                    total_exceptions=0,
                    met_sla_count=0,
                    breached_sla_count=0,
                    in_progress_count=0,
                    calculated_at=now,
                )

            total = row[0] or 0
            met = row[1] or 0
            breached = row[2] or 0
            in_progress = row[3] or 0

            # Compliance rate = met / (met + breached) * 100
            denominator = met + breached
            compliance_rate = (met / denominator * 100) if denominator > 0 else 100.0

            return SLAComplianceRate(
                tenant_id=tenant_id,
                period=period.value,
                compliance_rate_percent=round(compliance_rate, 2),
                total_exceptions=total,
                met_sla_count=met,
                breached_sla_count=breached,
                in_progress_count=in_progress,
                calculated_at=now,
            )
        except Exception as e:
            logger.error(f"Failed to calculate compliance rate: {e}")
            return SLAComplianceRate(
                tenant_id=tenant_id,
                period=period.value,
                compliance_rate_percent=0.0,
                total_exceptions=0,
                met_sla_count=0,
                breached_sla_count=0,
                in_progress_count=0,
                calculated_at=now,
            )

    async def get_breaches(
        self,
        tenant_id: str,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[SLABreach], int]:
        """
        Get list of SLA breaches for a tenant.

        Args:
            tenant_id: Tenant identifier.
            from_date: Start of date range (defaults to 30 days ago).
            to_date: End of date range (defaults to now).
            limit: Maximum results to return.
            offset: Number of results to skip.

        Returns:
            Tuple of (list of breaches, total count).
        """
        now = datetime.utcnow()
        if not from_date:
            from_date = now - timedelta(days=30)
        if not to_date:
            to_date = now

        # Query for breached exceptions
        query = text("""
            SELECT
                exception_id,
                tenant_id,
                severity,
                sla_deadline,
                CASE
                    WHEN status = 'resolved' THEN resolved_at
                    ELSE :now
                END as breached_at,
                status
            FROM exception
            WHERE tenant_id = :tenant_id
              AND sla_deadline IS NOT NULL
              AND (
                  (sla_deadline < :now AND status NOT IN ('resolved'))
                  OR (status = 'resolved' AND resolved_at > sla_deadline)
              )
              AND created_at >= :from_date
              AND created_at <= :to_date
            ORDER BY sla_deadline DESC
            LIMIT :limit OFFSET :offset
        """)

        count_query = text("""
            SELECT COUNT(*)
            FROM exception
            WHERE tenant_id = :tenant_id
              AND sla_deadline IS NOT NULL
              AND (
                  (sla_deadline < :now AND status NOT IN ('resolved'))
                  OR (status = 'resolved' AND resolved_at > sla_deadline)
              )
              AND created_at >= :from_date
              AND created_at <= :to_date
        """)

        try:
            result = await self.session.execute(
                query,
                {
                    "tenant_id": tenant_id,
                    "now": now,
                    "from_date": from_date,
                    "to_date": to_date,
                    "limit": limit,
                    "offset": offset,
                }
            )
            rows = result.fetchall()

            count_result = await self.session.execute(
                count_query,
                {
                    "tenant_id": tenant_id,
                    "now": now,
                    "from_date": from_date,
                    "to_date": to_date,
                }
            )
            total = count_result.scalar() or 0

            breaches = []
            for row in rows:
                sla_deadline = row[3]
                breached_at = row[4] or now
                breach_duration = (breached_at - sla_deadline).total_seconds() / 3600

                breaches.append(SLABreach(
                    exception_id=row[0],
                    tenant_id=row[1],
                    severity=row[2] or "unknown",
                    sla_deadline=sla_deadline,
                    breached_at=breached_at,
                    breach_duration_hours=round(breach_duration, 2),
                    current_status=row[5] or "unknown",
                ))

            return breaches, total
        except Exception as e:
            logger.error(f"Failed to get breaches: {e}")
            return [], 0

    async def get_at_risk_exceptions(
        self,
        tenant_id: str,
        threshold_percent: float = None,
        limit: int = 100,
    ) -> list[AtRiskException]:
        """
        Get exceptions approaching their SLA deadline.

        Args:
            tenant_id: Tenant identifier.
            threshold_percent: Percentage of SLA window elapsed to consider at-risk.
            limit: Maximum results to return.

        Returns:
            List of at-risk exceptions.
        """
        if threshold_percent is None:
            threshold_percent = self.AT_RISK_THRESHOLD_PERCENT

        now = datetime.utcnow()

        # Find exceptions where:
        # 1. Not yet resolved
        # 2. SLA deadline is in the future
        # 3. More than threshold_percent of time has elapsed
        query = text("""
            SELECT
                exception_id,
                tenant_id,
                severity,
                sla_deadline,
                created_at,
                status
            FROM exception
            WHERE tenant_id = :tenant_id
              AND status NOT IN ('resolved', 'escalated')
              AND sla_deadline IS NOT NULL
              AND sla_deadline > :now
            ORDER BY sla_deadline ASC
            LIMIT :limit
        """)

        try:
            result = await self.session.execute(
                query,
                {
                    "tenant_id": tenant_id,
                    "now": now,
                    "limit": limit * 2,  # Get extra to filter client-side
                }
            )
            rows = result.fetchall()

            at_risk = []
            for row in rows:
                created_at = row[4]
                sla_deadline = row[3]

                total_window = (sla_deadline - created_at).total_seconds()
                elapsed = (now - created_at).total_seconds()
                remaining = (sla_deadline - now).total_seconds()

                if total_window <= 0:
                    continue

                percent_elapsed = (elapsed / total_window) * 100

                # Only include if past threshold
                if percent_elapsed >= threshold_percent:
                    at_risk.append(AtRiskException(
                        exception_id=row[0],
                        tenant_id=row[1],
                        severity=row[2] or "unknown",
                        sla_deadline=sla_deadline,
                        time_remaining_hours=round(remaining / 3600, 2),
                        percent_elapsed=round(percent_elapsed, 1),
                        current_status=row[5] or "unknown",
                    ))

                if len(at_risk) >= limit:
                    break

            return at_risk
        except Exception as e:
            logger.error(f"Failed to get at-risk exceptions: {e}")
            return []

    async def get_resolution_time(
        self,
        tenant_id: str,
        period: TimePeriod = TimePeriod.DAY,
    ) -> list[ResolutionTime]:
        """
        Calculate average resolution time by severity.

        Args:
            tenant_id: Tenant identifier.
            period: Time period for calculation.

        Returns:
            List of ResolutionTime by severity.
        """
        now = datetime.utcnow()
        start_time = now - period.to_timedelta()

        query = text("""
            SELECT
                severity,
                AVG(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) as avg_hours,
                MIN(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) as min_hours,
                MAX(EXTRACT(EPOCH FROM (resolved_at - created_at)) / 3600) as max_hours,
                COUNT(*) as sample_count
            FROM exception
            WHERE tenant_id = :tenant_id
              AND status = 'resolved'
              AND resolved_at IS NOT NULL
              AND created_at >= :start_time
            GROUP BY severity
            ORDER BY severity
        """)

        try:
            result = await self.session.execute(
                query,
                {
                    "tenant_id": tenant_id,
                    "start_time": start_time,
                }
            )
            rows = result.fetchall()

            return [
                ResolutionTime(
                    tenant_id=tenant_id,
                    severity=row[0] or "unknown",
                    avg_resolution_hours=round(float(row[1]) if row[1] else 0, 2),
                    min_resolution_hours=round(float(row[2]) if row[2] else 0, 2),
                    max_resolution_hours=round(float(row[3]) if row[3] else 0, 2),
                    sample_count=row[4],
                    period=period.value,
                    calculated_at=now,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get resolution time: {e}")
            return []

    async def get_sla_summary(
        self,
        tenant_id: str,
        period: TimePeriod = TimePeriod.DAY,
    ) -> dict:
        """
        Get a complete SLA summary for a tenant.

        Args:
            tenant_id: Tenant identifier.
            period: Time period for calculation.

        Returns:
            Dictionary with compliance, at_risk, and resolution_time data.
        """
        compliance = await self.get_compliance_rate(tenant_id, period)
        at_risk = await self.get_at_risk_exceptions(tenant_id, limit=10)
        resolution_time = await self.get_resolution_time(tenant_id, period)

        return {
            "tenant_id": tenant_id,
            "period": period.value,
            "calculated_at": datetime.utcnow().isoformat(),
            "compliance": {
                "rate_percent": compliance.compliance_rate_percent,
                "total_exceptions": compliance.total_exceptions,
                "met_sla": compliance.met_sla_count,
                "breached_sla": compliance.breached_sla_count,
                "in_progress": compliance.in_progress_count,
            },
            "at_risk_count": len(at_risk),
            "at_risk_exceptions": [
                {
                    "exception_id": e.exception_id,
                    "severity": e.severity,
                    "time_remaining_hours": e.time_remaining_hours,
                    "percent_elapsed": e.percent_elapsed,
                }
                for e in at_risk
            ],
            "resolution_time_by_severity": [
                {
                    "severity": r.severity,
                    "avg_hours": r.avg_resolution_hours,
                    "min_hours": r.min_resolution_hours,
                    "max_hours": r.max_resolution_hours,
                    "sample_count": r.sample_count,
                }
                for r in resolution_time
            ],
        }


def get_sla_metrics_service(session: AsyncSession) -> SLAMetricsService:
    """Get an SLA metrics service instance."""
    return SLAMetricsService(session)
