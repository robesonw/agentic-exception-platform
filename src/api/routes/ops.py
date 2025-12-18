"""
Operations API routes for monitoring and debugging.

Provides read-only access to operational data like Dead Letter Queue entries.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.dead_letter_repository import DeadLetterEventRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ops", tags=["ops"])


class DLQEntryResponse(BaseModel):
    """Response model for DLQ entry."""
    
    event_id: str = Field(..., description="Original event identifier")
    event_type: str = Field(..., description="Type of the original event")
    tenant_id: str = Field(..., description="Tenant identifier")
    exception_id: Optional[str] = Field(None, description="Exception identifier")
    original_topic: str = Field(..., description="Original topic where event was published")
    failure_reason: str = Field(..., description="Reason for failure")
    retry_count: int = Field(..., description="Number of retry attempts made")
    worker_type: str = Field(..., description="Worker type that failed")
    payload: dict = Field(..., description="Original event payload")
    event_metadata: dict = Field(default_factory=dict, description="Event metadata")
    failed_at: str = Field(..., description="ISO datetime when event was moved to DLQ")


class DLQListResponse(BaseModel):
    """Response model for DLQ list."""
    
    items: list[DLQEntryResponse] = Field(..., description="List of DLQ entries")
    total: int = Field(..., description="Total number of DLQ entries matching filters")
    limit: int = Field(..., description="Limit used for pagination")
    offset: int = Field(..., description="Offset used for pagination")


@router.get("/dlq", response_model=DLQListResponse)
async def list_dlq_entries(
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (required)"),
    status: Optional[str] = Query(None, description="Filter by status (not currently used)"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of results"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
) -> DLQListResponse:
    """
    List Dead Letter Queue entries.
    
    GET /api/ops/dlq?tenant_id=&status=&limit=&offset=
    
    This is a read-only endpoint for monitoring DLQ entries.
    All queries are tenant-isolated.
    
    Args:
        request: FastAPI request object (for tenant extraction)
        tenant_id: Tenant identifier (required)
        status: Status filter (reserved for future use)
        limit: Maximum number of results (1-1000, default: 100)
        offset: Number of results to skip (default: 0)
        
    Returns:
        DLQListResponse with paginated DLQ entries
        
    Raises:
        HTTPException: If tenant_id is missing or invalid
    """
    # Extract tenant_id from request (could be from middleware or query param)
    # For now, require it as query param
    if not tenant_id:
        # Try to get from request state (set by middleware)
        tenant_id = getattr(request.state, "tenant_id", None)
    
    if not tenant_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_id is required (query parameter or authenticated tenant)",
        )
    
    try:
        async with get_db_session_context() as session:
            dlq_repo = DeadLetterEventRepository(session)
            
            # List DLQ entries with tenant isolation
            result = await dlq_repo.list_dlq_entries(
                tenant_id=tenant_id,
                limit=limit,
                offset=offset,
                order_by="failed_at",
                order_desc=True,
            )
            
            # Convert to response format
            items = [
                DLQEntryResponse(
                    event_id=entry.event_id,
                    event_type=entry.event_type,
                    tenant_id=entry.tenant_id,
                    exception_id=entry.exception_id,
                    original_topic=entry.original_topic,
                    failure_reason=entry.failure_reason,
                    retry_count=entry.retry_count,
                    worker_type=entry.worker_type,
                    payload=entry.payload or {},
                    event_metadata=entry.event_metadata or {},
                    failed_at=entry.failed_at.isoformat() if entry.failed_at else "",
                )
                for entry in result.items
            ]
            
            return DLQListResponse(
                items=items,
                total=result.total,
                limit=result.limit,
                offset=result.offset,
            )
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list DLQ entries: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve DLQ entries: {str(e)}",
        )

