"""
Tests for LLM fallback strategies, timeouts, and circuit breaker.

Tests Phase 3 fallback features:
- Timeout triggers fallback
- Repeated failures open circuit breaker
- Half-open probes work as expected
- Rule-based fallback used when breaker is open
"""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.llm.fallbacks import (
    CircuitBreaker,
    CircuitBreakerState,
    FallbackReason,
    LLMFallbackPolicy,
    call_with_fallback,
    llm_or_rules,
)
from src.llm.provider import LLMClientImpl, LLMProviderError, OpenAIProvider
from src.llm.validation import LLMValidationError


class TestLLMFallbackPolicy:
    """Tests for LLMFallbackPolicy configuration."""

    def test_default_policy(self):
        """Test default policy values."""
        policy = LLMFallbackPolicy()
        
        assert policy.timeout_s == 30.0
        assert policy.max_retries == 3
        assert policy.backoff_base == 1.0
        assert policy.backoff_max == 10.0
        assert policy.circuit_failure_threshold == 5
        assert policy.circuit_time_window_s == 60.0
        assert policy.circuit_half_open_timeout_s == 30.0
        assert policy.circuit_half_open_max_probes == 3

    def test_custom_policy(self):
        """Test custom policy values."""
        policy = LLMFallbackPolicy(
            timeout_s=60.0,
            max_retries=5,
            backoff_base=2.0,
            backoff_max=20.0,
            circuit_failure_threshold=10,
        )
        
        assert policy.timeout_s == 60.0
        assert policy.max_retries == 5
        assert policy.backoff_base == 2.0
        assert policy.backoff_max == 20.0
        assert policy.circuit_failure_threshold == 10


class TestCircuitBreaker:
    """Tests for CircuitBreaker implementation."""

    def test_initial_state_closed(self):
        """Test circuit breaker starts in CLOSED state."""
        policy = LLMFallbackPolicy()
        breaker = CircuitBreaker(policy)
        
        state = breaker.get_state("TestAgent", "tenant_001")
        assert state == CircuitBreakerState.CLOSED

    def test_can_attempt_when_closed(self):
        """Test can_attempt() returns True when circuit is CLOSED."""
        policy = LLMFallbackPolicy()
        breaker = CircuitBreaker(policy)
        
        assert breaker.can_attempt("TestAgent", "tenant_001") is True

    def test_record_failure_increments_count(self):
        """Test record_failure() increments failure count."""
        policy = LLMFallbackPolicy(circuit_failure_threshold=3)
        breaker = CircuitBreaker(policy)
        
        breaker.record_failure("TestAgent", "tenant_001")
        breaker.record_failure("TestAgent", "tenant_001")
        
        # Should still be CLOSED (threshold is 3)
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.CLOSED
        assert breaker.can_attempt("TestAgent", "tenant_001") is True

    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold is exceeded."""
        policy = LLMFallbackPolicy(circuit_failure_threshold=3)
        breaker = CircuitBreaker(policy)
        
        # Record failures up to threshold
        breaker.record_failure("TestAgent", "tenant_001")
        breaker.record_failure("TestAgent", "tenant_001")
        breaker.record_failure("TestAgent", "tenant_001")
        
        # Should now be OPEN
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.OPEN
        assert breaker.can_attempt("TestAgent", "tenant_001") is False

    def test_circuit_cannot_attempt_when_open(self):
        """Test can_attempt() returns False when circuit is OPEN."""
        policy = LLMFallbackPolicy(circuit_failure_threshold=1)
        breaker = CircuitBreaker(policy)
        
        breaker.record_failure("TestAgent", "tenant_001")
        
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.OPEN
        assert breaker.can_attempt("TestAgent", "tenant_001") is False

    def test_circuit_transitions_to_half_open_after_timeout(self):
        """Test circuit transitions to HALF_OPEN after timeout."""
        policy = LLMFallbackPolicy(
            circuit_failure_threshold=1,
            circuit_half_open_timeout_s=0.1,  # Short timeout for testing
        )
        breaker = CircuitBreaker(policy)
        
        # Open the circuit
        breaker.record_failure("TestAgent", "tenant_001")
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.OPEN
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Should transition to HALF_OPEN when can_attempt is called
        assert breaker.can_attempt("TestAgent", "tenant_001") is True
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.HALF_OPEN

    def test_half_open_allows_limited_probes(self):
        """Test half-open state allows limited probes."""
        policy = LLMFallbackPolicy(
            circuit_failure_threshold=1,
            circuit_half_open_timeout_s=0.1,
            circuit_half_open_max_probes=2,
        )
        breaker = CircuitBreaker(policy)
        
        # Open and transition to half-open
        breaker.record_failure("TestAgent", "tenant_001")
        time.sleep(0.15)
        breaker.can_attempt("TestAgent", "tenant_001")  # Transition to half-open
        
        # First probe allowed
        assert breaker.can_attempt("TestAgent", "tenant_001") is True
        
        # Second probe allowed
        assert breaker.can_attempt("TestAgent", "tenant_001") is True
        
        # Third probe should be rejected (max_probes = 2)
        assert breaker.can_attempt("TestAgent", "tenant_001") is False

    def test_success_in_half_open_closes_circuit(self):
        """Test success in half-open state closes the circuit."""
        policy = LLMFallbackPolicy(
            circuit_failure_threshold=1,
            circuit_half_open_timeout_s=0.1,
        )
        breaker = CircuitBreaker(policy)
        
        # Open and transition to half-open
        breaker.record_failure("TestAgent", "tenant_001")
        time.sleep(0.15)
        breaker.can_attempt("TestAgent", "tenant_001")  # Transition to half-open
        
        # Record success
        breaker.record_success("TestAgent", "tenant_001")
        
        # Should be CLOSED
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.CLOSED
        assert breaker.can_attempt("TestAgent", "tenant_001") is True

    def test_failure_in_half_open_reopens_circuit(self):
        """Test failure in half-open state reopens the circuit."""
        policy = LLMFallbackPolicy(
            circuit_failure_threshold=1,
            circuit_half_open_timeout_s=0.1,
        )
        breaker = CircuitBreaker(policy)
        
        # Open and transition to half-open
        breaker.record_failure("TestAgent", "tenant_001")
        time.sleep(0.15)
        breaker.can_attempt("TestAgent", "tenant_001")  # Transition to half-open
        
        # Record failure in half-open
        breaker.record_failure("TestAgent", "tenant_001")
        
        # Should be OPEN again
        assert breaker.get_state("TestAgent", "tenant_001") == CircuitBreakerState.OPEN
        assert breaker.can_attempt("TestAgent", "tenant_001") is False

    def test_per_agent_tenant_isolation(self):
        """Test circuit breaker state is isolated per agent/tenant."""
        policy = LLMFallbackPolicy(circuit_failure_threshold=1)
        breaker = CircuitBreaker(policy)
        
        # Open circuit for one agent/tenant
        breaker.record_failure("Agent1", "tenant_001")
        assert breaker.get_state("Agent1", "tenant_001") == CircuitBreakerState.OPEN
        
        # Other agent/tenant should still be CLOSED
        assert breaker.get_state("Agent2", "tenant_001") == CircuitBreakerState.CLOSED
        assert breaker.get_state("Agent1", "tenant_002") == CircuitBreakerState.CLOSED


class TestCallWithFallback:
    """Tests for call_with_fallback() function."""

    def test_successful_llm_call(self):
        """Test successful LLM call without fallback."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        mock_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "severity_confidence": 0.85,
            "classification_confidence": 0.90,
            "matched_rules": [],
            "diagnostic_summary": "Test",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.87,
            "natural_language_summary": "Test summary",
        }
        
        rule_based_fn = MagicMock(return_value={"fallback": "result"})
        
        with patch.object(client, "safe_generate", return_value=mock_response):
            result = call_with_fallback(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
            )
            
            assert result == mock_response
            assert "_metadata" not in result
            rule_based_fn.assert_not_called()

    def test_fallback_on_validation_error(self):
        """Test fallback triggered on validation error."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        rule_based_result = {"fallback": "result", "reason": "validation_failed"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        validation_error = LLMValidationError(
            message="Validation failed",
            schema_name="triage",
            error_type="SCHEMA_VALIDATION",
        )
        
        with patch.object(client, "safe_generate", side_effect=validation_error):
            result = call_with_fallback(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
                policy=LLMFallbackPolicy(max_retries=1),  # Single retry for faster test
            )
            
            assert result == rule_based_result
            assert result["_metadata"]["llm_fallback"] is True
            assert result["_metadata"]["fallback_reason"] == FallbackReason.VALIDATION_ERROR.value
            assert result["_metadata"]["fallback_path"] == "rule_based"
            rule_based_fn.assert_called_once()

    def test_fallback_on_provider_error(self):
        """Test fallback triggered on provider error."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        rule_based_result = {"fallback": "result"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        provider_error = LLMProviderError("Provider error")
        
        with patch.object(client, "safe_generate", side_effect=provider_error):
            result = call_with_fallback(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
                policy=LLMFallbackPolicy(max_retries=1),
            )
            
            assert result == rule_based_result
            assert result["_metadata"]["fallback_reason"] == FallbackReason.PROVIDER_ERROR.value
            rule_based_fn.assert_called_once()

    def test_fallback_on_circuit_open(self):
        """Test fallback when circuit breaker is open."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        policy = LLMFallbackPolicy(circuit_failure_threshold=1)
        breaker = CircuitBreaker(policy)
        
        # Open the circuit
        breaker.record_failure("TestAgent", "tenant_001")
        
        rule_based_result = {"fallback": "result"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        result = call_with_fallback(
            llm_client=client,
            agent_name="TestAgent",
            tenant_id="tenant_001",
            schema_name="triage",
            prompt="Test prompt",
            rule_based_fn=rule_based_fn,
            policy=policy,
            circuit_breaker=breaker,
        )
        
        assert result == rule_based_result
        assert result["_metadata"]["fallback_reason"] == FallbackReason.CIRCUIT_OPEN.value
        rule_based_fn.assert_called_once()
        # LLM should not be called when circuit is open
        assert not hasattr(client, "safe_generate") or not hasattr(
            client.safe_generate, "call_count"
        )

    def test_retry_with_exponential_backoff(self):
        """Test retry logic with exponential backoff."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        policy = LLMFallbackPolicy(
            max_retries=3,
            backoff_base=0.1,  # Short backoff for testing
            backoff_max=1.0,
        )
        
        rule_based_result = {"fallback": "result"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        # First two calls fail, third succeeds
        call_count = 0
        
        def mock_safe_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise LLMProviderError(f"Error {call_count}")
            return {"success": True}
        
        with patch.object(client, "safe_generate", side_effect=mock_safe_generate):
            start_time = time.time()
            result = call_with_fallback(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
                policy=policy,
            )
            elapsed = time.time() - start_time
            
            # Should have succeeded on third attempt
            assert result == {"success": True}
            assert call_count == 3
            # Should have had backoff delays (roughly 0.1s and 0.2s)
            assert elapsed >= 0.2  # At least some backoff time
            rule_based_fn.assert_not_called()

    def test_max_retries_exceeded_triggers_fallback(self):
        """Test fallback when max retries exceeded."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        policy = LLMFallbackPolicy(max_retries=2, backoff_base=0.01)
        
        rule_based_result = {"fallback": "result"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        with patch.object(client, "safe_generate", side_effect=LLMProviderError("Error")):
            result = call_with_fallback(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
                policy=policy,
            )
            
            assert result == rule_based_result
            assert result["_metadata"]["fallback_reason"] == FallbackReason.MAX_RETRIES_EXCEEDED.value
            rule_based_fn.assert_called_once()

    def test_audit_logging_on_fallback(self):
        """Test audit logging when fallback is used."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        audit_logger = MagicMock()
        rule_based_result = {"fallback": "result"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        with patch.object(client, "safe_generate", side_effect=LLMProviderError("Error")):
            call_with_fallback(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
                policy=LLMFallbackPolicy(max_retries=1),
                audit_logger=audit_logger,
            )
            
            # Verify audit logger was called
            assert audit_logger._write_log_entry.called
            call_args = audit_logger._write_log_entry.call_args
            assert call_args[1]["event_type"] == "llm_fallback"
            assert call_args[1]["data"]["agent_name"] == "TestAgent"
            assert call_args[1]["data"]["reason"] in [r.value for r in FallbackReason]
            assert call_args[1]["data"]["path"] == "rule_based"


class TestLLMOrRules:
    """Tests for llm_or_rules() helper function."""

    def test_llm_or_rules_success(self):
        """Test llm_or_rules() with successful LLM call."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        mock_response = {
            "predicted_exception_type": "DataQualityFailure",
            "predicted_severity": "HIGH",
            "severity_confidence": 0.85,
            "classification_confidence": 0.90,
            "matched_rules": [],
            "diagnostic_summary": "Test",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.87,
            "natural_language_summary": "Test summary",
        }
        
        rule_based_fn = MagicMock(return_value={"fallback": "result"})
        
        with patch.object(client, "safe_generate", return_value=mock_response):
            result = llm_or_rules(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
            )
            
            assert result == mock_response
            rule_based_fn.assert_not_called()

    def test_llm_or_rules_fallback(self):
        """Test llm_or_rules() falls back to rules on error."""
        provider = OpenAIProvider()
        client = LLMClientImpl(provider=provider)
        
        rule_based_result = {"fallback": "result"}
        rule_based_fn = MagicMock(return_value=rule_based_result)
        
        with patch.object(client, "safe_generate", side_effect=LLMProviderError("Error")):
            result = llm_or_rules(
                llm_client=client,
                agent_name="TestAgent",
                tenant_id="tenant_001",
                schema_name="triage",
                prompt="Test prompt",
                rule_based_fn=rule_based_fn,
                policy=LLMFallbackPolicy(max_retries=1),
            )
            
            assert result == rule_based_result
            assert result["_metadata"]["llm_fallback"] is True
            rule_based_fn.assert_called_once()

