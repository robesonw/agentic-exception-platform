"""
Tests for Severity Rule Recommendation Engine.

Tests Phase 3 enhancements:
- Pattern analysis from historical exceptions
- Severity rule suggestions with confidence scores
- Integration with Policy Learning
- Suggestion persistence
- Non-destructive suggestions (no rules auto-applied)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.learning.severity_recommender import (
    SeverityRecommender,
    SeverityRecommenderError,
    SeverityRuleSuggestion,
)
from src.models.domain_pack import SeverityRule
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def recommender_storage_dir(tmp_path):
    """Create a temporary storage directory for learning artifacts."""
    storage_dir = tmp_path / "learning"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return str(storage_dir)


@pytest.fixture
def severity_recommender(recommender_storage_dir):
    """Create a SeverityRecommender instance with temporary storage."""
    return SeverityRecommender(storage_dir=recommender_storage_dir)


@pytest.fixture
def sample_exceptions():
    """Create sample exceptions for testing."""
    exceptions = []
    
    # Create exceptions with a clear pattern: errorCode="E500" correlates with escalation
    for i in range(10):
        exception = ExceptionRecord(
            exception_id=f"exc_{i:03d}",
            tenant_id="tenant_001",
            source_system="ERP",
            timestamp=datetime.now(timezone.utc),
            exception_type="DataQualityFailure",
            severity=Severity.HIGH if i < 5 else Severity.MEDIUM,
            raw_payload={"errorCode": "E500" if i < 6 else "E200", "message": f"Error {i}"},
            normalized_context={},
            resolution_status=ResolutionStatus.ESCALATED if i < 6 else ResolutionStatus.RESOLVED,
        )
        exceptions.append(exception)
    
    return exceptions


class TestSeverityRecommender:
    """Tests for Severity Recommender."""

    def test_analyze_escalation_patterns(self, severity_recommender, sample_exceptions):
        """Test analyzing escalation patterns from historical exceptions."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=sample_exceptions,
        )
        
        # Should find pattern: errorCode="E500" correlates with escalation
        assert len(suggestions) > 0
        
        # Find suggestion for E500 pattern
        e500_suggestions = [
            s for s in suggestions
            if "E500" in s.pattern_description or "E500" in s.candidate_rule.condition
        ]
        assert len(e500_suggestions) > 0
        
        suggestion = e500_suggestions[0]
        assert suggestion.candidate_rule.severity in ("HIGH", "CRITICAL")
        assert "E500" in suggestion.candidate_rule.condition
        assert len(suggestion.example_exceptions) > 0
        assert suggestion.confidence_score > 0.5

    def test_analyze_severity_upgrade_patterns(self, severity_recommender):
        """Test analyzing patterns where severity should be upgraded."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create exceptions with human overrides upgrading severity
        exceptions = []
        human_overrides = []
        
        for i in range(5):
            exception = ExceptionRecord(
                exception_id=f"exc_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.MEDIUM,  # Original severity
                raw_payload={"errorCode": "E300"},
                normalized_context={},
            )
            exceptions.append(exception)
            
            # Human override upgrading to HIGH
            human_overrides.append({
                "type": "severity_change",
                "exceptionId": exception.exception_id,
                "oldSeverity": "MEDIUM",
                "newSeverity": "HIGH",
                "reason": "Should be HIGH due to impact",
            })
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=exceptions,
            human_overrides=human_overrides,
        )
        
        # Should find pattern suggesting HIGH severity
        upgrade_suggestions = [
            s for s in suggestions
            if s.candidate_rule.severity == "HIGH" and "DataQualityFailure" in s.candidate_rule.condition
        ]
        assert len(upgrade_suggestions) > 0
        
        suggestion = upgrade_suggestions[0]
        assert suggestion.candidate_rule.severity == "HIGH"
        assert len(suggestion.example_exceptions) > 0
        assert "upgraded" in suggestion.pattern_description.lower() or "manually set" in suggestion.pattern_description.lower()

    def test_analyze_critical_patterns(self, severity_recommender):
        """Test analyzing patterns in CRITICAL severity exceptions."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create exceptions with CRITICAL severity and a pattern in normalized_context
        exceptions = []
        
        for i in range(8):
            exception = ExceptionRecord(
                exception_id=f"exc_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.CRITICAL if i < 5 else Severity.HIGH,
                raw_payload={"errorCode": "E100"},
                normalized_context={
                    "impact": "financial" if i < 5 else "operational",  # Pattern: financial -> CRITICAL
                },
            )
            exceptions.append(exception)
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=exceptions,
        )
        
        # Should find pattern: impact="financial" correlates with CRITICAL
        critical_suggestions = [
            s for s in suggestions
            if s.candidate_rule.severity == "CRITICAL" and "financial" in s.pattern_description.lower()
        ]
        assert len(critical_suggestions) > 0
        
        suggestion = critical_suggestions[0]
        assert suggestion.candidate_rule.severity == "CRITICAL"
        assert "financial" in suggestion.candidate_rule.condition.lower() or "financial" in suggestion.pattern_description.lower()
        assert len(suggestion.example_exceptions) > 0

    def test_analyze_override_patterns(self, severity_recommender):
        """Test analyzing patterns in human severity overrides."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create exceptions with human overrides
        exceptions = []
        human_overrides = []
        
        for i in range(5):
            exception = ExceptionRecord(
                exception_id=f"exc_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.MEDIUM,
                raw_payload={"errorCode": "E400"},
                normalized_context={},
            )
            exceptions.append(exception)
            
            # Human override changing severity
            human_overrides.append({
                "type": "severity_change",
                "exceptionId": exception.exception_id,
                "oldSeverity": "MEDIUM",
                "newSeverity": "HIGH",
                "reason": "Manual adjustment",
            })
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=exceptions,
            human_overrides=human_overrides,
        )
        
        # Should find pattern from overrides
        override_suggestions = [
            s for s in suggestions
            if "manually set" in s.pattern_description.lower() or "override" in s.pattern_description.lower()
        ]
        assert len(override_suggestions) > 0
        
        suggestion = override_suggestions[0]
        assert suggestion.candidate_rule.severity == "HIGH"
        assert len(suggestion.example_exceptions) > 0

    def test_suggestions_persisted(self, severity_recommender, recommender_storage_dir, sample_exceptions):
        """Test that suggestions are persisted to JSONL file."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=sample_exceptions,
        )
        
        # Check that suggestions file was created
        suggestions_file = Path(recommender_storage_dir) / f"{tenant_id}_{domain_name}_severity_suggestions.jsonl"
        assert suggestions_file.exists()
        
        # Read and verify suggestions
        with open(suggestions_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0
            
            # Parse first suggestion
            suggestion_dict = json.loads(lines[0])
            assert "candidate_rule" in suggestion_dict
            assert "confidence_score" in suggestion_dict
            assert "example_exceptions" in suggestion_dict
            assert "timestamp" in suggestion_dict

    def test_no_suggestions_for_insufficient_data(self, severity_recommender):
        """Test that no suggestions are generated with insufficient data."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Only 2 exceptions (need at least 3 for patterns)
        exceptions = [
            ExceptionRecord(
                exception_id=f"exc_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.HIGH,
                raw_payload={"errorCode": "E500"},
                normalized_context={},
            )
            for i in range(2)
        ]
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=exceptions,
        )
        
        # Should have no suggestions (insufficient data)
        assert len(suggestions) == 0

    def test_suggestions_sorted_by_confidence(self, severity_recommender):
        """Test that suggestions are sorted by confidence (highest first)."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create exceptions with multiple patterns
        exceptions = []
        
        # Pattern 1: E500 with high escalation rate (high confidence)
        for i in range(8):
            exception = ExceptionRecord(
                exception_id=f"exc_1_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.HIGH,
                raw_payload={"errorCode": "E500"},
                normalized_context={},
                resolution_status=ResolutionStatus.ESCALATED if i < 6 else ResolutionStatus.RESOLVED,
            )
            exceptions.append(exception)
        
        # Pattern 2: E300 with lower escalation rate (lower confidence)
        for i in range(5):
            exception = ExceptionRecord(
                exception_id=f"exc_2_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.MEDIUM,
                raw_payload={"errorCode": "E300"},
                normalized_context={},
                resolution_status=ResolutionStatus.ESCALATED if i < 2 else ResolutionStatus.RESOLVED,
            )
            exceptions.append(exception)
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=exceptions,
        )
        
        # Should be sorted by confidence (highest first)
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].confidence_score >= suggestions[i + 1].confidence_score

    def test_no_auto_rule_application(self, severity_recommender, sample_exceptions):
        """Test that suggestions are not auto-applied (safety check)."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=sample_exceptions,
        )
        
        # Verify suggestions are returned but not applied
        assert len(suggestions) > 0
        
        # Suggestions should only contain candidate rules, not applied rules
        for suggestion in suggestions:
            assert isinstance(suggestion.candidate_rule, SeverityRule)
            # Verify it's a suggestion, not an applied rule
            assert suggestion.candidate_rule.condition is not None
            assert suggestion.candidate_rule.severity is not None

    def test_candidate_rule_structure(self, severity_recommender, sample_exceptions):
        """Test that candidate rules have correct Domain Pack structure."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=sample_exceptions,
        )
        
        # Verify candidate rule structure
        for suggestion in suggestions:
            candidate_rule = suggestion.candidate_rule
            assert isinstance(candidate_rule, SeverityRule)
            assert candidate_rule.condition is not None
            assert len(candidate_rule.condition) > 0
            assert candidate_rule.severity in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
            
            # Verify example exceptions
            assert isinstance(suggestion.example_exceptions, list)
            assert len(suggestion.example_exceptions) > 0
            
            # Verify confidence score
            assert 0.0 <= suggestion.confidence_score <= 1.0

    def test_multiple_pattern_types_detected(self, severity_recommender):
        """Test that multiple pattern types can be detected simultaneously."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create exceptions with multiple patterns
        exceptions = []
        human_overrides = []
        
        # Pattern 1: Escalation pattern (E500)
        for i in range(6):
            exception = ExceptionRecord(
                exception_id=f"exc_1_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.HIGH,
                raw_payload={"errorCode": "E500"},
                normalized_context={},
                resolution_status=ResolutionStatus.ESCALATED if i < 4 else ResolutionStatus.RESOLVED,
            )
            exceptions.append(exception)
        
        # Pattern 2: Severity upgrade pattern
        for i in range(5):
            exception = ExceptionRecord(
                exception_id=f"exc_2_{i:03d}",
                tenant_id=tenant_id,
                source_system="ERP",
                timestamp=datetime.now(timezone.utc),
                exception_type="DataQualityFailure",
                severity=Severity.MEDIUM,
                raw_payload={"errorCode": "E300"},
                normalized_context={},
            )
            exceptions.append(exception)
            
            human_overrides.append({
                "type": "severity_change",
                "exceptionId": exception.exception_id,
                "oldSeverity": "MEDIUM",
                "newSeverity": "HIGH",
                "reason": "Should be HIGH",
            })
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=exceptions,
            human_overrides=human_overrides,
        )
        
        # Should detect multiple patterns
        assert len(suggestions) >= 2
        
        # Should have escalation pattern
        escalation_suggestions = [
            s for s in suggestions if "E500" in s.candidate_rule.condition
        ]
        assert len(escalation_suggestions) > 0
        
        # Should have upgrade pattern
        upgrade_suggestions = [
            s for s in suggestions
            if "upgraded" in s.pattern_description.lower() or "manually set" in s.pattern_description.lower()
        ]
        assert len(upgrade_suggestions) > 0

    def test_empty_input_handling(self, severity_recommender):
        """Test handling of empty input data."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze with no exceptions
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=[],
        )
        
        # Should return empty list
        assert len(suggestions) == 0

    def test_supporting_metrics_included(self, severity_recommender, sample_exceptions):
        """Test that supporting metrics are included in suggestions."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze patterns
        suggestions = severity_recommender.analyze_severity_patterns(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_exceptions=sample_exceptions,
        )
        
        # Verify supporting metrics are included
        for suggestion in suggestions:
            assert isinstance(suggestion.supporting_metrics, dict)
            assert len(suggestion.supporting_metrics) > 0

    def test_integration_with_policy_learning(self, recommender_storage_dir, sample_exceptions):
        """Test integration with Policy Learning for combined suggestions."""
        from src.learning.policy_learning import PolicyLearning
        
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create severity recommender
        severity_recommender = SeverityRecommender(storage_dir=recommender_storage_dir)
        
        # Create policy learning with severity recommender
        policy_learning = PolicyLearning(
            storage_dir=recommender_storage_dir,
            severity_recommender=severity_recommender,
        )
        
        # Add some policy rule outcomes to generate policy suggestions
        for i in range(5):
            policy_learning.ingest_feedback(
                tenant_id=tenant_id,
                exception_id=f"exc_{i:03d}",
                outcome="SUCCESS",
                resolution_successful=True,
                policy_rules_applied=["rule_001"],
                human_override={
                    "type": "override",
                    "reason": "Rule blocked when it should have allowed",
                } if i < 2 else None,
            )
        
        # Get combined suggestions
        combined = policy_learning.get_combined_suggestions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            include_severity_rules=True,
        )
        
        # Verify combined structure
        assert combined["tenant_id"] == tenant_id
        assert combined["domain_name"] == domain_name
        assert "policy_suggestions" in combined
        assert "severity_rule_suggestions" in combined
        assert "timestamp" in combined
        
        # Should have policy suggestions
        assert isinstance(combined["policy_suggestions"], list)
        
        # Should have severity rule suggestions (if patterns found)
        assert isinstance(combined["severity_rule_suggestions"], list)

