"""
Supervisor Dashboard Backend APIs for Phase 3.

Provides supervisor view over:
- High-risk exceptions
- Escalations
- Policy violations
- Optimization suggestions

Matches specification from phase3-mvp-issues.md P3-15.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.services.supervisor_dashboard_service import (
    SupervisorDashboardService,
    get_supervisor_dashboard_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui/supervisor", tags=["supervisor-dashboard"])


# Response models
class OverviewResponse(BaseModel):
    """Response model for supervisor overview."""

    counts: dict = Field(..., description="Counts by severity and status")
    escalations_count: int = Field(..., description="Number of escalated exceptions")
    pending_approvals_count: int = Field(..., description="Number of pending approvals")
    top_policy_violations: list[dict] = Field(..., description="Top policy violations")
    optimization_suggestions_summary: dict = Field(..., description="Summary of optimization suggestions")


class EscalationItem(BaseModel):
    """Model for escalation item."""

    exception_id: str
    tenant_id: str
    domain: Optional[str]
    exception_type: Optional[str]
    severity: Optional[str]
    timestamp: Optional[str]
    escalation_reason: str


class EscalationsResponse(BaseModel):
    """Response model for escalations list."""

    escalations: list[EscalationItem] = Field(..., description="List of escalated exceptions")
    total: int = Field(..., description="Total number of escalations")


class PolicyViolationItem(BaseModel):
    """Model for policy violation item."""

    exception_id: str
    tenant_id: str
    domain: Optional[str]
    timestamp: str
    violation_type: str
    violated_rule: str
    decision: str


class PolicyViolationsResponse(BaseModel):
    """Response model for policy violations list."""

    violations: list[PolicyViolationItem] = Field(..., description="List of policy violations")
    total: int = Field(..., description="Total number of violations")


@router.get("/overview", response_model=OverviewResponse)
async def get_supervisor_overview(
    tenant_id: str = Query(..., description="Tenant identifier"),
    domain: Optional[str] = Query(None, description="Optional domain filter"),
    from_ts: Optional[str] = Query(None, description="Start timestamp (ISO format)"),
    to_ts: Optional[str] = Query(None, description="End timestamp (ISO format)"),
    dashboard_service: SupervisorDashboardService = Depends(get_supervisor_dashboard_service),
) -> OverviewResponse:
    """
    Get supervisor overview dashboard data.
    
    Returns:
    - Counts by severity and status
    - Number of escalations and pending approvals
    - Top policy violations
    - Summary of optimization suggestions
    
    Args:
        tenant_id: Tenant identifier
        domain: Optional domain filter
        from_ts: Optional start timestamp (ISO format)
        to_ts: Optional end timestamp (ISO format)
        dashboard_service: Supervisor dashboard service (dependency injection)
        
    Returns:
        OverviewResponse with aggregated dashboard data
        
    Raises:
        HTTPException: If data retrieval fails
    """
    # Parse timestamps if provided
    from_datetime = None
    to_datetime = None
    if from_ts:
        try:
            from_datetime = datetime.fromisoformat(from_ts.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid from_ts format: {from_ts}")
    
    if to_ts:
        try:
            to_datetime = datetime.fromisoformat(to_ts.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid to_ts format: {to_ts}")
    
    try:
        overview_data = dashboard_service.get_overview(
            tenant_id=tenant_id,
            domain=domain,
            from_ts=from_datetime,
            to_ts=to_datetime,
        )
        
        return OverviewResponse(**overview_data)
    except Exception as e:
        logger.error(f"Failed to get supervisor overview: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get supervisor overview: {str(e)}")


@router.get("/escalations", response_model=EscalationsResponse)
async def get_escalations(
    tenant_id: str = Query(..., description="Tenant identifier"),
    domain: Optional[str] = Query(None, description="Optional domain filter"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of escalations to return"),
    dashboard_service: SupervisorDashboardService = Depends(get_supervisor_dashboard_service),
) -> EscalationsResponse:
    """
    Get list of escalated exceptions with key metadata.
    
    Args:
        tenant_id: Tenant identifier
        domain: Optional domain filter
        limit: Maximum number of escalations to return (default: 50, max: 500)
        dashboard_service: Supervisor dashboard service (dependency injection)
        
    Returns:
        EscalationsResponse with list of escalated exceptions
        
    Raises:
        HTTPException: If data retrieval fails
    """
    try:
        escalations = dashboard_service.get_escalations(
            tenant_id=tenant_id,
            domain=domain,
            limit=limit,
        )
        
        return EscalationsResponse(
            escalations=[EscalationItem(**esc) for esc in escalations],
            total=len(escalations),
        )
    except Exception as e:
        logger.error(f"Failed to get escalations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get escalations: {str(e)}")


@router.get("/policy-violations", response_model=PolicyViolationsResponse)
async def get_policy_violations(
    tenant_id: str = Query(..., description="Tenant identifier"),
    domain: Optional[str] = Query(None, description="Optional domain filter"),
    limit: int = Query(50, ge=1, le=500, description="Maximum number of violations to return"),
    dashboard_service: SupervisorDashboardService = Depends(get_supervisor_dashboard_service),
) -> PolicyViolationsResponse:
    """
    Get recent policy violation events.
    
    Args:
        tenant_id: Tenant identifier
        domain: Optional domain filter
        limit: Maximum number of violations to return (default: 50, max: 500)
        dashboard_service: Supervisor dashboard service (dependency injection)
        
    Returns:
        PolicyViolationsResponse with list of policy violations
        
    Raises:
        HTTPException: If data retrieval fails
    """
    try:
        violations = dashboard_service.get_policy_violations(
            tenant_id=tenant_id,
            domain=domain,
            limit=limit,
        )
        
        return PolicyViolationsResponse(
            violations=[PolicyViolationItem(**viol) for viol in violations],
            total=len(violations),
        )
    except Exception as e:
        logger.error(f"Failed to get policy violations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get policy violations: {str(e)}")

