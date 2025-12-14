"""
Unit tests for Phase 8 Tool Definition schema validation.

Tests cover:
- Required fields validation
- Auth type enum validation
- Endpoint config validation for http tools
- Tenant scope validation
- Backward compatibility with legacy format
"""

import pytest
from pydantic import ValidationError

from src.models.tool_definition_phase8 import (
    ToolDefinitionRequest,
    ToolDefinitionConfig,
    EndpointConfig,
    AuthType,
    TenantScope,
)


class TestEndpointConfig:
    """Tests for EndpointConfig model."""

    def test_valid_endpoint_config(self):
        """Test valid endpoint configuration."""
        config = EndpointConfig(
            url="https://api.example.com/webhook",
            method="POST",
            headers={"Content-Type": "application/json"},
            timeout_seconds=30.0,
        )
        assert config.url == "https://api.example.com/webhook"
        assert config.method == "POST"
        assert config.headers == {"Content-Type": "application/json"}
        assert config.timeout_seconds == 30.0

    def test_endpoint_config_defaults(self):
        """Test endpoint configuration with defaults."""
        config = EndpointConfig(url="https://api.example.com/webhook")
        assert config.url == "https://api.example.com/webhook"
        assert config.method == "POST"
        assert config.headers == {}
        assert config.timeout_seconds is None

    def test_endpoint_config_invalid_url(self):
        """Test endpoint configuration with invalid URL."""
        with pytest.raises(ValidationError) as exc_info:
            EndpointConfig(url="")
        assert "min_length" in str(exc_info.value).lower() or "at least 1" in str(exc_info.value)


class TestToolDefinitionConfig:
    """Tests for ToolDefinitionConfig model."""

    def test_valid_config_all_fields(self):
        """Test valid config with all fields."""
        config = ToolDefinitionConfig(
            description="Test tool",
            input_schema={"type": "object", "properties": {"param": {"type": "string"}}},
            output_schema={"type": "object"},
            auth_type=AuthType.API_KEY,
            endpoint_config=EndpointConfig(url="https://api.example.com/webhook"),
            tenant_scope=TenantScope.TENANT,
        )
        assert config.description == "Test tool"
        assert config.auth_type == AuthType.API_KEY
        assert config.tenant_scope == TenantScope.TENANT

    def test_valid_config_minimal(self):
        """Test valid config with minimal required fields."""
        config = ToolDefinitionConfig(
            description="Test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            auth_type=AuthType.NONE,
        )
        assert config.description == "Test tool"
        assert config.auth_type == AuthType.NONE
        assert config.endpoint_config is None
        assert config.tenant_scope == TenantScope.TENANT  # Default

    def test_config_missing_required_fields(self):
        """Test config with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionConfig(
                description="Test tool",
                # Missing input_schema, output_schema, auth_type
            )
        assert "input_schema" in str(exc_info.value).lower() or "inputSchema" in str(exc_info.value)

    def test_config_invalid_auth_type(self):
        """Test config with invalid auth type."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionConfig(
                description="Test tool",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                auth_type="invalid_auth",  # Invalid
            )
        # Should fail enum validation
        assert "auth_type" in str(exc_info.value).lower() or "authType" in str(exc_info.value)

    def test_config_invalid_schema_type(self):
        """Test config with invalid schema (not a dict)."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionConfig(
                description="Test tool",
                input_schema="not a dict",  # Invalid
                output_schema={"type": "object"},
                auth_type=AuthType.NONE,
            )
        assert "schema" in str(exc_info.value).lower() or "dictionary" in str(exc_info.value).lower()

    def test_validate_for_tool_type_http_requires_endpoint(self):
        """Test that http tools require endpoint_config."""
        config_data = {
            "description": "HTTP tool",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "authType": "none",
            # Missing endpointConfig
        }
        
        with pytest.raises(ValueError) as exc_info:
            ToolDefinitionConfig.validate_for_tool_type("http", config_data)
        assert "endpoint_config" in str(exc_info.value).lower() or "endpointConfig" in str(exc_info.value).lower()

    def test_validate_for_tool_type_http_with_endpoint(self):
        """Test that http tools with endpoint_config are valid."""
        config_data = {
            "description": "HTTP tool",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "authType": "none",
            "endpointConfig": {
                "url": "https://api.example.com/webhook",
                "method": "POST",
            },
        }
        
        config = ToolDefinitionConfig.validate_for_tool_type("http", config_data)
        assert config.endpoint_config is not None
        assert config.endpoint_config.url == "https://api.example.com/webhook"

    def test_validate_for_tool_type_non_http_no_endpoint_required(self):
        """Test that non-http tools don't require endpoint_config."""
        config_data = {
            "description": "Dummy tool",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "authType": "none",
            # No endpointConfig - should be OK for non-http tools
        }
        
        config = ToolDefinitionConfig.validate_for_tool_type("dummy", config_data)
        assert config.endpoint_config is None


class TestToolDefinitionRequest:
    """Tests for ToolDefinitionRequest model."""

    def test_valid_request_all_fields(self):
        """Test valid request with all fields."""
        request = ToolDefinitionRequest(
            name="test_tool",
            type="http",
            description="Test tool",
            input_schema={"type": "object", "properties": {"param": {"type": "string"}}},
            output_schema={"type": "object"},
            auth_type=AuthType.API_KEY,
            endpoint_config=EndpointConfig(url="https://api.example.com/webhook"),
            tenant_scope=TenantScope.GLOBAL,
        )
        assert request.name == "test_tool"
        assert request.type == "http"
        assert request.description == "Test tool"
        assert request.auth_type == AuthType.API_KEY
        assert request.tenant_scope == TenantScope.GLOBAL

    def test_valid_request_minimal(self):
        """Test valid request with minimal fields."""
        request = ToolDefinitionRequest(
            name="dummy_tool",
            type="dummy",
            description="Dummy tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            auth_type=AuthType.NONE,
        )
        assert request.name == "dummy_tool"
        assert request.type == "dummy"
        assert request.endpoint_config is None  # Not required for non-http tools
        assert request.tenant_scope == TenantScope.TENANT  # Default

    def test_request_missing_required_fields(self):
        """Test request with missing required fields."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionRequest(
                name="test_tool",
                type="http",
                # Missing description, input_schema, output_schema, auth_type
            )
        assert "description" in str(exc_info.value).lower() or "required" in str(exc_info.value).lower()

    def test_request_http_requires_endpoint_config(self):
        """Test that http tools require endpoint_config."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionRequest(
                name="http_tool",
                type="http",
                description="HTTP tool",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                auth_type=AuthType.NONE,
                # Missing endpoint_config
            )
        assert "endpoint_config" in str(exc_info.value).lower() or "endpointConfig" in str(exc_info.value).lower()

    def test_request_rest_requires_endpoint_config(self):
        """Test that rest tools require endpoint_config."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionRequest(
                name="rest_tool",
                type="rest",
                description="REST tool",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                auth_type=AuthType.NONE,
                # Missing endpoint_config
            )
        assert "endpoint_config" in str(exc_info.value).lower()

    def test_request_webhook_requires_endpoint_config(self):
        """Test that webhook tools require endpoint_config."""
        with pytest.raises(ValidationError) as exc_info:
            ToolDefinitionRequest(
                name="webhook_tool",
                type="webhook",
                description="Webhook tool",
                input_schema={"type": "object"},
                output_schema={"type": "object"},
                auth_type=AuthType.NONE,
                # Missing endpoint_config
            )
        assert "endpoint_config" in str(exc_info.value).lower()

    def test_request_dummy_no_endpoint_required(self):
        """Test that dummy tools don't require endpoint_config."""
        request = ToolDefinitionRequest(
            name="dummy_tool",
            type="dummy",
            description="Dummy tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            auth_type=AuthType.NONE,
            # No endpoint_config - should be OK
        )
        assert request.endpoint_config is None

    def test_request_email_no_endpoint_required(self):
        """Test that email tools don't require endpoint_config."""
        request = ToolDefinitionRequest(
            name="email_tool",
            type="email",
            description="Email tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            auth_type=AuthType.NONE,
            # No endpoint_config - should be OK
        )
        assert request.endpoint_config is None

    def test_to_config_dict(self):
        """Test conversion to config dictionary."""
        request = ToolDefinitionRequest(
            name="test_tool",
            type="http",
            description="Test tool",
            input_schema={"type": "object"},
            output_schema={"type": "object"},
            auth_type=AuthType.API_KEY,
            endpoint_config=EndpointConfig(url="https://api.example.com/webhook"),
            tenant_scope=TenantScope.GLOBAL,
        )
        
        config_dict = request.to_config_dict()
        assert config_dict["description"] == "Test tool"
        assert config_dict["inputSchema"] == {"type": "object"}
        assert config_dict["outputSchema"] == {"type": "object"}
        assert config_dict["authType"] == "api_key"
        assert config_dict["tenantScope"] == "global"
        assert "endpointConfig" in config_dict
        assert config_dict["endpointConfig"]["url"] == "https://api.example.com/webhook"

    def test_from_config_dict_phase8_format(self):
        """Test creating request from Phase 8 config format."""
        config = {
            "description": "Test tool",
            "inputSchema": {"type": "object"},
            "outputSchema": {"type": "object"},
            "authType": "api_key",
            "endpointConfig": {
                "url": "https://api.example.com/webhook",
                "method": "POST",
            },
            "tenantScope": "global",
        }
        
        request = ToolDefinitionRequest.from_config_dict("test_tool", "http", config)
        assert request.name == "test_tool"
        assert request.type == "http"
        assert request.description == "Test tool"
        assert request.auth_type == AuthType.API_KEY
        assert request.tenant_scope == TenantScope.GLOBAL

    def test_from_config_dict_legacy_format(self):
        """Test creating request from legacy config format (backward compatibility)."""
        config = {
            "endpoint": "https://api.example.com/webhook",
            "method": "POST",
            "parameters": {"param": {"type": "string"}},
        }
        
        request = ToolDefinitionRequest.from_config_dict("legacy_tool", "http", config)
        assert request.name == "legacy_tool"
        assert request.type == "http"
        # Should have converted legacy format
        assert request.description is not None
        assert "inputSchema" in request.input_schema or request.input_schema == config["parameters"]
        assert request.endpoint_config is not None
        assert request.endpoint_config.url == "https://api.example.com/webhook"

    def test_from_config_dict_missing_required_fields(self):
        """Test from_config_dict with missing required fields (no endpoint, no description)."""
        config = {
            # Missing description, inputSchema, etc. and no endpoint either
            "some_field": "value",
        }
        
        with pytest.raises(ValueError) as exc_info:
            ToolDefinitionRequest.from_config_dict("tool", "http", config)
        assert "required" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower() or "cannot convert" in str(exc_info.value).lower()


class TestAuthTypeEnum:
    """Tests for AuthType enum."""

    def test_auth_type_none(self):
        """Test AuthType.NONE."""
        assert AuthType.NONE == "none"

    def test_auth_type_api_key(self):
        """Test AuthType.API_KEY."""
        assert AuthType.API_KEY == "api_key"

    def test_auth_type_oauth_stub(self):
        """Test AuthType.OAUTH_STUB."""
        assert AuthType.OAUTH_STUB == "oauth_stub"

    def test_auth_type_from_string(self):
        """Test creating AuthType from string."""
        assert AuthType("none") == AuthType.NONE
        assert AuthType("api_key") == AuthType.API_KEY
        assert AuthType("oauth_stub") == AuthType.OAUTH_STUB

    def test_auth_type_invalid(self):
        """Test invalid AuthType value."""
        with pytest.raises(ValueError):
            AuthType("invalid")


class TestTenantScopeEnum:
    """Tests for TenantScope enum."""

    def test_tenant_scope_global(self):
        """Test TenantScope.GLOBAL."""
        assert TenantScope.GLOBAL == "global"

    def test_tenant_scope_tenant(self):
        """Test TenantScope.TENANT."""
        assert TenantScope.TENANT == "tenant"

    def test_tenant_scope_from_string(self):
        """Test creating TenantScope from string."""
        assert TenantScope("global") == TenantScope.GLOBAL
        assert TenantScope("tenant") == TenantScope.TENANT

    def test_tenant_scope_invalid(self):
        """Test invalid TenantScope value."""
        with pytest.raises(ValueError):
            TenantScope("invalid")

