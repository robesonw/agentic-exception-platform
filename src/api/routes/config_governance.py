"""
Config Governance API Routes for Phase 10 (P10-10).

Provides configuration change governance endpoints:
- Submit config change requests
- List and view change requests
- Approve/reject change requests
- Apply approved changes

Reference: docs/phase10-ops-governance-mvp.md Section 7
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.config_change_repository import (
    ConfigChangeRepository,
    ConfigChangeStats,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/config-changes", tags=["config-governance"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ConfigChangeSubmitRequest(BaseModel):
    """Request to submit a config change."""
    change_type: str = Field(..., description="Type: domain_pack, tenant_policy, tool, playbook")
    resource_id: str = Field(..., description="ID of the resource being changed")
    proposed_config: dict = Field(..., description="Proposed new configuration")
    resource_name: Optional[str] = Field(None, description="Human-readable resource name")
    current_config: Optional[dict] = Field(None, description="Current configuration snapshot")
    diff_summary: Optional[str] = Field(None, description="Human-readable diff")
    change_reason: Optional[str] = Field(None, description="Reason for the change")


class ConfigChangeReviewRequest(BaseModel):
    """Request to approve or reject a change."""
    comment: Optional[str] = Field(None, description="Review comment")


class ConfigChangeApplyRequest(BaseModel):
    """Request to apply an approved change."""
    pass


class ConfigChangeResponse(BaseModel):
    """Response for a config change request."""
    id: str
    tenant_id: str
    change_type: str
    resource_id: str
    resource_name: Optional[str]
    status: str
    requested_by: str
    requested_at: datetime
    reviewed_by: Optional[str]
    reviewed_at: Optional[datetime]
    review_comment: Optional[str]
    applied_at: Optional[datetime]
    applied_by: Optional[str]
    diff_summary: Optional[str]
    change_reason: Optional[str]

    class Config:
        from_attributes = True


class ConfigChangeDetailResponse(ConfigChangeResponse):
    """Detailed response including config data."""
    current_config: Optional[dict]
    proposed_config: dict
    rollback_config: Optional[dict]

    class Config:
        from_attributes = True


class ConfigChangeStatsResponse(BaseModel):
    """Response for config change statistics."""
    tenant_id: str
    total_requests: int
    pending_count: int
    approved_count: int
    rejected_count: int
    applied_count: int
    by_change_type: dict[str, int]


class PaginatedConfigChangeResponse(BaseModel):
    """Paginated list of config changes."""
    items: list[ConfigChangeResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Helper Functions
# =============================================================================


def _to_response(change) -> ConfigChangeResponse:
    """Convert model to response."""
    return ConfigChangeResponse(
        id=change.id,
        tenant_id=change.tenant_id,
        change_type=change.change_type,
        resource_id=change.resource_id,
        resource_name=change.resource_name,
        status=change.status,
        requested_by=change.requested_by,
        requested_at=change.requested_at,
        reviewed_by=change.reviewed_by,
        reviewed_at=change.reviewed_at,
        review_comment=change.review_comment,
        applied_at=change.applied_at,
        applied_by=change.applied_by,
        diff_summary=change.diff_summary,
        change_reason=change.change_reason,
    )


def _to_detail_response(change) -> ConfigChangeDetailResponse:
    """Convert model to detailed response."""
    return ConfigChangeDetailResponse(
        id=change.id,
        tenant_id=change.tenant_id,
        change_type=change.change_type,
        resource_id=change.resource_id,
        resource_name=change.resource_name,
        status=change.status,
        requested_by=change.requested_by,
        requested_at=change.requested_at,
        reviewed_by=change.reviewed_by,
        reviewed_at=change.reviewed_at,
        review_comment=change.review_comment,
        applied_at=change.applied_at,
        applied_by=change.applied_by,
        diff_summary=change.diff_summary,
        change_reason=change.change_reason,
        current_config=change.current_config,
        proposed_config=change.proposed_config,
        rollback_config=change.rollback_config,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.post(
    "",
    response_model=ConfigChangeDetailResponse,
    status_code=http_status.HTTP_201_CREATED,
    summary="Submit a configuration change request",
)
async def submit_config_change(
    request: ConfigChangeSubmitRequest,
    tenant_id: str = Query(..., description="Tenant ID"),
    requested_by: str = Query(..., description="User submitting the change"),
):
    """
    Submit a new configuration change request for review.

    The change will be in 'pending' status until approved or rejected.
    """
    # Validate change type
    valid_types = ["domain_pack", "tenant_policy", "tool", "playbook"]
    if request.change_type not in valid_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid change_type. Must be one of: {valid_types}",
        )

    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        change = await repo.create_change_request(
            tenant_id=tenant_id,
            change_type=request.change_type,
            resource_id=request.resource_id,
            proposed_config=request.proposed_config,
            requested_by=requested_by,
            resource_name=request.resource_name,
            current_config=request.current_config,
            diff_summary=request.diff_summary,
            change_reason=request.change_reason,
        )

        await session.commit()

        logger.info(
            f"Config change submitted: id={change.id}, tenant_id={tenant_id}, "
            f"type={request.change_type}"
        )

        return _to_detail_response(change)


@router.get(
    "",
    response_model=PaginatedConfigChangeResponse,
    summary="List configuration change requests",
)
async def list_config_changes(
    tenant_id: str = Query(..., description="Tenant ID"),
    status: Optional[str] = Query(None, description="Filter by status"),
    change_type: Optional[str] = Query(None, description="Filter by change type"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """
    List configuration change requests for a tenant.

    Supports filtering by status and change type.
    """
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        filters = {}
        if status:
            filters["status"] = status
        if change_type:
            filters["change_type"] = change_type

        result = await repo.list_by_tenant(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            **filters,
        )

        return PaginatedConfigChangeResponse(
            items=[_to_response(c) for c in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )


@router.get(
    "/stats",
    response_model=ConfigChangeStatsResponse,
    summary="Get configuration change statistics",
)
async def get_config_change_stats(
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """Get statistics about configuration change requests for a tenant."""
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)
        stats = await repo.get_stats(tenant_id)

        return ConfigChangeStatsResponse(
            tenant_id=stats.tenant_id,
            total_requests=stats.total_requests,
            pending_count=stats.pending_count,
            approved_count=stats.approved_count,
            rejected_count=stats.rejected_count,
            applied_count=stats.applied_count,
            by_change_type=stats.by_change_type,
        )


@router.get(
    "/pending",
    response_model=PaginatedConfigChangeResponse,
    summary="List pending configuration change requests",
)
async def list_pending_config_changes(
    tenant_id: str = Query(..., description="Tenant ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
):
    """List all pending configuration change requests for a tenant."""
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        result = await repo.get_pending_requests(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
        )

        return PaginatedConfigChangeResponse(
            items=[_to_response(c) for c in result.items],
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )


@router.get(
    "/resource/{resource_id}",
    response_model=list[ConfigChangeResponse],
    summary="List change requests for a specific resource",
)
async def list_resource_config_changes(
    resource_id: str,
    tenant_id: str = Query(..., description="Tenant ID"),
    change_type: Optional[str] = Query(None, description="Filter by change type"),
):
    """List all configuration change requests for a specific resource."""
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        changes = await repo.get_requests_by_resource(
            tenant_id=tenant_id,
            resource_id=resource_id,
            change_type=change_type,
        )

        return [_to_response(c) for c in changes]


@router.get(
    "/{change_id}",
    response_model=ConfigChangeDetailResponse,
    summary="Get configuration change request details",
)
async def get_config_change(
    change_id: str,
    tenant_id: str = Query(..., description="Tenant ID"),
):
    """Get detailed information about a specific configuration change request."""
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)
        change = await repo.get_by_id(change_id, tenant_id)

        if not change:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Config change request not found: {change_id}",
            )

        return _to_detail_response(change)


@router.post(
    "/{change_id}/approve",
    response_model=ConfigChangeDetailResponse,
    summary="Approve a configuration change request",
)
async def approve_config_change(
    change_id: str,
    request: ConfigChangeReviewRequest,
    tenant_id: str = Query(..., description="Tenant ID"),
    reviewed_by: str = Query(..., description="User approving the change"),
):
    """
    Approve a pending configuration change request.

    The change must be in 'pending' status.
    """
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        try:
            change = await repo.approve_change_request(
                change_id=change_id,
                tenant_id=tenant_id,
                reviewed_by=reviewed_by,
                review_comment=request.comment,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        if not change:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Config change request not found: {change_id}",
            )

        await session.commit()

        logger.info(
            f"Config change approved: id={change_id}, reviewed_by={reviewed_by}"
        )

        return _to_detail_response(change)


@router.post(
    "/{change_id}/reject",
    response_model=ConfigChangeDetailResponse,
    summary="Reject a configuration change request",
)
async def reject_config_change(
    change_id: str,
    request: ConfigChangeReviewRequest,
    tenant_id: str = Query(..., description="Tenant ID"),
    reviewed_by: str = Query(..., description="User rejecting the change"),
):
    """
    Reject a pending configuration change request.

    The change must be in 'pending' status.
    """
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        try:
            change = await repo.reject_change_request(
                change_id=change_id,
                tenant_id=tenant_id,
                reviewed_by=reviewed_by,
                review_comment=request.comment,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        if not change:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Config change request not found: {change_id}",
            )

        await session.commit()

        logger.info(
            f"Config change rejected: id={change_id}, reviewed_by={reviewed_by}"
        )

        return _to_detail_response(change)


@router.post(
    "/{change_id}/apply",
    response_model=ConfigChangeDetailResponse,
    summary="Apply an approved configuration change",
)
async def apply_config_change(
    change_id: str,
    request: ConfigChangeApplyRequest,
    tenant_id: str = Query(..., description="Tenant ID"),
    applied_by: str = Query(..., description="User applying the change"),
):
    """
    Apply an approved configuration change.

    The change must be in 'approved' status. The actual configuration
    update should be handled by the caller after this endpoint succeeds.
    """
    async with get_db_session_context() as session:
        repo = ConfigChangeRepository(session)

        try:
            change = await repo.mark_as_applied(
                change_id=change_id,
                tenant_id=tenant_id,
                applied_by=applied_by,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

        if not change:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Config change request not found: {change_id}",
            )

        await session.commit()

        logger.info(
            f"Config change applied: id={change_id}, applied_by={applied_by}"
        )

        return _to_detail_response(change)
