"""
Domain event types and schemas for exception processing.

This module defines canonical event types and payload schemas for the
append-only event log, as specified in docs/phase6-persistence-mvp.md Sections 6.1 and 6.2.
"""

from src.domain.events.exception_events import (
    CopilotAnswerGivenPayload,
    CopilotQuestionAskedPayload,
    EventEnvelope,
    EventType,
    ExceptionCreatedPayload,
    ExceptionNormalizedPayload,
    FeedbackCapturedPayload,
    LLMDecisionProposedPayload,
    PolicyEvaluatedPayload,
    ResolutionApprovedPayload,
    ResolutionSuggestedPayload,
    TriageCompletedPayload,
    validate_and_build_event,
)

__all__ = [
    "EventType",
    "EventEnvelope",
    "ExceptionCreatedPayload",
    "ExceptionNormalizedPayload",
    "TriageCompletedPayload",
    "PolicyEvaluatedPayload",
    "ResolutionSuggestedPayload",
    "ResolutionApprovedPayload",
    "FeedbackCapturedPayload",
    "LLMDecisionProposedPayload",
    "CopilotQuestionAskedPayload",
    "CopilotAnswerGivenPayload",
    "validate_and_build_event",
]

