"""
UI Status API for Phase 2.

Provides UI-friendly endpoints for exception status dashboard.
Output derived from canonical schemas but formatted for UI consumption.

Matches specification from phase2-mvp-issues.md Issue 32.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from src.models.exception_record import ResolutionStatus
from src.orchestrator.store import get_exception_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui/exceptions", tags=["ui-status"])


@router.get("/{tenant_id}")
async def get_recent_exceptions(
    tenant_id: str = Path(..., description="Tenant identifier"),
    status: str | None = Query(None, description="Filter by resolution status"),
    limit: int = Query(50, ge=1, le=1000, description="Maximum number of exceptions to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> dict[str, Any]:
    """
    Get recent exceptions for a tenant (UI-friendly format).
    
    Returns recent exceptions with statuses in a format suitable for UI display.
    Output derived from canonical ExceptionRecord schema but formatted for UI.
    
    Args:
        tenant_id: Tenant identifier
        status: Optional status filter (OPEN, IN_PROGRESS, RESOLVED, ESCALATED, PENDING_APPROVAL)
        limit: Maximum number of exceptions to return
        offset: Offset for pagination
        
    Returns:
        Dictionary with UI-friendly exception data:
        {
            "tenantId": str,
            "exceptions": [
                {
                    "exceptionId": str,
                    "exceptionType": str,
                    "severity": str,
                    "status": str,
                    "timestamp": str,
                    "sourceSystem": str,
                    "summary": str,  # UI-friendly summary
                    "lastUpdated": str,
                },
                ...
            ],
            "total": int,
            "offset": int,
            "limit": int,
        }
    """
    exception_store = get_exception_store()
    
    # Get all exceptions for tenant
    tenant_exceptions = exception_store.get_tenant_exceptions(tenant_id)
    
    # Filter by status if provided
    if status:
        try:
            status_enum = ResolutionStatus(status.upper())
            tenant_exceptions = [
                (exc, result) for exc, result in tenant_exceptions
                if exc.resolution_status == status_enum
            ]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: OPEN, IN_PROGRESS, RESOLVED, ESCALATED, PENDING_APPROVAL"
            )
    
    # Sort by timestamp (most recent first)
    tenant_exceptions.sort(
        key=lambda x: x[0].timestamp if x[0].timestamp else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    
    # Apply pagination
    total = len(tenant_exceptions)
    paginated_exceptions = tenant_exceptions[offset:offset + limit]
    
    # Format for UI
    ui_exceptions = []
    for exception, pipeline_result in paginated_exceptions:
        # Generate UI-friendly summary
        summary = _generate_exception_summary(exception, pipeline_result)
        
        # Determine last updated timestamp
        last_updated = exception.timestamp
        if pipeline_result and "stages" in pipeline_result:
            # Try to find latest stage timestamp
            stages = pipeline_result.get("stages", {})
            # Use feedback stage if available (last stage)
            if "feedback" in stages:
                feedback_stage = stages["feedback"]
                if isinstance(feedback_stage, dict) and "timestamp" in feedback_stage:
                    last_updated = datetime.fromisoformat(feedback_stage["timestamp"])
        
        ui_exception = {
            "exceptionId": exception.exception_id,
            "exceptionType": exception.exception_type or "UNKNOWN",
            "severity": exception.severity.value if exception.severity else "UNKNOWN",
            "status": exception.resolution_status.value,
            "timestamp": exception.timestamp.isoformat() if exception.timestamp else None,
            "sourceSystem": exception.source_system,
            "summary": summary,
            "lastUpdated": last_updated.isoformat() if isinstance(last_updated, datetime) else str(last_updated),
        }
        
        # Add pipeline result summary if available
        if pipeline_result:
            stages = pipeline_result.get("stages", {})
            if stages:
                ui_exception["stages"] = {
                    stage_name: {
                        "status": "completed" if "error" not in stage_data else "failed",
                        "hasError": "error" in stage_data,
                    }
                    for stage_name, stage_data in stages.items()
                }
        
        ui_exceptions.append(ui_exception)
    
    return {
        "tenantId": tenant_id,
        "exceptions": ui_exceptions,
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _generate_exception_summary(
    exception: Any,
    pipeline_result: dict[str, Any] | None,
) -> str:
    """
    Generate UI-friendly summary of exception.
    
    Args:
        exception: ExceptionRecord
        pipeline_result: Optional pipeline result
        
    Returns:
        Human-readable summary string
    """
    parts = []
    
    # Exception type and severity
    if exception.exception_type:
        parts.append(exception.exception_type)
    if exception.severity:
        parts.append(f"({exception.severity.value})")
    
    # Status
    parts.append(f"- {exception.resolution_status.value}")
    
    # Add pipeline info if available
    if pipeline_result:
        stages = pipeline_result.get("stages", {})
        if stages:
            completed_stages = [s for s in stages.keys() if "error" not in stages.get(s, {})]
            parts.append(f"[{len(completed_stages)}/{len(stages)} stages]")
    
    return " ".join(parts)

