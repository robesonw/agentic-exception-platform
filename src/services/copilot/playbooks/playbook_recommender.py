"""
Playbook Recommender for Phase 13 Copilot Intelligence MVP.

This service recommends playbooks for exception resolution based on:
1. Playbook metadata from active tenant packs (playbook registry)
2. Scoring based on exception type, severity, tags, and domain
3. Optional similarity to playbook descriptions in copilot_documents

Phase 13 Prompt 3.4: Cross-reference playbook recommendations with tenant config.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.services.copilot.retrieval.retrieval_service import RetrievalService
from src.infrastructure.db.models import Playbook, PlaybookStep

logger = logging.getLogger(__name__)


@dataclass
class RecommendedPlaybook:
    """
    Data structure for recommended playbook response.
    
    Matches the schema from docs/phase13-copilot-intelligence-mvp.md.
    """
    playbook_id: str
    name: str  # Human-readable playbook name
    confidence: float  # 0.0 to 1.0
    steps: List[Dict[str, Any]]  # Read-only steps for UI
    rationale: str  # Human-readable explanation
    matched_fields: List[str]  # List of fields that matched
    pack_version: Optional[str] = None  # Version of source pack for citation


class PlaybookRecommender:
    """
    Service for recommending playbooks based on exception context.
    
    Provides config-driven playbook matching without domain-specific logic.
    All matching rules come from playbook conditions and tenant configuration.
    
    Usage:
        recommender = PlaybookRecommender(playbook_repo, retrieval_service)
        recommendation = await recommender.recommend_playbook(
            tenant_id="tenant-123",
            domain="finance", 
            exception_context={"type": "payment_failed", "severity": "high"},
            evidence_items=[]
        )
    """

    def __init__(
        self,
        playbook_repository: PlaybookRepository,
        retrieval_service: Optional[RetrievalService] = None
    ):
        """
        Initialize the PlaybookRecommender.
        
        Args:
            playbook_repository: Repository for accessing playbook data
            retrieval_service: Optional service for similarity search against playbook descriptions
        """
        self.playbook_repository = playbook_repository
        self.retrieval_service = retrieval_service

    async def recommend_playbook(
        self,
        tenant_id: str,
        domain: str,
        exception_context: Dict[str, Any],
        evidence_items: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[RecommendedPlaybook]:
        """
        Recommend a playbook for exception resolution.
        
        Args:
            tenant_id: Tenant identifier for isolation
            domain: Domain context (finance, healthcare, etc.)
            exception_context: Exception data for matching (type, severity, tags, etc.)
            evidence_items: Optional evidence from previous analysis
            
        Returns:
            RecommendedPlaybook if a suitable match is found, None otherwise
            
        Raises:
            ValueError: If required parameters are missing or invalid
        """
        # Input validation
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
            
        if not domain or not domain.strip():
            raise ValueError("domain cannot be empty")
            
        if not exception_context:
            raise ValueError("exception_context cannot be empty")

        logger.info(
            f"Recommending playbook for tenant {tenant_id}, domain {domain}, "
            f"context: {exception_context.get('type', 'unknown')}"
        )

        try:
            # Get all active playbooks for the tenant
            playbooks = await self.playbook_repository.list_playbooks(tenant_id)
            
            if not playbooks:
                logger.info(f"No playbooks found for tenant {tenant_id}")
                return None

            # Score each playbook and find the best match
            best_playbook = None
            best_score = 0.0
            best_matched_fields = []
            
            for playbook in playbooks:
                score, matched_fields = self._score_playbook_match(
                    playbook, domain, exception_context
                )
                
                if score > best_score:
                    best_score = score
                    best_playbook = playbook
                    best_matched_fields = matched_fields

            # Use similarity search to boost confidence if available
            if self.retrieval_service and best_playbook and best_score > 0.3:
                similarity_boost = await self._calculate_similarity_boost(
                    tenant_id, domain, exception_context, best_playbook
                )
                best_score = min(1.0, best_score + similarity_boost)

            # Return recommendation if score is above threshold
            if best_playbook and best_score >= 0.4:  # Minimum confidence threshold
                steps = await self._format_playbook_steps(best_playbook)
                rationale = self._generate_rationale(
                    best_playbook, best_matched_fields, best_score
                )
                
                logger.info(
                    f"Recommended playbook {best_playbook.playbook_id} "
                    f"with confidence {best_score:.2f}"
                )
                
                return RecommendedPlaybook(
                    playbook_id=f"PB-{best_playbook.playbook_id}",
                    name=best_playbook.name,
                    confidence=best_score,
                    steps=steps,
                    rationale=rationale,
                    matched_fields=best_matched_fields,
                    pack_version=str(best_playbook.version) if best_playbook.version else None
                )
                
            logger.info(f"No suitable playbook found (best score: {best_score:.2f})")
            return None

        except Exception as e:
            logger.error(f"Error recommending playbook for {tenant_id}: {str(e)}")
            raise

    def _score_playbook_match(
        self, 
        playbook: Playbook, 
        domain: str, 
        exception_context: Dict[str, Any]
    ) -> tuple[float, List[str]]:
        """
        Score how well a playbook matches the exception context.
        
        Args:
            playbook: Playbook to evaluate
            domain: Domain context 
            exception_context: Exception data for matching
            
        Returns:
            Tuple of (score, matched_fields) where score is 0.0-1.0
        """
        score = 0.0
        matched_fields = []
        
        # Parse playbook conditions (JSON format)
        conditions = playbook.conditions or {}
        
        # Match exception type (highest weight)
        playbook_types = conditions.get('exception_types', [])
        exception_type = exception_context.get('type', '')
        
        if exception_type and playbook_types:
            if exception_type in playbook_types:
                score += 0.4
                matched_fields.append('exception_type')
            elif any(ptype in exception_type for ptype in playbook_types):
                score += 0.2
                matched_fields.append('exception_type_partial')
        
        # Match severity (medium weight)
        playbook_severities = conditions.get('severities', [])
        exception_severity = exception_context.get('severity', '')
        
        if exception_severity and playbook_severities:
            if exception_severity in playbook_severities:
                score += 0.25
                matched_fields.append('severity')
        
        # Match domain (medium weight)
        playbook_domains = conditions.get('domains', [])
        
        if domain and playbook_domains:
            if domain in playbook_domains:
                score += 0.2
                matched_fields.append('domain')
        
        # Match tags (lower weight, additive)
        playbook_tags = conditions.get('tags', [])
        exception_tags = exception_context.get('tags', [])
        
        if playbook_tags and exception_tags:
            matching_tags = set(playbook_tags) & set(exception_tags)
            if matching_tags:
                tag_score = min(0.15, len(matching_tags) * 0.05)
                score += tag_score
                matched_fields.extend([f'tag:{tag}' for tag in matching_tags])
        
        # Match source system (lower weight)
        playbook_systems = conditions.get('source_systems', [])
        exception_system = exception_context.get('source_system', '')
        
        if exception_system and playbook_systems:
            if exception_system in playbook_systems:
                score += 0.1
                matched_fields.append('source_system')
        
        return min(1.0, score), matched_fields

    async def _calculate_similarity_boost(
        self,
        tenant_id: str,
        domain: str, 
        exception_context: Dict[str, Any],
        playbook: Playbook
    ) -> float:
        """
        Calculate similarity boost using vector search against playbook descriptions.
        
        Args:
            tenant_id: Tenant identifier
            domain: Domain context
            exception_context: Exception data
            playbook: Playbook to check similarity for
            
        Returns:
            Similarity boost value (0.0-0.2)
        """
        if not self.retrieval_service:
            return 0.0
            
        try:
            # Build query from exception context
            query_parts = []
            if exception_context.get('type'):
                query_parts.append(f"Exception type: {exception_context['type']}")
            if exception_context.get('severity'):
                query_parts.append(f"Severity: {exception_context['severity']}")
            if exception_context.get('description'):
                query_parts.append(exception_context['description'])
                
            query_text = " ".join(query_parts)
            
            # Search for similar playbook documents
            evidence_items = await self.retrieval_service.retrieve_evidence(
                tenant_id=tenant_id,
                query_text=query_text,
                domain=domain,
                source_types=["playbook"],  # Only playbook descriptions
                top_k=5
            )
            
            # Check if our playbook appears in similar results
            playbook_id_str = str(playbook.playbook_id)
            
            for evidence in evidence_items:
                if evidence.source_id == playbook_id_str:
                    # Boost based on similarity score
                    return min(0.2, evidence.similarity_score * 0.2)
                    
            return 0.0
            
        except Exception as e:
            logger.warning(f"Error calculating similarity boost: {str(e)}")
            return 0.0

    async def _format_playbook_steps(self, playbook: Playbook) -> List[Dict[str, Any]]:
        """
        Format playbook steps for UI consumption (read-only).
        
        Args:
            playbook: Playbook with steps relationship
            
        Returns:
            List of formatted step dictionaries
        """
        steps = []
        
        # Get steps ordered by step_order
        playbook_steps = sorted(playbook.steps, key=lambda s: s.step_order)
        
        for step in playbook_steps:
            step_dict = {
                "step": step.step_order,
                "text": step.name,
                "action_type": step.action_type,
                "description": step.params.get("description", "") if step.params else ""
            }
            steps.append(step_dict)
            
        return steps

    def _generate_rationale(
        self, 
        playbook: Playbook, 
        matched_fields: List[str], 
        confidence: float
    ) -> str:
        """
        Generate human-readable rationale for the recommendation.
        
        Args:
            playbook: Recommended playbook
            matched_fields: Fields that matched during scoring
            confidence: Final confidence score
            
        Returns:
            Human-readable rationale string
        """
        rationale_parts = [
            f"Recommended '{playbook.name}' (confidence: {confidence:.1%})"
        ]
        
        if matched_fields:
            match_descriptions = []
            for field in matched_fields:
                if field == 'exception_type':
                    match_descriptions.append("exact exception type match")
                elif field == 'exception_type_partial':
                    match_descriptions.append("partial exception type match")
                elif field == 'severity':
                    match_descriptions.append("severity level match")
                elif field == 'domain':
                    match_descriptions.append("domain match")
                elif field == 'source_system':
                    match_descriptions.append("source system match")
                elif field.startswith('tag:'):
                    tag = field[4:]
                    match_descriptions.append(f"tag '{tag}' match")
            
            if match_descriptions:
                rationale_parts.append(f"Based on: {', '.join(match_descriptions)}")
        
        return ". ".join(rationale_parts)