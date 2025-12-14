"""
Tool Validation Service for Phase 8.

Validates tool payloads, enforces tenant isolation, and handles secret redaction.
Reference: docs/phase8-tools-mvp.md Section 4.1
"""

import logging
import re
from typing import Any, Optional

try:
    import jsonschema
    from jsonschema import ValidationError as JSONSchemaValidationError
except ImportError:
    jsonschema = None
    JSONSchemaValidationError = Exception

from src.infrastructure.db.models import ToolDefinition
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
from src.models.tool_definition_phase8 import ToolDefinitionRequest, TenantScope

logger = logging.getLogger(__name__)


class ToolValidationError(Exception):
    """Raised when tool validation fails."""

    pass


class ToolValidationService:
    """
    Service for validating tool definitions and payloads.
    
    Provides:
    - Payload validation against input_schema (JSON Schema)
    - Tool enablement checking per tenant
    - Tenant scope validation
    - Secret redaction for logging/events
    """

    def __init__(
        self,
        tool_repository: ToolDefinitionRepository,
        enablement_repository: Optional[ToolEnablementRepository] = None,
    ):
        """
        Initialize the validation service.
        
        Args:
            tool_repository: Repository for accessing tool definitions
            enablement_repository: Optional repository for tool enablement (if None, uses in-memory dict for backward compatibility)
        """
        self.tool_repository = tool_repository
        self.enablement_repository = enablement_repository
        
        # Fallback: in-memory enablement tracking for backward compatibility
        # Format: {tenant_id: {tool_id: enabled}}
        self._tool_enablement: dict[str, dict[int, bool]] = {}
        
        if jsonschema is None:
            logger.warning(
                "jsonschema library not installed. JSON Schema validation will be limited. "
                "Install with: pip install jsonschema"
            )

    async def validate_payload(
        self, tool_id: int, payload: dict[str, Any], tenant_id: Optional[str] = None
    ) -> None:
        """
        Validate payload against tool's input_schema using JSON Schema.
        
        Args:
            tool_id: Tool identifier
            payload: Payload to validate
            tenant_id: Optional tenant identifier for tenant isolation
            
        Raises:
            ToolValidationError: If payload validation fails
            ValueError: If tool_id is invalid or tool not found
        """
        if tool_id < 1:
            raise ValueError(f"Invalid tool_id: {tool_id}")
        
        # Get tool definition with tenant isolation
        tool = await self.tool_repository.get_tool(tool_id=tool_id, tenant_id=tenant_id)
        if tool is None:
            raise ToolValidationError(
                f"Tool {tool_id} not found or access denied for tenant {tenant_id}"
            )
        
        # Extract input_schema from config
        config = tool.config if isinstance(tool.config, dict) else {}
        input_schema = config.get("inputSchema") or config.get("input_schema")
        
        if not input_schema:
            # For backward compatibility: if no input_schema, allow any payload
            logger.warning(
                f"Tool {tool_id} ({tool.name}) has no input_schema. "
                "Skipping payload validation for backward compatibility."
            )
            return
        
        # Validate using JSON Schema
        if jsonschema is None:
            logger.warning(
                f"jsonschema not available. Skipping validation for tool {tool_id}. "
                "Payload structure not validated."
            )
            return
        
        try:
            jsonschema.validate(instance=payload, schema=input_schema)
            logger.debug(f"Payload validation passed for tool {tool_id}")
        except JSONSchemaValidationError as e:
            error_msg = f"Payload validation failed for tool {tool_id}: {e.message}"
            if e.path:
                error_msg += f" (path: {'/'.join(str(p) for p in e.path)})"
            logger.warning(error_msg)
            raise ToolValidationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error during payload validation for tool {tool_id}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise ToolValidationError(error_msg) from e

    async def check_tool_enabled(self, tenant_id: str, tool_id: int) -> bool:
        """
        Check if tool is enabled for the tenant.
        
        For MVP: Tools are enabled by default unless explicitly disabled.
        In production, this would check a database table or policy configuration.
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            
        Returns:
            True if tool is enabled, False otherwise
            
        Raises:
            ValueError: If tenant_id is empty or tool_id is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required and cannot be empty")
        
        if tool_id < 1:
            raise ValueError(f"Invalid tool_id: {tool_id}")
        
        # Check if tool exists and is accessible to tenant
        tool = await self.tool_repository.get_tool(tool_id=tool_id, tenant_id=tenant_id)
        if tool is None:
            logger.warning(
                f"Tool {tool_id} not found or not accessible to tenant {tenant_id}"
            )
            return False
        
        # Use repository if available (Phase 8 P8-7)
        if self.enablement_repository is not None:
            return await self.enablement_repository.is_enabled(tenant_id, tool_id)
        
        # Fallback: Check in-memory enablement (for backward compatibility)
        tenant_enablement = self._tool_enablement.get(tenant_id, {})
        enabled = tenant_enablement.get(tool_id, True)  # Default to enabled
        
        if not enabled:
            logger.debug(f"Tool {tool_id} is disabled for tenant {tenant_id}")
        
        return enabled

    def set_tool_enabled(self, tenant_id: str, tool_id: int, enabled: bool) -> None:
        """
        Set tool enablement status for a tenant.
        
        For MVP: This is an in-memory operation.
        In production, this would update a database table.
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            enabled: Enablement status
        """
        if tenant_id not in self._tool_enablement:
            self._tool_enablement[tenant_id] = {}
        self._tool_enablement[tenant_id][tool_id] = enabled
        logger.info(
            f"Tool {tool_id} {'enabled' if enabled else 'disabled'} for tenant {tenant_id}"
        )

    async def check_tenant_scope(
        self, tenant_id: str, tool_id: int
    ) -> None:
        """
        Check tenant scope restrictions for tool access.
        
        Rules:
        - Global tools (tenant_id=None in DB) are accessible to all tenants
        - Tenant-scoped tools (tenant_id set in DB) are only accessible to that tenant
        
        Args:
            tenant_id: Tenant identifier requesting access
            tool_id: Tool identifier
            
        Raises:
            ToolValidationError: If tenant scope check fails
            ValueError: If tenant_id is empty or tool_id is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required and cannot be empty")
        
        if tool_id < 1:
            raise ValueError(f"Invalid tool_id: {tool_id}")
        
        # Get tool definition with tenant filtering (repository handles scope)
        tool = await self.tool_repository.get_tool(tool_id=tool_id, tenant_id=tenant_id)
        if tool is None:
            # Tool not found or not accessible due to scope
            # Try to get tool without tenant filter to provide better error message
            tool_no_tenant = await self.tool_repository.get_tool(tool_id=tool_id, tenant_id=None)
            if tool_no_tenant is not None and tool_no_tenant.tenant_id is not None:
                # Tool exists but is tenant-scoped to different tenant
                raise ToolValidationError(
                    f"Tool {tool_id} is tenant-scoped to '{tool_no_tenant.tenant_id}', "
                    f"but access requested by tenant '{tenant_id}'"
                )
            else:
                # Tool doesn't exist
                raise ToolValidationError(
                    f"Tool {tool_id} not found or access denied for tenant {tenant_id}"
                )
        
        # If we get here, tool is accessible (either global or tenant-scoped to requesting tenant)
        logger.debug(f"Tenant scope check passed for tool {tool_id}, tenant {tenant_id}")

    def redact_secrets(
        self, payload: dict[str, Any], tool_definition: Optional[ToolDefinition] = None
    ) -> dict[str, Any]:
        """
        Redact secrets from payload for safe logging/event storage.
        
        Identifies common secret field names and redacts their values.
        For MVP: Simple pattern matching on field names.
        In production: Could use tool definition metadata to identify secret fields.
        
        Args:
            payload: Payload dictionary to redact
            tool_definition: Optional tool definition for context
            
        Returns:
            Payload with secrets redacted (new dictionary, original unchanged)
        """
        if not isinstance(payload, dict):
            return payload
        
        # Common secret field name patterns (case-insensitive)
        secret_patterns = [
            r"password",
            r"passwd",
            r"secret",
            r"api[_-]?key",
            r"apikey",
            r"token",
            r"auth[_-]?token",
            r"access[_-]?token",
            r"refresh[_-]?token",
            r"credential",
            r"private[_-]?key",
            r"privatekey",
            r"apisecret",
            r"client[_-]?secret",
        ]
        
        # Compile patterns for efficiency
        compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in secret_patterns]
        
        def should_redact(key: str) -> bool:
            """Check if a key should be redacted."""
            return any(pattern.search(key) for pattern in compiled_patterns)
        
        def redact_value(value: Any) -> Any:
            """Recursively redact values in nested structures."""
            if isinstance(value, dict):
                return {
                    k: "[REDACTED]" if should_redact(k) else redact_value(v)
                    for k, v in value.items()
                }
            elif isinstance(value, list):
                return [redact_value(item) for item in value]
            else:
                return value
        
        # Create redacted copy
        # Always recurse into nested structures to check for secrets at any level
        redacted = {}
        for key, value in payload.items():
            if should_redact(key):
                # Key matches secret pattern - redact the value
                # But if value is a dict/list, we still need to recurse to redact nested secrets
                if isinstance(value, (dict, list)):
                    redacted[key] = redact_value(value)
                else:
                    redacted[key] = "[REDACTED]"
            else:
                # Key doesn't match - recurse to check nested structures
                redacted[key] = redact_value(value)
        
        return redacted

    async def validate_tool_access(
        self, tenant_id: str, tool_id: int, payload: Optional[dict[str, Any]] = None
    ) -> None:
        """
        Comprehensive validation: combines scope check, enablement check, and payload validation.
        
        This is a convenience method that performs all validation checks in the correct order.
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            payload: Optional payload to validate
            
        Raises:
            ToolValidationError: If any validation check fails
            ValueError: If parameters are invalid
        """
        # 1. Check tenant scope first (fastest check)
        await self.check_tenant_scope(tenant_id, tool_id)
        
        # 2. Check if tool is enabled
        if not await self.check_tool_enabled(tenant_id, tool_id):
            raise ToolValidationError(
                f"Tool {tool_id} is disabled for tenant {tenant_id}"
            )
        
        # 3. Validate payload if provided
        if payload is not None:
            await self.validate_payload(tool_id, payload, tenant_id=tenant_id)

