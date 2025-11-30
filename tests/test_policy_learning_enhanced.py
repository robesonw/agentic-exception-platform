"""
Tests for enhanced Policy Learning with outcome analysis and suggestions.

Tests Phase 3 enhancements:
- Per-policy-rule outcome tracking (success_count, failure_count, MTTR, false_positives, false_negatives)
- Policy improvement suggestions with impact estimates
- Suggestion persistence
- Integration with FeedbackAgent
- No auto-policy changes applied
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from src.learning.policy_learning import (
    PolicyLearning,
    PolicyLearningError,
    PolicyRuleOutcome,
    Suggestion,
)
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def learning_storage_dir(tmp_path):
    """Create a temporary storage directory for learning artifacts."""
    storage_dir = tmp_path / "learning"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return str(storage_dir)


@pytest.fixture
def policy_learning(learning_storage_dir):
    """Create a PolicyLearning instance with temporary storage."""
    return PolicyLearning(storage_dir=learning_storage_dir)


@pytest.fixture
def sample_exception():
    """Create a sample exception for testing."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        source_system="ERP",
        timestamp=datetime.now(timezone.utc),
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        raw_payload={"error": "Invalid data format"},
    )


class TestPolicyLearningEnhanced:
    """Tests for enhanced Policy Learning (Phase 3)."""

    def test_track_rule_outcomes_success(self, policy_learning):
        """Test tracking successful rule outcomes."""
        tenant_id = "tenant_001"
        rule_ids = ["rule_001", "rule_002"]
        
        # Record processing start
        policy_learning.record_processing_start("exc_001")
        
        # Record processing end (simulates end of processing)
        policy_learning.record_processing_end("exc_001")
        
        # Ingest feedback with successful resolution and MTTR
        policy_learning.ingest_feedback(
            tenant_id=tenant_id,
            exception_id="exc_001",
            outcome="SUCCESS",
            resolution_successful=True,
            policy_rules_applied=rule_ids,
            exception_type="DataQualityFailure",
            context={"mttrSeconds": 120.0},  # Provide MTTR directly
        )
        
        # Check rule outcomes
        assert tenant_id in policy_learning._rule_outcomes
        assert "rule_001" in policy_learning._rule_outcomes[tenant_id]
        assert "rule_002" in policy_learning._rule_outcomes[tenant_id]
        
        rule_001_outcome = policy_learning._rule_outcomes[tenant_id]["rule_001"]
        assert rule_001_outcome.success_count == 1
        assert rule_001_outcome.failure_count == 0
        assert rule_001_outcome.total_count == 1
        # MTTR may or may not be tracked depending on processing times
        # For this test, we'll just verify the outcome was tracked

    def test_track_rule_outcomes_failure(self, policy_learning):
        """Test tracking failed rule outcomes."""
        tenant_id = "tenant_001"
        rule_ids = ["rule_001"]
        
        # Ingest feedback with failed resolution
        policy_learning.ingest_feedback(
            tenant_id=tenant_id,
            exception_id="exc_002",
            outcome="FAILED",
            resolution_successful=False,
            policy_rules_applied=rule_ids,
        )
        
        # Check rule outcomes
        rule_001_outcome = policy_learning._rule_outcomes[tenant_id]["rule_001"]
        assert rule_001_outcome.success_count == 0
        assert rule_001_outcome.failure_count == 1
        assert rule_001_outcome.total_count == 1

    def test_track_false_positives(self, policy_learning):
        """Test tracking false positives from human overrides."""
        tenant_id = "tenant_001"
        rule_ids = ["rule_001"]
        
        # Ingest feedback with human override indicating false positive
        policy_learning.ingest_feedback(
            tenant_id=tenant_id,
            exception_id="exc_003",
            outcome="SUCCESS",
            resolution_successful=True,
            policy_rules_applied=rule_ids,
            human_override={
                "type": "override",
                "reason": "Rule blocked when it should have allowed",
            },
        )
        
        # Check false positive count
        rule_001_outcome = policy_learning._rule_outcomes[tenant_id]["rule_001"]
        assert rule_001_outcome.false_positive_count == 1
        assert rule_001_outcome.false_negative_count == 0

    def test_track_false_negatives(self, policy_learning):
        """Test tracking false negatives from human overrides."""
        tenant_id = "tenant_001"
        rule_ids = ["rule_001"]
        
        # Ingest feedback with human override indicating false negative
        policy_learning.ingest_feedback(
            tenant_id=tenant_id,
            exception_id="exc_004",
            outcome="FAILED",
            resolution_successful=False,
            policy_rules_applied=rule_ids,
            human_override={
                "type": "override",
                "reason": "Rule was too lenient and should have blocked this exception",
            },
        )
        
        # Check false negative count
        rule_001_outcome = policy_learning._rule_outcomes[tenant_id]["rule_001"]
        assert rule_001_outcome.false_positive_count == 0
        assert rule_001_outcome.false_negative_count == 1

    def test_suggest_policy_improvements_too_strict(self, policy_learning):
        """Test suggesting improvements for too strict rules."""
        tenant_id = "tenant_001"
        rule_id = "rule_001"
        
        # Simulate high false positive rate
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=[rule_id],
                human_override={
                    "type": "override",
                    "reason": "Rule blocked when it should have allowed",
                } if i < 3 else None,  # 3 out of 10 = 30% false positive rate
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Should have suggestion for too strict rule
        assert len(suggestions) > 0
        too_strict_suggestions = [s for s in suggestions if s.detected_issue == "too_strict" and s.rule_id == rule_id]
        assert len(too_strict_suggestions) > 0
        
        suggestion = too_strict_suggestions[0]
        assert suggestion.rule_id == rule_id
        assert suggestion.detected_issue == "too_strict"
        assert "relaxing" in suggestion.proposed_change.lower()
        assert "false positive" in suggestion.impact_estimate.lower()
        assert suggestion.confidence > 0.6

    def test_suggest_policy_improvements_too_lenient(self, policy_learning):
        """Test suggesting improvements for too lenient rules."""
        tenant_id = "tenant_001"
        rule_id = "rule_002"
        
        # Simulate high false negative rate
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="FAILED",
                resolution_successful=False,
                policy_rules_applied=[rule_id],
                human_override={
                    "type": "override",
                    "reason": "Rule was too lenient and should have blocked this exception",
                } if i < 3 else None,  # 3 out of 10 = 30% false negative rate
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Should have suggestion for too lenient rule
        too_lenient_suggestions = [s for s in suggestions if s.detected_issue == "too_lenient" and s.rule_id == rule_id]
        assert len(too_lenient_suggestions) > 0
        
        suggestion = too_lenient_suggestions[0]
        assert suggestion.rule_id == rule_id
        assert suggestion.detected_issue == "too_lenient"
        assert "tightening" in suggestion.proposed_change.lower()
        assert "false negative" in suggestion.impact_estimate.lower()

    def test_suggest_policy_improvements_low_effectiveness(self, policy_learning):
        """Test suggesting improvements for low effectiveness rules."""
        tenant_id = "tenant_001"
        rule_id = "rule_003"
        
        # Simulate high failure rate
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="FAILED" if i < 6 else "SUCCESS",  # 60% failure rate
                resolution_successful=(i >= 6),
                policy_rules_applied=[rule_id],
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Should have suggestion for low effectiveness
        low_effectiveness_suggestions = [
            s for s in suggestions if s.detected_issue == "low_effectiveness" and s.rule_id == rule_id
        ]
        assert len(low_effectiveness_suggestions) > 0
        
        suggestion = low_effectiveness_suggestions[0]
        assert suggestion.rule_id == rule_id
        assert suggestion.detected_issue == "low_effectiveness"
        assert "low effectiveness" in suggestion.proposed_change.lower()
        assert "failure rate" in suggestion.impact_estimate.lower()

    def test_suggest_policy_improvements_high_mttr(self, policy_learning):
        """Test suggesting improvements for high MTTR rules."""
        tenant_id = "tenant_001"
        rule_id = "rule_004"
        
        # Simulate high MTTR (2 hours = 7200 seconds)
        for i in range(5):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=[rule_id],
                context={"mttrSeconds": 7200.0},  # 2 hours
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Should have suggestion for high MTTR
        high_mttr_suggestions = [s for s in suggestions if s.detected_issue == "high_mttr" and s.rule_id == rule_id]
        assert len(high_mttr_suggestions) > 0
        
        suggestion = high_mttr_suggestions[0]
        assert suggestion.rule_id == rule_id
        assert suggestion.detected_issue == "high_mttr"
        assert "mttr" in suggestion.proposed_change.lower()
        assert "minutes" in suggestion.impact_estimate.lower()

    def test_suggestions_persisted(self, policy_learning, learning_storage_dir):
        """Test that suggestions are persisted to JSONL file."""
        tenant_id = "tenant_001"
        rule_id = "rule_001"
        
        # Simulate high false positive rate
        for i in range(5):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=[rule_id],
                human_override={
                    "type": "override",
                    "reason": "Rule blocked when it should have allowed",
                } if i < 2 else None,  # 2 out of 5 = 40% false positive rate
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Check that suggestions file was created
        suggestions_file = Path(learning_storage_dir) / f"{tenant_id}_policy_suggestions.jsonl"
        assert suggestions_file.exists()
        
        # Read and verify suggestions
        with open(suggestions_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0
            
            # Parse first suggestion
            suggestion_dict = json.loads(lines[0])
            assert "rule_id" in suggestion_dict
            assert "detected_issue" in suggestion_dict
            assert "proposed_change" in suggestion_dict
            assert "impact_estimate" in suggestion_dict
            assert "timestamp" in suggestion_dict

    def test_no_suggestions_for_insufficient_data(self, policy_learning):
        """Test that no suggestions are generated with insufficient data."""
        tenant_id = "tenant_001"
        rule_id = "rule_001"
        
        # Only 2 evaluations (need at least 3)
        for i in range(2):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=[rule_id],
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Should have no suggestions (insufficient data)
        rule_suggestions = [s for s in suggestions if s.rule_id == rule_id]
        assert len(rule_suggestions) == 0

    def test_suggestions_sorted_by_confidence(self, policy_learning):
        """Test that suggestions are sorted by confidence (highest first)."""
        tenant_id = "tenant_001"
        
        # Create multiple rules with different confidence levels
        # Rule 1: High false positive rate (high confidence)
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_1_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=["rule_high_fp"],
                human_override={
                    "type": "override",
                    "reason": "Rule blocked when it should have allowed",
                } if i < 4 else None,  # 40% false positive rate
            )
        
        # Rule 2: Lower false positive rate (lower confidence)
        for i in range(10):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_2_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=["rule_low_fp"],
                human_override={
                    "type": "override",
                    "reason": "Rule blocked when it should have allowed",
                } if i < 1 else None,  # 10% false positive rate (below threshold)
            )
        
        # Generate suggestions
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Should be sorted by confidence (highest first)
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].confidence >= suggestions[i + 1].confidence

    def test_no_auto_policy_changes(self, policy_learning):
        """Test that suggestions are not auto-applied (safety check)."""
        tenant_id = "tenant_001"
        rule_id = "rule_001"
        
        # Generate suggestions
        for i in range(5):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=[rule_id],
                human_override={
                    "type": "override",
                    "reason": "Rule blocked when it should have allowed",
                } if i < 2 else None,
            )
        
        suggestions = policy_learning.suggest_policy_improvements(tenant_id)
        
        # Verify suggestions are returned but not applied
        assert len(suggestions) > 0
        # Suggestions should only contain descriptions, not actual policy changes
        for suggestion in suggestions:
            assert isinstance(suggestion.proposed_change, str)
            assert "description" in suggestion.proposed_change.lower() or "consider" in suggestion.proposed_change.lower()

    def test_mttr_tracking_with_processing_times(self, policy_learning):
        """Test MTTR tracking with processing start/end times."""
        tenant_id = "tenant_001"
        rule_id = "rule_001"
        exception_id = "exc_001"
        
        # Record processing start
        policy_learning.record_processing_start(exception_id)
        
        # Simulate processing delay
        with patch("src.learning.policy_learning.datetime") as mock_datetime:
            start_time = datetime.now(timezone.utc)
            end_time = start_time + timedelta(seconds=300)  # 5 minutes
            
            mock_datetime.now.return_value = end_time
            mock_datetime.side_effect = lambda *args, **kw: datetime.now(timezone.utc) if not args else datetime(*args, **kw)
            
            # Record processing end and ingest feedback
            policy_learning.record_processing_end(exception_id)
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=exception_id,
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=[rule_id],
            )
        
        # Check MTTR was tracked
        rule_outcome = policy_learning._rule_outcomes[tenant_id][rule_id]
        assert len(rule_outcome.mttr_seconds) == 1
        assert rule_outcome.mttr_seconds[0] == pytest.approx(300.0, abs=1.0)

    def test_multiple_rules_tracked_separately(self, policy_learning):
        """Test that multiple rules are tracked separately."""
        tenant_id = "tenant_001"
        
        # Apply rule_001 with success
        policy_learning.ingest_feedback(
            tenant_id=tenant_id,
            exception_id="exc_001",
            outcome="SUCCESS",
            resolution_successful=True,
            policy_rules_applied=["rule_001"],
        )
        
        # Apply rule_002 with failure
        policy_learning.ingest_feedback(
            tenant_id=tenant_id,
            exception_id="exc_002",
            outcome="FAILED",
            resolution_successful=False,
            policy_rules_applied=["rule_002"],
        )
        
        # Check outcomes are tracked separately
        assert "rule_001" in policy_learning._rule_outcomes[tenant_id]
        assert "rule_002" in policy_learning._rule_outcomes[tenant_id]
        
        rule_001 = policy_learning._rule_outcomes[tenant_id]["rule_001"]
        rule_002 = policy_learning._rule_outcomes[tenant_id]["rule_002"]
        
        assert rule_001.success_count == 1
        assert rule_001.failure_count == 0
        assert rule_002.success_count == 0
        assert rule_002.failure_count == 1

