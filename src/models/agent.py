"""
Agent message contracts and response models.
"""

from typing import List

from pydantic import BaseModel, Field


class AgentResponse(BaseModel):
    """
    Standardized agent response format.
    All agents return this structure.
    """

    decision: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: List[str] = Field(default_factory=list)
    next_step: str = Field(..., alias="nextStep")

    class Config:
        populate_by_name = True

