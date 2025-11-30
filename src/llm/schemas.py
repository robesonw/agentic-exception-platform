"""
LLM output schemas for agent reasoning and decisions.

Defines structured Pydantic models for agent LLM outputs with:
- Structured reasoning (reasoning_steps, evidence_references)
- Main decision payload (agent-specific fields)
- Confidence scores
- Natural language summaries

Matches Phase 3 requirements from phase3-mvp-issues.md (P3-5, P3-1..P3-4).
"""

from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class ReasoningStep(BaseModel):
    """A single step in the agent's reasoning process."""

    model_config = ConfigDict(extra="forbid")

    step_number: int = Field(..., ge=1, description="Step number in reasoning sequence")
    description: str = Field(..., min_length=1, description="Description of this reasoning step")
    evidence_used: Optional[list[str]] = Field(
        default_factory=list, description="Evidence sources used in this step"
    )
    conclusion: Optional[str] = Field(None, description="Conclusion reached in this step")


class EvidenceReference(BaseModel):
    """Reference to evidence used in decision-making."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., min_length=1, description="Evidence source (e.g., 'RAG', 'Policy', 'Tool')")
    reference_id: Optional[str] = Field(None, description="ID of the evidence item")
    relevance_score: Optional[float] = Field(
        None, ge=0.0, le=1.0, description="Relevance score for this evidence"
    )
    description: str = Field(..., min_length=1, description="Description of the evidence")


class BaseAgentLLMOutput(BaseModel):
    """Base class for all agent LLM outputs."""

    model_config = ConfigDict(extra="forbid")

    reasoning_steps: list[ReasoningStep] = Field(
        default_factory=list, description="Structured reasoning steps"
    )
    evidence_references: list[EvidenceReference] = Field(
        default_factory=list, description="References to evidence used"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    natural_language_summary: str = Field(
        ..., min_length=1, description="Human-readable natural language summary"
    )


class TriageLLMOutput(BaseAgentLLMOutput):
    """
    LLM output schema for TriageAgent.
    
    Includes classification and severity scoring with explainable reasoning.
    """

    predicted_exception_type: str = Field(..., min_length=1, description="Predicted exception type")
    predicted_severity: str = Field(
        ..., description="Predicted severity (LOW|MEDIUM|HIGH|CRITICAL)"
    )
    severity_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in severity prediction"
    )
    classification_confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence in exception type classification"
    )
    root_cause_hypothesis: Optional[str] = Field(
        None, description="Hypothesized root cause based on RAG and rules"
    )
    matched_rules: list[str] = Field(
        default_factory=list, description="List of severity rules that matched"
    )
    diagnostic_summary: str = Field(
        ..., min_length=1, description="Detailed diagnostic summary"
    )


class PolicyLLMOutput(BaseAgentLLMOutput):
    """
    LLM output schema for PolicyAgent.
    
    Includes guardrail evaluation and approval/blocking decisions with explanations.
    """

    policy_decision: str = Field(
        ..., description="Policy decision (APPROVED|BLOCKED|REQUIRES_APPROVAL)"
    )
    applied_guardrails: list[str] = Field(
        default_factory=list, description="List of guardrails that were applied"
    )
    violated_rules: list[str] = Field(
        default_factory=list, description="List of rules that were violated (if any)"
    )
    approval_required: bool = Field(
        ..., description="Whether human approval is required"
    )
    approval_reason: Optional[str] = Field(
        None, description="Reason why approval is required"
    )
    policy_violation_report: Optional[str] = Field(
        None, description="Human-readable policy violation report (if blocked)"
    )
    tenant_policy_influence: Optional[str] = Field(
        None, description="How tenant-specific policies influenced the decision"
    )


class ResolutionLLMOutput(BaseAgentLLMOutput):
    """
    LLM output schema for ResolutionAgent.
    
    Includes playbook selection and tool execution rationale with explanations.
    """

    selected_playbook_id: Optional[str] = Field(
        None, description="ID of the selected playbook"
    )
    playbook_selection_rationale: str = Field(
        ..., min_length=1, description="Explanation for why this playbook was selected"
    )
    rejected_playbooks: list[dict[str, Any]] = Field(
        default_factory=list, description="List of playbooks that were considered but rejected"
    )
    action_rationale: str = Field(
        ..., min_length=1, description="Rationale for the chosen resolution actions"
    )
    tool_execution_plan: list[dict[str, Any]] = Field(
        default_factory=list, description="Plan for tool execution with order and dependencies"
    )
    expected_outcome: Optional[str] = Field(
        None, description="Expected outcome of the resolution"
    )
    resolution_status: str = Field(
        ..., description="Resolution status (RESOLVED|PARTIAL|FAILED|PENDING)"
    )


class SupervisorLLMOutput(BaseAgentLLMOutput):
    """
    LLM output schema for SupervisorAgent.
    
    Includes oversight decisions and intervention rationale with explanations.
    """

    oversight_decision: str = Field(
        ..., description="Oversight decision (APPROVED_FLOW|INTERVENED|ESCALATED)"
    )
    intervention_reason: Optional[str] = Field(
        None, description="Reason for intervention (if intervened)"
    )
    anomaly_detected: bool = Field(..., description="Whether an anomaly was detected")
    anomaly_description: Optional[str] = Field(
        None, description="Description of detected anomaly"
    )
    agent_chain_review: dict[str, Any] = Field(
        default_factory=dict, description="Review of the agent chain decisions"
    )
    recommended_action: Optional[str] = Field(
        None, description="Recommended action based on oversight"
    )
    escalation_reason: Optional[str] = Field(
        None, description="Reason for escalation (if escalated)"
    )
    suggested_human_message: Optional[str] = Field(
        None, description="Suggested message to show to human operator (if intervention or escalation)"
    )


class NLQAnswer(BaseModel):
    """
    Natural Language Query answer schema.
    
    Used for operator questions about exception processing decisions.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    answer: str = Field(..., min_length=1, description="Natural language answer to the question")
    answer_sources: list[str] = Field(
        default_factory=list, description="List of evidence/decision IDs referenced in the answer"
    )
    agent_context_used: list[str] = Field(
        default_factory=list, description="List of agent names whose decisions were used in the answer"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence in the answer")
    reasoning: Optional[str] = Field(None, description="Optional reasoning for the answer")


# Schema name to model mapping for LLMClient
SCHEMA_REGISTRY: dict[str, type[BaseAgentLLMOutput]] = {
    "triage": TriageLLMOutput,
    "policy": PolicyLLMOutput,
    "resolution": ResolutionLLMOutput,
    "supervisor": SupervisorLLMOutput,
}

# Extended registry for non-agent schemas
EXTENDED_SCHEMA_REGISTRY: dict[str, type[BaseModel]] = {
    "nlq_answer": NLQAnswer,
}


def get_schema_model(schema_name: str) -> type[BaseAgentLLMOutput]:
    """
    Get the Pydantic model class for a given schema name.
    
    Args:
        schema_name: Name of the schema (e.g., "triage", "policy")
        
    Returns:
        Pydantic model class for the schema
        
    Raises:
        ValueError: If schema_name is not recognized
    """
    schema_name_lower = schema_name.lower()
    if schema_name_lower not in SCHEMA_REGISTRY:
        raise ValueError(
            f"Unknown schema name: {schema_name}. "
            f"Available schemas: {list(SCHEMA_REGISTRY.keys())}"
        )
    return SCHEMA_REGISTRY[schema_name_lower]


def get_extended_schema_model(schema_name: str) -> type[BaseModel]:
    """
    Get extended schema model (including non-agent schemas like NLQAnswer).
    
    Args:
        schema_name: Schema name
        
    Returns:
        Pydantic model class
        
    Raises:
        ValueError: If schema_name is not recognized
    """
    schema_name_lower = schema_name.lower()
    # First check agent schemas
    if schema_name_lower in SCHEMA_REGISTRY:
        return SCHEMA_REGISTRY[schema_name_lower]
    # Then check extended schemas
    elif schema_name_lower in EXTENDED_SCHEMA_REGISTRY:
        return EXTENDED_SCHEMA_REGISTRY[schema_name_lower]
    else:
        raise ValueError(
            f"Unknown schema name: {schema_name}. "
            f"Available schemas: {list(SCHEMA_REGISTRY.keys()) + list(EXTENDED_SCHEMA_REGISTRY.keys())}"
        )

