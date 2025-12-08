"""
OpenRouter LLM Client for Phase 5 - AI Co-Pilot.

Provides OpenRouter API integration for LLM generation.
This client implements the LLMClient Protocol and communicates with OpenRouter's
chat/completions API.

Reference: docs/phase5-llm-routing.md Section 3 (Providers & LLMClient Implementations - OpenRouter)
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

from src.llm.base import LLMClient, LLMResponse
from src.llm.prompt_constraints import sanitize_prompt
from src.llm.utils import mask_secret

logger = logging.getLogger(__name__)


@dataclass
class OpenRouterConfig:
    """
    Configuration for OpenRouter LLM client.
    
    Attributes:
        api_key: OpenRouter API key (required)
        base_url: OpenRouter API base URL (default: https://openrouter.ai/api/v1/chat/completions)
        model: Model identifier to use (default: gpt-4.1-mini)
        timeout: Request timeout in seconds (default: 30.0)
    """
    api_key: str
    base_url: str = "https://openrouter.ai/api/v1/chat/completions"
    model: str = "gpt-4.1-mini"
    timeout: float = 30.0


class OpenRouterLLMClient:
    """
    OpenRouter LLM client implementation.
    
    This client implements the LLMClient Protocol and communicates with OpenRouter's
    chat/completions API. It supports:
    - Multiple model selection via OpenRouter
    - API key authentication
    - System and user message formatting
    - Error handling and fallback responses
    
    Example:
        config = OpenRouterConfig(
            api_key="sk-or-v1-...",
            model="gpt-4.1-mini"
        )
        client = OpenRouterLLMClient(config)
        response = await client.generate(
            prompt="What are today's exceptions?",
            context={"tenant_id": "tenant_001", "domain": "finance"}
        )
        # Returns: LLMResponse(text="...", raw={...})
    """
    
    def __init__(self, config: OpenRouterConfig):
        """
        Initialize OpenRouter LLM client.
        
        Args:
            config: OpenRouterConfig with API key, base URL, model, and timeout
        """
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get or create httpx AsyncClient instance.
        
        Returns:
            httpx.AsyncClient instance
        """
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.config.timeout)
        return self._client
    
    async def _close_client(self) -> None:
        """Close httpx AsyncClient if it exists."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None
    
    async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
        """
        Generate a text response from OpenRouter LLM.
        
        This method:
        1. Builds messages array with system and user messages
        2. Sends POST request to OpenRouter API
        3. Extracts response text from API response
        4. Returns LLMResponse with text and raw response data
        
        Args:
            prompt: The prompt text to send to the LLM
            context: Optional context dictionary (e.g., tenant info, domain info, intent_type)
                    Used to build system message and enrich user prompt
        
        Returns:
            LLMResponse containing the generated text and optional raw response data
            
        Raises:
            Exception: If generation fails (wrapped in LLMResponse.raw with error info)
        """
        # Extract domain from context for prompt sanitization (LR-9)
        domain = None
        if context:
            domain = context.get("domain")
        
        # Apply prompt constraints/sanitization before sending to external provider (LR-9)
        # This is especially important for PHI/PII-heavy domains like Healthcare
        sanitized_prompt = sanitize_prompt(domain, prompt, context)
        
        if sanitized_prompt != prompt:
            logger.debug(
                f"Prompt sanitized for domain '{domain}': "
                f"original_length={len(prompt)}, sanitized_length={len(sanitized_prompt)}"
            )
        
        # Build messages array for OpenRouter API using sanitized prompt
        messages = self._build_messages(sanitized_prompt, context)
        
        # Build request payload
        payload = {
            "model": self.config.model,
            "messages": messages,
        }
        
        # Build headers with API key
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
            # OpenRouter-specific headers
            "HTTP-Referer": "https://github.com/your-org/agentic-exception-platform",  # Optional: your app URL
            "X-Title": "SentinAI Exception Platform",  # Optional: your app name
        }
        
        # Log request (without exposing API key)
        logger.debug(
            f"OpenRouterLLMClient.generate called: model={self.config.model}, "
            f"prompt_length={len(prompt)}, has_context={context is not None}"
        )
        
        try:
            # Get HTTP client
            client = await self._get_client()
            
            # Make API request
            response = await client.post(
                self.config.base_url,
                json=payload,
                headers=headers,
            )
            
            # Raise exception for HTTP errors
            response.raise_for_status()
            
            # Parse response JSON
            response_data = response.json()
            
            # Extract text from first choice
            text = self._extract_text_from_response(response_data)
            
            # Build raw response dictionary for debugging/tracing
            raw_response = {
                "provider": "openrouter",
                "model": self.config.model,
                "base_url": self.config.base_url,
                "prompt_length": len(prompt),
                "has_context": context is not None,
                "response_data": response_data,
                # Extract useful metadata from OpenRouter response
                "usage": response_data.get("usage", {}),
                "model_used": response_data.get("model"),  # Actual model used (may differ from requested)
            }
            
            # Add context metadata if available
            if context:
                raw_response["context_keys"] = list(context.keys())
                intent_type = context.get("intent_type")
                if intent_type:
                    raw_response["intent_type"] = intent_type
            
            logger.debug(
                f"OpenRouterLLMClient.generate succeeded: "
                f"text_length={len(text)}, model_used={raw_response.get('model_used')}"
            )
            
            return LLMResponse(
                text=text,
                raw=raw_response,
            )
            
        except httpx.HTTPStatusError as e:
            # HTTP error (4xx, 5xx)
            error_message = f"OpenRouter API HTTP error: {e.response.status_code}"
            try:
                error_data = e.response.json()
                error_message += f" - {error_data.get('error', {}).get('message', 'Unknown error')}"
            except Exception:
                # Truncate response text to avoid logging sensitive data
                response_text = e.response.text[:200] if e.response.text else ""
                error_message += f" - {response_text}"
            
            # Log error without exposing API key
            logger.error(
                f"{error_message} (api_key={mask_secret(self.config.api_key)})"
            )
            
            # Return fallback response with error info in raw
            return LLMResponse(
                text="I apologize, but I encountered an error while processing your request. Please try again later.",
                raw={
                    "provider": "openrouter",
                    "model": self.config.model,
                    "error": True,
                    "error_type": "http_status_error",
                    "status_code": e.response.status_code,
                    "error_message": error_message,
                    "prompt_length": len(prompt),
                },
            )
            
        except httpx.RequestError as e:
            # Network/connection error
            error_message = f"OpenRouter API request error: {str(e)}"
            # Log error without exposing API key
            logger.error(
                f"{error_message} (api_key={mask_secret(self.config.api_key)})"
            )
            
            # Return fallback response with error info in raw
            return LLMResponse(
                text="I apologize, but I'm unable to connect to the AI service right now. Please try again later.",
                raw={
                    "provider": "openrouter",
                    "model": self.config.model,
                    "error": True,
                    "error_type": "request_error",
                    "error_message": error_message,
                    "prompt_length": len(prompt),
                },
            )
            
        except Exception as e:
            # Unexpected error
            error_message = f"OpenRouter API unexpected error: {str(e)}"
            # Log error without exposing API key
            logger.error(
                f"{error_message} (api_key={mask_secret(self.config.api_key)})",
                exc_info=True
            )
            
            # Return fallback response with error info in raw
            return LLMResponse(
                text="I apologize, but an unexpected error occurred. Please try again later.",
                raw={
                    "provider": "openrouter",
                    "model": self.config.model,
                    "error": True,
                    "error_type": "unexpected_error",
                    "error_message": error_message,
                    "prompt_length": len(prompt),
                },
            )
    
    def _build_messages(self, prompt: str, context: dict | None = None) -> list[dict[str, str]]:
        """
        Build messages array for OpenRouter API.
        
        OpenRouter uses a chat completions format with system and user messages.
        This method:
        1. Creates a system message with safety/role prompt (read-only copilot)
        2. Creates a user message with the prompt and optional context
        
        Args:
            prompt: The user prompt text
            context: Optional context dictionary (tenant_id, domain, intent_type, etc.)
        
        Returns:
            List of message dictionaries in OpenRouter format:
            [
                {"role": "system", "content": "..."},
                {"role": "user", "content": "..."}
            ]
        """
        messages = []
        
        # System message: Safety/role prompt for read-only copilot
        # TODO: Advanced routing per domain/tenant - customize system prompt based on domain/tenant
        system_content = (
            "You are the read-only AI Co-Pilot for a multi-tenant exception processing platform. "
            "Your role is to help operators understand exceptions, policies, and system behavior. "
            "You NEVER perform actions, approve exceptions, or execute commands. "
            "You only provide explanations, summaries, and policy hints based on the data you are given. "
            "Always be helpful, accurate, and concise in your responses."
        )
        
        # Add domain/tenant context to system message if available
        if context:
            tenant_id = context.get("tenant_id")
            domain = context.get("domain")
            if tenant_id and domain:
                system_content += f"\n\nYou are assisting tenant {tenant_id} in the {domain} domain."
        
        messages.append({
            "role": "system",
            "content": system_content,
        })
        
        # User message: Combine prompt with context if available
        user_content = prompt
        
        # TODO: Prompt constraint hook - apply PHI/PII sanitization before sending to external provider
        # This would be called here to sanitize the prompt for domains with strict data privacy requirements
        
        # Optionally enrich user message with context (if not already in prompt)
        if context:
            # Add context hints to user message (non-sensitive info only)
            context_hints = []
            intent_type = context.get("intent_type")
            if intent_type:
                context_hints.append(f"Intent: {intent_type}")
            
            # Don't add sensitive context (tenant_id, domain already in system message)
            # Only add non-sensitive metadata that helps the LLM understand the request
            
            if context_hints:
                user_content = f"{user_content}\n\n[Context: {', '.join(context_hints)}]"
        
        messages.append({
            "role": "user",
            "content": user_content,
        })
        
        return messages
    
    def _extract_text_from_response(self, response_data: dict[str, Any]) -> str:
        """
        Extract text from OpenRouter API response.
        
        OpenRouter response format:
        {
            "id": "...",
            "model": "...",
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "..."
                    },
                    "finish_reason": "stop"
                }
            ],
            "usage": {...}
        }
        
        Args:
            response_data: Parsed JSON response from OpenRouter API
        
        Returns:
            Extracted text content from first choice
        
        Raises:
            ValueError: If response format is invalid
        """
        if "choices" not in response_data:
            raise ValueError("OpenRouter response missing 'choices' field")
        
        choices = response_data["choices"]
        if not choices or len(choices) == 0:
            raise ValueError("OpenRouter response has empty 'choices' array")
        
        first_choice = choices[0]
        if "message" not in first_choice:
            raise ValueError("OpenRouter response choice missing 'message' field")
        
        message = first_choice["message"]
        if "content" not in message:
            raise ValueError("OpenRouter response message missing 'content' field")
        
        content = message["content"]
        if not isinstance(content, str):
            raise ValueError(f"OpenRouter response content is not a string: {type(content)}")
        
        return content
    
    async def __aenter__(self):
        """Async context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - close HTTP client."""
        await self._close_client()

