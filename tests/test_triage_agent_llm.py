"""
Tests for TriageAgent with LLM reasoning and explainability.

Tests Phase 3 enhancements:
- LLM-enhanced triage with structured reasoning
- Merging of rule-based, LLM, and RAG evidence
- Fallback to rule-based when LLM unavailable
- Structured reasoning in audit trail and evidence
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.triage import TriageAgent, TriageAgentError
from src.llm.fallbacks import FallbackReason
from src.llm.provider import LLMClient, LLMClientImpl, OpenAIProvider
from src.memory.rag import HybridSearchResult
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, SeverityRule
from src.models.exception_record import ExceptionRecord, Severity


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack for testing."""
    return DomainPack(
        domain_name="TestDomain",
        exception_types={
            "DataQualityFailure": ExceptionTypeDefinition(
                description="Data quality validation failure"
            ),
            "WorkflowFailure": ExceptionTypeDefinition(
                description="Workflow execution failure"
            ),
        },
        severity_rules=[
            SeverityRule(condition='exceptionType == "DataQualityFailure"', severity="HIGH"),
            SeverityRule(condition='exceptionType == "WorkflowFailure"', severity="MEDIUM"),
        ],
    )


@pytest.fixture
def sample_exception():
    """Create a sample exception for testing."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        source_system="ERP",
        timestamp=datetime.now(timezone.utc),
        raw_payload={
            "error": "Invalid data format",
            "errorCode": "DQ001",
            "exceptionType": "DataQualityFailure",  # Explicit type for classification
        },
    )


@pytest.fixture
def sample_rag_evidence():
    """Create sample RAG evidence for testing."""
    return [
        HybridSearchResult(
            exception_id="exc_prev_001",
            tenant_id="tenant_001",
            vector_score=0.92,
            keyword_score=0.85,
            combined_score=0.90,
            explanation="High similarity in error message and exception type",
            metadata={
                "exception_type": "DataQualityFailure",
                "severity": "HIGH",
                "resolution_summary": "Fixed by data validation",
            },
        ),
        HybridSearchResult(
            exception_id="exc_prev_002",
            tenant_id="tenant_001",
            vector_score=0.78,
            keyword_score=0.70,
            combined_score=0.75,
            explanation="Moderate similarity",
            metadata={
                "exception_type": "DataQualityFailure",
                "severity": "MEDIUM",
            },
        ),
    ]


class TestTriageAgentLLM:
    """Tests for TriageAgent with LLM enhancement."""

    @pytest.mark.asyncio
    async def test_llm_enhanced_triage_success(self, sample_domain_pack, sample_exception):
        """Test successful LLM-enhanced triage."""
        # Setup LLM client with mock response
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "severity_confidence": 0.90,
            "classification_confidence": 0.95,
            "root_cause_hypothesis": "Invalid data format detected in payload",
            "matched_rules": ['exceptionType == "DataQualityFailure" -> HIGH'],
            "diagnostic_summary": "Exception classified as DataQualityFailure with HIGH severity based on error code DQ001 and payload analysis.",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Analyzed error code DQ001 and payload structure",
                    "evidence_used": ["errorCode", "rawPayload"],
                    "conclusion": "Matches DataQualityFailure pattern",
                },
                {
                    "step_number": 2,
                    "description": "Evaluated severity rules",
                    "evidence_used": ['exceptionType == "DataQualityFailure" -> HIGH'],
                    "conclusion": "Severity: HIGH",
                },
            ],
            "evidence_references": [
                {
                    "source": "Domain Pack",
                    "description": "Exception type definition: DataQualityFailure",
                    "relevance_score": 0.95,
                },
                {
                    "source": "RAG",
                    "description": "Similar exception exc_prev_001 with HIGH severity",
                    "relevance_score": 0.90,
                },
            ],
            "confidence": 0.92,
            "natural_language_summary": "This exception was classified as a data quality failure with high severity based on the error code and payload analysis.",
        }
        
        # Mock memory index
        memory_index = MagicMock()
        memory_index.embedding_provider = MagicMock()
        
        agent = TriageAgent(
            domain_pack=sample_domain_pack,
            memory_index=memory_index,
            llm_client=llm_client,
        )
        
        # Mock hybrid_search and llm_or_rules
        with patch("src.agents.triage.hybrid_search", return_value=[]):
            with patch("src.agents.triage.llm_or_rules", return_value=mock_llm_response):
                decision = await agent.process(sample_exception)
        
        # Verify decision
        assert decision.decision == "Triaged DataQualityFailure HIGH"
        assert decision.confidence >= 0.9  # High confidence from LLM
        assert "ProceedToPolicy" in decision.next_step
        
        # Verify evidence includes reasoning
        evidence_text = " ".join(decision.evidence)
        assert "Summary:" in evidence_text
        assert "Reasoning steps:" in evidence_text
        assert "Evidence sources:" in evidence_text
        assert "LLM-enhanced reasoning" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rule_based(self, sample_domain_pack, sample_exception):
        """Test fallback to rule-based when LLM fails."""
        # Setup LLM client that will fail
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        # Mock memory index
        memory_index = MagicMock()
        memory_index.embedding_provider = MagicMock()
        
        agent = TriageAgent(
            domain_pack=sample_domain_pack,
            memory_index=memory_index,
            llm_client=llm_client,
        )
        
        # Mock hybrid_search and llm_or_rules to trigger fallback
        with patch("src.agents.triage.hybrid_search", return_value=[]):
            # Mock llm_or_rules to return fallback result (simulates LLM failure)
            fallback_result = {
                "predicted_exception_type": "DataQualityFailure",
                "predicted_severity": "HIGH",
                "severity_confidence": 0.75,
                "classification_confidence": 0.75,
                "matched_rules": [],
                "diagnostic_summary": "Rule-based classification",
                "reasoning_steps": [],
                "evidence_references": [],
                "confidence": 0.75,
                "natural_language_summary": "Rule-based fallback",
                "_metadata": {"llm_fallback": True},
            }
            with patch("src.agents.triage.llm_or_rules", return_value=fallback_result):
                decision = await agent.process(sample_exception)
        
        # Should still produce a valid decision (rule-based fallback)
        assert decision is not None
        assert decision.decision.startswith("Triaged")
        assert "ProceedToPolicy" in decision.next_step
        
        # Verify exception was classified
        assert sample_exception.exception_type is not None
        assert sample_exception.severity is not None

    @pytest.mark.asyncio
    async def test_build_triage_prompt(self, sample_domain_pack, sample_exception, sample_rag_evidence):
        """Test build_triage_prompt() method."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        prompt = agent.build_triage_prompt(sample_exception, sample_rag_evidence)
        
        # Verify prompt contains key elements
        assert "TriageAgent" in prompt
        assert sample_exception.exception_id in prompt
        assert sample_exception.tenant_id in prompt
        assert "DataQualityFailure" in prompt  # Exception type from domain pack
        assert "exc_prev_001" in prompt  # RAG evidence
        assert "similarity=" in prompt  # RAG scores
        assert "Instructions:" in prompt

    @pytest.mark.asyncio
    async def test_merge_triage_results_with_agreement(self, sample_domain_pack, sample_exception):
        """Test merging when LLM and rule-based agree."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        llm_result = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "confidence": 0.90,
            "reasoning_steps": [{"step_number": 1, "description": "Test"}],
            "evidence_references": [],
            "natural_language_summary": "Test summary",
        }
        
        rule_type = "DataQualityFailure"
        rule_severity = Severity.HIGH
        matched_rules = ['exceptionType == "DataQualityFailure" -> HIGH']
        
        final_type, final_severity, confidence, reasoning = agent._merge_triage_results(
            sample_exception,
            llm_result,
            rule_type,
            rule_severity,
            [],
            matched_rules,
        )
        
        # Should use LLM result with increased confidence due to agreement
        assert final_type == "DataQualityFailure"
        assert final_severity == Severity.HIGH
        assert confidence >= 0.90  # Should be increased due to agreement

    @pytest.mark.asyncio
    async def test_merge_triage_results_with_disagreement(self, sample_domain_pack, sample_exception):
        """Test merging when LLM and rule-based disagree."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        # LLM predicts different type
        llm_result = {
            "predicted_exception_type": "WorkflowFailure",
            "predicted_severity": "MEDIUM",
            "confidence": 0.85,
            "reasoning_steps": [],
            "evidence_references": [],
            "natural_language_summary": "Test",
        }
        
        rule_type = "DataQualityFailure"
        rule_severity = Severity.HIGH
        matched_rules = []
        
        final_type, final_severity, confidence, reasoning = agent._merge_triage_results(
            sample_exception,
            llm_result,
            rule_type,
            rule_severity,
            [],
            matched_rules,
        )
        
        # Should use LLM result but with decreased confidence
        assert final_type == "WorkflowFailure"
        assert final_severity == Severity.MEDIUM
        assert confidence < 0.85  # Should be decreased due to disagreement

    @pytest.mark.asyncio
    async def test_merge_triage_results_invalid_llm_type(self, sample_domain_pack, sample_exception):
        """Test merging when LLM predicts invalid exception type."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        # LLM predicts invalid type
        llm_result = {
            "predicted_exception_type": "InvalidType",
            "predicted_severity": "HIGH",
            "confidence": 0.90,
            "reasoning_steps": [],
            "evidence_references": [],
            "natural_language_summary": "Test",
        }
        
        rule_type = "DataQualityFailure"
        rule_severity = Severity.HIGH
        matched_rules = []
        
        final_type, final_severity, confidence, reasoning = agent._merge_triage_results(
            sample_exception,
            llm_result,
            rule_type,
            rule_severity,
            [],
            matched_rules,
        )
        
        # Should fallback to rule-based type
        assert final_type == "DataQualityFailure"
        assert final_severity == Severity.HIGH

    @pytest.mark.asyncio
    async def test_create_rule_based_triage_result(self, sample_domain_pack, sample_exception):
        """Test _create_rule_based_triage_result() method."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        result = agent._create_rule_based_triage_result(
            sample_exception,
            "DataQualityFailure",
            Severity.HIGH,
            ['exceptionType == "DataQualityFailure" -> HIGH'],
        )
        
        # Verify result structure matches TriageLLMOutput schema
        assert result["predicted_exception_type"] == "DataQualityFailure"
        assert result["predicted_severity"] == "HIGH"
        assert "confidence" in result
        assert "reasoning_steps" in result
        assert "evidence_references" in result
        assert "natural_language_summary" in result
        assert len(result["reasoning_steps"]) > 0

    @pytest.mark.asyncio
    async def test_create_decision_with_reasoning(self, sample_domain_pack, sample_exception, sample_rag_evidence):
        """Test _create_decision_with_reasoning() method."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        reasoning = {
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Analyzed error code",
                    "conclusion": "Matches DataQualityFailure",
                }
            ],
            "evidence_references": [
                {"source": "RAG", "description": "Similar case found"},
            ],
            "natural_language_summary": "Exception classified as DataQualityFailure",
        }
        
        context = {
            "hybrid_search_results": sample_rag_evidence,
            "llm_result": {"_metadata": {}},  # No fallback
        }
        
        decision = agent._create_decision_with_reasoning(
            sample_exception,
            "DataQualityFailure",
            Severity.HIGH,
            0.90,
            reasoning,
            context=context,
        )
        
        # Verify decision includes reasoning
        assert decision.confidence == 0.90
        evidence_text = " ".join(decision.evidence)
        assert "Summary:" in evidence_text
        assert "Reasoning steps:" in evidence_text
        assert "Evidence sources:" in evidence_text
        assert "LLM-enhanced reasoning" in evidence_text
        assert "exc_prev_001" in evidence_text  # RAG evidence

    @pytest.mark.asyncio
    async def test_triage_without_llm_client(self, sample_domain_pack, sample_exception):
        """Test TriageAgent works without LLM client (rule-based only)."""
        # Mock memory index
        memory_index = MagicMock()
        memory_index.embedding_provider = MagicMock()
        
        agent = TriageAgent(
            domain_pack=sample_domain_pack,
            memory_index=memory_index,
            llm_client=None,  # No LLM client
        )
        
        # Mock hybrid_search
        with patch("src.agents.triage.hybrid_search", return_value=[]):
            decision = await agent.process(sample_exception)
        
        # Should produce valid decision using rule-based logic
        assert decision is not None
        assert decision.decision.startswith("Triaged")
        assert sample_exception.exception_type is not None
        assert sample_exception.severity is not None

    @pytest.mark.asyncio
    async def test_triage_with_rag_evidence_in_prompt(self, sample_domain_pack, sample_exception, sample_rag_evidence):
        """Test that RAG evidence is included in prompt."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        prompt = agent.build_triage_prompt(sample_exception, sample_rag_evidence)
        
        # Verify RAG evidence is in prompt
        assert "exc_prev_001" in prompt
        assert "exc_prev_002" in prompt
        assert "similarity=" in prompt
        assert "0.90" in prompt or "0.75" in prompt  # Combined scores

    @pytest.mark.asyncio
    async def test_triage_reasoning_in_audit_trail(self, sample_domain_pack, sample_exception):
        """Test that reasoning is stored in audit trail."""
        # Setup audit logger
        audit_logger = MagicMock()
        
        # Setup LLM client
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "severity_confidence": 0.90,
            "classification_confidence": 0.95,
            "matched_rules": [],
            "diagnostic_summary": "Test diagnostic",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Test reasoning step",
                    "conclusion": "Test conclusion",
                }
            ],
            "evidence_references": [
                {"source": "RAG", "description": "Test evidence"},
            ],
            "confidence": 0.92,
            "natural_language_summary": "Test summary",
        }
        
        # Mock memory index
        memory_index = MagicMock()
        memory_index.embedding_provider = MagicMock()
        
        agent = TriageAgent(
            domain_pack=sample_domain_pack,
            audit_logger=audit_logger,
            memory_index=memory_index,
            llm_client=llm_client,
        )
        
        # Mock hybrid_search and llm_or_rules
        with patch("src.agents.triage.hybrid_search", return_value=[]):
            with patch("src.agents.triage.llm_or_rules", return_value=mock_llm_response):
                decision = await agent.process(sample_exception)
        
        # Verify audit logger was called
        assert audit_logger.log_agent_event.called
        call_args = audit_logger.log_agent_event.call_args
        assert call_args[0][0] == "TriageAgent"  # agent_name
        assert call_args[0][2] == decision  # output decision
        
        # Verify decision evidence includes reasoning
        evidence_text = " ".join(decision.evidence)
        assert "Reasoning steps:" in evidence_text
        assert "Test reasoning step" in evidence_text

    @pytest.mark.asyncio
    async def test_triage_fallback_metadata(self, sample_domain_pack, sample_exception):
        """Test that fallback metadata is properly handled."""
        # Setup LLM client that will trigger fallback
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        # Mock memory index
        memory_index = MagicMock()
        memory_index.embedding_provider = MagicMock()
        
        agent = TriageAgent(
            domain_pack=sample_domain_pack,
            memory_index=memory_index,
            llm_client=llm_client,
        )
        
        # Mock hybrid_search
        with patch("src.agents.triage.hybrid_search", return_value=[]):
            # Mock llm_or_rules to return fallback result
            fallback_result = {
                "predicted_exception_type": "DataQualityFailure",
                "predicted_severity": "HIGH",
                "severity_confidence": 0.75,
                "classification_confidence": 0.75,
                "matched_rules": [],
                "diagnostic_summary": "Rule-based classification",
                "reasoning_steps": [],
                "evidence_references": [],
                "confidence": 0.75,
                "natural_language_summary": "Rule-based fallback",
                "_metadata": {
                    "llm_fallback": True,
                    "fallback_reason": FallbackReason.CIRCUIT_OPEN.value,
                },
            }
            
            with patch("src.agents.triage.llm_or_rules", return_value=fallback_result):
                decision = await agent.process(sample_exception)
        
        # Verify decision indicates fallback was used
        evidence_text = " ".join(decision.evidence)
        assert "rule-based fallback" in evidence_text.lower() or "fallback" in evidence_text.lower()

    @pytest.mark.asyncio
    async def test_get_matched_severity_rules(self, sample_domain_pack, sample_exception):
        """Test _get_matched_severity_rules() method."""
        agent = TriageAgent(domain_pack=sample_domain_pack)
        
        # Set exception type to trigger rule matching
        sample_exception.exception_type = "DataQualityFailure"
        
        matched_rules = agent._get_matched_severity_rules(
            sample_exception, "DataQualityFailure"
        )
        
        # Should match the DataQualityFailure rule
        assert len(matched_rules) > 0
        assert any("DataQualityFailure" in rule for rule in matched_rules)
        assert any("HIGH" in rule for rule in matched_rules)

