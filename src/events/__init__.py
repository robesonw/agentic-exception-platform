"""
Canonical Event Model for Phase 9.

Defines the event schema and all event types for the event-driven architecture.
"""

from src.events.schema import CanonicalEvent
from src.events.types import (
    # Inbound events
    ExceptionIngested,
    ExceptionNormalized,
    ManualExceptionCreated,
    # Agent events
    TriageRequested,
    TriageCompleted,
    PolicyEvaluationRequested,
    PolicyEvaluationCompleted,
    PlaybookMatched,
    PlaybookRecalculationRequested,
    PlaybookStepCompletionRequested,
    StepExecutionRequested,
    ToolExecutionRequested,
    ToolExecutionCompleted,
    FeedbackCaptured,
    # Control events
    RetryScheduled,
    DeadLettered,
    SLAImminent,
    SLAExpired,
    BackpressureDetected,
)

__all__ = [
    "CanonicalEvent",
    # Inbound events
    "ExceptionIngested",
    "ExceptionNormalized",
    "ManualExceptionCreated",
    # Agent events
    "TriageRequested",
    "TriageCompleted",
    "PolicyEvaluationRequested",
    "PolicyEvaluationCompleted",
    "PlaybookMatched",
    "PlaybookRecalculationRequested",
    "PlaybookStepCompletionRequested",
    "StepExecutionRequested",
    "ToolExecutionRequested",
    "ToolExecutionCompleted",
    "FeedbackCaptured",
    # Control events
    "RetryScheduled",
    "DeadLettered",
    "SLAImminent",
    "SLAExpired",
    "BackpressureDetected",
]

