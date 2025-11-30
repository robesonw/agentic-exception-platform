"""
Natural Language Query (NLQ) API for Phase 3.

REST API for operators to ask questions about exceptions in natural language.
Answers use existing explainability data + LLM summarization.

Matches specification from phase3-mvp-issues.md P3-13.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.audit.logger import AuditLogger
from src.llm.provider import LLMClient
from src.services.nlq_service import NLQService, NLQServiceError, get_nlq_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["operator-ui"])


# Request/Response models
class NLQRequest(BaseModel):
    """Request model for NLQ endpoint."""

    tenant_id: str = Field(..., description="Tenant identifier")
    exception_id: str = Field(..., description="Exception identifier")
    question: str = Field(..., min_length=1, description="Natural language question")


class NLQResponse(BaseModel):
    """Response model for NLQ endpoint."""

    answer: str = Field(..., description="Natural language answer to the question")
    answer_sources: list[str] = Field(
        default_factory=list, description="List of evidence/decision IDs referenced in the answer"
    )
    agent_context_used: list[str] = Field(
        default_factory=list, description="List of agent names whose context was used"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the answer")
    supporting_evidence: list[str] = Field(
        default_factory=list, description="List of supporting evidence snippets"
    )


@router.post("/nlq", response_model=NLQResponse)
async def answer_nlq_question(
    request: NLQRequest,
) -> NLQResponse:
    """
    Answer a natural language question about an exception.
    
    Examples:
    - "Why did you block this?"
    - "What evidence did Triage use?"
    - "What alternative actions were possible?"
    
    The answer is generated using:
    - Existing explainability data (agent decisions, evidence, audit history)
    - LLM summarization (if LLM client is available)
    - Fallback to simple keyword-based answers if LLM unavailable
    
    Safety:
    - Tenant isolation enforced (cannot see cross-tenant data)
    - Question + answer are logged/audited
    
    Args:
        request: NLQ request with tenant_id, exception_id, and question
        
    Returns:
        NLQResponse with answer, sources, and metadata
        
    Raises:
        HTTPException: If exception not found or question cannot be answered
    """
    nlq_service = get_nlq_service()
    
    try:
        # Answer the question
        result = await nlq_service.answer_question(
            tenant_id=request.tenant_id,
            exception_id=request.exception_id,
            question=request.question,
        )
        
        return NLQResponse(
            answer=result["answer"],
            answer_sources=result["answer_sources"],
            agent_context_used=result["agent_context_used"],
            confidence=result["confidence"],
            supporting_evidence=result["supporting_evidence"],
        )
        
    except NLQServiceError as e:
        logger.error(f"NLQ service error: {e}")
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in NLQ endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to answer question: {e}")
