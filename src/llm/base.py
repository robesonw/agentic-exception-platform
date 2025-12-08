"""
LLM Abstraction Layer for Phase 5 - AI Co-Pilot.

Provides:
- LLMClient Protocol interface for Co-Pilot use case
- LLMResponse dataclass for Co-Pilot responses

This module defines the base interface for Phase 5 Co-Pilot LLM integration.
Provider implementations (DummyLLM, OpenAI, etc.) will implement this Protocol.

Reference: docs/phase5-copilot-mvp.md Section 5.1 (LLM Abstraction)
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass
class LLMResponse:
    """
    Response from LLM client.
    
    Attributes:
        text: The generated text response from the LLM
        raw: Optional raw response dictionary from the provider (for debugging/tracing)
    """
    text: str
    raw: dict | None = None


class LLMClient(Protocol):
    """
    Protocol interface for LLM clients used by Phase 5 Co-Pilot.
    
    This is a simpler, more generic interface than the Phase 3 LLMClient
    (which is schema-focused for agents). This interface is designed for
    conversational Co-Pilot use cases.
    
    Implementations should provide:
    - async generate() method that takes a prompt and optional context
    - Returns LLMResponse with text and optional raw response data
    
    Example:
        class MyLLMClient:
            async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
                # Implementation here
                return LLMResponse(text="...", raw={...})
    """
    
    async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
        """
        Generate a text response from the LLM.
        
        Args:
            prompt: The prompt text to send to the LLM
            context: Optional context dictionary (e.g., tenant info, domain info)
            
        Returns:
            LLMResponse containing the generated text and optional raw response
            
        Raises:
            Exception: If generation fails (specific exception types TBD by implementations)
        """
        ...

