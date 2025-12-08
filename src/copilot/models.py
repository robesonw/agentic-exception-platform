"""
Copilot Models for Phase 5 - AI Co-Pilot.

Pydantic models for Copilot request/response and citations.

Reference: docs/phase5-copilot-mvp.md Section 5.2 (Copilot Models)
"""

from typing import Literal

from pydantic import BaseModel, Field


class CopilotRequest(BaseModel):
    """
    Request model for Copilot chat endpoint.
    
    Attributes:
        message: The user's message/question to the Co-Pilot
        tenant_id: Tenant identifier for tenant-scoped queries
        domain: Domain identifier for domain-scoped queries
        context: Optional context dictionary (e.g., current exception ID, page context)
    """
    
    message: str = Field(..., description="User message/question to the Co-Pilot")
    tenant_id: str = Field(..., description="Tenant identifier")
    domain: str = Field(..., description="Domain identifier")
    context: dict | None = Field(
        default=None,
        description="Optional context dictionary (e.g., current exception ID, page context)",
    )


class CopilotCitation(BaseModel):
    """
    Citation model for Copilot responses.
    
    Represents a reference to a source used in generating the answer.
    
    Attributes:
        type: Type of citation (exception, policy, or domain)
        id: Identifier of the cited resource
    """
    
    type: Literal["exception", "policy", "domain"] = Field(
        ...,
        description="Type of citation: exception, policy, or domain",
    )
    id: str = Field(..., description="Identifier of the cited resource")


class CopilotResponse(BaseModel):
    """
    Response model for Copilot chat endpoint.
    
    Attributes:
        answer: The generated answer text from the Co-Pilot
        answer_type: Type of answer (EXPLANATION, SUMMARY, POLICY_HINT, or UNKNOWN)
        citations: List of citations used in generating the answer
        raw_llm_trace_id: Optional trace ID from the underlying LLM provider (for debugging)
    """
    
    answer: str = Field(..., description="Generated answer text from the Co-Pilot")
    answer_type: Literal["EXPLANATION", "SUMMARY", "POLICY_HINT", "UNKNOWN"] = Field(
        ...,
        description="Type of answer: EXPLANATION, SUMMARY, POLICY_HINT, or UNKNOWN",
    )
    citations: list[CopilotCitation] = Field(
        default_factory=list,
        description="List of citations used in generating the answer",
    )
    raw_llm_trace_id: str | None = Field(
        default=None,
        description="Optional trace ID from the underlying LLM provider (for debugging)",
    )

