"""
Unit tests for ToolValidationService.

Tests cover:
- Payload validation with JSON Schema
- Tool enablement checking
- Tenant scope validation
- Secret redaction
- Invalid payloads, disabled tools, scope violations
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.db.models import ToolDefinition
from src.tools.validation import (
    ToolValidationError,
    ToolValidationService,
)


class TestToolValidationService:
    """Tests for ToolValidationService."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock tool repository."""
        return AsyncMock()

    @pytest.fixture
    def validation_service(self, mock_repository):
        """Create a ToolValidationService instance."""
        return ToolValidationService(mock_repository)

    @pytest.fixture
    def sample_tool_global(self):
        """Create a sample global tool definition."""
        tool = MagicMock(spec=ToolDefinition)
        tool.tool_id = 1
        tool.name = "Global Tool"
        tool.tenant_id = None  # Global tool
        tool.type = "http"
        tool.config = {
            "description": "Global HTTP tool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "param1": {"type": "string"},
                    "param2": {"type": "number"},
                },
                "required": ["param1"],
            },
            "outputSchema": {"type": "object"},
            "authType": "none",
            "endpointConfig": {
                "url": "https://api.example.com/tool",
                "method": "POST",
            },
            "tenantScope": "global",
        }
        return tool

    @pytest.fixture
    def sample_tool_tenant_scoped(self):
        """Create a sample tenant-scoped tool definition."""
        tool = MagicMock(spec=ToolDefinition)
        tool.tool_id = 2
        tool.name = "Tenant Tool"
        tool.tenant_id = "TENANT_001"  # Tenant-scoped
        tool.type = "http"
        tool.config = {
            "description": "Tenant-scoped HTTP tool",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "param": {"type": "string"},
                },
                "required": ["param"],
            },
            "outputSchema": {"type": "object"},
            "authType": "api_key",
            "endpointConfig": {
                "url": "https://tenant1.example.com/tool",
                "method": "POST",
            },
            "tenantScope": "tenant",
        }
        return tool

    @pytest.mark.asyncio
    async def test_validate_payload_valid(self, validation_service, mock_repository, sample_tool_global):
        """Test validating a valid payload."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        payload = {"param1": "value1", "param2": 42}
        
        # Should not raise
        await validation_service.validate_payload(1, payload, tenant_id="TENANT_001")

    @pytest.mark.asyncio
    async def test_validate_payload_missing_required_field(self, validation_service, mock_repository, sample_tool_global):
        """Test validating payload with missing required field."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        payload = {"param2": 42}  # Missing required param1
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.validate_payload(1, payload, tenant_id="TENANT_001")
        assert "validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_payload_invalid_type(self, validation_service, mock_repository, sample_tool_global):
        """Test validating payload with invalid type."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        payload = {"param1": 123, "param2": "not a number"}  # param1 should be string, param2 should be number
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.validate_payload(1, payload, tenant_id="TENANT_001")
        assert "validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_payload_tool_not_found(self, validation_service, mock_repository):
        """Test validating payload for non-existent tool."""
        mock_repository.get_tool.return_value = None
        
        payload = {"param1": "value1"}
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.validate_payload(999, payload, tenant_id="TENANT_001")
        assert "not found" in str(exc_info.value).lower() or "access denied" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_payload_no_schema(self, validation_service, mock_repository):
        """Test validating payload for tool without input_schema (backward compatibility)."""
        tool = MagicMock(spec=ToolDefinition)
        tool.tool_id = 3
        tool.name = "Legacy Tool"
        tool.tenant_id = None
        tool.config = {"endpoint": "https://api.example.com/legacy"}  # No inputSchema
        
        mock_repository.get_tool.return_value = tool
        
        payload = {"any": "payload"}
        
        # Should not raise (backward compatibility)
        await validation_service.validate_payload(3, payload, tenant_id="TENANT_001")

    @pytest.mark.asyncio
    async def test_check_tool_enabled_default_enabled(self, validation_service, mock_repository, sample_tool_global):
        """Test that tools are enabled by default."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        enabled = await validation_service.check_tool_enabled("TENANT_001", 1)
        assert enabled is True

    @pytest.mark.asyncio
    async def test_check_tool_enabled_explicitly_disabled(self, validation_service, mock_repository, sample_tool_global):
        """Test checking a disabled tool."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        # Disable the tool
        validation_service.set_tool_enabled("TENANT_001", 1, False)
        
        enabled = await validation_service.check_tool_enabled("TENANT_001", 1)
        assert enabled is False

    @pytest.mark.asyncio
    async def test_check_tool_enabled_tool_not_found(self, validation_service, mock_repository):
        """Test checking enablement for non-existent tool."""
        mock_repository.get_tool.return_value = None
        
        enabled = await validation_service.check_tool_enabled("TENANT_001", 999)
        assert enabled is False

    @pytest.mark.asyncio
    async def test_check_tool_enabled_invalid_tenant_id(self, validation_service):
        """Test checking enablement with invalid tenant_id."""
        with pytest.raises(ValueError) as exc_info:
            await validation_service.check_tool_enabled("", 1)
        assert "tenant_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_tool_enabled_invalid_tool_id(self, validation_service):
        """Test checking enablement with invalid tool_id."""
        with pytest.raises(ValueError) as exc_info:
            await validation_service.check_tool_enabled("TENANT_001", 0)
        assert "tool_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_tenant_scope_global_tool(self, validation_service, mock_repository, sample_tool_global):
        """Test tenant scope check for global tool (accessible to all tenants)."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        # Should not raise - global tools accessible to all tenants
        await validation_service.check_tenant_scope("TENANT_001", 1)
        await validation_service.check_tenant_scope("TENANT_002", 1)

    @pytest.mark.asyncio
    async def test_check_tenant_scope_tenant_scoped_correct_tenant(self, validation_service, mock_repository, sample_tool_tenant_scoped):
        """Test tenant scope check for tenant-scoped tool with correct tenant."""
        mock_repository.get_tool.return_value = sample_tool_tenant_scoped
        
        # Should not raise - correct tenant
        await validation_service.check_tenant_scope("TENANT_001", 2)

    @pytest.mark.asyncio
    async def test_check_tenant_scope_tenant_scoped_wrong_tenant(self, validation_service, mock_repository, sample_tool_tenant_scoped):
        """Test tenant scope check for tenant-scoped tool with wrong tenant (scope violation)."""
        # Mock repository to return tool when queried with correct tenant
        # but we'll query with wrong tenant to test scope violation
        async def get_tool_side_effect(tool_id, tenant_id):
            if tool_id == 2 and tenant_id == "TENANT_001":
                return sample_tool_tenant_scoped
            return None
        
        mock_repository.get_tool.side_effect = get_tool_side_effect
        
        # Try to access tenant-scoped tool with wrong tenant
        # The repository should return None, but let's test the scope check logic
        # by manually setting up the scenario
        mock_repository.get_tool.return_value = sample_tool_tenant_scoped
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.check_tenant_scope("TENANT_002", 2)
        assert "tenant-scoped" in str(exc_info.value).lower() or "access denied" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_tenant_scope_tool_not_found(self, validation_service, mock_repository):
        """Test tenant scope check for non-existent tool."""
        mock_repository.get_tool.return_value = None
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.check_tenant_scope("TENANT_001", 999)
        assert "not found" in str(exc_info.value).lower() or "access denied" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_tenant_scope_invalid_tenant_id(self, validation_service):
        """Test tenant scope check with invalid tenant_id."""
        with pytest.raises(ValueError) as exc_info:
            await validation_service.check_tenant_scope("", 1)
        assert "tenant_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_check_tenant_scope_invalid_tool_id(self, validation_service):
        """Test tenant scope check with invalid tool_id."""
        with pytest.raises(ValueError) as exc_info:
            await validation_service.check_tenant_scope("TENANT_001", 0)
        assert "tool_id" in str(exc_info.value).lower()

    def test_redact_secrets_password(self, validation_service):
        """Test redacting password fields."""
        payload = {
            "username": "user1",
            "password": "secret123",
            "param": "value",
        }
        
        redacted = validation_service.redact_secrets(payload)
        
        assert redacted["username"] == "user1"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["param"] == "value"
        # Original should be unchanged
        assert payload["password"] == "secret123"

    def test_redact_secrets_api_key(self, validation_service):
        """Test redacting API key fields."""
        payload = {
            "action": "test",
            "api_key": "sk-1234567890",
            "apiKey": "another-key",
            "api_secret": "secret-value",
        }
        
        redacted = validation_service.redact_secrets(payload)
        
        assert redacted["action"] == "test"
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["apiKey"] == "[REDACTED]"
        assert redacted["api_secret"] == "[REDACTED]"

    def test_redact_secrets_token(self, validation_service):
        """Test redacting token fields."""
        payload = {
            "token": "abc123",
            "auth_token": "xyz789",
            "access_token": "def456",
            "refreshToken": "ghi789",
        }
        
        redacted = validation_service.redact_secrets(payload)
        
        assert redacted["token"] == "[REDACTED]"
        assert redacted["auth_token"] == "[REDACTED]"
        assert redacted["access_token"] == "[REDACTED]"
        assert redacted["refreshToken"] == "[REDACTED]"

    def test_redact_secrets_nested(self, validation_service):
        """Test redacting secrets in nested structures."""
        payload = {
            "config": {
                "api_key": "secret-key",
                "normal_field": "value",
            },
            "credentials": {
                "password": "pass123",
                "username": "user1",
            },
        }
        
        redacted = validation_service.redact_secrets(payload)
        
        assert redacted["config"]["api_key"] == "[REDACTED]"
        assert redacted["config"]["normal_field"] == "value"
        assert redacted["credentials"]["password"] == "[REDACTED]"
        assert redacted["credentials"]["username"] == "user1"

    def test_redact_secrets_list(self, validation_service):
        """Test redacting secrets in list structures."""
        payload = {
            "items": [
                {"name": "item1", "secret": "value1"},
                {"name": "item2", "api_key": "key2"},
            ],
        }
        
        redacted = validation_service.redact_secrets(payload)
        
        assert redacted["items"][0]["name"] == "item1"
        assert redacted["items"][0]["secret"] == "[REDACTED]"
        assert redacted["items"][1]["name"] == "item2"
        assert redacted["items"][1]["api_key"] == "[REDACTED]"

    def test_redact_secrets_no_secrets(self, validation_service):
        """Test redacting payload with no secret fields."""
        payload = {
            "param1": "value1",
            "param2": 42,
            "nested": {
                "field": "data",
            },
        }
        
        redacted = validation_service.redact_secrets(payload)
        
        # Should be identical (no redaction needed)
        assert redacted == payload
        # But should be a copy
        assert redacted is not payload

    def test_redact_secrets_non_dict(self, validation_service):
        """Test redacting non-dict payload."""
        payload = "not a dict"
        
        redacted = validation_service.redact_secrets(payload)
        
        assert redacted == payload

    @pytest.mark.asyncio
    async def test_validate_tool_access_comprehensive(self, validation_service, mock_repository, sample_tool_global):
        """Test comprehensive validation (all checks)."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        payload = {"param1": "value1", "param2": 42}
        
        # Should not raise - all checks pass
        await validation_service.validate_tool_access("TENANT_001", 1, payload)

    @pytest.mark.asyncio
    async def test_validate_tool_access_disabled_tool(self, validation_service, mock_repository, sample_tool_global):
        """Test comprehensive validation with disabled tool."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        # Disable the tool
        validation_service.set_tool_enabled("TENANT_001", 1, False)
        
        payload = {"param1": "value1"}
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.validate_tool_access("TENANT_001", 1, payload)
        assert "disabled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_tool_access_invalid_payload(self, validation_service, mock_repository, sample_tool_global):
        """Test comprehensive validation with invalid payload."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        payload = {"param2": 42}  # Missing required param1
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.validate_tool_access("TENANT_001", 1, payload)
        assert "validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_tool_access_scope_violation(self, validation_service, mock_repository, sample_tool_tenant_scoped):
        """Test comprehensive validation with scope violation."""
        # Setup: tool is tenant-scoped to TENANT_001, but accessed by TENANT_002
        # The repository should return None when queried with wrong tenant
        async def get_tool_side_effect(tool_id, tenant_id):
            if tool_id == 2 and tenant_id == "TENANT_001":
                return sample_tool_tenant_scoped
            return None
        
        mock_repository.get_tool.side_effect = get_tool_side_effect
        
        payload = {"param": "value"}
        
        with pytest.raises(ToolValidationError) as exc_info:
            await validation_service.validate_tool_access("TENANT_002", 2, payload)
        assert "not found" in str(exc_info.value).lower() or "access denied" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_set_tool_enabled(self, validation_service, mock_repository, sample_tool_global):
        """Test setting tool enablement status."""
        mock_repository.get_tool.return_value = sample_tool_global
        
        # Initially enabled (default)
        assert await validation_service.check_tool_enabled("TENANT_001", 1) is True
        
        # Disable
        validation_service.set_tool_enabled("TENANT_001", 1, False)
        assert await validation_service.check_tool_enabled("TENANT_001", 1) is False
        
        # Re-enable
        validation_service.set_tool_enabled("TENANT_001", 1, True)
        assert await validation_service.check_tool_enabled("TENANT_001", 1) is True








