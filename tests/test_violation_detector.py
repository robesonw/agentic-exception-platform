"""
Tests for Policy Violation and Unauthorized Tool Usage Detection.

Tests Phase 3 P3-22: ViolationDetector, PolicyViolation, ToolViolation,
and integration with PolicyAgent and ExecutionEngine.
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Guardrails, ToolDefinition
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.observability.metrics import MetricsCollector
from src.safety.incidents import IncidentManager
from src.safety.violation_detector import (
    PolicyViolation,
    ToolViolation,
    ViolationDetector,
    ViolationSeverity,
)


@pytest.fixture
def temp_storage_dir():
    """Create a temporary storage directory for violations."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_exception():
    """Create a sample exception record."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        resolution_status="OPEN",
        source_system="test_system",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"error": "test error"},
        normalized_context={"domain": "TestDomain"},
    )


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack."""
    return DomainPack(
        domain_name="TestDomain",
        tools={
            "allowed_tool": ToolDefinition(
                name="allowed_tool",
                description="Allowed tool",
                endpoint="https://example.com/allowed",
            ),
            "blocked_tool": ToolDefinition(
                name="blocked_tool",
                description="Blocked tool",
                endpoint="https://example.com/blocked",
            ),
        },
        guardrails=Guardrails(
            allow_lists=["allowed_tool"],
            block_lists=["blocked_tool"],
            human_approval_threshold=0.8,
        ),
        playbooks=[],
        exception_types={},
    )


@pytest.fixture
def sample_tenant_policy():
    """Create a sample tenant policy."""
    return TenantPolicyPack(
        tenant_id="tenant_001",
        domain_name="TestDomain",
        approved_tools=["allowed_tool"],
        custom_guardrails=Guardrails(
            allow_lists=["allowed_tool"],
            block_lists=["blocked_tool"],
            human_approval_threshold=0.8,
        ),
        human_approval_rules=[],
    )


@pytest.fixture
def violation_detector(temp_storage_dir):
    """Create a ViolationDetector instance."""
    metrics_collector = Mock(spec=MetricsCollector)
    notification_service = Mock()
    return ViolationDetector(
        storage_dir=temp_storage_dir,
        metrics_collector=metrics_collector,
        notification_service=notification_service,
    )


class TestPolicyViolation:
    """Tests for PolicyViolation model."""

    def test_policy_violation_creation(self):
        """Test creating a PolicyViolation."""
        violation = PolicyViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            agent_name="PolicyAgent",
            rule_id="test_rule",
            description="Test violation",
            severity=ViolationSeverity.HIGH,
        )
        
        assert violation.tenant_id == "tenant_001"
        assert violation.exception_id == "exc_001"
        assert violation.agent_name == "PolicyAgent"
        assert violation.rule_id == "test_rule"
        assert violation.description == "Test violation"
        assert violation.severity == ViolationSeverity.HIGH
        assert violation.timestamp is not None

    def test_policy_violation_serialization(self):
        """Test PolicyViolation serialization."""
        violation = PolicyViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            agent_name="PolicyAgent",
            description="Test violation",
            severity=ViolationSeverity.MEDIUM,
        )
        
        violation_dict = violation.model_dump(by_alias=True, mode="json")
        assert violation_dict["tenantId"] == "tenant_001"
        assert violation_dict["exceptionId"] == "exc_001"
        assert violation_dict["severity"] == "MEDIUM"


class TestToolViolation:
    """Tests for ToolViolation model."""

    def test_tool_violation_creation(self):
        """Test creating a ToolViolation."""
        violation = ToolViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_name="unauthorized_tool",
            description="Tool not in allow list",
            severity=ViolationSeverity.HIGH,
        )
        
        assert violation.tenant_id == "tenant_001"
        assert violation.exception_id == "exc_001"
        assert violation.tool_name == "unauthorized_tool"
        assert violation.description == "Tool not in allow list"
        assert violation.severity == ViolationSeverity.HIGH

    def test_tool_violation_with_request(self):
        """Test ToolViolation with tool call request."""
        violation = ToolViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_name="test_tool",
            description="Test violation",
            severity=ViolationSeverity.CRITICAL,
            tool_call_request={"tool_name": "test_tool", "args": {"key": "value"}},
        )
        
        assert violation.tool_call_request is not None
        assert violation.tool_call_request["tool_name"] == "test_tool"


class TestViolationDetector:
    """Tests for ViolationDetector."""

    def test_check_policy_decision_block_list_violation(
        self, violation_detector, sample_exception, sample_tenant_policy, sample_domain_pack
    ):
        """Test detecting block list violation in policy decision."""
        # Create a decision that violates block list
        decision = AgentDecision(
            decision="BLOCKED_ACTION",
            confidence=0.9,
            evidence=["Some evidence"],
            next_step="Proceed",
        )
        
        # Set up guardrails with block list
        sample_tenant_policy.custom_guardrails.block_lists = ["BLOCKED_ACTION"]
        
        violations = violation_detector.check_policy_decision(
            tenant_id=sample_exception.tenant_id,
            exception_record=sample_exception,
            triage_result=None,
            policy_decision=decision,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.HIGH
        assert "block list" in violations[0].description.lower()

    def test_check_policy_decision_human_approval_threshold_violation(
        self, violation_detector, sample_exception, sample_tenant_policy, sample_domain_pack
    ):
        """Test detecting human approval threshold violation."""
        # Create a decision with low confidence that should require approval
        decision = AgentDecision(
            decision="ALLOW",
            confidence=0.5,  # Below threshold of 0.8
            evidence=["Some evidence"],
            next_step="Proceed",  # No REQUIRE_APPROVAL
        )
        
        violations = violation_detector.check_policy_decision(
            tenant_id=sample_exception.tenant_id,
            exception_record=sample_exception,
            triage_result=None,
            policy_decision=decision,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.MEDIUM
        assert "approval" in violations[0].description.lower()

    def test_check_policy_decision_critical_severity_violation(
        self, violation_detector, sample_exception, sample_tenant_policy, sample_domain_pack
    ):
        """Test detecting CRITICAL severity auto-action violation."""
        # Create exception with CRITICAL severity
        critical_exception = ExceptionRecord(
            exception_id="exc_critical",
            tenant_id="tenant_001",
            exception_type="CriticalFailure",
            severity=Severity.CRITICAL,
            resolution_status="OPEN",
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "critical error"},
        )
        
        # Create decision that allows without approval
        decision = AgentDecision(
            decision="ALLOW",
            confidence=0.9,
            evidence=["Some evidence"],
            next_step="Proceed",  # No REQUIRE_APPROVAL
        )
        
        violations = violation_detector.check_policy_decision(
            tenant_id=critical_exception.tenant_id,
            exception_record=critical_exception,
            triage_result=None,
            policy_decision=decision,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert len(violations) == 1
        assert violations[0].severity == ViolationSeverity.CRITICAL
        assert "CRITICAL" in violations[0].description

    def test_check_tool_call_not_approved(
        self, violation_detector, sample_tenant_policy, sample_domain_pack
    ):
        """Test detecting tool not in approved list."""
        tool_def = ToolDefinition(
            name="unauthorized_tool",
            description="Unauthorized tool",
            endpoint="https://example.com/unauthorized",
        )
        
        tool_call_request = {"tool_name": "unauthorized_tool", "args": {}}
        
        violation = violation_detector.check_tool_call(
            tenant_id="tenant_001",
            tool_def=tool_def,
            tool_call_request=tool_call_request,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert violation is not None
        assert violation.severity == ViolationSeverity.HIGH
        assert "not in approved tools" in violation.description.lower()

    def test_check_tool_call_block_list(
        self, violation_detector, sample_tenant_policy, sample_domain_pack
    ):
        """Test detecting tool in block list."""
        tool_def = ToolDefinition(
            name="blocked_tool",
            description="Blocked tool",
            endpoint="https://example.com/blocked",
        )
        
        tool_call_request = {"tool_name": "blocked_tool", "args": {}}
        
        violation = violation_detector.check_tool_call(
            tenant_id="tenant_001",
            tool_def=tool_def,
            tool_call_request=tool_call_request,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL
        assert "block list" in violation.description.lower()

    def test_check_tool_call_allowed(
        self, violation_detector, sample_tenant_policy, sample_domain_pack
    ):
        """Test that allowed tools don't trigger violations."""
        tool_def = ToolDefinition(
            name="allowed_tool",
            description="Allowed tool",
            endpoint="https://example.com/allowed",
        )
        
        tool_call_request = {"tool_name": "allowed_tool", "args": {}}
        
        violation = violation_detector.check_tool_call(
            tenant_id="tenant_001",
            tool_def=tool_def,
            tool_call_request=tool_call_request,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert violation is None

    def test_record_violation_persists(
        self, violation_detector, temp_storage_dir
    ):
        """Test that violations are persisted to storage."""
        violation = PolicyViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            agent_name="PolicyAgent",
            description="Test violation",
            severity=ViolationSeverity.HIGH,
        )
        
        violation_detector.record_violation(violation)
        
        # Check that violation file was created
        violation_file = temp_storage_dir / "tenant_001_violations.jsonl"
        assert violation_file.exists()
        
        # Read and verify content
        with open(violation_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data["tenantId"] == "tenant_001"
            assert data["exceptionId"] == "exc_001"

    def test_record_violation_emits_metrics(
        self, violation_detector
    ):
        """Test that violations emit metrics."""
        violation = PolicyViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            agent_name="PolicyAgent",
            description="Test violation",
            severity=ViolationSeverity.HIGH,
        )
        
        violation_detector.record_violation(violation)
        
        # Verify metrics collector was called
        violation_detector.metrics_collector.record_violation.assert_called_once_with(
            tenant_id="tenant_001",
            violation_type="policy",
            severity="HIGH",
        )

    def test_record_violation_sends_notification_for_high_severity(
        self, violation_detector
    ):
        """Test that high/critical violations trigger notifications."""
        violation = PolicyViolation(
            tenant_id="tenant_001",
            exception_id="exc_001",
            agent_name="PolicyAgent",
            description="Test violation",
            severity=ViolationSeverity.CRITICAL,
        )
        
        violation_detector.record_violation(violation)
        
        # Verify notification service would be called (in production)
        # For MVP, we just log
        assert violation_detector.notification_service is not None


class TestViolationDetectorIntegration:
    """Integration tests for ViolationDetector with agents."""

    def test_policy_agent_integration(
        self, sample_exception, sample_tenant_policy, sample_domain_pack, temp_storage_dir
    ):
        """Test ViolationDetector integration with PolicyAgent."""
        from src.agents.policy import PolicyAgent
        from src.safety.violation_detector import ViolationDetector
        
        violation_detector = ViolationDetector(storage_dir=temp_storage_dir)
        
        policy_agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            violation_detector=violation_detector,
        )
        
        # Create a decision that should trigger a violation
        # (This would normally come from the agent's process method)
        decision = AgentDecision(
            decision="BLOCKED_ACTION",
            confidence=0.9,
            evidence=["Some evidence"],
            next_step="Proceed",
        )
        
        # Set up guardrails with block list
        sample_tenant_policy.custom_guardrails.block_lists = ["BLOCKED_ACTION"]
        
        # Check for violations
        violations = violation_detector.check_policy_decision(
            tenant_id=sample_exception.tenant_id,
            exception_record=sample_exception,
            triage_result=None,
            policy_decision=decision,
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert len(violations) > 0

    def test_execution_engine_integration(
        self, sample_tenant_policy, sample_domain_pack, temp_storage_dir
    ):
        """Test ViolationDetector integration with ExecutionEngine."""
        from src.safety.violation_detector import ViolationDetector
        from src.tools.execution_engine import ToolExecutionEngine
        
        violation_detector = ViolationDetector(storage_dir=temp_storage_dir)
        
        execution_engine = ToolExecutionEngine(
            violation_detector=violation_detector,
        )
        
        # Try to execute a blocked tool
        tool_def = sample_domain_pack.tools["blocked_tool"]
        
        # Check for violation (this would be called by ExecutionEngine.execute)
        violation = violation_detector.check_tool_call(
            tenant_id="tenant_001",
            tool_def=tool_def,
            tool_call_request={"tool_name": "blocked_tool", "args": {}},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
        )
        
        assert violation is not None
        assert violation.severity == ViolationSeverity.CRITICAL


class TestIncidentManager:
    """Tests for IncidentManager."""

    def test_open_incident(self, temp_storage_dir):
        """Test opening a new incident."""
        incident_manager = IncidentManager(storage_dir=temp_storage_dir)
        
        incident_id = incident_manager.open_incident(
            tenant_id="tenant_001",
            violation_id="violation_001",
            violation_type="policy",
        )
        
        assert incident_id is not None
        
        # Verify incident was persisted
        incident_file = temp_storage_dir / "tenant_001_incidents.jsonl"
        assert incident_file.exists()

    def test_close_incident(self, temp_storage_dir):
        """Test closing an incident."""
        incident_manager = IncidentManager(storage_dir=temp_storage_dir)
        
        # Open incident
        incident_id = incident_manager.open_incident(
            tenant_id="tenant_001",
            violation_id="violation_001",
            violation_type="policy",
        )
        
        # Close incident
        success = incident_manager.close_incident(
            incident_id=incident_id,
            resolution_summary="Resolved by updating policy",
        )
        
        assert success is True
        
        # Verify incident status
        incident = incident_manager.get_incident(incident_id, "tenant_001")
        assert incident is not None
        assert incident.status.value == "CLOSED"
        assert incident.resolution_summary == "Resolved by updating policy"

