"""
Comprehensive tests for Phase 2 Playbook Manager.

Tests:
- Loading playbooks from domain packs
- Selection by exception type
- Approval checking
- Tenant isolation
- Inheritance/composition
- Versioning
"""

import pytest

from src.models.domain_pack import DomainPack, Playbook, PlaybookStep, ToolDefinition
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.playbooks.manager import PlaybookManager, PlaybookManagerError


class TestPlaybookManagerLoading:
    """Tests for loading playbooks."""

    def test_load_playbooks_from_domain_pack(self):
        """Test loading playbooks from domain pack."""
        manager = PlaybookManager()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            playbooks=[
                Playbook(
                    exceptionType="TestException",
                    steps=[
                        PlaybookStep(action="invokeTool", parameters={"tool": "tool1"}),
                    ],
                ),
            ],
        )
        
        manager.load_playbooks(domain_pack, "tenant1")
        
        playbooks = manager.list_playbooks("tenant1", "TestDomain")
        assert len(playbooks) == 1
        assert playbooks[0].exception_type == "TestException"

    def test_load_playbooks_with_version(self):
        """Test loading playbooks with version."""
        manager = PlaybookManager()
        
        domain_pack = DomainPack(domainName="TestDomain", playbooks=[])
        
        manager.load_playbooks(domain_pack, "tenant1", version="2.0.0")
        
        version = manager.get_version("tenant1", "TestDomain")
        assert version == "2.0.0"

    def test_load_playbooks_empty_tenant_id_raises_error(self):
        """Test that loading with empty tenant ID raises error."""
        manager = PlaybookManager()
        
        domain_pack = DomainPack(domainName="TestDomain", playbooks=[])
        
        with pytest.raises(PlaybookManagerError):
            manager.load_playbooks(domain_pack, "")

    def test_load_playbooks_multiple_domains(self):
        """Test loading playbooks for multiple domains."""
        manager = PlaybookManager()
        
        domain_pack1 = DomainPack(
            domainName="Domain1",
            playbooks=[
                Playbook(exceptionType="Exception1", steps=[]),
            ],
        )
        domain_pack2 = DomainPack(
            domainName="Domain2",
            playbooks=[
                Playbook(exceptionType="Exception2", steps=[]),
            ],
        )
        
        manager.load_playbooks(domain_pack1, "tenant1")
        manager.load_playbooks(domain_pack2, "tenant1")
        
        playbooks1 = manager.list_playbooks("tenant1", "Domain1")
        playbooks2 = manager.list_playbooks("tenant1", "Domain2")
        
        assert len(playbooks1) == 1
        assert len(playbooks2) == 1
        assert playbooks1[0].exception_type == "Exception1"
        assert playbooks2[0].exception_type == "Exception2"


class TestPlaybookManagerSelection:
    """Tests for playbook selection."""

    @pytest.fixture
    def sample_domain_pack(self):
        """Create sample domain pack with playbooks."""
        return DomainPack(
            domainName="TestDomain",
            playbooks=[
                Playbook(
                    exceptionType="SETTLEMENT_FAIL",
                    steps=[
                        PlaybookStep(action="invokeTool", parameters={"tool": "retrySettlement"}),
                    ],
                ),
                Playbook(
                    exceptionType="PAYMENT_ERROR",
                    steps=[
                        PlaybookStep(action="invokeTool", parameters={"tool": "refundPayment"}),
                    ],
                ),
            ],
            tools={
                "retrySettlement": ToolDefinition(
                    description="Retry settlement",
                    parameters={},
                    endpoint="https://api.example.com/retry",
                ),
                "refundPayment": ToolDefinition(
                    description="Refund payment",
                    parameters={},
                    endpoint="https://api.example.com/refund",
                ),
            },
        )

    @pytest.fixture
    def sample_tenant_policy(self):
        """Create sample tenant policy."""
        return TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["retrySettlement", "refundPayment"],
        )

    @pytest.fixture
    def sample_exception(self):
        """Create sample exception record."""
        from datetime import datetime, timezone
        
        return ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant1",
            sourceSystem="TestSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )

    def test_select_playbook_by_exception_type(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test selecting playbook by exception type."""
        manager = PlaybookManager()
        manager.load_playbooks(sample_domain_pack, "tenant1")
        
        playbook = manager.select_playbook(sample_exception, sample_tenant_policy, sample_domain_pack)
        
        assert playbook is not None
        assert playbook.exception_type == "SETTLEMENT_FAIL"
        assert len(playbook.steps) == 1

    def test_select_playbook_returns_none_for_unknown_type(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that selecting playbook for unknown exception type returns None."""
        from datetime import datetime, timezone
        
        manager = PlaybookManager()
        manager.load_playbooks(sample_domain_pack, "tenant1")
        
        exception = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="tenant1",
            sourceSystem="TestSystem",
            exceptionType="UNKNOWN_EXCEPTION",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        playbook = manager.select_playbook(exception, sample_tenant_policy, sample_domain_pack)
        assert playbook is None

    def test_select_playbook_returns_none_for_no_exception_type(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that selecting playbook for exception without type returns None."""
        from datetime import datetime, timezone
        
        manager = PlaybookManager()
        manager.load_playbooks(sample_domain_pack, "tenant1")
        
        exception = ExceptionRecord(
            exceptionId="exc_003",
            tenantId="tenant1",
            sourceSystem="TestSystem",
            exceptionType=None,
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        playbook = manager.select_playbook(exception, sample_tenant_policy, sample_domain_pack)
        assert playbook is None

    def test_select_custom_playbook_from_tenant_policy(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that custom playbook from tenant policy is selected first."""
        manager = PlaybookManager()
        manager.load_playbooks(sample_domain_pack, "tenant1")
        
        # Add custom playbook to tenant policy
        custom_playbook = Playbook(
            exceptionType="SETTLEMENT_FAIL",
            steps=[
                PlaybookStep(action="invokeTool", parameters={"tool": "customTool"}),
                PlaybookStep(action="notify", parameters={"channel": "slack"}),
            ],
        )
        sample_tenant_policy.custom_playbooks.append(custom_playbook)
        
        playbook = manager.select_playbook(sample_exception, sample_tenant_policy, sample_domain_pack)
        
        # Should return custom playbook (has 2 steps vs 1 in domain pack)
        assert playbook is not None
        assert len(playbook.steps) == 2
        assert playbook.steps[0].action == "invokeTool"
        assert playbook.steps[1].action == "notify"


class TestPlaybookManagerTenantIsolation:
    """Tests for tenant isolation."""

    def test_playbooks_isolated_per_tenant(self):
        """Test that playbooks are isolated per tenant."""
        manager = PlaybookManager()
        
        domain_pack1 = DomainPack(
            domainName="TestDomain",
            playbooks=[
                Playbook(exceptionType="Exception1", steps=[]),
            ],
        )
        domain_pack2 = DomainPack(
            domainName="TestDomain",
            playbooks=[
                Playbook(exceptionType="Exception2", steps=[]),
            ],
        )
        
        manager.load_playbooks(domain_pack1, "tenant1")
        manager.load_playbooks(domain_pack2, "tenant2")
        
        playbooks1 = manager.list_playbooks("tenant1", "TestDomain")
        playbooks2 = manager.list_playbooks("tenant2", "TestDomain")
        
        assert len(playbooks1) == 1
        assert len(playbooks2) == 1
        assert playbooks1[0].exception_type == "Exception1"
        assert playbooks2[0].exception_type == "Exception2"

    def test_clear_tenant_playbooks(self):
        """Test clearing playbooks for a tenant."""
        manager = PlaybookManager()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            playbooks=[
                Playbook(exceptionType="Exception1", steps=[]),
            ],
        )
        
        manager.load_playbooks(domain_pack, "tenant1")
        assert len(manager.list_playbooks("tenant1", "TestDomain")) == 1
        
        manager.clear_tenant_playbooks("tenant1")
        assert len(manager.list_playbooks("tenant1", "TestDomain")) == 0
        assert manager.get_version("tenant1", "TestDomain") is None

    def test_tenant_cannot_access_other_tenant_playbooks(self):
        """Test that tenant cannot access other tenant's playbooks."""
        from datetime import datetime, timezone
        
        manager = PlaybookManager()
        
        domain_pack = DomainPack(
            domainName="TestDomain",
            playbooks=[
                Playbook(exceptionType="Exception1", steps=[]),
            ],
        )
        
        manager.load_playbooks(domain_pack, "tenant1")
        
        tenant_policy1 = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=[],
        )
        tenant_policy2 = TenantPolicyPack(
            tenantId="tenant2",
            domainName="TestDomain",
            approvedTools=[],
        )
        
        exception1 = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant1",
            sourceSystem="TestSystem",
            exceptionType="Exception1",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        exception2 = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="tenant2",
            sourceSystem="TestSystem",
            exceptionType="Exception1",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        # Tenant1 should find playbook
        playbook1 = manager.select_playbook(exception1, tenant_policy1, domain_pack)
        assert playbook1 is not None
        
        # Tenant2 should not find playbook (not loaded for tenant2)
        playbook2 = manager.select_playbook(exception2, tenant_policy2, domain_pack)
        assert playbook2 is None


class TestPlaybookManagerApproval:
    """Tests for playbook approval checking."""

    def test_custom_playbook_always_approved(self):
        """Test that custom playbooks are always approved."""
        manager = PlaybookManager()
        
        custom_playbook = Playbook(exceptionType="Exception1", steps=[])
        tenant_policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=[],
            customPlaybooks=[custom_playbook],
        )
        
        assert manager._is_playbook_approved(custom_playbook, tenant_policy) is True

    def test_domain_playbook_approved_by_default(self):
        """Test that domain playbooks are approved by default (MVP behavior)."""
        manager = PlaybookManager()
        
        domain_playbook = Playbook(
            exceptionType="Exception1",
            steps=[
                PlaybookStep(action="someAction", parameters={}),
            ],
        )
        tenant_policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=[],
        )
        
        # Should be approved by default (MVP)
        assert manager._is_playbook_approved(domain_playbook, tenant_policy) is True

    def test_playbook_with_approved_tool_is_approved(self):
        """Test that playbook referencing approved tool is approved."""
        manager = PlaybookManager()
        
        domain_playbook = Playbook(
            exceptionType="Exception1",
            steps=[
                PlaybookStep(
                    action="invokeTool",
                    parameters={"tool": "approvedTool"},
                ),
            ],
        )
        tenant_policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["approvedTool"],
        )
        
        assert manager._is_playbook_approved(domain_playbook, tenant_policy) is True


class TestPlaybookManagerComposition:
    """Tests for playbook inheritance and composition."""

    def test_custom_playbook_no_composition(self):
        """Test that custom playbooks are not composed."""
        manager = PlaybookManager()
        
        custom_playbook = Playbook(
            exceptionType="Exception1",
            steps=[
                PlaybookStep(action="customStep", parameters={}),
            ],
        )
        domain_pack = DomainPack(domainName="TestDomain", playbooks=[])
        tenant_policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=[],
            customPlaybooks=[custom_playbook],
        )
        
        composed = manager._apply_composition(custom_playbook, domain_pack, tenant_policy)
        
        # Should return as-is (no composition)
        assert composed == custom_playbook
        assert len(composed.steps) == 1

    def test_domain_playbook_no_parent_returns_as_is(self):
        """Test that domain playbook without parent returns as-is."""
        manager = PlaybookManager()
        
        domain_playbook = Playbook(
            exceptionType="Exception1",
            steps=[
                PlaybookStep(action="step1", parameters={}),
            ],
        )
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},  # No parent type defined
            playbooks=[],
        )
        tenant_policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=[],
        )
        
        composed = manager._apply_composition(domain_playbook, domain_pack, tenant_policy)
        
        # Should return as-is
        assert composed == domain_playbook
        assert len(composed.steps) == 1


class TestPlaybookManagerVersioning:
    """Tests for playbook versioning."""

    def test_get_version_returns_loaded_version(self):
        """Test getting version of loaded playbooks."""
        manager = PlaybookManager()
        
        domain_pack = DomainPack(domainName="TestDomain", playbooks=[])
        manager.load_playbooks(domain_pack, "tenant1", version="1.5.0")
        
        version = manager.get_version("tenant1", "TestDomain")
        assert version == "1.5.0"

    def test_get_version_returns_none_if_not_loaded(self):
        """Test that getting version for unloaded playbooks returns None."""
        manager = PlaybookManager()
        
        version = manager.get_version("tenant1", "TestDomain")
        assert version is None

    def test_version_updated_on_reload(self):
        """Test that version is updated when playbooks are reloaded."""
        manager = PlaybookManager()
        
        domain_pack = DomainPack(domainName="TestDomain", playbooks=[])
        manager.load_playbooks(domain_pack, "tenant1", version="1.0.0")
        assert manager.get_version("tenant1", "TestDomain") == "1.0.0"
        
        manager.load_playbooks(domain_pack, "tenant1", version="2.0.0")
        assert manager.get_version("tenant1", "TestDomain") == "2.0.0"

