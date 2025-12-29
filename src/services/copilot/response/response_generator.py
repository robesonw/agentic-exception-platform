"""
Copilot Response Generator for Phase 13 Intelligence MVP.

This service generates structured Copilot responses with evidence-based citations,
playbook recommendations, and safety constraints. Follows the response contract
from docs/phase13-copilot-intelligence-mvp.md Section 6.

Key responsibilities:
1. Generate structured responses matching the contract schema
2. Transform evidence items into properly formatted citations
3. Include safety constraints to enforce read-only behavior
4. Format playbook recommendations for UI consumption
5. Create actionable bullet points from evidence

Phase 13 Prompt 3.5: Structured output with mandatory citations.
"""

import logging
from typing import Dict, List, Optional, Any, Literal
from dataclasses import dataclass

from src.services.copilot.retrieval.retrieval_service import EvidenceItem
from src.services.copilot.playbooks.playbook_recommender import RecommendedPlaybook

logger = logging.getLogger(__name__)


@dataclass
class CopilotCitation:
    """
    Citation structure matching the contract from phase13 docs.
    
    Attributes:
        source_type: Type of source (policy_doc, exception, audit_event, tool_registry)
        source_id: Identifier of the source document
        title: Human-readable title of the source
        snippet: Relevant excerpt from the source
        url: Deep link to the source (if available)
    """
    source_type: str
    source_id: str
    title: str
    snippet: str
    url: Optional[str] = None


@dataclass
class CopilotSafety:
    """
    Safety constraints for Copilot actions.
    
    Attributes:
        mode: Safety mode (READ_ONLY enforced by default)
        actions_allowed: List of allowed actions (empty for read-only)
    """
    mode: Literal["READ_ONLY"] = "READ_ONLY"
    actions_allowed: List[str] = None
    
    def __post_init__(self):
        if self.actions_allowed is None:
            self.actions_allowed = []


class CopilotResponseGenerator:
    """
    Service for generating structured Copilot responses.
    
    Transforms raw evidence, similarities, and recommendations into
    structured responses following the enterprise contract specification.
    """
    
    def __init__(self):
        """Initialize the response generator."""
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def generate_response(
        self,
        intent: str,
        user_query: str,
        evidence_items: Optional[List[EvidenceItem]] = None,
        similar_cases: Optional[List[Dict[str, Any]]] = None,
        playbook_reco: Optional[RecommendedPlaybook] = None
    ) -> Dict[str, Any]:
        """
        Generate structured Copilot response according to contract specification.
        
        Args:
            intent: Detected user intent (summary, explain, similar, recommend, etc.)
            user_query: Original user query text
            evidence_items: Retrieved evidence items for RAG response
            similar_cases: Similar exceptions found (optional)
            playbook_reco: Recommended playbook from PlaybookRecommender (optional)
            
        Returns:
            Dict matching the response contract with:
            - answer: Text response
            - bullets: List of actionable bullet points
            - citations: List of source citations (mandatory if evidence exists)
            - recommended_playbook: Playbook recommendation (if available)
            - safety: Safety constraints (always READ_ONLY)
        """
        try:
            self.logger.info(f"Generating response for intent: {intent}")
            
            # Generate main answer text
            answer = self._generate_answer_text(intent, user_query, evidence_items, similar_cases, playbook_reco)
            
            # Generate actionable bullet points
            bullets = self._generate_bullet_points(intent, evidence_items, similar_cases, playbook_reco)
            
            # Transform evidence items into citations (mandatory if evidence exists)
            citations = self._generate_citations(evidence_items)
            
            # Format playbook recommendation
            recommended_playbook = self._format_playbook_recommendation(playbook_reco)
            
            # Always include safety constraints
            safety = CopilotSafety()
            
            response = {
                "answer": answer,
                "bullets": bullets,
                "citations": [self._citation_to_dict(c) for c in citations],
                "recommended_playbook": recommended_playbook,
                "safety": {
                    "mode": safety.mode,
                    "actions_allowed": safety.actions_allowed
                }
            }
            
            self.logger.debug(f"Generated response with {len(citations)} citations")
            return response
            
        except Exception as e:
            self.logger.error(f"Error generating Copilot response: {e}")
            # Return safe fallback response
            return self._generate_fallback_response(user_query)
    
    def _generate_answer_text(
        self,
        intent: str,
        user_query: str,
        evidence_items: Optional[List[EvidenceItem]] = None,
        similar_cases: Optional[List[Dict[str, Any]]] = None,
        playbook_reco: Optional[RecommendedPlaybook] = None
    ) -> str:
        """
        Generate the main answer text based on intent and available evidence.
        
        Keep the response read-only and advisory in nature.
        """
        if intent == "summary":
            return self._generate_summary_answer(evidence_items, similar_cases)
        elif intent == "explain":
            return self._generate_explanation_answer(evidence_items)
        elif intent == "similar":
            return self._generate_similar_cases_answer(similar_cases)
        elif intent == "recommend":
            return self._generate_recommendation_answer(playbook_reco, evidence_items)
        else:
            # Generic response with evidence
            if evidence_items:
                return f"Based on the available evidence, here's what I found regarding '{user_query}'. Please review the citations below for detailed information."
            else:
                return f"I couldn't find specific evidence to answer '{user_query}'. Consider checking your tenant configuration or refining your query."
    
    def _generate_summary_answer(
        self,
        evidence_items: Optional[List[EvidenceItem]] = None,
        similar_cases: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Generate summary-focused answer text."""
        if not evidence_items and not similar_cases:
            return "No relevant exceptions or evidence found for summarization."
        
        summary_parts = []
        if evidence_items:
            summary_parts.append(f"Found {len(evidence_items)} relevant documentation sources.")
        if similar_cases:
            summary_parts.append(f"Identified {len(similar_cases)} similar historical cases.")
            
        return "Summary: " + " ".join(summary_parts) + " Review the citations and bullets below for actionable insights."
    
    def _generate_explanation_answer(self, evidence_items: Optional[List[EvidenceItem]] = None) -> str:
        """Generate explanation-focused answer text."""
        if not evidence_items:
            return "No explanatory evidence available. This may require manual investigation."
        
        return f"Based on {len(evidence_items)} documentation sources, this appears to be related to established policies and procedures. Review the cited evidence for detailed explanations."
    
    def _generate_similar_cases_answer(self, similar_cases: Optional[List[Dict[str, Any]]] = None) -> str:
        """Generate similar cases answer text."""
        if not similar_cases:
            return "No similar historical cases found in this tenant's data."
        
        return f"Found {len(similar_cases)} similar cases with comparable patterns. These may provide insights into resolution strategies."
    
    def _generate_recommendation_answer(
        self,
        playbook_reco: Optional[RecommendedPlaybook] = None,
        evidence_items: Optional[List[EvidenceItem]] = None
    ) -> str:
        """Generate recommendation-focused answer text."""
        if playbook_reco:
            return f"Recommended playbook '{playbook_reco.playbook_id}' with {playbook_reco.confidence:.0%} confidence. This is advisory guidance only - please review and approve before taking action."
        elif evidence_items:
            return "While no specific playbook matches, the evidence suggests reviewing your tenant's established procedures for similar scenarios."
        else:
            return "No specific recommendations available based on current evidence. Consider manual evaluation."
    
    def _generate_bullet_points(
        self,
        intent: str,
        evidence_items: Optional[List[EvidenceItem]] = None,
        similar_cases: Optional[List[Dict[str, Any]]] = None,
        playbook_reco: Optional[RecommendedPlaybook] = None
    ) -> List[str]:
        """
        Generate actionable bullet points based on available evidence.
        
        Returns list of strings for UI bullet point display.
        """
        bullets = []
        
        # Add evidence-based bullets
        if evidence_items:
            for item in evidence_items[:3]:  # Limit to top 3 for brevity
                bullet = f"Review {item.source_type.replace('_', ' ').title()}: {item.title}"
                bullets.append(bullet)
        
        # Add similar cases bullets
        if similar_cases:
            bullets.append(f"Analyze {len(similar_cases)} similar historical cases for patterns")
            if len(similar_cases) > 0:
                # Add specific case reference if available
                first_case = similar_cases[0]
                if 'exception_id' in first_case:
                    bullets.append(f"Start with case {first_case['exception_id']} (highest similarity)")
        
        # Add playbook bullets
        if playbook_reco and playbook_reco.confidence > 0.7:
            bullets.append(f"Consider following playbook {playbook_reco.playbook_id} ({playbook_reco.confidence:.0%} match)")
            # Add first few playbook steps as bullets
            for step in playbook_reco.steps[:2]:  # Limit to first 2 steps
                bullets.append(f"Step {step.get('step', '?')}: {step.get('text', 'See playbook details')}")
        
        # Fallback bullets if no evidence
        if not bullets:
            bullets.append("Review tenant configuration for applicable policies")
            bullets.append("Check domain pack settings for this exception type")
            bullets.append("Consider manual investigation if automated guidance is insufficient")
        
        return bullets
    
    def _generate_citations(self, evidence_items: Optional[List[EvidenceItem]] = None) -> List[CopilotCitation]:
        """
        Transform evidence items into properly formatted citations.
        
        Citations are mandatory when evidence_items exist per the requirements.
        """
        if not evidence_items:
            return []
        
        citations = []
        for item in evidence_items:
            # Truncate snippet if too long
            snippet = item.snippet
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            
            citation = CopilotCitation(
                source_type=item.source_type.lower(),  # Normalize to lowercase
                source_id=item.source_id,
                title=item.title,
                snippet=snippet,
                url=item.url
            )
            citations.append(citation)
        
        return citations
    
    def _citation_to_dict(self, citation: CopilotCitation) -> Dict[str, Any]:
        """Convert CopilotCitation to dict format for JSON response."""
        return {
            "source_type": citation.source_type,
            "source_id": citation.source_id,
            "title": citation.title,
            "snippet": citation.snippet,
            "url": citation.url
        }
    
    def _format_playbook_recommendation(self, playbook_reco: Optional[RecommendedPlaybook] = None) -> Optional[Dict[str, Any]]:
        """
        Format playbook recommendation for response contract.
        
        Includes citation metadata for UI clickable evidence.
        Returns None if no recommendation available.
        """
        if not playbook_reco:
            return None
        
        # Extract playbook name from playbook_id if available (e.g., "PB-123" -> lookup name)
        playbook_name = getattr(playbook_reco, 'name', None) or playbook_reco.playbook_id
        
        # Get next 3 steps for summarization
        next_steps = playbook_reco.steps[:3] if playbook_reco.steps else []
        
        return {
            "playbook_id": playbook_reco.playbook_id,
            "name": playbook_name,
            "confidence": playbook_reco.confidence,
            "rationale": playbook_reco.rationale,
            "matched_fields": playbook_reco.matched_fields,
            "steps": playbook_reco.steps,
            "next_steps": next_steps,  # First 3 steps for summary
            # Citation metadata for UI
            "citation": {
                "source_type": "playbook",
                "source_id": playbook_reco.playbook_id.replace("PB-", ""),  # Strip prefix for lookup
                "title": f"Playbook: {playbook_name}",
                "url": f"/admin/playbooks/{playbook_reco.playbook_id.replace('PB-', '')}"  # Deep link
            }
        }
    
    def _generate_fallback_response(self, user_query: str) -> Dict[str, Any]:
        """
        Generate safe fallback response when error occurs.
        
        Always returns valid response structure.
        """
        return {
            "answer": f"I encountered an issue processing your query: '{user_query}'. Please try again or contact support.",
            "bullets": [
                "Verify your query is within tenant scope",
                "Check if relevant domain packs are configured",
                "Try rephrasing your question"
            ],
            "citations": [],
            "recommended_playbook": None,
            "safety": {
                "mode": "READ_ONLY",
                "actions_allowed": []
            }
        }