"""
Typed Tool Registry with allow-list enforcement and domain tool support.

Phase 2 enhancements:
- Domain tool namespacing (tenant:domain:tool)
- Tool inheritance and overrides from Tenant Policy Pack
- Tool version compatibility checks
- Property overrides (timeouts, retries)

Matches specification from docs/02-modules-components.md
"""

import logging
from typing import Optional

from src.models.domain_pack import DomainPack, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack, ToolOverride

logger = logging.getLogger(__name__)


class ToolRegistryError(Exception):
    """Raised when tool registry operations fail."""

    pass


class AllowListEnforcer:
    """
    Enforces allow-list rules from Tenant Policy Pack.
    Prevents access to tools not approved by tenant policy.
    """

    def __init__(self, policy_pack: TenantPolicyPack):
        """
        Initialize the allow-list enforcer.
        
        Args:
            policy_pack: Tenant Policy Pack containing approved tools
        """
        self._policy_pack = policy_pack
        # Build set of approved tools for fast lookup
        self._approved_tools = set(policy_pack.approved_tools)
        
        # Also check custom guardrails if present
        if policy_pack.custom_guardrails:
            # Custom guardrails can further restrict (block) tools
            self._blocked_tools = set(policy_pack.custom_guardrails.block_lists)
            # Custom allow lists override domain allow lists (more restrictive)
            if policy_pack.custom_guardrails.allow_lists:
                self._approved_tools = set(policy_pack.custom_guardrails.allow_lists)
        else:
            self._blocked_tools = set()

    def is_allowed(self, tool_name: str) -> bool:
        """
        Check if a tool is allowed based on tenant policy.
        
        Args:
            tool_name: Name of the tool to check
            
        Returns:
            True if tool is allowed, False otherwise
        """
        # First check if explicitly blocked
        if tool_name in self._blocked_tools:
            return False
        
        # Then check if explicitly approved
        return tool_name in self._approved_tools

    def get_approved_tools(self) -> set[str]:
        """
        Get set of approved tool names.
        
        Returns:
            Set of approved tool names
        """
        return self._approved_tools.copy()

    def get_blocked_tools(self) -> set[str]:
        """
        Get set of blocked tool names.
        
        Returns:
            Set of blocked tool names
        """
        return self._blocked_tools.copy()


class ToolRegistry:
    """
    Per-tenant tool registry with typed operations, allow-list enforcement, and domain tool support.
    
    Phase 2 enhancements:
    - Tools are namespaced by tenant:domain:toolName
    - Supports tool property overrides from Tenant Policy Pack
    - Implements version compatibility checks
    
    Maintains a dynamic registry of tenant-approved tools.
    Tools are validated against Domain Pack and access is controlled by Tenant Policy Pack.
    """

    def __init__(self):
        """Initialize the registry."""
        # tenant_id -> {namespaced_tool_name -> ToolDefinition}
        # Namespace format: {tenantId}:{domainName}:{toolName}
        self._tools: dict[str, dict[str, ToolDefinition]] = {}
        # tenant_id -> AllowListEnforcer
        self._enforcers: dict[str, AllowListEnforcer] = {}
        # tenant_id -> DomainPack (for validation and canonical definitions)
        self._domain_packs: dict[str, DomainPack] = {}
        # tenant_id -> {tool_name -> ToolOverride}
        self._tool_overrides: dict[str, dict[str, ToolOverride]] = {}
        # tenant_id -> {tool_name -> version} for compatibility tracking
        self._tool_versions: dict[str, dict[str, str]] = {}

    def _make_namespaced_name(self, tenant_id: str, domain_name: str, tool_name: str) -> str:
        """
        Create namespaced tool name: {tenantId}:{domainName}:{toolName}.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            tool_name: Tool name
            
        Returns:
            Namespaced tool name
        """
        return f"{tenant_id}:{domain_name}:{tool_name}"

    def _parse_namespaced_name(self, namespaced_name: str) -> tuple[str, str, str]:
        """
        Parse namespaced tool name into components.
        
        Args:
            namespaced_name: Namespaced tool name (tenant:domain:tool)
            
        Returns:
            Tuple of (tenant_id, domain_name, tool_name)
            
        Raises:
            ValueError: If namespaced name format is invalid
        """
        parts = namespaced_name.split(":", 2)
        if len(parts) != 3:
            raise ValueError(
                f"Invalid namespaced tool name format: {namespaced_name}. "
                f"Expected format: tenantId:domainName:toolName"
            )
        return tuple(parts)

    def register_domain_pack(self, tenant_id: str, domain_pack: DomainPack) -> None:
        """
        Register a Domain Pack for a tenant.
        This loads all tools from the domain pack into the registry with namespacing.
        
        Args:
            tenant_id: Tenant identifier
            domain_pack: Domain Pack containing tool definitions
            
        Raises:
            ToolRegistryError: If tool version compatibility check fails
        """
        if tenant_id not in self._tools:
            self._tools[tenant_id] = {}
        if tenant_id not in self._tool_versions:
            self._tool_versions[tenant_id] = {}
        
        self._domain_packs[tenant_id] = domain_pack
        
        # Register all tools from domain pack with namespacing
        for tool_name, tool_def in domain_pack.tools.items():
            namespaced_name = self._make_namespaced_name(
                tenant_id, domain_pack.domain_name, tool_name
            )
            
            # Check version compatibility if tool already exists
            if namespaced_name in self._tools[tenant_id]:
                existing_tool = self._tools[tenant_id][namespaced_name]
                if not self._check_version_compatibility(
                    existing_tool.version, tool_def.version, tenant_id, tool_name
                ):
                    raise ToolRegistryError(
                        f"Tool '{tool_name}' version '{tool_def.version}' is incompatible "
                        f"with existing version '{existing_tool.version}' for tenant {tenant_id}"
                    )
            
            # Store canonical tool definition
            self._tools[tenant_id][namespaced_name] = tool_def
            self._tool_versions[tenant_id][tool_name] = tool_def.version
            
            logger.debug(
                f"Registered domain tool '{namespaced_name}' "
                f"version {tool_def.version} for tenant {tenant_id}"
            )

    def register_policy_pack(self, tenant_id: str, policy_pack: TenantPolicyPack) -> None:
        """
        Register a Tenant Policy Pack for allow-list enforcement and tool overrides.
        
        Args:
            tenant_id: Tenant identifier
            policy_pack: Tenant Policy Pack containing approved tools and overrides
            
        Raises:
            ToolRegistryError: If tool overrides reference non-existent tools
        """
        self._enforcers[tenant_id] = AllowListEnforcer(policy_pack)
        
        # Process tool overrides
        if tenant_id not in self._tool_overrides:
            self._tool_overrides[tenant_id] = {}
        
        domain_pack = self._domain_packs.get(tenant_id)
        if domain_pack is None:
            logger.warning(
                f"Tenant Policy Pack registered for tenant {tenant_id} "
                f"but Domain Pack not yet registered. Tool overrides will be applied when Domain Pack is registered."
            )
        
        # Store tool overrides
        for override in policy_pack.tool_overrides:
            # Validate tool exists in domain pack if available
            if domain_pack and override.tool_name not in domain_pack.tools:
                raise ToolRegistryError(
                    f"Tool override references non-existent tool '{override.tool_name}' "
                    f"for tenant {tenant_id}, domain {policy_pack.domain_name}"
                )
            
            self._tool_overrides[tenant_id][override.tool_name] = override
            logger.debug(
                f"Registered tool override for '{override.tool_name}' "
                f"for tenant {tenant_id}"
            )
        
        # Apply overrides to existing tools
        if domain_pack:
            self._apply_overrides(tenant_id, domain_pack)

    def _check_version_compatibility(
        self, existing_version: str, new_version: str, tenant_id: str, tool_name: str
    ) -> bool:
        """
        Check if two tool versions are compatible.
        
        For MVP: Major version must match (e.g., 1.x.x compatible with 1.y.z, but not with 2.x.x).
        In production, could implement more sophisticated semantic versioning.
        
        Args:
            existing_version: Existing tool version
            new_version: New tool version to check
            tenant_id: Tenant identifier (for logging)
            tool_name: Tool name (for logging)
            
        Returns:
            True if versions are compatible, False otherwise
        """
        try:
            existing_parts = existing_version.split(".")
            new_parts = new_version.split(".")
            
            # Major version must match
            if len(existing_parts) > 0 and len(new_parts) > 0:
                if existing_parts[0] != new_parts[0]:
                    logger.warning(
                        f"Tool '{tool_name}' version incompatibility for tenant {tenant_id}: "
                        f"existing={existing_version}, new={new_version}"
                    )
                    return False
            
            return True
        except (ValueError, IndexError):
            # If version format is invalid, be conservative and reject
            logger.warning(
                f"Invalid version format for tool '{tool_name}': "
                f"existing={existing_version}, new={new_version}"
            )
            return False

    def _apply_overrides(self, tenant_id: str, domain_pack: DomainPack) -> None:
        """
        Apply tool overrides from Tenant Policy Pack to registered tools.
        
        Args:
            tenant_id: Tenant identifier
            domain_pack: Domain Pack containing canonical tool definitions
        """
        overrides = self._tool_overrides.get(tenant_id, {})
        
        for tool_name, override in overrides.items():
            if tool_name not in domain_pack.tools:
                continue
            
            namespaced_name = self._make_namespaced_name(
                tenant_id, domain_pack.domain_name, tool_name
            )
            
            if namespaced_name not in self._tools[tenant_id]:
                continue
            
            # Get canonical tool definition
            canonical_tool = domain_pack.tools[tool_name]
            
            # Create overridden tool definition
            overridden_tool = ToolDefinition(
                description=canonical_tool.description,
                parameters=canonical_tool.parameters,
                endpoint=canonical_tool.endpoint,
                version=canonical_tool.version,
                timeout_seconds=(
                    override.timeout_seconds
                    if override.timeout_seconds is not None
                    else canonical_tool.timeout_seconds
                ),
                max_retries=(
                    override.max_retries
                    if override.max_retries is not None
                    else canonical_tool.max_retries
                ),
            )
            
            # Update registry with overridden tool
            self._tools[tenant_id][namespaced_name] = overridden_tool
            
            logger.debug(
                f"Applied overrides to tool '{namespaced_name}' for tenant {tenant_id}: "
                f"timeout={overridden_tool.timeout_seconds}, retries={overridden_tool.max_retries}"
            )

    def register(
        self, tenant_id: str, tool_name: str, tool_definition: ToolDefinition
    ) -> None:
        """
        Register a tool for a tenant (legacy method, use register_domain_pack instead).
        
        Tool must exist in the tenant's Domain Pack to be registered.
        Tools are automatically namespaced.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            tool_definition: Tool definition
            
        Raises:
            ToolRegistryError: If tool is not in domain pack or version incompatible
        """
        # Validate tool exists in domain pack
        domain_pack = self._domain_packs.get(tenant_id)
        if domain_pack is None:
            raise ToolRegistryError(
                f"Domain Pack not registered for tenant {tenant_id}. "
                "Register domain pack before registering tools."
            )
        
        if tool_name not in domain_pack.tools:
            raise ToolRegistryError(
                f"Tool '{tool_name}' is not defined in Domain Pack for tenant {tenant_id}"
            )
        
        # Validate tool definition matches domain pack
        domain_tool = domain_pack.tools[tool_name]
        if tool_definition.endpoint != domain_tool.endpoint:
            raise ToolRegistryError(
                f"Tool '{tool_name}' endpoint mismatch. "
                f"Expected: {domain_tool.endpoint}, Got: {tool_definition.endpoint}"
            )
        
        # Check version compatibility
        if not self._check_version_compatibility(
            domain_tool.version, tool_definition.version, tenant_id, tool_name
        ):
            raise ToolRegistryError(
                f"Tool '{tool_name}' version '{tool_definition.version}' is incompatible "
                f"with Domain Pack version '{domain_tool.version}' for tenant {tenant_id}"
            )
        
        if tenant_id not in self._tools:
            self._tools[tenant_id] = {}
        
        # Use namespaced name
        namespaced_name = self._make_namespaced_name(
            tenant_id, domain_pack.domain_name, tool_name
        )
        self._tools[tenant_id][namespaced_name] = tool_definition

    def get(
        self, tenant_id: str, tool_name: str, domain_name: Optional[str] = None
    ) -> Optional[ToolDefinition]:
        """
        Get a tool definition for a tenant.
        
        Supports both namespaced and un-namespaced tool names for backward compatibility.
        If domain_name is provided, uses namespaced lookup: {tenantId}:{domainName}:{toolName}
        Otherwise, tries to find tool by searching all domains for the tenant.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool (or namespaced name)
            domain_name: Optional domain name for namespaced lookup
            
        Returns:
            ToolDefinition or None if not found
        """
        tenant_tools = self._tools.get(tenant_id, {})
        
        # If domain_name provided, use namespaced lookup
        if domain_name:
            namespaced_name = self._make_namespaced_name(tenant_id, domain_name, tool_name)
            return tenant_tools.get(namespaced_name)
        
        # Try direct lookup first (for backward compatibility)
        if tool_name in tenant_tools:
            return tenant_tools[tool_name]
        
        # Try namespaced lookup (search all namespaced tools)
        for namespaced_name, tool_def in tenant_tools.items():
            try:
                _, _, parsed_tool_name = self._parse_namespaced_name(namespaced_name)
                if parsed_tool_name == tool_name:
                    return tool_def
            except ValueError:
                # Not a namespaced name, skip
                continue
        
        return None

    def list_tools(
        self, tenant_id: str, domain_name: Optional[str] = None, unnamespaced: bool = True
    ) -> list[str]:
        """
        List all registered tools for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Optional domain name filter
            unnamespaced: If True, return un-namespaced tool names only
            
        Returns:
            List of tool names (namespaced or un-namespaced)
        """
        tenant_tools = self._tools.get(tenant_id, {})
        
        if domain_name:
            # Filter by domain
            prefix = f"{tenant_id}:{domain_name}:"
            tools = [name for name in tenant_tools.keys() if name.startswith(prefix)]
        else:
            tools = list(tenant_tools.keys())
        
        if unnamespaced:
            # Extract un-namespaced names
            result = []
            for namespaced_name in tools:
                try:
                    _, _, tool_name = self._parse_namespaced_name(namespaced_name)
                    result.append(tool_name)
                except ValueError:
                    # Not namespaced, use as-is
                    result.append(namespaced_name)
            return sorted(set(result))  # Remove duplicates
        
        return sorted(tools)

    def list_allowed_tools(
        self, tenant_id: str, domain_name: Optional[str] = None, unnamespaced: bool = True
    ) -> list[str]:
        """
        List only allowed tools for a tenant (based on policy pack).
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Optional domain name filter
            unnamespaced: If True, return un-namespaced tool names only
            
        Returns:
            List of allowed tool names
        """
        all_tools = self.list_tools(tenant_id, domain_name=domain_name, unnamespaced=unnamespaced)
        enforcer = self._enforcers.get(tenant_id)
        
        if enforcer is None:
            # No policy pack registered, return all tools
            return all_tools
        
        # Filter by allow-list (check un-namespaced tool names)
        allowed = []
        for tool_name in all_tools:
            # Extract un-namespaced name for allow-list check
            try:
                _, _, unnamespaced_name = self._parse_namespaced_name(tool_name)
                check_name = unnamespaced_name
            except ValueError:
                # Not namespaced, use as-is
                check_name = tool_name
            
            if enforcer.is_allowed(check_name):
                allowed.append(tool_name)
        
        return allowed

    def is_allowed(
        self, tenant_id: str, tool_name: str, domain_name: Optional[str] = None
    ) -> bool:
        """
        Check if a tool is allowed for a tenant.
        
        Checks:
        1. Tool is registered
        2. Tool is in allow-list (if policy pack is registered)
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool (or namespaced name)
            domain_name: Optional domain name for namespaced lookup
            
        Returns:
            True if tool is allowed, False otherwise
        """
        # First check if tool is registered
        tool_def = self.get(tenant_id, tool_name, domain_name=domain_name)
        if tool_def is None:
            return False
        
        # Extract un-namespaced name for allow-list check
        try:
            _, _, unnamespaced_name = self._parse_namespaced_name(tool_name)
            check_name = unnamespaced_name
        except ValueError:
            # Not namespaced, use as-is
            check_name = tool_name
        
        # Then check allow-list if policy pack is registered
        enforcer = self._enforcers.get(tenant_id)
        if enforcer is None:
            # No policy pack registered, allow all registered tools
            return True
        
        return enforcer.is_allowed(check_name)

    def validate_tool_access(
        self, tenant_id: str, tool_name: str, domain_name: Optional[str] = None
    ) -> None:
        """
        Validate that a tool can be accessed by a tenant.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool (or namespaced name)
            domain_name: Optional domain name for namespaced lookup
            
        Raises:
            ToolRegistryError: If tool access is not allowed
        """
        tool_def = self.get(tenant_id, tool_name, domain_name=domain_name)
        if tool_def is None:
            raise ToolRegistryError(
                f"Tool '{tool_name}' is not registered for tenant {tenant_id}"
            )
        
        # Extract un-namespaced name for allow-list check
        try:
            _, _, unnamespaced_name = self._parse_namespaced_name(tool_name)
            check_name = unnamespaced_name
        except ValueError:
            # Not namespaced, use as-is
            check_name = tool_name
        
        enforcer = self._enforcers.get(tenant_id)
        if enforcer is not None and not enforcer.is_allowed(check_name):
            raise ToolRegistryError(
                f"Tool '{tool_name}' is not in allow-list for tenant {tenant_id}. "
                f"Approved tools: {sorted(enforcer.get_approved_tools())}"
            )

    def get_enforcer(self, tenant_id: str) -> Optional[AllowListEnforcer]:
        """
        Get the allow-list enforcer for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            AllowListEnforcer instance or None if not registered
        """
        return self._enforcers.get(tenant_id)

    def clear_tenant(self, tenant_id: str) -> None:
        """
        Clear all tools and enforcers for a tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        self._tools.pop(tenant_id, None)
        self._enforcers.pop(tenant_id, None)
        self._domain_packs.pop(tenant_id, None)
        self._tool_overrides.pop(tenant_id, None)
        self._tool_versions.pop(tenant_id, None)

    def clear(self) -> None:
        """Clear all registered tools and enforcers."""
        self._tools.clear()
        self._enforcers.clear()
        self._domain_packs.clear()
        self._tool_overrides.clear()
        self._tool_versions.clear()

    def get_invoker(self, tenant_id: str) -> "ToolInvoker | None":
        """
        Get a ToolInvoker instance for a tenant.
        
        This is a convenience method that creates a ToolInvoker
        with the appropriate registry configuration.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            ToolInvoker instance or None if tenant not configured
        """
        from src.tools.invoker import ToolInvoker
        
        # Check if tenant has domain pack and policy pack registered
        if tenant_id not in self._domain_packs:
            return None
        
        # Create invoker with this registry
        return ToolInvoker(tool_registry=self)
