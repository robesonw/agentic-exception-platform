"""
Rate Limits API Routes for Phase 10 (P10-15 to P10-17).

Provides endpoints for rate limit management:
- Get tenant rate limits
- Update tenant rate limits
- Get current usage vs limits

Reference: docs/phase10-ops-governance-mvp.md Section 9
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status as http_status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.services.rate_limit_service import (
    RateLimitService,
    get_rate_limit_service,
    DEFAULT_RATE_LIMITS,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/rate-limits", tags=["rate-limits"])


# =============================================================================
# Request/Response Models
# =============================================================================


class RateLimitConfigRequest(BaseModel):
    """Request to update rate limit configuration."""
    limit_type: str = Field(..., description="Type: api_requests, events_ingested, tool_executions, report_generations")
    limit_value: int = Field(..., ge=1, description="Maximum allowed per window")
    window_seconds: int = Field(60, ge=1, description="Time window in seconds")
    enabled: bool = Field(True, description="Whether this limit is enabled")


class RateLimitConfigResponse(BaseModel):
    """Response for rate limit configuration."""
    tenant_id: str
    limit_type: str
    limit_value: int
    window_seconds: int
    enabled: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class RateLimitStatusResponse(BaseModel):
    """Response for current rate limit status."""
    tenant_id: str
    limit_type: str
    limit: int
    current: int
    remaining: int
    window_seconds: int
    reset_at: datetime
    enabled: bool


class RateLimitAllConfigsResponse(BaseModel):
    """Response containing all rate limit configs for a tenant."""
    tenant_id: str
    configs: list[RateLimitConfigResponse]
    defaults: dict[str, dict]


class RateLimitAllStatusResponse(BaseModel):
    """Response containing all rate limit statuses for a tenant."""
    tenant_id: str
    statuses: list[RateLimitStatusResponse]


# =============================================================================
# Helper Functions
# =============================================================================


def _to_config_response(config, tenant_id: str) -> RateLimitConfigResponse:
    """Convert model to response."""
    return RateLimitConfigResponse(
        tenant_id=tenant_id,
        limit_type=config.limit_type,
        limit_value=config.limit_value,
        window_seconds=config.window_seconds,
        enabled=config.enabled,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def _to_status_response(status) -> RateLimitStatusResponse:
    """Convert status dataclass to response."""
    return RateLimitStatusResponse(
        tenant_id=status.tenant_id,
        limit_type=status.limit_type,
        limit=status.limit,
        current=status.current,
        remaining=status.remaining,
        window_seconds=status.window_seconds,
        reset_at=status.reset_at,
        enabled=status.enabled,
    )


# =============================================================================
# Endpoints
# =============================================================================


@router.get(
    "/{tenant_id}",
    response_model=RateLimitAllConfigsResponse,
    summary="Get all rate limit configurations for a tenant",
)
async def get_tenant_rate_limits(
    tenant_id: str,
):
    """
    Get all rate limit configurations for a tenant.

    Returns configured limits and defaults for limit types without custom config.
    """
    async with get_db_session_context() as session:
        service = get_rate_limit_service(session)
        configs = await service.get_tenant_config(tenant_id)

        return RateLimitAllConfigsResponse(
            tenant_id=tenant_id,
            configs=[_to_config_response(c, tenant_id) for c in configs],
            defaults=DEFAULT_RATE_LIMITS,
        )


@router.put(
    "/{tenant_id}",
    response_model=RateLimitConfigResponse,
    summary="Update rate limit configuration for a tenant",
)
async def update_tenant_rate_limit(
    tenant_id: str,
    request: RateLimitConfigRequest,
):
    """
    Update or create rate limit configuration for a tenant.

    Valid limit types:
    - api_requests: API requests per minute
    - events_ingested: Events ingested per minute
    - tool_executions: Tool executions per minute
    - report_generations: Report generations per day
    """
    # Validate limit type
    valid_types = list(DEFAULT_RATE_LIMITS.keys())
    if request.limit_type not in valid_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid limit_type. Must be one of: {valid_types}",
        )

    async with get_db_session_context() as session:
        service = get_rate_limit_service(session)

        config = await service.update_tenant_config(
            tenant_id=tenant_id,
            limit_type=request.limit_type,
            limit_value=request.limit_value,
            window_seconds=request.window_seconds,
            enabled=request.enabled,
        )

        await session.commit()

        logger.info(
            f"Updated rate limit: tenant_id={tenant_id}, "
            f"type={request.limit_type}, limit={request.limit_value}"
        )

        return _to_config_response(config, tenant_id)


@router.delete(
    "/{tenant_id}",
    status_code=http_status.HTTP_204_NO_CONTENT,
    summary="Delete rate limit configuration for a tenant",
)
async def delete_tenant_rate_limit(
    tenant_id: str,
    limit_type: Optional[str] = Query(None, description="Specific limit type to delete"),
):
    """
    Delete rate limit configuration for a tenant.

    If limit_type is not specified, all configs for the tenant are deleted.
    Defaults will be used after deletion.
    """
    async with get_db_session_context() as session:
        service = get_rate_limit_service(session)

        deleted = await service.delete_tenant_config(
            tenant_id=tenant_id,
            limit_type=limit_type,
        )

        await session.commit()

        logger.info(
            f"Deleted {deleted} rate limit configs for tenant {tenant_id}"
        )

        return None


# Usage endpoints (for tenants to check their own usage)
usage_router = APIRouter(prefix="/usage/rate-limits", tags=["usage"])


@usage_router.get(
    "",
    response_model=RateLimitAllStatusResponse,
    summary="Get current rate limit usage",
)
async def get_rate_limit_usage(
    tenant_id: str = Query(..., description="Tenant ID"),
    limit_type: Optional[str] = Query(None, description="Specific limit type"),
):
    """
    Get current rate limit usage for a tenant.

    Returns current usage vs limits for all or specific limit types.
    """
    async with get_db_session_context() as session:
        service = get_rate_limit_service(session)

        statuses = await service.get_rate_limit_status(
            tenant_id=tenant_id,
            limit_type=limit_type,
        )

        return RateLimitAllStatusResponse(
            tenant_id=tenant_id,
            statuses=[_to_status_response(s) for s in statuses],
        )


# Combined router for main.py
def get_rate_limit_routers():
    """Get both rate limit routers."""
    return [router, usage_router]
