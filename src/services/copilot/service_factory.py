"""
Copilot Service Factory for Phase 13 dependency injection.

Provides factory functions to create properly wired CopilotService instances
with all required dependencies.

This is a temporary MVP implementation - in production this would be
replaced with a proper DI container like dependency-injector.
"""

import logging
from typing import Optional

from src.services.copilot.copilot_service import CopilotService
from src.infrastructure.repositories.copilot_session_repository import CopilotSessionRepository
from src.services.copilot.router.intent_router import IntentDetectionRouter
from src.services.copilot.retrieval.retrieval_service import RetrievalService
from src.services.copilot.similarity.similar_exceptions import SimilarExceptionsFinder
from src.services.copilot.playbooks.playbook_recommender import PlaybookRecommender
from src.services.copilot.response.response_generator import CopilotResponseGenerator
from src.services.copilot.safety.safety_service import CopilotSafetyService
from src.infrastructure.db.session import AsyncSession


logger = logging.getLogger(__name__)


async def create_copilot_service(db_session: AsyncSession) -> CopilotService:
    """
    Create a fully wired CopilotService instance.
    
    Args:
        db_session: Database session for repositories
        
    Returns:
        CopilotService: Ready-to-use service instance
    """
    logger.info("Creating CopilotService with dependencies")
    
    try:
        # Initialize repositories
        session_repository = CopilotSessionRepository(db_session)
        
        # Initialize services
        intent_router = create_intent_detection_router()
        retrieval_service = create_retrieval_service(db_session)
        similar_exceptions_finder = create_similar_exceptions_finder(db_session, retrieval_service)
        playbook_recommender = create_playbook_recommender(db_session)
        response_generator = create_response_generator()
        safety_service = create_safety_service()
        
        # Wire everything together
        return CopilotService(
            session_repository=session_repository,
            intent_router=intent_router,
            retrieval_service=retrieval_service,
            similar_exceptions_finder=similar_exceptions_finder,
            playbook_recommender=playbook_recommender,
            response_generator=response_generator,
            safety_service=safety_service,
        )
        
    except Exception as e:
        logger.error(f"Failed to create CopilotService: {e}", exc_info=True)
        raise


def create_intent_detection_router() -> IntentDetectionRouter:
    """Create intent detection router."""
    try:
        from src.services.copilot.router.intent_router import IntentDetectionRouter
        return IntentDetectionRouter()
    except ImportError as e:
        logger.warning(f"IntentDetectionRouter not available: {e}")
        # Return a mock implementation for MVP
        return create_mock_intent_router()


def create_retrieval_service(db_session: AsyncSession) -> RetrievalService:
    """Create evidence retrieval service."""
    try:
        from src.services.copilot.embedding_service import EmbeddingService
        from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
        
        embedding_service = EmbeddingService()
        document_repository = CopilotDocumentRepository(db_session)
        
        return RetrievalService(
            embedding_service=embedding_service,
            document_repository=document_repository
        )
    except ImportError as e:
        logger.warning(f"RetrievalService dependencies not available: {e}")
        return create_mock_retrieval_service()


def create_similar_exceptions_finder(
    db_session: AsyncSession,
    retrieval_service: RetrievalService
) -> SimilarExceptionsFinder:
    """Create similar exceptions finder."""
    try:
        from src.repository.exceptions_repository import ExceptionRepository
        
        exception_repository = ExceptionRepository(db_session)
        
        return SimilarExceptionsFinder(
            exception_repository=exception_repository,
            retrieval_service=retrieval_service
        )
    except ImportError as e:
        logger.warning(f"SimilarExceptionsFinder dependencies not available: {e}")
        return create_mock_similar_exceptions_finder()


def create_playbook_recommender(db_session: AsyncSession = None) -> PlaybookRecommender:
    """Create playbook recommender."""
    try:
        from src.services.copilot.playbooks.playbook_recommender import PlaybookRecommender
        from src.infrastructure.repositories.playbook_repository import PlaybookRepository
        from src.services.copilot.retrieval.retrieval_service import RetrievalService
        
        if db_session is None:
            logger.warning("No database session provided for PlaybookRecommender, using mock")
            return create_mock_playbook_recommender()
        
        # Try to create with required dependencies
        playbook_repository = PlaybookRepository(db_session)
        # Note: retrieval_service would be passed separately in real implementation
        # For MVP, we'll use the mock since the real service has complex dependencies
        return create_mock_playbook_recommender()
        
    except (ImportError, TypeError) as e:
        logger.warning(f"PlaybookRecommender not available: {e}")
        return create_mock_playbook_recommender()


def create_response_generator() -> CopilotResponseGenerator:
    """Create response generator."""
    try:
        from src.services.copilot.response.response_generator import CopilotResponseGenerator
        return CopilotResponseGenerator()
    except ImportError as e:
        logger.warning(f"CopilotResponseGenerator not available: {e}")
        return create_mock_response_generator()


def create_safety_service() -> CopilotSafetyService:
    """Create safety service."""
    try:
        from src.services.copilot.safety.safety_service import CopilotSafetyService
        return CopilotSafetyService()
    except ImportError as e:
        logger.warning(f"CopilotSafetyService not available: {e}")
        return create_mock_safety_service()


# Mock implementations for MVP when real services aren't available

class MockIntentDetectionRouter:
    """Mock intent detection router."""
    
    def detect_intent(
        self, 
        message: str, 
        exception_id: str = None,
        tenant_id: str = None,
        domain: str = None
    ):
        from src.services.copilot.router.intent_router import IntentResult, IntentType
        
        # Simple intent classification based on keywords
        message_lower = message.lower()
        
        if any(word in message_lower for word in ["similar", "like", "compare"]):
            intent_type = IntentType.SIMILAR_CASES
            confidence = 0.8
        elif any(word in message_lower for word in ["explain", "what", "how", "why"]):
            intent_type = IntentType.EXPLAIN
            confidence = 0.9
        elif any(word in message_lower for word in ["recommend", "suggest", "should", "playbook"]):
            intent_type = IntentType.RECOMMEND_PLAYBOOK
            confidence = 0.85
        elif any(word in message_lower for word in ["summary", "summarize"]):
            intent_type = IntentType.SUMMARY
            confidence = 0.85
        else:
            intent_type = IntentType.OTHER
            confidence = 0.6
            
        return IntentResult(
            intent_type=intent_type,
            confidence=confidence,
            extracted_params={"keywords": message_lower.split()[:5]},
            raw_message=message,
            processing_metadata={"mock": True}
        )


class MockRetrievalService:
    """Mock retrieval service."""
    
    async def retrieve_evidence(self, tenant_id, query_text: str, domain=None, top_k=5, **kwargs):
        from src.services.copilot.retrieval.retrieval_service import EvidenceItem
        
        # Return mock evidence based on query
        return [
            EvidenceItem(
                source_type="PolicyDoc",
                source_id="mock-doc-1",
                source_version="v1.0",
                title=f"Policy Document for {query_text[:20]}",
                snippet=f"Mock evidence for query: {query_text[:50]}...",
                url=f"/docs/mock-doc-1",
                similarity_score=0.85,
                chunk_text=f"Full mock evidence content for query: {query_text}. This would be the complete text chunk from the policy document."
            )
        ]


class MockSimilarExceptionsFinder:
    """Mock similar exceptions finder."""
    
    async def find_similar(self, tenant_id: str, exception_id: str, top_n: int = 5):
        return []  # No similar exceptions for MVP mock

    async def find_similar_by_query(self, query: str, tenant_id: str, top_n: int = 5):
        return []  # No similar exceptions for MVP mock


class MockPlaybookRecommender:
    """Mock playbook recommender."""
    
    async def recommend_playbook(self, evidence, similar_exceptions, tenant_id: str, **kwargs):
        return None  # No playbook recommendations for MVP mock


class MockResponseGenerator:
    """Mock response generator."""
    
    async def generate_response(
        self, 
        user_message: str,
        intent: str,
        evidence,
        similar_exceptions,
        playbook_recommendation,
        context
    ):
        return {
            "answer": f"This is a mock response for your {intent} query: {user_message[:50]}...",
            "bullets": [
                "This is a mock bullet point",
                "Another mock point based on evidence",
                "Final mock recommendation"
            ]
        }


class MockSafetyService:
    """Mock safety service."""
    
    def evaluate(self, intent: str, response_payload: dict, tenant_policy=None):
        from src.services.copilot.safety.safety_service import SafetyEvaluation
        
        return SafetyEvaluation(
            mode="READ_ONLY",
            actions_allowed=[],
            violations=[],
            warnings=[],
            redacted_content=False,
            modified_answer=None
        )


def create_mock_intent_router() -> MockIntentDetectionRouter:
    """Create mock intent detection router."""
    return MockIntentDetectionRouter()


def create_mock_retrieval_service() -> MockRetrievalService:
    """Create mock retrieval service."""
    return MockRetrievalService()


def create_mock_similar_exceptions_finder() -> MockSimilarExceptionsFinder:
    """Create mock similar exceptions finder."""
    return MockSimilarExceptionsFinder()


def create_mock_playbook_recommender() -> MockPlaybookRecommender:
    """Create mock playbook recommender."""
    return MockPlaybookRecommender()


def create_mock_response_generator() -> MockResponseGenerator:
    """Create mock response generator."""
    return MockResponseGenerator()


def create_mock_safety_service() -> MockSafetyService:
    """Create mock safety service."""
    return MockSafetyService()