"""
API routes for human-in-the-loop approval workflow.

Phase 2: Approval workflow endpoints.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.workflow.approval import ApprovalQueueRegistry, ApprovalStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/approvals", tags=["approvals"])


class ApprovalRequest(BaseModel):
    """Request body for submitting approval."""

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    plan: dict[str, Any] = Field(..., description="Resolution plan")
    evidence: list[str] = Field(default_factory=list, description="Evidence from agents")
    timeout_minutes: int = Field(60, alias="timeoutMinutes", description="Timeout in minutes")


class ApprovalActionRequest(BaseModel):
    """Request body for approve/reject actions."""

    user: str = Field(..., description="User performing the action")
    comments: str | None = Field(None, description="Optional comments")


class ApprovalResponse(BaseModel):
    """Response for approval operations."""

    approval_id: str = Field(..., alias="approvalId")
    tenant_id: str = Field(..., alias="tenantId")
    exception_id: str = Field(..., alias="exceptionId")
    status: str
    submitted_at: str = Field(..., alias="submittedAt")
    timeout_at: str | None = Field(None, alias="timeoutAt")
    approved_by: str | None = Field(None, alias="approvedBy")
    rejected_by: str | None = Field(None, alias="rejectedBy")
    approved_at: str | None = Field(None, alias="approvedAt")
    rejected_at: str | None = Field(None, alias="rejectedAt")
    approval_comments: str | None = Field(None, alias="approvalComments")
    rejection_comments: str | None = Field(None, alias="rejectionComments")


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


@router.post("/{tenant_id}", response_model=ApprovalResponse)
async def submit_approval(
    tenant_id: str = Path(..., description="Tenant identifier"),
    request: ApprovalRequest = ...,
) -> ApprovalResponse:
    """
    Submit a resolution plan for human approval.
    
    Args:
        tenant_id: Tenant identifier
        request: Approval request body
        
    Returns:
        ApprovalResponse with approval details
    """
    registry = get_approval_registry()
    approval_queue = registry.get_or_create_queue(tenant_id)
    
    approval_id = approval_queue.submit_for_approval(
        exception_id=request.exception_id,
        plan=request.plan,
        evidence=request.evidence,
        timeout_minutes=request.timeout_minutes,
    )
    
    approval = approval_queue.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    
    return ApprovalResponse(
        approvalId=approval.approval_id,
        tenantId=approval.tenant_id,
        exceptionId=approval.exception_id,
        status=approval.status.value,
        submittedAt=approval.submitted_at.isoformat(),
        timeoutAt=approval.timeout_at.isoformat() if approval.timeout_at else None,
        approvedBy=approval.approved_by,
        rejectedBy=approval.rejected_by,
        approvedAt=approval.approved_at.isoformat() if approval.approved_at else None,
        rejectedAt=approval.rejected_at.isoformat() if approval.rejected_at else None,
        approvalComments=approval.approval_comments,
        rejectionComments=approval.rejection_comments,
    )


@router.get("/{tenant_id}", response_model=list[ApprovalResponse])
async def list_approvals(
    tenant_id: str = Path(..., description="Tenant identifier"),
    status: str | None = Query(None, description="Filter by status (PENDING, APPROVED, REJECTED, etc.)"),
) -> list[ApprovalResponse]:
    """
    List approvals for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        status: Optional status filter
        
    Returns:
        List of ApprovalResponse objects
    """
    # Validate status filter first if provided
    status_filter = None
    if status:
        try:
            status_filter = ApprovalStatus(status.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    registry = get_approval_registry()
    approval_queue = registry.get_queue(tenant_id)
    
    if not approval_queue:
        return []
    
    approvals = approval_queue.list_all(status=status_filter)
    
    return [
        ApprovalResponse(
            approvalId=approval.approval_id,
            tenantId=approval.tenant_id,
            exceptionId=approval.exception_id,
            status=approval.status.value,
            submittedAt=approval.submitted_at.isoformat(),
            timeoutAt=approval.timeout_at.isoformat() if approval.timeout_at else None,
            approvedBy=approval.approved_by,
            rejectedBy=approval.rejected_by,
            approvedAt=approval.approved_at.isoformat() if approval.approved_at else None,
            rejectedAt=approval.rejected_at.isoformat() if approval.rejected_at else None,
            approvalComments=approval.approval_comments,
            rejectionComments=approval.rejection_comments,
        )
        for approval in approvals
    ]


@router.post("/{tenant_id}/{approval_id}/approve", response_model=ApprovalResponse)
async def approve_request(
    tenant_id: str = Path(..., description="Tenant identifier"),
    approval_id: str = Path(..., description="Approval identifier"),
    request: ApprovalActionRequest = ...,
) -> ApprovalResponse:
    """
    Approve a pending request.
    
    Args:
        tenant_id: Tenant identifier
        approval_id: Approval identifier
        request: Approval action request
        
    Returns:
        Updated ApprovalResponse
    """
    registry = get_approval_registry()
    approval_queue = registry.get_queue(tenant_id)
    
    if not approval_queue:
        raise HTTPException(status_code=404, detail=f"Approval queue not found for tenant {tenant_id}")
    
    try:
        approval = approval_queue.approve(
            approval_id=approval_id,
            user=request.user,
            comments=request.comments,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return ApprovalResponse(
        approvalId=approval.approval_id,
        tenantId=approval.tenant_id,
        exceptionId=approval.exception_id,
        status=approval.status.value,
        submittedAt=approval.submitted_at.isoformat(),
        timeoutAt=approval.timeout_at.isoformat() if approval.timeout_at else None,
        approvedBy=approval.approved_by,
        rejectedBy=approval.rejected_by,
        approvedAt=approval.approved_at.isoformat() if approval.approved_at else None,
        rejectedAt=approval.rejected_at.isoformat() if approval.rejected_at else None,
        approvalComments=approval.approval_comments,
        rejectionComments=approval.rejection_comments,
    )


@router.post("/{tenant_id}/{approval_id}/reject", response_model=ApprovalResponse)
async def reject_request(
    tenant_id: str = Path(..., description="Tenant identifier"),
    approval_id: str = Path(..., description="Approval identifier"),
    request: ApprovalActionRequest = ...,
) -> ApprovalResponse:
    """
    Reject a pending request.
    
    Args:
        tenant_id: Tenant identifier
        approval_id: Approval identifier
        request: Approval action request
        
    Returns:
        Updated ApprovalResponse
    """
    registry = get_approval_registry()
    approval_queue = registry.get_queue(tenant_id)
    
    if not approval_queue:
        raise HTTPException(status_code=404, detail=f"Approval queue not found for tenant {tenant_id}")
    
    try:
        approval = approval_queue.reject(
            approval_id=approval_id,
            user=request.user,
            comments=request.comments,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    
    return ApprovalResponse(
        approvalId=approval.approval_id,
        tenantId=approval.tenant_id,
        exceptionId=approval.exception_id,
        status=approval.status.value,
        submittedAt=approval.submitted_at.isoformat(),
        timeoutAt=approval.timeout_at.isoformat() if approval.timeout_at else None,
        approvedBy=approval.approved_by,
        rejectedBy=approval.rejected_by,
        approvedAt=approval.approved_at.isoformat() if approval.approved_at else None,
        rejectedAt=approval.rejected_at.isoformat() if approval.rejected_at else None,
        approvalComments=approval.approval_comments,
        rejectionComments=approval.rejection_comments,
    )


@router.get("/{tenant_id}/{approval_id}", response_model=ApprovalResponse)
async def get_approval(
    tenant_id: str = Path(..., description="Tenant identifier"),
    approval_id: str = Path(..., description="Approval identifier"),
) -> ApprovalResponse:
    """
    Get a specific approval by ID.
    
    Args:
        tenant_id: Tenant identifier
        approval_id: Approval identifier
        
    Returns:
        ApprovalResponse
    """
    registry = get_approval_registry()
    approval_queue = registry.get_queue(tenant_id)
    
    if not approval_queue:
        raise HTTPException(status_code=404, detail=f"Approval queue not found for tenant {tenant_id}")
    
    approval = approval_queue.get_approval(approval_id)
    if not approval:
        raise HTTPException(status_code=404, detail=f"Approval {approval_id} not found")
    
    return ApprovalResponse(
        approvalId=approval.approval_id,
        tenantId=approval.tenant_id,
        exceptionId=approval.exception_id,
        status=approval.status.value,
        submittedAt=approval.submitted_at.isoformat(),
        timeoutAt=approval.timeout_at.isoformat() if approval.timeout_at else None,
        approvedBy=approval.approved_by,
        rejectedBy=approval.rejected_by,
        approvedAt=approval.approved_at.isoformat() if approval.approved_at else None,
        rejectedAt=approval.rejected_at.isoformat() if approval.rejected_at else None,
        approvalComments=approval.approval_comments,
        rejectionComments=approval.rejection_comments,
    )

