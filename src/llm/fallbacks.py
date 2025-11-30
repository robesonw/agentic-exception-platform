"""
LLM fallback strategies, timeouts, and circuit breaker.

Provides:
- LLMFallbackPolicy for configuration
- Circuit breaker pattern (CLOSED → OPEN → HALF_OPEN)
- call_with_fallback() with timeout, retries, and exponential backoff
- llm_or_rules() helper for agent integration
- Comprehensive logging for fallback events

Matches Phase 3 requirements from phase3-mvp-issues.md P3-6.
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from src.llm.provider import LLMClient, LLMProviderError
from src.llm.validation import LLMValidationError

logger = logging.getLogger(__name__)


class CircuitBreakerState(Enum):
    """Circuit breaker states."""

    CLOSED = "CLOSED"  # Normal operation, allowing requests
    OPEN = "OPEN"  # Failing, rejecting requests immediately
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered, allowing limited requests


class FallbackReason(Enum):
    """Reasons for fallback to rule-based logic."""

    TIMEOUT = "timeout"
    VALIDATION_ERROR = "validation_error"
    CIRCUIT_OPEN = "circuit_open"
    PROVIDER_ERROR = "provider_error"
    MAX_RETRIES_EXCEEDED = "max_retries_exceeded"


@dataclass
class LLMFallbackPolicy:
    """
    Configuration for LLM fallback behavior.
    
    Attributes:
        timeout_s: Timeout in seconds per agent (default: 30)
        max_retries: Maximum retry attempts (default: 3)
        backoff_base: Base delay for exponential backoff in seconds (default: 1.0)
        backoff_max: Maximum backoff delay in seconds (default: 10.0)
        circuit_failure_threshold: Number of failures to open circuit (default: 5)
        circuit_time_window_s: Time window for counting failures in seconds (default: 60)
        circuit_half_open_timeout_s: Time before attempting half-open in seconds (default: 30)
        circuit_half_open_max_probes: Maximum probes in half-open state (default: 3)
    """

    timeout_s: float = 30.0
    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_max: float = 10.0
    circuit_failure_threshold: int = 5
    circuit_time_window_s: float = 60.0
    circuit_half_open_timeout_s: float = 30.0
    circuit_half_open_max_probes: int = 3


@dataclass
class CircuitBreakerStateData:
    """In-memory state for a circuit breaker (per agent/per tenant)."""

    state: CircuitBreakerState = CircuitBreakerState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[float] = None
    last_success_time: Optional[float] = None
    opened_at: Optional[float] = None
    half_open_probes: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for LLM calls.
    
    Tracks failures per agent/per tenant and opens circuit when threshold is exceeded.
    Supports CLOSED → OPEN → HALF_OPEN state transitions.
    """

    def __init__(self, policy: LLMFallbackPolicy):
        """
        Initialize circuit breaker.
        
        Args:
            policy: Fallback policy with circuit breaker configuration
        """
        self.policy = policy
        # In-memory state: key = (agent_name, tenant_id), value = CircuitBreakerStateData
        self._states: dict[tuple[str, Optional[str]], CircuitBreakerStateData] = {}

    def _get_state_key(self, agent_name: str, tenant_id: Optional[str]) -> tuple[str, Optional[str]]:
        """Get state key for agent and tenant."""
        return (agent_name, tenant_id)

    def _get_state(self, agent_name: str, tenant_id: Optional[str]) -> CircuitBreakerStateData:
        """Get or create circuit breaker state for agent/tenant."""
        key = self._get_state_key(agent_name, tenant_id)
        if key not in self._states:
            self._states[key] = CircuitBreakerStateData()
        return self._states[key]

    def record_success(self, agent_name: str, tenant_id: Optional[str]) -> None:
        """
        Record a successful LLM call.
        
        Args:
            agent_name: Name of the agent
            tenant_id: Optional tenant ID
        """
        state = self._get_state(agent_name, tenant_id)
        state.last_success_time = time.time()
        state.half_open_probes = 0
        
        if state.state == CircuitBreakerState.HALF_OPEN:
            # Success in half-open: close the circuit
            logger.info(
                f"Circuit breaker CLOSED for {agent_name}/{tenant_id} "
                f"after successful probe"
            )
            state.state = CircuitBreakerState.CLOSED
            state.failure_count = 0
            state.opened_at = None
        elif state.state == CircuitBreakerState.CLOSED:
            # Reset failure count on success
            state.failure_count = 0

    def record_failure(self, agent_name: str, tenant_id: Optional[str]) -> None:
        """
        Record a failed LLM call.
        
        Args:
            agent_name: Name of the agent
            tenant_id: Optional tenant ID
        """
        state = self._get_state(agent_name, tenant_id)
        state.last_failure_time = time.time()
        state.failure_count += 1
        
        if state.state == CircuitBreakerState.HALF_OPEN:
            # Failure in half-open: open the circuit again
            logger.warning(
                f"Circuit breaker OPENED for {agent_name}/{tenant_id} "
                f"after failed probe"
            )
            state.state = CircuitBreakerState.OPEN
            state.opened_at = time.time()
            state.half_open_probes = 0
        elif state.state == CircuitBreakerState.CLOSED:
            # Check if we should open the circuit
            current_time = time.time()
            
            # Reset failure count if outside time window
            if (
                state.last_failure_time
                and (current_time - state.last_failure_time) > self.policy.circuit_time_window_s
            ):
                state.failure_count = 1
            
            # Open circuit if threshold exceeded
            if state.failure_count >= self.policy.circuit_failure_threshold:
                logger.warning(
                    f"Circuit breaker OPENED for {agent_name}/{tenant_id} "
                    f"after {state.failure_count} failures"
                )
                state.state = CircuitBreakerState.OPEN
                state.opened_at = current_time

    def can_attempt(self, agent_name: str, tenant_id: Optional[str]) -> bool:
        """
        Check if a call can be attempted (circuit not open or in half-open with probes available).
        
        Args:
            agent_name: Name of the agent
            tenant_id: Optional tenant ID
            
        Returns:
            True if call can be attempted, False otherwise
        """
        state = self._get_state(agent_name, tenant_id)
        current_time = time.time()
        
        if state.state == CircuitBreakerState.CLOSED:
            return True
        
        if state.state == CircuitBreakerState.OPEN:
            # Check if enough time has passed to try half-open
            if (
                state.opened_at
                and (current_time - state.opened_at) >= self.policy.circuit_half_open_timeout_s
            ):
                logger.info(
                    f"Circuit breaker transitioning to HALF_OPEN for {agent_name}/{tenant_id}"
                )
                state.state = CircuitBreakerState.HALF_OPEN
                state.half_open_probes = 0
                return True
            return False
        
        if state.state == CircuitBreakerState.HALF_OPEN:
            # Allow limited probes in half-open state
            if state.half_open_probes < self.policy.circuit_half_open_max_probes:
                state.half_open_probes += 1
                return True
            return False
        
        return False

    def get_state(self, agent_name: str, tenant_id: Optional[str]) -> CircuitBreakerState:
        """
        Get current circuit breaker state.
        
        Args:
            agent_name: Name of the agent
            tenant_id: Optional tenant ID
            
        Returns:
            Current circuit breaker state
        """
        state = self._get_state(agent_name, tenant_id)
        return state.state


def _exponential_backoff(attempt: int, base: float, max_delay: float) -> float:
    """
    Calculate exponential backoff delay.
    
    Args:
        attempt: Attempt number (0-indexed)
        base: Base delay in seconds
        max_delay: Maximum delay in seconds
        
    Returns:
        Delay in seconds
    """
    delay = base * (2 ** attempt)
    return min(delay, max_delay)


def call_with_fallback(
    llm_client: LLMClient,
    agent_name: str,
    tenant_id: Optional[str],
    schema_name: str,
    prompt: str,
    rule_based_fn: Callable[[], dict[str, Any]],
    policy: Optional[LLMFallbackPolicy] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    audit_logger: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Call LLM with fallback to rule-based logic.
    
    Attempts LLM call with timeout and retries. If all attempts fail or circuit
    breaker is open, falls back to rule-based function.
    
    Args:
        llm_client: LLMClient instance
        agent_name: Name of the agent (for logging and circuit breaker)
        tenant_id: Optional tenant ID
        schema_name: Schema name for LLM output
        prompt: Prompt for LLM
        rule_based_fn: Fallback function that returns dict (rule-based logic)
        policy: Optional fallback policy (uses defaults if not provided)
        circuit_breaker: Optional circuit breaker instance (creates new if not provided)
        audit_logger: Optional AuditLogger for logging fallback events
        
    Returns:
        Dictionary result from LLM or rule-based function
        
    Raises:
        Exception: If both LLM and rule-based fallback fail
    """
    if policy is None:
        policy = LLMFallbackPolicy()
    
    if circuit_breaker is None:
        circuit_breaker = CircuitBreaker(policy)
    
    # Check circuit breaker
    if not circuit_breaker.can_attempt(agent_name, tenant_id):
        logger.warning(
            f"Circuit breaker OPEN for {agent_name}/{tenant_id}, "
            f"using rule-based fallback"
        )
        return _execute_fallback(
            agent_name=agent_name,
            tenant_id=tenant_id,
            reason=FallbackReason.CIRCUIT_OPEN,
            rule_based_fn=rule_based_fn,
            audit_logger=audit_logger,
        )
    
    # Attempt LLM call with retries
    last_error: Optional[Exception] = None
    for attempt in range(policy.max_retries):
        try:
            # Apply exponential backoff between retries
            if attempt > 0:
                backoff_delay = _exponential_backoff(
                    attempt - 1, policy.backoff_base, policy.backoff_max
                )
                logger.debug(
                    f"Retrying LLM call for {agent_name}/{tenant_id} "
                    f"after {backoff_delay:.2f}s backoff (attempt {attempt + 1}/{policy.max_retries})"
                )
                time.sleep(backoff_delay)
            
            # Attempt LLM call with timeout
            # Note: For MVP, timeout is not enforced in LLMClient, but we track elapsed time
            # In production, this would use asyncio.wait_for or similar
            start_time = time.time()
            try:
                result = llm_client.safe_generate(
                    schema_name=schema_name,
                    prompt=prompt,
                    tenant_id=tenant_id,
                    timeout_s=int(policy.timeout_s),
                    agent_name=agent_name,
                    audit_logger=audit_logger,
                )
                
                elapsed = time.time() - start_time
                
                # Check if timeout was exceeded (even if not enforced)
                if elapsed > policy.timeout_s:
                    logger.warning(
                        f"LLM call exceeded timeout for {agent_name}/{tenant_id} "
                        f"({elapsed:.2f}s > {policy.timeout_s}s)"
                    )
                    last_error = TimeoutError(f"Timeout after {elapsed:.2f}s")
                    circuit_breaker.record_failure(agent_name, tenant_id)
                    continue
                
                # Record success
                circuit_breaker.record_success(agent_name, tenant_id)
                
                logger.debug(
                    f"LLM call succeeded for {agent_name}/{tenant_id} "
                    f"in {elapsed:.2f}s"
                )
                
                return result
                
            except TimeoutError as e:
                elapsed = time.time() - start_time
                logger.warning(
                    f"LLM call timed out for {agent_name}/{tenant_id} "
                    f"after {elapsed:.2f}s (attempt {attempt + 1}/{policy.max_retries})"
                )
                last_error = e
                circuit_breaker.record_failure(agent_name, tenant_id)
                
            except LLMValidationError as e:
                logger.warning(
                    f"LLM validation error for {agent_name}/{tenant_id}: {e} "
                    f"(attempt {attempt + 1}/{policy.max_retries})"
                )
                last_error = e
                circuit_breaker.record_failure(agent_name, tenant_id)
                
            except LLMProviderError as e:
                logger.warning(
                    f"LLM provider error for {agent_name}/{tenant_id}: {e} "
                    f"(attempt {attempt + 1}/{policy.max_retries})"
                )
                last_error = e
                circuit_breaker.record_failure(agent_name, tenant_id)
                
            except Exception as e:
                logger.error(
                    f"Unexpected error in LLM call for {agent_name}/{tenant_id}: {e} "
                    f"(attempt {attempt + 1}/{policy.max_retries})"
                )
                last_error = e
                circuit_breaker.record_failure(agent_name, tenant_id)
        
        except Exception as e:
            # Catch any errors during retry logic
            logger.error(f"Error during LLM retry logic: {e}")
            last_error = e
    
    # All retries exhausted, fall back to rule-based
    # Determine the specific error type
    error_type = "unknown"
    if isinstance(last_error, TimeoutError):
        error_type = "timeout"
        reason = FallbackReason.TIMEOUT if policy.max_retries == 1 else FallbackReason.MAX_RETRIES_EXCEEDED
    elif isinstance(last_error, LLMValidationError):
        error_type = "validation_error"
        reason = FallbackReason.VALIDATION_ERROR if policy.max_retries == 1 else FallbackReason.MAX_RETRIES_EXCEEDED
    elif isinstance(last_error, LLMProviderError):
        error_type = "provider_error"
        reason = FallbackReason.PROVIDER_ERROR if policy.max_retries == 1 else FallbackReason.MAX_RETRIES_EXCEEDED
    else:
        reason = FallbackReason.MAX_RETRIES_EXCEEDED
    
    logger.warning(
        f"All LLM attempts failed for {agent_name}/{tenant_id}, "
        f"falling back to rule-based logic (reason: {reason.value}, error_type: {error_type})"
    )
    
    # Store error type in function for metadata (hacky but works for MVP)
    if not hasattr(rule_based_fn, "_last_error_type"):
        rule_based_fn._last_error_type = error_type
    
    return _execute_fallback(
        agent_name=agent_name,
        tenant_id=tenant_id,
        reason=reason,
        rule_based_fn=rule_based_fn,
        audit_logger=audit_logger,
    )


def _execute_fallback(
    agent_name: str,
    tenant_id: Optional[str],
    reason: FallbackReason,
    rule_based_fn: Callable[[], dict[str, Any]],
    audit_logger: Optional[Any],
) -> dict[str, Any]:
    """
    Execute rule-based fallback and log the event.
    
    Args:
        agent_name: Name of the agent
        tenant_id: Optional tenant ID
        reason: Reason for fallback
        rule_based_fn: Rule-based function to execute
        audit_logger: Optional AuditLogger
        
    Returns:
        Result from rule-based function
    """
    try:
        result = rule_based_fn()
        
        # Add metadata to indicate fallback was used
        if isinstance(result, dict):
            result["_metadata"] = result.get("_metadata", {})
            result["_metadata"]["llm_fallback"] = True
            result["_metadata"]["fallback_reason"] = reason.value
            result["_metadata"]["fallback_path"] = "rule_based"
            # Store underlying error type if available (for debugging)
            if hasattr(rule_based_fn, "_last_error_type"):
                result["_metadata"]["underlying_error_type"] = rule_based_fn._last_error_type
        
        # Log fallback event
        if audit_logger:
            try:
                audit_logger._write_log_entry(
                    event_type="llm_fallback",
                    data={
                        "agent_name": agent_name,
                        "reason": reason.value,
                        "path": "rule_based",
                        "tenant_id": tenant_id,
                    },
                    tenant_id=tenant_id,
                )
            except Exception as e:
                logger.warning(f"Failed to log fallback event to audit: {e}")
        
        logger.info(
            f"Rule-based fallback executed for {agent_name}/{tenant_id} "
            f"(reason: {reason.value})"
        )
        
        return result
        
    except Exception as e:
        logger.error(
            f"Rule-based fallback failed for {agent_name}/{tenant_id}: {e}"
        )
        raise


def llm_or_rules(
    llm_client: LLMClient,
    agent_name: str,
    tenant_id: Optional[str],
    schema_name: str,
    prompt: str,
    rule_based_fn: Callable[[], dict[str, Any]],
    policy: Optional[LLMFallbackPolicy] = None,
    circuit_breaker: Optional[CircuitBreaker] = None,
    audit_logger: Optional[Any] = None,
) -> dict[str, Any]:
    """
    Helper function for agents to call LLM with automatic fallback to rules.
    
    This is the main integration point for agents. It handles all fallback logic
    internally and returns either LLM result or rule-based result.
    
    Args:
        llm_client: LLMClient instance
        agent_name: Name of the agent (e.g., "TriageAgent", "PolicyAgent")
        tenant_id: Optional tenant ID
        schema_name: Schema name for LLM output (e.g., "triage", "policy")
        prompt: Prompt for LLM
        rule_based_fn: Fallback function that returns dict (rule-based logic)
        policy: Optional fallback policy (uses defaults if not provided)
        circuit_breaker: Optional circuit breaker instance (creates new if not provided)
        audit_logger: Optional AuditLogger for logging fallback events
        
    Returns:
        Dictionary result from LLM or rule-based function (with _metadata indicating path)
        
    Example:
        ```python
        result = llm_or_rules(
            llm_client=llm_client,
            agent_name="TriageAgent",
            tenant_id="tenant_001",
            schema_name="triage",
            prompt=prompt,
            rule_based_fn=lambda: self._classify_with_rules(exception),
        )
        ```
    """
    return call_with_fallback(
        llm_client=llm_client,
        agent_name=agent_name,
        tenant_id=tenant_id,
        schema_name=schema_name,
        prompt=prompt,
        rule_based_fn=rule_based_fn,
        policy=policy,
        circuit_breaker=circuit_breaker,
        audit_logger=audit_logger,
    )

