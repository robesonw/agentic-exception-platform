"""
Typed Tool Registry with allow-list enforcement.
Matches specification from docs/02-modules-components.md
"""

from typing import Optional

from src.models.domain_pack import DomainPack, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack


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
    Per-tenant tool registry with typed operations and allow-list enforcement.
    
    Maintains a dynamic registry of tenant-approved tools.
    Tools are validated against Domain Pack and access is controlled by Tenant Policy Pack.
    """

    def __init__(self):
        """Initialize the registry."""
        # tenant_id -> {tool_name -> ToolDefinition}
        self._tools: dict[str, dict[str, ToolDefinition]] = {}
        # tenant_id -> AllowListEnforcer
        self._enforcers: dict[str, AllowListEnforcer] = {}
        # tenant_id -> DomainPack (for validation)
        self._domain_packs: dict[str, DomainPack] = {}

    def register_domain_pack(self, tenant_id: str, domain_pack: DomainPack) -> None:
        """
        Register a Domain Pack for a tenant.
        This loads all tools from the domain pack into the registry.
        
        Args:
            tenant_id: Tenant identifier
            domain_pack: Domain Pack containing tool definitions
        """
        if tenant_id not in self._tools:
            self._tools[tenant_id] = {}
        
        self._domain_packs[tenant_id] = domain_pack
        
        # Register all tools from domain pack
        for tool_name, tool_def in domain_pack.tools.items():
            self._tools[tenant_id][tool_name] = tool_def

    def register_policy_pack(self, tenant_id: str, policy_pack: TenantPolicyPack) -> None:
        """
        Register a Tenant Policy Pack for allow-list enforcement.
        
        Args:
            tenant_id: Tenant identifier
            policy_pack: Tenant Policy Pack containing approved tools
        """
        self._enforcers[tenant_id] = AllowListEnforcer(policy_pack)

    def register(
        self, tenant_id: str, tool_name: str, tool_definition: ToolDefinition
    ) -> None:
        """
        Register a tool for a tenant.
        
        Tool must exist in the tenant's Domain Pack to be registered.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            tool_definition: Tool definition
            
        Raises:
            ToolRegistryError: If tool is not in domain pack
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
        
        if tenant_id not in self._tools:
            self._tools[tenant_id] = {}
        
        self._tools[tenant_id][tool_name] = tool_definition

    def get(self, tenant_id: str, tool_name: str) -> Optional[ToolDefinition]:
        """
        Get a tool definition for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            
        Returns:
            ToolDefinition or None if not found
        """
        tenant_tools = self._tools.get(tenant_id, {})
        return tenant_tools.get(tool_name)

    def list_tools(self, tenant_id: str) -> list[str]:
        """
        List all registered tools for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of tool names
        """
        return list(self._tools.get(tenant_id, {}).keys())

    def list_allowed_tools(self, tenant_id: str) -> list[str]:
        """
        List only allowed tools for a tenant (based on policy pack).
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of allowed tool names
        """
        all_tools = self.list_tools(tenant_id)
        enforcer = self._enforcers.get(tenant_id)
        
        if enforcer is None:
            # No policy pack registered, return all tools
            return all_tools
        
        return [tool for tool in all_tools if enforcer.is_allowed(tool)]

    def is_allowed(self, tenant_id: str, tool_name: str) -> bool:
        """
        Check if a tool is allowed for a tenant.
        
        Checks:
        1. Tool is registered
        2. Tool is in allow-list (if policy pack is registered)
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            
        Returns:
            True if tool is allowed, False otherwise
        """
        # First check if tool is registered
        if self.get(tenant_id, tool_name) is None:
            return False
        
        # Then check allow-list if policy pack is registered
        enforcer = self._enforcers.get(tenant_id)
        if enforcer is None:
            # No policy pack registered, allow all registered tools
            return True
        
        return enforcer.is_allowed(tool_name)

    def validate_tool_access(self, tenant_id: str, tool_name: str) -> None:
        """
        Validate that a tool can be accessed by a tenant.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            
        Raises:
            ToolRegistryError: If tool access is not allowed
        """
        tool_def = self.get(tenant_id, tool_name)
        if tool_def is None:
            raise ToolRegistryError(
                f"Tool '{tool_name}' is not registered for tenant {tenant_id}"
            )
        
        enforcer = self._enforcers.get(tenant_id)
        if enforcer is not None and not enforcer.is_allowed(tool_name):
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

    def clear(self) -> None:
        """Clear all registered tools and enforcers."""
        self._tools.clear()
        self._enforcers.clear()
        self._domain_packs.clear()

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
