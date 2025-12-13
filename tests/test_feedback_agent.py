"""
Comprehensive tests for FeedbackAgent.
Tests outcome field appending, decision creation, and audit logging.
"""

from datetime import datetime, timezone

import pytest

from src.agents.feedback import FeedbackAgent, FeedbackAgentError
from src.audit.logger import AuditLogger
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def sample_audit_logger(tmp_path, monkeypatch):
    """Create a sample audit logger with temp directory."""
    audit_dir = tmp_path / "runtime" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    def patched_get_log_file(self, tenant_id=None):
        if self._log_file is None:
            self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file
    
    def patched_ensure_dir(self):
        audit_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(AuditLogger, "_get_log_file", patched_get_log_file)
    monkeypatch.setattr(AuditLogger, "_ensure_audit_directory", patched_ensure_dir)
    
    return AuditLogger(run_id="test_run", tenant_id="tenant_001")


@pytest.fixture
def mock_resolution_output():
    """Create mock ResolutionAgent output context."""
    return {
        "resolvedPlan": [
            {
                "stepNumber": 1,
                "action": "getSettlement",
                "toolName": "getSettlement",
                "toolDescription": "Fetch settlement details",
                "parameters": {"orderId": "ORD-123"},
                "endpoint": "https://api.example.com/getSettlement",
                "validated": True,
            },
            {
                "stepNumber": 2,
                "action": "triggerSettlementRetry",
                "toolName": "triggerSettlementRetry",
                "toolDescription": "Retry settlement",
                "parameters": {"orderId": "ORD-123"},
                "endpoint": "https://api.example.com/triggerSettlementRetry",
                "validated": True,
            },
        ],
    }


class TestFeedbackAgentOutcomeFields:
    """Tests for outcome field appending."""

    @pytest.mark.asyncio
    async def test_append_feedback_captured_at(self, sample_audit_logger):
        """Test that feedbackCapturedAt is appended to normalized context."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        assert exception.normalized_context is not None
        assert "feedbackCapturedAt" in exception.normalized_context
        assert isinstance(exception.normalized_context["feedbackCapturedAt"], str)
        # Verify it's a valid ISO timestamp
        datetime.fromisoformat(exception.normalized_context["feedbackCapturedAt"].replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_append_learning_artifacts_placeholder(self, sample_audit_logger):
        """Test that learningArtifacts placeholder is appended."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        assert exception.normalized_context is not None
        assert "learningArtifacts" in exception.normalized_context
        assert exception.normalized_context["learningArtifacts"] == []

    @pytest.mark.asyncio
    async def test_update_resolution_status_with_plan(self, sample_audit_logger, mock_resolution_output):
        """Test that resolution status is updated when resolved plan exists."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = mock_resolution_output
        decision = await agent.process(exception, context)
        
        assert exception.resolution_status == ResolutionStatus.IN_PROGRESS

    @pytest.mark.asyncio
    async def test_keep_resolution_status_without_plan(self, sample_audit_logger):
        """Test that resolution status remains OPEN when no plan exists."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="UNKNOWN_TYPE",
            severity=Severity.LOW,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}  # No resolved plan
        decision = await agent.process(exception, context)
        
        assert exception.resolution_status == ResolutionStatus.OPEN

    @pytest.mark.asyncio
    async def test_preserve_existing_normalized_context(self, sample_audit_logger):
        """Test that existing normalized context is preserved."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        existing_context = {
            "pipelineId": "pipeline_001",
            "normalizedAt": "2024-01-15T10:30:00Z",
        }
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext=existing_context,
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        assert exception.normalized_context is not None
        assert exception.normalized_context["pipelineId"] == "pipeline_001"
        assert exception.normalized_context["normalizedAt"] == "2024-01-15T10:30:00Z"
        assert "feedbackCapturedAt" in exception.normalized_context
        assert "learningArtifacts" in exception.normalized_context


class TestFeedbackAgentDecision:
    """Tests for agent decision creation."""

    @pytest.mark.asyncio
    async def test_decision_contains_required_fields(self, sample_audit_logger):
        """Test that decision contains all required fields."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert decision.confidence == 1.0
        assert isinstance(decision.evidence, list)
        assert decision.next_step == "complete"

    @pytest.mark.asyncio
    async def test_decision_evidence_includes_resolution_summary(self, sample_audit_logger, mock_resolution_output):
        """Test that decision evidence includes resolution summary."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = mock_resolution_output
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "Resolution plan executed" in evidence_text
        assert "Actions executed: 2" in evidence_text

    @pytest.mark.asyncio
    async def test_decision_evidence_includes_feedback_timestamp(self, sample_audit_logger):
        """Test that decision evidence includes feedback timestamp."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "Feedback captured at:" in evidence_text

    @pytest.mark.asyncio
    async def test_decision_evidence_includes_learning_artifacts_placeholder(self, sample_audit_logger):
        """Test that decision evidence includes learning artifacts placeholder."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "Learning artifacts:" in evidence_text
        assert "MVP placeholder" in evidence_text

    @pytest.mark.asyncio
    async def test_decision_evidence_includes_final_status(self, sample_audit_logger):
        """Test that decision evidence includes final resolution status."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "Final status:" in evidence_text
        assert "OPEN" in evidence_text or "IN_PROGRESS" in evidence_text


class TestFeedbackAgentAuditLogging:
    """Tests for audit logging integration."""

    @pytest.mark.asyncio
    async def test_logs_agent_event(self, sample_audit_logger):
        """Test that agent events are logged."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        sample_audit_logger.close()
        
        # Verify log file was created
        log_file = sample_audit_logger._get_log_file()
        assert log_file.exists()
        
        # Verify log contains agent event
        import json
        with open(log_file, "r", encoding="utf-8") as f:
            line = f.readline()
            entry = json.loads(line)
        
        assert entry["event_type"] == "agent_event"
        assert entry["data"]["agent_name"] == "FeedbackAgent"

    @pytest.mark.asyncio
    async def test_logs_without_audit_logger(self):
        """Test that agent works without audit logger."""
        agent = FeedbackAgent()
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        # Should not raise
        decision = await agent.process(exception, context)
        
        assert decision.decision == "FEEDBACK_CAPTURED"


class TestFeedbackAgentWithMockResolutionOutput:
    """Tests using mocked ResolutionAgent output."""

    @pytest.mark.asyncio
    async def test_process_with_resolved_plan(self, sample_audit_logger, mock_resolution_output):
        """Test processing with mocked ResolutionAgent output containing resolved plan."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-123"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = mock_resolution_output
        decision = await agent.process(exception, context)
        
        # Verify outcome fields
        assert exception.normalized_context is not None
        assert "feedbackCapturedAt" in exception.normalized_context
        assert "learningArtifacts" in exception.normalized_context
        
        # Verify resolution status updated
        assert exception.resolution_status == ResolutionStatus.IN_PROGRESS
        
        # Verify decision
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert decision.confidence == 1.0
        assert decision.next_step == "complete"
        
        # Verify evidence includes resolution summary
        evidence_text = " ".join(decision.evidence)
        assert "Resolution plan executed" in evidence_text

    @pytest.mark.asyncio
    async def test_process_without_resolved_plan(self, sample_audit_logger):
        """Test processing without resolved plan (non-actionable case)."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="UNKNOWN_TYPE",
            severity=Severity.LOW,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}  # No resolved plan
        decision = await agent.process(exception, context)
        
        # Verify outcome fields still appended
        assert exception.normalized_context is not None
        assert "feedbackCapturedAt" in exception.normalized_context
        assert "learningArtifacts" in exception.normalized_context
        
        # Verify resolution status remains OPEN
        assert exception.resolution_status == ResolutionStatus.OPEN
        
        # Verify decision
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert decision.confidence == 1.0
        assert decision.next_step == "complete"
        
        # Verify evidence mentions no plan
        evidence_text = " ".join(decision.evidence)
        assert "No resolution plan" in evidence_text or "non-actionable" in evidence_text.lower()


class TestFeedbackAgentSchemaCorrectness:
    """Tests for schema correctness and validation."""

    @pytest.mark.asyncio
    async def test_normalized_context_schema(self, sample_audit_logger):
        """Test that normalized context follows correct schema."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify normalized context is a dict
        assert isinstance(exception.normalized_context, dict)
        
        # Verify required fields exist
        assert "feedbackCapturedAt" in exception.normalized_context
        assert "learningArtifacts" in exception.normalized_context
        
        # Verify types
        assert isinstance(exception.normalized_context["feedbackCapturedAt"], str)
        assert isinstance(exception.normalized_context["learningArtifacts"], list)

    @pytest.mark.asyncio
    async def test_decision_schema(self, sample_audit_logger):
        """Test that decision follows correct schema."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify decision structure
        assert hasattr(decision, "decision")
        assert hasattr(decision, "confidence")
        assert hasattr(decision, "evidence")
        assert hasattr(decision, "next_step")
        
        # Verify values
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert decision.confidence == 1.0
        assert isinstance(decision.evidence, list)
        assert decision.next_step == "complete"


class TestFeedbackAgentDomainAgnostic:
    """Tests to ensure domain-agnostic behavior."""

    @pytest.mark.asyncio
    async def test_works_with_finance_domain(self, sample_audit_logger):
        """Test that agent works with finance domain exceptions."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"accountId": "ACC-123"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert exception.normalized_context is not None

    @pytest.mark.asyncio
    async def test_works_with_healthcare_domain(self, sample_audit_logger):
        """Test that agent works with healthcare domain exceptions."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="HC-EXC-001",
            tenantId="TENANT_HEALTHCARE_042",
            sourceSystem="PharmacySystem",
            exceptionType="PHARMACY_DUPLICATE_THERAPY",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-123"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert exception.normalized_context is not None


class TestFeedbackAgentIntegration:
    """Integration tests for complete feedback workflow."""

    @pytest.mark.asyncio
    async def test_complete_feedback_workflow(self, sample_audit_logger, mock_resolution_output):
        """Test complete feedback workflow with resolution output."""
        agent = FeedbackAgent(audit_logger=sample_audit_logger)
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-123"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        context = mock_resolution_output
        decision = await agent.process(exception, context)
        sample_audit_logger.close()
        
        # Verify all components
        assert decision.decision == "FEEDBACK_CAPTURED"
        assert decision.confidence == 1.0
        assert decision.next_step == "complete"
        assert exception.normalized_context is not None
        assert "feedbackCapturedAt" in exception.normalized_context
        assert "learningArtifacts" in exception.normalized_context
        assert exception.resolution_status == ResolutionStatus.IN_PROGRESS


class TestFeedbackAgentPlaybookMetrics:
    """Tests for playbook metrics computation and event emission (P7-14)."""

    @pytest.mark.asyncio
    async def test_computes_metrics_when_resolved(self, sample_audit_logger):
        """Test that playbook metrics are computed when exception is resolved."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock repositories
        mock_playbook_repo = AsyncMock()
        mock_events_repo = AsyncMock()
        
        # Mock playbook with steps
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 1
        mock_playbook.tenant_id = "tenant_001"
        
        step1 = MagicMock()
        step1.step_order = 1
        step1.name = "Step 1"
        step1.action_type = "call_tool"
        step1.params = {}
        
        step2 = MagicMock()
        step2.step_order = 2
        step2.name = "Step 2"
        step2.action_type = "call_tool"
        step2.params = {}
        
        mock_playbook_repo.get_playbook_with_steps.return_value = (mock_playbook, [step1, step2])
        
        # Mock events
        mock_event = MagicMock()
        mock_event.actor_id = "ResolutionAgent"
        mock_events_repo.get_events_for_exception.return_value = [mock_event]
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = FeedbackAgent(
            audit_logger=sample_audit_logger,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
            currentPlaybookId=1,
            currentStep=2,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify metrics were computed
        evidence_text = " ".join(decision.evidence)
        assert "Playbook ID: 1" in evidence_text
        assert "Total steps: 2" in evidence_text
        assert "Completed steps: 2" in evidence_text
        assert "Duration:" in evidence_text
        assert "Last actor: ResolutionAgent" in evidence_text
        
        # Verify event was emitted
        mock_events_repo.append_event_if_new.assert_called_once()
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.event_type == "FeedbackCaptured"
        assert call_args.payload["playbook_id"] == 1
        assert call_args.payload["total_steps"] == 2
        assert call_args.payload["completed_steps"] == 2
        assert call_args.payload["last_actor"] == "ResolutionAgent"

    @pytest.mark.asyncio
    async def test_no_metrics_when_not_resolved(self, sample_audit_logger):
        """Test that metrics are not computed when exception is not resolved."""
        from unittest.mock import AsyncMock
        
        mock_playbook_repo = AsyncMock()
        mock_events_repo = AsyncMock()
        
        agent = FeedbackAgent(
            audit_logger=sample_audit_logger,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.IN_PROGRESS,
            currentPlaybookId=1,
            currentStep=1,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify metrics were not computed
        evidence_text = " ".join(decision.evidence)
        assert "Playbook ID:" not in evidence_text
        
        # Verify event was still emitted but without metrics
        mock_events_repo.append_event_if_new.assert_called_once()
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.payload["playbook_id"] is None

    @pytest.mark.asyncio
    async def test_no_metrics_when_no_playbook(self, sample_audit_logger):
        """Test that metrics are not computed when no playbook is assigned."""
        from unittest.mock import AsyncMock
        
        mock_playbook_repo = AsyncMock()
        mock_events_repo = AsyncMock()
        
        agent = FeedbackAgent(
            audit_logger=sample_audit_logger,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify metrics were not computed
        evidence_text = " ".join(decision.evidence)
        assert "Playbook ID:" not in evidence_text
        
        # Verify playbook repository was not called
        mock_playbook_repo.get_playbook_with_steps.assert_not_called()

    @pytest.mark.asyncio
    async def test_metrics_includes_duration(self, sample_audit_logger):
        """Test that duration is computed correctly."""
        from unittest.mock import AsyncMock, MagicMock
        
        mock_playbook_repo = AsyncMock()
        mock_events_repo = AsyncMock()
        
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 1
        mock_playbook.tenant_id = "tenant_001"
        
        step = MagicMock()
        step.step_order = 1
        step.name = "Step 1"
        step.action_type = "call_tool"
        step.params = {}
        
        mock_playbook_repo.get_playbook_with_steps.return_value = (mock_playbook, [step])
        mock_events_repo.get_events_for_exception.return_value = []
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = FeedbackAgent(
            audit_logger=sample_audit_logger,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        # Create exception with timestamp 100 seconds ago
        from datetime import timedelta
        exception_timestamp = datetime.now(timezone.utc) - timedelta(seconds=100)
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=exception_timestamp,
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
            currentPlaybookId=1,
            currentStep=1,
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify duration is approximately 100 seconds (allow some tolerance)
        mock_events_repo.append_event_if_new.assert_called_once()
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        duration = call_args.payload["duration"]
        assert duration is not None
        assert 95 <= duration <= 105  # Allow 5 second tolerance

    @pytest.mark.asyncio
    async def test_last_actor_from_audit_trail_fallback(self, sample_audit_logger):
        """Test that last_actor falls back to audit trail if events are not available."""
        from unittest.mock import AsyncMock, MagicMock
        from src.models.exception_record import AuditEntry
        
        mock_playbook_repo = AsyncMock()
        mock_events_repo = AsyncMock()
        
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 1
        mock_playbook.tenant_id = "tenant_001"
        
        step = MagicMock()
        step.step_order = 1
        step.name = "Step 1"
        step.action_type = "call_tool"
        step.params = {}
        
        mock_playbook_repo.get_playbook_with_steps.return_value = (mock_playbook, [step])
        # Simulate events repository failure
        mock_events_repo.get_events_for_exception.side_effect = Exception("Events unavailable")
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = FeedbackAgent(
            audit_logger=sample_audit_logger,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
            currentPlaybookId=1,
            currentStep=1,
            auditTrail=[
                AuditEntry(
                    action="Processed by PolicyAgent",
                    timestamp=datetime.now(timezone.utc),
                    actor="PolicyAgent",
                ),
                AuditEntry(
                    action="Processed by ResolutionAgent",
                    timestamp=datetime.now(timezone.utc),
                    actor="ResolutionAgent",
                ),
            ],
        )
        
        context = {}
        decision = await agent.process(exception, context)
        
        # Verify last_actor is from audit trail
        mock_events_repo.append_event_if_new.assert_called_once()
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.payload["last_actor"] == "ResolutionAgent"

    @pytest.mark.asyncio
    async def test_integration_metrics_capture(self, sample_audit_logger):
        """Integration test for complete metrics capture workflow."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock repositories
        mock_playbook_repo = AsyncMock()
        mock_events_repo = AsyncMock()
        
        # Mock playbook with 3 steps
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 42
        mock_playbook.tenant_id = "tenant_001"
        
        steps = []
        for i in range(1, 4):
            step = MagicMock()
            step.step_order = i
            step.name = f"Step {i}"
            step.action_type = "call_tool"
            step.params = {"param": f"value{i}"}
            steps.append(step)
        
        mock_playbook_repo.get_playbook_with_steps.return_value = (mock_playbook, steps)
        
        # Mock events with multiple actors
        mock_event1 = MagicMock()
        mock_event1.actor_id = "TriageAgent"
        mock_event2 = MagicMock()
        mock_event2.actor_id = "PolicyAgent"
        mock_event3 = MagicMock()
        mock_event3.actor_id = "ResolutionAgent"
        mock_events_repo.get_events_for_exception.return_value = [mock_event1, mock_event2, mock_event3]
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = FeedbackAgent(
            audit_logger=sample_audit_logger,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_integration_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
            currentPlaybookId=42,
            currentStep=3,  # All 3 steps completed
        )
        
        context = {"resolvedPlan": [{"step": 1}, {"step": 2}, {"step": 3}]}
        decision = await agent.process(exception, context)
        
        # Verify all metrics are present in evidence
        evidence_text = " ".join(decision.evidence)
        assert "Playbook ID: 42" in evidence_text
        assert "Total steps: 3" in evidence_text
        assert "Completed steps: 3" in evidence_text
        assert "Duration:" in evidence_text
        assert "Last actor: ResolutionAgent" in evidence_text
        
        # Verify event payload contains all metrics
        mock_events_repo.append_event_if_new.assert_called_once()
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        payload = call_args.payload
        
        assert payload["playbook_id"] == 42
        assert payload["total_steps"] == 3
        assert payload["completed_steps"] == 3
        assert payload["duration"] is not None
        assert payload["duration"] >= 0
        assert payload["last_actor"] == "ResolutionAgent"
        assert payload["resolution_effective"] is True
        assert payload["feedback_type"] == "positive"
