"""
Canonical event types and payload schemas for exception processing.

This module defines the standard event types and structured payloads for the
append-only event log, as specified in docs/phase6-persistence-mvp.md Sections 6.1 and 6.2.

Event types:
- ExceptionCreated
- ExceptionNormalized
- TriageCompleted
- PolicyEvaluated
- ResolutionSuggested
- ResolutionApproved
- FeedbackCaptured
- LLMDecisionProposed
- CopilotQuestionAsked
- CopilotAnswerGiven

All events are structured as EventEnvelope with typed payloads.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# Event Type Enum
# ============================================================================


class EventType(str, Enum):
    """
    Canonical event types for exception processing lifecycle.
    
    Matches docs/phase6-persistence-mvp.md Section 6.2 (Agent event types).
    """

    EXCEPTION_CREATED = "ExceptionCreated"
    EXCEPTION_NORMALIZED = "ExceptionNormalized"
    TRIAGE_COMPLETED = "TriageCompleted"
    POLICY_EVALUATED = "PolicyEvaluated"
    RESOLUTION_SUGGESTED = "ResolutionSuggested"
    RESOLUTION_APPROVED = "ResolutionApproved"
    FEEDBACK_CAPTURED = "FeedbackCaptured"
    LLM_DECISION_PROPOSED = "LLMDecisionProposed"
    COPILOT_QUESTION_ASKED = "CopilotQuestionAsked"
    COPILOT_ANSWER_GIVEN = "CopilotAnswerGiven"


# ============================================================================
# Actor Type (matches database model)
# ============================================================================


class ActorType(str, Enum):
    """Actor type for exception events (matches database ActorType enum)."""

    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


# ============================================================================
# Payload Schemas
# ============================================================================


class ExceptionCreatedPayload(BaseModel):
    """
    Payload for ExceptionCreated event.
    
    Fired when a new exception is ingested into the system.
    """

    source_system: str = Field(..., description="Source system name (e.g., 'ERP')")
    raw_payload: dict[str, Any] = Field(..., description="Original raw exception data")
    normalized_fields: dict[str, Any] | None = Field(
        None, description="Normalized fields if available at creation time"
    )

    model_config = {"extra": "forbid"}


class ExceptionNormalizedPayload(BaseModel):
    """
    Payload for ExceptionNormalized event.
    
    Fired after IntakeAgent normalizes the exception.
    """

    normalized_context: dict[str, Any] = Field(..., description="Normalized context fields")
    domain: str | None = Field(None, description="Detected domain name")
    entity: str | None = Field(None, description="Detected entity identifier")

    model_config = {"extra": "forbid"}


class TriageCompletedPayload(BaseModel):
    """
    Payload for TriageCompleted event.
    
    Fired when TriageAgent completes classification and severity assessment.
    """

    exception_type: str = Field(..., description="Classified exception type")
    severity: str = Field(..., description="Assessed severity (LOW|MEDIUM|HIGH|CRITICAL)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Classification confidence score")
    matched_rules: list[str] = Field(default_factory=list, description="Matched severity rules")
    evidence: list[str] | None = Field(None, description="Evidence for classification decision")

    model_config = {"extra": "forbid"}


class PolicyEvaluatedPayload(BaseModel):
    """
    Payload for PolicyEvaluated event.
    
    Fired when PolicyAgent evaluates guardrails and approval requirements.
    """

    decision: str = Field(..., description="Policy decision (ALLOW|BLOCK|REQUIRE_APPROVAL)")
    violated_rules: list[str] = Field(default_factory=list, description="Violated policy rules")
    approval_required: bool = Field(False, description="Whether human approval is required")
    guardrail_checks: dict[str, Any] | None = Field(None, description="Guardrail check results")
    playbook_id: int | None = Field(None, description="Assigned playbook ID if approved (P7-12)")
    reasoning: str | None = Field(None, description="Reasoning for playbook assignment (P7-12)")

    model_config = {"extra": "forbid"}


class ResolutionSuggestedPayload(BaseModel):
    """
    Payload for ResolutionSuggested event.
    
    Fired when ResolutionAgent suggests an action or playbook.
    """

    suggested_action: str = Field(..., description="Suggested action or playbook name")
    playbook_id: int | None = Field(None, description="Playbook ID if applicable (P7-13)")
    step_order: int | None = Field(None, description="Step order number if from assigned playbook (P7-13)")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Confidence in suggestion")
    reasoning: str | None = Field(None, description="Reasoning for the suggestion")
    tool_calls: list[dict[str, Any]] | None = Field(None, description="Suggested tool calls")

    model_config = {"extra": "forbid"}


class ResolutionApprovedPayload(BaseModel):
    """
    Payload for ResolutionApproved event.
    
    Fired when a resolution action is approved (by human or auto-approval).
    """

    approved_action: str = Field(..., description="Approved action or playbook name")
    playbook_id: int | None = Field(None, description="Playbook ID if applicable")
    approved_by: str = Field(..., description="Actor who approved (user_id or 'system')")
    approval_timestamp: datetime = Field(..., description="When approval was granted")

    model_config = {"extra": "forbid"}


class FeedbackCapturedPayload(BaseModel):
    """
    Payload for FeedbackCaptured event.
    
    Fired when FeedbackAgent captures user or system feedback.
    """

    feedback_type: str = Field(..., description="Type of feedback (positive|negative|correction)")
    feedback_text: str | None = Field(None, description="Free-form feedback text")
    rating: int | None = Field(None, ge=1, le=5, description="Numeric rating if applicable")
    resolution_effective: bool | None = Field(None, description="Whether resolution was effective")
    playbook_id: int | None = Field(None, description="ID of the playbook used for resolution (P7-14)")
    total_steps: int | None = Field(None, ge=0, description="Total number of steps in the playbook (P7-14)")
    completed_steps: int | None = Field(None, ge=0, description="Number of completed steps (P7-14)")
    duration: float | None = Field(None, ge=0.0, description="Duration in seconds from exception creation to resolution (P7-14)")
    last_actor: str | None = Field(None, description="Last actor that performed an action (P7-14)")

    model_config = {"extra": "forbid"}


class LLMDecisionProposedPayload(BaseModel):
    """
    Payload for LLMDecisionProposed event.
    
    Fired when an LLM-based agent proposes a decision.
    """

    agent_name: str = Field(..., description="Name of the agent (e.g., 'TriageAgent')")
    decision: dict[str, Any] = Field(..., description="LLM decision output")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="LLM confidence score")
    reasoning: str | None = Field(None, description="LLM reasoning/explanation")
    model_used: str | None = Field(None, description="LLM model identifier")
    tokens_used: int | None = Field(None, ge=0, description="Token count if available")

    model_config = {"extra": "forbid"}


class CopilotQuestionAskedPayload(BaseModel):
    """
    Payload for CopilotQuestionAsked event.
    
    Fired when a user asks a question via Co-Pilot.
    """

    question: str = Field(..., description="User's question text")
    context_exception_ids: list[str] = Field(
        default_factory=list, description="Exception IDs in context"
    )
    question_type: str | None = Field(None, description="Type of question (similar|history|sla|etc)")

    model_config = {"extra": "forbid"}


class CopilotAnswerGivenPayload(BaseModel):
    """
    Payload for CopilotAnswerGiven event.
    
    Fired when Co-Pilot provides an answer to a user question.
    """

    question_id: str | None = Field(None, description="Reference to question event if linked")
    answer: str = Field(..., description="Co-Pilot answer text")
    sources: list[dict[str, Any]] | None = Field(None, description="Source exceptions or evidence")
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Answer confidence")

    model_config = {"extra": "forbid"}


# ============================================================================
# Event Envelope
# ============================================================================


class EventEnvelope(BaseModel):
    """
    Canonical event envelope for all exception processing events.
    
    Wraps event payloads with metadata required for persistence and audit.
    Matches the structure expected by the exception_event table.
    """

    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    tenant_id: str = Field(..., min_length=1, description="Tenant identifier")
    exception_id: str = Field(..., min_length=1, description="Exception identifier")
    event_type: str = Field(..., description="Event type (from EventType enum)")
    actor_type: str = Field(..., description="Actor type (agent|user|system)")
    actor_id: str | None = Field(None, description="Actor identifier (agent name, user ID, or system component)")
    payload: dict[str, Any] = Field(..., description="Event payload (typed per event_type)")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Event timestamp")

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        """Validate event_type is a known EventType."""
        valid_types = [e.value for e in EventType]
        if v not in valid_types:
            raise ValueError(f"Invalid event_type: {v}. Must be one of {valid_types}")
        return v

    @field_validator("actor_type")
    @classmethod
    def validate_actor_type(cls, v: str) -> str:
        """Validate actor_type is a known ActorType."""
        valid_types = [e.value for e in ActorType]
        if v not in valid_types:
            raise ValueError(f"Invalid actor_type: {v}. Must be one of {valid_types}")
        return v

    model_config = {"extra": "forbid"}


# ============================================================================
# Event Type to Payload Class Mapping
# ============================================================================

EVENT_PAYLOAD_MAP: dict[str, type[BaseModel]] = {
    EventType.EXCEPTION_CREATED.value: ExceptionCreatedPayload,
    EventType.EXCEPTION_NORMALIZED.value: ExceptionNormalizedPayload,
    EventType.TRIAGE_COMPLETED.value: TriageCompletedPayload,
    EventType.POLICY_EVALUATED.value: PolicyEvaluatedPayload,
    EventType.RESOLUTION_SUGGESTED.value: ResolutionSuggestedPayload,
    EventType.RESOLUTION_APPROVED.value: ResolutionApprovedPayload,
    EventType.FEEDBACK_CAPTURED.value: FeedbackCapturedPayload,
    EventType.LLM_DECISION_PROPOSED.value: LLMDecisionProposedPayload,
    EventType.COPILOT_QUESTION_ASKED.value: CopilotQuestionAskedPayload,
    EventType.COPILOT_ANSWER_GIVEN.value: CopilotAnswerGivenPayload,
}


# ============================================================================
# Helper Functions
# ============================================================================


def validate_and_build_event(
    event_type: str | EventType,
    payload_dict: dict[str, Any],
    tenant_id: str,
    exception_id: str,
    actor_type: str | ActorType,
    actor_id: str | None = None,
    event_id: UUID | None = None,
    created_at: datetime | None = None,
) -> EventEnvelope:
    """
    Validate payload structure and build EventEnvelope.
    
    This function:
    1. Validates that event_type is known
    2. Validates payload structure against the event type's payload schema
    3. Creates an EventEnvelope with validated data
    
    Args:
        event_type: Event type (string or EventType enum)
        payload_dict: Payload data as dictionary
        tenant_id: Tenant identifier
        exception_id: Exception identifier
        actor_type: Actor type (string or ActorType enum)
        actor_id: Optional actor identifier
        event_id: Optional event ID (generated if not provided)
        created_at: Optional timestamp (defaults to now)
        
    Returns:
        EventEnvelope with validated payload
        
    Raises:
        ValueError: If event_type is unknown or payload validation fails
        ValidationError: If payload structure is invalid
    """
    # Normalize event_type
    if isinstance(event_type, EventType):
        event_type_str = event_type.value
    else:
        event_type_str = event_type
    
    # Validate event_type is known
    if event_type_str not in EVENT_PAYLOAD_MAP:
        raise ValueError(f"Unknown event_type: {event_type_str}. Must be one of {list(EVENT_PAYLOAD_MAP.keys())}")
    
    # Get payload class for this event type
    payload_class = EVENT_PAYLOAD_MAP[event_type_str]
    
    # Validate payload structure
    try:
        validated_payload = payload_class(**payload_dict)
    except Exception as e:
        raise ValueError(f"Invalid payload for {event_type_str}: {e}") from e
    
    # Normalize actor_type
    if isinstance(actor_type, ActorType):
        actor_type_str = actor_type.value
    else:
        actor_type_str = actor_type
    
    # Build envelope
    envelope = EventEnvelope(
        event_id=event_id or uuid4(),
        tenant_id=tenant_id,
        exception_id=exception_id,
        event_type=event_type_str,
        actor_type=actor_type_str,
        actor_id=actor_id,
        payload=validated_payload.model_dump(),
        created_at=created_at or datetime.utcnow(),
    )
    
    return envelope

