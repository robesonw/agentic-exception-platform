"""
Comprehensive unit tests for canonical schema models.
Tests strict validation, type safety, and JSON serialization.
"""

import json
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.models.agent_contracts import AgentDecision, AgentMessage
from src.models.domain_pack import (
    DomainPack,
    EntityDefinition,
    ExceptionTypeDefinition,
    Guardrails,
    Playbook,
    PlaybookStep,
    SeverityRule,
    TestCase,
    ToolDefinition,
)
from src.models.exception_record import AuditEntry, ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import HumanApprovalRule, RetentionPolicies, SeverityOverride, TenantPolicyPack


class TestExceptionRecord:
    """Tests for ExceptionRecord model."""

    def test_valid_exception_record(self):
        """Test creating a valid ExceptionRecord."""
        record = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.utcnow(),
            rawPayload={"error": "Invalid data"},
        )
        assert record.exception_id == "exc_001"
        assert record.tenant_id == "tenant_001"
        assert record.source_system == "ERP"
        assert record.resolution_status == ResolutionStatus.OPEN

    def test_exception_record_with_all_fields(self):
        """Test ExceptionRecord with all optional fields."""
        record = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="tenant_001",
            sourceSystem="CRM",
            exceptionType="DataQualityFailure",
            severity=Severity.HIGH,
            timestamp=datetime.utcnow(),
            rawPayload={"error": "Invalid format"},
            normalizedContext={"field": "value"},
            detectedRules=["rule1", "rule2"],
            suggestedActions=["retry", "escalate"],
            resolutionStatus=ResolutionStatus.IN_PROGRESS,
            auditTrail=[
                AuditEntry(
                    action="Created",
                    timestamp=datetime.utcnow(),
                    actor="IntakeAgent",
                )
            ],
        )
        assert record.exception_type == "DataQualityFailure"
        assert record.severity == Severity.HIGH
        assert len(record.audit_trail) == 1

    def test_exception_record_strict_validation(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError) as exc_info:
            ExceptionRecord(
                exceptionId="exc_001",
                tenantId="tenant_001",
                sourceSystem="ERP",
                timestamp=datetime.utcnow(),
                rawPayload={},
                invalidField="should fail",
            )
        # Pydantic v2 uses "Extra inputs are not permitted" or "extra inputs are not permitted"
        error_msg = str(exc_info.value).lower()
        assert "extra" in error_msg and ("inputs" in error_msg or "fields" in error_msg) and "permitted" in error_msg

    def test_exception_record_model_validate_json(self):
        """Test JSON validation and parsing."""
        json_data = json.dumps({
            "exceptionId": "exc_003",
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "timestamp": "2024-01-15T10:30:00Z",
            "rawPayload": {"error": "test"},
        })
        record = ExceptionRecord.model_validate_json(json_data)
        assert record.exception_id == "exc_003"
        assert isinstance(record.timestamp, datetime)

    def test_exception_record_model_dump_json(self):
        """Test JSON serialization."""
        record = ExceptionRecord(
            exceptionId="exc_004",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.utcnow(),
            rawPayload={"error": "test"},
        )
        json_str = record.model_dump_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["exceptionId"] == "exc_004"

    def test_exception_record_required_fields(self):
        """Test that required fields are enforced."""
        with pytest.raises(ValidationError):
            ExceptionRecord(
                tenantId="tenant_001",
                sourceSystem="ERP",
                timestamp=datetime.utcnow(),
                rawPayload={},
            )

    def test_exception_record_severity_enum(self):
        """Test severity enum validation."""
        with pytest.raises(ValidationError) as exc_info:
            ExceptionRecord(
                exceptionId="exc_005",
                tenantId="tenant_001",
                sourceSystem="ERP",
                timestamp=datetime.utcnow(),
                rawPayload={},
                severity="INVALID",
            )
        assert "severity" in str(exc_info.value).lower()
        assert "invalid" in str(exc_info.value).lower() or "low" in str(exc_info.value).lower()
        # Should raise validation error for invalid enum
        with pytest.raises(ValidationError):
            ExceptionRecord(
                exceptionId="exc_006",
                tenantId="tenant_001",
                sourceSystem="ERP",
                timestamp=datetime.utcnow(),
                rawPayload={},
                severity="INVALID",
            )


class TestAgentContracts:
    """Tests for AgentDecision and AgentMessage models."""

    def test_valid_agent_decision(self):
        """Test creating a valid AgentDecision."""
        decision = AgentDecision(
            decision="Classified as DataQualityFailure",
            confidence=0.85,
            evidence=["Rule matched", "RAG similarity: 0.92"],
            nextStep="ProceedToPolicy",
        )
        assert decision.decision == "Classified as DataQualityFailure"
        assert decision.confidence == 0.85
        assert len(decision.evidence) == 2
        assert decision.next_step == "ProceedToPolicy"

    def test_agent_decision_confidence_bounds(self):
        """Test confidence bounds validation."""
        # Valid confidence
        decision = AgentDecision(
            decision="Test", confidence=0.5, nextStep="Next"
        )
        assert decision.confidence == 0.5

        # Too low
        with pytest.raises(ValidationError):
            AgentDecision(decision="Test", confidence=-0.1, nextStep="Next")

        # Too high
        with pytest.raises(ValidationError):
            AgentDecision(decision="Test", confidence=1.1, nextStep="Next")

    def test_agent_decision_strict_validation(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            AgentDecision(
                decision="Test",
                confidence=0.8,
                nextStep="Next",
                invalidField="should fail",
            )

    def test_agent_decision_model_validate_json(self):
        """Test JSON validation for AgentDecision."""
        json_data = json.dumps({
            "decision": "Approved",
            "confidence": 0.9,
            "evidence": ["Rule passed"],
            "nextStep": "ProceedToResolution",
        })
        decision = AgentDecision.model_validate_json(json_data)
        assert decision.decision == "Approved"
        assert decision.confidence == 0.9

    def test_agent_message(self):
        """Test creating a valid AgentMessage."""
        exception = ExceptionRecord(
            exceptionId="exc_007",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.utcnow(),
            rawPayload={},
        )
        decision = AgentDecision(
            decision="Triaged",
            confidence=0.8,
            nextStep="ProceedToPolicy",
        )
        prior_outputs = {
            "intake": AgentDecision(
                decision="Normalized",
                confidence=1.0,
                nextStep="ProceedToTriage",
            )
        }

        message = AgentMessage(
            exception=exception,
            priorOutputs=prior_outputs,
            decision=decision,
        )
        assert message.exception.exception_id == "exc_007"
        assert message.decision.decision == "Triaged"
        assert "intake" in message.prior_outputs

    def test_agent_message_model_validate_json(self):
        """Test JSON validation for AgentMessage."""
        json_data = json.dumps({
            "exception": {
                "exceptionId": "exc_008",
                "tenantId": "tenant_001",
                "sourceSystem": "ERP",
                "timestamp": "2024-01-15T10:30:00Z",
                "rawPayload": {},
            },
            "priorOutputs": {},
            "decision": {
                "decision": "Test",
                "confidence": 0.8,
                "nextStep": "Next",
            },
        })
        message = AgentMessage.model_validate_json(json_data)
        assert message.exception.exception_id == "exc_008"
        assert message.decision.decision == "Test"


class TestDomainPack:
    """Tests for DomainPack model."""

    def test_valid_domain_pack_minimal(self):
        """Test creating a minimal valid DomainPack."""
        pack = DomainPack(domainName="Finance")
        assert pack.domain_name == "Finance"
        assert pack.entities == {}
        assert pack.exception_types == {}

    def test_domain_pack_with_all_fields(self):
        """Test DomainPack with all fields populated."""
        pack = DomainPack(
            domainName="Finance",
            entities={
                "Transaction": EntityDefinition(
                    attributes={"amount": "float", "currency": "string"},
                    relations=["Account"],
                )
            },
            exceptionTypes={
                "DataQualityFailure": ExceptionTypeDefinition(
                    description="Data quality issue",
                    detectionRules=["rule1"],
                )
            },
            severityRules=[
                SeverityRule(condition="amount > 1000", severity="HIGH")
            ],
            tools={
                "retry": ToolDefinition(
                    description="Retry operation",
                    parameters={"maxRetries": "int"},
                    endpoint="https://api.example.com/retry",
                )
            },
            playbooks=[
                Playbook(
                    exceptionType="DataQualityFailure",
                    steps=[
                        PlaybookStep(action="retry", parameters={"maxRetries": 3})
                    ],
                )
            ],
            guardrails=Guardrails(
                allowLists=["retry"],
                blockLists=["delete"],
                humanApprovalThreshold=0.8,
            ),
            testSuites=[
                TestCase(
                    input={"test": "data"},
                    expectedOutput={"result": "success"},
                )
            ],
        )
        assert pack.domain_name == "Finance"
        assert len(pack.entities) == 1
        assert len(pack.exception_types) == 1
        assert len(pack.playbooks) == 1

    def test_domain_pack_strict_validation(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            DomainPack(domainName="Finance", invalidField="should fail")

    def test_domain_pack_model_validate_json(self):
        """Test JSON validation for DomainPack."""
        json_data = json.dumps({
            "domainName": "Healthcare",
            "entities": {},
            "exceptionTypes": {},
            "severityRules": [],
            "tools": {},
            "playbooks": [],
            "guardrails": {
                "allowLists": [],
                "blockLists": [],
                "humanApprovalThreshold": 0.8,
            },
            "testSuites": [],
        })
        pack = DomainPack.model_validate_json(json_data)
        assert pack.domain_name == "Healthcare"

    def test_guardrails_threshold_validation(self):
        """Test guardrails threshold bounds."""
        # Valid threshold
        guardrails = Guardrails(humanApprovalThreshold=0.5)
        assert guardrails.human_approval_threshold == 0.5

        # Invalid threshold
        with pytest.raises(ValidationError):
            Guardrails(humanApprovalThreshold=1.5)


class TestTenantPolicyPack:
    """Tests for TenantPolicyPack model."""

    def test_valid_tenant_policy_pack_minimal(self):
        """Test creating a minimal valid TenantPolicyPack."""
        pack = TenantPolicyPack(
            tenantId="tenant_001",
            domainName="Finance",
        )
        assert pack.tenant_id == "tenant_001"
        assert pack.domain_name == "Finance"

    def test_tenant_policy_pack_with_all_fields(self):
        """Test TenantPolicyPack with all fields populated."""
        pack = TenantPolicyPack(
            tenantId="tenant_001",
            domainName="Finance",
            customSeverityOverrides=[
                SeverityOverride(exceptionType="DataQualityFailure", severity="CRITICAL")
            ],
            customGuardrails=Guardrails(
                allowLists=["retry"],
                blockLists=["delete"],
                humanApprovalThreshold=0.9,
            ),
            approvedTools=["retry", "validate"],
            humanApprovalRules=[
                HumanApprovalRule(severity="CRITICAL", requireApproval=True)
            ],
            retentionPolicies=RetentionPolicies(dataTTL=90),
            customPlaybooks=[
                Playbook(
                    exceptionType="DataQualityFailure",
                    steps=[PlaybookStep(action="retry")],
                )
            ],
        )
        assert pack.tenant_id == "tenant_001"
        assert len(pack.custom_severity_overrides) == 1
        assert pack.retention_policies is not None
        assert pack.retention_policies.data_ttl == 90

    def test_tenant_policy_pack_strict_validation(self):
        """Test that extra fields are rejected."""
        with pytest.raises(ValidationError):
            TenantPolicyPack(
                tenantId="tenant_001",
                domainName="Finance",
                invalidField="should fail",
            )

    def test_tenant_policy_pack_model_validate_json(self):
        """Test JSON validation for TenantPolicyPack."""
        json_data = json.dumps({
            "tenantId": "tenant_002",
            "domainName": "Healthcare",
            "customSeverityOverrides": [],
            "approvedTools": [],
            "humanApprovalRules": [],
            "customPlaybooks": [],
        })
        pack = TenantPolicyPack.model_validate_json(json_data)
        assert pack.tenant_id == "tenant_002"
        assert pack.domain_name == "Healthcare"

    def test_retention_policies_validation(self):
        """Test retention policies TTL validation."""
        # Valid TTL
        policies = RetentionPolicies(dataTTL=30)
        assert policies.data_ttl == 30

        # Invalid TTL (must be > 0)
        with pytest.raises(ValidationError):
            RetentionPolicies(dataTTL=0)


class TestIntegration:
    """Integration tests for model interactions."""

    def test_exception_record_with_audit_trail(self):
        """Test ExceptionRecord with multiple audit entries."""
        record = ExceptionRecord(
            exceptionId="exc_009",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.utcnow(),
            rawPayload={},
            auditTrail=[
                AuditEntry(
                    action="Created",
                    timestamp=datetime.utcnow(),
                    actor="IntakeAgent",
                ),
                AuditEntry(
                    action="Triaged",
                    timestamp=datetime.utcnow(),
                    actor="TriageAgent",
                ),
            ],
        )
        assert len(record.audit_trail) == 2
        assert record.audit_trail[0].actor == "IntakeAgent"
        assert record.audit_trail[1].actor == "TriageAgent"

    def test_agent_message_with_prior_outputs(self):
        """Test AgentMessage with multiple prior outputs."""
        exception = ExceptionRecord(
            exceptionId="exc_010",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.utcnow(),
            rawPayload={},
        )
        prior_outputs = {
            "intake": AgentDecision(
                decision="Normalized",
                confidence=1.0,
                nextStep="ProceedToTriage",
            ),
            "triage": AgentDecision(
                decision="Classified",
                confidence=0.9,
                nextStep="ProceedToPolicy",
            ),
        }
        decision = AgentDecision(
            decision="Approved",
            confidence=0.85,
            nextStep="ProceedToResolution",
        )

        message = AgentMessage(
            exception=exception,
            priorOutputs=prior_outputs,
            decision=decision,
        )
        assert len(message.prior_outputs) == 2
        assert message.prior_outputs["intake"].decision == "Normalized"
        assert message.prior_outputs["triage"].decision == "Classified"

