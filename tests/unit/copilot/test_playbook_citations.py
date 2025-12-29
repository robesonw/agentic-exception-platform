"""
Tests for Copilot playbook-aware responses with citations.

Verifies:
- PlaybookIndexer correctly indexes playbook definitions
- PlaybookRecommender returns name and pack_version
- CopilotResponseGenerator includes citation metadata
- UI can render clickable playbook citations

Reference: Phase 13 Copilot Intelligence MVP - Playbook Citations
"""

import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
from datetime import datetime
from typing import List, Dict, Any

from src.services.copilot.indexing.playbook_indexer import (
    PlaybookIndexer,
    PlaybookDefinition,
)
from src.services.copilot.playbooks.playbook_recommender import (
    PlaybookRecommender,
    RecommendedPlaybook,
)
from src.services.copilot.response.response_generator import (
    CopilotResponseGenerator,
)
from src.infrastructure.db.models import (
    Playbook,
    PlaybookStep,
    CopilotDocumentSourceType,
)


class TestPlaybookDefinition:
    """Test PlaybookDefinition dataclass and serialization."""

    def test_playbook_definition_to_indexable_text(self):
        """Test that PlaybookDefinition generates searchable text."""
        playbook = PlaybookDefinition(
            playbook_id="pb-001",
            name="Payment Failure Remediation",
            description="Handle payment processing failures and retries",
            steps=[
                {"step": 1, "name": "Check gateway status", "action_type": "validate"},
                {"step": 2, "name": "Retry transaction", "action_type": "execute"},
                {"step": 3, "name": "Notify customer", "action_type": "notify"},
            ],
            conditions={"severities": ["high", "critical"]},
            domain="finance",
            pack_version="1.0.0",
            exception_types=["payment_failed", "gateway_timeout"],
            tags=["payments", "retries"],
        )

        text = playbook.to_indexable_text()

        # Verify key elements are present in searchable text
        assert "Payment Failure Remediation" in text
        assert "pb-001" in text
        assert "Handle payment processing failures" in text
        assert "finance" in text
        assert "payment_failed" in text
        assert "gateway_timeout" in text
        assert "Step 1: Check gateway status" in text
        assert "Step 2: Retry transaction" in text
        assert "Step 3: Notify customer" in text
        assert "high" in text
        assert "critical" in text

    def test_playbook_definition_to_source_document(self):
        """Test conversion to SourceDocument for indexing."""
        playbook = PlaybookDefinition(
            playbook_id="pb-002",
            name="Security Breach Response",
            description="Respond to detected security incidents",
            steps=[{"step": 1, "name": "Isolate affected systems", "action_type": "execute"}],
            domain="security",
            pack_version="2.0.0",
            exception_types=["security_breach"],
        )

        source_doc = playbook.to_source_document()

        assert source_doc.source_type == CopilotDocumentSourceType.PLAYBOOK.value
        assert source_doc.source_id == "pb-002"
        assert source_doc.title == "Security Breach Response"
        assert source_doc.domain == "security"
        assert source_doc.version == "2.0.0"
        assert "playbook_id" in source_doc.metadata
        assert "steps" in source_doc.metadata
        assert source_doc.metadata["steps_count"] == 1

    def test_playbook_definition_from_db_playbook(self):
        """Test creation from database models."""
        # Create mock Playbook model
        db_playbook = Mock(spec=Playbook)
        db_playbook.playbook_id = "pb-003"
        db_playbook.name = "DB Test Playbook"
        db_playbook.version = 3
        db_playbook.conditions = {
            "description": "Test description from conditions",
            "exception_types": ["db_error"],
            "tags": ["database"],
        }

        # Create mock PlaybookStep models
        step1 = Mock(spec=PlaybookStep)
        step1.step_order = 1
        step1.name = "Verify connection"
        step1.action_type = "validate"
        step1.params = {"timeout": 30}

        step2 = Mock(spec=PlaybookStep)
        step2.step_order = 2
        step2.name = "Restart service"
        step2.action_type = "execute"
        step2.params = {}

        steps = [step2, step1]  # Out of order to test sorting

        playbook_def = PlaybookDefinition.from_db_playbook(
            db_playbook, steps, domain="infrastructure", pack_version="1.2.3"
        )

        assert playbook_def.playbook_id == "pb-003"
        assert playbook_def.name == "DB Test Playbook"
        assert playbook_def.description == "Test description from conditions"
        assert playbook_def.domain == "infrastructure"
        assert playbook_def.pack_version == "1.2.3"
        assert playbook_def.version == 3
        assert len(playbook_def.steps) == 2
        # Steps should be sorted by step_order
        assert playbook_def.steps[0]["step"] == 1
        assert playbook_def.steps[1]["step"] == 2


class TestRecommendedPlaybook:
    """Test RecommendedPlaybook dataclass fields."""

    def test_recommended_playbook_has_name_and_version(self):
        """Verify RecommendedPlaybook includes name and pack_version for citations."""
        reco = RecommendedPlaybook(
            playbook_id="PB-123",
            name="Escalation Playbook",
            confidence=0.85,
            steps=[{"step": 1, "name": "Escalate to tier 2", "action_type": "notify"}],
            rationale="Matched on exception type and severity",
            matched_fields=["exception_type", "severity"],
            pack_version="1.0.0",
        )

        assert reco.name == "Escalation Playbook"
        assert reco.pack_version == "1.0.0"
        assert reco.playbook_id == "PB-123"
        assert reco.confidence == 0.85


class TestCopilotResponseGeneratorPlaybooks:
    """Test CopilotResponseGenerator playbook citation formatting."""

    @pytest.fixture
    def generator(self):
        """Create response generator instance."""
        return CopilotResponseGenerator()

    def test_format_playbook_recommendation_includes_citation(self, generator):
        """Test that playbook recommendation includes citation metadata."""
        reco = RecommendedPlaybook(
            playbook_id="PB-456",
            name="Data Recovery Playbook",
            confidence=0.92,
            steps=[
                {"step": 1, "name": "Assess damage", "action_type": "validate"},
                {"step": 2, "name": "Restore from backup", "action_type": "execute"},
                {"step": 3, "name": "Verify integrity", "action_type": "validate"},
                {"step": 4, "name": "Notify stakeholders", "action_type": "notify"},
            ],
            rationale="High confidence match for data corruption exceptions",
            matched_fields=["exception_type", "severity", "domain"],
            pack_version="2.1.0",
        )

        formatted = generator._format_playbook_recommendation(reco)

        assert formatted is not None
        assert formatted["playbook_id"] == "PB-456"
        assert formatted["name"] == "Data Recovery Playbook"
        assert formatted["confidence"] == 0.92

        # Verify next_steps contains first 3 steps
        assert "next_steps" in formatted
        assert len(formatted["next_steps"]) == 3
        assert formatted["next_steps"][0]["name"] == "Assess damage"
        assert formatted["next_steps"][1]["name"] == "Restore from backup"
        assert formatted["next_steps"][2]["name"] == "Verify integrity"

        # Verify citation metadata for UI
        assert "citation" in formatted
        citation = formatted["citation"]
        assert citation["source_type"] == "playbook"
        assert citation["source_id"] == "456"  # Stripped PB- prefix
        assert "Data Recovery Playbook" in citation["title"]
        assert citation["url"] == "/admin/playbooks/456"

    def test_format_playbook_recommendation_returns_none_when_no_playbook(self, generator):
        """Test that None is returned when no playbook recommendation."""
        formatted = generator._format_playbook_recommendation(None)
        assert formatted is None

    def test_generate_response_with_playbook_reco(self, generator):
        """Test full response generation includes playbook with citation."""
        reco = RecommendedPlaybook(
            playbook_id="PB-789",
            name="Incident Response",
            confidence=0.88,
            steps=[{"step": 1, "name": "Identify scope", "action_type": "validate"}],
            rationale="Matched incident type",
            matched_fields=["exception_type"],
            pack_version="1.0.0",
        )

        response = generator.generate_response(
            intent="recommend",
            user_query="What should I do for this incident?",
            playbook_reco=reco,
        )

        assert "recommended_playbook" in response
        assert response["recommended_playbook"] is not None
        assert response["recommended_playbook"]["citation"]["source_type"] == "playbook"
        assert response["safety"]["mode"] == "READ_ONLY"


class TestPlaybookIndexer:
    """Test PlaybookIndexer for indexing playbook definitions."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies."""
        doc_repo = MagicMock()
        doc_repo.get_by_source = AsyncMock(return_value=None)
        doc_repo.delete_by_source = AsyncMock()
        doc_repo.upsert_chunks_batch = AsyncMock(return_value=1)

        embedding_service = MagicMock()
        # Create mock EmbeddingResult
        mock_embedding_result = MagicMock()
        mock_embedding_result.embedding = [0.1] * 768
        mock_embedding_result.model = "test-model"
        mock_embedding_result.dimension = 768
        # Return a list of EmbeddingResult objects
        embedding_service.generate_embeddings_batch = AsyncMock(return_value=[mock_embedding_result])

        return {
            "document_repository": doc_repo,
            "embedding_service": embedding_service,
        }

    @pytest.fixture
    def indexer(self, mock_dependencies):
        """Create PlaybookIndexer with mocked dependencies."""
        return PlaybookIndexer(
            document_repository=mock_dependencies["document_repository"],
            embedding_service=mock_dependencies["embedding_service"],
        )

    def test_indexer_source_type_is_playbook(self, indexer):
        """Verify indexer source type is correctly set."""
        assert indexer.source_type == CopilotDocumentSourceType.PLAYBOOK

    def test_indexer_supports_valid_tenant(self, indexer):
        """Test tenant validation."""
        assert indexer.supports_tenant("tenant-001") is True
        assert indexer.supports_tenant("TENANT_FINANCE_001") is True

    @pytest.mark.asyncio
    async def test_index_single_playbook(self, indexer, mock_dependencies):
        """Test indexing a single playbook definition."""
        playbook = PlaybookDefinition(
            playbook_id="pb-test-001",
            name="Test Playbook",
            description="A test playbook for unit testing",
            steps=[{"step": 1, "name": "Test step", "action_type": "validate"}],
            domain="test",
            exception_types=["test_error"],
        )

        result = await indexer.index_playbooks(
            tenant_id="tenant-test",
            playbooks=[playbook],
            domain="test",
            pack_version="1.0.0",
        )

        assert result.tenant_id == "tenant-test"
        assert result.chunks_indexed > 0

        # Verify embedding was generated
        mock_dependencies["embedding_service"].generate_embeddings_batch.assert_called()

    @pytest.mark.asyncio
    async def test_index_playbooks_empty_list(self, indexer):
        """Test indexing with empty playbook list."""
        result = await indexer.index_playbooks(
            tenant_id="tenant-test",
            playbooks=[],
            domain="test",
        )

        assert result.chunks_indexed == 0
        assert result.chunks_skipped == 0

    @pytest.mark.asyncio
    async def test_index_from_db_converts_models(self, indexer, mock_dependencies):
        """Test indexing from database models."""
        # Create mock DB playbook
        db_playbook = Mock(spec=Playbook)
        db_playbook.playbook_id = "pb-db-001"
        db_playbook.name = "DB Playbook"
        db_playbook.version = 1
        db_playbook.conditions = {"exception_types": ["db_error"]}

        step = Mock(spec=PlaybookStep)
        step.step_order = 1
        step.name = "DB Step"
        step.action_type = "execute"
        step.params = {}

        result = await indexer.index_from_db(
            tenant_id="tenant-db",
            playbooks=[(db_playbook, [step])],
            domain="database",
            pack_version="1.0.0",
        )

        assert result.tenant_id == "tenant-db"
