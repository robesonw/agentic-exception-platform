"""
Unit tests for Tool Provider implementations.

Tests cover:
- ToolProvider base interface
- HttpToolProvider: HTTP execution, auth, timeout, retry, error handling
- DummyToolProvider: Mock execution
"""

import asyncio
import os
from unittest.mock import MagicMock, patch

import httpx
import pytest

from src.infrastructure.db.models import ToolDefinition
from src.models.tool_definition_phase8 import AuthType, EndpointConfig, TenantScope
from src.tools.provider import (
    DummyToolProvider,
    HttpToolProvider,
    ToolProvider,
    ToolProviderAuthError,
    ToolProviderError,
    ToolProviderTimeoutError,
)


@pytest.fixture
def sample_tool_definition():
    """Create a sample tool definition for testing."""
    tool_def = ToolDefinition()
    tool_def.tool_id = 1
    tool_def.name = "test_tool"
    tool_def.type = "http"
    tool_def.tenant_id = "tenant_001"
    tool_def.config = {
        "description": "Test tool",
        "inputSchema": {"type": "object", "properties": {"param": {"type": "string"}}},
        "outputSchema": {"type": "object"},
        "authType": "none",
        "endpointConfig": {
            "url": "https://api.example.com/tool",
            "method": "POST",
            "headers": {},
            "timeout_seconds": 30.0,
        },
        "tenantScope": "tenant",
    }
    return tool_def


@pytest.fixture
def http_provider():
    """Create HttpToolProvider instance for testing."""
    return HttpToolProvider(default_timeout=5.0, max_retries=2, retry_delay=0.1)


@pytest.fixture
def dummy_provider():
    """Create DummyToolProvider instance for testing."""
    return DummyToolProvider(delay=0.01)


class TestToolProvider:
    """Tests for ToolProvider base interface."""

    def test_tool_provider_is_abstract(self):
        """Test that ToolProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            ToolProvider()  # type: ignore


class TestHttpToolProvider:
    """Tests for HttpToolProvider."""

    @pytest.mark.asyncio
    async def test_supports_tool_type_http(self, http_provider):
        """Test that HttpToolProvider supports HTTP tool types."""
        assert http_provider.supports_tool_type("http") is True
        assert http_provider.supports_tool_type("rest") is True
        assert http_provider.supports_tool_type("webhook") is True
        assert http_provider.supports_tool_type("https") is True

    @pytest.mark.asyncio
    async def test_supports_tool_type_non_http(self, http_provider):
        """Test that HttpToolProvider does not support non-HTTP tool types."""
        assert http_provider.supports_tool_type("email") is False
        assert http_provider.supports_tool_type("workflow") is False

    @pytest.mark.asyncio
    async def test_execute_success(self, http_provider, sample_tool_definition):
        """Test successful HTTP tool execution."""
        payload = {"param": "value"}
        expected_response = {"status": "success", "result": "data"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = expected_response
            mock_response.text = "{}"
            mock_request.return_value = mock_response

            result = await http_provider.execute(sample_tool_definition, payload)

            assert result == expected_response
            mock_request.assert_called_once()
            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["method"] == "POST"
            assert call_kwargs["url"] == "https://api.example.com/tool"
            assert call_kwargs["json"] == payload

    @pytest.mark.asyncio
    async def test_execute_get_method(self, http_provider, sample_tool_definition):
        """Test HTTP GET method execution."""
        sample_tool_definition.config["endpointConfig"]["method"] = "GET"
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "data"}
            mock_request.return_value = mock_response

            await http_provider.execute(sample_tool_definition, payload)

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["method"] == "GET"
            assert "params" in call_kwargs
            assert call_kwargs["params"] == payload
            assert "json" not in call_kwargs

    @pytest.mark.asyncio
    async def test_execute_auth_none(self, http_provider, sample_tool_definition):
        """Test execution with no authentication."""
        sample_tool_definition.config["authType"] = "none"
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "data"}
            mock_request.return_value = mock_response

            await http_provider.execute(sample_tool_definition, payload)

            call_kwargs = mock_request.call_args[1]
            headers = call_kwargs["headers"]
            assert "Authorization" not in headers
            assert headers["Content-Type"] == "application/json"

    @pytest.mark.asyncio
    async def test_execute_auth_api_key_success(self, http_provider, sample_tool_definition):
        """Test execution with API key authentication (success)."""
        sample_tool_definition.config["authType"] = "api_key"
        payload = {"param": "value"}

        with patch.dict(os.environ, {"TOOL_TEST_TOOL_API_KEY": "test-api-key-123"}):
            with patch("httpx.AsyncClient.request") as mock_request:
                mock_response = MagicMock()
                mock_response.is_success = True
                mock_response.status_code = 200
                mock_response.json.return_value = {"result": "data"}
                mock_request.return_value = mock_response

                await http_provider.execute(sample_tool_definition, payload)

                call_kwargs = mock_request.call_args[1]
                headers = call_kwargs["headers"]
                assert headers["Authorization"] == "Bearer test-api-key-123"

    @pytest.mark.asyncio
    async def test_execute_auth_api_key_missing(self, http_provider, sample_tool_definition):
        """Test execution with API key authentication (key missing)."""
        sample_tool_definition.config["authType"] = "api_key"
        payload = {"param": "value"}

        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ToolProviderAuthError) as exc_info:
                await http_provider.execute(sample_tool_definition, payload)
            assert "API key required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_auth_api_key_tenant_specific(self, http_provider, sample_tool_definition):
        """Test execution with tenant-specific API key."""
        sample_tool_definition.config["authType"] = "api_key"
        payload = {"param": "value"}

        with patch.dict(
            os.environ,
            {
                "TOOL_TENANT_001_TEST_TOOL_API_KEY": "tenant-key",
                "TOOL_TEST_TOOL_API_KEY": "global-key",
            },
        ):
            with patch("httpx.AsyncClient.request") as mock_request:
                mock_response = MagicMock()
                mock_response.is_success = True
                mock_response.status_code = 200
                mock_response.json.return_value = {"result": "data"}
                mock_request.return_value = mock_response

                await http_provider.execute(sample_tool_definition, payload)

                call_kwargs = mock_request.call_args[1]
                headers = call_kwargs["headers"]
                # Should use tenant-specific key
                assert headers["Authorization"] == "Bearer tenant-key"

    @pytest.mark.asyncio
    async def test_execute_auth_oauth_stub(self, http_provider, sample_tool_definition):
        """Test execution with OAuth stub authentication."""
        sample_tool_definition.config["authType"] = "oauth_stub"
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "data"}
            mock_request.return_value = mock_response

            await http_provider.execute(sample_tool_definition, payload)

            call_kwargs = mock_request.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["Authorization"] == "Bearer stub_oauth_token"

    @pytest.mark.asyncio
    async def test_execute_timeout(self, http_provider, sample_tool_definition):
        """Test timeout handling."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_request.side_effect = httpx.TimeoutException("Request timed out")

            with pytest.raises(ToolProviderTimeoutError) as exc_info:
                await http_provider.execute(sample_tool_definition, payload)
            assert "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_retry_on_timeout(self, http_provider, sample_tool_definition):
        """Test retry logic on timeout."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            # First two attempts timeout, third succeeds
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "data"}

            mock_request.side_effect = [
                httpx.TimeoutException("Request timed out"),
                httpx.TimeoutException("Request timed out"),
                mock_response,
            ]

            result = await http_provider.execute(sample_tool_definition, payload)

            assert result == {"result": "data"}
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_execute_retry_on_server_error(self, http_provider, sample_tool_definition):
        """Test retry logic on server errors (5xx)."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            # First attempt: 500 error, second: success
            mock_response_500 = MagicMock()
            mock_response_500.is_success = False
            mock_response_500.status_code = 500
            mock_response_500.text = "Internal Server Error"

            mock_response_200 = MagicMock()
            mock_response_200.is_success = True
            mock_response_200.status_code = 200
            mock_response_200.json.return_value = {"result": "data"}

            mock_request.side_effect = [mock_response_500, mock_response_200]

            result = await http_provider.execute(sample_tool_definition, payload)

            assert result == {"result": "data"}
            assert mock_request.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_no_retry_on_client_error(self, http_provider, sample_tool_definition):
        """Test that client errors (4xx) are not retried."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 400
            mock_response.text = "Bad Request"
            mock_request.return_value = mock_response

            with pytest.raises(ToolProviderError) as exc_info:
                await http_provider.execute(sample_tool_definition, payload)
            assert "400" in str(exc_info.value)

            # Should not retry
            assert mock_request.call_count == 1

    @pytest.mark.asyncio
    async def test_execute_auth_error_401(self, http_provider, sample_tool_definition):
        """Test handling of 401 Unauthorized error."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 401
            mock_response.text = "Unauthorized"
            mock_request.return_value = mock_response

            with pytest.raises(ToolProviderAuthError) as exc_info:
                await http_provider.execute(sample_tool_definition, payload)
            assert "Authentication failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_auth_error_403(self, http_provider, sample_tool_definition):
        """Test handling of 403 Forbidden error."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 403
            mock_response.text = "Forbidden"
            mock_request.return_value = mock_response

            with pytest.raises(ToolProviderAuthError) as exc_info:
                await http_provider.execute(sample_tool_definition, payload)
            assert "Access forbidden" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_not_found_404(self, http_provider, sample_tool_definition):
        """Test handling of 404 Not Found error."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = False
            mock_response.status_code = 404
            mock_response.text = "Not Found"
            mock_request.return_value = mock_response

            with pytest.raises(ToolProviderError) as exc_info:
                await http_provider.execute(sample_tool_definition, payload)
            assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_non_json_response(self, http_provider, sample_tool_definition):
        """Test handling of non-JSON response."""
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.side_effect = ValueError("Not JSON")
            mock_response.text = "Plain text response"
            mock_request.return_value = mock_response

            result = await http_provider.execute(sample_tool_definition, payload)

            assert "raw_response" in result
            assert result["raw_response"] == "Plain text response"
            assert result["status_code"] == 200

    @pytest.mark.asyncio
    async def test_execute_missing_endpoint_config(self, http_provider, sample_tool_definition):
        """Test error when endpoint_config is missing."""
        sample_tool_definition.config.pop("endpointConfig")
        payload = {"param": "value"}

        with pytest.raises(ToolProviderError) as exc_info:
            await http_provider.execute(sample_tool_definition, payload)
        assert "endpoint_config is required" in str(exc_info.value).lower() or "missing endpoint_config" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_invalid_tool_definition(self, http_provider):
        """Test error with invalid tool definition."""
        tool_def = ToolDefinition()
        tool_def.tool_id = 1
        tool_def.name = "invalid_tool"
        tool_def.type = "http"
        tool_def.config = {}  # Invalid config
        payload = {"param": "value"}

        with pytest.raises(ToolProviderError) as exc_info:
            await http_provider.execute(tool_def, payload)
        assert "Invalid tool definition" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_execute_custom_timeout(self, http_provider, sample_tool_definition):
        """Test custom timeout from endpoint config."""
        sample_tool_definition.config["endpointConfig"]["timeout_seconds"] = 10.0
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "data"}
            mock_request.return_value = mock_response

            await http_provider.execute(sample_tool_definition, payload)

            call_kwargs = mock_request.call_args[1]
            assert call_kwargs["timeout"] == 10.0

    @pytest.mark.asyncio
    async def test_execute_custom_headers(self, http_provider, sample_tool_definition):
        """Test custom headers from endpoint config."""
        sample_tool_definition.config["endpointConfig"]["headers"] = {
            "X-Custom-Header": "custom-value",
            "X-Another-Header": "another-value",
        }
        payload = {"param": "value"}

        with patch("httpx.AsyncClient.request") as mock_request:
            mock_response = MagicMock()
            mock_response.is_success = True
            mock_response.status_code = 200
            mock_response.json.return_value = {"result": "data"}
            mock_request.return_value = mock_response

            await http_provider.execute(sample_tool_definition, payload)

            call_kwargs = mock_request.call_args[1]
            headers = call_kwargs["headers"]
            assert headers["X-Custom-Header"] == "custom-value"
            assert headers["X-Another-Header"] == "another-value"

    @pytest.mark.asyncio
    async def test_close(self, http_provider):
        """Test closing HTTP client."""
        # Create client first
        await http_provider._get_client()
        assert http_provider._client is not None

        await http_provider.close()
        assert http_provider._client is None


class TestDummyToolProvider:
    """Tests for DummyToolProvider."""

    @pytest.mark.asyncio
    async def test_supports_tool_type(self, dummy_provider):
        """Test that DummyToolProvider supports all tool types."""
        assert dummy_provider.supports_tool_type("http") is True
        assert dummy_provider.supports_tool_type("email") is True
        assert dummy_provider.supports_tool_type("workflow") is True
        assert dummy_provider.supports_tool_type("custom") is True

    @pytest.mark.asyncio
    async def test_execute_http_tool(self, dummy_provider, sample_tool_definition):
        """Test dummy execution for HTTP tool."""
        payload = {"param": "value"}

        result = await dummy_provider.execute(sample_tool_definition, payload)

        assert result["status"] == "success"
        assert "message" in result
        assert result["input_received"] == payload
        assert result["tool_id"] == 1
        assert result["tool_name"] == "test_tool"

    @pytest.mark.asyncio
    async def test_execute_non_http_tool(self, dummy_provider):
        """Test dummy execution for non-HTTP tool."""
        tool_def = ToolDefinition()
        tool_def.tool_id = 2
        tool_def.name = "email_tool"
        tool_def.type = "email"
        tool_def.config = {}
        payload = {"to": "user@example.com", "subject": "Test"}

        result = await dummy_provider.execute(tool_def, payload)

        assert result["status"] == "success"
        assert result["tool"] == "email_tool"
        assert result["payload"] == payload

    @pytest.mark.asyncio
    async def test_execute_delay(self, dummy_provider, sample_tool_definition):
        """Test that dummy provider respects delay."""
        payload = {"param": "value"}
        dummy_provider.delay = 0.1

        start_time = asyncio.get_event_loop().time()
        await dummy_provider.execute(sample_tool_definition, payload)
        end_time = asyncio.get_event_loop().time()

        elapsed = end_time - start_time
        assert elapsed >= 0.1
        assert elapsed < 0.2  # Allow some margin

