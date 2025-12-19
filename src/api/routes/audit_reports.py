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
from pathlib import Path
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
    report_type: Optional[str] = Field(
        None,
        description="Type: exception_activity, tool_execution, policy_decisions, config_changes, sla_compliance",
    )
    reportType: Optional[str] = Field(
        None,
        description="Type (camelCase for frontend): exception_activity, tool_execution, policy_decisions, config_changes, sla_compliance",
    )
    title: Optional[str] = Field(None, description="Human-readable report title")
    format: str = Field("json", description="Output format: json, csv, pdf")
    parameters: Optional[dict] = Field(
        None,
        description="Report parameters (from_date, to_date, filters)",
    )
    # Frontend fields
    domain: Optional[str] = Field(None, description="Domain filter (optional)")
    dateFrom: Optional[str] = Field(None, description="Start date (YYYY-MM-DD)")
    dateTo: Optional[str] = Field(None, description="End date (YYYY-MM-DD)")


class ReportResponse(BaseModel):
    """Response for a report."""
    id: str
    reportId: Optional[str] = Field(None, description="Report ID (same as id, for frontend compatibility)")
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
        populate_by_name = True  # Allow both id and reportId


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
        reportId=report.id,  # Also set reportId explicitly for frontend
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


def _normalize_report_request(request: ReportGenerateRequest) -> dict:
    """Normalize frontend request to backend format."""
    # Get report_type from either field
    report_type = request.report_type or request.reportType
    if not report_type:
        raise ValueError("report_type or reportType is required")
    
    # Build parameters dict from frontend fields
    parameters = request.parameters or {}
    if request.dateFrom:
        parameters["from_date"] = request.dateFrom
    if request.dateTo:
        parameters["to_date"] = request.dateTo
    if request.domain:
        parameters["domain"] = request.domain
    
    # Generate title if not provided
    title = request.title
    if not title:
        # Create a title from report type
        type_titles = {
            "exception_activity": "Exception Activity Report",
            "tool_execution": "Tool Execution Report",
            "policy_decisions": "Policy Decisions Report",
            "config_changes": "Config Changes Report",
            "sla_compliance": "SLA Compliance Report",
        }
        title = type_titles.get(report_type, f"{report_type.replace('_', ' ').title()} Report")
        if request.dateFrom or request.dateTo:
            date_range = []
            if request.dateFrom:
                date_range.append(f"From {request.dateFrom}")
            if request.dateTo:
                date_range.append(f"To {request.dateTo}")
            if date_range:
                title += f" ({', '.join(date_range)})"
    
    return {
        "report_type": report_type,
        "title": title,
        "format": request.format,
        "parameters": parameters if parameters else None,
    }


@router.post(
    "",
    response_model=ReportResponse,
    status_code=http_status.HTTP_202_ACCEPTED,
    summary="Generate a new audit report",
)
async def generate_report(
    request: ReportGenerateRequest,
    tenant_id: str = Query(..., description="Tenant ID"),
    requested_by: str = Query("system", description="User requesting the report"),
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

    Parameters (in request.parameters or via dateFrom/dateTo):
    - from_date: Start date (ISO format or YYYY-MM-DD)
    - to_date: End date (ISO format or YYYY-MM-DD)
    - domain: Domain filter (optional)
    """
    try:
        normalized = _normalize_report_request(request)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    
    # Validate report type
    valid_types = [
        "exception_activity",
        "tool_execution",
        "policy_decisions",
        "config_changes",
        "sla_compliance",
    ]
    if normalized["report_type"] not in valid_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid report_type. Must be one of: {valid_types}",
        )

    # Validate format
    valid_formats = ["json", "csv", "pdf"]
    if normalized["format"] not in valid_formats:
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
            report_type=normalized["report_type"],
            title=normalized["title"],
            requested_by=requested_by,
            format=normalized["format"],
            parameters=normalized["parameters"],
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
            f"id={report.id}, type={normalized['report_type']}"
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
    page: Optional[int] = Query(None, ge=1, description="Page number (alternative to limit/offset)"),
    page_size: Optional[int] = Query(None, ge=1, le=100, description="Items per page (alternative to limit/offset)"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="Maximum number of results"),
    offset: Optional[int] = Query(None, ge=0, description="Number of results to skip"),
):
    """List audit reports for a tenant."""
    # Support both page/page_size and limit/offset pagination
    if limit is not None and offset is not None:
        # Convert limit/offset to page/page_size
        page = (offset // limit) + 1 if limit > 0 else 1
        page_size = limit
    else:
        # Use defaults if not provided
        page = page or 1
        page_size = page_size or 50
    
    try:
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
    except Exception as e:
        # Check if it's a table doesn't exist error
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "no such table" in error_msg or "relation" in error_msg:
            logger.warning(f"Audit reports table may not exist yet: {e}. Returning empty results.")
            return PaginatedReportResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
                total_pages=0,
            )
        logger.error(f"Failed to list audit reports: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list audit reports: {str(e)}",
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
    logger.info(f"Download request for report_id={report_id}, tenant_id={tenant_id}")
    try:
        async with get_db_session_context() as session:
            repo = AuditReportRepository(session)
            report = await repo.get_by_id(report_id, tenant_id)

            if not report:
                logger.warning(f"Report not found: report_id={report_id}, tenant_id={tenant_id}")
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

            # Convert file_path to Path object and resolve to absolute path
            file_path = Path(report.file_path)
            # Resolve relative paths (e.g., "./reports/file.json") to absolute paths
            if not file_path.is_absolute():
                file_path = file_path.resolve()
            
            if not file_path.exists():
                logger.error(f"Report file does not exist at path: {file_path} (resolved from {report.file_path})")
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Report file not found at path: {report.file_path}",
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

            logger.info(f"Serving report file: {file_path} (size: {file_path.stat().st_size} bytes)")
            return FileResponse(
                path=str(file_path),  # FileResponse accepts string path
                media_type=media_type,
                filename=filename,
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error downloading report {report_id}: {e}")
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error downloading report: {str(e)}",
        )
