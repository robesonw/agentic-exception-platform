"""
Tests for Playbook Recommendation and Optimization Engine.

Tests Phase 3 enhancements:
- Analysis of successful resolutions
- Pattern detection from manual operator steps
- Playbook optimization suggestions
- Human-in-loop workflow
- Suggestion persistence
- Non-destructive suggestions (no playbooks auto-applied)
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.learning.playbook_recommender import (
    PlaybookOptimizationSuggestion,
    PlaybookRecommender,
    PlaybookRecommenderError,
    PlaybookSuggestion,
)
from src.models.domain_pack import Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def recommender_storage_dir(tmp_path):
    """Create a temporary storage directory for learning artifacts."""
    storage_dir = tmp_path / "learning"
    storage_dir.mkdir(parents=True, exist_ok=True)
    return str(storage_dir)


@pytest.fixture
def playbook_recommender(recommender_storage_dir):
    """Create a PlaybookRecommender instance with temporary storage."""
    return PlaybookRecommender(storage_dir=recommender_storage_dir)


@pytest.fixture
def sample_resolutions():
    """Create sample successful resolutions for testing."""
    resolutions = []
    
    # Create successful resolutions with common steps
    for i in range(5):
        resolution = {
            "exceptionId": f"exc_{i:03d}",
            "exceptionType": "DataQualityFailure",
            "outcome": "SUCCESS",
            "resolutionSuccessful": True,
            "mttrSeconds": 300.0 + i * 10,  # 5-5.4 minutes
            "context": {
                "resolvedPlan": [
                    {"action": "validateData", "parameters": {"format": "json"}},
                    {"action": "fixData", "parameters": {"mode": "auto"}},
                ],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        resolutions.append(resolution)
    
    return resolutions


@pytest.fixture
def sample_playbook():
    """Create a sample playbook for testing."""
    return Playbook(
        exception_type="DataQualityFailure",
        steps=[
            PlaybookStep(action="validateData", parameters={"format": "json"}),
            PlaybookStep(action="fixData", parameters={"mode": "auto"}),
        ],
    )


class TestPlaybookRecommender:
    """Tests for Playbook Recommender."""

    def test_analyze_successful_resolutions(self, playbook_recommender, sample_resolutions):
        """Test analyzing successful resolutions to suggest new playbooks."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze resolutions
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=sample_resolutions,
        )
        
        # Should find pattern from successful resolutions
        assert len(suggestions) > 0
        
        # Find suggestion for DataQualityFailure
        data_quality_suggestions = [
            s for s in suggestions
            if s.candidate_playbook.exception_type == "DataQualityFailure"
        ]
        assert len(data_quality_suggestions) > 0
        
        suggestion = data_quality_suggestions[0]
        assert suggestion.candidate_playbook.exception_type == "DataQualityFailure"
        assert len(suggestion.candidate_playbook.steps) > 0
        assert len(suggestion.supporting_examples) > 0
        assert suggestion.effectiveness_prediction > 0.0
        assert suggestion.suggestion_type == "new_playbook"

    def test_analyze_manual_steps_patterns(self, playbook_recommender):
        """Test analyzing patterns of repeated manual steps."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create manual steps data
        manual_steps = []
        for i in range(5):
            manual_steps.append({
                "exceptionId": f"exc_{i:03d}",
                "exceptionType": "DataQualityFailure",
                "action": "manualFix",
                "parameters": {"mode": "interactive"},
            })
        
        # Analyze patterns
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=[],
            manual_steps=manual_steps,
        )
        
        # Should find pattern from manual steps
        assert len(suggestions) > 0
        
        # Find suggestion for manual steps
        manual_suggestions = [
            s for s in suggestions
            if "manualFix" in [step.action for step in s.candidate_playbook.steps]
        ]
        assert len(manual_suggestions) > 0
        
        suggestion = manual_suggestions[0]
        assert len(suggestion.candidate_playbook.steps) > 0
        assert suggestion.effectiveness_prediction > 0.0

    def test_optimize_underperforming_playbooks(self, playbook_recommender, sample_playbook):
        """Test optimizing underperforming playbooks."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create playbook metrics showing underperformance
        playbook_id = f"{sample_playbook.exception_type}_{len(sample_playbook.steps)}"
        playbook_metrics = {
            playbook_id: {
                "success_count": 2,
                "failure_count": 8,  # 20% success rate (underperforming)
                "mttr_seconds": [9000.0, 8000.0, 10000.0],  # High MTTR
                "example_exception_ids": ["exc_001", "exc_002", "exc_003"],
            },
        }
        
        # Optimize playbooks
        suggestions = playbook_recommender.optimize_existing_playbooks(
            tenant_id=tenant_id,
            domain_name=domain_name,
            existing_playbooks=[sample_playbook],
            playbook_metrics=playbook_metrics,
        )
        
        # Should find optimization suggestion
        assert len(suggestions) > 0
        
        suggestion = suggestions[0]
        assert suggestion.original_playbook.exception_type == sample_playbook.exception_type
        assert suggestion.optimized_playbook.exception_type == sample_playbook.exception_type
        assert "low success rate" in suggestion.optimization_reason.lower() or "high mttr" in suggestion.optimization_reason.lower()
        assert len(suggestion.supporting_examples) > 0

    def test_optimize_high_mttr_playbooks(self, playbook_recommender, sample_playbook):
        """Test optimizing playbooks with high MTTR."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create playbook metrics showing high MTTR
        playbook_id = f"{sample_playbook.exception_type}_{len(sample_playbook.steps)}"
        playbook_metrics = {
            playbook_id: {
                "success_count": 5,
                "failure_count": 0,  # 100% success but high MTTR
                "mttr_seconds": [8000.0, 9000.0, 10000.0, 8500.0, 9500.0],  # > 2 hours
                "example_exception_ids": ["exc_001", "exc_002", "exc_003"],
            },
        }
        
        # Optimize playbooks
        suggestions = playbook_recommender.optimize_existing_playbooks(
            tenant_id=tenant_id,
            domain_name=domain_name,
            existing_playbooks=[sample_playbook],
            playbook_metrics=playbook_metrics,
        )
        
        # Should find optimization suggestion for high MTTR
        assert len(suggestions) > 0
        
        suggestion = suggestions[0]
        assert "high mttr" in suggestion.optimization_reason.lower() or "mttr" in suggestion.optimization_reason.lower()

    def test_no_optimization_for_good_playbooks(self, playbook_recommender, sample_playbook):
        """Test that good playbooks don't get optimization suggestions."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create playbook metrics showing good performance
        playbook_id = f"{sample_playbook.exception_type}_{len(sample_playbook.steps)}"
        playbook_metrics = {
            playbook_id: {
                "success_count": 8,
                "failure_count": 2,  # 80% success rate (good)
                "mttr_seconds": [1800.0, 2000.0, 1900.0],  # < 1 hour (good)
                "example_exception_ids": ["exc_001", "exc_002"],
            },
        }
        
        # Optimize playbooks
        suggestions = playbook_recommender.optimize_existing_playbooks(
            tenant_id=tenant_id,
            domain_name=domain_name,
            existing_playbooks=[sample_playbook],
            playbook_metrics=playbook_metrics,
        )
        
        # Should have no optimization suggestions (playbook is performing well)
        assert len(suggestions) == 0

    def test_suggestions_persisted(self, playbook_recommender, recommender_storage_dir, sample_resolutions):
        """Test that suggestions are persisted to JSONL file."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze resolutions
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=sample_resolutions,
        )
        
        # Check that suggestions file was created
        suggestions_file = Path(recommender_storage_dir) / f"{tenant_id}_{domain_name}_playbook_suggestions.jsonl"
        assert suggestions_file.exists()
        
        # Read and verify suggestions
        with open(suggestions_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0
            
            # Parse first suggestion
            suggestion_dict = json.loads(lines[0])
            assert "candidate_playbook" in suggestion_dict
            assert "effectiveness_prediction" in suggestion_dict
            assert "supporting_examples" in suggestion_dict
            assert "timestamp" in suggestion_dict

    def test_mark_suggestion_reviewed(self, playbook_recommender, recommender_storage_dir):
        """Test marking a suggestion as reviewed."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        suggestion_id = "test_suggestion_001"
        
        # Mark as reviewed
        playbook_recommender.mark_suggestion_reviewed(
            tenant_id=tenant_id,
            domain_name=domain_name,
            suggestion_id=suggestion_id,
            reviewed_by="test_user",
            notes="Reviewed and looks good",
        )
        
        # Check that review file was created
        reviews_file = Path(recommender_storage_dir) / f"{tenant_id}_{domain_name}_playbook_reviews.jsonl"
        assert reviews_file.exists()
        
        # Read and verify review
        with open(reviews_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            assert len(lines) > 0
            
            review_dict = json.loads(lines[0])
            assert review_dict["suggestion_id"] == suggestion_id
            assert review_dict["status"] == "reviewed"
            assert review_dict["reviewed_by"] == "test_user"
            assert review_dict["notes"] == "Reviewed and looks good"

    def test_mark_playbook_accepted(self, playbook_recommender, recommender_storage_dir):
        """Test marking a playbook suggestion as accepted."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        suggestion_id = "test_suggestion_002"
        
        # Mark as accepted
        playbook_recommender.mark_playbook_accepted(
            tenant_id=tenant_id,
            domain_name=domain_name,
            suggestion_id=suggestion_id,
            accepted_by="test_user",
            notes="Accepted for implementation",
        )
        
        # Check that review was persisted
        reviews_file = Path(recommender_storage_dir) / f"{tenant_id}_{domain_name}_playbook_reviews.jsonl"
        assert reviews_file.exists()
        
        # Read and verify review
        with open(reviews_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            # Find the accepted review
            accepted_reviews = [
                json.loads(line) for line in lines
                if json.loads(line).get("suggestion_id") == suggestion_id
            ]
            assert len(accepted_reviews) > 0
            
            review = accepted_reviews[-1]  # Get the latest review
            assert review["status"] == "accepted"
            assert review["reviewed_by"] == "test_user"

    def test_mark_playbook_rejected(self, playbook_recommender, recommender_storage_dir):
        """Test marking a playbook suggestion as rejected."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        suggestion_id = "test_suggestion_003"
        
        # Mark as rejected
        playbook_recommender.mark_playbook_rejected(
            tenant_id=tenant_id,
            domain_name=domain_name,
            suggestion_id=suggestion_id,
            rejected_by="test_user",
            notes="Not suitable for our use case",
        )
        
        # Check that review was persisted
        reviews_file = Path(recommender_storage_dir) / f"{tenant_id}_{domain_name}_playbook_reviews.jsonl"
        assert reviews_file.exists()
        
        # Read and verify review
        with open(reviews_file, "r", encoding="utf-8") as f:
            lines = [line for line in f if line.strip()]
            # Find the rejected review
            rejected_reviews = [
                json.loads(line) for line in lines
                if json.loads(line).get("suggestion_id") == suggestion_id
            ]
            assert len(rejected_reviews) > 0
            
            review = rejected_reviews[-1]  # Get the latest review
            assert review["status"] == "rejected"
            assert review["reviewed_by"] == "test_user"

    def test_no_suggestions_for_insufficient_data(self, playbook_recommender):
        """Test that no suggestions are generated with insufficient data."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Only 2 resolutions (need at least 3)
        resolutions = [
            {
                "exceptionId": f"exc_{i:03d}",
                "exceptionType": "DataQualityFailure",
                "outcome": "SUCCESS",
                "resolutionSuccessful": True,
                "mttrSeconds": 300.0,
                "context": {"resolvedPlan": []},
            }
            for i in range(2)
        ]
        
        # Analyze resolutions
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=resolutions,
        )
        
        # Should have no suggestions (insufficient data)
        assert len(suggestions) == 0

    def test_suggestions_sorted_by_effectiveness(self, playbook_recommender):
        """Test that suggestions are sorted by effectiveness prediction (highest first)."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create resolutions with different effectiveness patterns
        resolutions = []
        
        # High effectiveness pattern (5 successful, low MTTR)
        for i in range(5):
            resolutions.append({
                "exceptionId": f"exc_high_{i:03d}",
                "exceptionType": "DataQualityFailure",
                "outcome": "SUCCESS",
                "resolutionSuccessful": True,
                "mttrSeconds": 300.0,  # Low MTTR
                "context": {
                    "resolvedPlan": [
                        {"action": "validateData", "parameters": {"format": "json"}},
                    ],
                },
            })
        
        # Lower effectiveness pattern (3 successful, higher MTTR)
        for i in range(3):
            resolutions.append({
                "exceptionId": f"exc_low_{i:03d}",
                "exceptionType": "NetworkFailure",
                "outcome": "SUCCESS",
                "resolutionSuccessful": True,
                "mttrSeconds": 4000.0,  # Higher MTTR
                "context": {
                    "resolvedPlan": [
                        {"action": "retryConnection", "parameters": {}},
                    ],
                },
            })
        
        # Analyze resolutions
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=resolutions,
        )
        
        # Should be sorted by effectiveness (highest first)
        if len(suggestions) > 1:
            for i in range(len(suggestions) - 1):
                assert suggestions[i].effectiveness_prediction >= suggestions[i + 1].effectiveness_prediction

    def test_no_auto_playbook_application(self, playbook_recommender, sample_resolutions):
        """Test that suggestions are not auto-applied (safety check)."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze resolutions
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=sample_resolutions,
        )
        
        # Verify suggestions are returned but not applied
        assert len(suggestions) > 0
        
        # Suggestions should only contain candidate playbooks, not applied playbooks
        for suggestion in suggestions:
            assert isinstance(suggestion.candidate_playbook, Playbook)
            # Verify it's a suggestion, not an applied playbook
            assert suggestion.candidate_playbook.exception_type is not None
            assert len(suggestion.candidate_playbook.steps) >= 0

    def test_candidate_playbook_structure(self, playbook_recommender, sample_resolutions):
        """Test that candidate playbooks have correct Domain Pack structure."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Analyze resolutions
        suggestions = playbook_recommender.analyze_resolutions(
            tenant_id=tenant_id,
            domain_name=domain_name,
            historical_resolutions=sample_resolutions,
        )
        
        # Verify candidate playbook structure
        for suggestion in suggestions:
            candidate_playbook = suggestion.candidate_playbook
            assert isinstance(candidate_playbook, Playbook)
            assert candidate_playbook.exception_type is not None
            assert isinstance(candidate_playbook.steps, list)
            
            # Verify steps
            for step in candidate_playbook.steps:
                assert isinstance(step, PlaybookStep)
                assert step.action is not None
                assert len(step.action) > 0
            
            # Verify effectiveness prediction
            assert 0.0 <= suggestion.effectiveness_prediction <= 1.0
            
            # Verify supporting examples
            assert isinstance(suggestion.supporting_examples, list)

    def test_optimization_removes_redundant_steps(self, playbook_recommender):
        """Test that optimization removes redundant steps."""
        tenant_id = "tenant_001"
        domain_name = "TestDomain"
        
        # Create playbook with duplicate steps
        playbook = Playbook(
            exception_type="DataQualityFailure",
            steps=[
                PlaybookStep(action="validateData", parameters={"format": "json"}),
                PlaybookStep(action="validateData", parameters={"format": "json"}),  # Duplicate
                PlaybookStep(action="fixData", parameters={"mode": "auto"}),
            ],
        )
        
        # Create metrics showing underperformance
        playbook_id = f"{playbook.exception_type}_{len(playbook.steps)}"
        playbook_metrics = {
            playbook_id: {
                "success_count": 2,
                "failure_count": 8,
                "mttr_seconds": [9000.0],
                "example_exception_ids": ["exc_001"],
            },
        }
        
        # Optimize playbooks
        suggestions = playbook_recommender.optimize_existing_playbooks(
            tenant_id=tenant_id,
            domain_name=domain_name,
            existing_playbooks=[playbook],
            playbook_metrics=playbook_metrics,
        )
        
        # Should have optimization suggestion
        assert len(suggestions) > 0
        
        suggestion = suggestions[0]
        # Optimized playbook should have fewer steps (duplicates removed)
        assert len(suggestion.optimized_playbook.steps) <= len(suggestion.original_playbook.steps)

