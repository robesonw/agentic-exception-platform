"""
Phase 13 End-to-End Test Script for Copilot Service.

This script tests the complete copilot implementation including:
- Service factory and dependency injection
- CopilotService orchestration
- Mock implementations for MVP
- API endpoint structure validation

Usage:
    python scripts/test_copilot_phase13.py
"""

import asyncio
import logging
import sys
import time
from unittest.mock import Mock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_service_factory():
    """Test the service factory with mock database session."""
    logger.info("Testing service factory...")
    
    try:
        # Mock database session
        mock_db_session = Mock()
        
        # Test service creation with mocks
        from src.services.copilot.service_factory import create_copilot_service
        copilot_service = await create_copilot_service(mock_db_session)
        
        logger.info(f"✓ Service factory created: {type(copilot_service).__name__}")
        return True
        
    except Exception as e:
        logger.error(f"✗ Service factory test failed: {e}")
        return False


async def test_copilot_service_orchestration():
    """Test the copilot service orchestration flow."""
    logger.info("Testing copilot service orchestration...")
    
    try:
        # Create mock dependencies using service factory
        mock_db_session = Mock()
        
        from src.services.copilot.service_factory import (
            create_mock_intent_router,
            create_mock_retrieval_service,
            create_mock_similar_exceptions_finder,
            create_mock_playbook_recommender,
            create_mock_response_generator,
            create_mock_safety_service
        )
        from src.infrastructure.repositories.copilot_session_repository import CopilotSessionRepository
        from src.services.copilot.copilot_service import CopilotService, CopilotRequest
        
        # Mock session repository
        session_repository = Mock()
        mock_session = Mock()
        mock_session.id = "test-session-123"
        session_repository.create_session = Mock(return_value=mock_session)
        session_repository.create_message = Mock()
        
        # Create service with mocks
        copilot_service = CopilotService(
            session_repository=session_repository,
            intent_router=create_mock_intent_router(),
            retrieval_service=create_mock_retrieval_service(),
            similar_exceptions_finder=create_mock_similar_exceptions_finder(),
            playbook_recommender=create_mock_playbook_recommender(),
            response_generator=create_mock_response_generator(),
            safety_service=create_mock_safety_service()
        )
        
        # Test orchestration
        request = CopilotRequest(
            message="What are the best practices for API error handling?",
            tenant_id="test-tenant",
            user_id="test-user",
            session_id=None,
            domain="engineering"
        )
        
        start_time = time.time()
        response = await copilot_service.process_message(request)
        processing_time = time.time() - start_time
        
        # Validate response
        assert response.session_id == "test-session-123"
        assert len(response.answer) > 0
        assert isinstance(response.bullets, list)
        assert response.intent in ["explain", "general"]
        assert 0 <= response.confidence <= 1
        assert response.processing_time_ms > 0
        assert response.safety["mode"] == "READ_ONLY"
        
        logger.info(f"✓ Orchestration test completed in {processing_time:.3f}s")
        logger.info(f"  - Answer: {response.answer[:100]}...")
        logger.info(f"  - Intent: {response.intent} (confidence: {response.confidence})")
        logger.info(f"  - Bullets: {len(response.bullets)} points")
        logger.info(f"  - Citations: {len(response.citations)} items")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Orchestration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_session_management():
    """Test session creation and retrieval."""
    logger.info("Testing session management...")
    
    try:
        # Mock dependencies
        session_repository = Mock()
        
        # Mock session creation
        mock_session = Mock()
        mock_session.id = "session-456"
        session_repository.create_session = Mock(return_value=mock_session)
        
        # Mock session retrieval
        mock_session.tenant_id = "test-tenant"
        mock_session.user_id = "test-user"
        mock_session.title = "Test Session"
        mock_session.created_at = None
        mock_session.updated_at = None
        session_repository.get_by_id = Mock(return_value=mock_session)
        session_repository.get_session_messages = Mock(return_value=[])
        
        from src.services.copilot.copilot_service import CopilotService
        from src.services.copilot.service_factory import (
            create_mock_intent_router,
            create_mock_retrieval_service,
            create_mock_similar_exceptions_finder,
            create_mock_playbook_recommender,
            create_mock_response_generator,
            create_mock_safety_service
        )
        
        copilot_service = CopilotService(
            session_repository=session_repository,
            intent_router=create_mock_intent_router(),
            retrieval_service=create_mock_retrieval_service(),
            similar_exceptions_finder=create_mock_similar_exceptions_finder(),
            playbook_recommender=create_mock_playbook_recommender(),
            response_generator=create_mock_response_generator(),
            safety_service=create_mock_safety_service()
        )
        
        # Test session creation
        session_id = await copilot_service.create_session(
            tenant_id="test-tenant",
            user_id="test-user",
            title="Test Session"
        )
        assert session_id == "session-456"
        
        # Test session retrieval
        session_data = await copilot_service.get_session("session-456", "test-tenant")
        assert session_data["session_id"] == "session-456"
        assert session_data["tenant_id"] == "test-tenant"
        assert session_data["user_id"] == "test-user"
        
        logger.info("✓ Session management test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Session management test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_api_models():
    """Test API request/response models."""
    logger.info("Testing API models...")
    
    try:
        from src.api.routes.router_copilot import (
            ChatRequest,
            ChatResponse,
            CreateSessionRequest,
            CreateSessionResponse,
            EvidenceDebugResponse
        )
        
        # Test ChatRequest
        chat_request = ChatRequest(
            message="Test message",
            session_id="session-123",
            context={"key": "value"},
            domain="test"
        )
        assert chat_request.message == "Test message"
        
        # Test ChatResponse
        chat_response = ChatResponse(
            request_id="req-123",
            session_id="session-456",
            answer="Test answer",
            bullets=["Point 1", "Point 2"],
            citations=[],
            recommended_playbook=None,
            similar_exceptions=None,
            intent="explain",
            confidence=0.85,
            processing_time_ms=250,
            safety={"mode": "READ_ONLY", "actions_allowed": [], "violations": [], "warnings": [], "redacted_content": False}
        )
        assert chat_response.answer == "Test answer"
        
        # Test session models
        create_session_request = CreateSessionRequest(title="Test")
        session_response = CreateSessionResponse(
            session_id="session-789",
            title="Test Session",
            created_at=str(time.time())
        )
        assert session_response.session_id == "session-789"
        
        logger.info("✓ API models test passed")
        return True
        
    except Exception as e:
        logger.error(f"✗ API models test failed: {e}")
        return False


async def run_all_tests():
    """Run all tests and report results."""
    logger.info("Starting Phase 13 Copilot Service Tests...")
    logger.info("=" * 60)
    
    tests = [
        ("Service Factory", test_service_factory()),
        ("Copilot Orchestration", test_copilot_service_orchestration()),
        ("Session Management", test_session_management()),
        ("API Models", test_api_models()),
    ]
    
    results = []
    for test_name, test_coro in tests:
        try:
            if asyncio.iscoroutine(test_coro):
                result = await test_coro
            else:
                result = test_coro
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Report results
    logger.info("=" * 60)
    logger.info("TEST RESULTS:")
    
    passed = 0
    for test_name, success in results:
        status = "PASS" if success else "FAIL"
        logger.info(f"  {test_name}: {status}")
        if success:
            passed += 1
    
    logger.info("-" * 60)
    logger.info(f"Tests passed: {passed}/{len(results)}")
    
    if passed == len(results):
        logger.info("🎉 All tests passed! Phase 13 implementation ready.")
        return True
    else:
        logger.error("❌ Some tests failed. Review implementation.")
        return False


def main():
    """Main entry point for test script."""
    success = asyncio.run(run_all_tests())
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()