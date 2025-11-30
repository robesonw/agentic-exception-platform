"""
Operator UI Backend APIs for Phase 3.

REST APIs to power an operator UI:
- Browse exceptions, decisions, evidence, audit history
- Filter/search/paginate
- Access RAG evidence and agent reasoning
- Optional real-time updates via SSE

Matches specification from phase3-mvp-issues.md P3-12.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi import Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.models.exception_record import ResolutionStatus, Severity
from src.services.ui_query_service import UIQueryService, get_ui_query_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["operator-ui"])


# Response models
class ExceptionListItem(BaseModel):
    """Exception list item for browsing."""

    exception_id: str
    tenant_id: str
    domain: Optional[str] = None
    exception_type: Optional[str] = None
    severity: Optional[str] = None
    resolution_status: str
    source_system: Optional[str] = None
    timestamp: datetime


class ExceptionListResponse(BaseModel):
    """Response for exception list endpoint."""

    items: list[ExceptionListItem]
    total: int
    page: int
    page_size: int
    total_pages: int


class ExceptionDetailResponse(BaseModel):
    """Response for exception detail endpoint."""

    exception: dict
    agent_decisions: dict
    pipeline_result: dict


class EvidenceResponse(BaseModel):
    """Response for evidence endpoint."""

    rag_results: list
    tool_outputs: list
    agent_evidence: list


# IMPORTANT: More specific routes (with path parameters) must come BEFORE less specific ones
# FastAPI matches routes in order, so /exceptions/{exception_id} must come before /exceptions
@router.get("/exceptions/{exception_id}", response_model=ExceptionDetailResponse)
async def get_exception_detail(
    exception_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> ExceptionDetailResponse:
    """
    Get full exception detail with agent decisions.
    
    Returns:
    - Exception record
    - Agent decisions from all stages (intake, triage, policy, resolution, feedback)
    - Full pipeline result
    """
    ui_query_service = get_ui_query_service()
    detail = ui_query_service.get_exception_detail(tenant_id, exception_id)
    if not detail:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    return ExceptionDetailResponse(
        exception=detail["exception"],
        agent_decisions=detail["agent_decisions"],
        pipeline_result=detail["pipeline_result"],
    )


@router.get("/exceptions", response_model=ExceptionListResponse)
async def browse_exceptions(
    tenant_id: str = Query(..., description="Tenant identifier"),
    domain: Optional[str] = Query(None, description="Domain filter"),
    status: Optional[str] = Query(None, description="Resolution status filter"),
    severity: Optional[str] = Query(None, description="Severity filter"),
    from_ts: Optional[datetime] = Query(None, description="Start timestamp filter"),
    to_ts: Optional[datetime] = Query(None, description="End timestamp filter"),
    search: Optional[str] = Query(None, description="Text search query"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
) -> ExceptionListResponse:
    """
    Browse exceptions with filtering, search, and pagination.
    
    Query parameters:
    - tenant_id: Required tenant identifier
    - domain: Optional domain filter
    - status: Optional resolution status (PENDING, RESOLVED, ESCALATED, etc.)
    - severity: Optional severity (LOW, MEDIUM, HIGH, CRITICAL)
    - from_ts: Optional start timestamp (ISO format)
    - to_ts: Optional end timestamp (ISO format)
    - search: Optional text search in exception_type, source_system, raw_payload
    - page: Page number (default: 1)
    - page_size: Results per page (default: 50, max: 100)
    """
    ui_query_service = get_ui_query_service()
    
    # Parse status and severity enums
    status_enum = None
    if status:
        try:
            status_enum = ResolutionStatus(status.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
    
    severity_enum = None
    if severity:
        try:
            severity_enum = Severity(severity.upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")
    
    # Search exceptions
    result = ui_query_service.search_exceptions(
        tenant_id=tenant_id,
        domain=domain,
        status=status_enum,
        severity=severity_enum,
        from_ts=from_ts,
        to_ts=to_ts,
        search=search,
        page=page,
        page_size=page_size,
    )
    
    # Convert to response format
    items = []
    for item in result["items"]:
        exception_dict = item["exception"]
        # Extract domain from normalized_context if present
        normalized_context = exception_dict.get("normalized_context", {})
        domain = normalized_context.get("domain") if isinstance(normalized_context, dict) else None
        
        items.append(
            ExceptionListItem(
                exception_id=exception_dict.get("exception_id", ""),
                tenant_id=exception_dict.get("tenant_id", ""),
                domain=domain,
                exception_type=exception_dict.get("exception_type"),
                severity=exception_dict.get("severity"),
                resolution_status=exception_dict.get("resolution_status", "PENDING"),
                source_system=exception_dict.get("source_system"),
                timestamp=exception_dict.get("timestamp"),
            )
        )
    
    return ExceptionListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        page_size=result["page_size"],
        total_pages=result["total_pages"],
    )


@router.get("/exceptions/{exception_id}/evidence", response_model=EvidenceResponse)
async def get_exception_evidence(
    exception_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> EvidenceResponse:
    """
    Get evidence chains for an exception.
    
    Returns:
    - RAG results (similar historical exceptions)
    - Tool outputs (executed tool results)
    - Agent evidence (evidence from each agent stage)
    """
    ui_query_service = get_ui_query_service()
    evidence = ui_query_service.get_exception_evidence(tenant_id, exception_id)
    if not evidence:
        raise HTTPException(status_code=404, detail="Exception not found")
    
    return EvidenceResponse(
        rag_results=evidence.get("rag_results", []),
        tool_outputs=evidence.get("tool_outputs", []),
        agent_evidence=evidence.get("agent_evidence", []),
    )


@router.get("/exceptions/{exception_id}/audit")
async def get_exception_audit(
    exception_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict:
    """
    Get audit events related to an exception.
    
    Returns list of audit events with:
    - timestamp
    - run_id
    - event_type (agent_event, tool_call, decision)
    - data (event-specific data)
    """
    ui_query_service = get_ui_query_service()
    audit_events = ui_query_service.get_exception_audit(tenant_id, exception_id)
    
    return {
        "exception_id": exception_id,
        "tenant_id": tenant_id,
        "events": audit_events,
        "count": len(audit_events),
    }


@router.get("/stream/exceptions")
async def stream_exceptions(
    tenant_id: str = Query(..., description="Tenant identifier"),
    exception_id: Optional[str] = Query(None, description="Optional exception ID to subscribe to"),
    request: Request = None,
) -> StreamingResponse:
    """
    Server-Sent Events (SSE) stream for real-time exception updates.

    Streams StageCompletedEvent as JSON.
    Allows subscription per exception_id or all exceptions for a tenant.
    """
    from src.streaming.decision_stream import get_decision_stream_service
    
    decision_stream_service = get_decision_stream_service()
    queue: asyncio.Queue = asyncio.Queue()

    async def event_generator():
        # Send initial connection event
        yield f"data: {json.dumps({'type': 'connected', 'tenant_id': tenant_id, 'exception_id': exception_id})}\n\n"
        
        # Subscribe to events
        if exception_id:
            await decision_stream_service.subscribe_to_exception(tenant_id, exception_id, queue)
        else:
            await decision_stream_service.subscribe_to_tenant(tenant_id, queue)

        try:
            while True:
                if request and await request.is_disconnected():
                    logger.info(f"Client disconnected from SSE stream for tenant {tenant_id}")
                    break
                try:
                    # Wait for an event from the queue with a timeout
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps({'type': 'stage_completed', 'event': event.model_dump(mode='json')})}\n\n"
                except asyncio.TimeoutError:
                    # Send a heartbeat to keep the connection alive
                    yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': datetime.now(timezone.utc).isoformat()})}\n\n"
                except asyncio.CancelledError:
                    logger.info(f"SSE stream for tenant {tenant_id} cancelled.")
                    break
        except Exception as e:
            logger.error(f"Error in SSE event generator for tenant {tenant_id}: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        finally:
            # Unsubscribe when the client disconnects or an error occurs
            if exception_id:
                await decision_stream_service.unsubscribe(tenant_id, exception_id, queue)
            else:
                await decision_stream_service.unsubscribe(tenant_id, "*", queue)
            logger.info(f"SSE stream for tenant {tenant_id} closed.")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
