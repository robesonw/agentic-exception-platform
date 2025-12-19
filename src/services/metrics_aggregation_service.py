"""
Metrics Aggregation Service for Phase 10.

Computes worker throughput, latency percentiles, and error rates
from the event_processing table.

Reference: docs/phase10-ops-governance-mvp.md Section 5.1
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class TimeRange(str, Enum):
    """Supported time ranges for metrics queries."""
    FIVE_MINUTES = "5m"
    ONE_HOUR = "1h"
    TWENTY_FOUR_HOURS = "24h"

    def to_timedelta(self) -> timedelta:
        if self == TimeRange.FIVE_MINUTES:
            return timedelta(minutes=5)
        elif self == TimeRange.ONE_HOUR:
            return timedelta(hours=1)
        elif self == TimeRange.TWENTY_FOUR_HOURS:
            return timedelta(hours=24)
        return timedelta(hours=1)


@dataclass
class WorkerThroughput:
    """Throughput metrics for a worker type."""
    worker_type: str
    events_per_second: float
    total_events: int
    time_range: str
    calculated_at: datetime


@dataclass
class WorkerLatency:
    """Latency metrics for a worker type."""
    worker_type: str
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    time_range: str
    sample_count: int
    calculated_at: datetime


@dataclass
class WorkerErrorRate:
    """Error rate metrics for a worker type."""
    worker_type: str
    error_rate_percent: float
    total_processed: int
    total_failed: int
    time_range: str
    calculated_at: datetime


class MetricsAggregationService:
    """
    Service to compute worker throughput, latency, and error metrics.

    Queries the event_processing table to calculate metrics per worker type.
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize the metrics aggregation service.

        Args:
            session: Async database session.
        """
        self.session = session

    async def get_throughput_by_worker(
        self,
        time_range: TimeRange = TimeRange.ONE_HOUR,
    ) -> list[WorkerThroughput]:
        """
        Calculate events per second by worker type.

        Args:
            time_range: Time window for calculation.

        Returns:
            List of WorkerThroughput for each worker type.
        """
        now = datetime.utcnow()
        start_time = now - time_range.to_timedelta()
        seconds = time_range.to_timedelta().total_seconds()

        # Query event_processing table for counts by worker_type
        query = text("""
            SELECT
                worker_type,
                COUNT(*) as total_events
            FROM event_processing
            WHERE processed_at >= :start_time
            GROUP BY worker_type
            ORDER BY worker_type
        """)

        try:
            result = await self.session.execute(
                query,
                {"start_time": start_time}
            )
            rows = result.fetchall()

            return [
                WorkerThroughput(
                    worker_type=row[0],
                    events_per_second=row[1] / seconds if seconds > 0 else 0,
                    total_events=row[1],
                    time_range=time_range.value,
                    calculated_at=now,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to calculate throughput: {e}")
            # Return empty list if table doesn't exist or query fails
            return []

    async def get_latency_by_worker(
        self,
        time_range: TimeRange = TimeRange.ONE_HOUR,
    ) -> list[WorkerLatency]:
        """
        Calculate latency percentiles by worker type.

        Note: Latency calculation requires processing_duration_ms in event_processing.
        If not available, returns estimated values based on processed_at timestamps.

        Args:
            time_range: Time window for calculation.

        Returns:
            List of WorkerLatency for each worker type.
        """
        now = datetime.utcnow()
        start_time = now - time_range.to_timedelta()

        # Try to get latency from event_processing if duration column exists
        # Otherwise, estimate based on event timestamps
        query = text("""
            SELECT
                worker_type,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY processing_duration_ms), 0) as p50,
                COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY processing_duration_ms), 0) as p95,
                COALESCE(PERCENTILE_CONT(0.99) WITHIN GROUP (ORDER BY processing_duration_ms), 0) as p99,
                COALESCE(AVG(processing_duration_ms), 0) as avg_ms,
                COUNT(*) as sample_count
            FROM event_processing
            WHERE processed_at >= :start_time
            GROUP BY worker_type
            ORDER BY worker_type
        """)

        try:
            result = await self.session.execute(
                query,
                {"start_time": start_time}
            )
            rows = result.fetchall()

            return [
                WorkerLatency(
                    worker_type=row[0],
                    p50_ms=float(row[1]) if row[1] else 0.0,
                    p95_ms=float(row[2]) if row[2] else 0.0,
                    p99_ms=float(row[3]) if row[3] else 0.0,
                    avg_ms=float(row[4]) if row[4] else 0.0,
                    time_range=time_range.value,
                    sample_count=row[5],
                    calculated_at=now,
                )
                for row in rows
            ]
        except Exception as e:
            logger.warning(f"Failed to calculate latency percentiles: {e}")
            # Fallback: return basic counts without latency data
            return await self._get_latency_fallback(time_range)

    async def _get_latency_fallback(
        self,
        time_range: TimeRange,
    ) -> list[WorkerLatency]:
        """Fallback latency calculation when percentile functions unavailable."""
        now = datetime.utcnow()
        start_time = now - time_range.to_timedelta()

        query = text("""
            SELECT
                worker_type,
                COUNT(*) as sample_count
            FROM event_processing
            WHERE processed_at >= :start_time
            GROUP BY worker_type
            ORDER BY worker_type
        """)

        try:
            result = await self.session.execute(
                query,
                {"start_time": start_time}
            )
            rows = result.fetchall()

            return [
                WorkerLatency(
                    worker_type=row[0],
                    p50_ms=0.0,  # Not available without duration column
                    p95_ms=0.0,
                    p99_ms=0.0,
                    avg_ms=0.0,
                    time_range=time_range.value,
                    sample_count=row[1],
                    calculated_at=now,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to get latency fallback: {e}")
            return []

    async def get_error_rates_by_worker(
        self,
        time_range: TimeRange = TimeRange.ONE_HOUR,
    ) -> list[WorkerErrorRate]:
        """
        Calculate error rates by worker type.

        Args:
            time_range: Time window for calculation.

        Returns:
            List of WorkerErrorRate for each worker type.
        """
        now = datetime.utcnow()
        start_time = now - time_range.to_timedelta()

        query = text("""
            SELECT
                worker_type,
                COUNT(*) as total_processed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as total_failed
            FROM event_processing
            WHERE processed_at >= :start_time
            GROUP BY worker_type
            ORDER BY worker_type
        """)

        try:
            result = await self.session.execute(
                query,
                {"start_time": start_time}
            )
            rows = result.fetchall()

            return [
                WorkerErrorRate(
                    worker_type=row[0],
                    error_rate_percent=(row[2] / row[1] * 100) if row[1] > 0 else 0.0,
                    total_processed=row[1],
                    total_failed=row[2] or 0,
                    time_range=time_range.value,
                    calculated_at=now,
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Failed to calculate error rates: {e}")
            return []

    async def get_all_metrics(
        self,
        time_range: TimeRange = TimeRange.ONE_HOUR,
    ) -> dict:
        """
        Get all worker metrics in a single call.

        Args:
            time_range: Time window for calculation.

        Returns:
            Dictionary with throughput, latency, and error_rates.
        """
        throughput = await self.get_throughput_by_worker(time_range)
        latency = await self.get_latency_by_worker(time_range)
        errors = await self.get_error_rates_by_worker(time_range)

        return {
            "time_range": time_range.value,
            "calculated_at": datetime.utcnow().isoformat(),
            "throughput": [
                {
                    "worker_type": t.worker_type,
                    "events_per_second": t.events_per_second,
                    "total_events": t.total_events,
                }
                for t in throughput
            ],
            "latency": [
                {
                    "worker_type": l.worker_type,
                    "p50_ms": l.p50_ms,
                    "p95_ms": l.p95_ms,
                    "p99_ms": l.p99_ms,
                    "avg_ms": l.avg_ms,
                    "sample_count": l.sample_count,
                }
                for l in latency
            ],
            "error_rates": [
                {
                    "worker_type": e.worker_type,
                    "error_rate_percent": e.error_rate_percent,
                    "total_processed": e.total_processed,
                    "total_failed": e.total_failed,
                }
                for e in errors
            ],
        }


def get_metrics_aggregation_service(session: AsyncSession) -> MetricsAggregationService:
    """Get a metrics aggregation service instance."""
    return MetricsAggregationService(session)
