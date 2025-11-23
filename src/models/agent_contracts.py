"""
Agent message contracts with strict Pydantic v2 validation.
Matches specification from docs/03-data-models-apis.md
"""

from typing import Any

from pydantic import BaseModel, Field, ConfigDict

from src.models.exception_record import ExceptionRecord


class AgentDecision(BaseModel):
    """
    Standardized agent decision output.
    
    All agents return this structure as part of AgentMessage.
    Matches specification from docs/master_project_instruction_full.md Section 7.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
        json_schema_extra={
            "example": {
                "decision": "Classified as DataQualityFailure",
                "confidence": 0.85,
                "evidence": ["Rule matched: invalid_format", "RAG similarity: 0.92"],
                "nextStep": "ProceedToPolicy",
            }
        },
    )

    decision: str = Field(..., min_length=1, description="Agent decision description")
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score between 0.0 and 1.0"
    )
    evidence: list[str] = Field(
        default_factory=list, description="Array of strings providing evidence for decision"
    )
    next_step: str = Field(..., alias="nextStep", min_length=1, description="Next step in workflow")

    @classmethod
    def model_validate_json(cls, json_data: str | bytes, *, strict: bool | None = None) -> "AgentDecision":
        """
        Validate and create AgentDecision from JSON string.
        
        Args:
            json_data: JSON string or bytes
            strict: Enable strict mode validation
            
        Returns:
            Validated AgentDecision instance
        """
        return super().model_validate_json(json_data, strict=strict)

    def model_dump_json(self, *, exclude_none: bool = False, **kwargs) -> str:
        """
        Serialize AgentDecision to JSON string.
        
        Args:
            exclude_none: Exclude None values from output
            **kwargs: Additional serialization options
            
        Returns:
            JSON string representation
        """
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)


class AgentMessage(BaseModel):
    """
    Complete agent message contract.
    
    Input: exception + prior agent outputs
    Output: standardized decision with context
    
    Matches specification from docs/03-data-models-apis.md Section "Agent Message Contracts".
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    exception: ExceptionRecord = Field(..., description="Canonical exception record")
    prior_outputs: dict[str, AgentDecision] = Field(
        default_factory=dict,
        alias="priorOutputs",
        description="Outputs from previous agents in pipeline",
    )
    decision: AgentDecision = Field(..., description="Current agent's decision")

    @classmethod
    def model_validate_json(cls, json_data: str | bytes, *, strict: bool | None = None) -> "AgentMessage":
        """
        Validate and create AgentMessage from JSON string.
        
        Args:
            json_data: JSON string or bytes
            strict: Enable strict mode validation
            
        Returns:
            Validated AgentMessage instance
        """
        return super().model_validate_json(json_data, strict=strict)

    def model_dump_json(self, *, exclude_none: bool = False, **kwargs) -> str:
        """
        Serialize AgentMessage to JSON string.
        
        Args:
            exclude_none: Exclude None values from output
            **kwargs: Additional serialization options
            
        Returns:
            JSON string representation
        """
        return super().model_dump_json(exclude_none=exclude_none, **kwargs)

