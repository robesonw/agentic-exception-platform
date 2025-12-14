"""
Tool Provider interface and implementations for Phase 8.

Provides abstraction for different tool execution backends:
- HttpToolProvider: HTTP/REST API calls
- DummyToolProvider: Mock provider for demos/tests

Reference: docs/phase8-tools-mvp.md Section 4.3
Phase 8 P8-14: Security enhancements - URL validation, secret redaction, API key masking
"""

import asyncio
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

from src.infrastructure.db.models import ToolDefinition
from src.models.tool_definition_phase8 import AuthType, EndpointConfig, ToolDefinitionRequest
from src.tools.security import (
    URLValidationError,
    mask_api_key_in_headers,
    redact_secrets_from_dict,
    safe_log_payload,
    validate_url,
)

logger = logging.getLogger(__name__)


class ToolProviderError(Exception):
    """Base exception for tool provider errors."""

    pass


class ToolProviderTimeoutError(ToolProviderError):
    """Raised when tool execution times out."""

    pass


class ToolProviderAuthError(ToolProviderError):
    """Raised when authentication fails."""

    pass


class ToolProvider(ABC):
    """
    Base interface for tool providers.
    
    All tool providers must implement execute() to run tool invocations.
    """

    @abstractmethod
    async def execute(
        self,
        tool_definition: ToolDefinition,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute a tool with the given payload.
        
        Args:
            tool_definition: Tool definition from database
            payload: Input payload for the tool
            
        Returns:
            Tool execution result dictionary
            
        Raises:
            ToolProviderError: If execution fails
            ToolProviderTimeoutError: If execution times out
            ToolProviderAuthError: If authentication fails
        """
        pass

    @abstractmethod
    def supports_tool_type(self, tool_type: str) -> bool:
        """
        Check if this provider supports the given tool type.
        
        Args:
            tool_type: Tool type string (e.g., 'http', 'rest', 'webhook')
            
        Returns:
            True if this provider can execute tools of this type
        """
        pass


class HttpToolProvider(ToolProvider):
    """
    HTTP/REST tool provider.
    
    Executes HTTP requests using endpoint configuration from ToolDefinition.
    Supports:
    - Authentication: none, api_key (env-based)
    - Timeout and retry logic
    - Graceful error handling
    - URL validation and endpoint allow-list enforcement (P8-14)
    - Secret redaction in logging (P8-14)
    """

    def __init__(
        self,
        default_timeout: float = 30.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        allowed_domains: Optional[list[str]] = None,
        allowed_schemes: Optional[list[str]] = None,
    ):
        """
        Initialize HTTP tool provider.
        
        Args:
            default_timeout: Default timeout in seconds (default: 30.0)
            max_retries: Maximum number of retries on failure (default: 3)
            retry_delay: Delay between retries in seconds (default: 1.0)
            allowed_domains: Optional list of allowed domains for endpoint URLs (P8-14)
                          If None, allows any domain (not recommended for production)
                          Supports wildcards: ['*.example.com', 'api.example.com']
            allowed_schemes: Optional list of allowed URL schemes (default: ['https'])
                          If None, defaults to ['https'] for security
        """
        self.default_timeout = default_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.allowed_domains = allowed_domains
        self.allowed_schemes = allowed_schemes or ['https']
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(self.default_timeout, connect=10.0),
                follow_redirects=True,
            )
        return self._client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def supports_tool_type(self, tool_type: str) -> bool:
        """Check if provider supports HTTP-based tool types."""
        http_types = ("http", "rest", "webhook", "https")
        return tool_type.lower() in http_types

    def _get_api_key(self, tool_name: str, tenant_id: Optional[str] = None) -> Optional[str]:
        """
        Get API key from environment variable.
        
        Environment variable naming convention:
        - TOOL_{TOOL_NAME}_API_KEY (uppercase, underscores)
        - TOOL_{TENANT_ID}_{TOOL_NAME}_API_KEY (if tenant_id provided)
        
        P8-14: API keys are never logged in raw form.
        
        Args:
            tool_name: Tool name
            tenant_id: Optional tenant ID for tenant-specific keys
            
        Returns:
            API key string or None if not found
        """
        # Normalize tool name for env var (uppercase, replace special chars with underscores)
        normalized_name = tool_name.upper().replace("-", "_").replace(".", "_").replace(" ", "_")
        
        # Try tenant-specific key first if tenant_id provided
        if tenant_id:
            normalized_tenant = tenant_id.upper().replace("-", "_").replace(".", "_").replace(" ", "_")
            tenant_key = f"TOOL_{normalized_tenant}_{normalized_name}_API_KEY"
            api_key = os.getenv(tenant_key)
            if api_key:
                # P8-14: Never log API key, only indicate it was found
                logger.debug(
                    f"Found tenant-specific API key for tool {tool_name} (tenant: {tenant_id}) "
                    "[API key masked in logs]"
                )
                return api_key
        
        # Fall back to global tool key
        global_key = f"TOOL_{normalized_name}_API_KEY"
        api_key = os.getenv(global_key)
        if api_key:
            # P8-14: Never log API key, only indicate it was found
            logger.debug(f"Found global API key for tool {tool_name} [API key masked in logs]")
        else:
            logger.warning(
                f"API key not found for tool {tool_name}. "
                f"Expected env var: {global_key} (value masked if present)"
            )
        return api_key

    def _build_headers(
        self,
        tool_definition: ToolDefinition,
        endpoint_config: EndpointConfig,
        payload: dict[str, Any],
    ) -> dict[str, str]:
        """
        Build HTTP headers for the request.
        
        Args:
            tool_definition: Tool definition
            endpoint_config: Endpoint configuration
            payload: Request payload (not used, but available for custom logic)
            
        Returns:
            Headers dictionary
            
        Raises:
            ToolProviderAuthError: If API key is required but not found
        """
        headers = dict(endpoint_config.headers or {})
        
        # Parse tool definition to get auth type
        try:
            tool_def_request = ToolDefinitionRequest.from_config_dict(
                name=tool_definition.name,
                type=tool_definition.type,
                config=tool_definition.config,
            )
        except ValueError as e:
            logger.warning(f"Failed to parse tool definition for headers: {e}")
            # Fall back to checking config directly
            auth_type_str = tool_definition.config.get("authType") or tool_definition.config.get("auth_type", "none")
            auth_type = AuthType(auth_type_str) if isinstance(auth_type_str, str) else AuthType.NONE
        else:
            auth_type = tool_def_request.auth_type
        
        # Add authentication headers
        if auth_type == AuthType.API_KEY:
            api_key = self._get_api_key(tool_definition.name, tool_definition.tenant_id)
            if not api_key:
                raise ToolProviderAuthError(
                    f"API key required for tool '{tool_definition.name}' but not found in environment. "
                    f"Set TOOL_{tool_definition.name.upper().replace('-', '_')}_API_KEY"
                )
            # Add API key header (common patterns: Authorization, X-API-Key, api-key)
            # Default to Authorization: Bearer <key>
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_type == AuthType.OAUTH_STUB:
            # OAuth stub: use placeholder token (for MVP)
            headers["Authorization"] = "Bearer stub_oauth_token"
            logger.debug(f"Using OAuth stub for tool '{tool_definition.name}'")
        # AuthType.NONE: no auth headers needed
        
        # Set content type if not specified
        if "Content-Type" not in headers:
            headers["Content-Type"] = "application/json"
        
        return headers

    async def execute(
        self,
        tool_definition: ToolDefinition,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute HTTP tool with retry and error handling.
        
        Args:
            tool_definition: Tool definition from database
            payload: Input payload for the tool
            
        Returns:
            Tool execution result dictionary
            
        Raises:
            ToolProviderError: If execution fails
            ToolProviderTimeoutError: If execution times out
            ToolProviderAuthError: If authentication fails
        """
        # Parse tool definition to get endpoint config
        try:
            tool_def_request = ToolDefinitionRequest.from_config_dict(
                name=tool_definition.name,
                type=tool_definition.type,
                config=tool_definition.config,
            )
        except ValueError as e:
            raise ToolProviderError(
                f"Invalid tool definition for '{tool_definition.name}': {e}"
            ) from e
        
        if not tool_def_request.endpoint_config:
            raise ToolProviderError(
                f"Tool '{tool_definition.name}' is HTTP type but missing endpoint_config"
            )
        
        endpoint_config = tool_def_request.endpoint_config
        url = endpoint_config.url
        method = endpoint_config.method.upper()
        timeout = endpoint_config.timeout_seconds or self.default_timeout
        
        # P8-14: Validate URL against allow-list before execution
        try:
            validate_url(
                url,
                allowed_domains=self.allowed_domains,
                allowed_schemes=self.allowed_schemes,
            )
        except URLValidationError as e:
            error_msg = f"URL validation failed for tool '{tool_definition.name}': {e}"
            logger.error(error_msg)
            raise ToolProviderError(error_msg) from e
        
        # Build headers with authentication
        try:
            headers = self._build_headers(tool_definition, endpoint_config, payload)
        except ToolProviderAuthError:
            raise
        except Exception as e:
            raise ToolProviderError(f"Failed to build headers: {e}") from e
        
        # Execute with retry logic
        client = await self._get_client()
        last_error: Optional[Exception] = None
        
        # P8-14: Redact secrets from payload for logging
        redacted_payload = redact_secrets_from_dict(payload)
        # P8-14: Mask API keys in headers for logging
        masked_headers = mask_api_key_in_headers(headers)
        
        for attempt in range(self.max_retries + 1):
            try:
                # P8-14: Log with redacted payload and masked headers
                logger.debug(
                    f"Executing HTTP tool '{tool_definition.name}' "
                    f"(attempt {attempt + 1}/{self.max_retries + 1}): {method} {url}\n"
                    f"Headers (secrets masked): {masked_headers}\n"
                    f"Payload (secrets redacted): {safe_log_payload(redacted_payload)}"
                )
                
                # Create request with timeout
                request_kwargs: dict[str, Any] = {
                    "method": method,
                    "url": url,
                    "headers": headers,  # Use original headers for actual request
                    "timeout": timeout,
                }
                
                # Add body for methods that support it
                if method in ("POST", "PUT", "PATCH"):
                    request_kwargs["json"] = payload
                elif method == "GET":
                    # For GET, add params as query string
                    request_kwargs["params"] = payload
                
                response = await client.request(**request_kwargs)
                
                # Handle HTTP errors gracefully
                if response.is_success:
                    # Parse JSON response
                    try:
                        result = response.json()
                    except Exception as e:
                        logger.warning(
                            f"Tool '{tool_definition.name}' returned non-JSON response: {e}. "
                            f"Using text response."
                        )
                        result = {"raw_response": response.text, "status_code": response.status_code}
                    
                    # P8-14: Redact secrets from response before logging
                    redacted_result = redact_secrets_from_dict(result) if isinstance(result, dict) else result
                    logger.info(
                        f"Tool '{tool_definition.name}' executed successfully "
                        f"(status: {response.status_code})\n"
                        f"Response (secrets redacted): {safe_log_payload(redacted_result)}"
                    )
                    return result
                
                # Handle HTTP error status codes
                status_code = response.status_code
                if status_code == 401:
                    raise ToolProviderAuthError(
                        f"Authentication failed for tool '{tool_definition.name}' "
                        f"(status: {status_code})"
                    )
                elif status_code == 403:
                    raise ToolProviderAuthError(
                        f"Access forbidden for tool '{tool_definition.name}' "
                        f"(status: {status_code})"
                    )
                elif status_code == 404:
                    raise ToolProviderError(
                        f"Tool endpoint not found for '{tool_definition.name}' "
                        f"(status: {status_code}, url: {url})"
                    )
                elif status_code >= 500:
                    # Server errors: retry
                    error_msg = (
                        f"Server error for tool '{tool_definition.name}' "
                        f"(status: {status_code})"
                    )
                    if attempt < self.max_retries:
                        logger.warning(f"{error_msg}. Retrying...")
                        last_error = ToolProviderError(error_msg)
                        await asyncio.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                        continue
                    else:
                        raise ToolProviderError(error_msg)
                else:
                    # Client errors (4xx): don't retry
                    error_text = response.text[:200] if response.text else ""
                    raise ToolProviderError(
                        f"Tool '{tool_definition.name}' returned error "
                        f"(status: {status_code}): {error_text}"
                    )
            
            except httpx.TimeoutException as e:
                error_msg = f"Tool '{tool_definition.name}' execution timed out after {timeout}s"
                if attempt < self.max_retries:
                    logger.warning(f"{error_msg}. Retrying...")
                    last_error = ToolProviderTimeoutError(error_msg)
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise ToolProviderTimeoutError(error_msg) from e
            
            except httpx.RequestError as e:
                error_msg = f"Request error for tool '{tool_definition.name}': {e}"
                if attempt < self.max_retries:
                    logger.warning(f"{error_msg}. Retrying...")
                    last_error = ToolProviderError(error_msg)
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise ToolProviderError(error_msg) from e
            
            except (ToolProviderAuthError, ToolProviderError) as e:
                # Don't retry auth errors or explicit provider errors
                raise
            
            except Exception as e:
                error_msg = f"Unexpected error executing tool '{tool_definition.name}': {e}"
                if attempt < self.max_retries:
                    logger.warning(f"{error_msg}. Retrying...")
                    last_error = ToolProviderError(error_msg)
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise ToolProviderError(error_msg) from e
        
        # If we exhausted retries, raise last error
        if last_error:
            raise last_error
        
        raise ToolProviderError(f"Failed to execute tool '{tool_definition.name}' after {self.max_retries + 1} attempts")


class DummyToolProvider(ToolProvider):
    """
    Dummy tool provider for demos and tests.
    
    Returns mock responses without making actual HTTP calls.
    Useful for:
    - Development and testing
    - Demos without external dependencies
    - Dry-run mode
    """

    def __init__(self, delay: float = 0.1):
        """
        Initialize dummy tool provider.
        
        Args:
            delay: Simulated execution delay in seconds (default: 0.1)
        """
        self.delay = delay

    def supports_tool_type(self, tool_type: str) -> bool:
        """Dummy provider supports all tool types."""
        return True

    async def execute(
        self,
        tool_definition: ToolDefinition,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Execute dummy tool (returns mock response).
        
        Args:
            tool_definition: Tool definition from database
            payload: Input payload for the tool
            
        Returns:
            Mock execution result dictionary
        """
        # Simulate execution delay
        await asyncio.sleep(self.delay)
        
        # Return mock response based on tool type
        tool_type = tool_definition.type.lower()
        
        if tool_type in ("http", "rest", "webhook"):
            return {
                "status": "success",
                "message": f"Dummy execution of tool '{tool_definition.name}'",
                "input_received": payload,
                "tool_id": tool_definition.tool_id,
                "tool_name": tool_definition.name,
            }
        else:
            # Generic mock response for other tool types
            return {
                "status": "success",
                "message": f"Dummy execution completed",
                "tool": tool_definition.name,
                "payload": payload,
            }

