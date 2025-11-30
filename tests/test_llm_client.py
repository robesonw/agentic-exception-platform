"""
Tests for LLMClient interface and implementations.

Tests Phase 3 LLMClient with:
- generate_json() method with schema_name
- Tenant-aware logging
- Token/cost logging hooks
- Timeout support (stubbed for MVP)
- Mocked provider HTTP calls
"""

from unittest.mock import MagicMock, patch

import pytest

from src.llm.provider import (
    LLMClient,
    LLMClientFactory,
    LLMClientImpl,
    LLMProviderError,
    LLMUsageMetrics,
    OpenAIProvider,
)


class TestLLMClient:
    """Tests for LLMClient interface and implementation."""

    def test_llm_client_interface(self):
        """Test that LLMClient is an abstract base class."""
        # Should not be able to instantiate directly
        with pytest.raises(TypeError):
            LLMClient()

    def test_llm_client_impl_creation(self):
        """Test creating LLMClientImpl with provider."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        assert isinstance(client, LLMClient)
        assert client.provider == provider

    def test_generate_json_with_schema_name(self):
        """Test generate_json() with schema_name parameter."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        # Mock the provider's safe_generate to return valid triage output
        mock_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "severity_confidence": 0.85,
            "classification_confidence": 0.90,
            "root_cause_hypothesis": "Invalid data format detected",
            "matched_rules": ["rule_1", "rule_2"],
            "diagnostic_summary": "Exception classified as DataQualityFailure with HIGH severity",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.87,
            "natural_language_summary": "This exception was classified as a data quality failure with high severity.",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            result = client.generate_json(
                prompt="Classify this exception",
                schema_name="triage",
                tenant_id="test_tenant_001",
            )
            
            assert isinstance(result, dict)
            assert result["predicted_exception_type"] == "DataQualityFailure"
            assert result["predicted_severity"] == "HIGH"
            assert result["confidence"] == 0.87

    def test_generate_json_with_invalid_schema_name(self):
        """Test generate_json() with invalid schema_name."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        with pytest.raises(LLMProviderError, match="Invalid schema name"):
            client.generate_json(
                prompt="Test prompt",
                schema_name="invalid_schema",
                tenant_id="test_tenant_001",
            )

    def test_generate_json_with_tenant_id(self):
        """Test generate_json() with tenant_id for logging."""
        provider = OpenAIProvider()
        token_logger = MagicMock()
        cost_logger = MagicMock()
        
        client = LLMClientImpl(
            provider=provider,
            tenant_id="default_tenant",
            token_logger=token_logger,
            cost_logger=cost_logger,
        )
        
        mock_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "MEDIUM",
            "severity_confidence": 0.75,
            "classification_confidence": 0.80,
            "matched_rules": [],
            "diagnostic_summary": "Test diagnostic",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.77,
            "natural_language_summary": "Test summary",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            result = client.generate_json(
                prompt="Test prompt",
                schema_name="triage",
                tenant_id="custom_tenant",
            )
            
            # Verify token logger was called with custom tenant
            assert token_logger.called
            call_args = token_logger.call_args
            assert call_args[0][0] == "custom_tenant"  # tenant_id
            assert isinstance(call_args[0][1], LLMUsageMetrics)  # metrics

    def test_generate_json_with_timeout(self):
        """Test generate_json() with timeout parameter (stubbed for MVP)."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        mock_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "LOW",
            "severity_confidence": 0.65,
            "classification_confidence": 0.70,
            "matched_rules": [],
            "diagnostic_summary": "Test diagnostic",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.67,
            "natural_language_summary": "Test summary",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            # Timeout is logged but not enforced in MVP
            result = client.generate_json(
                prompt="Test prompt",
                schema_name="triage",
                timeout_s=30,
            )
            
            assert isinstance(result, dict)
            assert result["predicted_exception_type"] == "DataQualityFailure"

    def test_generate_json_validation_failure(self):
        """Test generate_json() with invalid response that fails validation."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        # Mock response missing required fields
        invalid_response = {
            "status": "success",
            "message": "Invalid response missing required fields",
        }
        
        with patch.object(provider, "safe_generate", return_value=invalid_response):
            with pytest.raises(LLMProviderError, match="Response validation failed"):
                client.generate_json(
                    prompt="Test prompt",
                    schema_name="triage",
                )

    def test_get_usage_metrics(self):
        """Test get_usage_metrics() returns metrics from last call."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        # Initially should return None
        assert client.get_usage_metrics() is None
        
        mock_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "severity_confidence": 0.85,
            "classification_confidence": 0.90,
            "matched_rules": [],
            "diagnostic_summary": "Test diagnostic",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.87,
            "natural_language_summary": "Test summary",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            client.generate_json(
                prompt="Test prompt",
                schema_name="triage",
            )
            
            metrics = client.get_usage_metrics()
            assert metrics is not None
            assert isinstance(metrics, LLMUsageMetrics)
            assert metrics.prompt_tokens > 0
            assert metrics.completion_tokens > 0
            assert metrics.total_tokens > 0
            assert metrics.latency_ms is not None

    def test_llm_usage_metrics(self):
        """Test LLMUsageMetrics class."""
        metrics = LLMUsageMetrics(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            estimated_cost=0.002,
            latency_ms=500.0,
        )
        
        assert metrics.prompt_tokens == 100
        assert metrics.completion_tokens == 50
        assert metrics.total_tokens == 150
        assert metrics.estimated_cost == 0.002
        assert metrics.latency_ms == 500.0
        
        # Test to_dict()
        metrics_dict = metrics.to_dict()
        assert metrics_dict["prompt_tokens"] == 100
        assert metrics_dict["completion_tokens"] == 50
        assert metrics_dict["total_tokens"] == 150
        assert metrics_dict["estimated_cost"] == 0.002
        assert metrics_dict["latency_ms"] == 500.0

    def test_llm_client_factory(self):
        """Test LLMClientFactory creates clients correctly."""
        # Test OpenAI client
        client = LLMClientFactory.create_client(
            provider_type="openai",
            api_key="test_key",
            model="gpt-4",
            tenant_id="test_tenant",
        )
        
        assert isinstance(client, LLMClient)
        assert isinstance(client, LLMClientImpl)
        assert client.default_tenant_id == "test_tenant"
        assert isinstance(client.provider, OpenAIProvider)
        assert client.provider.model == "gpt-4"

    def test_llm_client_factory_with_loggers(self):
        """Test LLMClientFactory with token and cost loggers."""
        token_logger = MagicMock()
        cost_logger = MagicMock()
        
        client = LLMClientFactory.create_client(
            provider_type="openai",
            tenant_id="test_tenant",
            token_logger=token_logger,
            cost_logger=cost_logger,
        )
        
        assert client.token_logger == token_logger
        assert client.cost_logger == cost_logger

    def test_llm_client_factory_invalid_provider(self):
        """Test LLMClientFactory with invalid provider type."""
        with pytest.raises(LLMProviderError, match="Unknown provider type"):
            LLMClientFactory.create_client(provider_type="invalid_provider")

    def test_generate_json_policy_schema(self):
        """Test generate_json() with policy schema."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        mock_response = {
            "policy_decision": "APPROVED",
            "applied_guardrails": ["guardrail_1", "guardrail_2"],
            "violated_rules": [],
            "approval_required": False,
            "policy_violation_report": None,
            "tenant_policy_influence": "Tenant policy allowed this action",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.95,
            "natural_language_summary": "Action approved based on guardrails",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            result = client.generate_json(
                prompt="Evaluate this action",
                schema_name="policy",
            )
            
            assert result["policy_decision"] == "APPROVED"
            assert result["approval_required"] is False
            assert result["confidence"] == 0.95

    def test_generate_json_resolution_schema(self):
        """Test generate_json() with resolution schema."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        mock_response = {
            "selected_playbook_id": "playbook_001",
            "playbook_selection_rationale": "This playbook matches the exception type",
            "rejected_playbooks": [],
            "action_rationale": "Retry operation with exponential backoff",
            "tool_execution_plan": [],
            "expected_outcome": "Exception resolved",
            "resolution_status": "RESOLVED",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.88,
            "natural_language_summary": "Selected playbook for resolution",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            result = client.generate_json(
                prompt="Select playbook for resolution",
                schema_name="resolution",
            )
            
            assert result["selected_playbook_id"] == "playbook_001"
            assert result["resolution_status"] == "RESOLVED"
            assert result["confidence"] == 0.88

    def test_generate_json_supervisor_schema(self):
        """Test generate_json() with supervisor schema."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        mock_response = {
            "oversight_decision": "APPROVED_FLOW",
            "intervention_reason": None,
            "anomaly_detected": False,
            "anomaly_description": None,
            "agent_chain_review": {"triage": "OK", "policy": "OK"},
            "recommended_action": None,
            "escalation_reason": None,
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.92,
            "natural_language_summary": "Agent chain approved",
        }
        
        with patch.object(provider, "safe_generate", return_value=mock_response):
            result = client.generate_json(
                prompt="Review agent chain",
                schema_name="supervisor",
            )
            
            assert result["oversight_decision"] == "APPROVED_FLOW"
            assert result["anomaly_detected"] is False
            assert result["confidence"] == 0.92

