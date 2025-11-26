"""
Comprehensive tests for Phase 2 Tool Registry domain tools enhancements.

Tests:
- Domain tool loading with namespacing
- Tool inheritance and overrides
- Version compatibility checks
- Tenant and domain isolation
"""

import pytest

from src.models.domain_pack import DomainPack, Guardrails, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack, ToolOverride
from src.tools.registry import ToolRegistry, ToolRegistryError


class TestDomainToolNamespacing:
    """Tests for domain tool namespacing."""

    def test_tool_namespacing_on_registration(self):
        """Test that tools are namespaced when domain pack is registered."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # Tool should be namespaced when unnamespaced=False
        tools = registry.list_tools("tenant1", unnamespaced=False)
        assert len(tools) == 1
        assert "tenant1:TestDomain:tool1" in tools

    def test_get_tool_with_namespace(self):
        """Test getting a tool using namespaced name."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # Get using namespaced name
        tool = registry.get("tenant1", "tenant1:TestDomain:tool1")
        assert tool is not None
        assert tool.description == "Tool 1"

    def test_get_tool_with_domain_name(self):
        """Test getting a tool using domain_name parameter."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # Get using domain_name parameter
        tool = registry.get("tenant1", "tool1", domain_name="TestDomain")
        assert tool is not None
        assert tool.description == "Tool 1"

    def test_list_tools_unnamespaced(self):
        """Test listing tools with unnamespaced option."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                ),
                "tool2": ToolDefinition(
                    description="Tool 2",
                    parameters={},
                    endpoint="https://api.example.com/tool2",
                ),
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # List unnamespaced
        tools = registry.list_tools("tenant1", unnamespaced=True)
        assert "tool1" in tools
        assert "tool2" in tools
        assert "tenant1:TestDomain:tool1" not in tools

    def test_list_tools_by_domain(self):
        """Test listing tools filtered by domain."""
        registry = ToolRegistry()
        
        domain_pack1 = DomainPack(
            domainName="Domain1",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        domain_pack2 = DomainPack(
            domainName="Domain2",
            exceptionTypes={},
            tools={
                "tool2": ToolDefinition(
                    description="Tool 2",
                    parameters={},
                    endpoint="https://api.example.com/tool2",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack1)
        registry.register_domain_pack("tenant1", domain_pack2)
        
        # List tools for Domain1
        tools1 = registry.list_tools("tenant1", domain_name="Domain1", unnamespaced=False)
        assert len(tools1) == 1
        assert "tenant1:Domain1:tool1" in tools1
        
        # List tools for Domain2
        tools2 = registry.list_tools("tenant1", domain_name="Domain2", unnamespaced=False)
        assert len(tools2) == 1
        assert "tenant1:Domain2:tool2" in tools2


class TestToolInheritanceAndOverrides:
    """Tests for tool inheritance and overrides from Tenant Policy Pack."""

    def test_tool_override_timeout(self):
        """Test that tool timeout can be overridden from Tenant Policy Pack."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    timeout_seconds=30.0,
                    max_retries=3,
                )
            },
        )
        
        policy_pack = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(
                    toolName="tool1",
                    timeoutSeconds=60.0,  # Override timeout
                )
            ],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_policy_pack("tenant1", policy_pack)
        
        # Get tool and verify override applied
        tool = registry.get("tenant1", "tool1", domain_name="TestDomain")
        assert tool is not None
        assert tool.timeout_seconds == 60.0  # Overridden
        assert tool.max_retries == 3  # Not overridden, uses canonical

    def test_tool_override_retries(self):
        """Test that tool retries can be overridden from Tenant Policy Pack."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    timeout_seconds=30.0,
                    max_retries=3,
                )
            },
        )
        
        policy_pack = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(
                    toolName="tool1",
                    maxRetries=5,  # Override retries
                )
            ],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_policy_pack("tenant1", policy_pack)
        
        # Get tool and verify override applied
        tool = registry.get("tenant1", "tool1", domain_name="TestDomain")
        assert tool is not None
        assert tool.timeout_seconds == 30.0  # Not overridden, uses canonical
        assert tool.max_retries == 5  # Overridden

    def test_tool_override_both_properties(self):
        """Test that both timeout and retries can be overridden."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    timeout_seconds=30.0,
                    max_retries=3,
                )
            },
        )
        
        policy_pack = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(
                    toolName="tool1",
                    timeoutSeconds=90.0,
                    maxRetries=10,
                )
            ],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_policy_pack("tenant1", policy_pack)
        
        # Get tool and verify both overrides applied
        tool = registry.get("tenant1", "tool1", domain_name="TestDomain")
        assert tool is not None
        assert tool.timeout_seconds == 90.0
        assert tool.max_retries == 10

    def test_tool_override_nonexistent_tool(self):
        """Test that overriding non-existent tool raises error."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        policy_pack = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(
                    toolName="nonexistent",
                    timeoutSeconds=60.0,
                )
            ],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # Should raise error when registering policy pack
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.register_policy_pack("tenant1", policy_pack)
        assert "non-existent tool" in str(exc_info.value).lower()

    def test_canonical_tool_definition_preserved(self):
        """Test that canonical tool definition properties are preserved."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Canonical Tool 1",
                    parameters={"param1": "string"},
                    endpoint="https://api.example.com/tool1",
                    timeout_seconds=30.0,
                    max_retries=3,
                )
            },
        )
        
        policy_pack = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(
                    toolName="tool1",
                    timeoutSeconds=60.0,
                )
            ],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_policy_pack("tenant1", policy_pack)
        
        # Get tool and verify canonical properties preserved
        tool = registry.get("tenant1", "tool1", domain_name="TestDomain")
        assert tool is not None
        assert tool.description == "Canonical Tool 1"
        assert tool.parameters == {"param1": "string"}
        assert tool.endpoint == "https://api.example.com/tool1"
        assert tool.timeout_seconds == 60.0  # Overridden
        assert tool.max_retries == 3  # Canonical (not overridden)


class TestToolVersionCompatibility:
    """Tests for tool version compatibility checks."""

    def test_compatible_versions(self):
        """Test that compatible versions are accepted."""
        registry = ToolRegistry()
        
        domain_pack1 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    version="1.0.0",
                )
            },
        )
        
        domain_pack2 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    version="1.2.3",  # Same major version
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack1)
        # Should not raise - compatible versions
        registry.register_domain_pack("tenant1", domain_pack2)

    def test_incompatible_versions(self):
        """Test that incompatible versions are rejected."""
        registry = ToolRegistry()
        
        domain_pack1 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    version="1.0.0",
                )
            },
        )
        
        domain_pack2 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    version="2.0.0",  # Different major version
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack1)
        
        # Should raise error - incompatible versions
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.register_domain_pack("tenant1", domain_pack2)
        assert "incompatible" in str(exc_info.value).lower()

    def test_version_compatibility_on_register(self):
        """Test version compatibility check when registering individual tool."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    version="1.0.0",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # Try to register incompatible version
        incompatible_tool = ToolDefinition(
            description="Tool 1",
            parameters={},
            endpoint="https://api.example.com/tool1",
            version="2.0.0",  # Incompatible
        )
        
        with pytest.raises(ToolRegistryError) as exc_info:
            registry.register("tenant1", "tool1", incompatible_tool)
        assert "incompatible" in str(exc_info.value).lower()


class TestTenantDomainIsolation:
    """Tests for tenant and domain isolation."""

    def test_same_tool_different_domains(self):
        """Test that same tool name in different domains are isolated."""
        registry = ToolRegistry()
        
        domain_pack1 = DomainPack(
            domainName="Domain1",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1 from Domain1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        domain_pack2 = DomainPack(
            domainName="Domain2",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1 from Domain2",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack1)
        registry.register_domain_pack("tenant1", domain_pack2)
        
        # Both tools should exist with different namespaces
        tool1 = registry.get("tenant1", "tool1", domain_name="Domain1")
        tool2 = registry.get("tenant1", "tool1", domain_name="Domain2")
        
        assert tool1 is not None
        assert tool2 is not None
        assert tool1.description == "Tool 1 from Domain1"
        assert tool2.description == "Tool 1 from Domain2"

    def test_same_tool_different_tenants(self):
        """Test that same tool in same domain for different tenants are isolated."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_domain_pack("tenant2", domain_pack)
        
        # Both tenants should have their own namespaced tools
        tools1 = registry.list_tools("tenant1", unnamespaced=False)
        tools2 = registry.list_tools("tenant2", unnamespaced=False)
        
        assert "tenant1:TestDomain:tool1" in tools1
        assert "tenant2:TestDomain:tool1" in tools2
        assert "tenant1:TestDomain:tool1" not in tools2
        assert "tenant2:TestDomain:tool1" not in tools1

    def test_tool_override_tenant_isolation(self):
        """Test that tool overrides are tenant-isolated."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                    timeout_seconds=30.0,
                )
            },
        )
        
        policy_pack1 = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(toolName="tool1", timeoutSeconds=60.0)
            ],
        )
        
        policy_pack2 = TenantPolicyPack(
            tenantId="tenant2",
            domainName="TestDomain",
            approvedTools=["tool1"],
            toolOverrides=[
                ToolOverride(toolName="tool1", timeoutSeconds=90.0)
            ],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_domain_pack("tenant2", domain_pack)
        registry.register_policy_pack("tenant1", policy_pack1)
        registry.register_policy_pack("tenant2", policy_pack2)
        
        # Each tenant should have their own override
        tool1 = registry.get("tenant1", "tool1", domain_name="TestDomain")
        tool2 = registry.get("tenant2", "tool1", domain_name="TestDomain")
        
        assert tool1.timeout_seconds == 60.0
        assert tool2.timeout_seconds == 90.0


class TestBackwardCompatibility:
    """Tests for backward compatibility with existing code."""

    def test_get_tool_backward_compatible(self):
        """Test that get() works without domain_name for backward compatibility."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        
        # Should be able to get tool without domain_name (searches all domains)
        tool = registry.get("tenant1", "tool1")
        assert tool is not None
        assert tool.description == "Tool 1"

    def test_is_allowed_backward_compatible(self):
        """Test that is_allowed() works without domain_name."""
        registry = ToolRegistry()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        policy_pack = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1"],
        )
        
        registry.register_domain_pack("tenant1", domain_pack)
        registry.register_policy_pack("tenant1", policy_pack)
        
        # Should work without domain_name
        assert registry.is_allowed("tenant1", "tool1") is True

