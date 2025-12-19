"""
Audit Report Repository for Phase 10 (P10-11 to P10-14).

Provides CRUD operations for audit report management with tenant isolation.

Reference: docs/phase10-ops-governance-mvp.md Section 8
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    AuditReport,
    AuditReportStatus,
    AuditReportType,
    AuditReportFormat,
)
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


def generate_report_id() -> str:
    """Generate a unique report ID."""
    return str(uuid.uuid4())


@dataclass
class AuditReportStats:
    """Statistics about audit reports for a tenant."""
    tenant_id: str
    total_reports: int
    pending_count: int
    generating_count: int
    completed_count: int
    failed_count: int
    by_report_type: dict[str, int]


class AuditReportRepository(AbstractBaseRepository[AuditReport]):
    """
    Repository for audit report management.

    Provides:
    - Create report requests
    - Get report by ID
    - List reports for a tenant
    - Update report status during generation
    - Mark reports as completed or failed

    All operations enforce tenant isolation.
    """

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[AuditReport]:
        """Get audit report by ID with tenant isolation."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(AuditReport)
            .where(AuditReport.id == id)
            .where(AuditReport.tenant_id == tenant_id)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[AuditReport]:
        """List audit reports for a tenant with pagination."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(AuditReport).where(AuditReport.tenant_id == tenant_id)

        # Apply filters
        if filters.get("status"):
            query = query.where(AuditReport.status == filters["status"])
        if filters.get("report_type"):
            query = query.where(AuditReport.report_type == filters["report_type"])
        if filters.get("requested_by"):
            query = query.where(AuditReport.requested_by == filters["requested_by"])

        # Order by created_at descending (newest first)
        query = query.order_by(desc(AuditReport.created_at))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_report(
        self,
        tenant_id: str,
        report_type: str,
        title: str,
        requested_by: str,
        format: str = "json",
        parameters: Optional[dict] = None,
    ) -> AuditReport:
        """
        Create a new audit report request.

        Args:
            tenant_id: Tenant identifier
            report_type: Type of report (exception_activity, tool_execution, etc.)
            title: Human-readable report title
            requested_by: User requesting the report
            format: Output format (json, csv, pdf)
            parameters: Report generation parameters

        Returns:
            Created AuditReport
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        report_id = generate_report_id()

        report = AuditReport(
            id=report_id,
            tenant_id=tenant_id,
            report_type=report_type,
            title=title,
            status="pending",
            format=format,
            parameters=parameters or {},
            requested_by=requested_by,
        )

        self.session.add(report)
        await self.session.flush()
        await self.session.refresh(report)

        logger.info(
            f"Created audit report: id={report_id}, tenant_id={tenant_id}, "
            f"report_type={report_type}"
        )

        return report

    async def start_generation(
        self,
        report_id: str,
        tenant_id: str,
    ) -> Optional[AuditReport]:
        """
        Mark report as generating.

        Args:
            report_id: Report ID
            tenant_id: Tenant identifier

        Returns:
            Updated AuditReport or None if not found
        """
        report = await self.get_by_id(report_id, tenant_id)
        if not report:
            return None

        if report.status != "pending":
            logger.warning(
                f"Cannot start generation for report {report_id}: status is {report.status}"
            )
            raise ValueError(f"Report is not pending (status: {report.status})")

        report.status = "generating"
        report.started_at = datetime.now(timezone.utc)

        await self.session.flush()
        await self.session.refresh(report)

        logger.info(f"Started generation for report: id={report_id}")

        return report

    async def complete_report(
        self,
        report_id: str,
        tenant_id: str,
        file_path: str,
        file_size_bytes: int,
        row_count: int,
        download_url: Optional[str] = None,
        download_expires_hours: int = 24,
    ) -> Optional[AuditReport]:
        """
        Mark report as completed with file details.

        Args:
            report_id: Report ID
            tenant_id: Tenant identifier
            file_path: Path to generated file
            file_size_bytes: Size of the file
            row_count: Number of rows/records
            download_url: Optional signed URL for download
            download_expires_hours: Hours until download URL expires

        Returns:
            Updated AuditReport or None if not found
        """
        report = await self.get_by_id(report_id, tenant_id)
        if not report:
            return None

        if report.status != "generating":
            logger.warning(
                f"Cannot complete report {report_id}: status is {report.status}"
            )
            raise ValueError(f"Report is not generating (status: {report.status})")

        report.status = "completed"
        report.completed_at = datetime.now(timezone.utc)
        report.file_path = file_path
        report.file_size_bytes = file_size_bytes
        report.row_count = row_count
        report.download_url = download_url
        if download_url:
            report.download_expires_at = datetime.now(timezone.utc) + timedelta(
                hours=download_expires_hours
            )

        await self.session.flush()
        await self.session.refresh(report)

        logger.info(
            f"Completed report: id={report_id}, file_path={file_path}, "
            f"row_count={row_count}"
        )

        return report

    async def fail_report(
        self,
        report_id: str,
        tenant_id: str,
        error_message: str,
    ) -> Optional[AuditReport]:
        """
        Mark report as failed.

        Args:
            report_id: Report ID
            tenant_id: Tenant identifier
            error_message: Error description

        Returns:
            Updated AuditReport or None if not found
        """
        report = await self.get_by_id(report_id, tenant_id)
        if not report:
            return None

        report.status = "failed"
        report.completed_at = datetime.now(timezone.utc)
        report.error_message = error_message

        await self.session.flush()
        await self.session.refresh(report)

        logger.error(f"Failed report: id={report_id}, error={error_message}")

        return report

    async def get_pending_reports(
        self,
        limit: int = 10,
    ) -> list[AuditReport]:
        """
        Get pending reports for processing (admin use, no tenant filter).

        Args:
            limit: Maximum number of reports to return

        Returns:
            List of pending AuditReports
        """
        query = (
            select(AuditReport)
            .where(AuditReport.status == "pending")
            .order_by(AuditReport.created_at)
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_stats(self, tenant_id: str) -> AuditReportStats:
        """
        Get statistics about audit reports for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            AuditReportStats with counts and breakdowns
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        # Get total count
        total_query = (
            select(func.count())
            .select_from(AuditReport)
            .where(AuditReport.tenant_id == tenant_id)
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        # Get counts by status
        status_query = (
            select(
                AuditReport.status,
                func.count().label("count"),
            )
            .where(AuditReport.tenant_id == tenant_id)
            .group_by(AuditReport.status)
        )
        status_result = await self.session.execute(status_query)
        status_counts = {row.status: row.count for row in status_result.fetchall()}

        # Get counts by report type
        type_query = (
            select(
                AuditReport.report_type,
                func.count().label("count"),
            )
            .where(AuditReport.tenant_id == tenant_id)
            .group_by(AuditReport.report_type)
        )
        type_result = await self.session.execute(type_query)
        type_counts = {row.report_type: row.count for row in type_result.fetchall()}

        return AuditReportStats(
            tenant_id=tenant_id,
            total_reports=total,
            pending_count=status_counts.get("pending", 0),
            generating_count=status_counts.get("generating", 0),
            completed_count=status_counts.get("completed", 0),
            failed_count=status_counts.get("failed", 0),
            by_report_type=type_counts,
        )

    async def cleanup_expired_reports(
        self,
        days_old: int = 30,
    ) -> int:
        """
        Clean up old completed/failed reports (admin use).

        Args:
            days_old: Delete reports older than this many days

        Returns:
            Number of reports deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_old)

        # First get the count
        count_query = (
            select(func.count())
            .select_from(AuditReport)
            .where(AuditReport.created_at < cutoff)
            .where(AuditReport.status.in_(["completed", "failed"]))
        )
        count_result = await self.session.execute(count_query)
        count = count_result.scalar() or 0

        if count > 0:
            # Delete the reports
            from sqlalchemy import delete
            delete_stmt = (
                delete(AuditReport)
                .where(AuditReport.created_at < cutoff)
                .where(AuditReport.status.in_(["completed", "failed"]))
            )
            await self.session.execute(delete_stmt)
            await self.session.flush()

            logger.info(f"Cleaned up {count} expired audit reports")

        return count
