"""
Tests for Copilot REST API endpoints.

Tests POST /api/copilot/chat endpoint.
"""

import os
import pytest
from fastapi.testclient import TestClient

from src.api.auth import Role, get_api_key_auth
from src.api.main import app
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import get_exception_store

client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch):
    """Set up test environment."""
    # Ensure DummyLLMClient is used for all tests
    monkeypatch.setenv("LLM_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_MODEL", "dummy-model")
    
    # Set up API keys
    auth = get_api_key_auth()
    auth.register_api_key(DEFAULT_API_KEY, "TENANT_001", Role.ADMIN)
    
    # Clear exception store
    store = get_exception_store()
    store.clear_all()
    
    yield
    
    # Cleanup
    store.clear_all()


class TestCopilotChatEndpoint:
    """Tests for POST /api/copilot/chat endpoint."""

    def test_valid_request(self):
        """Test valid copilot chat request."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "summarize today's exceptions",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
            },
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        
        # Check response structure matches CopilotResponse
        assert "answer" in data, "Response should have answer field"
        assert "answer_type" in data, "Response should have answer_type field"
        assert "citations" in data, "Response should have citations field"
        assert "raw_llm_trace_id" in data, "Response should have raw_llm_trace_id field"
        
        # Check answer is not empty
        assert data["answer"] is not None, "Answer should not be None"
        assert data["answer"] != "", "Answer should not be empty"
        
        # Check answer_type is valid
        assert data["answer_type"] in ["EXPLANATION", "SUMMARY", "POLICY_HINT", "UNKNOWN"], \
            f"Invalid answer_type: {data['answer_type']}"
        
        # Check citations is a list
        assert isinstance(data["citations"], list), "Citations should be a list"

    def test_invalid_missing_tenant_id(self):
        """Test request with missing tenant_id."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "summarize today's exceptions",
                "domain": "Capital Markets",
                # tenant_id is missing
            },
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    def test_invalid_empty_tenant_id(self):
        """Test request with empty tenant_id."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "summarize today's exceptions",
                "tenant_id": "",
                "domain": "Capital Markets",
            },
        )
        
        # Empty tenant_id triggers tenant isolation check first (403) or validation (400)
        assert response.status_code in [400, 403], \
            f"Expected 400 or 403, got {response.status_code}: {response.text}"

    def test_invalid_empty_message(self):
        """Test request with empty message."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
            },
        )
        
        assert response.status_code == 400, f"Expected 400, got {response.status_code}: {response.text}"

    def test_invalid_missing_domain(self):
        """Test request with missing domain."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "summarize today's exceptions",
                "tenant_id": "TENANT_001",
                # domain is missing
            },
        )
        
        assert response.status_code == 422, f"Expected 422, got {response.status_code}: {response.text}"

    def test_explanation_query_with_exception_id(self):
        """Test explanation query with exception ID."""
        # Create a test exception first
        store = get_exception_store()
        exception = ExceptionRecord(
            exception_id="EX-12345",
            tenant_id="TENANT_001",
            source_system="ERP",
            exception_type="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp="2024-01-15T10:30:00Z",
            raw_payload={"orderId": "ORD-001"},
            normalized_context={"domain": "Capital Markets"},
            resolution_status=ResolutionStatus.OPEN,
        )
        store.store_exception(exception, {"status": "COMPLETED", "stages": {}})
        
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "explain EX-12345",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
            },
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["answer_type"] == "EXPLANATION", f"Expected EXPLANATION, got {data['answer_type']}"
        assert len(data["citations"]) > 0, "Should have citations for explanation query"

    def test_policy_query(self):
        """Test policy query."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "What is the policy for settlement failures?",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
            },
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["answer_type"] == "POLICY_HINT", f"Expected POLICY_HINT, got {data['answer_type']}"

    def test_summary_query(self):
        """Test summary query."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "summarize today's exceptions",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
            },
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["answer_type"] == "SUMMARY", f"Expected SUMMARY, got {data['answer_type']}"

    def test_unknown_query(self):
        """Test unknown query."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "Hello, how are you?",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
            },
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["answer_type"] == "UNKNOWN", f"Expected UNKNOWN, got {data['answer_type']}"

    def test_request_with_context(self):
        """Test request with optional context."""
        response = client.post(
            "/api/copilot/chat",
            headers={"X-API-KEY": DEFAULT_API_KEY},
            json={
                "message": "summarize today's exceptions",
                "tenant_id": "TENANT_001",
                "domain": "Capital Markets",
                "context": {
                    "current_page": "exceptions",
                    "selected_exception_id": "EX-12345",
                },
            },
        )
        
        assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"
        data = response.json()
        assert "answer" in data, "Response should have answer field"

