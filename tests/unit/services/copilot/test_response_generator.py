"""
Unit tests for CopilotResponseGenerator service.

Tests the structured response generation with evidence-based citations,
playbook recommendations, and safety constraints according to the 
Phase 13 response contract specification.
"""

import pytest
from unittest.mock import MagicMock
from typing import Dict, Any

from src.services.copilot.response.response_generator import (
    CopilotResponseGenerator,
    CopilotCitation,
    CopilotSafety
)
from src.services.copilot.retrieval.retrieval_service import EvidenceItem
from src.services.copilot.playbooks.playbook_recommender import RecommendedPlaybook


class TestCopilotCitation:
    """Test CopilotCitation dataclass."""
    
    def test_citation_creation(self):
        """Test creation of citation with all fields."""
        citation = CopilotCitation(
            source_type="policy_doc",
            source_id="SOP-FIN-001",
            title="Financial Exception Handling",
            snippet="In case of payment failures, escalate to...",
            url="/policies/SOP-FIN-001"
        )
        
        assert citation.source_type == "policy_doc"
        assert citation.source_id == "SOP-FIN-001"
        assert citation.title == "Financial Exception Handling"
        assert citation.snippet == "In case of payment failures, escalate to..."
        assert citation.url == "/policies/SOP-FIN-001"
    
    def test_citation_without_url(self):
        """Test citation creation without URL."""
        citation = CopilotCitation(
            source_type="exception",
            source_id="EX-2024-1120",
            title="Resolved case",
            snippet="Similar payment issue resolved by..."
        )
        
        assert citation.url is None


class TestCopilotSafety:
    """Test CopilotSafety dataclass."""
    
    def test_safety_defaults(self):
        """Test default safety configuration."""
        safety = CopilotSafety()
        
        assert safety.mode == "READ_ONLY"
        assert safety.actions_allowed == []
    
    def test_safety_with_explicit_values(self):
        """Test safety with explicit configuration."""
        safety = CopilotSafety(mode="READ_ONLY", actions_allowed=[])
        
        assert safety.mode == "READ_ONLY"
        assert safety.actions_allowed == []


class TestCopilotResponseGenerator:
    """Test CopilotResponseGenerator service."""
    
    @pytest.fixture
    def generator(self):
        """Create CopilotResponseGenerator instance."""
        return CopilotResponseGenerator()
    
    @pytest.fixture
    def sample_evidence_items(self):
        """Create sample evidence items for testing."""
        return [
            EvidenceItem(
                source_type="policy_doc",
                source_id="SOP-FIN-001",
                source_version="v1.2",
                title="Financial Exception Handling",
                snippet="In case of payment failures, escalate to finance team and follow the standard resolution procedures.",
                url="/policies/SOP-FIN-001",
                similarity_score=0.92,
                chunk_text="Full policy text about handling financial exceptions..."
            ),
            EvidenceItem(
                source_type="exception",
                source_id="EX-2024-1120",
                source_version=None,
                title="Resolved Payment Failure",
                snippet="Similar payment issue resolved by contacting payment processor and updating gateway configuration.",
                url="/exceptions/EX-2024-1120",
                similarity_score=0.87,
                chunk_text="Exception details with full resolution steps..."
            )
        ]
    
    @pytest.fixture
    def sample_similar_cases(self):
        """Create sample similar cases for testing."""
        return [
            {
                "exception_id": "EX-2024-1115",
                "similarity_score": 0.89,
                "title": "Payment Gateway Timeout"
            },
            {
                "exception_id": "EX-2024-1100",
                "similarity_score": 0.82,
                "title": "Credit Card Processing Error"
            }
        ]
    
    @pytest.fixture
    def sample_playbook_reco(self):
        """Create sample playbook recommendation for testing."""
        return RecommendedPlaybook(
            playbook_id="PB-FIN-001",
            confidence=0.92,
            steps=[
                {"step": 1, "text": "Check payment processor status"},
                {"step": 2, "text": "Verify gateway configuration"},
                {"step": 3, "text": "Contact payment provider if needed"}
            ],
            rationale="High confidence match based on exception type and severity",
            matched_fields=["exception_types", "domain", "severity"]
        )
    
    def test_generate_response_with_all_inputs(self, generator, sample_evidence_items, sample_similar_cases, sample_playbook_reco):
        """Test complete response generation with all input types."""
        response = generator.generate_response(
            intent="recommend",
            user_query="How do I handle this payment failure?",
            evidence_items=sample_evidence_items,
            similar_cases=sample_similar_cases,
            playbook_reco=sample_playbook_reco
        )
        
        # Validate response structure
        assert isinstance(response, dict)
        assert "answer" in response
        assert "bullets" in response
        assert "citations" in response
        assert "recommended_playbook" in response
        assert "safety" in response
        
        # Validate answer
        assert isinstance(response["answer"], str)
        assert len(response["answer"]) > 0
        assert "PB-FIN-001" in response["answer"]
        
        # Validate bullets
        assert isinstance(response["bullets"], list)
        assert len(response["bullets"]) > 0
        
        # Validate citations (mandatory with evidence)
        assert isinstance(response["citations"], list)
        assert len(response["citations"]) == 2
        
        # Validate citation structure
        for citation in response["citations"]:
            assert "source_type" in citation
            assert "source_id" in citation
            assert "title" in citation
            assert "snippet" in citation
            assert "url" in citation
        
        # Validate playbook recommendation
        assert response["recommended_playbook"] is not None
        assert response["recommended_playbook"]["playbook_id"] == "PB-FIN-001"
        assert response["recommended_playbook"]["confidence"] == 0.92
        
        # Validate safety
        assert response["safety"]["mode"] == "READ_ONLY"
        assert response["safety"]["actions_allowed"] == []
    
    def test_generate_response_summary_intent(self, generator, sample_evidence_items, sample_similar_cases):
        """Test response generation for summary intent."""
        response = generator.generate_response(
            intent="summary",
            user_query="Summarize today's exceptions",
            evidence_items=sample_evidence_items,
            similar_cases=sample_similar_cases
        )
        
        assert "Summary:" in response["answer"]
        assert f"Found {len(sample_evidence_items)} relevant documentation" in response["answer"]
        assert f"Identified {len(sample_similar_cases)} similar historical" in response["answer"]
    
    def test_generate_response_explain_intent(self, generator, sample_evidence_items):
        """Test response generation for explain intent."""
        response = generator.generate_response(
            intent="explain",
            user_query="Why was this classified as critical?",
            evidence_items=sample_evidence_items
        )
        
        assert "explanation" in response["answer"].lower()
        assert f"{len(sample_evidence_items)} documentation sources" in response["answer"]
    
    def test_generate_response_similar_intent(self, generator, sample_similar_cases):
        """Test response generation for similar cases intent."""
        response = generator.generate_response(
            intent="similar",
            user_query="Find similar cases",
            similar_cases=sample_similar_cases
        )
        
        assert f"Found {len(sample_similar_cases)} similar cases" in response["answer"]
        # Check that the exception ID appears in one of the bullets
        bullet_text = " ".join(response["bullets"])
        assert "EX-2024-1115" in bullet_text
    
    def test_generate_response_no_evidence(self, generator):
        """Test response generation without evidence items."""
        response = generator.generate_response(
            intent="explain",
            user_query="Explain this error"
        )
        
        assert "No explanatory evidence available" in response["answer"] or "couldn't find specific evidence" in response["answer"]
        assert response["citations"] == []
        assert len(response["bullets"]) > 0  # Should have fallback bullets
    
    def test_generate_response_generic_intent(self, generator, sample_evidence_items):
        """Test response generation for unknown/generic intent."""
        response = generator.generate_response(
            intent="unknown",
            user_query="Help me understand this",
            evidence_items=sample_evidence_items
        )
        
        assert "available evidence" in response["answer"]
        assert len(response["citations"]) > 0
    
    def test_citations_generation_from_evidence(self, generator, sample_evidence_items):
        """Test citation generation from evidence items."""
        citations = generator._generate_citations(sample_evidence_items)
        
        assert len(citations) == 2
        
        # Check first citation
        assert citations[0].source_type == "policy_doc"
        assert citations[0].source_id == "SOP-FIN-001"
        assert citations[0].title == "Financial Exception Handling"
        assert "payment failures" in citations[0].snippet
        assert citations[0].url == "/policies/SOP-FIN-001"
        
        # Check second citation
        assert citations[1].source_type == "exception"
        assert citations[1].source_id == "EX-2024-1120"
    
    def test_citations_snippet_truncation(self, generator):
        """Test citation snippet truncation for long content."""
        long_evidence = EvidenceItem(
            source_type="policy_doc",
            source_id="LONG-001",
            source_version="v1.0",
            title="Very Long Policy",
            snippet="This is a very long snippet that definitely exceeds the 200 character limit and should be truncated with ellipsis to ensure the UI displays properly without overwhelming the user with too much text content. This extra text ensures we go over the limit.",
            url="/policies/LONG-001",
            similarity_score=0.95,
            chunk_text="Full text..."
        )

        citations = generator._generate_citations([long_evidence])

        assert len(citations[0].snippet) <= 204  # 200 chars + "..."
        assert citations[0].snippet.endswith("...")
    
    def test_bullet_points_generation(self, generator, sample_evidence_items, sample_similar_cases, sample_playbook_reco):
        """Test bullet points generation from various inputs."""
        bullets = generator._generate_bullet_points(
            intent="recommend",
            evidence_items=sample_evidence_items,
            similar_cases=sample_similar_cases,
            playbook_reco=sample_playbook_reco
        )
        
        assert len(bullets) > 0
        
        # Should contain evidence bullets
        evidence_bullet_found = any("Review" in bullet and "Policy Doc" in bullet for bullet in bullets)
        assert evidence_bullet_found
        
        # Should contain similar cases bullet
        similar_bullet_found = any("similar historical cases" in bullet for bullet in bullets)
        assert similar_bullet_found
        
        # Should contain playbook bullets (high confidence)
        playbook_bullet_found = any("PB-FIN-001" in bullet for bullet in bullets)
        assert playbook_bullet_found
    
    def test_bullet_points_fallback(self, generator):
        """Test bullet points fallback when no evidence available."""
        bullets = generator._generate_bullet_points(
            intent="explain",
            evidence_items=None,
            similar_cases=None,
            playbook_reco=None
        )
        
        assert len(bullets) == 3  # Should have 3 fallback bullets
        assert "Review tenant configuration" in bullets[0]
        assert "Check domain pack settings" in bullets[1]
        assert "Consider manual investigation" in bullets[2]
    
    def test_playbook_recommendation_formatting(self, generator, sample_playbook_reco):
        """Test playbook recommendation formatting."""
        formatted = generator._format_playbook_recommendation(sample_playbook_reco)
        
        assert formatted is not None
        assert formatted["playbook_id"] == "PB-FIN-001"
        assert formatted["confidence"] == 0.92
        assert len(formatted["steps"]) == 3
        assert formatted["steps"][0]["step"] == 1
        assert formatted["steps"][0]["text"] == "Check payment processor status"
    
    def test_playbook_recommendation_none(self, generator):
        """Test playbook recommendation formatting with None input."""
        formatted = generator._format_playbook_recommendation(None)
        assert formatted is None
    
    def test_fallback_response_generation(self, generator):
        """Test fallback response generation for error handling."""
        response = generator._generate_fallback_response("test query")
        
        assert "encountered an issue" in response["answer"]
        assert len(response["bullets"]) == 3
        assert response["citations"] == []
        assert response["recommended_playbook"] is None
        assert response["safety"]["mode"] == "READ_ONLY"
    
    def test_citation_to_dict_conversion(self, generator):
        """Test citation to dictionary conversion."""
        citation = CopilotCitation(
            source_type="audit_event",
            source_id="AUDIT-001",
            title="Configuration Change",
            snippet="User modified playbook settings",
            url="/audit/AUDIT-001"
        )
        
        citation_dict = generator._citation_to_dict(citation)
        
        assert citation_dict["source_type"] == "audit_event"
        assert citation_dict["source_id"] == "AUDIT-001"
        assert citation_dict["title"] == "Configuration Change"
        assert citation_dict["snippet"] == "User modified playbook settings"
        assert citation_dict["url"] == "/audit/AUDIT-001"
    
    def test_response_contract_validation(self, generator):
        """Test that response matches the contract schema."""
        response = generator.generate_response(
            intent="summary",
            user_query="Test query"
        )
        
        # Validate required fields exist
        required_fields = ["answer", "bullets", "citations", "recommended_playbook", "safety"]
        for field in required_fields:
            assert field in response
        
        # Validate field types
        assert isinstance(response["answer"], str)
        assert isinstance(response["bullets"], list)
        assert isinstance(response["citations"], list)
        assert response["recommended_playbook"] is None or isinstance(response["recommended_playbook"], dict)
        assert isinstance(response["safety"], dict)
        
        # Validate safety structure
        assert "mode" in response["safety"]
        assert "actions_allowed" in response["safety"]
        assert response["safety"]["mode"] == "READ_ONLY"
        assert isinstance(response["safety"]["actions_allowed"], list)
    
    @pytest.mark.parametrize("intent", ["summary", "explain", "similar", "recommend", "unknown"])
    def test_response_generation_all_intents(self, generator, intent):
        """Test response generation for all supported intents."""
        response = generator.generate_response(
            intent=intent,
            user_query=f"Test query for {intent}"
        )
        
        # All responses should be valid
        assert isinstance(response, dict)
        assert len(response["answer"]) > 0
        assert response["safety"]["mode"] == "READ_ONLY"
    
    def test_mandatory_citations_with_evidence(self, generator, sample_evidence_items):
        """Test that citations are mandatory when evidence items exist."""
        response = generator.generate_response(
            intent="explain",
            user_query="Explain this issue",
            evidence_items=sample_evidence_items
        )
        
        # Citations must exist when evidence is provided
        assert len(response["citations"]) > 0
        assert len(response["citations"]) == len(sample_evidence_items)
    
    def test_read_only_safety_constraint(self, generator, sample_evidence_items, sample_playbook_reco):
        """Test that safety constraints always enforce READ_ONLY mode."""
        response = generator.generate_response(
            intent="recommend",
            user_query="Fix this issue automatically",
            evidence_items=sample_evidence_items,
            playbook_reco=sample_playbook_reco
        )
        
        # Safety must always be READ_ONLY
        assert response["safety"]["mode"] == "READ_ONLY"
        assert response["safety"]["actions_allowed"] == []
        
        # Answer should contain advisory language
        assert "advisory" in response["answer"] or "review" in response["answer"].lower()