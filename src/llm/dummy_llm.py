"""
Dummy LLM Client for Phase 5 - AI Co-Pilot.

Provides a mock LLM client implementation for testing and development.
This client does not make any real API calls and returns deterministic
mock responses.

Reference: docs/phase5-copilot-mvp.md Section 5.1 (LLM Abstraction - default: DummyLLMClient)
"""

import logging
from typing import Callable, Optional

from src.llm.base import LLMClient, LLMResponse

logger = logging.getLogger(__name__)


class DummyLLMClient:
    """
    Dummy LLM client implementation for testing and development.
    
    This client implements the LLMClient Protocol and returns mock responses
    without making any real API calls. It's useful for:
    - Development and testing
    - CI/CD pipelines
    - Default fallback when no provider is configured
    
    The client can be configured with:
    - Default mock response text
    - Custom response generator function
    - Context-aware responses
    
    Example:
        # Default behavior
        client = DummyLLMClient()
        response = await client.generate("Hello")
        # Returns: LLMResponse(text="[Dummy LLM] Mock response for: Hello")
        
        # Custom response
        client = DummyLLMClient(default_response="Custom text")
        response = await client.generate("Hello")
        # Returns: LLMResponse(text="Custom text")
        
        # Custom generator function
        def my_generator(prompt: str, context: dict | None) -> str:
            return f"Response to: {prompt}"
        
        client = DummyLLMClient(response_generator=my_generator)
        response = await client.generate("Hello")
        # Returns: LLMResponse(text="Response to: Hello")
    """
    
    def __init__(
        self,
        default_response: Optional[str] = None,
        response_generator: Optional[Callable[[str, dict | None], str]] = None,
    ):
        """
        Initialize DummyLLMClient.
        
        Args:
            default_response: Optional default text to return for all prompts.
                             If None, uses a deterministic mock response.
            response_generator: Optional function that takes (prompt, context) and
                               returns a string. Overrides default_response if provided.
        """
        self.default_response = default_response
        self.response_generator = response_generator
    
    async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
        """
        Generate a mock text response from the dummy LLM.
        
        This method does NOT make any real API calls. It returns a deterministic
        mock response based on the configuration.
        
        Args:
            prompt: The prompt text (logged but not used for real API calls)
            context: Optional context dictionary (logged but not used for real API calls)
            
        Returns:
            LLMResponse containing mock text and optional raw response data
            
        Raises:
            Never raises exceptions (always returns successfully)
        """
        # Log the call (safe placeholder - no sensitive data)
        logger.debug(
            f"DummyLLMClient.generate called: prompt_length={len(prompt)}, "
            f"has_context={context is not None}"
        )
        
        # Generate response text based on configuration
        if self.response_generator:
            # Use custom generator function
            text = self.response_generator(prompt, context)
        elif self.default_response:
            # Use provided default response
            text = self.default_response
        else:
            # Use deterministic default mock response
            text = self._generate_default_response(prompt, context)
        
        # Create raw response dictionary for debugging/tracing
        raw_response = {
            "provider": "dummy",
            "model": "dummy-model",
            "prompt_length": len(prompt),
            "has_context": context is not None,
            "context_keys": list(context.keys()) if context else [],
        }
        
        # Add intent_type and stats to raw response if available
        if context:
            intent_type = context.get("intent_type")
            if intent_type:
                raw_response["intent_type"] = intent_type
            
            exceptions_stats = context.get("exceptions_stats")
            if exceptions_stats:
                raw_response["stats"] = exceptions_stats
        
        return LLMResponse(
            text=text,
            raw=raw_response,
        )
    
    def _generate_default_response(self, prompt: str, context: dict | None) -> str:
        """
        Generate a deterministic default mock response with context-aware summaries.
        
        Args:
            prompt: The prompt text
            context: Optional context dictionary with intent_type, exceptions_stats, etc.
            
        Returns:
            Human-friendly summary text based on context, or generic fallback
        """
        if not context:
            return "This is a dummy Co-Pilot response (no real LLM configured)."
        
        intent_type = context.get("intent_type")
        tenant_id = context.get("tenant_id", "unknown")
        domain = context.get("domain", "unknown")
        
        # Handle SUMMARY intent
        if intent_type == "SUMMARY":
            exceptions_stats = context.get("exceptions_stats", {})
            total = exceptions_stats.get("total", 0)
            by_severity = exceptions_stats.get("by_severity", {})
            
            if total > 0:
                # Build natural language summary with detailed breakdown
                severity_parts = []
                for severity_level in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
                    count = by_severity.get(severity_level, 0)
                    if count > 0:
                        severity_parts.append(f"{count} {severity_level.lower()}")
                
                # Format: "For tenant X in Y, there are N exceptions today: X critical, Y high, ..."
                if severity_parts:
                    summary = f"For tenant {tenant_id} in {domain}, there are {total} exception{'s' if total != 1 else ''} today: {', '.join(severity_parts)}."
                else:
                    summary = f"For tenant {tenant_id} in {domain}, there are {total} exception{'s' if total != 1 else ''} today."
                
                # Add sample exceptions if available
                sample_exceptions = context.get("sample_exceptions", [])
                if sample_exceptions:
                    example_parts = []
                    for exc in sample_exceptions[:3]:  # Limit to 3 examples
                        exc_id = exc.get("id", "unknown")
                        exc_type = exc.get("type", "unknown")
                        exc_severity = exc.get("severity", "unknown")
                        example_parts.append(f"{exc_id} ({exc_type}, {exc_severity})")
                    
                    if example_parts:
                        summary += f" Examples: {', '.join(example_parts)}."
                
                return summary
            else:
                return f"For tenant {tenant_id} in {domain}, there are no active exceptions in the current time window. Operations appear stable right now."
        
        # Handle EXPLANATION intent
        elif intent_type == "EXPLANATION":
            sample_exceptions = context.get("sample_exceptions", [])
            
            if sample_exceptions and len(sample_exceptions) == 1:
                exc = sample_exceptions[0]
                exc_id = exc.get("id", "unknown")
                exc_type = exc.get("type", "unknown")
                exc_severity = exc.get("severity", "unknown")
                entity = exc.get("entity")
                
                parts = [
                    f"Exception {exc_id} is a {exc_type} in {domain}",
                    f"with severity {exc_severity}",
                ]
                
                if entity:
                    parts.append(f"for {entity}.")
                else:
                    parts.append(".")
                
                return " ".join(parts)
            else:
                # Fallback for EXPLANATION without specific exception
                return f"This is a dummy Co-Pilot response for explanation (no real LLM configured)."
        
        # Handle POLICY_HINT intent
        elif intent_type == "POLICY_HINT":
            policies = context.get("policies", [])
            if policies:
                policy_count = len(policies)
                return f"For tenant {tenant_id} in {domain}, there are {policy_count} relevant policy rule{'s' if policy_count != 1 else ''} configured."
            else:
                return f"For tenant {tenant_id} in {domain}, no specific policy information is available."
        
        # Fallback for UNKNOWN or other intents
        return "This is a dummy Co-Pilot response (no real LLM configured)."

