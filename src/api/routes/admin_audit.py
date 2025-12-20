"""
Admin Audit API Routes for Phase 12+ Governance & Audit Polish.

Provides endpoints for querying governance audit events:
- GET /admin/audit/events - Query events with filters and pagination
- GET /admin/audit/events/{event_id} - Get single event details
- GET /admin/audit/timeline - Get entity timeline

Reference: Phase 12+ Governance & Audit Polish requirements.
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, Request, status as http_status
from pydantic import BaseModel, Field

from src.api.routes.onboarding import require_admin_role, get_user_id
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.governance_audit_repository import (
    GovernanceAuditRepository,
    event_to_response,
)
from src.services.governance_audit import (
    AuditEventFilter,
    GovernanceAuditEventResponse,
    EntityTypes,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/audit", tags=["admin-audit"])


# =============================================================================
# Response Models
# =============================================================================


class PaginatedAuditEventsResponse(BaseModel):
    """Paginated list of audit events."""

    items: list[GovernanceAuditEventResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class EntityTimelineResponse(BaseModel):
    """Timeline of events for an entity."""

    entity_type: str
    entity_id: str
    tenant_id: Optional[str]
    events: list[GovernanceAuditEventResponse]
    total: int


class RecentChangesResponse(BaseModel):
    """Recent changes for an entity or tenant."""

    items: list[GovernanceAuditEventResponse]
    total: int


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/events", response_model=PaginatedAuditEventsResponse)
async def list_audit_events(
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    entity_type: Optional[str] = Query(None, description="Filter by entity type"),
    entity_id: Optional[str] = Query(None, description="Filter by entity ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    action: Optional[str] = Query(None, description="Filter by action"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    correlation_id: Optional[str] = Query(None, description="Filter by correlation ID"),
    from_date: Optional[str] = Query(None, description="Filter events after (ISO format)"),
    to_date: Optional[str] = Query(None, description="Filter events before (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
):
    """
    List audit events with filtering and pagination.

    RBAC: Admin/Supervisor only. Tenant admins can only see their tenant's events.
    """
    require_admin_role(request)
    user_id = get_user_id(request)

    # Parse date filters
    from_dt = None
    to_dt = None

    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid from_date format: {e}. Expected ISO format.",
            )

    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid to_date format: {e}. Expected ISO format.",
            )

    # Build filter
    filter_params = AuditEventFilter(
        tenant_id=tenant_id,
        domain=domain,
        entity_type=entity_type,
        entity_id=entity_id,
        event_type=event_type,
        action=action,
        actor_id=actor_id,
        correlation_id=correlation_id,
        from_date=from_dt,
        to_date=to_dt,
    )

    try:
        async with get_db_session_context() as session:
            repo = GovernanceAuditRepository(session)
            result = await repo.query_events(filter_params, page=page, page_size=page_size)

            return PaginatedAuditEventsResponse(
                items=[event_to_response(e) for e in result.items],
                total=result.total,
                page=result.page,
                page_size=result.page_size,
                total_pages=result.total_pages,
            )
    except Exception as e:
        logger.error(f"Error querying audit events: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to query audit events: {str(e)}",
        )


@router.get("/events/{event_id}", response_model=GovernanceAuditEventResponse)
async def get_audit_event(
    event_id: str,
    request: Request,
):
    """
    Get a single audit event by ID.

    RBAC: Admin/Supervisor only.
    """
    require_admin_role(request)

    try:
        async with get_db_session_context() as session:
            repo = GovernanceAuditRepository(session)
            event = await repo.get_by_id(event_id)

            if not event:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Audit event not found: {event_id}",
                )

            return event_to_response(event)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting audit event {event_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get audit event: {str(e)}",
        )


@router.get("/timeline", response_model=EntityTimelineResponse)
async def get_entity_timeline(
    entity_type: str = Query(..., description="Entity type"),
    entity_id: str = Query(..., description="Entity ID"),
    request: Request = None,
    tenant_id: Optional[str] = Query(None, description="Tenant ID (for tenant-scoped entities)"),
    limit: int = Query(50, ge=1, le=200, description="Maximum events to return"),
):
    """
    Get timeline of events for a specific entity.

    Shows all audit events related to the entity in chronological order.
    """
    require_admin_role(request)

    # Validate entity type
    valid_entity_types = [
        EntityTypes.TENANT,
        EntityTypes.DOMAIN_PACK,
        EntityTypes.TENANT_PACK,
        EntityTypes.PLAYBOOK,
        EntityTypes.TOOL,
        EntityTypes.RATE_LIMIT,
        EntityTypes.ALERT_CONFIG,
        EntityTypes.CONFIG_CHANGE,
        EntityTypes.ACTIVE_CONFIG,
    ]

    if entity_type not in valid_entity_types:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid entity_type: {entity_type}. Valid types: {valid_entity_types}",
        )

    try:
        async with get_db_session_context() as session:
            repo = GovernanceAuditRepository(session)
            events = await repo.get_entity_timeline(
                entity_type=entity_type,
                entity_id=entity_id,
                tenant_id=tenant_id,
                limit=limit,
            )

            return EntityTimelineResponse(
                entity_type=entity_type,
                entity_id=entity_id,
                tenant_id=tenant_id,
                events=[event_to_response(e) for e in events],
                total=len(events),
            )
    except Exception as e:
        logger.error(f"Error getting entity timeline: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get entity timeline: {str(e)}",
        )


@router.get("/recent/{tenant_id}", response_model=RecentChangesResponse)
async def get_recent_changes_by_tenant(
    tenant_id: str,
    request: Request,
    entity_types: Optional[str] = Query(
        None,
        description="Comma-separated entity types to filter (e.g., 'tenant,domain_pack,tool')",
    ),
    limit: int = Query(20, ge=1, le=100, description="Maximum events to return"),
):
    """
    Get recent audit events for a tenant.

    Useful for "Recent Changes" panels in tenant detail views.
    """
    require_admin_role(request)

    # Parse entity types
    entity_type_list = None
    if entity_types:
        entity_type_list = [t.strip() for t in entity_types.split(",")]

    try:
        async with get_db_session_context() as session:
            repo = GovernanceAuditRepository(session)
            events = await repo.get_recent_events_by_tenant(
                tenant_id=tenant_id,
                limit=limit,
                entity_types=entity_type_list,
            )

            return RecentChangesResponse(
                items=[event_to_response(e) for e in events],
                total=len(events),
            )
    except Exception as e:
        logger.error(f"Error getting recent changes for tenant {tenant_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent changes: {str(e)}",
        )


@router.get("/entity/{entity_type}/{entity_id}/recent", response_model=RecentChangesResponse)
async def get_recent_changes_for_entity(
    entity_type: str,
    entity_id: str,
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Tenant ID (for tenant-scoped entities)"),
    limit: int = Query(5, ge=1, le=20, description="Maximum events to return"),
):
    """
    Get recent changes for a specific entity.

    Useful for "Recent Changes" panels in entity detail views.
    """
    require_admin_role(request)

    try:
        async with get_db_session_context() as session:
            repo = GovernanceAuditRepository(session)
            events = await repo.get_recent_events_for_entity(
                entity_type=entity_type,
                entity_id=entity_id,
                tenant_id=tenant_id,
                limit=limit,
            )

            return RecentChangesResponse(
                items=[event_to_response(e) for e in events],
                total=len(events),
            )
    except Exception as e:
        logger.error(
            f"Error getting recent changes for {entity_type}:{entity_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get recent changes: {str(e)}",
        )


@router.get("/correlation/{correlation_id}", response_model=list[GovernanceAuditEventResponse])
async def get_events_by_correlation(
    correlation_id: str,
    request: Request,
):
    """
    Get all events for a correlation ID.

    Useful for distributed tracing and understanding the full context of a change.
    """
    require_admin_role(request)

    try:
        async with get_db_session_context() as session:
            repo = GovernanceAuditRepository(session)
            events = await repo.get_events_by_correlation_id(correlation_id)

            return [event_to_response(e) for e in events]
    except Exception as e:
        logger.error(
            f"Error getting events for correlation {correlation_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get correlated events: {str(e)}",
        )
