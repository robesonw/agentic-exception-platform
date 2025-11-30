"""
Tests for Metrics-Driven Optimization Engine.

Tests Phase 3 enhancements:
- Signal collection from various sources
- Unified recommendation generation
- Recommendation persistence
- Integration with policy/severity/playbook recommenders
- Category, impact, and confidence fields
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.optimization.engine import (
    OptimizationEngine,
    OptimizationEngineError,
    OptimizationRecommendation,
    OptimizationSignal,
)
from src.learning.policy_learning import PolicyLearning, Suggestion
from src.learning.severity_recommender import SeverityRecommender, SeverityRuleSuggestion
from src.learning.playbook_recommender import PlaybookRecommender, PlaybookSuggestion
from src.models.domain_pack import Playbook, PlaybookStep, SeverityRule


@pytest.fixture
def optimization_storage_dir(tmp_path):
    """Create a temporary storage directory for optimization artifacts."""
    storage_dir = tmp_path / "optimization"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return str(storage_dir)


@pytest.fixture
def optimization_engine(optimization_storage_dir):
    """Create an OptimizationEngine instance with temporary storage."""
    return OptimizationEngine(storage_dir=optimization_storage_dir)


@pytest.fixture
def mock_policy_learning():
    """Create a mock PolicyLearning instance."""
    mock = MagicMock(spec=PolicyLearning)
    mock._rule_outcomes = {}
    mock.suggest_policy_improvements.return_value = []
    return mock


@pytest.fixture
def mock_severity_recommender():
    """Create a mock SeverityRecommender instance."""
    mock = MagicMock(spec=SeverityRecommender)
    mock.analyze_severity_patterns.return_value = []
    return mock


@pytest.fixture
def mock_playbook_recommender():
    """Create a mock PlaybookRecommender instance."""
    mock = MagicMock(spec=PlaybookRecommender)
    mock.analyze_resolutions.return_value = []
    return mock


class TestOptimizationEngine:
    """Tests for Optimization Engine."""

    def test_collect_policy_signals(self, optimization_engine, mock_policy_learning):
        """Test collecting optimization signals from policy learning."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock policy learning with rule outcomes
        mock_policy_learning._rule_outcomes = {
            tenant_id: {
                "rule_001": MagicMock(
                    total_count=10,
                    success_count=3,
                    failure_count=7,
                    false_positive_count=2,
                    false_negative_count=1,
                ),
                "rule_002": MagicMock(
                    total_count=10,
                    success_count=8,
                    failure_count=2,
                    false_positive_count=0,
                    false_negative_count=0,
                ),
            }
        }
        
        optimization_engine.policy_learning = mock_policy_learning
        
        # Collect signals
        signals = optimization_engine.collect_signals(tenant_id, domain)
        
        # Should find signals for rule_001 (low success rate, false positives)
        assert len(signals) > 0
        
        # Find signal for low success rate
        success_signals = [
            s for s in signals
            if s.metric_type == "success_rate" and s.entity_id == "rule_001"
        ]
        assert len(success_signals) > 0
        assert success_signals[0].current_value < 0.5
        assert success_signals[0].target_value == 0.8

    def test_collect_severity_signals(self, optimization_engine, mock_severity_recommender):
        """Test collecting optimization signals from severity recommender."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock severity recommender with suggestions
        mock_suggestion = SeverityRuleSuggestion(
            candidate_rule=SeverityRule(condition="test_condition", severity="HIGH"),
            confidence_score=0.85,
            example_exceptions=["exc_001", "exc_002"],
            pattern_description="Test pattern",
            supporting_metrics={},
        )
        mock_severity_recommender.analyze_severity_patterns.return_value = [mock_suggestion]
        
        optimization_engine.severity_recommender = mock_severity_recommender
        
        # Collect signals
        signals = optimization_engine.collect_signals(tenant_id, domain)
        
        # Should find signal for high confidence severity rule
        severity_signals = [
            s for s in signals
            if s.source == "severity_recommender" and s.metric_type == "severity_rule_confidence"
        ]
        assert len(severity_signals) > 0
        assert severity_signals[0].current_value > 0.7

    def test_collect_playbook_signals(self, optimization_engine, mock_playbook_recommender):
        """Test collecting optimization signals from playbook recommender."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock playbook recommender with suggestions
        mock_suggestion = PlaybookSuggestion(
            candidate_playbook=Playbook(
                exception_type="DataQualityFailure",
                steps=[PlaybookStep(action="validateData", parameters={})],
            ),
            effectiveness_prediction=0.85,
            supporting_examples=["exc_001", "exc_002"],
            suggestion_type="new_playbook",
            rationale="Test rationale",
            supporting_metrics={},
        )
        mock_playbook_recommender.analyze_resolutions.return_value = [mock_suggestion]
        
        optimization_engine.playbook_recommender = mock_playbook_recommender
        
        # Collect signals
        signals = optimization_engine.collect_signals(tenant_id, domain)
        
        # Should find signal for high effectiveness playbook
        playbook_signals = [
            s for s in signals
            if s.source == "playbook_recommender" and s.metric_type == "playbook_effectiveness"
        ]
        assert len(playbook_signals) > 0
        assert playbook_signals[0].current_value > 0.7

    def test_generate_policy_recommendations(self, optimization_engine, mock_policy_learning):
        """Test generating recommendations from policy learning."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock policy learning with suggestions
        mock_suggestion = Suggestion(
            rule_id="rule_001",
            detected_issue="too_strict",
            proposed_change="Consider relaxing rule 'rule_001'",
            impact_estimate="High: 80% false positive rate",
            confidence=0.85,
            metrics={"false_positive_rate": 0.8},
        )
        mock_policy_learning.suggest_policy_improvements.return_value = [mock_suggestion]
        
        optimization_engine.policy_learning = mock_policy_learning
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Should have policy recommendation
        assert len(recommendations) > 0
        
        policy_recs = [r for r in recommendations if r.category == "policy"]
        assert len(policy_recs) > 0
        
        rec = policy_recs[0]
        assert rec.tenant_id == tenant_id
        assert rec.domain == domain
        assert rec.category == "policy"
        assert rec.source == "policy_learning"
        assert rec.confidence == 0.85
        assert "rule_001" in rec.related_entities
        assert rec.description == "Consider relaxing rule 'rule_001'"

    def test_generate_severity_recommendations(self, optimization_engine, mock_severity_recommender):
        """Test generating recommendations from severity recommender."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock severity recommender with suggestions
        mock_suggestion = SeverityRuleSuggestion(
            candidate_rule=SeverityRule(condition="test_condition", severity="HIGH"),
            confidence_score=0.85,
            example_exceptions=["exc_001", "exc_002"],
            pattern_description="Test pattern description",
            supporting_metrics={"escalation_rate": 0.6},
        )
        mock_severity_recommender.analyze_severity_patterns.return_value = [mock_suggestion]
        
        optimization_engine.severity_recommender = mock_severity_recommender
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Should have severity recommendation
        severity_recs = [r for r in recommendations if r.category == "severity"]
        assert len(severity_recs) > 0
        
        rec = severity_recs[0]
        assert rec.tenant_id == tenant_id
        assert rec.domain == domain
        assert rec.category == "severity"
        assert rec.source == "severity_recommender"
        assert rec.confidence == 0.85
        assert len(rec.related_entities) > 0

    def test_generate_playbook_recommendations(self, optimization_engine, mock_playbook_recommender):
        """Test generating recommendations from playbook recommender."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock playbook recommender with suggestions
        mock_suggestion = PlaybookSuggestion(
            candidate_playbook=Playbook(
                exception_type="DataQualityFailure",
                steps=[PlaybookStep(action="validateData", parameters={})],
            ),
            effectiveness_prediction=0.85,
            supporting_examples=["exc_001", "exc_002"],
            suggestion_type="new_playbook",
            rationale="Based on 5 successful resolutions",
            supporting_metrics={"success_count": 5},
        )
        mock_playbook_recommender.analyze_resolutions.return_value = [mock_suggestion]
        
        optimization_engine.playbook_recommender = mock_playbook_recommender
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Should have playbook recommendation
        playbook_recs = [r for r in recommendations if r.category == "playbook"]
        assert len(playbook_recs) > 0
        
        rec = playbook_recs[0]
        assert rec.tenant_id == tenant_id
        assert rec.domain == domain
        assert rec.category == "playbook"
        assert rec.source == "playbook_recommender"
        assert rec.confidence == 0.85
        assert len(rec.related_entities) > 0

    def test_recommendations_sorted_by_confidence(self, optimization_engine, mock_policy_learning, mock_severity_recommender):
        """Test that recommendations are sorted by confidence (highest first)."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock policy learning with multiple suggestions
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Change 1",
                impact_estimate="High",
                confidence=0.9,
                metrics={},
            ),
            Suggestion(
                rule_id="rule_002",
                detected_issue="too_lenient",
                proposed_change="Change 2",
                impact_estimate="Medium",
                confidence=0.7,
                metrics={},
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        optimization_engine.severity_recommender = mock_severity_recommender
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Should be sorted by confidence (highest first)
        if len(recommendations) > 1:
            for i in range(len(recommendations) - 1):
                assert recommendations[i].confidence >= recommendations[i + 1].confidence

    def test_recommendations_persisted(self, optimization_engine, optimization_storage_dir, mock_policy_learning):
        """Test that recommendations are persisted to JSONL file."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock policy learning with suggestions
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Test change",
                impact_estimate="High",
                confidence=0.85,
                metrics={},
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Check that recommendations file was created
        recommendations_file = Path(optimization_storage_dir) / f"{tenant_id}_{domain}_recommendations.jsonl"
        assert recommendations_file.exists()
        
        # Read and verify recommendations
        with open(recommendations_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0
            
            # Parse first recommendation
            rec_dict = json.loads(lines[0])
            assert "id" in rec_dict
            assert "tenant_id" in rec_dict
            assert "domain" in rec_dict
            assert "category" in rec_dict
            assert "description" in rec_dict
            assert "impact_estimate" in rec_dict
            assert "confidence" in rec_dict
            assert "timestamp" in rec_dict

    def test_categories_set_correctly(self, optimization_engine, mock_policy_learning, mock_severity_recommender, mock_playbook_recommender):
        """Test that recommendation categories are set correctly."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mocks with suggestions
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Policy change",
                impact_estimate="High",
                confidence=0.85,
                metrics={},
            ),
        ]
        
        mock_severity_recommender.analyze_severity_patterns.return_value = [
            SeverityRuleSuggestion(
                candidate_rule=SeverityRule(condition="test", severity="HIGH"),
                confidence_score=0.8,
                example_exceptions=["exc_001"],
                pattern_description="Severity pattern",
                supporting_metrics={},
            ),
        ]
        
        mock_playbook_recommender.analyze_resolutions.return_value = [
            PlaybookSuggestion(
                candidate_playbook=Playbook(exception_type="Test", steps=[]),
                effectiveness_prediction=0.75,
                supporting_examples=["exc_001"],
                suggestion_type="new_playbook",
                rationale="Playbook rationale",
                supporting_metrics={},
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        optimization_engine.severity_recommender = mock_severity_recommender
        optimization_engine.playbook_recommender = mock_playbook_recommender
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Verify categories
        categories = {r.category for r in recommendations}
        assert "policy" in categories
        assert "severity" in categories
        assert "playbook" in categories

    def test_impact_and_confidence_fields_set(self, optimization_engine, mock_policy_learning):
        """Test that impact_estimate and confidence fields are set correctly."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock with suggestion
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Test change",
                impact_estimate="High: 80% false positive rate",
                confidence=0.85,
                metrics={},
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Verify impact and confidence are set
        assert len(recommendations) > 0
        rec = recommendations[0]
        assert rec.impact_estimate == "High: 80% false positive rate"
        assert rec.confidence == 0.85
        assert 0.0 <= rec.confidence <= 1.0

    def test_related_entities_set(self, optimization_engine, mock_policy_learning):
        """Test that related_entities field is set correctly."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock with suggestion
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Test change",
                impact_estimate="High",
                confidence=0.85,
                metrics={},
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Verify related_entities are set
        assert len(recommendations) > 0
        rec = recommendations[0]
        assert isinstance(rec.related_entities, list)
        assert "rule_001" in rec.related_entities

    def test_empty_recommendations_when_no_sources(self, optimization_engine):
        """Test that empty list is returned when no recommenders are set."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Generate recommendations without setting recommenders
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Should return empty list
        assert len(recommendations) == 0

    def test_combined_recommendations_from_multiple_sources(self, optimization_engine, mock_policy_learning, mock_severity_recommender, mock_playbook_recommender):
        """Test that recommendations from multiple sources are combined."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up all mocks
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Policy change",
                impact_estimate="High",
                confidence=0.85,
                metrics={},
            ),
        ]
        
        mock_severity_recommender.analyze_severity_patterns.return_value = [
            SeverityRuleSuggestion(
                candidate_rule=SeverityRule(condition="test", severity="HIGH"),
                confidence_score=0.8,
                example_exceptions=["exc_001"],
                pattern_description="Severity pattern",
                supporting_metrics={},
            ),
        ]
        
        mock_playbook_recommender.analyze_resolutions.return_value = [
            PlaybookSuggestion(
                candidate_playbook=Playbook(exception_type="Test", steps=[]),
                effectiveness_prediction=0.75,
                supporting_examples=["exc_001"],
                suggestion_type="new_playbook",
                rationale="Playbook rationale",
                supporting_metrics={},
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        optimization_engine.severity_recommender = mock_severity_recommender
        optimization_engine.playbook_recommender = mock_playbook_recommender
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Should have recommendations from all sources
        assert len(recommendations) >= 3
        
        categories = {r.category for r in recommendations}
        assert "policy" in categories
        assert "severity" in categories
        assert "playbook" in categories

    def test_metadata_preserved(self, optimization_engine, mock_policy_learning):
        """Test that metadata from source suggestions is preserved."""
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mock with suggestion containing metadata
        test_metrics = {
            "false_positive_rate": 0.8,
            "false_positive_count": 8,
            "total_count": 10,
        }
        
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Test change",
                impact_estimate="High",
                confidence=0.85,
                metrics=test_metrics,
            ),
        ]
        
        optimization_engine.policy_learning = mock_policy_learning
        
        # Generate recommendations
        recommendations = optimization_engine.generate_recommendations(tenant_id, domain)
        
        # Verify metadata is preserved
        assert len(recommendations) > 0
        rec = recommendations[0]
        assert rec.metadata == test_metrics

    def test_optimization_service_run_periodic(self, optimization_storage_dir, mock_policy_learning, mock_severity_recommender, mock_playbook_recommender):
        """Test OptimizationService.run_periodic_optimization()."""
        from src.optimization.engine import OptimizationEngine
        from src.services.optimization_service import OptimizationService
        
        tenant_id = "tenant_001"
        domain = "TestDomain"
        
        # Set up mocks
        mock_policy_learning.suggest_policy_improvements.return_value = [
            Suggestion(
                rule_id="rule_001",
                detected_issue="too_strict",
                proposed_change="Test change",
                impact_estimate="High",
                confidence=0.85,
                metrics={},
            ),
        ]
        
        # Create service with engine using test storage directory
        engine = OptimizationEngine(storage_dir=optimization_storage_dir)
        service = OptimizationService(optimization_engine=engine)
        service.run_periodic_optimization(
            tenant_id=tenant_id,
            domain=domain,
            policy_learning=mock_policy_learning,
            severity_recommender=mock_severity_recommender,
            playbook_recommender=mock_playbook_recommender,
        )
        
        # Verify recommendations were generated and persisted
        recommendations_file = Path(optimization_storage_dir) / f"{tenant_id}_{domain}_recommendations.jsonl"
        assert recommendations_file.exists()
        
        # Read recommendations
        with open(recommendations_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0

