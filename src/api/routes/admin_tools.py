"""
Admin API routes for Tool Management.

Phase 2: Tool registration, override, listing, and disable functionality.

Matches specification from phase2-mvp-issues.md Issue 39.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path as PathParam
from pydantic import BaseModel, Field

from src.domainpack.loader import DomainPackRegistry
from src.models.domain_pack import ToolDefinition
from src.models.tenant_policy import TenantPolicyPack
from src.tenantpack.loader import TenantPolicyRegistry
from src.tools.registry import AllowListEnforcer, ToolRegistry, ToolRegistryError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/tools", tags=["admin-tools"])

# Global instance (would be injected via dependency in production)
_tool_registry: ToolRegistry | None = None
_domain_pack_registry: DomainPackRegistry | None = None
_tenant_policy_registry: TenantPolicyRegistry | None = None


def set_tool_registry(registry: ToolRegistry) -> None:
    """Set the tool registry (for dependency injection)."""
    global _tool_registry
    _tool_registry = registry


def set_domain_pack_registry(registry: DomainPackRegistry) -> None:
    """Set the domain pack registry (for dependency injection)."""
    global _domain_pack_registry
    _domain_pack_registry = registry


def set_tenant_policy_registry(registry: TenantPolicyRegistry) -> None:
    """Set the tenant policy registry (for dependency injection)."""
    global _tenant_policy_registry
    _tenant_policy_registry = registry


def get_tool_registry() -> ToolRegistry:
    """Get the tool registry instance."""
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry()
    return _tool_registry


def get_domain_pack_registry() -> DomainPackRegistry:
    """Get the domain pack registry instance."""
    global _domain_pack_registry
    if _domain_pack_registry is None:
        _domain_pack_registry = DomainPackRegistry()
    return _domain_pack_registry


def get_tenant_policy_registry() -> TenantPolicyRegistry:
    """Get the tenant policy registry instance."""
    global _tenant_policy_registry
    if _tenant_policy_registry is None:
        _tenant_policy_registry = TenantPolicyRegistry()
    return _tenant_policy_registry


class ToolRegistrationRequest(BaseModel):
    """Request for registering or overriding a tool."""

    model_config = {"populate_by_name": True}

    tool_name: str = Field(..., alias="toolName", min_length=1, description="Tool name")
    description: str = Field(..., min_length=1, description="Tool description")
    endpoint: str = Field(..., min_length=1, description="Tool endpoint URL")
    parameters: dict[str, Any] = Field(default_factory=dict, description="Tool parameters schema")
    version: str = Field(default="1.0.0", description="Tool version")
    timeout_seconds: float | None = Field(
        None, alias="timeoutSeconds", ge=0.0, description="Request timeout in seconds"
    )
    max_retries: int = Field(default=3, alias="maxRetries", ge=0, description="Maximum number of retry attempts")


class ToolRegistrationResponse(BaseModel):
    """Response for tool registration."""

    tool_name: str = Field(..., alias="toolName")
    domain_name: str = Field(..., alias="domainName")
    version: str
    message: str
    registered: bool = Field(..., description="Whether tool was registered successfully")
    is_override: bool = Field(..., alias="isOverride", description="Whether this was an override of existing tool")


class ToolInfo(BaseModel):
    """Information about a tool."""

    tool_name: str = Field(..., alias="toolName")
    description: str
    endpoint: str
    version: str
    timeout_seconds: float | None = Field(None, alias="timeoutSeconds")
    max_retries: int = Field(..., alias="maxRetries")
    is_allowed: bool = Field(..., alias="isAllowed", description="Whether tool is in allow-list")
    is_blocked: bool = Field(..., alias="isBlocked", description="Whether tool is in block-list")
    is_disabled: bool = Field(..., alias="isDisabled", description="Whether tool is disabled")


class ToolListResponse(BaseModel):
    """Response for listing tools."""

    tenant_id: str = Field(..., alias="tenantId")
    domain_name: str = Field(..., alias="domainName")
    tools: list[ToolInfo]
    total: int
    allowed_count: int = Field(..., alias="allowedCount")
    blocked_count: int = Field(..., alias="blockedCount")
    disabled_count: int = Field(..., alias="disabledCount")


class DisableToolRequest(BaseModel):
    """Request for disabling a tool."""

    tool_name: str = Field(..., alias="toolName", min_length=1, description="Tool name to disable")


class DisableToolResponse(BaseModel):
    """Response for tool disable operation."""

    tool_name: str = Field(..., alias="toolName")
    domain_name: str = Field(..., alias="domainName")
    disabled: bool
    message: str


# Track disabled tools per tenant:domain
_disabled_tools: dict[str, set[str]] = {}  # {f"{tenant_id}:{domain_name}": {tool_name, ...}}


def _get_disabled_key(tenant_id: str, domain_name: str) -> str:
    """Get key for disabled tools storage."""
    return f"{tenant_id}:{domain_name}"


def _is_tool_disabled(tenant_id: str, domain_name: str, tool_name: str) -> bool:
    """Check if a tool is disabled."""
    key = _get_disabled_key(tenant_id, domain_name)
    return tool_name in _disabled_tools.get(key, set())


def _disable_tool(tenant_id: str, domain_name: str, tool_name: str) -> None:
    """Disable a tool."""
    key = _get_disabled_key(tenant_id, domain_name)
    if key not in _disabled_tools:
        _disabled_tools[key] = set()
    _disabled_tools[key].add(tool_name)


def _enable_tool(tenant_id: str, domain_name: str, tool_name: str) -> None:
    """Enable a tool (remove from disabled set)."""
    key = _get_disabled_key(tenant_id, domain_name)
    if key in _disabled_tools:
        _disabled_tools[key].discard(tool_name)


@router.post("/{tenant_id}/{domain_name}", response_model=ToolRegistrationResponse)
async def register_tool(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
    domain_name: str = PathParam(..., description="Domain name"),
    request: ToolRegistrationRequest = ...,
) -> ToolRegistrationResponse:
    """
    Register or override a tool definition for a tenant and domain.
    
    The tool must exist in the Domain Pack for the tenant. This endpoint allows
    overriding tool properties (timeout, retries, etc.) while maintaining the
    canonical definition from the Domain Pack.
    
    Args:
        tenant_id: Tenant identifier
        domain_name: Domain name
        request: Tool registration request
        
    Returns:
        ToolRegistrationResponse with registration status
        
    Raises:
        HTTPException: If registration fails
    """
    tool_registry = get_tool_registry()
    domain_pack_registry = get_domain_pack_registry()
    
    # Get domain pack to validate tool exists
    domain_pack = domain_pack_registry.get_latest(domain_name=domain_name, tenant_id=tenant_id)
    if not domain_pack:
        raise HTTPException(
            status_code=404,
            detail=f"Domain Pack '{domain_name}' not found for tenant '{tenant_id}'. "
                   f"Please upload a Domain Pack first."
        )
    
    # Check if tool exists in domain pack
    if request.tool_name not in domain_pack.tools:
        raise HTTPException(
            status_code=400,
            detail=f"Tool '{request.tool_name}' is not defined in Domain Pack '{domain_name}'. "
                   f"Available tools: {sorted(domain_pack.tools.keys())}"
        )
    
    # Get canonical tool definition
    canonical_tool = domain_pack.tools[request.tool_name]
    
    # Check if this is an override (tool already registered via API)
    # Note: Tools from domain pack registration don't count as "overrides" for this API
    # We check if there's a custom registration by checking if properties differ from canonical
    existing_tool = tool_registry.get(
        tenant_id=tenant_id,
        tool_name=request.tool_name,
        domain_name=domain_name,
    )
    # If tool exists and properties differ from canonical, it's an override
    # Otherwise, if tool exists but matches canonical, it's not an override (just from domain pack)
    is_override = False
    if existing_tool is not None:
        # Check if properties differ from canonical (indicating a previous API override)
        if (existing_tool.timeout_seconds != canonical_tool.timeout_seconds or
            existing_tool.max_retries != canonical_tool.max_retries or
            existing_tool.description != canonical_tool.description):
            is_override = True
    
    # Create tool definition (merge with canonical, allow overrides)
    tool_def = ToolDefinition(
        description=request.description or canonical_tool.description,
        endpoint=request.endpoint or canonical_tool.endpoint,
        parameters=request.parameters or canonical_tool.parameters,
        version=request.version or canonical_tool.version,
        timeout_seconds=request.timeout_seconds if request.timeout_seconds is not None else canonical_tool.timeout_seconds,
        max_retries=request.max_retries if request.max_retries is not None else canonical_tool.max_retries,
    )
    
    # Validate version compatibility
    if not tool_registry._check_version_compatibility(
        canonical_tool.version, tool_def.version, tenant_id, request.tool_name
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Tool version '{tool_def.version}' is incompatible with Domain Pack version '{canonical_tool.version}'"
        )
    
    # Register tool
    try:
        tool_registry.register(
            tenant_id=tenant_id,
            tool_name=request.tool_name,
            tool_definition=tool_def,
        )
        
        # Ensure domain pack is registered in tool registry
        if not tool_registry._domain_packs.get(tenant_id):
            tool_registry.register_domain_pack(tenant_id=tenant_id, domain_pack=domain_pack)
        
        logger.info(
            f"{'Overrode' if is_override else 'Registered'} tool '{request.tool_name}' "
            f"for tenant '{tenant_id}', domain '{domain_name}'"
        )
        
        return ToolRegistrationResponse(
            toolName=request.tool_name,
            domainName=domain_name,
            version=tool_def.version,
            message=f"Tool '{request.tool_name}' {'overridden' if is_override else 'registered'} successfully",
            registered=True,
            isOverride=is_override,
        )
    except ToolRegistryError as e:
        logger.error(f"Failed to register tool: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to register tool: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register tool: {str(e)}"
        )


@router.get("/{tenant_id}/{domain_name}", response_model=ToolListResponse)
async def list_tools(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
    domain_name: str = PathParam(..., description="Domain name"),
) -> ToolListResponse:
    """
    List all tools for a tenant and domain with allowlist status.
    
    Args:
        tenant_id: Tenant identifier
        domain_name: Domain name
        
    Returns:
        ToolListResponse with list of tools and their allowlist status
    """
    tool_registry = get_tool_registry()
    domain_pack_registry = get_domain_pack_registry()
    tenant_policy_registry = get_tenant_policy_registry()
    
    # Get domain pack
    domain_pack = domain_pack_registry.get_latest(domain_name=domain_name, tenant_id=tenant_id)
    if not domain_pack:
        raise HTTPException(
            status_code=404,
            detail=f"Domain Pack '{domain_name}' not found for tenant '{tenant_id}'"
        )
    
    # Get tenant policy for allowlist enforcement
    tenant_policy = tenant_policy_registry.get(tenant_id=tenant_id)
    enforcer: AllowListEnforcer | None = None
    if tenant_policy:
        enforcer = tool_registry.get_enforcer(tenant_id=tenant_id)
        if not enforcer:
            # Create enforcer if policy exists but not registered
            tool_registry.register_policy_pack(tenant_id=tenant_id, policy_pack=tenant_policy)
            enforcer = tool_registry.get_enforcer(tenant_id=tenant_id)
    
    # Get all tools from domain pack
    tool_infos = []
    allowed_count = 0
    blocked_count = 0
    disabled_count = 0
    
    for tool_name, tool_def in domain_pack.tools.items():
        # Check if tool is registered (may have overrides)
        registered_tool = tool_registry.get(
            tenant_id=tenant_id,
            tool_name=tool_name,
            domain_name=domain_name,
        )
        
        # Use registered tool if available, otherwise use canonical
        display_tool = registered_tool if registered_tool else tool_def
        
        # Check allowlist status
        is_allowed = False
        is_blocked = False
        if enforcer:
            is_allowed = enforcer.is_allowed(tool_name)
            is_blocked = tool_name in enforcer.get_blocked_tools()
        else:
            # No policy, all tools are allowed
            is_allowed = True
        
        # Check if disabled
        is_disabled = _is_tool_disabled(tenant_id, domain_name, tool_name)
        
        if is_allowed:
            allowed_count += 1
        if is_blocked:
            blocked_count += 1
        if is_disabled:
            disabled_count += 1
        
        tool_info = ToolInfo(
            toolName=tool_name,
            description=display_tool.description,
            endpoint=display_tool.endpoint,
            version=display_tool.version,
            timeoutSeconds=display_tool.timeout_seconds,
            maxRetries=display_tool.max_retries,
            isAllowed=is_allowed and not is_disabled,  # Disabled tools are not allowed
            isBlocked=is_blocked,
            isDisabled=is_disabled,
        )
        tool_infos.append(tool_info)
    
    # Sort by tool name
    tool_infos.sort(key=lambda x: x.tool_name)
    
    return ToolListResponse(
        tenantId=tenant_id,
        domainName=domain_name,
        tools=tool_infos,
        total=len(tool_infos),
        allowedCount=allowed_count,
        blockedCount=blocked_count,
        disabledCount=disabled_count,
    )


@router.post("/{tenant_id}/{domain_name}/disable", response_model=DisableToolResponse)
async def disable_tool(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
    domain_name: str = PathParam(..., description="Domain name"),
    request: DisableToolRequest = ...,
) -> DisableToolResponse:
    """
    Disable a tool for a tenant and domain.
    
    Disabled tools cannot be invoked even if they are in the allow-list.
    This is a tenant-level override that takes precedence over allow-list rules.
    
    Args:
        tenant_id: Tenant identifier
        domain_name: Domain name
        request: Disable tool request
        
    Returns:
        DisableToolResponse with disable status
        
    Raises:
        HTTPException: If disable operation fails
    """
    tool_registry = get_tool_registry()
    domain_pack_registry = get_domain_pack_registry()
    
    # Get domain pack to validate tool exists
    domain_pack = domain_pack_registry.get_latest(domain_name=domain_name, tenant_id=tenant_id)
    if not domain_pack:
        raise HTTPException(
            status_code=404,
            detail=f"Domain Pack '{domain_name}' not found for tenant '{tenant_id}'"
        )
    
    # Check if tool exists in domain pack
    if request.tool_name not in domain_pack.tools:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{request.tool_name}' is not defined in Domain Pack '{domain_name}'. "
                   f"Available tools: {sorted(domain_pack.tools.keys())}"
        )
    
    # Disable tool
    try:
        _disable_tool(tenant_id, domain_name, request.tool_name)
        
        logger.info(
            f"Disabled tool '{request.tool_name}' for tenant '{tenant_id}', domain '{domain_name}'"
        )
        
        return DisableToolResponse(
            toolName=request.tool_name,
            domainName=domain_name,
            disabled=True,
            message=f"Tool '{request.tool_name}' disabled successfully",
        )
    except Exception as e:
        logger.error(f"Failed to disable tool: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to disable tool: {str(e)}"
        )

