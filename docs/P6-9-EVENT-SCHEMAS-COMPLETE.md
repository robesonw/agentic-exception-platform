# P6-9: Standard Event Types and Payload Schemas - Implementation Complete

## ✅ Implementation Summary

Successfully implemented canonical event types and structured payload schemas for the append-only event log, as specified in `docs/phase6-persistence-mvp.md` Sections 6.1 and 6.2.

## Files Created

### 1. `src/domain/events/exception_events.py`
Main module containing:
- **EventType Enum**: 10 canonical event types
- **ActorType Enum**: 3 actor types (agent, user, system)
- **10 Payload Schemas**: One Pydantic model per event type
- **EventEnvelope**: Canonical event envelope schema
- **validate_and_build_event()**: Helper function for validation and envelope creation

### 2. `src/domain/events/__init__.py`
Package initialization with exports for all public APIs.

### 3. `tests/domain/test_exception_events.py`
Comprehensive unit tests covering:
- Valid payload structures
- Rejection of invalid fields
- Event envelope creation
- Event type validation
- Actor type validation
- All 10 event types

### 4. `scripts/test_event_schemas.py`
Quick validation script for manual testing.

## Event Types Implemented

All 10 canonical event types from the specification:

1. **ExceptionCreated** - New exception ingested
2. **ExceptionNormalized** - Exception normalized by IntakeAgent
3. **TriageCompleted** - Classification and severity assessment complete
4. **PolicyEvaluated** - Guardrails and approval requirements evaluated
5. **ResolutionSuggested** - Resolution action or playbook suggested
6. **ResolutionApproved** - Resolution action approved
7. **FeedbackCaptured** - User or system feedback captured
8. **LLMDecisionProposed** - LLM-based agent decision proposed
9. **CopilotQuestionAsked** - User question via Co-Pilot
10. **CopilotAnswerGiven** - Co-Pilot answer provided

## Payload Schemas

Each event type has a corresponding Pydantic payload schema:

- **ExceptionCreatedPayload**: `source_system`, `raw_payload`, `normalized_fields`
- **ExceptionNormalizedPayload**: `normalized_context`, `domain`, `entity`
- **TriageCompletedPayload**: `exception_type`, `severity`, `confidence`, `matched_rules`, `evidence`
- **PolicyEvaluatedPayload**: `decision`, `violated_rules`, `approval_required`, `guardrail_checks`
- **ResolutionSuggestedPayload**: `suggested_action`, `playbook_id`, `confidence`, `reasoning`, `tool_calls`
- **ResolutionApprovedPayload**: `approved_action`, `playbook_id`, `approved_by`, `approval_timestamp`
- **FeedbackCapturedPayload**: `feedback_type`, `feedback_text`, `rating`, `resolution_effective`
- **LLMDecisionProposedPayload**: `agent_name`, `decision`, `confidence`, `reasoning`, `model_used`, `tokens_used`
- **CopilotQuestionAskedPayload**: `question`, `context_exception_ids`, `question_type`
- **CopilotAnswerGivenPayload**: `question_id`, `answer`, `sources`, `confidence`

## EventEnvelope Schema

Canonical envelope wrapping all events:

```python
class EventEnvelope(BaseModel):
    event_id: UUID
    tenant_id: str
    exception_id: str
    event_type: str  # Validated against EventType enum
    actor_type: str  # Validated against ActorType enum
    actor_id: str | None
    payload: dict[str, Any]  # Typed per event_type
    created_at: datetime
```

## Validation Features

1. **Type Safety**: All payloads are Pydantic models with strict validation
2. **Extra Fields Rejected**: All schemas use `extra="forbid"` to prevent invalid fields
3. **Enum Validation**: Event types and actor types validated against enums
4. **Bounds Checking**: Numeric fields (confidence, rating, tokens) have proper bounds
5. **Required Fields**: All required fields enforced

## Helper Function

`validate_and_build_event()`:
- Validates event_type is known
- Validates payload structure against event type's schema
- Creates EventEnvelope with validated data
- Supports both enum and string inputs for event_type and actor_type
- Generates UUID and timestamp if not provided

## Test Results

✅ All tests passing:
- Payload schema validation
- Invalid field rejection
- Event envelope creation
- Event type validation
- Actor type validation
- All 10 event types can be built successfully

## Usage Example

```python
from src.domain.events.exception_events import (
    EventType,
    ActorType,
    validate_and_build_event,
)

# Create an ExceptionCreated event
envelope = validate_and_build_event(
    event_type=EventType.EXCEPTION_CREATED,
    payload_dict={
        "source_system": "ERP",
        "raw_payload": {"error": "Invalid data"},
    },
    tenant_id="tenant_001",
    exception_id="exc_001",
    actor_type=ActorType.SYSTEM,
)

# envelope is a validated EventEnvelope ready for persistence
```

## Next Steps

This module provides the foundation for:
1. **Agent Integration**: Agents can use these schemas when emitting events
2. **Repository Integration**: `ExceptionEventRepository` can validate events before persistence
3. **Kafka Migration**: Event structure matches Phase 9 requirements
4. **Type Safety**: Full type checking for all event payloads

## Notes

- **No Persistence**: This module only defines types and schemas. Persistence is handled by repositories.
- **Domain-Agnostic**: Payloads contain only event-specific fields, not domain-specific attributes.
- **Future-Proof**: Structure supports easy migration to Kafka-based event sourcing in Phase 9.

## Acceptance Criteria Met

✅ Canonical event types defined as Enum  
✅ Pydantic payload schemas for each event type  
✅ EventEnvelope schema created  
✅ validate_and_build_event helper function  
✅ Unit tests for valid payload structures  
✅ Unit tests for rejection of invalid fields  
✅ Unit tests for event envelope creation  
✅ No persistence logic (as required)

