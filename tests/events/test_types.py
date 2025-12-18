"""
Unit tests for event type definitions.
"""

import pytest
from datetime import datetime, timezone

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
    StepExecutionRequested,
    ToolExecutionRequested,
    ToolExecutionCompleted,
    FeedbackCaptured,
    # Control events
    RetryScheduled,
    DeadLettered,
    SLAImminent,
    SLAExpired,
)


class TestInboundEvents:
    """Test inbound event types."""
    
    def test_exception_ingested(self):
        """Test ExceptionIngested event."""
        event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"error": "test"},
            source_system="ERP",
            ingestion_method="api",
        )
        
        assert event.event_type == "ExceptionIngested"
        assert event.tenant_id == "tenant_001"
        assert event.payload["raw_payload"] == {"error": "test"}
        assert event.payload["source_system"] == "ERP"
        assert event.payload["ingestion_method"] == "api"
        
    def test_exception_normalized(self):
        """Test ExceptionNormalized event."""
        normalized_exception = {
            "exception_id": "exc_001",
            "exception_type": "DataQualityFailure",
            "severity": "HIGH",
        }
        
        event = ExceptionNormalized.create(
            tenant_id="tenant_001",
            normalized_exception=normalized_exception,
            exception_id="exc_001",
            normalization_rules=["rule1", "rule2"],
        )
        
        assert event.event_type == "ExceptionNormalized"
        assert event.exception_id == "exc_001"
        assert event.payload["normalized_exception"] == normalized_exception
        assert event.payload["normalization_rules"] == ["rule1", "rule2"]
        
    def test_manual_exception_created(self):
        """Test ManualExceptionCreated event."""
        event = ManualExceptionCreated.create(
            tenant_id="tenant_001",
            exception_data={"type": "test"},
            created_by="user_123",
            creation_method="ui",
        )
        
        assert event.event_type == "ManualExceptionCreated"
        assert event.payload["exception_data"] == {"type": "test"}
        assert event.payload["created_by"] == "user_123"
        assert event.payload["creation_method"] == "ui"


class TestAgentEvents:
    """Test agent event types."""
    
    def test_triage_requested(self):
        """Test TriageRequested event."""
        event = TriageRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            requested_by="orchestrator",
        )
        
        assert event.event_type == "TriageRequested"
        assert event.exception_id == "exc_001"
        assert event.payload["exception_id"] == "exc_001"
        assert event.payload["requested_by"] == "orchestrator"
        
    def test_triage_completed(self):
        """Test TriageCompleted event."""
        triage_result = {
            "decision": "proceed",
            "confidence": 0.9,
            "evidence": ["evidence1"],
        }
        
        event = TriageCompleted.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            triage_result=triage_result,
            severity="HIGH",
            exception_type="DataQualityFailure",
        )
        
        assert event.event_type == "TriageCompleted"
        assert event.payload["triage_result"] == triage_result
        assert event.payload["severity"] == "HIGH"
        assert event.payload["exception_type"] == "DataQualityFailure"
        
    def test_policy_evaluation_requested(self):
        """Test PolicyEvaluationRequested event."""
        event = PolicyEvaluationRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            requested_by="triage_agent",
        )
        
        assert event.event_type == "PolicyEvaluationRequested"
        assert event.payload["requested_by"] == "triage_agent"
        
    def test_policy_evaluation_completed(self):
        """Test PolicyEvaluationCompleted event."""
        policy_result = {
            "decision": "approved",
            "approved_actions": ["action1"],
        }
        
        event = PolicyEvaluationCompleted.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            policy_result=policy_result,
            approved_actions=["action1", "action2"],
            guardrails_applied=["guardrail1"],
        )
        
        assert event.event_type == "PolicyEvaluationCompleted"
        assert event.payload["approved_actions"] == ["action1", "action2"]
        assert event.payload["guardrails_applied"] == ["guardrail1"]
        
    def test_playbook_matched(self):
        """Test PlaybookMatched event."""
        event = PlaybookMatched.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id="pb_001",
            playbook_name="Data Quality Fix",
            match_score=0.95,
            match_reason="Exception type matches",
        )
        
        assert event.event_type == "PlaybookMatched"
        assert event.payload["playbook_id"] == "pb_001"
        assert event.payload["playbook_name"] == "Data Quality Fix"
        assert event.payload["match_score"] == 0.95
        assert event.payload["match_reason"] == "Exception type matches"
        
    def test_step_execution_requested(self):
        """Test StepExecutionRequested event."""
        step_action = {
            "action_type": "notify",
            "recipient": "admin@example.com",
        }
        
        event = StepExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id="pb_001",
            step_number=1,
            step_action=step_action,
        )
        
        assert event.event_type == "StepExecutionRequested"
        assert event.payload["step_number"] == 1
        assert event.payload["step_action"] == step_action
        
    def test_tool_execution_requested(self):
        """Test ToolExecutionRequested event."""
        event = ToolExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="tool_001",
            tool_name="Data Fix Tool",
            tool_params={"param1": "value1"},
            execution_context={"context": "test"},
        )
        
        assert event.event_type == "ToolExecutionRequested"
        assert event.payload["tool_id"] == "tool_001"
        assert event.payload["tool_name"] == "Data Fix Tool"
        assert event.payload["tool_params"] == {"param1": "value1"}
        
    def test_tool_execution_completed(self):
        """Test ToolExecutionCompleted event."""
        result = {"status": "success", "output": "fixed"}
        
        event = ToolExecutionCompleted.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="tool_001",
            execution_id="exec_001",
            result=result,
            status="success",
        )
        
        assert event.event_type == "ToolExecutionCompleted"
        assert event.payload["status"] == "success"
        assert event.payload["result"] == result
        
    def test_tool_execution_completed_with_error(self):
        """Test ToolExecutionCompleted event with error."""
        event = ToolExecutionCompleted.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="tool_001",
            execution_id="exec_001",
            result={},
            status="error",
            error_message="Tool execution failed",
        )
        
        assert event.payload["status"] == "error"
        assert event.payload["error_message"] == "Tool execution failed"
        
    def test_feedback_captured(self):
        """Test FeedbackCaptured event."""
        feedback_data = {
            "rating": 5,
            "comment": "Great resolution",
        }
        
        event = FeedbackCaptured.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            feedback_type="resolution",
            feedback_data=feedback_data,
            captured_by="user_123",
        )
        
        assert event.event_type == "FeedbackCaptured"
        assert event.payload["feedback_type"] == "resolution"
        assert event.payload["feedback_data"] == feedback_data
        assert event.payload["captured_by"] == "user_123"


class TestControlEvents:
    """Test control and ops event types."""
    
    def test_retry_scheduled(self):
        """Test RetryScheduled event."""
        event = RetryScheduled.create(
            tenant_id="tenant_001",
            retry_reason="Transient error",
            retry_count=2,
            retry_delay_seconds=60.0,
            original_event_id="event_001",
            exception_id="exc_001",
        )
        
        assert event.event_type == "RetryScheduled"
        assert event.payload["retry_count"] == 2
        assert event.payload["retry_delay_seconds"] == 60.0
        assert event.payload["original_event_id"] == "event_001"
        
    def test_dead_lettered(self):
        """Test DeadLettered event."""
        event = DeadLettered.create(
            tenant_id="tenant_001",
            original_event_id="event_001",
            original_event_type="ExceptionIngested",
            failure_reason="Max retries exceeded",
            retry_count=5,
            original_topic="exceptions",
            exception_id="exc_001",
        )
        
        assert event.event_type == "DeadLettered"
        assert event.payload["original_event_type"] == "ExceptionIngested"
        assert event.payload["retry_count"] == 5
        assert event.payload["original_topic"] == "exceptions"
        
    def test_sla_imminent(self):
        """Test SLAImminent event."""
        sla_deadline = datetime.now(timezone.utc)
        
        event = SLAImminent.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            sla_deadline=sla_deadline,
            time_remaining_seconds=3600.0,
            threshold_percentage=0.8,
        )
        
        assert event.event_type == "SLAImminent"
        assert event.payload["time_remaining_seconds"] == 3600.0
        assert event.payload["threshold_percentage"] == 0.8
        
    def test_sla_expired(self):
        """Test SLAExpired event."""
        sla_deadline = datetime.now(timezone.utc)
        
        event = SLAExpired.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            sla_deadline=sla_deadline,
            breach_duration_seconds=1800.0,
        )
        
        assert event.event_type == "SLAExpired"
        assert event.payload["breach_duration_seconds"] == 1800.0


class TestEventImmutability:
    """Test that all event types are immutable."""
    
    @pytest.mark.parametrize("event_class", [
        ExceptionIngested,
        ExceptionNormalized,
        ManualExceptionCreated,
        TriageRequested,
        TriageCompleted,
        PolicyEvaluationRequested,
        PolicyEvaluationCompleted,
        PlaybookMatched,
        StepExecutionRequested,
        ToolExecutionRequested,
        ToolExecutionCompleted,
        FeedbackCaptured,
        RetryScheduled,
        DeadLettered,
        SLAImminent,
        SLAExpired,
    ])
    def test_event_immutability(self, event_class):
        """Test that all event types are immutable."""
        # Create a minimal event
        if event_class == ExceptionIngested:
            event = event_class.create(
                tenant_id="tenant_001",
                raw_payload={"data": "test"},
                source_system="test",
            )
        elif event_class == ExceptionNormalized:
            event = event_class.create(
                tenant_id="tenant_001",
                normalized_exception={"exception_id": "exc_001"},
                exception_id="exc_001",
            )
        elif event_class == ManualExceptionCreated:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_data={"data": "test"},
                created_by="user_123",
            )
        elif event_class in [TriageRequested, PolicyEvaluationRequested]:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
            )
        elif event_class == TriageCompleted:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                triage_result={"decision": "proceed"},
            )
        elif event_class == PolicyEvaluationCompleted:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                policy_result={"decision": "approved"},
            )
        elif event_class == PlaybookMatched:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id="pb_001",
                playbook_name="Test Playbook",
            )
        elif event_class == StepExecutionRequested:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id="pb_001",
                step_number=1,
                step_action={"action": "test"},
            )
        elif event_class == ToolExecutionRequested:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                tool_id="tool_001",
                tool_name="Test Tool",
                tool_params={},
            )
        elif event_class == ToolExecutionCompleted:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                tool_id="tool_001",
                execution_id="exec_001",
                result={},
                status="success",
            )
        elif event_class == FeedbackCaptured:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                feedback_type="resolution",
                feedback_data={},
            )
        elif event_class == RetryScheduled:
            event = event_class.create(
                tenant_id="tenant_001",
                retry_reason="test",
                retry_count=1,
                retry_delay_seconds=60.0,
                original_event_id="event_001",
            )
        elif event_class == DeadLettered:
            event = event_class.create(
                tenant_id="tenant_001",
                original_event_id="event_001",
                original_event_type="TestEvent",
                failure_reason="test",
                retry_count=1,
                original_topic="test-topic",
            )
        elif event_class == SLAImminent:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                sla_deadline=datetime.now(timezone.utc),
                time_remaining_seconds=3600.0,
            )
        elif event_class == SLAExpired:
            event = event_class.create(
                tenant_id="tenant_001",
                exception_id="exc_001",
                sla_deadline=datetime.now(timezone.utc),
                breach_duration_seconds=1800.0,
            )
        
        # Attempting to modify should raise an error (Pydantic raises TypeError for frozen models)
        with pytest.raises((TypeError, ValueError)):
            event.event_type = "ModifiedEvent"


class TestEventVersioning:
    """Test event versioning support."""
    
    def test_event_default_version(self):
        """Test events have default version of 1."""
        event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"data": "test"},
            source_system="test",
        )
        
        assert event.version == 1
        
    def test_event_custom_version(self):
        """Test events can have custom version."""
        event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"data": "test"},
            source_system="test",
            version=2,
        )
        
        assert event.version == 2
        
    def test_event_version_validation(self):
        """Test version must be >= 1."""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ExceptionIngested.create(
                tenant_id="tenant_001",
                raw_payload={"data": "test"},
                source_system="test",
                version=0,
            )

