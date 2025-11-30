"""
Tests for Guardrail Adjustment Recommendation System (P3-10).
"""

import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock, MagicMock

from src.learning.guardrail_recommender import (
    GuardrailAnalysisConfig,
    GuardrailPerformanceMetrics,
    GuardrailRecommender,
    GuardrailRecommenderError,
    GuardrailRecommendation,
)
from src.models.domain_pack import DomainPack, Guardrails
from src.models.tenant_policy import TenantPolicyPack


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack with guardrails."""
    return DomainPack(
        domain_name="TestDomain",
        guardrails=Guardrails(
            allow_lists=["tool1", "tool2"],
            block_lists=["tool3"],
            human_approval_threshold=0.8,
        ),
    )


@pytest.fixture
def sample_tenant_policy():
    """Create a sample tenant policy pack."""
    return TenantPolicyPack(
        tenant_id="tenant_001",
        domain_name="TestDomain",
        custom_guardrails=None,  # Use domain pack guardrails
    )


@pytest.fixture
def guardrail_recommender(tmp_path):
    """Create guardrail recommender with temporary storage."""
    return GuardrailRecommender(storage_dir=str(tmp_path / "learning"))


class TestGuardrailPerformanceMetrics:
    """Tests for GuardrailPerformanceMetrics."""

    def test_false_positive_ratio(self):
        """Test false positive ratio calculation."""
        metrics = GuardrailPerformanceMetrics("test_guardrail")
        metrics.total_checks = 100
        metrics.false_positive_count = 75
        
        assert metrics.get_false_positive_ratio() == 0.75

    def test_false_negative_ratio(self):
        """Test false negative ratio calculation."""
        metrics = GuardrailPerformanceMetrics("test_guardrail")
        metrics.total_checks = 100
        metrics.false_negative_count = 30
        
        assert metrics.get_false_negative_ratio() == 0.3

    def test_accuracy(self):
        """Test accuracy calculation."""
        metrics = GuardrailPerformanceMetrics("test_guardrail")
        metrics.total_checks = 100
        metrics.true_positive_count = 20
        metrics.true_negative_count = 50
        metrics.false_positive_count = 20
        metrics.false_negative_count = 10
        
        assert metrics.get_accuracy() == 0.7  # (20 + 50) / 100


class TestGuardrailRecommender:
    """Tests for GuardrailRecommender."""

    def test_analyze_guardrail_performance_basic(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test basic guardrail performance analysis."""
        # Create mock historical decisions with high false positives
        historical_decisions = [
            {"decision": "BLOCK", "evidence": ["override: too strict"]},
            {"decision": "BLOCK", "evidence": ["override: too strict"]},
            {"decision": "ALLOW", "evidence": []},
        ]
        
        metrics = guardrail_recommender.analyze_guardrail_performance(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            historical_decisions=historical_decisions,
        )
        
        assert "human_approval_threshold" in metrics
        assert metrics["human_approval_threshold"].total_checks >= 2
        assert metrics["human_approval_threshold"].false_positive_count >= 2

    def test_generate_recommendations_too_strict(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test generating recommendations for overly strict guardrail."""
        # Create performance metrics with high false positives
        performance_metrics = {
            "human_approval_threshold": GuardrailPerformanceMetrics("human_approval_threshold"),
        }
        perf_metrics = performance_metrics["human_approval_threshold"]
        perf_metrics.total_checks = 100
        perf_metrics.false_positive_count = 80  # 80% false positive rate
        perf_metrics.blocked_count = 80
        perf_metrics.allowed_count = 20
        
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        assert len(recommendations) > 0
        
        # Check that recommendation suggests relaxation
        relaxation_rec = next(
            (r for r in recommendations if "relax" in r.reason.lower() or "increase" in r.reason.lower()),
            None,
        )
        assert relaxation_rec is not None
        assert relaxation_rec.guardrail_id == "human_approval_threshold"
        assert relaxation_rec.review_required is True
        assert "impactAnalysis" in relaxation_rec.model_dump(by_alias=True)
        assert relaxation_rec.confidence >= guardrail_recommender.config.MIN_CONFIDENCE_THRESHOLD

    def test_generate_recommendations_too_lenient(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test generating recommendations for overly lenient guardrail."""
        # Create performance metrics with high false negatives
        performance_metrics = {
            "human_approval_threshold": GuardrailPerformanceMetrics("human_approval_threshold"),
        }
        perf_metrics = performance_metrics["human_approval_threshold"]
        perf_metrics.total_checks = 100
        perf_metrics.false_negative_count = 35  # 35% false negative rate
        perf_metrics.blocked_count = 10
        perf_metrics.allowed_count = 90
        
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        assert len(recommendations) > 0
        
        # Check that recommendation suggests tightening
        tightening_rec = next(
            (r for r in recommendations if "tighten" in r.reason.lower() or "decrease" in r.reason.lower()),
            None,
        )
        assert tightening_rec is not None
        assert tightening_rec.guardrail_id == "human_approval_threshold"
        assert tightening_rec.review_required is True
        assert "impactAnalysis" in tightening_rec.model_dump(by_alias=True)
        assert tightening_rec.confidence >= guardrail_recommender.config.MIN_CONFIDENCE_THRESHOLD

    def test_generate_recommendations_balanced(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test that balanced performance generates no or low-confidence recommendations."""
        # Create performance metrics with balanced false positives/negatives
        performance_metrics = {
            "human_approval_threshold": GuardrailPerformanceMetrics("human_approval_threshold"),
        }
        perf_metrics = performance_metrics["human_approval_threshold"]
        perf_metrics.total_checks = 100
        perf_metrics.false_positive_count = 5  # 5% false positive rate (low)
        perf_metrics.false_negative_count = 5  # 5% false negative rate (low)
        perf_metrics.blocked_count = 50
        perf_metrics.allowed_count = 50
        
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        # Should have no recommendations (both ratios below thresholds)
        assert len(recommendations) == 0

    def test_attach_impact_analysis(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test that impact analysis is attached to recommendations."""
        # Create recommendation
        recommendation = GuardrailRecommendation(
            guardrail_id="human_approval_threshold",
            tenant_id="tenant_001",
            current_config={"human_approval_threshold": 0.8},
            proposed_change={"human_approval_threshold": 0.9},
            reason="Test recommendation",
            impact_analysis={},  # Empty initially
            review_required=True,
            confidence=0.85,
        )
        
        # Create performance metrics
        performance_metrics = {
            "human_approval_threshold": GuardrailPerformanceMetrics("human_approval_threshold"),
        }
        perf_metrics = performance_metrics["human_approval_threshold"]
        perf_metrics.total_checks = 100
        perf_metrics.false_positive_count = 75
        perf_metrics.false_negative_count = 5
        
        # Attach impact analysis
        guardrail_recommender.attach_impact_analysis(recommendation, performance_metrics)
        
        # Verify impact analysis is populated
        assert recommendation.impact_analysis is not None
        assert "estimatedFalsePositiveChange" in recommendation.impact_analysis
        assert "estimatedFalseNegativeChange" in recommendation.impact_analysis
        assert "confidence" in recommendation.impact_analysis
        assert "currentFalsePositiveRatio" in recommendation.impact_analysis
        assert "currentFalseNegativeRatio" in recommendation.impact_analysis

    def test_persist_and_load_recommendations(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test persisting and loading recommendations."""
        # Create performance metrics
        performance_metrics = {
            "human_approval_threshold": GuardrailPerformanceMetrics("human_approval_threshold"),
        }
        perf_metrics = performance_metrics["human_approval_threshold"]
        perf_metrics.total_checks = 100
        perf_metrics.false_positive_count = 80
        
        # Generate recommendations (this will persist them)
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        assert len(recommendations) > 0
        
        # Load recommendations
        loaded = guardrail_recommender.load_recommendations("tenant_001", "TestDomain")
        
        assert len(loaded) == len(recommendations)
        assert loaded[0].guardrail_id == recommendations[0].guardrail_id
        assert loaded[0].tenant_id == recommendations[0].tenant_id

    def test_insufficient_data_no_recommendations(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test that insufficient data generates no recommendations."""
        # Create performance metrics with insufficient sample size
        performance_metrics = {
            "human_approval_threshold": GuardrailPerformanceMetrics("human_approval_threshold"),
        }
        perf_metrics = performance_metrics["human_approval_threshold"]
        perf_metrics.total_checks = 5  # Below MIN_SAMPLE_SIZE (10)
        perf_metrics.false_positive_count = 4
        
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        # Should have no recommendations due to insufficient data
        assert len(recommendations) == 0

    def test_allow_list_guardrail_recommendation(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test recommendation for allow_lists guardrail."""
        # Create performance metrics for allow_lists
        performance_metrics = {
            "allow_lists": GuardrailPerformanceMetrics("allow_lists"),
        }
        perf_metrics = performance_metrics["allow_lists"]
        perf_metrics.total_checks = 100
        perf_metrics.false_positive_count = 75  # High false positives
        
        # Update domain pack with allow_lists
        sample_domain_pack.guardrails.allow_lists = ["tool1", "tool2"]
        
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        # Should generate recommendation for allow_lists
        allow_list_rec = next(
            (r for r in recommendations if r.guardrail_id == "allow_lists"),
            None,
        )
        assert allow_list_rec is not None
        assert "allow" in allow_list_rec.reason.lower() or "expand" in allow_list_rec.reason.lower()

    def test_block_list_guardrail_recommendation(
        self, guardrail_recommender, sample_domain_pack, sample_tenant_policy
    ):
        """Test recommendation for block_lists guardrail."""
        # Create performance metrics for block_lists with high false negatives
        performance_metrics = {
            "block_lists": GuardrailPerformanceMetrics("block_lists"),
        }
        perf_metrics = performance_metrics["block_lists"]
        perf_metrics.total_checks = 100
        perf_metrics.false_negative_count = 35  # High false negatives
        
        # Update domain pack with block_lists
        sample_domain_pack.guardrails.block_lists = ["tool3"]
        
        recommendations = guardrail_recommender.generate_recommendations(
            tenant_id="tenant_001",
            domain_name="TestDomain",
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            performance_metrics=performance_metrics,
        )
        
        # Should generate recommendation for block_lists
        block_list_rec = next(
            (r for r in recommendations if r.guardrail_id == "block_lists"),
            None,
        )
        assert block_list_rec is not None
        assert "block" in block_list_rec.reason.lower() or "expand" in block_list_rec.reason.lower()

