"""
Comprehensive tests for Phase 2 SupervisorAgent.

Tests:
- SupervisorAgent review_post_policy
- SupervisorAgent review_post_resolution
- Confidence threshold checks
- Policy compliance checks
- Severity-confidence mismatch detection
- Override to ESCALATE
- Integration with orchestrator
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from src.agents.supervisor import SupervisorAgent, SupervisorAgentError
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack, HumanApprovalRule


@pytest.fixture
def sample_domain_pack():
    """Sample domain pack for testing."""
    return DomainPack(
        domainName="Finance",
        exceptionTypes={
            "SETTLEMENT_FAIL": {
                "description": "Settlement failure",
                "detectionRules": [],
            }
        },
        playbooks=[],
    )


@pytest.fixture
def sample_tenant_policy():
    """Sample tenant policy for testing."""
    return TenantPolicyPack(
        tenantId="TENANT_A",
        domainName="Finance",
        customGuardrails={},
        humanApprovalRules=[
            HumanApprovalRule(
                severity="CRITICAL",
                requireApproval=True,
            )
        ],
    )


@pytest.fixture
def supervisor_agent(sample_domain_pack, sample_tenant_policy):
    """SupervisorAgent instance for testing."""
    return SupervisorAgent(
        domain_pack=sample_domain_pack,
        tenant_policy=sample_tenant_policy,
        min_confidence_threshold=0.6,
    )


@pytest.fixture
def sample_exception():
    """Sample exception for testing."""
    return ExceptionRecord(
        exceptionId="exc_1",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD-001"},
    )


class TestSupervisorAgentPostPolicy:
    """Tests for SupervisorAgent review_post_policy."""

    @pytest.mark.asyncio
    async def test_review_post_policy_approves_high_confidence(
        self, supervisor_agent, sample_exception
    ):
        """Test that supervisor approves high confidence policy decisions."""
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.9,
            evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
            nextStep="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.85, evidence=[], nextStep="policy"
                ),
            },
        }
        
        result = await supervisor_agent.review_post_policy(
            exception=sample_exception,
            policy_decision=policy_decision,
            context=context,
        )
        
        assert result.next_step == "ProceedToResolution"  # Preserved
        assert "approved" in result.decision.lower()
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_review_post_policy_escalates_low_confidence(
        self, supervisor_agent, sample_exception
    ):
        """Test that supervisor escalates low confidence policy decisions."""
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.4,  # Below threshold
            evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
            nextStep="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.5, evidence=[], nextStep="policy"
                ),
            },
        }
        
        result = await supervisor_agent.review_post_policy(
            exception=sample_exception,
            policy_decision=policy_decision,
            context=context,
        )
        
        assert result.next_step == "ESCALATE"
        assert "intervened" in result.decision.lower() or "escalating" in result.decision.lower()
        assert "Confidence issue" in " ".join(result.evidence)

    @pytest.mark.asyncio
    async def test_review_post_policy_escalates_critical_without_approval(
        self, supervisor_agent
    ):
        """Test that supervisor escalates CRITICAL exceptions without approval flag."""
        critical_exception = ExceptionRecord(
            exceptionId="exc_critical",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.9,
            evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
            nextStep="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.9, evidence=[], nextStep="policy"
                ),
            },
            "humanApprovalRequired": False,  # Not flagged but should be
        }
        
        result = await supervisor_agent.review_post_policy(
            exception=critical_exception,
            policy_decision=policy_decision,
            context=context,
        )
        
        assert result.next_step == "ESCALATE"
        assert "Policy breach" in " ".join(result.evidence)

    @pytest.mark.asyncio
    async def test_review_post_policy_escalates_severity_confidence_mismatch(
        self, supervisor_agent
    ):
        """Test that supervisor escalates high severity with low confidence."""
        high_severity_exception = ExceptionRecord(
            exceptionId="exc_high",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.5,  # Low for HIGH severity
            evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
            nextStep="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.6, evidence=[], nextStep="policy"
                ),
            },
        }
        
        result = await supervisor_agent.review_post_policy(
            exception=high_severity_exception,
            policy_decision=policy_decision,
            context=context,
        )
        
        assert result.next_step == "ESCALATE"
        assert "Severity issue" in " ".join(result.evidence)


class TestSupervisorAgentPostResolution:
    """Tests for SupervisorAgent review_post_resolution."""

    @pytest.mark.asyncio
    async def test_review_post_resolution_approves_safe_plan(
        self, supervisor_agent, sample_exception
    ):
        """Test that supervisor approves safe resolution plans."""
        resolution_decision = AgentDecision(
            decision="Resolution plan created",
            confidence=0.9,
            evidence=["resolvedPlan: available"],
            nextStep="ProceedToFeedback",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.85, evidence=[], nextStep="policy"
                ),
                "policy": AgentDecision(
                    decision="Policy approved",
                    confidence=0.9,
                    evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                    nextStep="resolution",
                ),
            },
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "resolvedPlan": "available",
        }
        
        result = await supervisor_agent.review_post_resolution(
            exception=sample_exception,
            resolution_decision=resolution_decision,
            context=context,
        )
        
        assert result.next_step == "ProceedToFeedback"  # Preserved
        assert "approved" in result.decision.lower()
        assert result.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_review_post_resolution_escalates_critical_low_confidence(
        self, supervisor_agent
    ):
        """Test that supervisor escalates CRITICAL exceptions with low resolution confidence."""
        critical_exception = ExceptionRecord(
            exceptionId="exc_critical",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        resolution_decision = AgentDecision(
            decision="Resolution plan created",
            confidence=0.5,  # Too low for CRITICAL
            evidence=["resolvedPlan: available"],
            nextStep="ProceedToFeedback",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.7, evidence=[], nextStep="policy"
                ),
                "policy": AgentDecision(
                    decision="Policy approved",
                    confidence=0.8,
                    evidence=[],
                    nextStep="resolution",
                ),
            },
        }
        
        result = await supervisor_agent.review_post_resolution(
            exception=critical_exception,
            resolution_decision=resolution_decision,
            context=context,
        )
        
        assert result.next_step == "ESCALATE"
        assert "Critical issue" in " ".join(result.evidence)

    @pytest.mark.asyncio
    async def test_review_post_resolution_escalates_missing_plan(
        self, supervisor_agent, sample_exception
    ):
        """Test that supervisor escalates actionable exceptions without resolution plan."""
        resolution_decision = AgentDecision(
            decision="Resolution attempted",
            confidence=0.8,
            evidence=[],
            nextStep="ProceedToFeedback",
        )
        
        context = {
            "prior_outputs": {
                "policy": AgentDecision(
                    decision="Policy approved",
                    confidence=0.9,
                    evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                    nextStep="resolution",
                ),
            },
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "resolvedPlan": None,  # Missing plan
        }
        
        result = await supervisor_agent.review_post_resolution(
            exception=sample_exception,
            resolution_decision=resolution_decision,
            context=context,
        )
        
        assert result.next_step == "ESCALATE"
        assert "Safety issue" in " ".join(result.evidence)


class TestSupervisorAgentConfidenceChecks:
    """Tests for confidence checking logic."""

    @pytest.mark.asyncio
    async def test_confidence_degradation_detection(
        self, supervisor_agent, sample_exception
    ):
        """Test that supervisor detects confidence degradation."""
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.4,  # Degraded from 0.9
            evidence=[],
            nextStep="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.9, evidence=[], nextStep="policy"
                ),
            },
        }
        
        result = await supervisor_agent.review_post_policy(
            exception=sample_exception,
            policy_decision=policy_decision,
            context=context,
        )
        
        assert result.next_step == "ESCALATE"
        assert "degraded" in " ".join(result.evidence).lower()


class TestSupervisorAgentIntegration:
    """Tests for SupervisorAgent integration with orchestrator."""

    @pytest.mark.asyncio
    async def test_supervisor_override_escalates_exception(
        self, supervisor_agent, sample_exception
    ):
        """Test that supervisor override sets exception status to ESCALATED."""
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.4,  # Low confidence
            evidence=[],
            nextStep="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged", confidence=0.5, evidence=[], nextStep="policy"
                ),
            },
        }
        
        result = await supervisor_agent.review_post_policy(
            exception=sample_exception,
            policy_decision=policy_decision,
            context=context,
        )
        
        # Verify override
        assert result.next_step == "ESCALATE"
        assert result.confidence >= 0.8  # High confidence in escalation decision

