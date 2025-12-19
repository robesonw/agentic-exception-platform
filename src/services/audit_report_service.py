"""
Audit Report Service for Phase 10 (P10-11 to P10-14).

Provides report generation logic for various audit report types:
- Exception Activity
- Tool Execution
- Policy Decisions
- Config Changes
- SLA Compliance

Reference: docs/phase10-ops-governance-mvp.md Section 8
"""

import csv
import io
import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    AuditReport,
    Exception as ExceptionModel,
    ExceptionEvent,
    ToolExecution,
    ConfigChangeRequest,
)

logger = logging.getLogger(__name__)


# Default reports directory
REPORTS_DIR = Path(os.environ.get("REPORTS_DIR", "./reports"))


@dataclass
class ReportGenerationResult:
    """Result of report generation."""
    success: bool
    file_path: Optional[str] = None
    file_size_bytes: int = 0
    row_count: int = 0
    error_message: Optional[str] = None


class AuditReportService:
    """
    Service for generating audit reports.

    Generates reports in JSON, CSV, or PDF format based on report type
    and parameters.
    """

    def __init__(self, session: AsyncSession):
        """Initialize the service with a database session."""
        self.session = session
        self._ensure_reports_dir()

    def _ensure_reports_dir(self) -> None:
        """Ensure reports directory exists."""
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    async def generate_report(
        self,
        report: AuditReport,
    ) -> ReportGenerationResult:
        """
        Generate a report based on its type and parameters.

        Args:
            report: AuditReport with type, format, and parameters

        Returns:
            ReportGenerationResult with file details or error
        """
        try:
            # Route to appropriate generator
            if report.report_type == "exception_activity":
                return await self._generate_exception_activity_report(report)
            elif report.report_type == "tool_execution":
                return await self._generate_tool_execution_report(report)
            elif report.report_type == "policy_decisions":
                return await self._generate_policy_decisions_report(report)
            elif report.report_type == "config_changes":
                return await self._generate_config_changes_report(report)
            elif report.report_type == "sla_compliance":
                return await self._generate_sla_compliance_report(report)
            else:
                return ReportGenerationResult(
                    success=False,
                    error_message=f"Unknown report type: {report.report_type}",
                )
        except Exception as e:
            logger.exception(f"Error generating report {report.id}: {e}")
            return ReportGenerationResult(
                success=False,
                error_message=str(e),
            )

    async def _generate_exception_activity_report(
        self,
        report: AuditReport,
    ) -> ReportGenerationResult:
        """Generate exception activity report."""
        params = report.parameters or {}
        from_date = self._parse_date(params.get("from_date"))
        to_date = self._parse_date(params.get("to_date"))

        # Build query
        query = (
            select(ExceptionModel)
            .where(ExceptionModel.tenant_id == report.tenant_id)
        )

        if from_date:
            query = query.where(ExceptionModel.created_at >= from_date)
        if to_date:
            query = query.where(ExceptionModel.created_at <= to_date)

        query = query.order_by(ExceptionModel.created_at.desc())

        result = await self.session.execute(query)
        exceptions = result.scalars().all()

        # Convert to report format
        data = []
        for exc in exceptions:
            data.append({
                "exception_id": exc.exception_id,
                "tenant_id": exc.tenant_id,
                "domain": exc.domain,
                "type": exc.type,
                "severity": exc.severity.value if exc.severity else None,
                "status": exc.status.value if exc.status else None,
                "source_system": exc.source_system,
                "entity": exc.entity,
                "owner": exc.owner,
                "sla_deadline": exc.sla_deadline.isoformat() if exc.sla_deadline else None,
                "created_at": exc.created_at.isoformat() if exc.created_at else None,
                "updated_at": exc.updated_at.isoformat() if exc.updated_at else None,
            })

        return await self._write_report(report, data)

    async def _generate_tool_execution_report(
        self,
        report: AuditReport,
    ) -> ReportGenerationResult:
        """Generate tool execution report."""
        params = report.parameters or {}
        from_date = self._parse_date(params.get("from_date"))
        to_date = self._parse_date(params.get("to_date"))

        # Build query
        query = (
            select(ToolExecution)
            .where(ToolExecution.tenant_id == report.tenant_id)
        )

        if from_date:
            query = query.where(ToolExecution.created_at >= from_date)
        if to_date:
            query = query.where(ToolExecution.created_at <= to_date)

        query = query.order_by(ToolExecution.created_at.desc())

        result = await self.session.execute(query)
        executions = result.scalars().all()

        # Convert to report format
        data = []
        for exec in executions:
            data.append({
                "id": str(exec.id),
                "tenant_id": exec.tenant_id,
                "tool_id": exec.tool_id,
                "exception_id": exec.exception_id,
                "status": exec.status.value if exec.status else None,
                "requested_by_actor_type": exec.requested_by_actor_type.value if exec.requested_by_actor_type else None,
                "requested_by_actor_id": exec.requested_by_actor_id,
                "input_payload": exec.input_payload,
                "output_payload": exec.output_payload,
                "error_message": exec.error_message,
                "created_at": exec.created_at.isoformat() if exec.created_at else None,
                "updated_at": exec.updated_at.isoformat() if exec.updated_at else None,
            })

        return await self._write_report(report, data)

    async def _generate_policy_decisions_report(
        self,
        report: AuditReport,
    ) -> ReportGenerationResult:
        """Generate policy decisions report from exception events."""
        params = report.parameters or {}
        from_date = self._parse_date(params.get("from_date"))
        to_date = self._parse_date(params.get("to_date"))

        # Build query for policy-related events
        policy_event_types = [
            "PolicyEvaluated",
            "TriageCompleted",
            "ActionTaken",
            "EscalationTriggered",
        ]

        query = (
            select(ExceptionEvent)
            .where(ExceptionEvent.tenant_id == report.tenant_id)
            .where(ExceptionEvent.event_type.in_(policy_event_types))
        )

        if from_date:
            query = query.where(ExceptionEvent.created_at >= from_date)
        if to_date:
            query = query.where(ExceptionEvent.created_at <= to_date)

        query = query.order_by(ExceptionEvent.created_at.desc())

        result = await self.session.execute(query)
        events = result.scalars().all()

        # Convert to report format
        data = []
        for event in events:
            data.append({
                "event_id": str(event.event_id),
                "exception_id": event.exception_id,
                "tenant_id": event.tenant_id,
                "event_type": event.event_type,
                "actor_type": event.actor_type.value if event.actor_type else None,
                "actor_id": event.actor_id,
                "payload": event.payload,
                "created_at": event.created_at.isoformat() if event.created_at else None,
            })

        return await self._write_report(report, data)

    async def _generate_config_changes_report(
        self,
        report: AuditReport,
    ) -> ReportGenerationResult:
        """Generate config changes report."""
        params = report.parameters or {}
        from_date = self._parse_date(params.get("from_date"))
        to_date = self._parse_date(params.get("to_date"))

        # Build query
        query = (
            select(ConfigChangeRequest)
            .where(ConfigChangeRequest.tenant_id == report.tenant_id)
        )

        if from_date:
            query = query.where(ConfigChangeRequest.requested_at >= from_date)
        if to_date:
            query = query.where(ConfigChangeRequest.requested_at <= to_date)

        query = query.order_by(ConfigChangeRequest.requested_at.desc())

        result = await self.session.execute(query)
        changes = result.scalars().all()

        # Convert to report format
        data = []
        for change in changes:
            data.append({
                "id": change.id,
                "tenant_id": change.tenant_id,
                "change_type": change.change_type,
                "resource_id": change.resource_id,
                "resource_name": change.resource_name,
                "status": change.status,
                "requested_by": change.requested_by,
                "requested_at": change.requested_at.isoformat() if change.requested_at else None,
                "reviewed_by": change.reviewed_by,
                "reviewed_at": change.reviewed_at.isoformat() if change.reviewed_at else None,
                "review_comment": change.review_comment,
                "applied_at": change.applied_at.isoformat() if change.applied_at else None,
                "applied_by": change.applied_by,
                "diff_summary": change.diff_summary,
                "change_reason": change.change_reason,
            })

        return await self._write_report(report, data)

    async def _generate_sla_compliance_report(
        self,
        report: AuditReport,
    ) -> ReportGenerationResult:
        """Generate SLA compliance report."""
        params = report.parameters or {}
        from_date = self._parse_date(params.get("from_date"))
        to_date = self._parse_date(params.get("to_date"))

        # Build query for exceptions with SLA data
        query = (
            select(ExceptionModel)
            .where(ExceptionModel.tenant_id == report.tenant_id)
            .where(ExceptionModel.sla_deadline.isnot(None))
        )

        if from_date:
            query = query.where(ExceptionModel.created_at >= from_date)
        if to_date:
            query = query.where(ExceptionModel.created_at <= to_date)

        result = await self.session.execute(query)
        exceptions = result.scalars().all()

        # Calculate SLA metrics
        total = len(exceptions)
        breached = 0
        met = 0
        pending = 0
        now = datetime.now(timezone.utc)

        data = []
        for exc in exceptions:
            sla_deadline = exc.sla_deadline
            resolved_at = exc.updated_at if exc.status and exc.status.value == "resolved" else None

            if resolved_at and sla_deadline:
                if resolved_at <= sla_deadline:
                    sla_status = "met"
                    met += 1
                else:
                    sla_status = "breached"
                    breached += 1
            elif sla_deadline and sla_deadline < now:
                sla_status = "breached"
                breached += 1
            else:
                sla_status = "pending"
                pending += 1

            data.append({
                "exception_id": exc.exception_id,
                "domain": exc.domain,
                "type": exc.type,
                "severity": exc.severity.value if exc.severity else None,
                "status": exc.status.value if exc.status else None,
                "sla_deadline": sla_deadline.isoformat() if sla_deadline else None,
                "resolved_at": resolved_at.isoformat() if resolved_at else None,
                "sla_status": sla_status,
                "created_at": exc.created_at.isoformat() if exc.created_at else None,
            })

        # Add summary at the beginning
        summary = {
            "_summary": {
                "total_with_sla": total,
                "met": met,
                "breached": breached,
                "pending": pending,
                "compliance_rate_percent": round((met / total) * 100, 2) if total > 0 else 0,
            }
        }

        # For JSON format, include summary; for CSV, just the data
        if report.format == "json":
            output_data = {"summary": summary["_summary"], "details": data}
        else:
            output_data = data

        return await self._write_report(report, output_data if report.format != "json" else [output_data])

    async def _write_report(
        self,
        report: AuditReport,
        data: list[dict] | dict,
    ) -> ReportGenerationResult:
        """Write report data to file in the specified format."""
        file_name = f"{report.id}.{report.format}"
        file_path = REPORTS_DIR / file_name

        try:
            if report.format == "json":
                content = json.dumps(data, indent=2, default=str)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                row_count = len(data) if isinstance(data, list) else 1

            elif report.format == "csv":
                if not data or (isinstance(data, list) and len(data) == 0):
                    # Empty report
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write("")
                    return ReportGenerationResult(
                        success=True,
                        file_path=str(file_path),
                        file_size_bytes=0,
                        row_count=0,
                    )

                # Get headers from first item
                if isinstance(data, list):
                    headers = list(data[0].keys()) if data else []
                    rows = data
                else:
                    headers = list(data.keys())
                    rows = [data]

                with open(file_path, "w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(f, fieldnames=headers)
                    writer.writeheader()
                    for row in rows:
                        # Convert non-string values to strings
                        cleaned_row = {
                            k: json.dumps(v) if isinstance(v, (dict, list)) else v
                            for k, v in row.items()
                        }
                        writer.writerow(cleaned_row)
                row_count = len(rows)

            else:
                # PDF not implemented yet - fall back to JSON
                logger.warning(f"PDF format not implemented, falling back to JSON for report {report.id}")
                content = json.dumps(data, indent=2, default=str)
                file_path = REPORTS_DIR / f"{report.id}.json"
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                row_count = len(data) if isinstance(data, list) else 1

            file_size = file_path.stat().st_size

            return ReportGenerationResult(
                success=True,
                file_path=str(file_path),
                file_size_bytes=file_size,
                row_count=row_count,
            )

        except Exception as e:
            logger.exception(f"Error writing report {report.id}: {e}")
            return ReportGenerationResult(
                success=False,
                error_message=str(e),
            )

    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None

        try:
            # Try ISO format first
            if "T" in date_str:
                return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            else:
                # Assume YYYY-MM-DD format
                return datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            logger.warning(f"Could not parse date: {date_str}")
            return None


# Singleton instance
_audit_report_service: Optional[AuditReportService] = None


def get_audit_report_service(session: AsyncSession) -> AuditReportService:
    """Get or create the audit report service."""
    return AuditReportService(session)
