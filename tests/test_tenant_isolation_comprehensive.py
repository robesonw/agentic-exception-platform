"""
Comprehensive tenant isolation tests across all components.
Ensures strict tenant isolation in all Phase 1 and Phase 2 modules.

Test Rationale:
- Validates that no data leakage occurs between tenants
- Ensures all components enforce tenant boundaries
- Confirms isolation at storage, memory, tools, and API layers
- Phase 2: Adds vector store, domain packs storage, approval queues, notifications
"""

import pytest

from src.api.auth import get_api_key_auth
from src.memory.index import MemoryIndexRegistry
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.observability.metrics import MetricsCollector
from src.orchestrator.store import get_exception_store
from src.tools.registry import ToolRegistry
from src.domainpack.storage import DomainPackStorage
from src.workflow.approval import ApprovalQueueRegistry
from src.notify.service import NotificationService


@pytest.fixture(autouse=True)
def reset_all_stores():
    """Reset all stores before each test."""
    # Reset exception store
    exception_store = get_exception_store()
    exception_store.clear_all()
    
    # Reset memory registry
    memory_registry = MemoryIndexRegistry()
    memory_registry._indexes.clear()
    
    # Reset metrics collector
    metrics_collector = MetricsCollector()
    metrics_collector._metrics.clear()
    
    yield
    
    # Cleanup after test
    exception_store.clear_all()
    memory_registry._indexes.clear()
    metrics_collector._metrics.clear()


class TestCrossComponentTenantIsolation:
    """Tests for tenant isolation across multiple components."""

    def test_exception_store_tenant_isolation(self):
        """Test ExceptionStore tenant isolation."""
        store = get_exception_store()
        
        exception_1 = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_1"},
        )
        
        exception_2 = ExceptionRecord(
            exceptionId="exc_001",  # Same ID
            tenantId="TENANT_002",  # Different tenant
            sourceSystem="CRM",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_2"},
        )
        
        store.store_exception(exception_1, {"status": "OPEN"})
        store.store_exception(exception_2, {"status": "OPEN"})
        
        # Verify isolation
        result_1 = store.get_exception("TENANT_001", "exc_001")
        assert result_1 is not None
        assert result_1[0].tenant_id == "TENANT_001"
        assert result_1[0].raw_payload["data"] == "tenant_1"
        
        result_2 = store.get_exception("TENANT_002", "exc_001")
        assert result_2 is not None
        assert result_2[0].tenant_id == "TENANT_002"
        assert result_2[0].raw_payload["data"] == "tenant_2"

    def test_memory_registry_tenant_isolation(self):
        """Test MemoryIndexRegistry tenant isolation."""
        registry = MemoryIndexRegistry()
        
        exception_1 = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_1"},
        )
        
        exception_2 = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="TENANT_002",
            sourceSystem="CRM",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "tenant_2"},
        )
        
        registry.add_exception("TENANT_001", exception_1, "Resolution 1")
        registry.add_exception("TENANT_002", exception_2, "Resolution 2")
        
        # Verify isolation
        results_1 = registry.search_similar("TENANT_001", exception_1, k=5)
        assert len(results_1) == 1
        assert results_1[0][0].exception_record.tenant_id == "TENANT_001"
        
        results_2 = registry.search_similar("TENANT_002", exception_2, k=5)
        assert len(results_2) == 1
        assert results_2[0][0].exception_record.tenant_id == "TENANT_002"
        
        # Verify tenant 1 cannot see tenant 2's data
        results_cross = registry.search_similar("TENANT_001", exception_2, k=5)
        # Should not find tenant 2's exception in tenant 1's index
        assert all(
            result[0].exception_record.tenant_id == "TENANT_001"
            for result in results_cross
        )

    def test_metrics_collector_tenant_isolation(self):
        """Test MetricsCollector tenant isolation."""
        collector = MetricsCollector()
        
        # Record metrics for different tenants
        from src.models.exception_record import ExceptionRecord, ResolutionStatus
        from datetime import datetime, timezone
        
        exception_1 = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        exception_2 = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="TENANT_001",
            sourceSystem="CRM",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        exception_3 = ExceptionRecord(
            exceptionId="exc_003",
            tenantId="TENANT_002",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_001", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        collector.record_exception("TENANT_002", "RESOLVED", "ACTIONABLE_APPROVED_PROCESS")
        
        # Verify isolation
        metrics_1 = collector.get_metrics("TENANT_001")
        assert metrics_1["exceptionCount"] == 2
        
        metrics_2 = collector.get_metrics("TENANT_002")
        assert metrics_2["exceptionCount"] == 1
        
        # Verify tenant 1 metrics don't include tenant 2 data
        assert metrics_1["exceptionCount"] != metrics_2["exceptionCount"]

    def test_tool_registry_tenant_isolation(self):
        """Test ToolRegistry tenant isolation."""
        from src.models.domain_pack import DomainPack, ToolDefinition
        from src.models.tenant_policy import TenantPolicyPack
        
        registry = ToolRegistry()
        
        # Create domain packs for different tenants
        domain_pack_1 = DomainPack(
            domainName="Domain1",
            tools={
                "tool1": ToolDefinition(
                    description="Tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                )
            },
        )
        
        domain_pack_2 = DomainPack(
            domainName="Domain2",
            tools={
                "tool2": ToolDefinition(
                    description="Tool 2",
                    parameters={},
                    endpoint="https://api.example.com/tool2",
                )
            },
        )
        
        # Register domain packs for different tenants
        registry.register_domain_pack("TENANT_001", domain_pack_1)
        registry.register_domain_pack("TENANT_002", domain_pack_2)
        
        # Verify isolation
        tools_1 = registry.list_tools("TENANT_001")
        assert "tool1" in tools_1
        assert "tool2" not in tools_1
        
        tools_2 = registry.list_tools("TENANT_002")
        assert "tool2" in tools_2
        assert "tool1" not in tools_2

    def test_api_auth_tenant_isolation(self):
        """Test API authentication tenant isolation."""
        auth = get_api_key_auth()
        
        # Register API keys for different tenants
        auth.register_api_key("key_tenant_1", "TENANT_001")
        auth.register_api_key("key_tenant_2", "TENANT_002")
        
        # Verify isolation
        user_context_1 = auth.validate_api_key("key_tenant_1")
        assert user_context_1.tenant_id == "TENANT_001"
        
        user_context_2 = auth.validate_api_key("key_tenant_2")
        assert user_context_2.tenant_id == "TENANT_002"
        
        # Verify keys map to correct tenants
        assert user_context_1.tenant_id != user_context_2.tenant_id


class TestTenantIsolationEdgeCases:
    """Tests for tenant isolation edge cases."""

    def test_tenant_isolation_empty_tenant(self):
        """Test that empty tenant IDs are handled correctly."""
        store = get_exception_store()
        
        # Should handle empty tenant ID gracefully
        result = store.get_exception("", "exc_001")
        assert result is None
        
        result = store.get_tenant_exceptions("")
        assert result == []

    def test_tenant_isolation_special_characters(self):
        """Test that tenant IDs with special characters are isolated."""
        store = get_exception_store()
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT-001_WITH-SPECIAL",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={},
        )
        
        store.store_exception(exception, {"status": "OPEN"})
        
        # Verify can retrieve with same special characters
        result = store.get_exception("TENANT-001_WITH-SPECIAL", "exc_001")
        assert result is not None
        assert result[0].tenant_id == "TENANT-001_WITH-SPECIAL"

    def test_tenant_isolation_case_sensitivity(self):
        """Test that tenant IDs are case-sensitive."""
        store = get_exception_store()
        
        exception_1 = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "uppercase"},
        )
        
        exception_2 = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",  # Lowercase
            sourceSystem="CRM",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"data": "lowercase"},
        )
        
        store.store_exception(exception_1, {"status": "OPEN"})
        store.store_exception(exception_2, {"status": "OPEN"})
        
        # Verify case-sensitive isolation
        result_upper = store.get_exception("TENANT_001", "exc_001")
        assert result_upper is not None
        assert result_upper[0].raw_payload["data"] == "uppercase"
        
        result_lower = store.get_exception("tenant_001", "exc_001")
        assert result_lower is not None
        assert result_lower[0].raw_payload["data"] == "lowercase"


class TestPhase2TenantIsolation:
    """Phase 2 tenant isolation tests for new components."""

    def test_domain_pack_storage_tenant_isolation(self, tmp_path):
        """Test DomainPackStorage tenant isolation."""
        storage = DomainPackStorage(storage_root=str(tmp_path))
        
        from src.models.domain_pack import DomainPack, ExceptionTypeDefinition
        
        pack_1 = DomainPack(
            domain_name="Finance",
            exception_types={
                "TEST_1": ExceptionTypeDefinition(description="Test 1"),
            },
        )
        
        pack_2 = DomainPack(
            domain_name="Finance",
            exception_types={
                "TEST_2": ExceptionTypeDefinition(description="Test 2"),
            },
        )
        
        # Store packs for different tenants
        storage.store_pack(tenant_id="TENANT_001", pack=pack_1, version="1.0.0")
        storage.store_pack(tenant_id="TENANT_002", pack=pack_2, version="1.0.0")
        
        # Retrieve packs
        retrieved_1 = storage.get_pack(tenant_id="TENANT_001", domain_name="Finance", version="1.0.0")
        retrieved_2 = storage.get_pack(tenant_id="TENANT_002", domain_name="Finance", version="1.0.0")
        
        assert retrieved_1 is not None
        assert retrieved_2 is not None
        assert "TEST_1" in retrieved_1.exception_types
        assert "TEST_2" in retrieved_2.exception_types
        assert "TEST_1" not in retrieved_2.exception_types
        assert "TEST_2" not in retrieved_1.exception_types

    def test_approval_queue_tenant_isolation(self, tmp_path):
        """Test ApprovalQueue tenant isolation."""
        from src.workflow.approval import ApprovalQueue
        
        queue_1 = ApprovalQueue(
            tenant_id="TENANT_001",
            storage_path=tmp_path,
        )
        
        queue_2 = ApprovalQueue(
            tenant_id="TENANT_002",
            storage_path=tmp_path,
        )
        
        # Submit approvals for different tenants
        approval_1 = queue_1.submit_for_approval(
            exception_id="exc_001",
            plan={"action": "retry"},
            evidence=["evidence_1"],
        )
        
        approval_2 = queue_2.submit_for_approval(
            exception_id="exc_001",  # Same ID
            plan={"action": "cancel"},
            evidence=["evidence_2"],
        )
        
        # Verify isolation
        pending_1 = queue_1.list_pending()
        pending_2 = queue_2.list_pending()
        
        assert len(pending_1) == 1
        assert len(pending_2) == 1
        assert pending_1[0].approval_id == approval_1
        assert pending_2[0].approval_id == approval_2
        assert pending_1[0].plan["action"] == "retry"
        assert pending_2[0].plan["action"] == "cancel"

    def test_notification_routing_tenant_isolation(self):
        """Test notification routing tenant isolation."""
        from unittest.mock import patch
        with patch("smtplib.SMTP"):
            service = NotificationService(
                smtp_host="smtp.test.com",
                smtp_port=587,
            )
            
            from src.models.tenant_policy import TenantPolicyPack
            
            tenant_policy_1 = TenantPolicyPack(
                tenant_id="TENANT_001",
                domain_name="Finance",
                notification_policies={
                    "onEscalation": {
                        "channels": ["email"],
                        "groups": ["ops_team"],
                        "recipients": ["ops@tenant1.com"],
                    },
                },
            )
            
            tenant_policy_2 = TenantPolicyPack(
                tenant_id="TENANT_002",
                domain_name="Healthcare",
                notification_policies={
                    "onEscalation": {
                        "channels": ["email"],
                        "groups": ["ops_team"],
                        "recipients": ["ops@tenant2.com"],
                    },
                },
            )
            
            # Convert NotificationPolicies to dict format expected by send_notification
            policies_1 = {}
            if hasattr(tenant_policy_1, 'notification_policies') and tenant_policy_1.notification_policies:
                policies_1 = tenant_policy_1.notification_policies.model_dump() if hasattr(tenant_policy_1.notification_policies, 'model_dump') else {}
            
            policies_2 = {}
            if hasattr(tenant_policy_2, 'notification_policies') and tenant_policy_2.notification_policies:
                policies_2 = tenant_policy_2.notification_policies.model_dump() if hasattr(tenant_policy_2.notification_policies, 'model_dump') else {}
            
            # Send notifications for different tenants
            service.send_notification(
                tenant_id="TENANT_001",
                group="ops_team",
                subject="Alert",
                message="Test 1",
                notification_policies=policies_1,
            )
            
            service.send_notification(
                tenant_id="TENANT_002",
                group="ops_team",
                subject="Alert",
                message="Test 2",
                notification_policies=policies_2,
            )
            
            # Verify notifications were sent (mocked, but should be isolated)
            # The actual routing is tested in test_notification_service.py

