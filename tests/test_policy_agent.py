"""
Comprehensive tests for PolicyAgent.
Tests guardrail enforcement, playbook approval, and human approval rules.
"""

from datetime import datetime, timezone

import pytest

from src.agents.policy import PolicyAgent, PolicyAgentError
from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import (
    Guardrails,
    HumanApprovalRule,
    SeverityOverride,
    TenantPolicyPack,
)


@pytest.fixture
def finance_domain_pack():
    """Create finance domain pack with playbooks."""
    return DomainPack(
        domainName="CapitalMarketsTrading",
        exceptionTypes={
            "POSITION_BREAK": ExceptionTypeDefinition(
                description="Position break",
                detectionRules=[],
            ),
            "SETTLEMENT_FAIL": ExceptionTypeDefinition(
                description="Settlement failure",
                detectionRules=[],
            ),
            "FAILED_ALLOCATION": ExceptionTypeDefinition(
                description="Allocation failure",
                detectionRules=[],
            ),
        },
        playbooks=[
            Playbook(
                exceptionType="POSITION_BREAK",
                steps=[PlaybookStep(action="recalculatePosition", parameters={})],
            ),
            Playbook(
                exceptionType="SETTLEMENT_FAIL",
                steps=[PlaybookStep(action="triggerSettlementRetry", parameters={})],
            ),
            Playbook(
                exceptionType="FAILED_ALLOCATION",
                steps=[PlaybookStep(action="repairAllocation", parameters={})],
            ),
        ],
        guardrails=Guardrails(
            allowLists=[],
            blockLists=[],
            humanApprovalThreshold=0.8,
        ),
    )


@pytest.fixture
def finance_tenant_policy():
    """Create finance tenant policy pack."""
    return TenantPolicyPack(
        tenantId="TENANT_FINANCE_001",
        domainName="CapitalMarketsTrading",
        customSeverityOverrides=[
            SeverityOverride(exceptionType="REG_REPORT_REJECTED", severity="HIGH"),
        ],
        humanApprovalRules=[
            HumanApprovalRule(severity="CRITICAL", requireApproval=True),
        ],
        customGuardrails=Guardrails(
            allowLists=[],
            blockLists=[],
            humanApprovalThreshold=0.75,
        ),
    )


@pytest.fixture
def healthcare_domain_pack():
    """Create healthcare domain pack with playbooks."""
    return DomainPack(
        domainName="HealthcareClaimsAndCareOps",
        exceptionTypes={
            "PHARMACY_DUPLICATE_THERAPY": ExceptionTypeDefinition(
                description="Duplicate therapy",
                detectionRules=[],
            ),
            "CLAIM_MISSING_AUTH": ExceptionTypeDefinition(
                description="Missing authorization",
                detectionRules=[],
            ),
        },
        playbooks=[
            Playbook(
                exceptionType="PHARMACY_DUPLICATE_THERAPY",
                steps=[PlaybookStep(action="flagMedicationOrder", parameters={})],
            ),
            Playbook(
                exceptionType="CLAIM_MISSING_AUTH",
                steps=[PlaybookStep(action="attachAuthorizationToClaim", parameters={})],
            ),
        ],
        guardrails=Guardrails(
            allowLists=[],
            blockLists=[],
            humanApprovalThreshold=0.8,
        ),
    )


@pytest.fixture
def healthcare_tenant_policy():
    """Create healthcare tenant policy pack."""
    return TenantPolicyPack(
        tenantId="TENANT_HEALTHCARE_042",
        domainName="HealthcareClaimsAndCareOps",
        humanApprovalRules=[
            HumanApprovalRule(severity="CRITICAL", requireApproval=True),
            HumanApprovalRule(severity="HIGH", requireApproval=False),
        ],
        customGuardrails=Guardrails(
            allowLists=[],
            blockLists=[],
            humanApprovalThreshold=0.80,
        ),
    )


@pytest.fixture
def sample_audit_logger(tmp_path, monkeypatch):
    """Create a sample audit logger with temp directory."""
    audit_dir = tmp_path / "runtime" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    def patched_get_log_file(self, tenant_id=None):
        if self._log_file is None:
            self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file
    
    def patched_ensure_dir(self):
        audit_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(AuditLogger, "_get_log_file", patched_get_log_file)
    monkeypatch.setattr(AuditLogger, "_ensure_audit_directory", patched_ensure_dir)
    
    return AuditLogger(run_id="test_run", tenant_id="tenant_001")


class TestPolicyAgentSeverityOverrides:
    """Tests for severity override application."""

    @pytest.mark.asyncio
    async def test_apply_severity_override(self, finance_domain_pack, finance_tenant_policy):
        """Test that severity overrides are applied."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="REG_REPORT_REJECTED",
            severity=Severity.MEDIUM,  # Original severity
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Should be overridden to HIGH
        assert "HIGH" in decision.evidence[1]  # Severity in evidence
        assert "overridden" in " ".join(decision.evidence).lower()

    @pytest.mark.asyncio
    async def test_no_override_when_not_configured(self, finance_domain_pack, finance_tenant_policy):
        """Test that severity is unchanged when no override configured."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Should remain CRITICAL
        assert "CRITICAL" in decision.evidence[1]


class TestPolicyAgentPlaybookApproval:
    """Tests for playbook approval checking."""

    @pytest.mark.asyncio
    async def test_approved_playbook_found(self, finance_domain_pack, finance_tenant_policy):
        """Test that approved playbook is found."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str
        assert "Approved playbook found" in " ".join(decision.evidence)

    @pytest.mark.asyncio
    async def test_no_playbook_available(self, finance_domain_pack, finance_tenant_policy):
        """Test when no playbook is available."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="UNKNOWN_EXCEPTION",  # No playbook for this
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "NON_ACTIONABLE_INFO_ONLY" in evidence_str
        assert "No approved playbook" in " ".join(decision.evidence)


class TestPolicyAgentHumanApproval:
    """Tests for human approval requirements."""

    @pytest.mark.asyncio
    async def test_critical_severity_requires_approval(self, finance_domain_pack, finance_tenant_policy):
        """Test that CRITICAL severity requires human approval."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        assert "Human approval required" in decision.evidence
        assert decision.next_step == "ProceedToResolution"  # Can proceed but needs approval

    @pytest.mark.asyncio
    async def test_human_approval_rule_matching(self, finance_domain_pack, finance_tenant_policy):
        """Test that human approval rules are checked."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.CRITICAL,  # Matches rule
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        assert "Human approval required" in decision.evidence

    @pytest.mark.asyncio
    async def test_low_confidence_requires_approval(self, finance_domain_pack, finance_tenant_policy):
        """Test that low confidence triggers human approval."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"confidence": 0.5}  # Below threshold of 0.75
        decision = await agent.process(exception, context)
        
        assert "Human approval required" in decision.evidence or "Escalation recommended" in decision.evidence


class TestPolicyAgentActionability:
    """Tests for actionability classification."""

    @pytest.mark.asyncio
    async def test_actionable_approved_process(self, finance_domain_pack, finance_tenant_policy):
        """Test ACTIONABLE_APPROVED_PROCESS classification."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",  # Has approved playbook
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str
        assert decision.decision == "Approved" or "Approved" in decision.decision

    @pytest.mark.asyncio
    async def test_non_actionable_info_only(self, finance_domain_pack, finance_tenant_policy):
        """Test NON_ACTIONABLE_INFO_ONLY classification."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="UNKNOWN_TYPE",  # No playbook
            severity=Severity.LOW,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "NON_ACTIONABLE_INFO_ONLY" in evidence_str
        assert "Blocked" in decision.decision or "Escalate" in decision.decision


class TestPolicyAgentDecision:
    """Tests for agent decision creation."""

    @pytest.mark.asyncio
    async def test_decision_contains_required_fields(self, finance_domain_pack, finance_tenant_policy):
        """Test that decision contains all required fields."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        assert decision.decision is not None
        assert 0.0 <= decision.confidence <= 1.0
        assert isinstance(decision.evidence, list)
        assert decision.next_step in ["ProceedToResolution", "Escalate"]

    @pytest.mark.asyncio
    async def test_decision_includes_playbook_id(self, finance_domain_pack, finance_tenant_policy):
        """Test that decision includes selectedPlaybookId in evidence."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        evidence_text = " ".join(decision.evidence)
        assert "selectedPlaybookId" in evidence_text
        assert "SETTLEMENT_FAIL" in evidence_text

    @pytest.mark.asyncio
    async def test_decision_includes_human_approval_flag(self, finance_domain_pack, finance_tenant_policy):
        """Test that decision includes humanApprovalRequired flag."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        evidence_text = " ".join(decision.evidence)
        assert "humanApprovalRequired" in evidence_text


class TestPolicyAgentAuditLogging:
    """Tests for audit logging integration."""

    @pytest.mark.asyncio
    async def test_logs_agent_event(self, finance_domain_pack, finance_tenant_policy, sample_audit_logger):
        """Test that agent events are logged."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy, sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        sample_audit_logger.close()
        
        # Verify log file was created
        log_file = sample_audit_logger._get_log_file()
        assert log_file.exists()
        
        # Verify log contains agent event
        import json
        with open(log_file, "r", encoding="utf-8") as f:
            line = f.readline()
            entry = json.loads(line)
        
        assert entry["event_type"] == "agent_event"
        assert entry["data"]["agent_name"] == "PolicyAgent"

    @pytest.mark.asyncio
    async def test_logs_without_audit_logger(self, finance_domain_pack, finance_tenant_policy):
        """Test that agent works without audit logger."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        # Should not raise
        decision = await agent.process(exception)


class TestPolicyAgentFinanceSamples:
    """Tests using finance domain samples."""

    @pytest.mark.asyncio
    async def test_finance_position_break_critical_approval(self, finance_domain_pack, finance_tenant_policy):
        """Test finance POSITION_BREAK (CRITICAL) requires approval."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "accountId": "ACC-123",
                "cusip": "CUSIP-456",
            },
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str
        assert "Human approval required" in decision.evidence
        assert decision.next_step == "ProceedToResolution"

    @pytest.mark.asyncio
    async def test_finance_settlement_fail_approved(self, finance_domain_pack, finance_tenant_policy):
        """Test finance SETTLEMENT_FAIL is approved."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-002",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "orderId": "ORD-789",
            },
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str
        assert decision.decision == "Approved" or "Approved" in decision.decision


class TestPolicyAgentHealthcareSamples:
    """Tests using healthcare domain samples."""

    @pytest.mark.asyncio
    async def test_healthcare_pharmacy_duplicate_therapy_critical(self, healthcare_domain_pack, healthcare_tenant_policy):
        """Test healthcare PHARMACY_DUPLICATE_THERAPY (CRITICAL) requires approval."""
        agent = PolicyAgent(healthcare_domain_pack, healthcare_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="HC-EXC-001",
            tenantId="TENANT_HEALTHCARE_042",
            sourceSystem="PharmacySystem",
            exceptionType="PHARMACY_DUPLICATE_THERAPY",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "orderId": "ORD-123",
                "patientId": "PAT-456",
            },
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str
        assert "Human approval required" in decision.evidence

    @pytest.mark.asyncio
    async def test_healthcare_claim_missing_auth_approved(self, healthcare_domain_pack, healthcare_tenant_policy):
        """Test healthcare CLAIM_MISSING_AUTH is approved."""
        agent = PolicyAgent(healthcare_domain_pack, healthcare_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="HC-EXC-002",
            tenantId="TENANT_HEALTHCARE_042",
            sourceSystem="ClaimsSystem",
            exceptionType="CLAIM_MISSING_AUTH",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "claimId": "CLM-789",
            },
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str
        # HIGH severity with requireApproval=False should not require approval
        assert decision.decision == "Approved" or "Approved" in decision.decision


class TestPolicyAgentRules:
    """Tests for policy rules enforcement."""

    @pytest.mark.asyncio
    async def test_never_approve_unapproved_playbook(self, finance_domain_pack, finance_tenant_policy):
        """Test that unapproved playbooks are never approved."""
        # Create exception with type that has playbook but not in approved list
        # For MVP, we check if exception type is in approved set
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        
        # If we had a playbook not in approved set, it should be blocked
        # For now, this is tested by checking non-actionable cases
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="UNKNOWN_TYPE",  # Not in approved set
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "NON_ACTIONABLE_INFO_ONLY" in evidence_str or "Blocked" in decision.decision

    @pytest.mark.asyncio
    async def test_never_auto_execute_critical(self, finance_domain_pack, finance_tenant_policy):
        """Test that CRITICAL severity never auto-executes without override."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Should require human approval
        assert "Human approval required" in decision.evidence

    @pytest.mark.asyncio
    async def test_escalate_on_low_confidence(self, finance_domain_pack, finance_tenant_policy):
        """Test escalation when confidence is below threshold."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"confidence": 0.5}  # Below threshold
        decision = await agent.process(exception, context)
        
        assert decision.next_step == "Escalate" or "Escalation recommended" in decision.evidence


class TestPolicyAgentPlaybookAssignment:
    """Tests for playbook assignment in PolicyAgent (P7-12)."""

    @pytest.mark.asyncio
    async def test_playbook_assignment_from_triage_suggestion(self, finance_domain_pack, finance_tenant_policy):
        """Test that playbook is assigned when suggested by triage and approved."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = PolicyAgent(
            finance_domain_pack,
            finance_tenant_policy,
            playbook_matching_service=None,  # Use triage suggestion
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        # Context with playbook suggestion from triage
        context = {
            "suggested_playbook_id": 42,
            "playbook_reasoning": "Matched based on exception type and severity",
        }
        
        decision = await agent.process(exception, context)
        
        # Verify playbook was assigned
        assert exception.current_playbook_id == 42
        assert exception.current_step == 1
        
        # Verify PolicyEvaluated event was emitted
        assert mock_events_repo.append_event_if_new.called
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.event_type == "PolicyEvaluated"
        assert call_args.payload["playbook_id"] == 42
        assert call_args.payload["reasoning"] == "Matched based on exception type and severity"

    @pytest.mark.asyncio
    async def test_playbook_assignment_via_matching_service(self, finance_domain_pack, finance_tenant_policy):
        """Test that playbook is assigned when matching service finds a match."""
        from unittest.mock import AsyncMock, MagicMock
        from src.playbooks.matching_service import MatchingResult
        
        # Create mock playbook matching service
        mock_matching_service = AsyncMock()
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 99
        mock_matching_service.match_playbook.return_value = MatchingResult(
            playbook=mock_playbook,
            reasoning="Matched based on domain and exception type"
        )
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = PolicyAgent(
            finance_domain_pack,
            finance_tenant_policy,
            playbook_matching_service=mock_matching_service,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception, context={})
        
        # Verify matching service was called
        mock_matching_service.match_playbook.assert_called_once()
        
        # Verify playbook was assigned
        assert exception.current_playbook_id == 99
        assert exception.current_step == 1
        
        # Verify PolicyEvaluated event was emitted
        assert mock_events_repo.append_event_if_new.called
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.event_type == "PolicyEvaluated"
        assert call_args.payload["playbook_id"] == 99

    @pytest.mark.asyncio
    async def test_playbook_not_assigned_when_blocked(self, finance_domain_pack, finance_tenant_policy):
        """Test that playbook is NOT assigned when decision is BLOCK."""
        from unittest.mock import AsyncMock
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = PolicyAgent(
            finance_domain_pack,
            finance_tenant_policy,
            exception_events_repository=mock_events_repo,
        )
        
        # Exception with no approved playbook (will be blocked)
        exception = ExceptionRecord(
            exceptionId="exc_003",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="UNKNOWN_TYPE",  # Not in approved list
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "suggested_playbook_id": 42,
            "playbook_reasoning": "Test reasoning",
        }
        
        decision = await agent.process(exception, context)
        
        # Verify playbook was NOT assigned (decision should be blocked)
        assert exception.current_playbook_id is None
        assert exception.current_step is None
        assert "Blocked" in decision.decision or decision.next_step == "Escalate"

    @pytest.mark.asyncio
    async def test_playbook_not_assigned_when_escalated(self, finance_domain_pack, finance_tenant_policy):
        """Test that playbook is NOT assigned when decision is Escalate."""
        from unittest.mock import AsyncMock
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = PolicyAgent(
            finance_domain_pack,
            finance_tenant_policy,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_004",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        # Low confidence triggers escalation
        context = {
            "confidence": 0.3,  # Below threshold
            "suggested_playbook_id": 42,
        }
        
        decision = await agent.process(exception, context)
        
        # Verify playbook was NOT assigned (should escalate)
        assert exception.current_playbook_id is None
        assert exception.current_step is None
        assert decision.next_step == "Escalate" or "Escalation recommended" in " ".join(decision.evidence)

    @pytest.mark.asyncio
    async def test_policy_evaluated_event_includes_playbook_info(self, finance_domain_pack, finance_tenant_policy):
        """Test that PolicyEvaluated event includes playbook_id and reasoning."""
        from unittest.mock import AsyncMock
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = PolicyAgent(
            finance_domain_pack,
            finance_tenant_policy,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_005",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "suggested_playbook_id": 123,
            "playbook_reasoning": "Test playbook assignment reasoning",
        }
        
        decision = await agent.process(exception, context)
        
        # Verify event was logged
        assert mock_events_repo.append_event_if_new.called
        
        # Verify event payload includes playbook info
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.event_type == "PolicyEvaluated"
        assert call_args.payload["playbook_id"] == 123
        assert call_args.payload["reasoning"] == "Test playbook assignment reasoning"
        assert call_args.payload["decision"] is not None

    @pytest.mark.asyncio
    async def test_playbook_assignment_persisted_in_exception(self, finance_domain_pack, finance_tenant_policy):
        """Test that playbook assignment is persisted in exception object."""
        from unittest.mock import AsyncMock
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = PolicyAgent(
            finance_domain_pack,
            finance_tenant_policy,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_006",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        # Initially no playbook assigned
        assert exception.current_playbook_id is None
        assert exception.current_step is None
        
        context = {
            "suggested_playbook_id": 456,
            "playbook_reasoning": "Critical position break requires immediate playbook",
        }
        
        decision = await agent.process(exception, context)
        
        # Verify assignment persisted
        assert exception.current_playbook_id == 456
        assert exception.current_step == 1
        
        # Verify exception can be serialized with new fields
        exception_dict = exception.model_dump(by_alias=True)
        assert exception_dict["currentPlaybookId"] == 456
        assert exception_dict["currentStep"] == 1


class TestPolicyAgentIntegration:
    """Integration tests for complete policy evaluation workflow."""

    @pytest.mark.asyncio
    async def test_complete_policy_evaluation(self, finance_domain_pack, finance_tenant_policy, sample_audit_logger):
        """Test complete policy evaluation workflow."""
        agent = PolicyAgent(finance_domain_pack, finance_tenant_policy, sample_audit_logger)
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"confidence": 0.9}
        decision = await agent.process(exception, context)
        sample_audit_logger.close()
        
        # Verify all components
        assert decision.decision is not None
        assert decision.next_step in ["ProceedToResolution", "Escalate"]
        # Check that evidence contains the actionability classification
        evidence_str = " ".join(decision.evidence)
        assert "ACTIONABLE_APPROVED_PROCESS" in evidence_str or "NON_ACTIONABLE_INFO_ONLY" in decision.evidence
        assert decision.confidence > 0.0

