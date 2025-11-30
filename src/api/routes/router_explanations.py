"""
Explanation API Endpoints (P3-30).

Exposes explanations via API with support for:
- JSON format
- Natural language text
- Structured formats
- Timeline and evidence graph views
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict

from src.services.explanation_service import (
    ExplanationFormat,
    ExplanationService,
    ExplanationSummary,
    get_explanation_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/explanations", tags=["explanations"])


class ExplanationResponse(BaseModel):
    """Response for explanation endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    explanation: dict[str, Any] | str = Field(..., description="Explanation in requested format")
    format: str = Field(..., description="Format used (json, text, structured)")
    version: dict[str, Any] = Field(..., description="Version information")


class ExplanationSearchResponse(BaseModel):
    """Response for explanation search endpoint."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    items: list[ExplanationSummary] = Field(..., description="List of explanation summaries")
    total: int = Field(..., description="Total number of results")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., alias="pageSize", description="Page size")
    total_pages: int = Field(..., alias="totalPages", description="Total number of pages")


@router.get("/{exception_id}", response_model=ExplanationResponse)
async def get_explanation(
    exception_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
    format: str = Query("json", description="Output format: json, text, or structured"),
) -> ExplanationResponse:
    """
    Get explanation for an exception.
    
    Supports multiple formats:
    - json: Full JSON structure with timeline, evidence, and decisions
    - text: Natural language text summary
    - structured: Structured data format with grouped evidence
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        format: Output format (json, text, structured)
        
    Returns:
        ExplanationResponse with explanation in requested format
    """
    try:
        # Validate format
        try:
            explanation_format = ExplanationFormat(format.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid format: {format}. Must be one of: json, text, structured",
            )
        
        # Get explanation service (with audit logger from request state if available)
        # For MVP, we'll create a basic audit logger if needed
        from src.audit.logger import AuditLogger
        audit_logger = AuditLogger(run_id=f"explanation_{exception_id}", tenant_id=tenant_id)
        service = get_explanation_service(audit_logger=audit_logger)
        
        # Get explanation
        explanation = service.get_explanation(exception_id, tenant_id, explanation_format)
        
        # Extract version info
        if isinstance(explanation, dict):
            version_info = explanation.get("version", {})
        else:
            # For text format, version info is not included in the text
            # We'll need to get it separately
            result = service.exception_store.get_exception(tenant_id, exception_id)
            if result:
                exception, _ = result
                version_info = {
                    "version": exception.exception_id,
                    "timestamp": exception.timestamp.isoformat(),
                }
            else:
                from datetime import timezone
                version_info = {"version": exception_id, "timestamp": datetime.now(timezone.utc).isoformat()}
        
        return ExplanationResponse(
            exception_id=exception_id,
            explanation=explanation,
            format=format.lower(),
            version=version_info,
        )
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting explanation: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/search", response_model=ExplanationSearchResponse)
async def search_explanations(
    tenant_id: str = Query(..., description="Tenant identifier"),
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    decision_type: Optional[str] = Query(None, description="Filter by decision type"),
    from_ts: Optional[datetime] = Query(None, description="Start timestamp filter"),
    to_ts: Optional[datetime] = Query(None, description="End timestamp filter"),
    text: Optional[str] = Query(None, description="Text search query"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
) -> ExplanationSearchResponse:
    """
    Search explanations with filters.
    
    Supports filtering by:
    - Agent name
    - Decision type
    - Timestamp range
    - Text search
    
    Args:
        tenant_id: Tenant identifier
        agent_name: Optional agent name filter
        decision_type: Optional decision type filter
        from_ts: Optional start timestamp filter
        to_ts: Optional end timestamp filter
        text: Optional text search query
        page: Page number (1-indexed)
        page_size: Page size (max 100)
        
    Returns:
        ExplanationSearchResponse with paginated results
    """
    try:
        service = get_explanation_service()
        
        # Search explanations
        summaries = service.search_explanations(
            tenant_id=tenant_id,
            agent_name=agent_name,
            decision_type=decision_type,
            from_ts=from_ts,
            to_ts=to_ts,
            text=text,
            page=page,
            page_size=page_size,
        )
        
        # Calculate total (for MVP, we'll use a simple count)
        # In production, this would be more efficient
        all_summaries = service.search_explanations(
            tenant_id=tenant_id,
            agent_name=agent_name,
            decision_type=decision_type,
            from_ts=from_ts,
            to_ts=to_ts,
            text=text,
            page=1,
            page_size=10000,  # Large page size to get all
        )
        total = len(all_summaries)
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return ExplanationSearchResponse(
            items=summaries,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )
        
    except Exception as e:
        logger.error(f"Error searching explanations: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{exception_id}/timeline")
async def get_explanation_timeline(
    exception_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict[str, Any]:
    """
    Get decision timeline for an exception.
    
    Returns the DecisionTimeline from P3-28 with all events in chronological order.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        
    Returns:
        DecisionTimeline JSON
    """
    try:
        service = get_explanation_service()
        
        timeline = service.get_timeline(exception_id, tenant_id)
        
        return timeline.model_dump(by_alias=True)
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/{exception_id}/evidence")
async def get_explanation_evidence(
    exception_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict[str, Any]:
    """
    Get evidence graph for an exception.
    
    Returns evidence items and links from P3-29, including:
    - All evidence items (RAG, tool, policy)
    - Evidence links to agent decisions
    - Evidence graph structure (nodes and edges)
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        
    Returns:
        Evidence graph JSON
    """
    try:
        service = get_explanation_service()
        
        evidence_graph = service.get_evidence_graph(exception_id, tenant_id)
        
        return evidence_graph
        
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting evidence graph: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

