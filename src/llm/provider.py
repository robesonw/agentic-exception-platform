"""
LLM Provider interface and implementations for Phase 2.

Provides:
- LLMProvider interface
- GrokProvider/OpenAIProvider stubs (config-driven)
- safe_generate(prompt, schema) enforcing JSON-only output

Matches specification from phase2-mvp-issues.md Issue 27.
"""

import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

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

