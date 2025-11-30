"""
Tests for Natural Language Query (NLQ) API.

Tests Phase 3 enhancements:
- Answering questions about exceptions
- Context bundle construction
- LLM integration
- Fallback when LLM unavailable
- Tenant isolation
- Audit logging
"""

import json
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.audit.logger import AuditLogger
from src.llm.provider import LLMClient, LLMUsageMetrics
from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store
from src.services.nlq_service import NLQService, NLQServiceError
from src.services.ui_query_service import UIQueryService, get_ui_query_service

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture(autouse=True)
def setup_auth():
    """Set up authentication for tests."""
    auth = get_api_key_auth()
    auth.register_api_key(DEFAULT_API_KEY, "tenant_001", Role.ADMIN)
    yield
    # Cleanup if needed


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def auth_headers():
    """Create authentication headers for API requests."""
    return {"X-API-KEY": DEFAULT_API_KEY}


@pytest.fixture
def sample_exception():
    """Create a sample exception record."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        resolution_status=ResolutionStatus.OPEN,
        source_system="test_system",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"error": "test error"},
    )


@pytest.fixture
def sample_pipeline_result():
    """Create a sample pipeline result with agent decisions."""
    return {
        "stages": {
            "intake": AgentDecision(
                decision="Normalized",
                confidence=1.0,
                evidence=["Extracted fields"],
                next_step="ProceedToTriage",
            ),
            "triage": AgentDecision(
                decision="Classified as DataQualityFailure",
                confidence=0.9,
                evidence=["Rule matched: invalid_format", "RAG similarity: 0.92"],
                next_step="ProceedToPolicy",
            ),
            "policy": AgentDecision(
                decision="Blocked by guardrails",
                confidence=0.95,
                evidence=["Guardrail: CRITICAL severity requires approval"],
                next_step="Escalate",
            ),
        },
        "rag_results": [
            {"similarity": 0.92, "exception_id": "exc_000", "summary": "Similar exception"}
        ],
        "tool_outputs": [{"tool": "validateData", "result": "success"}],
    }


@pytest.fixture
def setup_exception_store(sample_exception, sample_pipeline_result):
    """Set up exception store with sample data."""
    store = get_exception_store()
    store.store_exception(sample_exception, sample_pipeline_result)
    yield store
    store.clear_all()


class TestNLQAPI:
    """Tests for NLQ API."""

    @pytest.mark.asyncio
    async def test_answer_question_with_llm(self, setup_exception_store):
        """Test answering a question with LLM client."""
        # Create mock LLM client
        mock_llm_client = AsyncMock(spec=LLMClient)
        mock_llm_client.generate_json = AsyncMock(
            return_value={
                "answer": "The exception was blocked because it has CRITICAL severity and requires human approval per guardrails.",
                "answer_sources": ["policy_decision"],
                "agent_context_used": ["PolicyAgent"],
                "confidence": 0.95,
                "reasoning": "PolicyAgent decision shows blocking due to CRITICAL severity guardrail.",
            }
        )
        
        # Create NLQ service with mock LLM client
        nlq_service = NLQService(llm_client=mock_llm_client)
        
        # Answer question
        result = await nlq_service.answer_question(
            tenant_id="tenant_001",
            exception_id="exc_001",
            question="Why did you block this?",
        )
        
        # Verify answer
        assert "blocked" in result["answer"].lower() or "block" in result["answer"].lower()
        assert len(result["answer_sources"]) > 0
        assert "PolicyAgent" in result["agent_context_used"]
        assert result["confidence"] > 0.0
        
        # Verify LLM was called
        mock_llm_client.generate_json.assert_called_once()
        call_args = mock_llm_client.generate_json.call_args
        assert call_args.kwargs["schema_name"] == "nlq_answer"
        assert call_args.kwargs["tenant_id"] == "tenant_001"
        assert "Why did you block this?" in call_args.kwargs["prompt"]

    @pytest.mark.asyncio
    async def test_answer_question_fallback(self, setup_exception_store):
        """Test answering a question without LLM client (fallback)."""
        # Create NLQ service without LLM client
        nlq_service = NLQService(llm_client=None)
        
        # Answer question
        result = await nlq_service.answer_question(
            tenant_id="tenant_001",
            exception_id="exc_001",
            question="Why did you block this?",
        )
        
        # Verify fallback answer
        assert len(result["answer"]) > 0
        assert result["confidence"] > 0.0
        assert isinstance(result["answer_sources"], list)
        assert isinstance(result["agent_context_used"], list)

    @pytest.mark.asyncio
    async def test_answer_question_evidence(self, setup_exception_store):
        """Test answering question about evidence."""
        # Create NLQ service
        nlq_service = NLQService(llm_client=None)
        
        # Answer question about evidence
        result = await nlq_service.answer_question(
            tenant_id="tenant_001",
            exception_id="exc_001",
            question="What evidence did Triage use?",
        )
        
        # Verify answer mentions evidence
        assert len(result["answer"]) > 0
        assert "TriageAgent" in result["agent_context_used"] or "triage" in result["answer"].lower()

    @pytest.mark.asyncio
    async def test_answer_question_alternatives(self, setup_exception_store):
        """Test answering question about alternatives."""
        # Create NLQ service
        nlq_service = NLQService(llm_client=None)
        
        # Answer question about alternatives
        result = await nlq_service.answer_question(
            tenant_id="tenant_001",
            exception_id="exc_001",
            question="What alternative actions were possible?",
        )
        
        # Verify answer
        assert len(result["answer"]) > 0
        assert result["confidence"] > 0.0

    def test_context_bundle_construction(self, setup_exception_store):
        """Test that context bundle is constructed correctly."""
        # Create NLQ service
        nlq_service = NLQService()
        
        # Get exception detail
        ui_service = get_ui_query_service()
        exception_detail = ui_service.get_exception_detail("tenant_001", "exc_001")
        evidence = ui_service.get_exception_evidence("tenant_001", "exc_001")
        audit_events = ui_service.get_exception_audit("tenant_001", "exc_001")
        
        # Build context bundle
        context_bundle = nlq_service._build_context_bundle(exception_detail, evidence, audit_events)
        
        # Verify context bundle structure
        assert "exception" in context_bundle
        assert "agent_decisions" in context_bundle
        assert "evidence" in context_bundle
        assert "recent_audit_events" in context_bundle
        
        # Verify exception summary
        assert context_bundle["exception"]["exception_id"] == "exc_001"
        assert context_bundle["exception"]["exception_type"] == "DataQualityFailure"
        
        # Verify agent decisions
        assert "triage" in context_bundle["agent_decisions"]
        assert "policy" in context_bundle["agent_decisions"]
        
        # Verify evidence
        assert "rag_results" in context_bundle["evidence"]
        assert "tool_outputs" in context_bundle["evidence"]

    def test_nlq_prompt_construction(self, setup_exception_store):
        """Test that NLQ prompt is constructed correctly."""
        # Create NLQ service
        nlq_service = NLQService()
        
        # Get context bundle
        ui_service = get_ui_query_service()
        exception_detail = ui_service.get_exception_detail("tenant_001", "exc_001")
        evidence = ui_service.get_exception_evidence("tenant_001", "exc_001")
        audit_events = ui_service.get_exception_audit("tenant_001", "exc_001")
        context_bundle = nlq_service._build_context_bundle(exception_detail, evidence, audit_events)
        
        # Build prompt
        prompt = nlq_service._build_nlq_prompt("Why did you block this?", context_bundle)
        
        # Verify prompt contains question and context
        assert "Why did you block this?" in prompt
        assert "Exception:" in prompt
        assert "Agent Decisions:" in prompt
        assert "Evidence:" in prompt
        assert "Instructions:" in prompt

    def test_api_endpoint(self, client, setup_exception_store, auth_headers):
        """Test NLQ API endpoint."""
        # Create request
        request_data = {
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
            "question": "Why did you block this?",
        }
        
        # Call API
        response = client.post("/ui/nlq", json=request_data, headers=auth_headers)
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "answer_sources" in data
        assert "agent_context_used" in data
        assert "confidence" in data
        assert "supporting_evidence" in data
        assert len(data["answer"]) > 0
        assert 0.0 <= data["confidence"] <= 1.0

    def test_api_endpoint_not_found(self, client, auth_headers):
        """Test NLQ API endpoint with non-existent exception."""
        # Create request
        request_data = {
            "tenant_id": "tenant_001",
            "exception_id": "nonexistent",
            "question": "Why did you block this?",
        }
        
        # Call API
        response = client.post("/ui/nlq", json=request_data, headers=auth_headers)
        
        # Verify 404 response
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_api_endpoint_tenant_isolation(self, client, setup_exception_store, auth_headers):
        """Test that NLQ enforces tenant isolation."""
        # Create exception for different tenant
        store = get_exception_store()
        other_tenant_exc = ExceptionRecord(
            exception_id="exc_other",
            tenant_id="tenant_002",
            exception_type="DataQualityFailure",
            severity=Severity.HIGH,
            resolution_status=ResolutionStatus.OPEN,
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "other tenant"},
        )
        store.store_exception(other_tenant_exc, {"stages": {}})
        
        # Try to query with wrong tenant
        request_data = {
            "tenant_id": "tenant_001",
            "exception_id": "exc_other",
            "question": "Why did you block this?",
        }
        
        # Call API
        response = client.post("/ui/nlq", json=request_data, headers=auth_headers)
        
        # Should fail due to tenant isolation
        assert response.status_code in [404, 500]  # Either not found or tenant isolation error
        
        store.clear_all()

    @pytest.mark.asyncio
    async def test_audit_logging(self, setup_exception_store):
        """Test that NLQ questions and answers are logged to audit."""
        # Create mock audit logger
        mock_audit_logger = MagicMock(spec=AuditLogger)
        mock_audit_logger.log_decision = MagicMock()
        
        # Create NLQ service with audit logger
        nlq_service = NLQService(audit_logger=mock_audit_logger)
        
        # Answer question
        await nlq_service.answer_question(
            tenant_id="tenant_001",
            exception_id="exc_001",
            question="Why did you block this?",
        )
        
        # Verify audit logging was called
        mock_audit_logger.log_decision.assert_called_once()
        call_args = mock_audit_logger.log_decision.call_args
        assert call_args.kwargs["stage"] == "nlq"
        assert "question" in call_args.kwargs["decision_json"]
        assert "answer" in call_args.kwargs["decision_json"]
        assert call_args.kwargs["tenant_id"] == "tenant_001"

    @pytest.mark.asyncio
    async def test_multi_question_scenarios(self, setup_exception_store):
        """Test multiple questions in sequence."""
        # Create NLQ service
        nlq_service = NLQService(llm_client=None)
        
        questions = [
            "Why did you block this?",
            "What evidence did Triage use?",
            "What alternative actions were possible?",
        ]
        
        results = []
        for question in questions:
            result = await nlq_service.answer_question(
                tenant_id="tenant_001",
                exception_id="exc_001",
                question=question,
            )
            results.append(result)
        
        # Verify all questions were answered
        assert len(results) == 3
        for result in results:
            assert len(result["answer"]) > 0
            assert result["confidence"] > 0.0

    def test_api_endpoint_invalid_request(self, client, auth_headers):
        """Test NLQ API endpoint with invalid request."""
        # Missing question
        request_data = {
            "tenant_id": "tenant_001",
            "exception_id": "exc_001",
        }
        
        response = client.post("/ui/nlq", json=request_data, headers=auth_headers)
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_llm_error_handling(self, setup_exception_store):
        """Test that LLM errors are handled gracefully with fallback."""
        # Create mock LLM client that raises error
        mock_llm_client = AsyncMock(spec=LLMClient)
        from src.llm.provider import LLMProviderError
        mock_llm_client.generate_json = AsyncMock(side_effect=LLMProviderError("LLM unavailable"))
        
        # Create NLQ service with failing LLM client
        nlq_service = NLQService(llm_client=mock_llm_client)
        
        # Answer question (should fallback)
        result = await nlq_service.answer_question(
            tenant_id="tenant_001",
            exception_id="exc_001",
            question="Why did you block this?",
        )
        
        # Verify fallback answer was generated
        assert len(result["answer"]) > 0
        assert result["confidence"] > 0.0
