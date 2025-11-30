"""
LLM Provider module for Phase 2 and Phase 3.

Exports LLMProvider interface and implementations (Phase 2).
Exports LLMClient interface and implementations (Phase 3).
"""

from src.llm.provider import (
    GrokProvider,
    LLMClient,
    LLMClientFactory,
    LLMClientImpl,
    LLMProvider,
    LLMProviderError,
    LLMProviderFactory,
    LLMUsageMetrics,
    OpenAIProvider,
)
from src.llm.schemas import (
    BaseAgentLLMOutput,
    EvidenceReference,
    NLQAnswer,
    PolicyLLMOutput,
    ReasoningStep,
    ResolutionLLMOutput,
    SCHEMA_REGISTRY,
    SupervisorLLMOutput,
    TriageLLMOutput,
    get_extended_schema_model,
    get_schema_model,
)
from src.llm.validation import (
    LLMValidationError,
    extract_json_from_text,
    sanitize_llm_output,
    validate_llm_output,
)
from src.llm.fallbacks import (
    CircuitBreaker,
    CircuitBreakerState,
    FallbackReason,
    LLMFallbackPolicy,
    call_with_fallback,
    llm_or_rules,
)

__all__ = [
    # Phase 2 exports
    "LLMProvider",
    "LLMProviderError",
    "LLMProviderFactory",
    "OpenAIProvider",
    "GrokProvider",
    # Phase 3 exports
    "LLMClient",
    "LLMClientFactory",
    "LLMClientImpl",
    "LLMUsageMetrics",
    # Schema exports
    "BaseAgentLLMOutput",
    "TriageLLMOutput",
    "PolicyLLMOutput",
    "ResolutionLLMOutput",
    "SupervisorLLMOutput",
    "ReasoningStep",
    "EvidenceReference",
    "SCHEMA_REGISTRY",
    "NLQAnswer",
    "get_schema_model",
    "get_extended_schema_model",
    # Validation exports
    "LLMValidationError",
    "validate_llm_output",
    "sanitize_llm_output",
    "extract_json_from_text",
    # Fallback exports
    "LLMFallbackPolicy",
    "CircuitBreaker",
    "CircuitBreakerState",
    "FallbackReason",
    "call_with_fallback",
    "llm_or_rules",
]

