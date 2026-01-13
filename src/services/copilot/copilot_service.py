"""
Phase 13 Copilot Service Orchestrator.

Coordinates the complete copilot workflow from user query to structured response,
integrating session management, intent detection, evidence retrieval, and safety checks.

Flow:
1) Load/create session (CopilotSessionRepository)
2) Store user message
3) Detect intent (IntentDetectionRouter)
4) Retrieve evidence (RetrievalService)
5) Compute similar cases if needed (SimilarExceptionsFinder)
6) Recommend playbook if needed (PlaybookRecommender)
7) Generate structured response (CopilotResponseGenerator)
8) Apply safety (CopilotSafetyService)
9) Store assistant message with citations + intent metadata
10) Return structured payload

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4-6
- Phase 13 Issues P13-15, P13-17, P13-18, P13-19, P13-21
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

from src.infrastructure.repositories.copilot_session_repository import CopilotSessionRepository
from src.services.copilot.router.intent_router import IntentDetectionRouter, IntentResult
from src.services.copilot.retrieval.retrieval_service import RetrievalService, EvidenceItem
from src.services.copilot.similarity.similar_exceptions import SimilarExceptionsFinder, SimilarException
from src.services.copilot.playbooks.playbook_recommender import PlaybookRecommender, RecommendedPlaybook
from src.services.copilot.response.response_generator import CopilotResponseGenerator
from src.services.copilot.safety.safety_service import CopilotSafetyService, SafetyEvaluation


@dataclass
class CopilotRequest:
    """Structured request for copilot interaction."""
    message: str
    tenant_id: str
    user_id: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    domain: Optional[str] = None


@dataclass
class Citation:
    """Evidence citation with metadata."""
    id: str
    source_type: str  # 'policy_doc', 'resolved_exception', 'audit_event', 'tool_registry'
    title: str
    snippet: str
    relevance_score: float
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class CopilotSessionResponse:
    """Complete copilot response with session context."""
    request_id: str
    session_id: str
    answer: str
    bullets: List[str]
    citations: List[Citation]
    recommended_playbook: Optional[Dict[str, Any]]
    similar_exceptions: Optional[List[Dict[str, Any]]]
    intent: str
    confidence: float
    processing_time_ms: int
    safety: Dict[str, Any]


class CopilotService:
    """
    Main orchestrator for copilot interactions.
    
    Coordinates all phases of copilot processing while maintaining
    tenant isolation and security constraints.
    """

    def __init__(
        self,
        session_repository: CopilotSessionRepository,
        intent_router: IntentDetectionRouter,
        retrieval_service: RetrievalService,
        similar_exceptions_finder: SimilarExceptionsFinder,
        playbook_recommender: PlaybookRecommender,
        response_generator: CopilotResponseGenerator,
        safety_service: CopilotSafetyService,
    ):
        """Initialize copilot service with required dependencies."""
        self.session_repository = session_repository
        self.intent_router = intent_router
        self.retrieval_service = retrieval_service
        self.similar_exceptions_finder = similar_exceptions_finder
        self.playbook_recommender = playbook_recommender
        self.response_generator = response_generator
        self.safety_service = safety_service
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def process_message(self, request: CopilotRequest) -> CopilotSessionResponse:
        """
        Process a copilot message through the complete workflow.
        
        Args:
            request: Copilot request with message and context
            
        Returns:
            CopilotSessionResponse: Complete structured response
        """
        start_time = time.time()
        request_id = str(uuid4())
        
        self.logger.info(
            f"Processing copilot message: request_id={request_id}, "
            f"tenant_id={request.tenant_id}, user_id={request.user_id}, "
            f"message_length={len(request.message)}"
        )
        
        try:
            # Step 1: Load or create session
            session = await self._load_or_create_session(
                request.session_id, request.tenant_id, request.user_id
            )
            
            # Step 2: Store user message
            await self._store_user_message(session.id, request.message, request_id, request.tenant_id)
            
            # Step 3: Detect intent
            detected_intent = await self._detect_intent(request.message, request.context)
            
            # Step 4: Retrieve evidence
            evidence = await self._retrieve_evidence(
                request.message, detected_intent, request.tenant_id, request.domain
            )
            
            # Step 5: Find similar cases if needed
            similar_exceptions = await self._find_similar_exceptions(
                detected_intent, request.message, request.tenant_id
            )
            
            # Step 6: Recommend playbook if needed
            playbook_recommendation = await self._recommend_playbook(
                detected_intent, evidence, similar_exceptions, request.tenant_id
            )
            
            # Step 7: Generate structured response
            raw_response = await self._generate_response(
                request.message,
                detected_intent,
                evidence,
                similar_exceptions,
                playbook_recommendation,
                request.context
            )
            
            # Step 8: Apply safety checks
            safety_evaluation = await self._apply_safety(
                detected_intent.intent_type.value, raw_response, request.tenant_id
            )
            
            # Step 9: Store assistant message
            final_response_data = self._build_response_data(
                raw_response, safety_evaluation, evidence, similar_exceptions, playbook_recommendation
            )
            await self._store_assistant_message(
                session.id, final_response_data, detected_intent, request_id, request.tenant_id
            )
            
            # Step 10: Return structured response
            processing_time_ms = int((time.time() - start_time) * 1000)
            
            return CopilotSessionResponse(
                request_id=request_id,
                session_id=session.id,
                answer=safety_evaluation.modified_answer or raw_response.get("answer", ""),
                bullets=raw_response.get("bullets", []),
                citations=self._convert_evidence_to_citations(evidence),
                recommended_playbook=self._format_playbook_recommendation(playbook_recommendation),
                similar_exceptions=self._format_similar_exceptions(similar_exceptions),
                intent=detected_intent.intent_type.value,
                confidence=detected_intent.confidence,
                processing_time_ms=processing_time_ms,
                safety={
                    "mode": safety_evaluation.mode,
                    "actions_allowed": safety_evaluation.actions_allowed,
                    "violations": safety_evaluation.violations,
                    "warnings": safety_evaluation.warnings,
                    "redacted_content": safety_evaluation.redacted_content
                }
            )
            
        except Exception as e:
            self.logger.error(f"Error processing copilot message: {e}", exc_info=True)
            # Return helpful fallback response that still addresses the user's query
            error_detail = str(e)[:200] if str(e) else "Unknown error"
            fallback_answer = (
                f"I'm having trouble processing your query right now. "
                f"You can review the exception details, timeline, and status in the exception view. "
                f"If this issue persists, please check the system logs or contact support."
            )
            
            return CopilotSessionResponse(
                request_id=request_id,
                session_id=request.session_id or str(uuid4()),
                answer=fallback_answer,
                bullets=[
                    "Review the exception details view for timeline, status, and attributes",
                    "Check the exception's pipeline status and current stage",
                    "Review any available evidence or audit logs for this exception",
                    "If the issue persists, check system logs or contact support"
                ],
                citations=[],
                recommended_playbook=None,
                similar_exceptions=None,
                intent="error",
                confidence=0.0,
                processing_time_ms=int((time.time() - start_time) * 1000),
                safety={
                    "mode": "READ_ONLY",
                    "actions_allowed": [],
                    "violations": [f"Processing error: {error_detail}"],
                    "warnings": ["Error occurred during processing - showing fallback response"],
                    "redacted_content": False
                }
            )

    async def _load_or_create_session(
        self, session_id: Optional[str], tenant_id: str, user_id: str
    ) -> Any:
        """Load existing session or create new one."""
        if session_id:
            session = await self.session_repository.get_by_id(session_id, tenant_id)
            if session and session.user_id == user_id:
                return session
        
        # Create new session
        return await self.session_repository.create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            title=f"Copilot Session {int(time.time())}"
        )

    async def _store_user_message(self, session_id: str, message: str, request_id: str, tenant_id: str) -> None:
        """Store user message in session."""
        await self.session_repository.add_message(
            session_id=session_id,
            tenant_id=tenant_id,
            role="user",
            content=message,
            metadata={"request_id": request_id, "timestamp": time.time()},
            request_id=request_id
        )

    async def _detect_intent(self, message: str, context: Optional[Dict[str, Any]]) -> IntentResult:
        """Detect user intent from message."""
        tenant_id = context.get("tenant_id") if context else None
        domain = context.get("domain") if context else None
        exception_id = context.get("exception_id") if context else None
        
        return self.intent_router.detect_intent(
            message=message,
            exception_id=exception_id,
            tenant_id=tenant_id,
            domain=domain
        )

    async def _retrieve_evidence(
        self, message: str, intent: IntentResult, tenant_id: str, domain: Optional[str]
    ) -> List[EvidenceItem]:
        """Retrieve relevant evidence for the query."""
        return await self.retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text=message,
            domain=domain,
            top_k=10
        )

    async def _find_similar_exceptions(
        self, intent: IntentResult, message: str, tenant_id: str
    ) -> Optional[List[SimilarException]]:
        """Find similar exceptions if intent requires it."""
        if intent.intent_type.value in ["similar_cases", "explain", "recommend_playbook"]:
            return await self.similar_exceptions_finder.find_similar_by_query(
                query=message,
                tenant_id=tenant_id,
                top_n=5
            )
        return None

    async def _recommend_playbook(
        self,
        intent: IntentResult,
        evidence: List[EvidenceItem],
        similar_exceptions: Optional[List[SimilarException]],
        tenant_id: str
    ) -> Optional[RecommendedPlaybook]:
        """Recommend playbook if intent requires it."""
        if intent.intent_type.value in ["recommend_playbook"]:
            return await self.playbook_recommender.recommend_playbook(
                evidence=evidence,
                similar_exceptions=similar_exceptions,
                tenant_id=tenant_id
            )
        return None

    async def _generate_response(
        self,
        message: str,
        intent: IntentResult,
        evidence: List[EvidenceItem],
        similar_exceptions: Optional[List[SimilarException]],
        playbook_recommendation: Optional[RecommendedPlaybook],
        context: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Generate structured response."""
        return self.response_generator.generate_response(
            user_query=message,
            intent=intent.intent_type.value,
            evidence_items=evidence,
            similar_cases=similar_exceptions,
            playbook_reco=playbook_recommendation
        )

    async def _apply_safety(
        self, intent: str, response: Dict[str, Any], tenant_id: str
    ) -> SafetyEvaluation:
        """Apply safety evaluation to response."""
        # Get tenant-specific safety policies if any
        tenant_policy = await self._get_tenant_safety_policy(tenant_id)
        
        return self.safety_service.evaluate(
            intent=intent,
            response_payload=response,
            tenant_policy=tenant_policy
        )

    async def _get_tenant_safety_policy(self, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get tenant-specific safety policy."""
        # For MVP, return None - can be enhanced with tenant policy lookup
        return None

    def _build_response_data(
        self,
        raw_response: Dict[str, Any],
        safety_evaluation: SafetyEvaluation,
        evidence: List[EvidenceItem],
        similar_exceptions: Optional[List[SimilarException]],
        playbook_recommendation: Optional[RecommendedPlaybook]
    ) -> Dict[str, Any]:
        """Build complete response data for storage."""
        return {
            "answer": safety_evaluation.modified_answer or raw_response.get("answer", ""),
            "bullets": raw_response.get("bullets", []),
            "citations": [self._evidence_to_dict(r) for r in evidence],
            "similar_exceptions": [self._similar_to_dict(s) for s in (similar_exceptions or [])],
            "playbook_recommendation": self._playbook_to_dict(playbook_recommendation),
            "safety_metadata": {
                "violations": safety_evaluation.violations,
                "warnings": safety_evaluation.warnings,
                "redacted_content": safety_evaluation.redacted_content
            }
        }

    async def _store_assistant_message(
        self,
        session_id: str,
        response_data: Dict[str, Any],
        intent: IntentResult,
        request_id: str,
        tenant_id: str
    ) -> None:
        """Store assistant message with metadata."""
        await self.session_repository.add_message(
            session_id=session_id,
            tenant_id=tenant_id,
            role="assistant",
            content=response_data["answer"],
            metadata={
                "request_id": request_id,
                "intent": intent.intent_type.value,
                "confidence": intent.confidence,
                "bullets": response_data["bullets"],
                "citations": response_data["citations"],
                "similar_exceptions": response_data["similar_exceptions"],
                "playbook_recommendation": response_data["playbook_recommendation"],
                "safety_metadata": response_data["safety_metadata"],
                "timestamp": time.time()
            },
            request_id=request_id
        )

    def _convert_evidence_to_citations(self, evidence: List[EvidenceItem]) -> List[Citation]:
        """Convert retrieval results to citations."""
        citations = []
        for item in evidence:
            citations.append(Citation(
                id=item.source_id,
                source_type=item.source_type,
                title=item.title,
                snippet=item.snippet,
                relevance_score=item.similarity_score,
                metadata={
                    "url": item.url,
                    "version": item.source_version,
                    "chunk_text": item.chunk_text
                }
            ))
        return citations

    def _format_playbook_recommendation(
        self, recommendation: Optional[RecommendedPlaybook]
    ) -> Optional[Dict[str, Any]]:
        """Format playbook recommendation for response."""
        if not recommendation:
            return None
        
        return {
            "playbook_id": recommendation.playbook_id,
            "confidence": recommendation.confidence,
            "rationale": recommendation.rationale,
            "matched_fields": recommendation.matched_fields,
            "steps_preview": recommendation.steps[:3] if recommendation.steps else []
        }

    def _format_similar_exceptions(
        self, similar_exceptions: Optional[List[SimilarException]]
    ) -> Optional[List[Dict[str, Any]]]:
        """Format similar exceptions for response."""
        if not similar_exceptions:
            return None
        
        return [{
            "exception_id": exc.exception_id,
            "similarity_score": exc.similarity_score,
            "title": exc.title,
            "outcome_summary": exc.outcome_summary,
            "resolution_date": exc.resolution_date
        } for exc in similar_exceptions]

    def _evidence_to_dict(self, evidence: EvidenceItem) -> Dict[str, Any]:
        """Convert evidence item to dict."""
        return {
            "source_id": evidence.source_id,
            "source_type": evidence.source_type,
            "title": evidence.title,
            "snippet": evidence.snippet,
            "similarity_score": evidence.similarity_score,
            "url": evidence.url,
            "source_version": evidence.source_version,
            "chunk_text": evidence.chunk_text
        }

    def _similar_to_dict(self, similar: SimilarException) -> Dict[str, Any]:
        """Convert similar exception to dict."""
        return {
            "exception_id": similar.exception_id,
            "similarity_score": similar.similarity_score,
            "title": similar.title,
            "outcome_summary": similar.outcome_summary,
            "resolution_date": similar.resolution_date
        }

    def _playbook_to_dict(self, recommendation: Optional[RecommendedPlaybook]) -> Optional[Dict[str, Any]]:
        """Convert playbook recommendation to dict."""
        if not recommendation:
            return None
        
        return {
            "playbook_id": recommendation.playbook_id,
            "confidence": recommendation.confidence,
            "rationale": recommendation.rationale,
            "matched_fields": recommendation.matched_fields,
            "steps": recommendation.steps
        }

    async def get_session(self, session_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Get session details with messages."""
        session = await self.session_repository.get_by_id(session_id, tenant_id)
        if not session:
            return None
        
        messages = await self.session_repository.get_session_messages(
            session_id, tenant_id, limit=100
        )
        
        return {
            "session_id": session.id,
            "tenant_id": session.tenant_id,
            "user_id": session.user_id,
            "title": session.title,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "updated_at": session.updated_at.isoformat() if session.updated_at else None,
            "messages": [
                {
                    "id": msg.id,
                    "role": msg.role,
                    "content": msg.content,
                    "metadata": msg.metadata,
                    "created_at": msg.created_at.isoformat() if msg.created_at else None
                }
                for msg in messages
            ]
        }

    async def create_session(self, tenant_id: str, user_id: str, title: Optional[str] = None) -> str:
        """Create new session and return session ID."""
        logger.info(f"CopilotService.create_session called with tenant_id='{tenant_id}', user_id='{user_id}', title='{title}'")
        
        # Debug validation
        if not user_id:
            logger.error(f"CopilotService received empty user_id: {repr(user_id)}")
            raise ValueError(f"user_id is required (CopilotService received: {repr(user_id)})")
        
        session = await self.session_repository.create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title or f"New Conversation {int(time.time())}"
        )
        session_id = str(session.id)
        logger.info(f"Session created with ID: {session_id}")
        return session_id

    async def get_evidence_debug_info(self, request_id: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """
        Get evidence debug information for a specific request (admin-only).
        
        Args:
            request_id: The request ID to look up
            tenant_id: Tenant ID for isolation
            
        Returns:
            Debug information about evidence retrieval and processing
        """
        # This would typically query stored debug information
        # For MVP, return placeholder structure
        return {
            "request_id": request_id,
            "tenant_id": tenant_id,
            "retrieval_debug": {
                "query_embedding": "vector_placeholder",
                "retrieved_documents": [],
                "similarity_scores": [],
                "filter_criteria": {}
            },
            "intent_debug": {
                "detected_intent": "unknown",
                "confidence": 0.0,
                "features": {}
            },
            "processing_timeline": [],
            "outcome_summary": f"Debug information for request {request_id} in tenant {tenant_id}",
            "closed_at": None,
            "link_url": None
        }