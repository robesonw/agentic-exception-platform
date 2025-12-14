"""
Phase 8 Tool Definition schema models with strict validation.

Enhances tool definitions with required fields:
- name, type, description
- input_schema (JSON Schema)
- output_schema
- auth_type (none, api_key, oauth_stub)
- endpoint_config (for http tools only)
- tenant_scope (global or tenant-specific)

Reference: docs/phase8-tools-mvp.md Section 2 (In Scope)
"""

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


class AuthType(str, Enum):
    """Authentication type for tools."""

    NONE = "none"
    API_KEY = "api_key"
    OAUTH_STUB = "oauth_stub"


class TenantScope(str, Enum):
    """Tenant scope for tools."""

    GLOBAL = "global"
    TENANT = "tenant"


class EndpointConfig(BaseModel):
    """Endpoint configuration for HTTP tools."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )

    url: str = Field(..., min_length=1, description="Endpoint URL")
    method: str = Field(default="POST", description="HTTP method (GET, POST, PUT, DELETE)")
    headers: dict[str, str] = Field(default_factory=dict, description="Additional HTTP headers")
    timeout_seconds: Optional[float] = Field(
        default=None, ge=0.0, description="Request timeout in seconds"
    )


class ToolDefinitionConfig(BaseModel):
    """
    Phase 8 Tool Definition configuration schema.
    
    This model validates the structure of the 'config' JSONB field in the tool_definition table.
    All required fields must be present and validated.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    description: str = Field(..., min_length=1, description="Tool description")
    input_schema: dict[str, Any] = Field(
        ..., alias="inputSchema", description="JSON Schema for tool input parameters"
    )
    output_schema: dict[str, Any] = Field(
        ..., alias="outputSchema", description="JSON Schema for tool output"
    )
    auth_type: AuthType = Field(
        ..., alias="authType", description="Authentication type: none, api_key, or oauth_stub"
    )
    endpoint_config: Optional[EndpointConfig] = Field(
        None, alias="endpointConfig", description="Endpoint configuration (required for http tools)"
    )
    tenant_scope: TenantScope = Field(
        default=TenantScope.TENANT,
        alias="tenantScope",
        description="Tenant scope: global or tenant",
    )

    @field_validator("input_schema", "output_schema", mode="before")
    @classmethod
    def validate_schema_dict(cls, v: Any) -> dict[str, Any]:
        """
        Validate that input_schema and output_schema are dictionaries.
        
        Args:
            v: Value to validate
            
        Returns:
            Validated dictionary
            
        Raises:
            ValueError: If value is not a dictionary
        """
        if not isinstance(v, dict):
            raise ValueError("Schema must be a dictionary (JSON Schema)")
        return v

    @model_validator(mode="after")
    def validate_endpoint_config_for_http(self) -> "ToolDefinitionConfig":
        """
        Validate that endpoint_config is provided for http tools.
        
        This validator is called after all field validators.
        It checks that if the tool type is 'http' (checked in parent model),
        then endpoint_config must be provided.
        
        Note: The tool 'type' field is not in this model (it's in the parent ToolDefinitionRequest),
        so we rely on the API layer to pass the type for validation.
        """
        return self

    @classmethod
    def validate_for_tool_type(cls, tool_type: str, config_data: dict[str, Any]) -> "ToolDefinitionConfig":
        """
        Validate config for a specific tool type.
        
        Args:
            tool_type: Tool type (e.g., 'http', 'webhook', 'email', 'workflow')
            config_data: Configuration data to validate
            
        Returns:
            Validated ToolDefinitionConfig
            
        Raises:
            ValueError: If validation fails (e.g., endpoint_config missing for http tools)
        """
        # Parse the config
        config = cls.model_validate(config_data)
        
        # For http tools, endpoint_config is required
        if tool_type.lower() in ("http", "rest", "webhook"):
            if config.endpoint_config is None:
                raise ValueError(
                    f"endpoint_config is required for tool type '{tool_type}'. "
                    "HTTP tools must specify endpoint configuration."
                )
        
        return config


class ToolDefinitionRequest(BaseModel):
    """
    Phase 8 Tool Definition request model for API create/update operations.
    
    This model validates the full tool definition including name, type, and config.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    name: str = Field(..., min_length=1, description="Tool name")
    type: str = Field(..., min_length=1, description="Tool type (e.g., 'http', 'webhook', 'email', 'workflow', 'dummy')")
    description: str = Field(..., min_length=1, description="Tool description")
    input_schema: dict[str, Any] = Field(
        ..., alias="inputSchema", description="JSON Schema for tool input parameters"
    )
    output_schema: dict[str, Any] = Field(
        ..., alias="outputSchema", description="JSON Schema for tool output"
    )
    auth_type: AuthType = Field(
        ..., alias="authType", description="Authentication type: none, api_key, or oauth_stub"
    )
    endpoint_config: Optional[EndpointConfig] = Field(
        None, alias="endpointConfig", description="Endpoint configuration (required for http tools)"
    )
    tenant_scope: TenantScope = Field(
        default=TenantScope.TENANT,
        alias="tenantScope",
        description="Tenant scope: global or tenant",
    )

    @field_validator("input_schema", "output_schema", mode="before")
    @classmethod
    def validate_schema_dict(cls, v: Any) -> dict[str, Any]:
        """
        Validate that input_schema and output_schema are dictionaries.
        
        Args:
            v: Value to validate
            
        Returns:
            Validated dictionary
            
        Raises:
            ValueError: If value is not a dictionary
        """
        if not isinstance(v, dict):
            raise ValueError("Schema must be a dictionary (JSON Schema)")
        return v

    @model_validator(mode="after")
    def validate_endpoint_config_for_http(self) -> "ToolDefinitionRequest":
        """
        Validate that endpoint_config is provided for http tools.
        
        Returns:
            Self after validation
            
        Raises:
            ValueError: If endpoint_config is missing for http tools
        """
        # Check if this is an HTTP tool type
        http_types = ("http", "rest", "webhook")
        if self.type.lower() in http_types:
            if self.endpoint_config is None:
                raise ValueError(
                    f"endpoint_config is required for tool type '{self.type}'. "
                    "HTTP tools must specify endpoint configuration."
                )
        
        return self

    def to_config_dict(self) -> dict[str, Any]:
        """
        Convert to config dictionary for storage in database.
        
        Returns:
            Dictionary suitable for storing in tool_definition.config JSONB field
        """
        return {
            "description": self.description,
            "inputSchema": self.input_schema,
            "outputSchema": self.output_schema,
            "authType": self.auth_type.value,
            "endpointConfig": self.endpoint_config.model_dump(exclude_none=True, by_alias=True) if self.endpoint_config else None,
            "tenantScope": self.tenant_scope.value,
        }

    @classmethod
    def from_config_dict(
        cls, name: str, type: str, config: dict[str, Any]
    ) -> "ToolDefinitionRequest":
        """
        Create ToolDefinitionRequest from database fields.
        
        Args:
            name: Tool name
            type: Tool type
            config: Config dictionary from database
            
        Returns:
            ToolDefinitionRequest instance
            
        Raises:
            ValueError: If config structure is invalid
        """
        # Handle backward compatibility: if config doesn't have new fields, try to infer
        # This allows existing tools to work
        if "description" not in config:
            # Try to use old structure
            if "endpoint" in config:
                # Old format: convert to new format
                config = {
                    "description": config.get("description", f"Tool {name}"),
                    "inputSchema": config.get("parameters", {}),
                    "outputSchema": config.get("outputSchema", {"type": "object"}),
                    "authType": config.get("auth", {}).get("type", "none") if isinstance(config.get("auth"), dict) else "none",
                    "endpointConfig": {
                        "url": config["endpoint"],
                        "method": config.get("method", "POST"),
                        "headers": config.get("headers", {}),
                        "timeoutSeconds": config.get("timeoutSeconds"),
                    } if "endpoint" in config else None,
                    "tenantScope": "tenant",  # Default to tenant scope
                }
            else:
                raise ValueError(
                    f"Cannot convert old config format for tool '{name}'. "
                    "Missing required fields: description, inputSchema, outputSchema, authType"
                )
        
        # Normalize field names (support both camelCase and snake_case)
        endpoint_config_data = config.get("endpointConfig") or config.get("endpoint_config")
        endpoint_config_obj = None
        if endpoint_config_data:
            if isinstance(endpoint_config_data, dict):
                # Filter out None values to avoid Pydantic validation errors
                endpoint_config_clean = {k: v for k, v in endpoint_config_data.items() if v is not None}
                endpoint_config_obj = EndpointConfig(**endpoint_config_clean)
            elif isinstance(endpoint_config_data, EndpointConfig):
                endpoint_config_obj = endpoint_config_data
        
        normalized_config = {
            "description": config.get("description") or config.get("description", ""),
            "inputSchema": config.get("inputSchema") or config.get("input_schema", {}),
            "outputSchema": config.get("outputSchema") or config.get("output_schema", {}),
            "authType": config.get("authType") or config.get("auth_type", "none"),
            "endpointConfig": endpoint_config_obj,
            "tenantScope": config.get("tenantScope") or config.get("tenant_scope", "tenant"),
        }
        
        # Create the request model
        return cls(
            name=name,
            type=type,
            description=normalized_config["description"],
            input_schema=normalized_config["inputSchema"],
            output_schema=normalized_config["outputSchema"],
            auth_type=AuthType(normalized_config["authType"].lower()) if isinstance(normalized_config["authType"], str) else normalized_config["authType"],
            endpoint_config=normalized_config["endpointConfig"],
            tenant_scope=TenantScope(normalized_config["tenantScope"].lower()) if isinstance(normalized_config["tenantScope"], str) else normalized_config["tenantScope"],
        )

