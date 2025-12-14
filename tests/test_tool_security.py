"""
Security tests for tool execution.

Phase 8 P8-14: Tests for:
- Secret redaction in logging and events
- API key masking
- URL validation and endpoint allow-list enforcement
- Blocking arbitrary URLs
"""

import os
import pytest
from unittest.mock import MagicMock, patch, AsyncMock

from src.tools.security import (
    SecurityError,
    URLValidationError,
    redact_secrets_from_dict,
    redact_secrets_from_string,
    validate_url,
    mask_api_key_in_headers,
    safe_log_payload,
)
from src.tools.provider import HttpToolProvider, ToolProviderError
from src.infrastructure.db.models import ToolDefinition
from src.models.tool_definition_phase8 import AuthType, EndpointConfig


class TestSecretRedaction:
    """Tests for secret redaction functionality."""

    def test_redact_api_key_in_dict(self):
        """Test that API keys are redacted from dictionaries."""
        payload = {
            "action": "test",
            "api_key": "sk-1234567890abcdef",
            "data": {"value": 123},
        }
        
        redacted = redact_secrets_from_dict(payload)
        
        assert redacted["action"] == "test"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["data"]["value"] == 123

    def test_redact_password_in_dict(self):
        """Test that passwords are redacted from dictionaries."""
        payload = {
            "username": "user1",
            "password": "secret123",
            "nested": {
                "userPassword": "another_secret",
            },
        }
        
        redacted = redact_secrets_from_dict(payload)
        
        assert redacted["username"] == "user1"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["nested"]["userPassword"] == "[REDACTED]"

    def test_redact_token_in_dict(self):
        """Test that tokens are redacted from dictionaries."""
        payload = {
            "token": "bearer_token_12345",
            "access_token": "access_123",
            "refresh_token": "refresh_456",
        }
        
        redacted = redact_secrets_from_dict(payload)
        
        assert redacted["token"] == "[REDACTED]"
        assert redacted["access_token"] == "[REDACTED]"
        assert redacted["refresh_token"] == "[REDACTED]"

    def test_redact_nested_secrets(self):
        """Test that secrets are redacted in nested structures."""
        payload = {
            "level1": {
                "level2": {
                    "api_key": "sk-secret123",
                    "normal_field": "value",
                },
            },
        }
        
        redacted = redact_secrets_from_dict(payload)
        
        assert redacted["level1"]["level2"]["api_key"] == "[REDACTED]"
        assert redacted["level1"]["level2"]["normal_field"] == "value"

    def test_redact_secrets_from_string(self):
        """Test that secrets are redacted from strings."""
        text = '{"api_key": "sk-123456", "password": "secret"}'
        
        redacted = redact_secrets_from_string(text)
        
        assert "sk-***" in redacted or "[REDACTED]" in redacted
        assert "secret" not in redacted or "[REDACTED]" in redacted

    def test_redact_secrets_with_additional_patterns(self):
        """Test that additional patterns can be provided for redaction."""
        payload = {
            "custom_secret": "secret_value",
            "normal_field": "value",
        }
        
        redacted = redact_secrets_from_dict(
            payload,
            additional_patterns=[r"custom_secret"],
        )
        
        assert redacted["custom_secret"] == "[REDACTED]"
        assert redacted["normal_field"] == "value"

    def test_redact_secrets_with_custom_placeholder(self):
        """Test that custom redaction placeholder can be used."""
        payload = {"api_key": "secret123"}
        
        redacted = redact_secrets_from_dict(
            payload,
            redaction_placeholder="***MASKED***",
        )
        
        assert redacted["api_key"] == "***MASKED***"

    def test_redact_secrets_with_list_containing_dicts(self):
        """Test that secrets in lists containing dicts are redacted."""
        payload = {
            "items": [
                {"name": "item1", "api_key": "key1"},
                {"name": "item2", "password": "pass2"},
            ],
        }
        
        redacted = redact_secrets_from_dict(payload)
        
        assert redacted["items"][0]["api_key"] == "[REDACTED]"
        assert redacted["items"][1]["password"] == "[REDACTED]"
        assert redacted["items"][0]["name"] == "item1"
        assert redacted["items"][1]["name"] == "item2"

    def test_redact_secrets_non_dict_input(self):
        """Test that non-dict input returns as-is."""
        result = redact_secrets_from_dict("not a dict")
        assert result == "not a dict"
        
        result = redact_secrets_from_dict(None)
        assert result is None
        
        result = redact_secrets_from_dict(123)
        assert result == 123

    def test_redact_secrets_from_string_non_string_input(self):
        """Test that non-string input returns as-is."""
        result = redact_secrets_from_string(None)
        assert result is None
        
        result = redact_secrets_from_string(123)
        assert result == 123
        
        result = redact_secrets_from_string({"key": "value"})
        assert result == {"key": "value"}

    def test_redact_secrets_from_string_bearer_token(self):
        """Test that Bearer tokens are redacted from strings."""
        text = 'Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        
        redacted = redact_secrets_from_string(text)
        
        assert "Bearer ***" in redacted
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in redacted

    def test_redact_secrets_from_string_sk_live(self):
        """Test that sk_live_ tokens are redacted."""
        text = 'api_key: sk_live_1234567890abcdef'
        
        redacted = redact_secrets_from_string(text)
        
        assert "sk_live_***" in redacted
        assert "1234567890abcdef" not in redacted

    def test_redact_secrets_from_string_sk_test(self):
        """Test that sk_test_ tokens are redacted."""
        text = 'api_key: sk_test_1234567890abcdef'
        
        redacted = redact_secrets_from_string(text)
        
        assert "sk_test_***" in redacted
        assert "1234567890abcdef" not in redacted

    def test_redact_authorization_header(self):
        """Test that Authorization headers are masked."""
        headers = {
            "Authorization": "Bearer sk-1234567890abcdef",
            "X-API-Key": "api_key_12345",
            "Content-Type": "application/json",
        }
        
        masked = mask_api_key_in_headers(headers)
        
        assert masked["Authorization"] != headers["Authorization"]
        assert "***" in masked["Authorization"] or "masked" in masked["Authorization"].lower()
        assert masked["X-API-Key"] != headers["X-API-Key"]
        assert masked["Content-Type"] == "application/json"  # Non-sensitive header unchanged


class TestURLValidation:
    """Tests for URL validation and allow-list enforcement."""

    def test_validate_url_allows_https(self):
        """Test that HTTPS URLs are allowed by default."""
        validate_url("https://api.example.com/endpoint")

    def test_validate_url_blocks_http(self):
        """Test that HTTP URLs are blocked by default."""
        with pytest.raises(URLValidationError, match="scheme.*not allowed"):
            validate_url("http://api.example.com/endpoint")

    def test_validate_url_allows_custom_schemes(self):
        """Test that custom schemes can be allowed."""
        validate_url("http://api.example.com/endpoint", allowed_schemes=["http", "https"])

    def test_validate_url_enforces_domain_allow_list(self):
        """Test that domain allow-list is enforced."""
        allowed = ["api.example.com", "*.example.org"]
        
        # Allowed domains
        validate_url("https://api.example.com/endpoint", allowed_domains=allowed)
        validate_url("https://sub.example.org/endpoint", allowed_domains=allowed)
        
        # Blocked domain
        with pytest.raises(URLValidationError, match="not in allow-list"):
            validate_url("https://api.evil.com/endpoint", allowed_domains=allowed)

    def test_validate_url_blocks_localhost(self):
        """Test that localhost is blocked by default."""
        with pytest.raises(URLValidationError, match="localhost"):
            validate_url("https://localhost:8080/endpoint")
        
        with pytest.raises(URLValidationError, match="localhost"):
            validate_url("https://127.0.0.1:8080/endpoint")

    def test_validate_url_allows_localhost_if_in_allow_list(self):
        """Test that localhost can be allowed if explicitly listed."""
        validate_url(
            "https://localhost:8080/endpoint",
            allowed_domains=["localhost", "*.example.com"],
        )

    def test_validate_url_blocks_private_ips(self):
        """Test that private IPs are blocked."""
        with pytest.raises(URLValidationError, match="private IP"):
            validate_url("https://192.168.1.1/endpoint")

    def test_validate_url_invalid_format(self):
        """Test that invalid URL formats are rejected."""
        with pytest.raises(URLValidationError):
            validate_url("not-a-url")


class TestHttpToolProviderSecurity:
    """Tests for HttpToolProvider security features."""

    @pytest.fixture
    def mock_tool_definition(self):
        """Create a mock tool definition."""
        config = {
            "description": "Test tool",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "authType": "api_key",
            "endpointConfig": {
                "url": "https://api.example.com/endpoint",
                "method": "POST",
            },
        }
        
        tool_def = ToolDefinition(
            tool_id=1,
            tenant_id=None,
            name="test_tool",
            type="http",
            config=config,
        )
        return tool_def

    @pytest.mark.asyncio
    async def test_http_provider_validates_url_against_allow_list(self, mock_tool_definition):
        """Test that HttpToolProvider validates URLs against allow-list."""
        # Set API key for auth
        os.environ["TOOL_TEST_TOOL_API_KEY"] = "test_key_123"
        
        provider = HttpToolProvider(
            allowed_domains=["api.example.com"],
            allowed_schemes=["https"],
        )
        
        # Should work with allowed domain
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.is_success = True
            mock_response.json.return_value = {"result": "success"}
            mock_request.return_value = mock_response
            
            result = await provider.execute(mock_tool_definition, {"action": "test"})
            assert result["result"] == "success"
        
        # Cleanup
        del os.environ["TOOL_TEST_TOOL_API_KEY"]

    @pytest.mark.asyncio
    async def test_http_provider_blocks_arbitrary_urls(self, mock_tool_definition):
        """Test that HttpToolProvider blocks arbitrary URLs."""
        provider = HttpToolProvider(
            allowed_domains=["api.example.com"],
            allowed_schemes=["https"],
        )
        
        # Change URL to blocked domain
        config = mock_tool_definition.config.copy()
        config["endpointConfig"]["url"] = "https://evil.com/endpoint"
        mock_tool_definition.config = config
        
        with pytest.raises(ToolProviderError, match="URL validation failed"):
            await provider.execute(mock_tool_definition, {"action": "test"})

    @pytest.mark.asyncio
    async def test_http_provider_blocks_http_scheme(self, mock_tool_definition):
        """Test that HttpToolProvider blocks HTTP (non-HTTPS) by default."""
        provider = HttpToolProvider(
            allowed_domains=["api.example.com"],
        )  # Default allowed_schemes is ['https']
        
        # Change URL to HTTP
        config = mock_tool_definition.config.copy()
        config["endpointConfig"]["url"] = "http://api.example.com/endpoint"
        mock_tool_definition.config = config
        
        with pytest.raises(ToolProviderError, match="URL validation failed"):
            await provider.execute(mock_tool_definition, {"action": "test"})

    @pytest.mark.asyncio
    async def test_http_provider_never_logs_api_keys(self, mock_tool_definition):
        """Test that HttpToolProvider never logs API keys in raw form."""
        # Set API key in environment
        os.environ["TOOL_TEST_TOOL_API_KEY"] = "sk-secret123456"
        
        provider = HttpToolProvider(
            allowed_domains=["api.example.com"],
        )
        
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request, \
             patch("src.tools.provider.logger") as mock_logger:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.is_success = True
            mock_response.json.return_value = {"result": "success"}
            mock_request.return_value = mock_response
            
            await provider.execute(mock_tool_definition, {"action": "test"})
            
            # Verify that API key was never logged in raw form
            log_calls = str(mock_logger.debug.call_args_list) + str(mock_logger.info.call_args_list)
            assert "sk-secret123456" not in log_calls
            # Should contain masked version
            assert "masked" in log_calls.lower() or "***" in log_calls or "[REDACTED]" in log_calls
        
        # Cleanup
        del os.environ["TOOL_TEST_TOOL_API_KEY"]

    @pytest.mark.asyncio
    async def test_http_provider_redacts_secrets_in_logging(self, mock_tool_definition):
        """Test that HttpToolProvider redacts secrets in payload logging."""
        # Set API key for auth
        os.environ["TOOL_TEST_TOOL_API_KEY"] = "test_key_123"
        
        provider = HttpToolProvider(
            allowed_domains=["api.example.com"],
        )
        
        payload = {
            "action": "test",
            "api_key": "sk-secret123",
            "password": "secret_password",
        }
        
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request, \
             patch("src.tools.provider.logger") as mock_logger:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.is_success = True
            mock_response.json.return_value = {"result": "success"}
            mock_request.return_value = mock_response
            
            await provider.execute(mock_tool_definition, payload)
            
            # Verify that secrets were redacted in logs
            log_calls = str(mock_logger.debug.call_args_list) + str(mock_logger.info.call_args_list)
            assert "sk-secret123" not in log_calls
            assert "secret_password" not in log_calls
            assert "[REDACTED]" in log_calls or "masked" in log_calls.lower()
        
        # Cleanup
        del os.environ["TOOL_TEST_TOOL_API_KEY"]

    @pytest.mark.asyncio
    async def test_http_provider_redacts_secrets_in_response_logging(self, mock_tool_definition):
        """Test that HttpToolProvider redacts secrets in response logging."""
        # Set API key for auth
        os.environ["TOOL_TEST_TOOL_API_KEY"] = "test_key_123"
        
        provider = HttpToolProvider(
            allowed_domains=["api.example.com"],
        )
        
        with patch("httpx.AsyncClient.request", new_callable=AsyncMock) as mock_request, \
             patch("src.tools.provider.logger") as mock_logger:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.is_success = True
            mock_response.json.return_value = {
                "result": "success",
                "token": "secret_token_123",
                "api_key": "sk-secret456",
            }
            mock_request.return_value = mock_response
            
            await provider.execute(mock_tool_definition, {"action": "test"})
            
            # Verify that secrets were redacted in response logs
            log_calls = str(mock_logger.debug.call_args_list) + str(mock_logger.info.call_args_list)
            assert "secret_token_123" not in log_calls
            assert "sk-secret456" not in log_calls
            assert "[REDACTED]" in log_calls or "masked" in log_calls.lower()
        
        # Cleanup
        del os.environ["TOOL_TEST_TOOL_API_KEY"]


class TestToolInvokerSecurity:
    """Tests for ToolInvoker security features."""

    @pytest.mark.asyncio
    async def test_invoker_redacts_secrets_in_audit_log(self):
        """Test that ToolInvoker redacts secrets in audit logs."""
        from src.tools.invoker import ToolInvoker
        from src.tools.registry import ToolRegistry
        from src.audit.logger import AuditLogger
        from src.models.domain_pack import DomainPack, ToolDefinition as DomainToolDefinition
        from src.models.tenant_policy import TenantPolicyPack
        
        # Create minimal domain pack and tenant policy
        tool_def = DomainToolDefinition(
            description="Test tool",
            endpoint="https://api.example.com/endpoint",
        )
        domain_pack = DomainPack(domain_name="test", tools={"test_tool": tool_def})
        tenant_policy = TenantPolicyPack(
            tenant_id="TENANT_001",
            domain_name="test",
            approved_tools=["test_tool"],
        )
        
        registry = ToolRegistry()
        registry.register_domain_pack("TENANT_001", domain_pack)
        
        # Create audit logger that captures logs
        captured_logs = []
        
        class CapturingAuditLogger:
            def log_decision(self, event_type, data, tenant_id):
                captured_logs.append({"event_type": event_type, "data": data, "tenant_id": tenant_id})
        
        invoker = ToolInvoker(
            tool_registry=registry,
            audit_logger=CapturingAuditLogger(),
            use_execution_engine=False,
        )
        
        payload = {
            "action": "test",
            "api_key": "sk-secret123",
            "password": "secret_password",
        }
        
        # Execute in dry-run mode (won't make actual HTTP call)
        result = await invoker.invoke(
            tool_name="test_tool",
            args=payload,
            tenant_policy=tenant_policy,
            domain_pack=domain_pack,
            tenant_id="TENANT_001",
            dry_run=True,
        )
        
        # Verify that audit log contains redacted secrets
        assert len(captured_logs) > 0
        audit_data = captured_logs[0]["data"]
        assert "sk-secret123" not in str(audit_data)
        assert "secret_password" not in str(audit_data)
        assert "[REDACTED]" in str(audit_data) or "masked" in str(audit_data).lower()
        
        await invoker.close()


class TestSafeLogging:
    """Tests for safe logging utilities."""

    def test_safe_log_payload_redacts_secrets(self):
        """Test that safe_log_payload redacts secrets."""
        payload = {
            "action": "test",
            "api_key": "sk-secret123",
            "nested": {
                "password": "secret",
            },
        }
        
        safe_log = safe_log_payload(payload)
        
        assert "sk-secret123" not in safe_log
        assert "secret" not in safe_log or "[REDACTED]" in safe_log
        assert "[REDACTED]" in safe_log

    def test_safe_log_payload_handles_strings(self):
        """Test that safe_log_payload handles string payloads."""
        payload = '{"api_key": "sk-123"}'
        
        safe_log = safe_log_payload(payload)
        
        assert "sk-123" not in safe_log
        assert "[REDACTED]" in safe_log or "***" in safe_log

    def test_safe_log_payload_handles_non_dict_non_string(self):
        """Test that safe_log_payload handles non-dict, non-string payloads."""
        payload = 12345
        
        safe_log = safe_log_payload(payload)
        
        # Should convert to string and attempt redaction
        assert isinstance(safe_log, str)

    def test_safe_log_payload_handles_list(self):
        """Test that safe_log_payload handles list payloads."""
        payload = [{"api_key": "secret"}, {"password": "pass"}]
        
        safe_log = safe_log_payload(payload)
        
        assert "secret" not in safe_log
        assert "pass" not in safe_log or "[REDACTED]" in safe_log

    def test_validate_url_empty_string(self):
        """Test that empty URL strings are rejected."""
        with pytest.raises(URLValidationError, match="non-empty string"):
            validate_url("")

    def test_validate_url_none(self):
        """Test that None URLs are rejected."""
        with pytest.raises(URLValidationError, match="non-empty string"):
            validate_url(None)

    def test_validate_url_wildcard_domain_matching(self):
        """Test that wildcard domain patterns work correctly."""
        allowed = ["*.example.com"]
        
        # Should match subdomains
        validate_url("https://api.example.com/endpoint", allowed_domains=allowed)
        validate_url("https://sub.example.com/endpoint", allowed_domains=allowed)
        
        # Should not match different base domain
        with pytest.raises(URLValidationError):
            validate_url("https://api.example.org/endpoint", allowed_domains=allowed)

    def test_validate_url_wildcard_base_domain(self):
        """Test that wildcard matches base domain too."""
        allowed = ["*.example.com"]
        
        # Base domain should match
        validate_url("https://example.com/endpoint", allowed_domains=allowed)

    def test_validate_url_with_port(self):
        """Test that URLs with ports are handled correctly."""
        validate_url("https://api.example.com:8080/endpoint", allowed_domains=["api.example.com"])

    def test_validate_url_ipv6_localhost(self):
        """Test that IPv6 localhost is blocked."""
        with pytest.raises(URLValidationError, match="localhost"):
            validate_url("https://[::1]:8080/endpoint")

    def test_mask_api_key_in_headers_case_insensitive(self):
        """Test that header masking is case-insensitive."""
        headers = {
            "AUTHORIZATION": "Bearer token123",
            "X-Api-Key": "key123",
            "x-auth-token": "token456",
        }
        
        masked = mask_api_key_in_headers(headers)
        
        assert masked["AUTHORIZATION"] != "Bearer token123"
        assert masked["X-Api-Key"] != "key123"
        assert masked["x-auth-token"] != "token456"

    def test_mask_api_key_in_headers_preserves_non_sensitive(self):
        """Test that non-sensitive headers are preserved."""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "test-agent",
            "X-Custom-Header": "value",
        }
        
        masked = mask_api_key_in_headers(headers)
        
        assert masked["Content-Type"] == "application/json"
        assert masked["User-Agent"] == "test-agent"
        assert masked["X-Custom-Header"] == "value"

