"""
Approval UI backend API for Phase 2.

Provides UI-friendly endpoints for approval dashboard.
Output derived from canonical schemas but formatted for UI consumption.

Matches specification from phase2-mvp-issues.md Issue 32.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query

from src.workflow.approval import ApprovalQueueRegistry, ApprovalStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui/approvals", tags=["ui-approvals"])


# Global approval queue registry (would be injected via dependency in production)
_approval_registry: ApprovalQueueRegistry | None = None


def set_approval_registry(registry: ApprovalQueueRegistry) -> None:
    """Set the approval queue registry (for dependency injection)."""
    global _approval_registry
    _approval_registry = registry


def get_approval_registry() -> ApprovalQueueRegistry:
    """Get the approval queue registry."""
    global _approval_registry
    if _approval_registry is None:
        from pathlib import Path
        _approval_registry = ApprovalQueueRegistry(storage_path=Path("./runtime/approvals"))
    return _approval_registry


@router.get("/{tenant_id}")
async def get_pending_approvals(
    tenant_id: str = Path(..., description="Tenant identifier"),
    status: str | None = Query(None, description="Filter by status (PENDING, APPROVED, REJECTED, etc.)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of approvals to return"),
) -> dict[str, Any]:
    """
    Get pending approvals for a tenant (UI-friendly format).
    
    Returns pending approvals with evidence and plan in a format suitable for UI display.
    Output derived from canonical ApprovalRequest schema but formatted for UI.
    
    Args:
        tenant_id: Tenant identifier
        status: Optional status filter (default: PENDING)
        limit: Maximum number of approvals to return
        
    Returns:
        Dictionary with UI-friendly approval data:
        {
            "tenantId": str,
            "approvals": [
                {
                    "approvalId": str,
                    "exceptionId": str,
                    "status": str,
                    "submittedAt": str,
                    "timeoutAt": str | null,
                    "plan": dict,  # Resolution plan
                    "evidence": list[str],  # Evidence from agents
                    "summary": str,  # UI-friendly summary
                },
                ...
            ],
            "total": int,
        }
    """
    registry = get_approval_registry()
    approval_queue = registry.get_or_create_queue(tenant_id)
    
    # Get approvals (filtered by status if provided)
    if status:
        try:
            status_enum = ApprovalStatus(status.upper())
            approvals = approval_queue.list_all(status=status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Valid values: PENDING, APPROVED, REJECTED, TIMED_OUT, ESCALATED"
            )
    else:
        # Default to pending approvals
        approvals = approval_queue.list_pending()
    
    # Limit results
    approvals = approvals[:limit]
    
    # Format for UI
    ui_approvals = []
    for approval in approvals:
        # Extract plan and evidence from approval
        plan = approval.plan
        evidence = approval.evidence
        
        # Generate UI-friendly summary
        summary = _generate_approval_summary(approval, plan, evidence)
        
        ui_approval = {
            "approvalId": approval.approval_id,
            "exceptionId": approval.exception_id,
            "status": approval.status.value,
            "submittedAt": approval.submitted_at.isoformat() if approval.submitted_at else None,
            "timeoutAt": approval.timeout_at.isoformat() if approval.timeout_at else None,
            "plan": plan,
            "evidence": evidence,
            "summary": summary,
        }
        
        # Add approval/rejection info if available
        if approval.approved_by:
            ui_approval["approvedBy"] = approval.approved_by
            ui_approval["approvedAt"] = approval.approved_at.isoformat() if approval.approved_at else None
            ui_approval["approvalComments"] = approval.approval_comments
        
        if approval.rejected_by:
            ui_approval["rejectedBy"] = approval.rejected_by
            ui_approval["rejectedAt"] = approval.rejected_at.isoformat() if approval.rejected_at else None
            ui_approval["rejectionComments"] = approval.rejection_comments
        
        if approval.escalated_at:
            ui_approval["escalatedAt"] = approval.escalated_at.isoformat()
            ui_approval["escalationReason"] = approval.escalation_reason
        
        ui_approvals.append(ui_approval)
    
    return {
        "tenantId": tenant_id,
        "approvals": ui_approvals,
        "total": len(ui_approvals),
    }


def _generate_approval_summary(
    approval: Any,
    plan: dict[str, Any],
    evidence: list[str],
) -> str:
    """
    Generate UI-friendly summary of approval request.
    
    Args:
        approval: ApprovalRequest
        plan: Resolution plan
        evidence: Evidence from agents
        
    Returns:
        Human-readable summary string
    """
    # Extract key information from plan
    plan_summary = "Resolution plan"
    if isinstance(plan, dict):
        resolved_plan = plan.get("resolvedPlan")
        if isinstance(resolved_plan, list):
            plan_summary = f"Resolution plan with {len(resolved_plan)} steps"
        elif resolved_plan:
            plan_summary = "Resolution plan available"
    
    # Extract exception info from plan if available
    exception_info = plan.get("exception", {})
    if isinstance(exception_info, dict):
        exception_type = exception_info.get("exceptionType", "Unknown")
        severity = exception_info.get("severity", "Unknown")
        plan_summary = f"{exception_type} ({severity}) - {plan_summary}"
    
    # Add evidence count
    evidence_count = len(evidence) if evidence else 0
    if evidence_count > 0:
        plan_summary += f" ({evidence_count} evidence items)"
    
    return plan_summary

