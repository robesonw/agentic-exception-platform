"""
Audit API endpoints for Phase 9.

Provides audit trail querying using EventStoreRepository as source of truth.

Phase 9 P9-25: Enhance Audit Trail with Event Store Integration.
Reference: docs/phase9-async-scale-mvp.md Section 11
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from src.services.audit_service import AuditService, AuditServiceError, get_audit_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/audit", tags=["audit"])


class AuditEventResponse(BaseModel):
    """Response model for a single audit event."""

    event_id: str = Field(..., description="Event identifier")
    event_type: str = Field(..., description="Event type")
    tenant_id: str = Field(..., description="Tenant identifier")
    exception_id: Optional[str] = Field(None, description="Exception identifier")
    correlation_id: Optional[str] = Field(None, description="Correlation ID for distributed tracing")
    timestamp: Optional[str] = Field(None, description="Event timestamp (ISO format)")
    payload: dict = Field(..., description="Event payload")
    metadata: dict = Field(default_factory=dict, description="Event metadata")
    version: int = Field(..., description="Event schema version")

    model_config = {
        "json_schema_extra": {
            "example": {
                "event_id": "evt_001",
                "event_type": "ExceptionIngested",
                "tenant_id": "TENANT_001",
                "exception_id": "EXC_001",
                "correlation_id": "EXC_001",
                "timestamp": "2024-01-15T12:00:00Z",
                "payload": {"raw_payload": {}},
                "metadata": {},
                "version": 1,
            }
        }
    }


class AuditTrailResponse(BaseModel):
    """Response model for paginated audit trail."""

    items: list[AuditEventResponse] = Field(..., description="List of audit events")
    total: int = Field(..., description="Total number of events")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")

    model_config = {
        "json_schema_extra": {
            "example": {
                "items": [],
                "total": 0,
                "page": 1,
                "page_size": 50,
                "total_pages": 0,
            }
        }
    }


@router.get(
    "/exceptions/{tenant_id}/{exception_id}",
    response_model=AuditTrailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_exception_audit_trail(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    start_timestamp: Optional[str] = Query(None, description="Filter events after this timestamp (ISO format)"),
    end_timestamp: Optional[str] = Query(None, description="Filter events before this timestamp (ISO format)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=1000, description="Number of items per page"),
    request: Request = None,
) -> AuditTrailResponse:
    """
    Get audit trail for a specific exception.
    
    Phase 9 P9-25: Queries EventStoreRepository for all events related to an exception.
    Events are immutable and append-only, ensuring audit trail integrity.
    
    Returns:
        Paginated audit trail with events for the exception
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"path={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match path tenant '{tenant_id}'",
            )
        tenant_id = authenticated_tenant_id
    
    # Parse timestamps if provided
    start_ts = None
    end_ts = None
    if start_timestamp:
        try:
            start_ts = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid start_timestamp format: {e}. Expected ISO format.",
            )
    if end_timestamp:
        try:
            end_ts = datetime.fromisoformat(end_timestamp.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid end_timestamp format: {e}. Expected ISO format.",
            )
    
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_audit_trail_for_exception(
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type=event_type,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            page=page,
            page_size=page_size,
        )
        
        # Convert to response model
        audit_events = [
            AuditEventResponse(**event_dict) for event_dict in result.items
        ]
        
        return AuditTrailResponse(
            items=audit_events,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )
    except AuditServiceError as e:
        logger.error(f"Audit service error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting audit trail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get(
    "/tenants/{tenant_id}",
    response_model=AuditTrailResponse,
    status_code=status.HTTP_200_OK,
)
async def get_tenant_audit_trail(
    tenant_id: str = Path(..., description="Tenant identifier"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    exception_id: Optional[str] = Query(None, description="Filter by exception ID"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    start_timestamp: Optional[str] = Query(None, description="Filter events after this timestamp (ISO format)"),
    end_timestamp: Optional[str] = Query(None, description="Filter events before this timestamp (ISO format)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=1000, description="Number of items per page"),
    request: Request = None,
) -> AuditTrailResponse:
    """
    Get audit trail for a tenant with pagination.
    
    Phase 9 P9-25: Queries EventStoreRepository for all events for a tenant.
    Supports filtering and pagination for large result sets.
    
    Returns:
        Paginated audit trail with events for the tenant
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"path={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match path tenant '{tenant_id}'",
            )
        tenant_id = authenticated_tenant_id
    
    # Parse timestamps if provided
    start_ts = None
    end_ts = None
    if start_timestamp:
        try:
            start_ts = datetime.fromisoformat(start_timestamp.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid start_timestamp format: {e}. Expected ISO format.",
            )
    if end_timestamp:
        try:
            end_ts = datetime.fromisoformat(end_timestamp.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid end_timestamp format: {e}. Expected ISO format.",
            )
    
    try:
        audit_service = get_audit_service()
        result = await audit_service.get_audit_trail_for_tenant(
            tenant_id=tenant_id,
            event_type=event_type,
            exception_id=exception_id,
            correlation_id=correlation_id,
            start_timestamp=start_ts,
            end_timestamp=end_ts,
            page=page,
            page_size=page_size,
        )
        
        # Convert to response model
        audit_events = [
            AuditEventResponse(**event_dict) for event_dict in result.items
        ]
        
        return AuditTrailResponse(
            items=audit_events,
            total=result.total,
            page=result.page,
            page_size=result.page_size,
            total_pages=result.total_pages,
        )
    except AuditServiceError as e:
        logger.error(f"Audit service error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error getting audit trail: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")



