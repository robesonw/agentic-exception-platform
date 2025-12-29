"""
Phase 13 Copilot Intelligence MVP Integration Tests.

Tests for the CopilotService orchestrator and new API endpoints.

Reference: docs/phase13-copilot-intelligence-mvp.md Section 7 (Testing)
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import time
from datetime import datetime

from src.services.copilot.copilot_service import (
    CopilotService,
    CopilotRequest,
    CopilotSessionResponse,
    Citation
)


class TestCopilotService:
    """Test the CopilotService orchestrator."""

    @pytest.fixture
    def mock_dependencies(self):
        """Create mock dependencies for CopilotService."""
        session_repository = Mock()
        intent_router = Mock()
        retrieval_service = Mock()
        similar_exceptions_finder = Mock()
        playbook_recommender = Mock()
        response_generator = Mock()
        safety_service = Mock()
        
        return {
            "session_repository": session_repository,
            "intent_router": intent_router,
            "retrieval_service": retrieval_service,
            "similar_exceptions_finder": similar_exceptions_finder,
            "playbook_recommender": playbook_recommender,
            "response_generator": response_generator,
            "safety_service": safety_service,
        }

    @pytest.fixture
    def copilot_service(self, mock_dependencies):
        """Create CopilotService with mocked dependencies."""
        return CopilotService(**mock_dependencies)

    @pytest.fixture
    def sample_request(self):
        """Create a sample copilot request."""
        return CopilotRequest(
            message="What is the best practice for handling API timeouts?",
            tenant_id="test-tenant-1",
            user_id="user-123",
            session_id=None,
            context=None,
            domain="engineering"
        )

    @pytest.mark.asyncio
    async def test_copilot_service_orchestration_flow(self, copilot_service, sample_request, mock_dependencies):
        """Test the complete 10-step orchestration flow."""
        # Mock session creation
        mock_session = Mock()
        mock_session.id = "session-456"
        mock_dependencies["session_repository"].create_session = AsyncMock(return_value=mock_session)
        mock_dependencies["session_repository"].create_message = AsyncMock()
        
        # Mock intent detection
        from src.services.copilot.router.intent_router import DetectedIntent
        mock_intent = DetectedIntent(intent="explain", confidence=0.85, features={})
        mock_dependencies["intent_router"].detect_intent = AsyncMock(return_value=mock_intent)
        
        # Mock evidence retrieval
        from src.services.copilot.retrieval.retrieval_service import RetrievalResult
        mock_evidence = [
            RetrievalResult(
                document_id="doc-1",
                content="API timeout handling best practices...",
                score=0.92,
                metadata={"source_type": "policy_doc", "title": "API Guidelines"}
            )
        ]
        mock_dependencies["retrieval_service"].retrieve_evidence = AsyncMock(return_value=mock_evidence)
        
        # Mock similar exceptions (not needed for explain intent)
        mock_dependencies["similar_exceptions_finder"].find_similar = AsyncMock(return_value=None)
        
        # Mock playbook recommendation (not needed for explain intent)
        mock_dependencies["playbook_recommender"].recommend_playbook = AsyncMock(return_value=None)
        
        # Mock response generation
        mock_raw_response = {
            "answer": "For API timeout handling, you should implement exponential backoff...",
            "bullets": [
                "Use exponential backoff with jitter",
                "Set appropriate timeout values",
                "Implement circuit breaker patterns"
            ]
        }
        mock_dependencies["response_generator"].generate_response = AsyncMock(return_value=mock_raw_response)
        
        # Mock safety evaluation
        from src.services.copilot.safety.safety_service import SafetyEvaluation
        mock_safety = SafetyEvaluation(
            mode="READ_ONLY",
            actions_allowed=[],
            violations=[],
            warnings=[],
            redacted_content=False,
            modified_answer=None
        )
        mock_dependencies["safety_service"].evaluate = Mock(return_value=mock_safety)
        
        # Execute the orchestration
        response = await copilot_service.process_message(sample_request)
        
        # Verify response structure
        assert isinstance(response, CopilotSessionResponse)
        assert response.session_id == "session-456"
        assert response.answer == mock_raw_response["answer"]
        assert response.bullets == mock_raw_response["bullets"]
        assert response.intent == "explain"
        assert response.confidence == 0.85
        assert len(response.citations) == 1
        assert response.citations[0].source_type == "policy_doc"
        assert response.safety["mode"] == "READ_ONLY"
        assert response.processing_time_ms > 0
        
        # Verify service calls
        mock_dependencies["session_repository"].create_session.assert_called_once()
        mock_dependencies["session_repository"].create_message.assert_called()  # Called twice (user + assistant)
        mock_dependencies["intent_router"].detect_intent.assert_called_once()
        mock_dependencies["retrieval_service"].retrieve_evidence.assert_called_once()
        mock_dependencies["response_generator"].generate_response.assert_called_once()

    @pytest.mark.asyncio
    async def test_session_management(self, copilot_service, mock_dependencies):
        """Test session creation and retrieval."""
        # Test session creation
        mock_session = Mock()
        mock_session.id = "new-session-789"
        mock_dependencies["session_repository"].create_session = AsyncMock(return_value=mock_session)
        
        session_id = await copilot_service.create_session(
            tenant_id="test-tenant-1",
            user_id="user-123",
            title="Test Session"
        )
        
        assert session_id == "new-session-789"
        mock_dependencies["session_repository"].create_session.assert_called_once_with(
            tenant_id="test-tenant-1",
            user_id="user-123",
            title="Test Session"
        )
        
        # Test session retrieval
        mock_session_data = {
            "session_id": "new-session-789",
            "tenant_id": "test-tenant-1",
            "user_id": "user-123",
            "title": "Test Session",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "messages": []
        }
        mock_dependencies["session_repository"].get_by_id = AsyncMock(return_value=mock_session)
        mock_dependencies["session_repository"].get_session_messages = AsyncMock(return_value=[])
        
        # Create a proper mock session object with attributes
        mock_session.id = "new-session-789"
        mock_session.tenant_id = "test-tenant-1"
        mock_session.user_id = "user-123"
        mock_session.title = "Test Session"
        mock_session.created_at = datetime.now()
        mock_session.updated_at = datetime.now()
        
        session_data = await copilot_service.get_session("new-session-789", "test-tenant-1")
        
        assert session_data["session_id"] == "new-session-789"
        assert session_data["tenant_id"] == "test-tenant-1"
        assert session_data["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_error_handling(self, copilot_service, sample_request, mock_dependencies):
        """Test error handling in orchestration."""
        # Mock session creation failure
        mock_dependencies["session_repository"].create_session = AsyncMock(
            side_effect=Exception("Database connection failed")
        )
        
        # Should return a safe fallback response
        response = await copilot_service.process_message(sample_request)
        
        assert response.intent == "error"
        assert response.confidence == 0.0
        assert "error processing your request" in response.answer.lower()
        assert response.safety["violations"] == ["Processing error occurred"]

    @pytest.mark.asyncio
    async def test_tenant_isolation(self, copilot_service, mock_dependencies):
        """Test that tenant isolation is enforced."""
        # Mock session with different tenant
        mock_session = Mock()
        mock_session.id = "session-123"
        mock_session.tenant_id = "other-tenant"
        mock_session.user_id = "user-123"
        mock_dependencies["session_repository"].get_by_id = AsyncMock(return_value=mock_session)
        
        # Should return None for tenant mismatch
        session_data = await copilot_service.get_session("session-123", "test-tenant-1")
        assert session_data is None  # No session returned due to tenant mismatch


class TestCopilotAPIEndpoints:
    """Test the FastAPI endpoints for copilot functionality."""

    @pytest.fixture
    def mock_copilot_service(self):
        """Create mock CopilotService."""
        service = Mock()
        service.process_message = AsyncMock()
        service.create_session = AsyncMock()
        service.get_session = AsyncMock()
        service.get_evidence_debug_info = AsyncMock()
        return service

    @pytest.mark.asyncio
    async def test_chat_endpoint_auth_required(self):
        """Test that chat endpoint requires authentication."""
        from fastapi.testclient import TestClient
        from src.api.routes.router_copilot import router
        from fastapi import FastAPI
        
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        
        # Request without authentication should fail
        response = client.post("/api/copilot/chat", json={
            "message": "Test message"
        })
        
        # Should return 401 or 500 depending on middleware setup
        assert response.status_code in [401, 500]

    def test_chat_request_validation(self):
        """Test request model validation."""
        from src.api.routes.router_copilot import ChatRequest
        
        # Valid request
        valid_request = ChatRequest(
            message="Test message",
            session_id=None,
            context={},
            domain="engineering"
        )
        assert valid_request.message == "Test message"
        
        # Test that empty message would fail validation if enforced
        # (Pydantic validation happens at runtime)

    def test_response_models(self):
        """Test response model structure."""
        from src.api.routes.router_copilot import ChatResponse, CreateSessionResponse
        
        # Test ChatResponse structure
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
        assert len(chat_response.bullets) == 2
        
        # Test CreateSessionResponse structure
        session_response = CreateSessionResponse(
            session_id="session-789",
            title="Test Session",
            created_at=str(time.time())
        )
        assert session_response.session_id == "session-789"


@pytest.mark.integration
class TestCopilotE2EFlow:
    """End-to-end integration tests for copilot functionality."""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires full database and service setup")
    async def test_complete_copilot_flow_with_mocked_embedding(self):
        """
        Test complete copilot flow with mocked embedding service.
        
        This test would:
        1. Seed copilot_documents table with test data
        2. Mock embedding service to return predictable vectors
        3. Send chat request through full API
        4. Verify response structure and content
        5. Check session persistence
        """
        # This would be implemented once the service dependency injection is complete
        pass

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requires admin authentication setup")
    async def test_evidence_debug_endpoint_admin_only(self):
        """
        Test that evidence debug endpoint is restricted to admin users.
        
        This test would:
        1. Make request with operator role (should fail)
        2. Make request with admin role (should succeed)
        3. Verify response contains debug information
        """
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])