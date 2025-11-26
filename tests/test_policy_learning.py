"""
Comprehensive tests for Phase 2 Policy Learning and Improvement.

Tests:
- PolicyLearning.ingest_feedback
- Pattern detection for recurring exceptions
- Success/failure pattern detection
- Human override pattern detection
- Policy suggestion generation
- Learning artifact persistence
- Integration with FeedbackAgent
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.learning.policy_learning import (
    PolicyLearning,
    PolicyLearningError,
    PolicySuggestion,
)
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def temp_storage_dir():
    """Temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def policy_learning(temp_storage_dir):
    """PolicyLearning instance for testing."""
    return PolicyLearning(storage_dir=temp_storage_dir)


@pytest.fixture
def sample_exception():
    """Sample exception for testing."""
    return ExceptionRecord(
        exceptionId="exc_1",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD-001"},
    )


class TestPolicyLearningIngestFeedback:
    """Tests for PolicyLearning.ingest_feedback."""

    def test_ingest_feedback_success(self, policy_learning, temp_storage_dir):
        """Test successful feedback ingestion."""
        policy_learning.ingest_feedback(
            tenant_id="TENANT_A",
            exception_id="exc_1",
            outcome="RESOLVED",
            exception_type="SETTLEMENT_FAIL",
            severity="HIGH",
        )
        
        # Verify feedback was persisted
        feedback_file = Path(temp_storage_dir) / "TENANT_A.jsonl"
        assert feedback_file.exists()
        
        # Read and verify content
        with open(feedback_file) as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) == 1
            
            feedback = json.loads(lines[0])
            assert feedback["exceptionId"] == "exc_1"
            assert feedback["outcome"] == "RESOLVED"
            assert feedback["exceptionType"] == "SETTLEMENT_FAIL"

    def test_ingest_feedback_with_human_override(self, policy_learning, temp_storage_dir):
        """Test feedback ingestion with human override."""
        human_override = {
            "type": "severity_change",
            "originalSeverity": "MEDIUM",
            "newSeverity": "HIGH",
            "reason": "Manual escalation",
        }
        
        policy_learning.ingest_feedback(
            tenant_id="TENANT_A",
            exception_id="exc_1",
            outcome="ESCALATED",
            human_override=human_override,
            exception_type="SETTLEMENT_FAIL",
        )
        
        # Verify override was persisted
        feedback_file = Path(temp_storage_dir) / "TENANT_A.jsonl"
        with open(feedback_file) as f:
            feedback = json.loads(f.readline())
            assert feedback["humanOverride"] == human_override

    def test_ingest_feedback_multiple_exceptions(self, policy_learning, temp_storage_dir):
        """Test ingesting feedback for multiple exceptions."""
        # Ingest multiple feedback records
        for i in range(5):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED" if i % 2 == 0 else "FAILED",
                exception_type="SETTLEMENT_FAIL",
                severity="HIGH",
            )
        
        # Verify all were persisted
        feedback_file = Path(temp_storage_dir) / "TENANT_A.jsonl"
        with open(feedback_file) as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) == 5

    def test_ingest_feedback_tenant_isolation(self, policy_learning, temp_storage_dir):
        """Test that feedback is isolated per tenant."""
        policy_learning.ingest_feedback(
            tenant_id="TENANT_A",
            exception_id="exc_1",
            outcome="RESOLVED",
            exception_type="SETTLEMENT_FAIL",
        )
        
        policy_learning.ingest_feedback(
            tenant_id="TENANT_B",
            exception_id="exc_2",
            outcome="FAILED",
            exception_type="PAYMENT_FAIL",
        )
        
        # Verify separate files
        file_a = Path(temp_storage_dir) / "TENANT_A.jsonl"
        file_b = Path(temp_storage_dir) / "TENANT_B.jsonl"
        
        assert file_a.exists()
        assert file_b.exists()
        
        # Verify isolation
        with open(file_a) as f:
            feedback_a = json.loads(f.readline())
            assert feedback_a["tenantId"] == "TENANT_A"
        
        with open(file_b) as f:
            feedback_b = json.loads(f.readline())
            assert feedback_b["tenantId"] == "TENANT_B"


class TestPolicyLearningPatternDetection:
    """Tests for pattern detection."""

    def test_detect_recurring_exceptions(self, policy_learning):
        """Test detection of recurring exceptions."""
        # Ingest multiple occurrences of same exception type
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED",
                exception_type="SETTLEMENT_FAIL",
                severity="HIGH",
            )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Should suggest severity override
        severity_suggestions = [
            s for s in suggestions if s.suggestion_type == "severity_override"
        ]
        assert len(severity_suggestions) > 0
        
        suggestion = severity_suggestions[0]
        assert suggestion.confidence >= 0.7
        assert "SETTLEMENT_FAIL" in suggestion.description
        assert suggestion.suggested_change["exceptionType"] == "SETTLEMENT_FAIL"

    def test_detect_success_failure_patterns(self, policy_learning):
        """Test detection of success/failure patterns."""
        # Ingest feedback with high failure rate
        for i in range(10):
            outcome = "FAILED" if i < 7 else "RESOLVED"  # 70% failure rate
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome=outcome,
                exception_type="SETTLEMENT_FAIL",
            )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Should suggest approval rule
        approval_suggestions = [
            s for s in suggestions if s.suggestion_type == "approval_rule"
        ]
        assert len(approval_suggestions) > 0
        
        suggestion = approval_suggestions[0]
        assert suggestion.confidence >= 0.7
        assert "failure rate" in suggestion.description.lower()
        assert suggestion.suggested_change.get("requireApproval") is True

    def test_detect_high_success_patterns(self, policy_learning):
        """Test detection of high success patterns."""
        # Ingest feedback with high success rate
        for i in range(10):
            outcome = "RESOLVED" if i < 9 else "FAILED"  # 90% success rate
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome=outcome,
                exception_type="SETTLEMENT_FAIL",
            )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Should suggest auto-approval
        auto_approval_suggestions = [
            s for s in suggestions if s.suggestion_type == "auto_approval"
        ]
        assert len(auto_approval_suggestions) > 0
        
        suggestion = auto_approval_suggestions[0]
        assert suggestion.confidence >= 0.7
        assert "success rate" in suggestion.description.lower()
        assert suggestion.suggested_change.get("autoApprove") is True

    def test_detect_human_override_patterns(self, policy_learning):
        """Test detection of human override patterns."""
        # Ingest feedback with frequent human overrides
        for i in range(10):
            human_override = (
                {
                    "type": "severity_change",
                    "originalSeverity": "MEDIUM",
                    "newSeverity": "HIGH",
                }
                if i < 5  # 50% override rate
                else None
            )
            
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED",
                exception_type="SETTLEMENT_FAIL",
                human_override=human_override,
            )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Should suggest policy update
        policy_update_suggestions = [
            s for s in suggestions if s.suggestion_type == "policy_update"
        ]
        assert len(policy_update_suggestions) > 0
        
        suggestion = policy_update_suggestions[0]
        assert suggestion.confidence >= 0.7
        assert "human overrides" in suggestion.description.lower()
        assert "overridePattern" in suggestion.suggested_change


class TestPolicyLearningSuggestions:
    """Tests for policy suggestion generation."""

    def test_suggestions_sorted_by_confidence(self, policy_learning):
        """Test that suggestions are sorted by confidence."""
        # Ingest various feedback
        for i in range(15):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED" if i < 12 else "FAILED",
                exception_type="SETTLEMENT_FAIL",
                severity="HIGH",
            )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.5,
        )
        
        # Verify sorted by confidence (descending)
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].confidence >= suggestions[i + 1].confidence

    def test_suggestions_respect_min_confidence(self, policy_learning):
        """Test that suggestions respect minimum confidence threshold."""
        # Ingest minimal feedback (low confidence patterns)
        for i in range(3):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED",
                exception_type="SETTLEMENT_FAIL",
            )
        
        # Get suggestions with high min_confidence
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.9,
        )
        
        # All suggestions should meet threshold
        for suggestion in suggestions:
            assert suggestion.confidence >= 0.9

    def test_no_suggestions_for_insufficient_data(self, policy_learning):
        """Test that no suggestions are generated for insufficient data."""
        # Ingest minimal feedback
        policy_learning.ingest_feedback(
            tenant_id="TENANT_A",
            exception_id="exc_1",
            outcome="RESOLVED",
            exception_type="SETTLEMENT_FAIL",
        )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Should have few or no suggestions
        # (depends on thresholds, but with only 1 data point, should be minimal)
        assert len(suggestions) <= 1  # May have 0 or 1 low-confidence suggestion


class TestPolicyLearningPersistence:
    """Tests for learning artifact persistence."""

    def test_persistence_creates_directory(self, temp_storage_dir):
        """Test that persistence creates storage directory."""
        storage_path = Path(temp_storage_dir) / "custom" / "learning"
        learning = PolicyLearning(storage_dir=str(storage_path))
        
        # Directory should be created
        assert storage_path.exists()
        assert storage_path.is_dir()

    def test_persistence_appends_to_file(self, policy_learning, temp_storage_dir):
        """Test that persistence appends to JSONL file."""
        # Ingest multiple feedback records
        for i in range(3):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED",
                exception_type="SETTLEMENT_FAIL",
            )
        
        # Verify all in file
        feedback_file = Path(temp_storage_dir) / "TENANT_A.jsonl"
        with open(feedback_file) as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) == 3

    def test_load_patterns_from_persisted_data(self, policy_learning, temp_storage_dir):
        """Test that patterns can be loaded from persisted data."""
        # Ingest feedback
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED",
                exception_type="SETTLEMENT_FAIL",
                severity="HIGH",
            )
        
        # Create new instance (simulates restart)
        new_learning = PolicyLearning(storage_dir=temp_storage_dir)
        
        # Get suggestions (should load from persisted data)
        suggestions = new_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Should have suggestions based on persisted data
        assert len(suggestions) > 0


class TestPolicyLearningSafety:
    """Tests for safety features (suggestions only, never auto-applied)."""

    def test_suggestions_never_auto_applied(self, policy_learning):
        """Test that suggestions are never auto-applied."""
        # Ingest feedback
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id="TENANT_A",
                exception_id=f"exc_{i}",
                outcome="RESOLVED",
                exception_type="SETTLEMENT_FAIL",
                severity="HIGH",
            )
        
        # Get suggestions
        suggestions = policy_learning.get_policy_suggestions(
            tenant_id="TENANT_A",
            min_confidence=0.7,
        )
        
        # Verify suggestions are returned (not applied)
        assert isinstance(suggestions, list)
        for suggestion in suggestions:
            assert isinstance(suggestion, PolicySuggestion)
            # Suggestions have description and rationale, but are not applied
            assert suggestion.description
            assert suggestion.rationale
            assert suggestion.suggested_change


class TestPolicyLearningIntegration:
    """Tests for integration with FeedbackAgent."""

    def test_feedback_agent_integrates_learning(self):
        """Test that FeedbackAgent can integrate with PolicyLearning."""
        from src.agents.feedback import FeedbackAgent
        from src.learning.policy_learning import PolicyLearning
        
        # Create learning instance
        learning = PolicyLearning()
        
        # Create feedback agent with learning
        feedback_agent = FeedbackAgent(policy_learning=learning)
        
        # Verify integration
        assert feedback_agent.policy_learning is not None
        assert feedback_agent.policy_learning == learning

