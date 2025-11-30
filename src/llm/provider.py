"""
LLM Provider interface and implementations for Phase 2 and Phase 3.

Provides:
- LLMProvider interface (Phase 2)
- LLMClient interface (Phase 3) with generate_json() and schema support
- GrokProvider/OpenAIProvider stubs (config-driven)
- safe_generate(prompt, schema) enforcing JSON-only output
- generate_json(prompt, schema_name, timeout_s) with tenant-aware support

Matches specification from:
- phase2-mvp-issues.md Issue 27
- phase3-mvp-issues.md P3-5, P3-1..P3-4
"""

import json
import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Callable, Optional

from src.llm.schemas import get_extended_schema_model, get_schema_model
from src.llm.validation import LLMValidationError, sanitize_llm_output, validate_llm_output

# Import SafetyViolation for type checking (avoid circular import)
try:
    from src.safety.rules import SafetyViolation
except ImportError:
    SafetyViolation = Exception  # Fallback for type hints

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Raised when LLM provider operations fail."""

    pass


class LLMProvider(ABC):
    """
    Abstract interface for LLM providers.
    
    Ensures JSON-only output with schema validation.
    """

    @abstractmethod
    def safe_generate(
        self, prompt: str, schema: Optional[dict[str, Any]] = None, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Generate JSON response from LLM with schema validation.
        
        Args:
            prompt: Prompt text for LLM
            schema: Optional JSON schema to validate output against
            max_retries: Maximum retry attempts if output is invalid
            
        Returns:
            Dictionary parsed from JSON response
            
        Raises:
            LLMProviderError: If generation fails or output is invalid
        """
        pass


class OpenAIProvider(LLMProvider):
    """
    OpenAI provider stub (config-driven).
    
    For MVP, returns mock responses. In production, would call OpenAI API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (optional for MVP)
            model: Model name (default: gpt-4)
            temperature: Temperature for generation (default: 0.3)
            max_tokens: Maximum tokens in response (default: 2000)
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def safe_generate(
        self, prompt: str, schema: Optional[dict[str, Any]] = None, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Generate JSON response from OpenAI with schema validation.
        
        Args:
            prompt: Prompt text
            schema: Optional JSON schema
            max_retries: Maximum retry attempts
            
        Returns:
            Dictionary parsed from JSON response
            
        Raises:
            LLMProviderError: If generation fails
        """
        # For MVP, return mock response
        # In production, would call OpenAI API with JSON mode
        logger.debug(f"OpenAIProvider.safe_generate called (model: {self.model})")
        
        # Mock response for MVP
        mock_response = {
            "status": "success",
            "message": "Mock OpenAI response - replace with actual API call in production",
        }
        
        # Validate against schema if provided
        if schema:
            try:
                self._validate_schema(mock_response, schema)
            except Exception as e:
                if max_retries > 0:
                    logger.warning(f"Schema validation failed, retrying: {e}")
                    return self.safe_generate(prompt, schema, max_retries - 1)
                raise LLMProviderError(f"Schema validation failed after retries: {e}")
        
        return mock_response

    def _validate_schema(self, data: dict[str, Any], schema: dict[str, Any]) -> None:
        """
        Validate data against JSON schema.
        
        Args:
            data: Data to validate
            schema: JSON schema
            
        Raises:
            ValueError: If validation fails
        """
        # Simple schema validation for MVP
        # In production, use jsonschema library
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")


class GrokProvider(LLMProvider):
    """
    Grok provider stub (config-driven).
    
    For MVP, returns mock responses. In production, would call Grok API.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "grok-beta",
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ):
        """
        Initialize Grok provider.
        
        Args:
            api_key: Grok API key (optional for MVP)
            model: Model name (default: grok-beta)
            temperature: Temperature for generation (default: 0.3)
            max_tokens: Maximum tokens in response (default: 2000)
        """
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def safe_generate(
        self, prompt: str, schema: Optional[dict[str, Any]] = None, max_retries: int = 3
    ) -> dict[str, Any]:
        """
        Generate JSON response from Grok with schema validation.
        
        Args:
            prompt: Prompt text
            schema: Optional JSON schema
            max_retries: Maximum retry attempts
            
        Returns:
            Dictionary parsed from JSON response
            
        Raises:
            LLMProviderError: If generation fails
        """
        # For MVP, return mock response
        # In production, would call Grok API with JSON mode
        logger.debug(f"GrokProvider.safe_generate called (model: {self.model})")
        
        # Mock response for MVP
        mock_response = {
            "status": "success",
            "message": "Mock Grok response - replace with actual API call in production",
        }
        
        # Validate against schema if provided
        if schema:
            try:
                self._validate_schema(mock_response, schema)
            except Exception as e:
                if max_retries > 0:
                    logger.warning(f"Schema validation failed, retrying: {e}")
                    return self.safe_generate(prompt, schema, max_retries - 1)
                raise LLMProviderError(f"Schema validation failed after retries: {e}")
        
        return mock_response

    def _validate_schema(self, data: dict[str, Any], schema: dict[str, Any]) -> None:
        """
        Validate data against JSON schema.
        
        Args:
            data: Data to validate
            schema: JSON schema
            
        Raises:
            ValueError: If validation fails
        """
        # Simple schema validation for MVP
        # In production, use jsonschema library
        required_fields = schema.get("required", [])
        for field in required_fields:
            if field not in data:
                raise ValueError(f"Missing required field: {field}")


class LLMProviderFactory:
    """
    Factory for creating LLM providers based on configuration.
    """

    @staticmethod
    def create_provider(
        provider_type: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs,
    ) -> LLMProvider:
        """
        Create LLM provider instance.
        
        Args:
            provider_type: Provider type ("openai" or "grok")
            api_key: API key for provider
            model: Model name (optional)
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMProvider instance
            
        Raises:
            LLMProviderError: If provider type is unknown
        """
        if provider_type.lower() == "openai":
            return OpenAIProvider(
                api_key=api_key,
                model=model or "gpt-4",
                **kwargs,
            )
        elif provider_type.lower() == "grok":
            return GrokProvider(
                api_key=api_key,
                model=model or "grok-beta",
                **kwargs,
            )
        else:
            raise LLMProviderError(f"Unknown provider type: {provider_type}")


# Phase 3: LLMClient interface with schema support and tenant awareness


class LLMUsageMetrics:
    """Metrics for LLM usage (tokens, cost, etc.)."""

    def __init__(
        self,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
        estimated_cost: Optional[float] = None,
        latency_ms: Optional[float] = None,
    ):
        """
        Initialize LLM usage metrics.
        
        Args:
            prompt_tokens: Number of tokens in prompt
            completion_tokens: Number of tokens in completion
            total_tokens: Total tokens used
            estimated_cost: Estimated cost in USD (if available)
            latency_ms: Request latency in milliseconds
        """
        self.prompt_tokens = prompt_tokens
        self.completion_tokens = completion_tokens
        self.total_tokens = total_tokens
        self.estimated_cost = estimated_cost
        self.latency_ms = latency_ms

    def to_dict(self) -> dict[str, Any]:
        """Convert metrics to dictionary."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": self.estimated_cost,
            "latency_ms": self.latency_ms,
        }


class LLMClient(ABC):
    """
    Phase 3 LLMClient interface with schema support and tenant awareness.
    
    Provides generate_json() method that:
    - Accepts schema_name to identify which schema to use
    - Supports timeout configuration
    - Is tenant-aware (accepts tenant_id for future per-tenant model/tuning)
    - Logs token/cost usage via hooks
    - Always requests JSON-only output
    """

    @abstractmethod
    def generate_json(
        self,
        prompt: str,
        schema_name: str,
        tenant_id: Optional[str] = None,
        timeout_s: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Generate JSON response from LLM using named schema.
        
        Args:
            prompt: Prompt text for LLM
            schema_name: Name of the schema to use (e.g., "triage", "policy")
            tenant_id: Optional tenant ID for per-tenant configuration/logging
            timeout_s: Optional timeout in seconds
            
        Returns:
            Dictionary parsed from JSON response (validated against schema)
            
        Raises:
            LLMProviderError: If generation fails, times out, or output is invalid
        """
        pass

    @abstractmethod
    def get_usage_metrics(self) -> Optional[LLMUsageMetrics]:
        """
        Get usage metrics from the last call.
        
        Returns:
            LLMUsageMetrics if available, None otherwise
        """
        pass

    def safe_generate(
        self,
        schema_name: str,
        prompt: str,
        tenant_id: Optional[str] = None,
        timeout_s: Optional[int] = None,
        agent_name: Optional[str] = None,
        audit_logger: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Generate and validate LLM output with strict schema validation.
        
        This method:
        1. Calls the underlying provider to generate raw text
        2. Validates the output against the schema (with fallback JSON parsing)
        3. Sanitizes the output (strips unknown fields, clamps values)
        4. Logs validation failures to audit if audit_logger is provided
        
        Args:
            schema_name: Name of the schema to use (e.g., "triage", "policy")
            prompt: Prompt text for LLM
            tenant_id: Optional tenant ID for logging
            timeout_s: Optional timeout in seconds
            agent_name: Optional agent name for audit logging (e.g., "TriageAgent")
            audit_logger: Optional AuditLogger instance for logging validation failures
            
        Returns:
            Validated and sanitized dictionary
            
        Raises:
            LLMProviderError: If generation fails
            LLMValidationError: If validation or sanitization fails
        """
        # This is a default implementation that can be overridden
        # For LLMClientImpl, we'll provide a concrete implementation
        return self.generate_json(
            prompt=prompt,
            schema_name=schema_name,
            tenant_id=tenant_id,
            timeout_s=timeout_s,
        )


class LLMClientImpl(LLMClient):
    """
    Implementation of LLMClient that wraps LLMProvider.
    
    Provides Phase 3 features:
    - Schema-aware generation via schema_name
    - Tenant-aware logging
    - Token/cost logging hooks
    - Timeout support
    """

    def __init__(
        self,
        provider: LLMProvider,
        tenant_id: Optional[str] = None,
        token_logger: Optional[Callable[[str, LLMUsageMetrics], None]] = None,
        cost_logger: Optional[Callable[[str, float], None]] = None,
        audit_logger: Optional[Any] = None,
        safety_enforcer: Optional[Any] = None,
        quota_enforcer: Optional[Any] = None,
    ):
        """
        Initialize LLMClient implementation.
        
        Args:
            provider: Underlying LLMProvider instance
            tenant_id: Optional default tenant ID
            token_logger: Optional callback for token usage logging (tenant_id, metrics)
            cost_logger: Optional callback for cost logging (tenant_id, cost)
            audit_logger: Optional AuditLogger instance for logging validation failures
            safety_enforcer: Optional SafetyEnforcer instance for safety rule enforcement
            quota_enforcer: Optional QuotaEnforcer instance for quota enforcement (P3-26)
        """
        self.provider = provider
        self.default_tenant_id = tenant_id
        self.token_logger = token_logger
        self.cost_logger = cost_logger
        self.audit_logger = audit_logger
        self.safety_enforcer = safety_enforcer
        self.quota_enforcer = quota_enforcer
        self._last_usage_metrics: Optional[LLMUsageMetrics] = None

    def generate_json(
        self,
        prompt: str,
        schema_name: str,
        tenant_id: Optional[str] = None,
        timeout_s: Optional[int] = None,
    ) -> dict[str, Any]:
        """
        Generate JSON response from LLM using named schema.
        
        Args:
            prompt: Prompt text for LLM
            schema_name: Name of the schema to use (e.g., "triage", "policy")
            tenant_id: Optional tenant ID (uses default if not provided)
            timeout_s: Optional timeout in seconds
            
        Returns:
            Dictionary parsed from JSON response (validated against schema)
            
        Raises:
            LLMProviderError: If generation fails, times out, or output is invalid
        """
        # Resolve tenant_id
        resolved_tenant_id = tenant_id or self.default_tenant_id
        
        # Get schema model for validation (try extended registry first for non-agent schemas)
        try:
            schema_model = get_extended_schema_model(schema_name)
        except ValueError as e:
            raise LLMProviderError(f"Invalid schema name: {e}") from e
        
        # Get JSON schema from Pydantic model
        json_schema = schema_model.model_json_schema()
        
        # Phase 3: Check safety rules before making LLM call
        if resolved_tenant_id and self.safety_enforcer:
            try:
                # Estimate tokens and cost before call
                estimated_tokens = self._estimate_tokens(prompt) + 1000  # Add buffer for completion
                estimated_cost = self._estimate_cost(estimated_tokens)  # Approximate cost
                
                # Check safety rules
                self.safety_enforcer.check_llm_call(
                    tenant_id=resolved_tenant_id,
                    tokens=estimated_tokens,
                    estimated_cost=estimated_cost,
                )
            except Exception as e:
                # Re-raise SafetyViolation as-is, wrap other exceptions
                if isinstance(e, Exception) and hasattr(e, 'rule_type'):
                    raise
                raise LLMProviderError(f"Safety check failed: {e}") from e
        
        # Record start time for latency calculation
        start_time = time.time()
        
        try:
            # Generate response with timeout handling
            if timeout_s is not None:
                # For MVP, we don't have actual async/timeout support in providers
                # In production, this would use asyncio.wait_for or similar
                logger.debug(f"Timeout requested: {timeout_s}s (not enforced in MVP)")
            
            # Call underlying provider with JSON schema
            response = self.provider.safe_generate(
                prompt=prompt,
                schema=json_schema,
                max_retries=3,
            )
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Validate response against Pydantic model
            try:
                validated_response = schema_model.model_validate(response)
                # Convert back to dict for return
                result = validated_response.model_dump()
            except Exception as e:
                raise LLMProviderError(
                    f"Response validation failed against schema '{schema_name}': {e}"
                ) from e
            
            # Estimate usage metrics (mock for MVP)
            # In production, this would come from provider response metadata
            total_tokens = self._estimate_tokens(prompt) + self._estimate_tokens(str(result))
            estimated_cost = self._estimate_cost(total_tokens)
            
            self._last_usage_metrics = LLMUsageMetrics(
                prompt_tokens=self._estimate_tokens(prompt),
                completion_tokens=self._estimate_tokens(str(result)),
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                latency_ms=latency_ms,
            )
            
            # Phase 3: Record usage with safety enforcer
            if resolved_tenant_id and self.safety_enforcer:
                try:
                    self.safety_enforcer.record_llm_usage(
                        tenant_id=resolved_tenant_id,
                        tokens=total_tokens,
                        actual_cost=estimated_cost,
                    )
                except Exception as e:
                    logger.warning(f"Failed to record LLM usage with safety enforcer: {e}")
            
            # Log usage metrics via hooks
            if resolved_tenant_id and self.token_logger:
                try:
                    self.token_logger(resolved_tenant_id, self._last_usage_metrics)
                except Exception as e:
                    logger.warning(f"Token logger callback failed: {e}")
            
            if resolved_tenant_id and self.cost_logger and self._last_usage_metrics.estimated_cost:
                try:
                    self.cost_logger(resolved_tenant_id, self._last_usage_metrics.estimated_cost)
                except Exception as e:
                    logger.warning(f"Cost logger callback failed: {e}")
            
            # Log tenant-aware usage
            if resolved_tenant_id:
                logger.debug(
                    f"LLM call completed for tenant {resolved_tenant_id}, "
                    f"schema: {schema_name}, latency: {latency_ms:.2f}ms"
                )
            
            return result
            
        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(f"LLM generation failed: {e}") from e

    def safe_generate(
        self,
        schema_name: str,
        prompt: str,
        tenant_id: Optional[str] = None,
        timeout_s: Optional[int] = None,
        agent_name: Optional[str] = None,
        audit_logger: Optional[Any] = None,
    ) -> dict[str, Any]:
        """
        Generate and validate LLM output with strict schema validation.
        
        This method:
        1. Calls the underlying provider to generate raw text
        2. Validates the output against the schema (with fallback JSON parsing)
        3. Sanitizes the output (strips unknown fields, clamps values)
        4. Logs validation failures to audit if audit_logger is provided
        
        Args:
            schema_name: Name of the schema to use (e.g., "triage", "policy")
            prompt: Prompt text for LLM
            tenant_id: Optional tenant ID for logging
            timeout_s: Optional timeout in seconds
            agent_name: Optional agent name for audit logging (e.g., "TriageAgent")
            audit_logger: Optional AuditLogger instance for logging validation failures
            
        Returns:
            Validated and sanitized dictionary
            
        Raises:
            LLMProviderError: If generation fails
            LLMValidationError: If validation or sanitization fails
        """
        resolved_tenant_id = tenant_id or self.default_tenant_id
        resolved_audit_logger = audit_logger or self.audit_logger
        
        # Get schema model for JSON schema
        try:
            schema_model = get_schema_model(schema_name)
            json_schema = schema_model.model_json_schema()
        except ValueError as e:
            raise LLMProviderError(f"Invalid schema name: {e}") from e
        
        # Phase 3: Check safety rules before making LLM call
        if resolved_tenant_id and self.safety_enforcer:
            try:
                # Estimate tokens and cost before call
                estimated_tokens = self._estimate_tokens(prompt) + 1000  # Add buffer for completion
                estimated_cost = self._estimate_cost(estimated_tokens)  # Approximate cost
                
                # Check safety rules
                self.safety_enforcer.check_llm_call(
                    tenant_id=resolved_tenant_id,
                    tokens=estimated_tokens,
                    estimated_cost=estimated_cost,
                )
            except Exception as e:
                # Re-raise SafetyViolation as-is, wrap other exceptions
                if isinstance(e, Exception) and hasattr(e, 'rule_type'):
                    raise
                raise LLMProviderError(f"Safety check failed: {e}") from e
        
        # Record start time for latency calculation
        start_time = time.time()
        
        try:
            # Generate raw response from provider
            # Note: For MVP, providers return dict, but in production they might return raw text
            # We'll handle both cases
            if timeout_s is not None:
                logger.debug(f"Timeout requested: {timeout_s}s (not enforced in MVP)")
            
            raw_response = self.provider.safe_generate(
                prompt=prompt,
                schema=json_schema,
                max_retries=3,
            )
            
            # Calculate latency
            latency_ms = (time.time() - start_time) * 1000
            
            # Convert response to raw text if it's already a dict
            # In production, provider would return raw text that needs parsing
            if isinstance(raw_response, dict):
                # For MVP, provider already returns dict, so we serialize it for validation
                raw_text = json.dumps(raw_response)
            else:
                raw_text = str(raw_response)
            
            # Validate and sanitize the output
            # Note: validate_llm_output already calls sanitize_llm_output internally
            try:
                sanitized = validate_llm_output(schema_name, raw_text)
            except LLMValidationError as e:
                # Log validation failure to audit
                if resolved_audit_logger and resolved_tenant_id:
                    try:
                        resolved_audit_logger._write_log_entry(
                            event_type="llm_validation_failure",
                            data={
                                "agent_name": agent_name,
                                "schema_name": schema_name,
                                "error_type": e.error_type,
                                "error_message": str(e),
                                "validation_errors": e.validation_errors,
                                "raw_text_preview": e.raw_text,
                            },
                            tenant_id=resolved_tenant_id,
                        )
                    except Exception as log_error:
                        logger.warning(f"Failed to log validation failure to audit: {log_error}")
                
                # Re-raise the validation error
                raise
            
            # Estimate usage metrics
            total_tokens = self._estimate_tokens(prompt) + self._estimate_tokens(raw_text)
            estimated_cost = self._estimate_cost(total_tokens)
            
            self._last_usage_metrics = LLMUsageMetrics(
                prompt_tokens=self._estimate_tokens(prompt),
                completion_tokens=self._estimate_tokens(raw_text),
                total_tokens=total_tokens,
                estimated_cost=estimated_cost,
                latency_ms=latency_ms,
            )
            
            # Phase 3: Record usage with safety enforcer
            if resolved_tenant_id and self.safety_enforcer:
                try:
                    self.safety_enforcer.record_llm_usage(
                        tenant_id=resolved_tenant_id,
                        tokens=total_tokens,
                        actual_cost=estimated_cost,
                    )
                except Exception as e:
                    logger.warning(f"Failed to record LLM usage with safety enforcer: {e}")
            
            # Log usage metrics via hooks
            if resolved_tenant_id and self.token_logger:
                try:
                    self.token_logger(resolved_tenant_id, self._last_usage_metrics)
                except Exception as e:
                    logger.warning(f"Token logger callback failed: {e}")
            
            if resolved_tenant_id and self.cost_logger and self._last_usage_metrics.estimated_cost:
                try:
                    self.cost_logger(resolved_tenant_id, self._last_usage_metrics.estimated_cost)
                except Exception as e:
                    logger.warning(f"Cost logger callback failed: {e}")
            
            # Log tenant-aware usage
            if resolved_tenant_id:
                logger.debug(
                    f"LLM safe_generate completed for tenant {resolved_tenant_id}, "
                    f"schema: {schema_name}, latency: {latency_ms:.2f}ms"
                )
            
            return sanitized
            
        except LLMValidationError:
            raise
        except LLMProviderError:
            raise
        except Exception as e:
            raise LLMProviderError(f"LLM generation failed: {e}") from e

    def get_usage_metrics(self) -> Optional[LLMUsageMetrics]:
        """Get usage metrics from the last call."""
        return self._last_usage_metrics

    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count for text (rough approximation).
        
        Args:
            text: Text to estimate tokens for
            
        Returns:
            Estimated token count
        """
        # Rough approximation: ~4 characters per token
        # In production, use tiktoken or similar
        return len(text) // 4
    
    def _estimate_cost(self, tokens: int) -> float:
        """
        Estimate cost for token usage (simple approximation).
        
        Args:
            tokens: Number of tokens
            
        Returns:
            Estimated cost in USD
        """
        # Simple approximation: ~$0.03 per 1K tokens (GPT-4 pricing)
        # In production, use actual provider pricing
        return (tokens / 1000.0) * 0.03


class LLMClientFactory:
    """
    Factory for creating LLMClient instances.
    """

    @staticmethod
    def create_client(
        provider_type: str = "openai",
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        tenant_id: Optional[str] = None,
        token_logger: Optional[Callable[[str, LLMUsageMetrics], None]] = None,
        cost_logger: Optional[Callable[[str, float], None]] = None,
        audit_logger: Optional[Any] = None,
        **kwargs,
    ) -> LLMClient:
        """
        Create LLMClient instance.
        
        Args:
            provider_type: Provider type ("openai" or "grok")
            api_key: API key for provider
            model: Model name (optional)
            tenant_id: Optional default tenant ID
            token_logger: Optional callback for token usage logging
            cost_logger: Optional callback for cost logging
            audit_logger: Optional AuditLogger instance for logging validation failures
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLMClient instance
            
        Raises:
            LLMProviderError: If provider type is unknown
        """
        provider = LLMProviderFactory.create_provider(
            provider_type=provider_type,
            api_key=api_key,
            model=model,
            **kwargs,
        )
        return LLMClientImpl(
            provider=provider,
            tenant_id=tenant_id,
            token_logger=token_logger,
            cost_logger=cost_logger,
            audit_logger=audit_logger,
        )

