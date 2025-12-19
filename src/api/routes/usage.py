"""
Usage Metering API Routes for Phase 10 (P10-18 to P10-20).

Provides endpoints for usage reporting:
- Get usage summary
- Get detailed usage
- Export usage for billing

Reference: docs/phase10-ops-governance-mvp.md Section 10
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.services.usage_metering_service import (
    UsageMeteringService,
    get_usage_metering_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/usage", tags=["usage"])


# =============================================================================
# Request/Response Models
# =============================================================================


class UsageSummaryResponse(BaseModel):
    """Response for usage summary."""
    tenant_id: str
    period: str
    period_start: datetime
    period_end: datetime
    totals: dict[str, int]
    by_resource: dict[str, dict[str, int]]


class UsageDetailRecord(BaseModel):
    """Single usage detail record."""
    metric_type: str
    resource_id: Optional[str]
    period_start: datetime
    period_end: datetime
    count: int
    bytes_value: Optional[int]


class UsageDetailsResponse(BaseModel):
    """Response for detailed usage."""
    tenant_id: str
    metric_type: str
    from_date: datetime
    to_date: datetime
    records: list[UsageDetailRecord]
    total_count: int


class UsageExportMetric(BaseModel):
    """Single metric in export."""
    metric_type: str
    resource_id: Optional[str]
    count: int
    bytes_value: Optional[int]


class UsageExportResponse(BaseModel):
    """Response for usage export."""
    tenant_id: str
    period: str
    period_start: datetime
    period_end: datetime
    metrics: list[UsageExportMetric]
    totals: dict[str, int]
    generated_at: datetime


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/summary",
    response_model=UsageSummaryResponse,
    summary="Get usage summary",
)
async def get_usage_summary(
    tenant_id: str = Query(..., description="Tenant ID"),
    period: str = Query("day", description="Period: day, week, month"),
    from_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
):
    """
    Get usage summary for a tenant.

    Returns totals by metric type and breakdown by resource.

    Periods:
    - day: Current day (midnight to now)
    - week: Last 7 days
    - month: Current month (1st to now)
    """
    # Validate period
    valid_periods = ["day", "week", "month"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {valid_periods}",
        )

    async with get_db_session_context() as session:
        service = get_usage_metering_service(session)

        summary = await service.get_usage_summary(
            tenant_id=tenant_id,
            period=period,
            from_date=from_date,
            to_date=to_date,
        )

        return UsageSummaryResponse(
            tenant_id=summary.tenant_id,
            period=summary.period,
            period_start=summary.period_start,
            period_end=summary.period_end,
            totals=summary.totals,
            by_resource=summary.by_resource,
        )


@router.get(
    "/details",
    response_model=UsageDetailsResponse,
    summary="Get detailed usage",
)
async def get_usage_details(
    tenant_id: str = Query(..., description="Tenant ID"),
    metric_type: str = Query(..., description="Metric type: api_calls, exceptions, tool_executions, events, storage"),
    from_date: datetime = Query(..., description="Start date (ISO format)"),
    to_date: datetime = Query(..., description="End date (ISO format)"),
    resource_id: Optional[str] = Query(None, description="Filter by resource ID"),
):
    """
    Get detailed usage records for a specific metric type.

    Returns individual usage records within the date range.
    """
    # Validate metric type
    valid_types = ["api_calls", "exceptions", "tool_executions", "events", "storage"]
    if metric_type not in valid_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid metric_type. Must be one of: {valid_types}",
        )

    async with get_db_session_context() as session:
        service = get_usage_metering_service(session)

        details = await service.get_usage_details(
            tenant_id=tenant_id,
            metric_type=metric_type,
            from_date=from_date,
            to_date=to_date,
            resource_id=resource_id,
        )

        records = [
            UsageDetailRecord(
                metric_type=d.metric_type,
                resource_id=d.resource_id,
                period_start=d.period_start,
                period_end=d.period_end,
                count=d.count,
                bytes_value=d.bytes_value,
            )
            for d in details
        ]

        total_count = sum(d.count for d in details)

        return UsageDetailsResponse(
            tenant_id=tenant_id,
            metric_type=metric_type,
            from_date=from_date,
            to_date=to_date,
            records=records,
            total_count=total_count,
        )


@router.get(
    "/export",
    response_model=UsageExportResponse,
    summary="Export usage for billing",
)
async def export_usage(
    tenant_id: str = Query(..., description="Tenant ID"),
    period: str = Query("month", description="Period: day, week, month"),
    from_date: Optional[datetime] = Query(None, description="Start date (ISO format)"),
    to_date: Optional[datetime] = Query(None, description="End date (ISO format)"),
):
    """
    Export usage data for billing purposes.

    Returns aggregated usage by metric type and resource,
    suitable for generating billing reports.
    """
    # Validate period
    valid_periods = ["day", "week", "month"]
    if period not in valid_periods:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid period. Must be one of: {valid_periods}",
        )

    async with get_db_session_context() as session:
        service = get_usage_metering_service(session)

        export = await service.export_usage(
            tenant_id=tenant_id,
            period=period,
            from_date=from_date,
            to_date=to_date,
        )

        metrics = [
            UsageExportMetric(
                metric_type=m["metric_type"],
                resource_id=m["resource_id"],
                count=m["count"],
                bytes_value=m["bytes_value"],
            )
            for m in export.metrics
        ]

        return UsageExportResponse(
            tenant_id=export.tenant_id,
            period=export.period,
            period_start=export.period_start,
            period_end=export.period_end,
            metrics=metrics,
            totals=export.totals,
            generated_at=export.generated_at,
        )
