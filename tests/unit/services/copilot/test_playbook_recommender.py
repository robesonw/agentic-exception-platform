"""
Unit tests for PlaybookRecommender service.

Tests the playbook recommendation functionality including:
- Recommendation scoring and matching logic
- Tenant isolation enforcement  
- Integration with vector similarity search
- Error handling and edge cases
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

from src.services.copilot.playbooks.playbook_recommender import (
    PlaybookRecommender,
    RecommendedPlaybook
)
from src.services.copilot.retrieval.retrieval_service import EvidenceItem


class TestRecommendedPlaybook:
    """Test the RecommendedPlaybook dataclass."""

    def test_recommended_playbook_creation(self):
        """Test creating a RecommendedPlaybook with all fields."""
        playbook = RecommendedPlaybook(
            playbook_id="PB-123",
            confidence=0.85,
            steps=[{"step": 1, "text": "First step"}],
            rationale="Matched on exception type and severity",
            matched_fields=["exception_type", "severity"]
        )
        
        assert playbook.playbook_id == "PB-123"
        assert playbook.confidence == 0.85
        assert len(playbook.steps) == 1
        assert playbook.steps[0]["step"] == 1
        assert "exception type" in playbook.rationale
        assert "exception_type" in playbook.matched_fields


@pytest.mark.asyncio
class TestPlaybookRecommender:
    """Test the PlaybookRecommender service."""

    @pytest.fixture
    def mock_playbook_repository(self):
        """Mock playbook repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_retrieval_service(self):
        """Mock retrieval service."""
        return AsyncMock()

    @pytest.fixture
    def recommender(self, mock_playbook_repository, mock_retrieval_service):
        """Create PlaybookRecommender with mocked dependencies."""
        return PlaybookRecommender(mock_playbook_repository, mock_retrieval_service)

    @pytest.fixture
    def sample_playbook(self):
        """Sample playbook with steps for testing."""
        playbook = MagicMock()
        playbook.playbook_id = 123
        playbook.name = "Payment Failed Resolution"
        playbook.conditions = {
            "exception_types": ["payment_failed", "transaction_declined"],
            "severities": ["high", "critical"],
            "domains": ["finance"],
            "tags": ["payment", "retry"]
        }
        
        # Mock steps
        step1 = MagicMock()
        step1.step_order = 1
        step1.name = "Verify account balance"
        step1.action_type = "verify"
        step1.params = {"description": "Check customer account status"}
        
        step2 = MagicMock()
        step2.step_order = 2
        step2.name = "Retry payment"
        step2.action_type = "retry"
        step2.params = {"description": "Attempt payment retry with backup gateway"}
        
        playbook.steps = [step1, step2]
        return playbook

    @pytest.fixture
    def sample_exception_context(self):
        """Sample exception context for testing."""
        return {
            "type": "payment_failed",
            "severity": "high",
            "source_system": "PaymentGateway",
            "tags": ["payment", "timeout"],
            "description": "Payment processing failed due to timeout"
        }

    async def test_recommend_playbook_successful_match(
        self, recommender, mock_playbook_repository, sample_playbook, sample_exception_context
    ):
        """Test successful playbook recommendation with high confidence."""
        mock_playbook_repository.list_playbooks.return_value = [sample_playbook]

        result = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance",
            exception_context=sample_exception_context
        )

        assert result is not None
        assert result.playbook_id == "PB-123"
        assert result.confidence >= 0.4
        assert len(result.steps) == 2
        assert result.steps[0]["step"] == 1
        assert result.steps[0]["text"] == "Verify account balance"
        assert "exception_type" in result.matched_fields
        assert "severity" in result.matched_fields
        assert "Payment Failed Resolution" in result.rationale

    async def test_recommend_playbook_no_match_below_threshold(
        self, recommender, mock_playbook_repository, sample_playbook
    ):
        """Test no recommendation when score is below threshold."""
        # Create context that doesn't match well
        poor_context = {
            "type": "database_error",  # Doesn't match playbook types
            "severity": "low",  # Doesn't match playbook severities
            "source_system": "UnknownSystem"
        }
        
        mock_playbook_repository.list_playbooks.return_value = [sample_playbook]

        result = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="infrastructure", 
            exception_context=poor_context
        )

        assert result is None

    async def test_recommend_playbook_no_playbooks_available(
        self, recommender, mock_playbook_repository, sample_exception_context
    ):
        """Test handling when no playbooks are available for tenant."""
        mock_playbook_repository.list_playbooks.return_value = []

        result = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance",
            exception_context=sample_exception_context
        )

        assert result is None

    async def test_recommend_playbook_with_similarity_boost(
        self, recommender, mock_playbook_repository, mock_retrieval_service, 
        sample_playbook, sample_exception_context
    ):
        """Test recommendation with similarity boost from vector search."""
        mock_playbook_repository.list_playbooks.return_value = [sample_playbook]
        
        # Mock similarity search returning our playbook
        evidence = EvidenceItem(
            source_type="playbook",
            source_id="123",
            source_version="v1",
            title="Payment Processing Resolution",
            snippet="Handle payment failures...",
            url=None,
            similarity_score=0.8,
            chunk_text="Payment processing failure resolution steps"
        )
        mock_retrieval_service.retrieve_evidence.return_value = [evidence]

        result = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance",
            exception_context=sample_exception_context
        )

        assert result is not None
        assert result.confidence > 0.8  # Should be boosted by similarity
        mock_retrieval_service.retrieve_evidence.assert_called_once()

    async def test_recommend_playbook_input_validation(self, recommender):
        """Test input validation for recommend_playbook method."""
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            await recommender.recommend_playbook(
                tenant_id="",
                domain="finance",
                exception_context={"type": "test"}
            )

        with pytest.raises(ValueError, match="domain cannot be empty"):
            await recommender.recommend_playbook(
                tenant_id="tenant-123",
                domain="",
                exception_context={"type": "test"}
            )

        with pytest.raises(ValueError, match="exception_context cannot be empty"):
            await recommender.recommend_playbook(
                tenant_id="tenant-123",
                domain="finance",
                exception_context={}
            )

    async def test_tenant_isolation_enforcement(
        self, recommender, mock_playbook_repository, sample_exception_context
    ):
        """Test that tenant isolation is properly enforced."""
        await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance", 
            exception_context=sample_exception_context
        )

        # Verify repository was called with correct tenant_id
        mock_playbook_repository.list_playbooks.assert_called_once_with("tenant-123")

    def test_score_playbook_match_exact_type_match(self, recommender, sample_playbook):
        """Test scoring with exact exception type match."""
        context = {
            "type": "payment_failed",
            "severity": "high"
        }
        
        score, matched_fields = recommender._score_playbook_match(
            sample_playbook, "finance", context
        )
        
        assert score >= 0.6  # Should have high score
        assert "exception_type" in matched_fields
        assert "severity" in matched_fields
        assert "domain" in matched_fields

    def test_score_playbook_match_partial_type_match(self, recommender):
        """Test scoring with partial exception type match."""
        playbook = MagicMock()
        playbook.conditions = {
            "exception_types": ["payment"],
            "severities": ["high"]
        }
        
        context = {
            "type": "payment_failed",  # Contains "payment"
            "severity": "high"
        }
        
        score, matched_fields = recommender._score_playbook_match(
            playbook, "finance", context
        )
        
        assert score > 0.4
        assert "exception_type_partial" in matched_fields

    def test_score_playbook_match_tag_matching(self, recommender):
        """Test scoring with tag matching."""
        playbook = MagicMock()
        playbook.conditions = {
            "exception_types": ["payment_failed"],
            "tags": ["payment", "retry", "timeout"]
        }
        
        context = {
            "type": "payment_failed",
            "tags": ["payment", "network"]  # One matching tag
        }
        
        score, matched_fields = recommender._score_playbook_match(
            playbook, "finance", context
        )
        
        assert score > 0.4
        assert any("tag:payment" in field for field in matched_fields)

    def test_score_playbook_match_no_conditions(self, recommender):
        """Test scoring when playbook has no conditions."""
        playbook = MagicMock()
        playbook.conditions = None
        
        context = {"type": "payment_failed"}
        
        score, matched_fields = recommender._score_playbook_match(
            playbook, "finance", context
        )
        
        assert score == 0.0
        assert matched_fields == []

    async def test_format_playbook_steps(self, recommender, sample_playbook):
        """Test formatting playbook steps for UI."""
        steps = await recommender._format_playbook_steps(sample_playbook)
        
        assert len(steps) == 2
        assert steps[0]["step"] == 1
        assert steps[0]["text"] == "Verify account balance"
        assert steps[0]["action_type"] == "verify"
        assert "Check customer account" in steps[0]["description"]
        
        assert steps[1]["step"] == 2
        assert steps[1]["text"] == "Retry payment"

    def test_generate_rationale(self, recommender, sample_playbook):
        """Test rationale generation."""
        matched_fields = ["exception_type", "severity", "tag:payment"]
        confidence = 0.85
        
        rationale = recommender._generate_rationale(
            sample_playbook, matched_fields, confidence
        )
        
        assert "Payment Failed Resolution" in rationale
        assert "85.0%" in rationale
        assert "exact exception type match" in rationale
        assert "severity level match" in rationale
        assert "tag 'payment' match" in rationale

    async def test_calculate_similarity_boost_no_retrieval_service(self, mock_playbook_repository):
        """Test similarity boost when no retrieval service is available."""
        recommender = PlaybookRecommender(mock_playbook_repository, None)
        
        boost = await recommender._calculate_similarity_boost(
            "tenant-123", "finance", {"type": "test"}, MagicMock()
        )
        
        assert boost == 0.0

    async def test_calculate_similarity_boost_with_match(
        self, recommender, mock_retrieval_service, sample_playbook
    ):
        """Test similarity boost calculation with matching evidence."""
        evidence = EvidenceItem(
            source_type="playbook",
            source_id="123",  # Matches sample_playbook.playbook_id
            source_version="v1",
            title="Test Playbook",
            snippet="Test snippet",
            url=None,
            similarity_score=0.9,
            chunk_text="Test content"
        )
        mock_retrieval_service.retrieve_evidence.return_value = [evidence]
        
        boost = await recommender._calculate_similarity_boost(
            "tenant-123", "finance", {"type": "payment_failed"}, sample_playbook
        )
        
        assert boost > 0.0
        assert boost <= 0.2  # Maximum boost

    async def test_calculate_similarity_boost_no_match(
        self, recommender, mock_retrieval_service, sample_playbook
    ):
        """Test similarity boost when no matching evidence is found."""
        evidence = EvidenceItem(
            source_type="playbook",
            source_id="999",  # Different from sample_playbook.playbook_id
            source_version="v1",
            title="Different Playbook",
            snippet="Test snippet",
            url=None,
            similarity_score=0.9,
            chunk_text="Test content"
        )
        mock_retrieval_service.retrieve_evidence.return_value = [evidence]
        
        boost = await recommender._calculate_similarity_boost(
            "tenant-123", "finance", {"type": "payment_failed"}, sample_playbook
        )
        
        assert boost == 0.0

    async def test_error_handling_repository_failure(
        self, recommender, mock_playbook_repository, sample_exception_context
    ):
        """Test error handling when repository fails."""
        mock_playbook_repository.list_playbooks.side_effect = RuntimeError("Database error")

        with pytest.raises(RuntimeError, match="Database error"):
            await recommender.recommend_playbook(
                tenant_id="tenant-123",
                domain="finance",
                exception_context=sample_exception_context
            )

    async def test_multiple_playbooks_best_match(
        self, recommender, mock_playbook_repository, sample_exception_context
    ):
        """Test selection of best matching playbook from multiple options."""
        # Create multiple playbooks with different match qualities
        good_playbook = MagicMock()
        good_playbook.playbook_id = 1
        good_playbook.name = "Good Match"
        good_playbook.conditions = {
            "exception_types": ["payment_failed"],
            "severities": ["high"],
            "domains": ["finance"]
        }
        good_playbook.steps = []
        
        poor_playbook = MagicMock()
        poor_playbook.playbook_id = 2
        poor_playbook.name = "Poor Match"
        poor_playbook.conditions = {
            "exception_types": ["database_error"],  # Different type
            "severities": ["low"]  # Different severity
        }
        poor_playbook.steps = []
        
        mock_playbook_repository.list_playbooks.return_value = [poor_playbook, good_playbook]

        result = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance",
            exception_context=sample_exception_context
        )

        assert result is not None
        assert result.playbook_id == "PB-1"  # Should select the better matching playbook
        assert "Good Match" in result.rationale

    async def test_empty_evidence_items_parameter(
        self, recommender, mock_playbook_repository, sample_playbook, sample_exception_context
    ):
        """Test handling of empty evidence_items parameter."""
        mock_playbook_repository.list_playbooks.return_value = [sample_playbook]

        result = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance",
            exception_context=sample_exception_context,
            evidence_items=[]
        )

        assert result is not None
        assert result.confidence >= 0.4