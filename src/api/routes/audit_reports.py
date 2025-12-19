"""
Audit Reports API Routes for Phase 10 (P10-11 to P10-14).

Provides endpoints for generating and managing audit reports:
- Generate reports (async)
- Get report status and download URL
- List generated reports

Reference: docs/phase10-ops-governance-mvp.md Section 8
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status as http_status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.audit_report_repository import (
    AuditReportRepository,
    AuditReportStats,
)
from src.services.audit_report_service import (
    AuditReportService,
    get_audit_report_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/audit/reports", tags=["audit-reports"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ReportGenerateRequest(BaseModel):
    """Request to generate a new report."""
    report_type: str = Field(
        ...,
        description="Type: exception_activity, tool_execution, policy_decisions, config_changes, sla_compliance",
    )
    title: str = Field(..., description="Human-readable report title")
    format: str = Field("json", description="Output format: json, csv, pdf")
    parameters: Optional[dict] = Field(
        None,
        description="Report parameters (from_date, to_date, filters)",
    )


class ReportResponse(BaseModel):
    """Response for a report."""
    id: str
    tenant_id: str
    report_type: str
    title: str
    status: str
    format: str
    parameters: Optional[dict]
    file_size_bytes: Optional[int]
    row_count: Optional[int]
    download_url: Optional[str]
    download_expires_at: Optional[datetime]
    error_message: Optional[str]
    requested_by: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ReportStatsResponse(BaseModel):
    """Response for report statistics."""
    tenant_id: str
    total_reports: int
    pending_count: int
    generating_count: int
    completed_count: int
    failed_count: int
    by_report_type: dict[str, int]


class PaginatedReportResponse(BaseModel):
    """Paginated list of reports."""
    items: list[ReportResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Helper Functions
# =============================================================================


def _to_response(report) -> ReportResponse:
    """Convert model to response."""
    return ReportResponse(
        id=report.id,
        tenant_id=report.tenant_id,
        report_type=report.report_type,
        title=report.title,
        status=report.status,
        format=report.format,
        parameters=report.parameters,
        file_size_bytes=report.file_size_bytes,
        row_count=report.row_count,
        download_url=report.download_url,
        download_expires_at=report.download_expires_at,
        error_message=report.error_message,
        requested_by=report.requested_by,
        started_at=report.started_at,
        completed_at=report.completed_at,
        created_at=report.created_at,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=ReportResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
    summary="Generate a new audit report",
)
async def generate_report(
    request: ReportGenerateRequest,
    tenant_id: str = Query(..., description="Tenant ID"),
    requested_by: str = Query(..., description="User requesting the report"),
):
    """
    Generate a new audit report (async).

    The report will be generated asynchronously. Poll the GET endpoint
    to check status and get the download URL when complete.

    Report types:
    - exception_activity: All exceptions with status changes
    - tool_execution: All tool executions with outcomes
    - policy_decisions: All policy evaluations with actions
    - config_changes: All config change requests and outcomes
    - sla_compliance: SLA metrics summary

    Parameters (in request.parameters):
    - from_date: Start date (ISO format or YYYY-MM-DD)
    - to_date: End date (ISO format or YYYY-MM-DD)
    """
    # Validate report type
    valid_types = [
        "exception_activity",
        "tool_execution",
        "policy_decisions",
        "config_changes",
        "sla_compliance",
    ]
    if request.report_type not in valid_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report_type. Must be one of: {valid_types}",
        )

    # Validate format
    valid_formats = ["json", "csv", "pdf"]
    if request.format not in valid_formats:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid format. Must be one of: {valid_formats}",
        )

    async with get_db_session_context() as session:
        repo = AuditReportRepository(session)
        service = get_audit_report_service(session)

        # Create the report record
        report = await repo.create_report(
            tenant_id=tenant_id,
            report_type=request.report_type,
            title=request.title,
            requested_by=requested_by,
            format=request.format,
            parameters=request.parameters,
        )

        await session.commit()

        # For MVP, generate synchronously (in production, this would be a background task)
        # Start generation
        report = await repo.start_generation(report.id, tenant_id)
        await session.commit()

        # Generate the report
        result = await service.generate_report(report)

        if result.success:
            # Mark as completed
            report = await repo.complete_report(
                report_id=report.id,
                tenant_id=tenant_id,
                file_path=result.file_path,
                file_size_bytes=result.file_size_bytes,
                row_count=result.row_count,
                download_url=f"/audit/reports/{report.id}/download",
            )
        else:
            # Mark as failed
            report = await repo.fail_report(
                report_id=report.id,
                tenant_id=tenant_id,
                error_message=result.error_message,
            )

        await session.commit()

        logger.info(
            f"Report generation {'completed' if result.success else 'failed'}: "
            f"id={report.id}, type={request.report_type}"
        )

        return _to_response(report)


@router.get(
    "",
    response_model=PaginatedReportResponse,
    summary="List audit reports",
)
async def list_reports(
    tenant_id: str = Query(..., description="Tenant ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    report_type: Optional[str] = Query(None, description="Filter by report type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """List audit reports for a tenant."""
    async with get_db_session_context() as session:
        repo = AuditReportRepository(session)

        filters = {}
        if status:
            filters["status"] = status
        if report_type:
            filters["report_type"] = report_type

        result = await repo.list_by_tenant(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            **filters,
        )

        return PaginatedReportResponse(
            items=[_to_response(r) for r in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )


@router.get(
    "/stats",
    response_model=ReportStatsResponse,
    summary="Get report statistics",
)
async def get_report_stats(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """Get statistics about audit reports for a tenant."""
    async with get_db_session_context() as session:
        repo = AuditReportRepository(session)
        stats = await repo.get_stats(tenant_id)

        return ReportStatsResponse(
            tenant_id=stats.tenant_id,
            total_reports=stats.total_reports,
            pending_count=stats.pending_count,
            generating_count=stats.generating_count,
            completed_count=stats.completed_count,
            failed_count=stats.failed_count,
            by_report_type=stats.by_report_type,
        )


@router.get(
    "/{report_id}",
    response_model=ReportResponse,
    summary="Get report details",
)
async def get_report(
    report_id: str,
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """Get details of a specific audit report."""
    async with get_db_session_context() as session:
        repo = AuditReportRepository(session)
        report = await repo.get_by_id(report_id, tenant_id)

        if not report:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Report not found: {report_id}",
            )

        return _to_response(report)


@router.get(
    "/{report_id}/download",
    summary="Download a completed report",
)
async def download_report(
    report_id: str,
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """
    Download a completed audit report.

    Returns the report file for download.
    """
    async with get_db_session_context() as session:
        repo = AuditReportRepository(session)
        report = await repo.get_by_id(report_id, tenant_id)

        if not report:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Report not found: {report_id}",
            )

        if report.status != "completed":
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Report is not ready for download (status: {report.status})",
            )

        if not report.file_path:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail="Report file not found",
            )

        # Determine media type
        media_type_map = {
            "json": "application/json",
            "csv": "text/csv",
            "pdf": "application/pdf",
        }
        media_type = media_type_map.get(report.format, "application/octet-stream")

        # Generate filename
        safe_title = "".join(c if c.isalnum() or c in "._- " else "_" for c in report.title)
        filename = f"{safe_title}.{report.format}"

        return FileResponse(
            path=report.file_path,
            media_type=media_type,
            filename=filename,
        )
