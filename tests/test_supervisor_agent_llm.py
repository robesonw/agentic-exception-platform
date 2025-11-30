"""
Tests for SupervisorAgent with LLM oversight reasoning.

Tests Phase 3 enhancements:
- LLM-enhanced oversight with structured reasoning
- Oversight decisions (OK, ESCALATE, REQUIRE_APPROVAL)
- Anomaly detection and explanation
- Guardrail enforcement (LLM cannot override blocked flows)
- Fallback to rule-based when LLM unavailable
- Structured reasoning in audit trail and evidence
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.agents.supervisor import SupervisorAgent
from src.llm.provider import LLMClient, LLMClientImpl, OpenAIProvider
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Guardrails
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack for testing."""
    return DomainPack(
        domain_name="TestDomain",
        exception_types={},
        playbooks=[],
        tools={},
        guardrails=Guardrails(human_approval_threshold=0.7),
    )


@pytest.fixture
def sample_tenant_policy():
    """Create a sample tenant policy for testing."""
    return TenantPolicyPack(
        tenant_id="tenant_001",
        domain_name="TestDomain",
        custom_guardrails=None,
        human_approval_rules=[],
        custom_severity_overrides=[],
        custom_playbooks=[],
    )


@pytest.fixture
def sample_exception():
    """Create a sample exception for testing."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        source_system="ERP",
        timestamp=datetime.now(timezone.utc),
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        raw_payload={"error": "Invalid data format"},
    )


class TestSupervisorAgentLLM:
    """Tests for SupervisorAgent with LLM enhancement."""

    @pytest.mark.asyncio
    async def test_llm_oversight_escalation(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test LLM-enhanced oversight can trigger escalation."""
        # Setup LLM client with mock response
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "oversight_decision": "ESCALATED",
            "intervention_reason": "High risk + low confidence combo detected",
            "anomaly_detected": True,
            "anomaly_description": "CRITICAL severity with confidence < 0.8",
            "agent_chain_review": {
                "inconsistencies": ["Triage confidence degraded significantly"],
                "confidence_issues": ["Policy confidence below threshold"],
            },
            "recommended_action": "ESCALATE",
            "escalation_reason": "High severity exception with low confidence across agent chain",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Reviewed agent chain confidence",
                    "outcome": "Found confidence degradation",
                },
            ],
            "evidence_references": [
                {
                    "reference_id": "guardrails",
                    "description": "Tenant policy guardrails",
                    "relevance_score": 1.0,
                },
            ],
            "confidence": 0.90,
            "natural_language_summary": "Escalating due to high risk and low confidence combination.",
            "suggested_human_message": "High severity exception with low confidence across agent chain. Please review manually.",
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.5,  # Low confidence
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.6,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Verify decision triggers escalation
        assert decision.next_step == "ESCALATE"
        assert "escalating" in decision.decision.lower()
        
        # Verify evidence includes LLM reasoning
        evidence_text = " ".join(decision.evidence).lower()
        assert "escalation reason" in evidence_text
        assert "anomaly detected" in evidence_text
        assert "reasoning steps" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_cannot_override_guardrails(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that LLM cannot allow flows that guardrails blocked."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        # LLM tries to approve, but rule-based says ESCALATE (guardrails blocked)
        mock_llm_response = {
            "oversight_decision": "APPROVED_FLOW",  # LLM wants to approve
            "intervention_reason": None,
            "anomaly_detected": False,
            "anomaly_description": None,
            "agent_chain_review": {},
            "recommended_action": "CONTINUE",
            "escalation_reason": None,
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.80,
            "natural_language_summary": "Flow approved",
            "suggested_human_message": None,
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        # Create a policy decision that should trigger escalation (low confidence)
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.4,  # Very low confidence - should trigger escalation
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.5,  # Also low
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # CRITICAL: Even though LLM said APPROVED_FLOW, guardrails should enforce ESCALATE
        assert decision.next_step == "ESCALATE", "Guardrails must be enforced even if LLM approves"
        
        # Verify warning was logged
        evidence_text = " ".join(decision.evidence).lower()
        assert "escalat" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_oversight_requires_approval(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test LLM-enhanced oversight can require approval (INTERVENED)."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "oversight_decision": "INTERVENED",
            "intervention_reason": "Moderate risk detected, requires human review",
            "anomaly_detected": True,
            "anomaly_description": "Confidence below approval threshold",
            "agent_chain_review": {
                "confidence_issues": ["Confidence below threshold"],
            },
            "recommended_action": "REQUIRE_APPROVAL",
            "escalation_reason": None,
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.85,
            "natural_language_summary": "Requiring human approval due to moderate risk.",
            "suggested_human_message": "Moderate risk detected. Please review and approve before proceeding.",
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.65,  # Below threshold
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.7,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Verify decision requires approval
        assert decision.next_step == "PENDING_APPROVAL"
        assert "requiring human approval" in decision.decision.lower()
        
        # Verify evidence includes intervention reason
        evidence_text = " ".join(decision.evidence).lower()
        assert "intervention reason" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rule_based(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test fallback to rule-based when LLM fails."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.4,  # Low confidence - should trigger escalation
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.5,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules to raise error (will trigger fallback)
        with patch("src.agents.supervisor.llm_or_rules", side_effect=Exception("LLM error")):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Should still produce a valid decision (rule-based fallback)
        assert decision is not None
        assert decision.next_step in ["ESCALATE", "ProceedToResolution"]
        # With low confidence, should escalate
        if decision.next_step == "ESCALATE":
            assert "escalating" in decision.decision.lower()

    @pytest.mark.asyncio
    async def test_supervisor_without_llm_client(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test SupervisorAgent works without LLM client (rule-based only)."""
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=None,  # No LLM client
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.4,  # Low confidence - should trigger escalation
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.5,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Should produce valid decision using rule-based logic
        assert decision is not None
        assert decision.next_step is not None
        # With low confidence, should escalate
        assert decision.next_step == "ESCALATE"

    @pytest.mark.asyncio
    async def test_build_supervisor_prompt(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test build_supervisor_prompt() method."""
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.8,
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.85,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        context_snapshot = agent._build_context_snapshot(
            sample_exception,
            context["prior_outputs"],
            policy_decision,
            context,
            checkpoint="post_policy",
        )
        
        prompt = agent.build_supervisor_prompt(context_snapshot)
        
        # Verify prompt contains key elements
        assert "SupervisorAgent" in prompt
        assert sample_exception.exception_id in prompt
        assert "Exception Details" in prompt
        assert "Agent Chain Decisions" in prompt
        assert "Guardrails" in prompt
        assert "Instructions" in prompt
        assert "guardrails have blocked" in prompt.lower() or "cannot approve flows" in prompt.lower()

    @pytest.mark.asyncio
    async def test_supervisor_reasoning_in_audit_trail(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that reasoning is stored in audit trail."""
        # Setup audit logger
        audit_logger = MagicMock()
        
        # Setup LLM client
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "oversight_decision": "ESCALATED",
            "intervention_reason": "Test intervention reason",
            "anomaly_detected": True,
            "anomaly_description": "Test anomaly",
            "agent_chain_review": {
                "inconsistencies": ["Test inconsistency"],
            },
            "recommended_action": "ESCALATE",
            "escalation_reason": "Test escalation reason",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Test reasoning step",
                    "outcome": "Test outcome",
                },
            ],
            "evidence_references": [],
            "confidence": 0.90,
            "natural_language_summary": "Test summary",
            "suggested_human_message": "Test human message",
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            audit_logger=audit_logger,
            llm_client=llm_client,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.8,
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.85,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Verify audit logger was called
        assert audit_logger.log_agent_event.called
        call_args = audit_logger.log_agent_event.call_args
        assert call_args[0][0] == "SupervisorAgent"  # agent_name
        assert call_args[0][2] == decision  # output decision
        
        # Verify decision evidence includes reasoning
        evidence_text = " ".join(decision.evidence).lower()
        assert "reasoning steps" in evidence_text
        assert "test reasoning step" in evidence_text

    @pytest.mark.asyncio
    async def test_supervisor_post_resolution_review(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test LLM-enhanced oversight at post-resolution checkpoint."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "oversight_decision": "APPROVED_FLOW",
            "intervention_reason": None,
            "anomaly_detected": False,
            "anomaly_description": None,
            "agent_chain_review": {},
            "recommended_action": "CONTINUE",
            "escalation_reason": None,
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.80,
            "natural_language_summary": "Resolution plan is safe",
            "suggested_human_message": None,
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        resolution_decision = AgentDecision(
            decision="Resolution plan created",
            confidence=0.85,
            evidence=["Resolution decision"],
            next_step="ProceedToFeedback",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.85,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
                "policy": AgentDecision(
                    decision="Policy approved",
                    confidence=0.80,
                    evidence=["Policy decision"],
                    next_step="ProceedToResolution",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_resolution(sample_exception, resolution_decision, context)
        
        # Should approve flow
        assert decision.next_step == "ProceedToFeedback"
        assert "approved" in decision.decision.lower()

    @pytest.mark.asyncio
    async def test_supervisor_anomaly_detection(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that anomalies are detected and explained."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "oversight_decision": "ESCALATED",
            "intervention_reason": "Anomaly detected",
            "anomaly_detected": True,
            "anomaly_description": "Inconsistency: Triage says HIGH but policy allows auto-action",
            "agent_chain_review": {
                "inconsistencies": ["Triage and policy decisions are inconsistent"],
            },
            "recommended_action": "ESCALATE",
            "escalation_reason": "Anomaly detected in agent chain",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Detected inconsistency between agents",
                    "outcome": "Anomaly found",
                },
            ],
            "evidence_references": [],
            "confidence": 0.90,
            "natural_language_summary": "Anomaly detected: inconsistency between triage and policy.",
            "suggested_human_message": "Anomaly detected in agent chain. Please review manually.",
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.8,
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.85,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Verify anomaly is in evidence
        evidence_text = " ".join(decision.evidence).lower()
        assert "anomaly detected" in evidence_text
        assert "inconsistency" in evidence_text

    @pytest.mark.asyncio
    async def test_supervisor_suggested_human_message(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that suggested_human_message is included in evidence."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "oversight_decision": "ESCALATED",
            "intervention_reason": "Test intervention",
            "anomaly_detected": True,
            "anomaly_description": "Test anomaly",
            "agent_chain_review": {},
            "recommended_action": "ESCALATE",
            "escalation_reason": "Test escalation",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.90,
            "natural_language_summary": "Test summary",
            "suggested_human_message": "Please review this exception manually. High risk detected.",
        }
        
        agent = SupervisorAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        policy_decision = AgentDecision(
            decision="Policy approved",
            confidence=0.8,
            evidence=["Policy decision"],
            next_step="ProceedToResolution",
        )
        
        context = {
            "prior_outputs": {
                "triage": AgentDecision(
                    decision="Triaged HIGH",
                    confidence=0.85,
                    evidence=["Triage decision"],
                    next_step="ProceedToPolicy",
                ),
            },
        }
        
        # Mock llm_or_rules
        with patch("src.agents.supervisor.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.review_post_policy(sample_exception, policy_decision, context)
        
        # Verify suggested human message is in evidence
        evidence_text = " ".join(decision.evidence).lower()
        assert "suggested human message" in evidence_text
        assert "please review" in evidence_text.lower()

