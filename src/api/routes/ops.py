"""
Operations API routes for monitoring and debugging.

Phase 10: Enhanced with worker health, throughput, SLA metrics, and DLQ management.

Provides operational visibility into:
- Worker health aggregation (P10-1)
- Worker throughput/latency/errors metrics (P10-2)
- SLA compliance metrics (P10-3)
- Dead Letter Queue management (P10-4)
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi import status as http_status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.dead_letter_repository import DeadLetterEventRepository
from src.services.worker_health_service import (
    WorkerHealthService,
    WorkerHealthStatus,
    get_worker_health_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])


# =============================================================================
# P10-1: Worker Health Models and Endpoints
# =============================================================================


class WorkerHealthResponse(BaseModel):
    """Health status for a single worker instance."""

    worker_type: str = Field(..., description="Type of worker (intake, triage, etc.)")
    instance_id: str = Field(..., description="Instance identifier")
    status: str = Field(..., description="Health status (healthy, degraded, unhealthy, unknown)")
    healthz_ok: bool = Field(..., description="Whether /healthz returned 200")
    readyz_ok: bool = Field(..., description="Whether /readyz returned 200")
    last_check: str = Field(..., description="ISO datetime of last health check")
    response_time_ms: Optional[float] = Field(None, description="Response time in milliseconds")
    error_message: Optional[str] = Field(None, description="Error message if unhealthy")


class WorkerHealthListResponse(BaseModel):
    """Response for all worker health statuses."""

    workers: list[WorkerHealthResponse] = Field(..., description="Health status of all workers")
    total_workers: int = Field(..., description="Total number of workers monitored")
    status_counts: dict[str, int] = Field(..., description="Count of workers by status")
    checked_at: str = Field(..., description="ISO datetime when check was performed")


@router.get("/workers/health", response_model=WorkerHealthListResponse)
async def get_worker_health(
    refresh: bool = Query(False, description="Force refresh (bypass cache)"),
) -> WorkerHealthListResponse:
    """
    Get health status of all worker instances.

    GET /ops/workers/health?refresh=false

    Returns aggregated health information from all configured workers by
    polling their /healthz and /readyz endpoints.

    Args:
        refresh: If true, bypass cache and perform fresh health checks.

    Returns:
        WorkerHealthListResponse with health status of all workers.
    """
    try:
        service = get_worker_health_service()
        results = await service.get_all_worker_health(use_cache=not refresh)

        # Count by status
        status_counts = {s.value: 0 for s in WorkerHealthStatus}
        for result in results:
            status_counts[result.status.value] += 1

        workers = [
            WorkerHealthResponse(
                worker_type=r.worker_type,
                instance_id=r.instance_id,
                status=r.status.value,
                healthz_ok=r.healthz_ok,
                readyz_ok=r.readyz_ok,
                last_check=r.last_check.isoformat(),
                response_time_ms=r.response_time_ms,
                error_message=r.error_message,
            )
            for r in results
        ]

        return WorkerHealthListResponse(
            workers=workers,
            total_workers=len(workers),
            status_counts=status_counts,
            checked_at=datetime.utcnow().isoformat(),
        )

    except Exception as e:
        logger.error(f"Failed to get worker health: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve worker health: {str(e)}",
        )


# =============================================================================
# P10-2: Worker Throughput/Latency/Errors Metrics Endpoints
# =============================================================================


class WorkerThroughputResponse(BaseModel):
    """Throughput metrics for a worker type."""

    worker_type: str = Field(..., description="Type of worker")
    events_per_second: float = Field(..., description="Events processed per second")
    total_events: int = Field(..., description="Total events in time range")


class WorkerLatencyResponse(BaseModel):
    """Latency metrics for a worker type."""

    worker_type: str = Field(..., description="Type of worker")
    p50_ms: float = Field(..., description="50th percentile latency (ms)")
    p95_ms: float = Field(..., description="95th percentile latency (ms)")
    p99_ms: float = Field(..., description="99th percentile latency (ms)")
    avg_ms: float = Field(..., description="Average latency (ms)")
    sample_count: int = Field(..., description="Number of samples")


class WorkerErrorRateResponse(BaseModel):
    """Error rate metrics for a worker type."""

    worker_type: str = Field(..., description="Type of worker")
    error_rate_percent: float = Field(..., description="Error rate percentage")
    total_processed: int = Field(..., description="Total events processed")
    total_failed: int = Field(..., description="Total failed events")


class MetricsListResponse(BaseModel):
    """Response for metrics list endpoint."""

    time_range: str = Field(..., description="Time range used for calculation")
    calculated_at: str = Field(..., description="ISO datetime when calculated")
    items: list = Field(..., description="List of metric items")


@router.get("/workers/throughput", response_model=MetricsListResponse)
async def get_worker_throughput(
    time_range: str = Query("1h", description="Time range: 5m, 1h, 24h"),
) -> MetricsListResponse:
    """
    Get worker throughput metrics (events per second).

    GET /ops/workers/throughput?time_range=1h
    """
    from src.services.metrics_aggregation_service import (
        MetricsAggregationService,
        TimeRange,
    )

    # Parse time range
    try:
        tr = TimeRange(time_range)
    except ValueError:
        tr = TimeRange.ONE_HOUR

    try:
        async with get_db_session_context() as session:
            service = MetricsAggregationService(session)
            results = await service.get_throughput_by_worker(tr)

            return MetricsListResponse(
                time_range=tr.value,
                calculated_at=datetime.utcnow().isoformat(),
                items=[
                    WorkerThroughputResponse(
                        worker_type=r.worker_type,
                        events_per_second=round(r.events_per_second, 4),
                        total_events=r.total_events,
                    ).model_dump()
                    for r in results
                ],
            )
    except Exception as e:
        logger.error(f"Failed to get throughput metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve throughput metrics: {str(e)}",
        )


@router.get("/workers/latency", response_model=MetricsListResponse)
async def get_worker_latency(
    time_range: str = Query("1h", description="Time range: 5m, 1h, 24h"),
) -> MetricsListResponse:
    """
    Get worker latency percentiles (p50, p95, p99).

    GET /ops/workers/latency?time_range=1h
    """
    from src.services.metrics_aggregation_service import (
        MetricsAggregationService,
        TimeRange,
    )

    try:
        tr = TimeRange(time_range)
    except ValueError:
        tr = TimeRange.ONE_HOUR

    try:
        async with get_db_session_context() as session:
            service = MetricsAggregationService(session)
            results = await service.get_latency_by_worker(tr)

            return MetricsListResponse(
                time_range=tr.value,
                calculated_at=datetime.utcnow().isoformat(),
                items=[
                    WorkerLatencyResponse(
                        worker_type=r.worker_type,
                        p50_ms=r.p50_ms,
                        p95_ms=r.p95_ms,
                        p99_ms=r.p99_ms,
                        avg_ms=r.avg_ms,
                        sample_count=r.sample_count,
                    ).model_dump()
                    for r in results
                ],
            )
    except Exception as e:
        logger.error(f"Failed to get latency metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve latency metrics: {str(e)}",
        )


@router.get("/workers/errors", response_model=MetricsListResponse)
async def get_worker_errors(
    time_range: str = Query("1h", description="Time range: 5m, 1h, 24h"),
) -> MetricsListResponse:
    """
    Get worker error rates.

    GET /ops/workers/errors?time_range=1h
    """
    from src.services.metrics_aggregation_service import (
        MetricsAggregationService,
        TimeRange,
    )

    try:
        tr = TimeRange(time_range)
    except ValueError:
        tr = TimeRange.ONE_HOUR

    try:
        async with get_db_session_context() as session:
            service = MetricsAggregationService(session)
            results = await service.get_error_rates_by_worker(tr)

            return MetricsListResponse(
                time_range=tr.value,
                calculated_at=datetime.utcnow().isoformat(),
                items=[
                    WorkerErrorRateResponse(
                        worker_type=r.worker_type,
                        error_rate_percent=round(r.error_rate_percent, 2),
                        total_processed=r.total_processed,
                        total_failed=r.total_failed,
                    ).model_dump()
                    for r in results
                ],
            )
    except Exception as e:
        logger.error(f"Failed to get error metrics: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve error metrics: {str(e)}",
        )


# =============================================================================
# P10-3: SLA Compliance Metrics Endpoints
# =============================================================================


class SLAComplianceResponse(BaseModel):
    """SLA compliance metrics."""

    tenant_id: str = Field(..., description="Tenant identifier")
    period: str = Field(..., description="Time period (day, week, month)")
    compliance_rate_percent: float = Field(..., description="SLA compliance rate")
    total_exceptions: int = Field(..., description="Total exceptions in period")
    met_sla_count: int = Field(..., description="Exceptions that met SLA")
    breached_sla_count: int = Field(..., description="Exceptions that breached SLA")
    in_progress_count: int = Field(..., description="In-progress exceptions")
    calculated_at: str = Field(..., description="ISO datetime when calculated")


class SLABreachResponse(BaseModel):
    """SLA breach details."""

    exception_id: str = Field(..., description="Exception identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    severity: str = Field(..., description="Exception severity")
    sla_deadline: str = Field(..., description="SLA deadline ISO datetime")
    breached_at: str = Field(..., description="When SLA was breached")
    breach_duration_hours: float = Field(..., description="Hours past deadline")
    current_status: str = Field(..., description="Current exception status")


class SLABreachListResponse(BaseModel):
    """Response for SLA breach list."""

    items: list[SLABreachResponse] = Field(..., description="List of breaches")
    total: int = Field(..., description="Total breach count")
    limit: int = Field(..., description="Limit used")
    offset: int = Field(..., description="Offset used")


class AtRiskExceptionResponse(BaseModel):
    """Exception approaching SLA deadline."""

    exception_id: str = Field(..., description="Exception identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    severity: str = Field(..., description="Exception severity")
    sla_deadline: str = Field(..., description="SLA deadline ISO datetime")
    time_remaining_hours: float = Field(..., description="Hours until deadline")
    percent_elapsed: float = Field(..., description="Percentage of SLA window elapsed")
    current_status: str = Field(..., description="Current exception status")


class ResolutionTimeResponse(BaseModel):
    """Resolution time by severity."""

    severity: str = Field(..., description="Exception severity")
    avg_resolution_hours: float = Field(..., description="Average resolution time")
    min_resolution_hours: float = Field(..., description="Minimum resolution time")
    max_resolution_hours: float = Field(..., description="Maximum resolution time")
    sample_count: int = Field(..., description="Number of resolved exceptions")


@router.get("/sla/compliance", response_model=SLAComplianceResponse)
async def get_sla_compliance(
    tenant_id: str = Query(..., description="Tenant identifier"),
    period: str = Query("day", description="Period: day, week, month"),
) -> SLAComplianceResponse:
    """
    Get SLA compliance rate for a tenant.

    GET /ops/sla/compliance?tenant_id=...&period=day
    """
    from src.services.sla_metrics_service import SLAMetricsService, TimePeriod

    try:
        tp = TimePeriod(period)
    except ValueError:
        tp = TimePeriod.DAY

    try:
        async with get_db_session_context() as session:
            service = SLAMetricsService(session)
            result = await service.get_compliance_rate(tenant_id, tp)

            return SLAComplianceResponse(
                tenant_id=result.tenant_id,
                period=result.period,
                compliance_rate_percent=result.compliance_rate_percent,
                total_exceptions=result.total_exceptions,
                met_sla_count=result.met_sla_count,
                breached_sla_count=result.breached_sla_count,
                in_progress_count=result.in_progress_count,
                calculated_at=result.calculated_at.isoformat(),
            )
    except Exception as e:
        logger.error(f"Failed to get SLA compliance: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve SLA compliance: {str(e)}",
        )


@router.get("/sla/breaches", response_model=SLABreachListResponse)
async def get_sla_breaches(
    tenant_id: str = Query(..., description="Tenant identifier"),
    from_date: Optional[str] = Query(None, description="Start date ISO format"),
    to_date: Optional[str] = Query(None, description="End date ISO format"),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> SLABreachListResponse:
    """
    Get list of SLA breaches for a tenant.

    GET /ops/sla/breaches?tenant_id=...&from_date=...&to_date=...
    """
    from src.services.sla_metrics_service import SLAMetricsService

    # Parse dates
    from_dt = None
    to_dt = None
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    try:
        async with get_db_session_context() as session:
            service = SLAMetricsService(session)
            breaches, total = await service.get_breaches(
                tenant_id, from_dt, to_dt, limit, offset
            )

            return SLABreachListResponse(
                items=[
                    SLABreachResponse(
                        exception_id=b.exception_id,
                        tenant_id=b.tenant_id,
                        severity=b.severity,
                        sla_deadline=b.sla_deadline.isoformat(),
                        breached_at=b.breached_at.isoformat(),
                        breach_duration_hours=b.breach_duration_hours,
                        current_status=b.current_status,
                    )
                    for b in breaches
                ],
                total=total,
                limit=limit,
                offset=offset,
            )
    except Exception as e:
        logger.error(f"Failed to get SLA breaches: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve SLA breaches: {str(e)}",
        )


@router.get("/sla/at-risk")
async def get_at_risk_exceptions(
    tenant_id: str = Query(..., description="Tenant identifier"),
    threshold_percent: float = Query(80.0, description="At-risk threshold (default 80%)"),
    limit: int = Query(100, ge=1, le=1000),
) -> dict:
    """
    Get exceptions approaching SLA deadline.

    GET /ops/sla/at-risk?tenant_id=...&threshold_percent=80
    """
    from src.services.sla_metrics_service import SLAMetricsService

    try:
        async with get_db_session_context() as session:
            service = SLAMetricsService(session)
            at_risk = await service.get_at_risk_exceptions(
                tenant_id, threshold_percent, limit
            )

            return {
                "tenant_id": tenant_id,
                "threshold_percent": threshold_percent,
                "count": len(at_risk),
                "items": [
                    AtRiskExceptionResponse(
                        exception_id=e.exception_id,
                        tenant_id=e.tenant_id,
                        severity=e.severity,
                        sla_deadline=e.sla_deadline.isoformat(),
                        time_remaining_hours=e.time_remaining_hours,
                        percent_elapsed=e.percent_elapsed,
                        current_status=e.current_status,
                    ).model_dump()
                    for e in at_risk
                ],
            }
    except Exception as e:
        logger.error(f"Failed to get at-risk exceptions: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve at-risk exceptions: {str(e)}",
        )


@router.get("/sla/resolution-time")
async def get_resolution_time(
    tenant_id: str = Query(..., description="Tenant identifier"),
    period: str = Query("day", description="Period: day, week, month"),
) -> dict:
    """
    Get average resolution time by severity.

    GET /ops/sla/resolution-time?tenant_id=...&period=day
    """
    from src.services.sla_metrics_service import SLAMetricsService, TimePeriod

    try:
        tp = TimePeriod(period)
    except ValueError:
        tp = TimePeriod.DAY

    try:
        async with get_db_session_context() as session:
            service = SLAMetricsService(session)
            results = await service.get_resolution_time(tenant_id, tp)

            return {
                "tenant_id": tenant_id,
                "period": tp.value,
                "calculated_at": datetime.utcnow().isoformat(),
                "items": [
                    ResolutionTimeResponse(
                        severity=r.severity,
                        avg_resolution_hours=r.avg_resolution_hours,
                        min_resolution_hours=r.min_resolution_hours,
                        max_resolution_hours=r.max_resolution_hours,
                        sample_count=r.sample_count,
                    ).model_dump()
                    for r in results
                ],
            }
    except Exception as e:
        logger.error(f"Failed to get resolution time: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve resolution time: {str(e)}",
        )


# =============================================================================
# P10-4: DLQ Management (Enhanced from existing)
# =============================================================================


class DLQEntryResponse(BaseModel):
    """Response model for DLQ entry."""
    
    event_id: str = Field(..., description="Original event identifier")
    event_type: str = Field(..., description="Type of the original event")
    tenant_id: str = Field(..., description="Tenant identifier")
    exception_id: Optional[str] = Field(None, description="Exception identifier")
    original_topic: str = Field(..., description="Original topic where event was published")
    failure_reason: str = Field(..., description="Reason for failure")
    retry_count: int = Field(..., description="Number of retry attempts made")
    worker_type: str = Field(..., description="Worker type that failed")
    payload: dict = Field(..., description="Original event payload")
    event_metadata: dict = Field(default_factory=dict, description="Event metadata")
    failed_at: str = Field(..., description="ISO datetime when event was moved to DLQ")


class DLQListResponse(BaseModel):
    """Response model for DLQ list."""
    
    items: list[DLQEntryResponse] = Field(..., description="List of DLQ entries")
    total: int = Field(..., description="Total number of DLQ entries matching filters")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")


@router.get("/dlq", response_model=DLQListResponse)
async def list_dlq_entries(
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (required)"),
    status: Optional[str] = Query(None, description="Filter by status (not currently used)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> DLQListResponse:
    """
    List Dead Letter Queue entries.
    
    GET /api/ops/dlq?tenant_id=&status=&limit=&offset=
    
    This is a read-only endpoint for monitoring DLQ entries.
    All queries are tenant-isolated.
    
    Args:
        request: FastAPI request object (for tenant extraction)
        tenant_id: Tenant identifier (required)
        status: Status filter (reserved for future use)
        limit: Maximum number of results (1-1000, default: 100)
        offset: Number of results to skip (default: 0)
        
    Returns:
        DLQListResponse with paginated DLQ entries
        
    Raises:
        HTTPException: If tenant_id is missing or invalid
    """
    # Extract tenant_id from request (could be from middleware or query param)
    # For now, require it as query param
    if not tenant_id:
        # Try to get from request state (set by middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
    
    if not tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="tenant_id is required (query parameter or authenticated tenant)",
        )
    
    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)
            
            # List DLQ entries with tenant isolation
            result = await dlq_repo.list_dlq_entries(
                tenant_id=tenant_id,
                limit=limit,
                offset=offset,
                order_by="failed_at",
                order_desc=True,
            )
            
            # Convert to response format
            items = [
                DLQEntryResponse(
                    event_id=entry.event_id,
                    event_type=entry.event_type,
                    tenant_id=entry.tenant_id,
                    exception_id=entry.exception_id,
                    original_topic=entry.original_topic,
                    failure_reason=entry.failure_reason,
                    retry_count=entry.retry_count,
                    worker_type=entry.worker_type,
                    payload=entry.payload or {},
                    event_metadata=entry.event_metadata or {},
                    failed_at=entry.failed_at.isoformat() if entry.failed_at else "",
                )
                for entry in result.items
            ]
            
            return DLQListResponse(
                items=items,
                total=result.total,
                limit=limit,
                offset=offset,
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # Check if it's a table doesn't exist error
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "no such table" in error_msg or "relation" in error_msg:
            logger.warning(f"DLQ table may not exist yet: {e}. Returning empty results.")
            return DLQListResponse(
                items=[],
                total=0,
                limit=limit,
                offset=offset,
            )
        logger.error(f"Failed to list DLQ entries: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ entries: {str(e)}",
        )


# -----------------------------------------------------------------------------
# P10-4: Enhanced DLQ Management Endpoints
# -----------------------------------------------------------------------------


class DLQEntryDetailResponse(BaseModel):
    """Detailed response model for a single DLQ entry."""

    id: int = Field(..., description="DLQ entry primary key")
    event_id: str = Field(..., description="Original event identifier")
    event_type: str = Field(..., description="Type of the original event")
    tenant_id: str = Field(..., description="Tenant identifier")
    exception_id: Optional[str] = Field(None, description="Exception identifier")
    original_topic: str = Field(..., description="Original topic where event was published")
    failure_reason: str = Field(..., description="Reason for failure")
    retry_count: int = Field(..., description="Number of retry attempts made")
    worker_type: str = Field(..., description="Worker type that failed")
    payload: dict = Field(..., description="Original event payload")
    event_metadata: dict = Field(default_factory=dict, description="Event metadata")
    status: str = Field(..., description="DLQ entry status")
    failed_at: str = Field(..., description="ISO datetime when event was moved to DLQ")
    retried_at: Optional[str] = Field(None, description="ISO datetime of last retry")
    discarded_at: Optional[str] = Field(None, description="ISO datetime when discarded")
    discarded_by: Optional[str] = Field(None, description="Who discarded the entry")


class DLQStatsResponse(BaseModel):
    """DLQ statistics response."""

    tenant_id: str = Field(..., description="Tenant identifier")
    total: int = Field(..., description="Total DLQ entries")
    pending: int = Field(..., description="Pending entries")
    retrying: int = Field(..., description="Currently retrying")
    discarded: int = Field(..., description="Discarded entries")
    succeeded: int = Field(..., description="Successfully retried")
    by_event_type: dict[str, int] = Field(..., description="Counts by event type")
    by_worker_type: dict[str, int] = Field(..., description="Counts by worker type")


class DLQRetryRequest(BaseModel):
    """Request body for retry operation."""

    reason: Optional[str] = Field(None, description="Reason for retry")


class DLQBatchRetryRequest(BaseModel):
    """Request body for batch retry operation."""

    dlq_ids: list[int] = Field(..., description="List of DLQ entry IDs to retry")
    reason: Optional[str] = Field(None, description="Reason for retry")


class DLQBatchRetryResponse(BaseModel):
    """Response for batch retry operation."""

    updated_count: int = Field(..., description="Number of entries updated")
    requested_count: int = Field(..., description="Number of entries requested")


class DLQDiscardRequest(BaseModel):
    """Request body for discard operation."""

    reason: Optional[str] = Field(None, description="Reason for discarding")


@router.get("/dlq/stats", response_model=DLQStatsResponse)
async def get_dlq_stats(
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> DLQStatsResponse:
    """
    Get DLQ statistics for a tenant.

    GET /ops/dlq/stats?tenant_id=...

    Returns counts by status, event type, and worker type.
    """
    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)
            stats = await dlq_repo.get_stats(tenant_id)

            return DLQStatsResponse(
                tenant_id=stats.tenant_id,
                total=stats.total,
                pending=stats.pending,
                retrying=stats.retrying,
                discarded=stats.discarded,
                succeeded=stats.succeeded,
                by_event_type=stats.by_event_type,
                by_worker_type=stats.by_worker_type,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get DLQ stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ stats: {str(e)}",
        )


@router.get("/dlq/{dlq_id}", response_model=DLQEntryDetailResponse)
async def get_dlq_entry(
    dlq_id: int,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> DLQEntryDetailResponse:
    """
    Get a single DLQ entry by ID.

    GET /ops/dlq/{dlq_id}?tenant_id=...

    Returns full details of a DLQ entry including status tracking fields.
    """
    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)
            entry = await dlq_repo.get_dlq_entry_by_id(dlq_id, tenant_id)

            if not entry:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"DLQ entry {dlq_id} not found for tenant {tenant_id}",
                )

            return DLQEntryDetailResponse(
                id=entry.id,
                event_id=entry.event_id,
                event_type=entry.event_type,
                tenant_id=entry.tenant_id,
                exception_id=entry.exception_id,
                original_topic=entry.original_topic,
                failure_reason=entry.failure_reason,
                retry_count=entry.retry_count,
                worker_type=entry.worker_type,
                payload=entry.payload or {},
                event_metadata=entry.event_metadata or {},
                status=entry.status or "pending",
                failed_at=entry.failed_at.isoformat() if entry.failed_at else "",
                retried_at=entry.retried_at.isoformat() if entry.retried_at else None,
                discarded_at=entry.discarded_at.isoformat() if entry.discarded_at else None,
                discarded_by=entry.discarded_by,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get DLQ entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ entry: {str(e)}",
        )


@router.post("/dlq/{dlq_id}/retry", response_model=DLQEntryDetailResponse)
async def retry_dlq_entry(
    dlq_id: int,
    tenant_id: str = Query(..., description="Tenant identifier"),
    body: Optional[DLQRetryRequest] = None,
) -> DLQEntryDetailResponse:
    """
    Retry a single DLQ entry.

    POST /ops/dlq/{dlq_id}/retry?tenant_id=...

    Marks the entry as 'retrying' and increments retry count.
    The actual retry is handled by the worker processing loop.
    """
    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)

            # Mark as retrying
            entry = await dlq_repo.mark_retrying(dlq_id, tenant_id)

            if not entry:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"DLQ entry {dlq_id} not found for tenant {tenant_id}",
                )

            await session.commit()

            logger.info(
                f"DLQ entry marked for retry: dlq_id={dlq_id}, tenant_id={tenant_id}, "
                f"reason={body.reason if body else 'not specified'}"
            )

            return DLQEntryDetailResponse(
                id=entry.id,
                event_id=entry.event_id,
                event_type=entry.event_type,
                tenant_id=entry.tenant_id,
                exception_id=entry.exception_id,
                original_topic=entry.original_topic,
                failure_reason=entry.failure_reason,
                retry_count=entry.retry_count,
                worker_type=entry.worker_type,
                payload=entry.payload or {},
                event_metadata=entry.event_metadata or {},
                status=entry.status or "retrying",
                failed_at=entry.failed_at.isoformat() if entry.failed_at else "",
                retried_at=entry.retried_at.isoformat() if entry.retried_at else None,
                discarded_at=entry.discarded_at.isoformat() if entry.discarded_at else None,
                discarded_by=entry.discarded_by,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to retry DLQ entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retry DLQ entry: {str(e)}",
        )


@router.post("/dlq/retry-batch", response_model=DLQBatchRetryResponse)
async def retry_dlq_batch(
    tenant_id: str = Query(..., description="Tenant identifier"),
    body: DLQBatchRetryRequest = ...,
) -> DLQBatchRetryResponse:
    """
    Retry multiple DLQ entries at once.

    POST /ops/dlq/retry-batch?tenant_id=...
    Body: {"dlq_ids": [1, 2, 3], "reason": "optional reason"}

    Marks all specified entries as 'retrying' in a single transaction.
    """
    from src.infrastructure.db.models import DLQStatus

    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)

            updated_count = await dlq_repo.batch_update_status(
                dlq_ids=body.dlq_ids,
                tenant_id=tenant_id,
                new_status=DLQStatus.RETRYING.value,
            )

            await session.commit()

            logger.info(
                f"DLQ batch retry: updated={updated_count}, requested={len(body.dlq_ids)}, "
                f"tenant_id={tenant_id}, reason={body.reason or 'not specified'}"
            )

            return DLQBatchRetryResponse(
                updated_count=updated_count,
                requested_count=len(body.dlq_ids),
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to batch retry DLQ entries: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to batch retry DLQ entries: {str(e)}",
        )


@router.post("/dlq/{dlq_id}/discard", response_model=DLQEntryDetailResponse)
async def discard_dlq_entry(
    dlq_id: int,
    tenant_id: str = Query(..., description="Tenant identifier"),
    actor: Optional[str] = Query(None, description="User who discarded"),
    body: Optional[DLQDiscardRequest] = None,
) -> DLQEntryDetailResponse:
    """
    Discard a DLQ entry (mark as not worth retrying).

    POST /ops/dlq/{dlq_id}/discard?tenant_id=...&actor=...

    Marks the entry as 'discarded' with timestamp and actor info.
    """
    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)

            # Mark as discarded
            entry = await dlq_repo.mark_discarded(dlq_id, tenant_id, actor)

            if not entry:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"DLQ entry {dlq_id} not found for tenant {tenant_id}",
                )

            await session.commit()

            logger.info(
                f"DLQ entry discarded: dlq_id={dlq_id}, tenant_id={tenant_id}, "
                f"actor={actor or 'unknown'}, reason={body.reason if body else 'not specified'}"
            )

            return DLQEntryDetailResponse(
                id=entry.id,
                event_id=entry.event_id,
                event_type=entry.event_type,
                tenant_id=entry.tenant_id,
                exception_id=entry.exception_id,
                original_topic=entry.original_topic,
                failure_reason=entry.failure_reason,
                retry_count=entry.retry_count,
                worker_type=entry.worker_type,
                payload=entry.payload or {},
                event_metadata=entry.event_metadata or {},
                status=entry.status or "discarded",
                failed_at=entry.failed_at.isoformat() if entry.failed_at else "",
                retried_at=entry.retried_at.isoformat() if entry.retried_at else None,
                discarded_at=entry.discarded_at.isoformat() if entry.discarded_at else None,
                discarded_by=entry.discarded_by,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to discard DLQ entry: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to discard DLQ entry: {str(e)}",
        )

