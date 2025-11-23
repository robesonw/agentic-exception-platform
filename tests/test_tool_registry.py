"""
Comprehensive tests for Tool Registry with allow-list enforcement.
Tests registration, validation, and access control.
"""

import pytest

from src.models.domain_pack import DomainPack, Guardrails, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack
from src.tools.registry import AllowListEnforcer, ToolRegistry, ToolRegistryError


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack with tools."""
    return DomainPack(
        domainName="TestDomain",
        exceptionTypes={},
        tools={
            "tool1": ToolDefinition(
                description="Tool 1",
                parameters={"param1": "string"},
                endpoint="https://api.example.com/tool1",
            ),
            "tool2": ToolDefinition(
                description="Tool 2",
                parameters={"param2": "int"},
                endpoint="https://api.example.com/tool2",
            ),
            "tool3": ToolDefinition(
                description="Tool 3",
                parameters={},
                endpoint="https://api.example.com/tool3",
            ),
        },
        guardrails=Guardrails(
            allowLists=["tool1", "tool2"],
            blockLists=[],
            humanApprovalThreshold=0.8,
        ),
    )


@pytest.fixture
def sample_policy_pack():
    """Create a sample tenant policy pack with approved tools."""
    return TenantPolicyPack(
        tenantId="tenant_001",
        domainName="TestDomain",
        approvedTools=["tool1", "tool2"],
    )


@pytest.fixture
def restrictive_policy_pack():
    """Create a restrictive policy pack with custom guardrails."""
    return TenantPolicyPack(
        tenantId="tenant_002",
        domainName="TestDomain",
        approvedTools=["tool1", "tool2", "tool3"],
        customGuardrails=Guardrails(
            allowLists=["tool1"],  # More restrictive than approvedTools
            blockLists=["tool3"],
            humanApprovalThreshold=0.9,
        ),
    )


class TestAllowListEnforcer:
    """Tests for AllowListEnforcer class."""

    def test_is_allowed_with_approved_tools(self, sample_policy_pack):
        """Test that approved tools are allowed."""
        enforcer = AllowListEnforcer(sample_policy_pack)
        
        assert enforcer.is_allowed("tool1") is True
        assert enforcer.is_allowed("tool2") is True
        assert enforcer.is_allowed("tool3") is False

    def test_is_allowed_with_custom_guardrails(self, restrictive_policy_pack):
        """Test that custom guardrails override approved tools."""
        enforcer = AllowListEnforcer(restrictive_policy_pack)
        
        # Custom guardrails only allow tool1
        assert enforcer.is_allowed("tool1") is True
        assert enforcer.is_allowed("tool2") is False  # Not in custom allow list
        assert enforcer.is_allowed("tool3") is False  # Blocked

    def test_get_approved_tools(self, sample_policy_pack):
        """Test getting approved tools set."""
        enforcer = AllowListEnforcer(sample_policy_pack)
        approved = enforcer.get_approved_tools()
        
        assert "tool1" in approved
        assert "tool2" in approved
        assert "tool3" not in approved

    def test_get_blocked_tools(self, restrictive_policy_pack):
        """Test getting blocked tools set."""
        enforcer = AllowListEnforcer(restrictive_policy_pack)
        blocked = enforcer.get_blocked_tools()
        
        assert "tool3" in blocked
        assert "tool1" not in blocked


class TestToolRegistry:
    """Tests for ToolRegistry class."""

    def test_register_domain_pack(self, sample_domain_pack):
        """Test registering a domain pack loads all tools."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        tools = registry.list_tools("tenant_001")
        assert "tool1" in tools
        assert "tool2" in tools
        assert "tool3" in tools

    def test_register_policy_pack(self, sample_policy_pack):
        """Test registering a policy pack creates enforcer."""
        registry = ToolRegistry()
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        enforcer = registry.get_enforcer("tenant_001")
        assert enforcer is not None
        assert enforcer.is_allowed("tool1") is True

    def test_register_tool_without_domain_pack(self, sample_domain_pack):
        """Test registering a tool without domain pack raises error."""
        registry = ToolRegistry()
        tool_def = sample_domain_pack.tools["tool1"]
        
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.register("tenant_001", "tool1", tool_def)
        assert "Domain Pack not registered" in str(exc_info.value)

    def test_register_tool_not_in_domain_pack(self, sample_domain_pack):
        """Test registering a tool not in domain pack raises error."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        invalid_tool = ToolDefinition(
            description="Invalid tool",
            parameters={},
            endpoint="https://api.example.com/invalid",
        )
        
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.register("tenant_001", "invalidTool", invalid_tool)
        assert "not defined in Domain Pack" in str(exc_info.value)

    def test_register_tool_with_endpoint_mismatch(self, sample_domain_pack):
        """Test registering a tool with endpoint mismatch raises error."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        mismatched_tool = ToolDefinition(
            description="Tool 1",
            parameters={"param1": "string"},
            endpoint="https://api.example.com/wrong",  # Different endpoint
        )
        
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.register("tenant_001", "tool1", mismatched_tool)
        assert "endpoint mismatch" in str(exc_info.value).lower()

    def test_get_tool(self, sample_domain_pack):
        """Test getting a registered tool."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        tool = registry.get("tenant_001", "tool1")
        assert tool is not None
        assert tool.description == "Tool 1"
        assert tool.endpoint == "https://api.example.com/tool1"

    def test_get_nonexistent_tool(self, sample_domain_pack):
        """Test getting a non-existent tool returns None."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        tool = registry.get("tenant_001", "nonexistent")
        assert tool is None

    def test_list_tools(self, sample_domain_pack):
        """Test listing all registered tools."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        tools = registry.list_tools("tenant_001")
        assert len(tools) == 3
        assert "tool1" in tools
        assert "tool2" in tools
        assert "tool3" in tools

    def test_list_allowed_tools_without_policy(self, sample_domain_pack):
        """Test listing allowed tools without policy pack returns all."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        allowed = registry.list_allowed_tools("tenant_001")
        assert len(allowed) == 3  # All tools allowed when no policy

    def test_list_allowed_tools_with_policy(self, sample_domain_pack, sample_policy_pack):
        """Test listing allowed tools with policy pack filters correctly."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        allowed = registry.list_allowed_tools("tenant_001")
        assert len(allowed) == 2
        assert "tool1" in allowed
        assert "tool2" in allowed
        assert "tool3" not in allowed

    def test_is_allowed_without_policy(self, sample_domain_pack):
        """Test is_allowed without policy pack allows all registered tools."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        assert registry.is_allowed("tenant_001", "tool1") is True
        assert registry.is_allowed("tenant_001", "tool2") is True
        assert registry.is_allowed("tenant_001", "tool3") is True
        assert registry.is_allowed("tenant_001", "nonexistent") is False

    def test_is_allowed_with_policy(self, sample_domain_pack, sample_policy_pack):
        """Test is_allowed with policy pack enforces allow-list."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        assert registry.is_allowed("tenant_001", "tool1") is True
        assert registry.is_allowed("tenant_001", "tool2") is True
        assert registry.is_allowed("tenant_001", "tool3") is False

    def test_is_allowed_with_restrictive_policy(
        self, sample_domain_pack, restrictive_policy_pack
    ):
        """Test is_allowed with restrictive custom guardrails."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_002", sample_domain_pack)
        registry.register_policy_pack("tenant_002", restrictive_policy_pack)
        
        assert registry.is_allowed("tenant_002", "tool1") is True
        assert registry.is_allowed("tenant_002", "tool2") is False  # Not in custom allow list
        assert registry.is_allowed("tenant_002", "tool3") is False  # Blocked

    def test_validate_tool_access_allowed(self, sample_domain_pack, sample_policy_pack):
        """Test validate_tool_access for allowed tool."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        # Should not raise
        registry.validate_tool_access("tenant_001", "tool1")

    def test_validate_tool_access_not_registered(self, sample_domain_pack):
        """Test validate_tool_access for non-registered tool raises error."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.validate_tool_access("tenant_001", "nonexistent")
        assert "not registered" in str(exc_info.value).lower()

    def test_validate_tool_access_not_allowed(self, sample_domain_pack, sample_policy_pack):
        """Test validate_tool_access for non-allowed tool raises error."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.validate_tool_access("tenant_001", "tool3")
        assert "not in allow-list" in str(exc_info.value).lower()

    def test_get_enforcer(self, sample_policy_pack):
        """Test getting enforcer for a tenant."""
        registry = ToolRegistry()
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        enforcer = registry.get_enforcer("tenant_001")
        assert enforcer is not None
        assert isinstance(enforcer, AllowListEnforcer)

    def test_get_enforcer_nonexistent(self):
        """Test getting enforcer for non-existent tenant returns None."""
        registry = ToolRegistry()
        enforcer = registry.get_enforcer("nonexistent")
        assert enforcer is None

    def test_clear_tenant(self, sample_domain_pack, sample_policy_pack):
        """Test clearing all data for a tenant."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        
        assert registry.get("tenant_001", "tool1") is not None
        assert registry.get_enforcer("tenant_001") is not None
        
        registry.clear_tenant("tenant_001")
        
        assert registry.get("tenant_001", "tool1") is None
        assert registry.get_enforcer("tenant_001") is None

    def test_clear_all(self, sample_domain_pack, sample_policy_pack):
        """Test clearing all registry data."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        registry.register_domain_pack("tenant_002", sample_domain_pack)
        
        registry.clear()
        
        assert registry.get("tenant_001", "tool1") is None
        assert registry.get("tenant_002", "tool1") is None
        assert registry.get_enforcer("tenant_001") is None


class TestIntegration:
    """Integration tests for tool registry workflow."""

    def test_full_workflow(self, sample_domain_pack, sample_policy_pack):
        """Test complete workflow: register domain, register policy, access tools."""
        registry = ToolRegistry()
        
        # Step 1: Register domain pack (loads all tools)
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        assert len(registry.list_tools("tenant_001")) == 3
        
        # Step 2: Register policy pack (creates enforcer)
        registry.register_policy_pack("tenant_001", sample_policy_pack)
        assert registry.get_enforcer("tenant_001") is not None
        
        # Step 3: Check allowed tools
        allowed = registry.list_allowed_tools("tenant_001")
        assert len(allowed) == 2
        assert "tool1" in allowed
        assert "tool2" in allowed
        
        # Step 4: Validate tool access
        registry.validate_tool_access("tenant_001", "tool1")
        registry.validate_tool_access("tenant_001", "tool2")
        
        with pytest.raises(ToolRegistryError):
            registry.validate_tool_access("tenant_001", "tool3")

    def test_multi_tenant_isolation(self, sample_domain_pack):
        """Test that tenants are properly isolated."""
        registry = ToolRegistry()
        
        # Create different policy packs for different tenants
        policy1 = TenantPolicyPack(
            tenantId="tenant_001",
            domainName="TestDomain",
            approvedTools=["tool1"],
        )
        policy2 = TenantPolicyPack(
            tenantId="tenant_002",
            domainName="TestDomain",
            approvedTools=["tool2"],
        )
        
        registry.register_domain_pack("tenant_001", sample_domain_pack)
        registry.register_domain_pack("tenant_002", sample_domain_pack)
        registry.register_policy_pack("tenant_001", policy1)
        registry.register_policy_pack("tenant_002", policy2)
        
        # Tenant 1 can only access tool1
        assert registry.is_allowed("tenant_001", "tool1") is True
        assert registry.is_allowed("tenant_001", "tool2") is False
        
        # Tenant 2 can only access tool2
        assert registry.is_allowed("tenant_002", "tool1") is False
        assert registry.is_allowed("tenant_002", "tool2") is True

    def test_custom_guardrails_override(self, sample_domain_pack, restrictive_policy_pack):
        """Test that custom guardrails override approved tools."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant_002", sample_domain_pack)
        registry.register_policy_pack("tenant_002", restrictive_policy_pack)
        
        # Even though approvedTools includes tool2 and tool3,
        # custom guardrails only allow tool1 and block tool3
        assert registry.is_allowed("tenant_002", "tool1") is True
        assert registry.is_allowed("tenant_002", "tool2") is False
        assert registry.is_allowed("tenant_002", "tool3") is False

