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

# Changed prefix from /ui/exceptions to /ui/status to avoid conflict with router_operator's /ui/exceptions/{exception_id}
router = APIRouter(prefix="/ui/status", tags=["ui-status"])


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
    # Phase 6: Read from PostgreSQL
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        from src.repository.dto import ExceptionFilter
        from src.models.exception_record import ExceptionRecord, Severity, ResolutionStatus
        from datetime import datetime, timezone
        
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            
            # Build filter
            filters = ExceptionFilter()
            if status:
                # Map UI status to database status
                status_map = {
                    "OPEN": "open",
                    "IN_PROGRESS": "analyzing",
                    "RESOLVED": "resolved",
                    "ESCALATED": "escalated",
                    "PENDING_APPROVAL": "analyzing",
                }
                filters.status = status_map.get(status.upper())
            
            # List exceptions from PostgreSQL
            result = await repo.list_exceptions(
                tenant_id=tenant_id,
                filters=filters,
                page=(offset // limit) + 1 if limit > 0 else 1,
                page_size=limit,
            )
            
            # Convert database exceptions to ExceptionRecord format
            tenant_exceptions = []
            for db_exc in result.items:
                # Map severity
                severity_map = {
                    "low": Severity.LOW,
                    "medium": Severity.MEDIUM,
                    "high": Severity.HIGH,
                    "critical": Severity.CRITICAL,
                }
                severity = severity_map.get(
                    db_exc.severity.value if hasattr(db_exc.severity, 'value') else str(db_exc.severity).lower(),
                    Severity.MEDIUM
                )
                
                # Map status
                status_map = {
                    "open": ResolutionStatus.OPEN,
                    "analyzing": ResolutionStatus.IN_PROGRESS,
                    "resolved": ResolutionStatus.RESOLVED,
                    "escalated": ResolutionStatus.ESCALATED,
                }
                resolution_status = status_map.get(
                    db_exc.status.value if hasattr(db_exc.status, 'value') else str(db_exc.status).lower(),
                    ResolutionStatus.OPEN
                )
                
                # Build normalized context
                normalized_context = {"domain": db_exc.domain}
                if db_exc.entity:
                    normalized_context["entity"] = db_exc.entity
                
                # Create ExceptionRecord
                exception = ExceptionRecord(
                    exception_id=db_exc.exception_id,
                    tenant_id=db_exc.tenant_id,
                    source_system=db_exc.source_system,
                    exception_type=db_exc.type,
                    severity=severity,
                    timestamp=db_exc.created_at or datetime.now(timezone.utc),
                    raw_payload={},
                    normalized_context=normalized_context,
                    resolution_status=resolution_status,
                )
                
                # Create minimal pipeline result
                pipeline_result = {
                    "status": "COMPLETED" if resolution_status == ResolutionStatus.RESOLVED else "IN_PROGRESS",
                    "stages": {},
                }
                
                tenant_exceptions.append((exception, pipeline_result))
            
            total = result.total
    except Exception as e:
        logger.warning(f"Error reading from PostgreSQL, falling back to in-memory store: {e}")
        # Fallback to in-memory store
        exception_store = get_exception_store()
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
        
        total = len(tenant_exceptions)
    
    # Sort by timestamp (most recent first) - only if not already sorted by DB
    tenant_exceptions.sort(
        key=lambda x: x[0].timestamp if x[0].timestamp else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    
    # Apply pagination (if not already paginated by DB)
    if offset > 0 or len(tenant_exceptions) > limit:
        paginated_exceptions = tenant_exceptions[offset:offset + limit]
    else:
        paginated_exceptions = tenant_exceptions
    
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
        
        # Extract domain from normalized_context
        domain = exception.normalized_context.get("domain") if exception.normalized_context else None
        
        ui_exception = {
            "exceptionId": exception.exception_id,
            "exceptionType": exception.exception_type or "UNKNOWN",
            "severity": exception.severity.value if exception.severity else "UNKNOWN",
            "status": exception.resolution_status.value,
            "timestamp": exception.timestamp.isoformat() if exception.timestamp else None,
            "sourceSystem": exception.source_system,
            "domain": domain,  # Add domain to UI response
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

