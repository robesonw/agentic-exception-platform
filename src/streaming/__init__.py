"""
Streaming module for Phase 3.

Provides incremental decision streaming, event bus functionality, and backpressure control.
"""

from src.streaming.backpressure import (
    BackpressureController,
    BackpressurePolicy,
    BackpressureState,
    get_backpressure_controller,
)
from src.streaming.decision_stream import (
    DecisionStreamService,
    EventBus,
    StageCompletedEvent,
    emit_stage_completed,
    get_decision_stream_service,
    get_event_bus,
)

__all__ = [
    "DecisionStreamService",
    "EventBus",
    "StageCompletedEvent",
    "emit_stage_completed",
    "get_decision_stream_service",
    "get_event_bus",
    "BackpressureController",
    "BackpressurePolicy",
    "BackpressureState",
    "get_backpressure_controller",
]

