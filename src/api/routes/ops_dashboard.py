"""
Ops Dashboard API Routes for Phase 10 (P10-21 to P10-28).

Provides backend APIs for operations UI screens:
- Ops Home overview
- Worker Dashboard
- SLA Dashboard
- DLQ Management summary
- Alert summary
- Usage overview

Reference: docs/phase10-ops-governance-mvp.md Section 11
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.services.worker_health_service import (
    get_worker_health_service,
    WorkerHealthStatus,
)
from src.services.metrics_aggregation_service import (
    get_metrics_aggregation_service,
)
from src.services.sla_metrics_service import get_sla_metrics_service
from src.infrastructure.repositories.dead_letter_repository import DeadLetterEventRepository
from src.infrastructure.repositories.alert_repository import AlertHistoryRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops/dashboard", tags=["ops-dashboard"])


# =============================================================================
# Response Models
# =============================================================================


class WorkerHealthSummary(BaseModel):
    """Worker health summary for dashboard."""
    total_workers: int
    healthy_count: int
    degraded_count: int
    unhealthy_count: int
    health_percent: float


class MetricsSummary(BaseModel):
    """Metrics summary for dashboard."""
    total_events_per_second: float
    average_latency_ms: float
    average_error_rate_percent: float


class SLASummary(BaseModel):
    """SLA summary for dashboard."""
    compliance_rate_percent: float
    total_with_sla: int
    met_count: int
    breached_count: int
    at_risk_count: int


class DLQSummary(BaseModel):
    """DLQ summary for dashboard."""
    total_entries: int
    pending_count: int
    retrying_count: int
    error_rate_percent: float


class AlertSummary(BaseModel):
    """Alert summary for dashboard."""
    triggered_count: int
    acknowledged_count: int
    resolved_count: int
    critical_unacknowledged: int


class OpsHomeResponse(BaseModel):
    """Response for ops home dashboard."""
    tenant_id: str
    timestamp: datetime
    workers: WorkerHealthSummary
    metrics: MetricsSummary
    sla: SLASummary
    dlq: DLQSummary
    alerts: AlertSummary


class WorkerDetail(BaseModel):
    """Detailed worker status."""
    worker_type: str
    instance_id: str
    status: str
    healthz_ok: bool
    readyz_ok: bool
    response_time_ms: Optional[float]
    last_check: Optional[datetime]


class WorkerDashboardResponse(BaseModel):
    """Response for worker dashboard."""
    tenant_id: str
    timestamp: datetime
    summary: WorkerHealthSummary
    workers: list[WorkerDetail]
    throughput_by_worker: dict[str, float]


class SLADashboardResponse(BaseModel):
    """Response for SLA dashboard."""
    tenant_id: str
    timestamp: datetime
    summary: SLASummary
    trend_7_days: list[dict]
    recent_breaches: list[dict]


class DLQDashboardResponse(BaseModel):
    """Response for DLQ dashboard."""
    tenant_id: str
    timestamp: datetime
    summary: DLQSummary
    by_event_type: dict[str, int]
    by_worker: dict[str, int]
    recent_entries: list[dict]


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/home",
    response_model=OpsHomeResponse,
    summary="Get ops home dashboard data",
)
async def get_ops_home(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """
    Get overview data for ops home dashboard.

    Returns:
    - Worker health summary
    - Key metrics (throughput, latency, error rate)
    - SLA compliance summary
    - DLQ summary
    - Active alerts summary
    """
    async with get_db_session_context() as session:
        now = datetime.now(timezone.utc)

        # Worker health
        worker_service = get_worker_health_service()
        try:
            worker_health = await worker_service.get_health_summary()
            total_workers = worker_health.get("total_workers", 0)
            status_counts = worker_health.get("status_counts", {})
            healthy = status_counts.get("healthy", 0)
            degraded = status_counts.get("degraded", 0)
            unhealthy = status_counts.get("unhealthy", 0)
        except Exception as e:
            logger.warning(f"Failed to get worker health: {e}")
            total_workers = 0
            healthy = degraded = unhealthy = 0

        health_percent = (healthy / total_workers * 100) if total_workers > 0 else 0

        # Metrics summary
        metrics_service = get_metrics_aggregation_service(session)
        try:
            throughput = await metrics_service.get_throughput_by_worker()
            total_eps = sum(t.events_per_second for t in throughput)

            latency = await metrics_service.get_latency_by_worker()
            avg_latency = sum(l.avg_ms for l in latency) / len(latency) if latency else 0

            errors = await metrics_service.get_error_rates_by_worker()
            avg_error = sum(e.error_rate_percent for e in errors) / len(errors) if errors else 0
        except Exception as e:
            logger.warning(f"Failed to get metrics: {e}")
            total_eps = avg_latency = avg_error = 0

        # SLA summary
        sla_service = get_sla_metrics_service(session)
        try:
            sla_data = await sla_service.get_compliance_rate(tenant_id)
            at_risk = await sla_service.get_at_risk_exceptions(tenant_id, limit=100)
            sla_summary = SLASummary(
                compliance_rate_percent=sla_data.compliance_rate_percent,
                total_with_sla=sla_data.total_exceptions,
                met_count=sla_data.met_sla_count,
                breached_count=sla_data.breached_sla_count,
                at_risk_count=len(at_risk),
            )
        except Exception as e:
            logger.warning(f"Failed to get SLA data: {e}")
            sla_summary = SLASummary(
                compliance_rate_percent=0,
                total_with_sla=0,
                met_count=0,
                breached_count=0,
                at_risk_count=0,
            )

        # DLQ summary
        dlq_repo = DeadLetterEventRepository(session)
        try:
            dlq_stats = await dlq_repo.get_dlq_stats(tenant_id)
            dlq_summary = DLQSummary(
                total_entries=dlq_stats.total_entries,
                pending_count=dlq_stats.pending_count,
                retrying_count=dlq_stats.retrying_count,
                error_rate_percent=dlq_stats.error_rate_percent,
            )
        except Exception as e:
            logger.warning(f"Failed to get DLQ stats: {e}")
            dlq_summary = DLQSummary(
                total_entries=0,
                pending_count=0,
                retrying_count=0,
                error_rate_percent=0,
            )

        # Alert summary
        alert_repo = AlertHistoryRepository(session)
        try:
            alert_counts = await alert_repo.get_alert_counts(tenant_id)
            critical_query = await alert_repo.list_by_tenant(
                tenant_id=tenant_id,
                page=1,
                page_size=100,
                status="triggered",
            )
            critical_unack = sum(
                1 for a in critical_query.items
                if a.severity == "critical"
            )
            alert_summary = AlertSummary(
                triggered_count=alert_counts.get("triggered", 0),
                acknowledged_count=alert_counts.get("acknowledged", 0),
                resolved_count=alert_counts.get("resolved", 0),
                critical_unacknowledged=critical_unack,
            )
        except Exception as e:
            logger.warning(f"Failed to get alert summary: {e}")
            alert_summary = AlertSummary(
                triggered_count=0,
                acknowledged_count=0,
                resolved_count=0,
                critical_unacknowledged=0,
            )

        return OpsHomeResponse(
            tenant_id=tenant_id,
            timestamp=now,
            workers=WorkerHealthSummary(
                total_workers=total_workers,
                healthy_count=healthy,
                degraded_count=degraded,
                unhealthy_count=unhealthy,
                health_percent=health_percent,
            ),
            metrics=MetricsSummary(
                total_events_per_second=total_eps,
                average_latency_ms=avg_latency,
                average_error_rate_percent=avg_error,
            ),
            sla=sla_summary,
            dlq=dlq_summary,
            alerts=alert_summary,
        )


@router.get(
    "/workers",
    response_model=WorkerDashboardResponse,
    summary="Get worker dashboard data",
)
async def get_worker_dashboard(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """
    Get detailed worker health and throughput data.

    Returns:
    - Worker health summary
    - Individual worker status
    - Throughput by worker type
    """
    async with get_db_session_context() as session:
        now = datetime.now(timezone.utc)

        # Worker health
        worker_service = get_worker_health_service()
        try:
            all_health = await worker_service.get_all_worker_health()
            health_summary = await worker_service.get_health_summary()

            workers = [
                WorkerDetail(
                    worker_type=h.worker_type,
                    instance_id=h.instance_id,
                    status=h.status.value if h.status else "unknown",
                    healthz_ok=h.healthz_ok,
                    readyz_ok=h.readyz_ok,
                    response_time_ms=h.response_time_ms,
                    last_check=h.last_check,
                )
                for h in all_health
            ]

            total_workers = health_summary.get("total_workers", 0)
            status_counts = health_summary.get("status_counts", {})
        except Exception as e:
            logger.warning(f"Failed to get worker health: {e}")
            workers = []
            total_workers = 0
            status_counts = {}

        # Throughput by worker
        metrics_service = get_metrics_aggregation_service(session)
        try:
            throughput = await metrics_service.get_throughput_by_worker()
            throughput_by_worker = {
                t.worker_type: t.events_per_second for t in throughput
            }
        except Exception as e:
            logger.warning(f"Failed to get throughput: {e}")
            throughput_by_worker = {}

        return WorkerDashboardResponse(
            tenant_id=tenant_id,
            timestamp=now,
            summary=WorkerHealthSummary(
                total_workers=total_workers,
                healthy_count=status_counts.get("healthy", 0),
                degraded_count=status_counts.get("degraded", 0),
                unhealthy_count=status_counts.get("unhealthy", 0),
                health_percent=(status_counts.get("healthy", 0) / total_workers * 100) if total_workers > 0 else 0,
            ),
            workers=workers,
            throughput_by_worker=throughput_by_worker,
        )


@router.get(
    "/sla",
    response_model=SLADashboardResponse,
    summary="Get SLA dashboard data",
)
async def get_sla_dashboard(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """
    Get SLA compliance data for dashboard.

    Returns:
    - SLA compliance summary
    - 7-day trend
    - Recent breaches
    """
    async with get_db_session_context() as session:
        now = datetime.now(timezone.utc)

        sla_service = get_sla_metrics_service(session)

        try:
            sla_data = await sla_service.get_compliance_rate(tenant_id)
            at_risk = await sla_service.get_at_risk_exceptions(tenant_id, limit=100)
            sla_summary = SLASummary(
                compliance_rate_percent=sla_data.compliance_rate_percent,
                total_with_sla=sla_data.total_exceptions,
                met_count=sla_data.met_sla_count,
                breached_count=sla_data.breached_sla_count,
                at_risk_count=len(at_risk),
            )

            # Get recent breaches
            breaches, _ = await sla_service.get_breaches(tenant_id, limit=10)
            recent_breaches = [
                {
                    "exception_id": b.exception_id,
                    "breach_time": b.breached_at.isoformat() if b.breached_at else None,
                    "sla_deadline": b.sla_deadline.isoformat() if b.sla_deadline else None,
                    "severity": b.severity,
                }
                for b in breaches
            ]

            # Trend data not available - return empty for MVP
            trend_7_days = []
        except Exception as e:
            logger.warning(f"Failed to get SLA data: {e}")
            sla_summary = SLASummary(
                compliance_rate_percent=0,
                total_with_sla=0,
                met_count=0,
                breached_count=0,
                at_risk_count=0,
            )
            trend_7_days = []
            recent_breaches = []

        return SLADashboardResponse(
            tenant_id=tenant_id,
            timestamp=now,
            summary=sla_summary,
            trend_7_days=trend_7_days,
            recent_breaches=recent_breaches,
        )


@router.get(
    "/dlq",
    response_model=DLQDashboardResponse,
    summary="Get DLQ dashboard data",
)
async def get_dlq_dashboard(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """
    Get DLQ management data for dashboard.

    Returns:
    - DLQ summary
    - Breakdown by event type
    - Breakdown by worker
    - Recent entries
    """
    async with get_db_session_context() as session:
        now = datetime.now(timezone.utc)

        dlq_repo = DeadLetterEventRepository(session)

        try:
            # Summary stats
            stats = await dlq_repo.get_dlq_stats(tenant_id)
            summary = DLQSummary(
                total_entries=stats.total_entries,
                pending_count=stats.pending_count,
                retrying_count=stats.retrying_count,
                error_rate_percent=stats.error_rate_percent,
            )

            by_event_type = stats.by_event_type
            by_worker = stats.by_worker

            # Recent entries
            recent_result = await dlq_repo.list_dlq_entries(
                tenant_id=tenant_id,
                limit=10,
            )
            recent_entries = [
                {
                    "id": e.id,
                    "event_id": e.event_id,
                    "event_type": e.event_type,
                    "worker_type": e.worker_type,
                    "status": e.status,
                    "failure_reason": e.failure_reason,
                    "retry_count": e.retry_count,
                    "failed_at": e.failed_at.isoformat() if e.failed_at else None,
                }
                for e in recent_result.items
            ]
        except Exception as e:
            logger.warning(f"Failed to get DLQ data: {e}")
            summary = DLQSummary(
                total_entries=0,
                pending_count=0,
                retrying_count=0,
                error_rate_percent=0,
            )
            by_event_type = {}
            by_worker = {}
            recent_entries = []

        return DLQDashboardResponse(
            tenant_id=tenant_id,
            timestamp=now,
            summary=summary,
            by_event_type=by_event_type,
            by_worker=by_worker,
            recent_entries=recent_entries,
        )
