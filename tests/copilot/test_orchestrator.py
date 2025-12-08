"""
Tests for Copilot Orchestrator.

Tests intent classification and orchestrator processing.
"""

import os
import pytest

from src.copilot.models import CopilotRequest
from src.copilot.orchestrator import CopilotOrchestrator, classify_intent
from src.llm.dummy_llm import DummyLLMClient


@pytest.fixture(autouse=True)
def ensure_dummy_llm(monkeypatch):
    """Ensure DummyLLMClient is used for all tests."""
    monkeypatch.setenv("LLM_PROVIDER", "dummy")
    monkeypatch.setenv("LLM_MODEL", "dummy-model")


class TestClassifyIntent:
    """Tests for classify_intent() function."""

    def test_summary_queries(self):
        """Test summary intent classification."""
        test_cases = [
            "summarize today's exceptions",
            "Show me today's exceptions",
            "What are the exceptions today?",
            "Give me a summary",
            "List exceptions",
        ]
        
        for message in test_cases:
            intent_type, exception_ids = classify_intent(message)
            assert intent_type == "SUMMARY", f"Expected SUMMARY for '{message}', got {intent_type}"
            assert isinstance(exception_ids, list), "exception_ids should be a list"

    def test_policy_queries(self):
        """Test policy intent classification."""
        test_cases = [
            "What is the policy for settlement failures?",
            "Show me the rules",
            "Explain the domain pack",
            "What are the guardrails?",
            "Tell me about the policy",
        ]
        
        for message in test_cases:
            intent_type, exception_ids = classify_intent(message)
            assert intent_type == "POLICY_HINT", f"Expected POLICY_HINT for '{message}', got {intent_type}"
            assert isinstance(exception_ids, list), "exception_ids should be a list"

    def test_explanation_queries(self):
        """Test explanation intent classification."""
        test_cases = [
            ("explain EX-12345", ["EX-12345"]),
            ("Why did EX-001 fail?", ["EX-001"]),
            ("What happened with EX-999?", ["EX-999"]),
            ("Explain EX-12345 and EX-67890", ["EX-12345", "EX-67890"]),
        ]
        
        for message, expected_ids in test_cases:
            intent_type, exception_ids = classify_intent(message)
            assert intent_type == "EXPLANATION", f"Expected EXPLANATION for '{message}', got {intent_type}"
            assert set(exception_ids) == set(expected_ids), \
                f"Expected exception IDs {expected_ids}, got {exception_ids}"

    def test_unknown_queries(self):
        """Test unknown intent classification."""
        test_cases = [
            "Hello, how are you?",
            "What is the weather?",
            "Random question",
            "",
        ]
        
        for message in test_cases:
            intent_type, exception_ids = classify_intent(message)
            assert intent_type == "UNKNOWN", f"Expected UNKNOWN for '{message}', got {intent_type}"
            assert exception_ids == [], "Unknown queries should have no exception IDs"


class TestCopilotOrchestrator:
    """Tests for CopilotOrchestrator class."""

    @pytest.fixture
    def orchestrator(self):
        """Create orchestrator with DummyLLMClient."""
        llm = DummyLLMClient()
        return CopilotOrchestrator(llm=llm)

    @pytest.mark.asyncio
    async def test_process_summary_query(self, orchestrator):
        """Test processing a summary query."""
        request = CopilotRequest(
            message="summarize today's exceptions",
            tenant_id="TENANT_001",
            domain="Capital Markets",
        )
        
        response = await orchestrator.process(request)
        
        assert response.answer is not None, "Answer should not be None"
        assert response.answer != "", "Answer should not be empty"
        assert response.answer_type == "SUMMARY", f"Expected SUMMARY, got {response.answer_type}"
        assert isinstance(response.citations, list), "Citations should be a list"

    @pytest.mark.asyncio
    async def test_process_policy_query(self, orchestrator):
        """Test processing a policy query."""
        request = CopilotRequest(
            message="What is the policy for settlement failures?",
            tenant_id="TENANT_001",
            domain="Capital Markets",
        )
        
        response = await orchestrator.process(request)
        
        assert response.answer is not None, "Answer should not be None"
        assert response.answer != "", "Answer should not be empty"
        assert response.answer_type == "POLICY_HINT", f"Expected POLICY_HINT, got {response.answer_type}"
        assert isinstance(response.citations, list), "Citations should be a list"

    @pytest.mark.asyncio
    async def test_process_explanation_query(self, orchestrator):
        """Test processing an explanation query."""
        request = CopilotRequest(
            message="explain EX-12345",
            tenant_id="TENANT_001",
            domain="Capital Markets",
        )
        
        response = await orchestrator.process(request)
        
        assert response.answer is not None, "Answer should not be None"
        assert response.answer != "", "Answer should not be empty"
        assert response.answer_type == "EXPLANATION", f"Expected EXPLANATION, got {response.answer_type}"
        assert isinstance(response.citations, list), "Citations should be a list"

    @pytest.mark.asyncio
    async def test_process_unknown_query(self, orchestrator):
        """Test processing an unknown query."""
        request = CopilotRequest(
            message="Hello, how are you?",
            tenant_id="TENANT_001",
            domain="Capital Markets",
        )
        
        response = await orchestrator.process(request)
        
        assert response.answer is not None, "Answer should not be None"
        assert response.answer != "", "Answer should not be empty"
        assert response.answer_type == "UNKNOWN", f"Expected UNKNOWN, got {response.answer_type}"
        assert isinstance(response.citations, list), "Citations should be a list"

    @pytest.mark.asyncio
    async def test_response_structure(self, orchestrator):
        """Test that response has correct structure."""
        request = CopilotRequest(
            message="summarize today's exceptions",
            tenant_id="TENANT_001",
            domain="Capital Markets",
        )
        
        response = await orchestrator.process(request)
        
        # Check all required fields are present
        assert hasattr(response, "answer"), "Response should have answer field"
        assert hasattr(response, "answer_type"), "Response should have answer_type field"
        assert hasattr(response, "citations"), "Response should have citations field"
        assert hasattr(response, "raw_llm_trace_id"), "Response should have raw_llm_trace_id field"
        
        # Check types
        assert isinstance(response.answer, str), "Answer should be a string"
        assert isinstance(response.answer_type, str), "Answer type should be a string"
        assert isinstance(response.citations, list), "Citations should be a list"
        assert response.raw_llm_trace_id is None or isinstance(response.raw_llm_trace_id, str), \
            "raw_llm_trace_id should be None or string"

