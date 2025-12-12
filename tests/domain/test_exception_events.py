"""
Unit tests for exception event types and payload schemas.

Tests:
- Valid payload structures
- Rejection of invalid fields
- Event envelope creation
- Event type validation
- Actor type validation
"""

import pytest
from datetime import datetime
from uuid import UUID

from pydantic import ValidationError

from src.domain.events.exception_events import (
    ActorType,
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


# ============================================================================
# Payload Schema Tests
# ============================================================================


class TestExceptionCreatedPayload:
    """Test ExceptionCreatedPayload schema."""

    def test_valid_payload(self):
        """Test valid ExceptionCreated payload."""
        payload = ExceptionCreatedPayload(
            source_system="ERP",
            raw_payload={"error": "Invalid data"},
        )
        assert payload.source_system == "ERP"
        assert payload.raw_payload == {"error": "Invalid data"}
        assert payload.normalized_fields is None

    def test_with_normalized_fields(self):
        """Test payload with normalized fields."""
        payload = ExceptionCreatedPayload(
            source_system="ERP",
            raw_payload={"error": "Invalid data"},
            normalized_fields={"domain": "finance"},
        )
        assert payload.normalized_fields == {"domain": "finance"}

    def test_rejects_extra_fields(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            ExceptionCreatedPayload(
                source_system="ERP",
                raw_payload={"error": "Invalid data"},
                invalid_field="should fail",
            )

    def test_requires_source_system(self):
        """Test that source_system is required."""
        with pytest.raises(ValidationError):
            ExceptionCreatedPayload(raw_payload={"error": "Invalid data"})


class TestExceptionNormalizedPayload:
    """Test ExceptionNormalizedPayload schema."""

    def test_valid_payload(self):
        """Test valid ExceptionNormalized payload."""
        payload = ExceptionNormalizedPayload(
            normalized_context={"domain": "finance", "entity": "account_123"},
        )
        assert payload.normalized_context == {"domain": "finance", "entity": "account_123"}
        assert payload.domain is None
        assert payload.entity is None

    def test_with_domain_and_entity(self):
        """Test payload with domain and entity."""
        payload = ExceptionNormalizedPayload(
            normalized_context={"domain": "finance"},
            domain="finance",
            entity="account_123",
        )
        assert payload.domain == "finance"
        assert payload.entity == "account_123"


class TestTriageCompletedPayload:
    """Test TriageCompletedPayload schema."""

    def test_valid_payload(self):
        """Test valid TriageCompleted payload."""
        payload = TriageCompletedPayload(
            exception_type="DataQualityFailure",
            severity="HIGH",
            confidence=0.95,
        )
        assert payload.exception_type == "DataQualityFailure"
        assert payload.severity == "HIGH"
        assert payload.confidence == 0.95
        assert payload.matched_rules == []

    def test_confidence_bounds(self):
        """Test confidence must be between 0 and 1."""
        # Valid
        TriageCompletedPayload(exception_type="Test", severity="LOW", confidence=0.5)
        
        # Invalid: too high
        with pytest.raises(ValidationError):
            TriageCompletedPayload(exception_type="Test", severity="LOW", confidence=1.5)
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            TriageCompletedPayload(exception_type="Test", severity="LOW", confidence=-0.1)


class TestPolicyEvaluatedPayload:
    """Test PolicyEvaluatedPayload schema."""

    def test_valid_payload(self):
        """Test valid PolicyEvaluated payload."""
        payload = PolicyEvaluatedPayload(
            decision="ALLOW",
            approval_required=False,
        )
        assert payload.decision == "ALLOW"
        assert payload.approval_required is False
        assert payload.violated_rules == []

    def test_with_violated_rules(self):
        """Test payload with violated rules."""
        payload = PolicyEvaluatedPayload(
            decision="BLOCK",
            violated_rules=["rule1", "rule2"],
            approval_required=True,
        )
        assert payload.decision == "BLOCK"
        assert payload.violated_rules == ["rule1", "rule2"]
        assert payload.approval_required is True


class TestResolutionSuggestedPayload:
    """Test ResolutionSuggestedPayload schema."""

    def test_valid_payload(self):
        """Test valid ResolutionSuggested payload."""
        payload = ResolutionSuggestedPayload(
            suggested_action="run_playbook",
            playbook_id=123,
            confidence=0.8,
        )
        assert payload.suggested_action == "run_playbook"
        assert payload.playbook_id == 123
        assert payload.confidence == 0.8


class TestResolutionApprovedPayload:
    """Test ResolutionApprovedPayload schema."""

    def test_valid_payload(self):
        """Test valid ResolutionApproved payload."""
        timestamp = datetime.utcnow()
        payload = ResolutionApprovedPayload(
            approved_action="run_playbook",
            approved_by="user_123",
            approval_timestamp=timestamp,
        )
        assert payload.approved_action == "run_playbook"
        assert payload.approved_by == "user_123"
        assert payload.approval_timestamp == timestamp


class TestFeedbackCapturedPayload:
    """Test FeedbackCapturedPayload schema."""

    def test_valid_payload(self):
        """Test valid FeedbackCaptured payload."""
        payload = FeedbackCapturedPayload(
            feedback_type="positive",
            rating=5,
        )
        assert payload.feedback_type == "positive"
        assert payload.rating == 5

    def test_rating_bounds(self):
        """Test rating must be between 1 and 5."""
        # Valid
        FeedbackCapturedPayload(feedback_type="positive", rating=3)
        
        # Invalid: too high
        with pytest.raises(ValidationError):
            FeedbackCapturedPayload(feedback_type="positive", rating=6)
        
        # Invalid: too low
        with pytest.raises(ValidationError):
            FeedbackCapturedPayload(feedback_type="positive", rating=0)


class TestLLMDecisionProposedPayload:
    """Test LLMDecisionProposedPayload schema."""

    def test_valid_payload(self):
        """Test valid LLMDecisionProposed payload."""
        payload = LLMDecisionProposedPayload(
            agent_name="TriageAgent",
            decision={"type": "DataQualityFailure", "severity": "HIGH"},
        )
        assert payload.agent_name == "TriageAgent"
        assert payload.decision == {"type": "DataQualityFailure", "severity": "HIGH"}

    def test_tokens_used_non_negative(self):
        """Test tokens_used must be non-negative."""
        # Valid
        LLMDecisionProposedPayload(
            agent_name="TestAgent",
            decision={},
            tokens_used=100,
        )
        
        # Invalid: negative
        with pytest.raises(ValidationError):
            LLMDecisionProposedPayload(
                agent_name="TestAgent",
                decision={},
                tokens_used=-1,
            )


class TestCopilotQuestionAskedPayload:
    """Test CopilotQuestionAskedPayload schema."""

    def test_valid_payload(self):
        """Test valid CopilotQuestionAsked payload."""
        payload = CopilotQuestionAskedPayload(
            question="What similar exceptions exist?",
            context_exception_ids=["exc1", "exc2"],
        )
        assert payload.question == "What similar exceptions exist?"
        assert payload.context_exception_ids == ["exc1", "exc2"]


class TestCopilotAnswerGivenPayload:
    """Test CopilotAnswerGivenPayload schema."""

    def test_valid_payload(self):
        """Test valid CopilotAnswerGiven payload."""
        payload = CopilotAnswerGivenPayload(
            answer="Found 5 similar exceptions",
            confidence=0.9,
        )
        assert payload.answer == "Found 5 similar exceptions"
        assert payload.confidence == 0.9


# ============================================================================
# EventEnvelope Tests
# ============================================================================


class TestEventEnvelope:
    """Test EventEnvelope schema."""

    def test_valid_envelope(self):
        """Test valid EventEnvelope."""
        envelope = EventEnvelope(
            tenant_id="tenant_001",
            exception_id="exc_001",
            event_type="ExceptionCreated",
            actor_type="system",
            payload={"source_system": "ERP", "raw_payload": {}},
        )
        assert envelope.tenant_id == "tenant_001"
        assert envelope.exception_id == "exc_001"
        assert envelope.event_type == "ExceptionCreated"
        assert envelope.actor_type == "system"
        assert isinstance(envelope.event_id, UUID)
        assert isinstance(envelope.created_at, datetime)

    def test_invalid_event_type(self):
        """Test that invalid event_type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            EventEnvelope(
                tenant_id="tenant_001",
                exception_id="exc_001",
                event_type="InvalidEventType",
                actor_type="system",
                payload={},
            )
        assert "Invalid event_type" in str(exc_info.value)

    def test_invalid_actor_type(self):
        """Test that invalid actor_type is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            EventEnvelope(
                tenant_id="tenant_001",
                exception_id="exc_001",
                event_type="ExceptionCreated",
                actor_type="invalid",
                payload={},
            )
        assert "Invalid actor_type" in str(exc_info.value)

    def test_rejects_extra_fields(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            EventEnvelope(
                tenant_id="tenant_001",
                exception_id="exc_001",
                event_type="ExceptionCreated",
                actor_type="system",
                payload={},
                invalid_field="should fail",
            )

    def test_actor_id_optional(self):
        """Test that actor_id is optional."""
        envelope = EventEnvelope(
            tenant_id="tenant_001",
            exception_id="exc_001",
            event_type="ExceptionCreated",
            actor_type="system",
            payload={},
        )
        assert envelope.actor_id is None


# ============================================================================
# validate_and_build_event Tests
# ============================================================================


class TestValidateAndBuildEvent:
    """Test validate_and_build_event helper function."""

    def test_valid_exception_created_event(self):
        """Test building a valid ExceptionCreated event."""
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
        
        assert envelope.event_type == "ExceptionCreated"
        assert envelope.tenant_id == "tenant_001"
        assert envelope.exception_id == "exc_001"
        assert envelope.actor_type == "system"
        assert envelope.payload["source_system"] == "ERP"
        assert isinstance(envelope.event_id, UUID)
        assert isinstance(envelope.created_at, datetime)

    def test_valid_triage_completed_event(self):
        """Test building a valid TriageCompleted event."""
        envelope = validate_and_build_event(
            event_type="TriageCompleted",
            payload_dict={
                "exception_type": "DataQualityFailure",
                "severity": "HIGH",
                "confidence": 0.95,
            },
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="agent",
            actor_id="TriageAgent",
        )
        
        assert envelope.event_type == "TriageCompleted"
        assert envelope.actor_type == "agent"
        assert envelope.actor_id == "TriageAgent"
        assert envelope.payload["exception_type"] == "DataQualityFailure"
        assert envelope.payload["severity"] == "HIGH"
        assert envelope.payload["confidence"] == 0.95

    def test_unknown_event_type(self):
        """Test that unknown event_type is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_and_build_event(
                event_type="UnknownEvent",
                payload_dict={},
                tenant_id="tenant_001",
                exception_id="exc_001",
                actor_type="system",
            )
        assert "Unknown event_type" in str(exc_info.value)

    def test_invalid_payload_structure(self):
        """Test that invalid payload structure is rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_and_build_event(
                event_type=EventType.EXCEPTION_CREATED,
                payload_dict={
                    "invalid_field": "should fail",
                },
                tenant_id="tenant_001",
                exception_id="exc_001",
                actor_type="system",
            )
        assert "Invalid payload" in str(exc_info.value)

    def test_missing_required_payload_field(self):
        """Test that missing required payload fields are rejected."""
        with pytest.raises(ValueError) as exc_info:
            validate_and_build_event(
                event_type=EventType.EXCEPTION_CREATED,
                payload_dict={
                    "source_system": "ERP",
                    # Missing required raw_payload
                },
                tenant_id="tenant_001",
                exception_id="exc_001",
                actor_type="system",
            )
        assert "Invalid payload" in str(exc_info.value)

    def test_custom_event_id(self):
        """Test that custom event_id is used if provided."""
        custom_id = UUID("12345678-1234-5678-1234-567812345678")
        envelope = validate_and_build_event(
            event_type=EventType.EXCEPTION_CREATED,
            payload_dict={
                "source_system": "ERP",
                "raw_payload": {},
            },
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="system",
            event_id=custom_id,
        )
        assert envelope.event_id == custom_id

    def test_custom_timestamp(self):
        """Test that custom timestamp is used if provided."""
        custom_time = datetime(2024, 1, 1, 12, 0, 0)
        envelope = validate_and_build_event(
            event_type=EventType.EXCEPTION_CREATED,
            payload_dict={
                "source_system": "ERP",
                "raw_payload": {},
            },
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="system",
            created_at=custom_time,
        )
        assert envelope.created_at == custom_time

    def test_string_event_type(self):
        """Test that string event_type works."""
        envelope = validate_and_build_event(
            event_type="ExceptionCreated",
            payload_dict={
                "source_system": "ERP",
                "raw_payload": {},
            },
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="system",
        )
        assert envelope.event_type == "ExceptionCreated"

    def test_string_actor_type(self):
        """Test that string actor_type works."""
        envelope = validate_and_build_event(
            event_type=EventType.EXCEPTION_CREATED,
            payload_dict={
                "source_system": "ERP",
                "raw_payload": {},
            },
            tenant_id="tenant_001",
            exception_id="exc_001",
            actor_type="user",
        )
        assert envelope.actor_type == "user"

    def test_all_event_types(self):
        """Test that all event types can be built."""
        test_cases = [
            (EventType.EXCEPTION_CREATED, {"source_system": "ERP", "raw_payload": {}}),
            (EventType.EXCEPTION_NORMALIZED, {"normalized_context": {"domain": "finance"}}),
            (EventType.TRIAGE_COMPLETED, {"exception_type": "Test", "severity": "LOW"}),
            (EventType.POLICY_EVALUATED, {"decision": "ALLOW"}),
            (EventType.RESOLUTION_SUGGESTED, {"suggested_action": "run_playbook"}),
            (
                EventType.RESOLUTION_APPROVED,
                {
                    "approved_action": "run_playbook",
                    "approved_by": "user_123",
                    "approval_timestamp": datetime.utcnow(),
                },
            ),
            (EventType.FEEDBACK_CAPTURED, {"feedback_type": "positive"}),
            (EventType.LLM_DECISION_PROPOSED, {"agent_name": "TestAgent", "decision": {}}),
            (EventType.COPILOT_QUESTION_ASKED, {"question": "Test question"}),
            (EventType.COPILOT_ANSWER_GIVEN, {"answer": "Test answer"}),
        ]
        
        for event_type, payload_dict in test_cases:
            envelope = validate_and_build_event(
                event_type=event_type,
                payload_dict=payload_dict,
                tenant_id="tenant_001",
                exception_id="exc_001",
                actor_type="system",
            )
            assert envelope.event_type == event_type.value
            assert envelope.payload is not None

