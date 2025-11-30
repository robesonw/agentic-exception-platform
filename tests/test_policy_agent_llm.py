"""
Tests for PolicyAgent with LLM reasoning and policy explanation.

Tests Phase 3 enhancements:
- LLM-enhanced policy evaluation with structured reasoning
- Guardrail explanation and violation reporting
- Merging of LLM and rule-based decisions
- Fallback to rule-based when LLM unavailable
- Structured reasoning in audit trail and evidence
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from src.agents.policy import PolicyAgent, PolicyAgentError
from src.llm.fallbacks import FallbackReason
from src.llm.provider import LLMClient, LLMClientImpl, OpenAIProvider
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, Guardrails, Playbook, SeverityRule
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import HumanApprovalRule, TenantPolicyPack


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack for testing."""
    return DomainPack(
        domain_name="TestDomain",
        exception_types={
            "DataQualityFailure": ExceptionTypeDefinition(
                description="Data quality validation failure"
            ),
        },
        severity_rules=[
            SeverityRule(condition='exceptionType == "DataQualityFailure"', severity="HIGH"),
        ],
        playbooks=[
            Playbook(
                exception_type="DataQualityFailure",
                steps=[],
            ),
        ],
        guardrails=Guardrails(
            human_approval_threshold=0.7,
        ),
    )


@pytest.fixture
def sample_tenant_policy():
    """Create a sample tenant policy for testing."""
    return TenantPolicyPack(
        tenant_id="tenant_001",
        domain_name="TestDomain",
        custom_guardrails=Guardrails(
            human_approval_threshold=0.8,
        ),
        human_approval_rules=[
            HumanApprovalRule(
                severity="CRITICAL",
                require_approval=True,
            ),
        ],
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
        raw_payload={"error": "Invalid data format", "errorCode": "DQ001"},
    )


class TestPolicyAgentLLM:
    """Tests for PolicyAgent with LLM enhancement."""

    @pytest.mark.asyncio
    async def test_llm_enhanced_policy_success(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test successful LLM-enhanced policy evaluation."""
        # Setup LLM client with mock response
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "policy_decision": "ALLOW",
            "applied_guardrails": [
                "Human approval threshold: 0.8",
                "CRITICAL severity requires approval",
            ],
            "violated_rules": [],
            "approval_required": False,
            "approval_reason": None,
            "policy_violation_report": None,
            "tenant_policy_influence": "Tenant policy allows auto-action for HIGH severity with approved playbook.",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Evaluated exception against guardrails",
                    "outcome": "No violations detected",
                },
                {
                    "step_number": 2,
                    "description": "Checked playbook approval status",
                    "outcome": "Playbook approved for DataQualityFailure",
                },
            ],
            "evidence_references": [
                {
                    "reference_id": "tenant_policy",
                    "description": "Tenant Policy Pack guardrails",
                    "relevance_score": 1.0,
                },
            ],
            "confidence": 0.90,
            "natural_language_summary": "Exception approved for auto-action. Approved playbook available and no guardrails violated.",
        }
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "triage_decision": "Triaged DataQualityFailure HIGH",
            "confidence": 0.85,
        }
        
        # Mock llm_or_rules
        with patch("src.agents.policy.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception, context)
        
        # Verify decision
        assert decision.decision == "Approved"
        assert decision.confidence >= 0.8
        assert "ProceedToResolution" in decision.next_step
        
        # Verify evidence includes reasoning
        evidence_text = " ".join(decision.evidence)
        assert "Summary:" in evidence_text
        assert "Reasoning steps:" in evidence_text
        assert "Evidence sources:" in evidence_text
        assert "Applied guardrails:" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_policy_blocked_with_violation_report(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test LLM policy evaluation with violation report."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "policy_decision": "BLOCK",
            "applied_guardrails": ["Human approval threshold: 0.8"],
            "violated_rules": ["No approved playbook available"],
            "approval_required": False,
            "approval_reason": None,
            "policy_violation_report": "Exception blocked: No approved playbook found for this exception type.",
            "tenant_policy_influence": "Tenant policy requires approved playbook for auto-action.",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Checked playbook approval",
                    "outcome": "No approved playbook found",
                },
            ],
            "evidence_references": [],
            "confidence": 0.75,
            "natural_language_summary": "Exception blocked due to missing approved playbook.",
        }
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        # Remove approved playbook by clearing the set
        agent._approved_playbook_ids.clear()
        
        with patch("src.agents.policy.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception)
        
        # Verify decision is blocked
        assert "Blocked" in decision.decision
        evidence_text = " ".join(decision.evidence).lower()
        assert "violation report" in evidence_text
        assert "violated rules" in evidence_text or "no approved playbook" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_policy_requires_approval(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test LLM policy evaluation requiring human approval."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        # Set exception to CRITICAL to trigger approval requirement
        sample_exception.severity = Severity.CRITICAL
        
        mock_llm_response = {
            "policy_decision": "REQUIRE_APPROVAL",
            "applied_guardrails": ["CRITICAL severity requires approval"],
            "violated_rules": [],
            "approval_required": True,
            "approval_reason": "CRITICAL severity requires human approval per tenant policy",
            "policy_violation_report": None,
            "tenant_policy_influence": "Tenant policy requires approval for CRITICAL severity exceptions.",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Checked severity-based approval rules",
                    "outcome": "CRITICAL severity requires approval",
                },
            ],
            "evidence_references": [],
            "confidence": 0.85,
            "natural_language_summary": "Exception requires human approval due to CRITICAL severity.",
        }
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        with patch("src.agents.policy.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception)
        
        # Verify decision requires approval
        assert "Human approval required" in decision.decision or "approval" in decision.decision.lower()
        assert "Human approval required" in " ".join(decision.evidence)

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rule_based(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test fallback to rule-based when LLM fails."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        # Mock llm_or_rules to raise error (will trigger fallback)
        with patch("src.agents.policy.llm_or_rules", side_effect=Exception("LLM error")):
            decision = await agent.process(sample_exception)
        
        # Should still produce a valid decision (rule-based fallback)
        assert decision is not None
        assert decision.decision is not None
        assert decision.next_step is not None

    @pytest.mark.asyncio
    async def test_policy_without_llm_client(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test PolicyAgent works without LLM client (rule-based only)."""
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=None,  # No LLM client
        )
        
        decision = await agent.process(sample_exception)
        
        # Should produce valid decision using rule-based logic
        assert decision is not None
        assert decision.decision is not None
        assert decision.next_step is not None

    @pytest.mark.asyncio
    async def test_build_policy_prompt(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test build_policy_prompt() method."""
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
        )
        
        context = {
            "triage_decision": "Triaged DataQualityFailure HIGH",
            "confidence": 0.85,
        }
        
        prompt = agent.build_policy_prompt(sample_exception, context)
        
        # Verify prompt contains key elements
        assert "PolicyAgent" in prompt
        assert sample_exception.exception_id in prompt
        assert sample_exception.tenant_id in prompt
        assert "DataQualityFailure" in prompt
        assert "Guardrails" in prompt
        assert "Instructions:" in prompt
        assert "ALLOW" in prompt or "BLOCK" in prompt or "REQUIRE_APPROVAL" in prompt

    @pytest.mark.asyncio
    async def test_llm_does_not_contradict_guardrails(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that LLM reasoning does not contradict critical guardrails."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        # Remove approved playbook to force BLOCK in rule-based
        agent._approved_playbook_ids.clear()
        
        # LLM tries to ALLOW, but rule-based says BLOCK (no approved playbook)
        mock_llm_response = {
            "policy_decision": "ALLOW",  # LLM wants to allow
            "applied_guardrails": [],
            "violated_rules": [],
            "approval_required": False,
            "approval_reason": None,
            "policy_violation_report": None,
            "tenant_policy_influence": "LLM suggests allowing",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.9,
            "natural_language_summary": "LLM suggests allowing",
        }
        
        with patch("src.agents.policy.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception)
        
        # Should not allow if rule-based says BLOCK due to no approved playbook
        # Should either BLOCK or REQUIRE_APPROVAL (compromise)
        assert decision.decision != "Approved" or "approval" in decision.decision.lower()

    @pytest.mark.asyncio
    async def test_policy_reasoning_in_audit_trail(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that reasoning is stored in audit trail."""
        # Setup audit logger
        audit_logger = MagicMock()
        
        # Setup LLM client
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "policy_decision": "ALLOW",
            "applied_guardrails": ["Test guardrail"],
            "violated_rules": [],
            "approval_required": False,
            "approval_reason": None,
            "policy_violation_report": None,
            "tenant_policy_influence": "Test influence",
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
        }
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            audit_logger=audit_logger,
            llm_client=llm_client,
        )
        
        with patch("src.agents.policy.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception)
        
        # Verify audit logger was called
        assert audit_logger.log_agent_event.called
        call_args = audit_logger.log_agent_event.call_args
        assert call_args[0][0] == "PolicyAgent"  # agent_name
        assert call_args[0][2] == decision  # output decision
        
        # Verify decision evidence includes reasoning
        evidence_text = " ".join(decision.evidence)
        assert "Reasoning steps:" in evidence_text
        assert "Test reasoning step" in evidence_text

    @pytest.mark.asyncio
    async def test_policy_fallback_metadata(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test that fallback metadata is properly handled."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        # Mock llm_or_rules to return fallback result
        fallback_result = {
            "policy_decision": "ALLOW",
            "applied_guardrails": ["Rule-based guardrail"],
            "violated_rules": [],
            "approval_required": False,
            "approval_reason": None,
            "policy_violation_report": None,
            "tenant_policy_influence": "Rule-based evaluation",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.75,
            "natural_language_summary": "Rule-based fallback",
            "_metadata": {
                "llm_fallback": True,
                "fallback_reason": FallbackReason.CIRCUIT_OPEN.value,
            },
        }
        
        with patch("src.agents.policy.llm_or_rules", return_value=fallback_result):
            decision = await agent.process(sample_exception)
        
        # Should still produce valid decision
        assert decision is not None
        assert decision.decision is not None

    @pytest.mark.asyncio
    async def test_merge_policy_results_with_agreement(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test merging when LLM and rule-based agree."""
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
        )
        
        llm_result = {
            "policy_decision": "ALLOW",
            "applied_guardrails": ["Guardrail 1"],
            "violated_rules": [],
            "approval_required": False,
            "policy_violation_report": None,
            "tenant_policy_influence": "Test influence",
            "reasoning_steps": [{"step_number": 1, "description": "Test"}],
            "evidence_references": [],
            "natural_language_summary": "Test summary",
        }
        
        rule_based_result = {
            "effective_severity": Severity.HIGH,
            "applicable_playbooks": [sample_domain_pack.playbooks[0]],
            "approved_playbook": sample_domain_pack.playbooks[0],
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "human_approval_required": False,
            "should_escalate": False,
            "applied_guardrails": ["Guardrail 1"],
            "violated_rules": [],
            "policy_decision": "ALLOW",
        }
        
        decision = agent._merge_policy_results(
            sample_exception, None, llm_result, rule_based_result
        )
        
        # Should use LLM result with agreement
        assert decision.decision == "Approved" or "Approved" in decision.decision
        assert decision.confidence >= 0.8

    @pytest.mark.asyncio
    async def test_create_rule_based_policy_result(
        self, sample_domain_pack, sample_tenant_policy, sample_exception
    ):
        """Test _create_rule_based_policy_result() method."""
        agent = PolicyAgent(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
        )
        
        rule_based_result = {
            "effective_severity": Severity.HIGH,
            "applicable_playbooks": [],
            "approved_playbook": None,
            "actionability": "NON_ACTIONABLE_INFO_ONLY",
            "human_approval_required": False,
            "should_escalate": False,
            "applied_guardrails": ["Guardrail 1"],
            "violated_rules": ["No approved playbook"],
            "policy_decision": "BLOCK",
        }
        
        result = agent._create_rule_based_policy_result(
            sample_exception, None, rule_based_result
        )
        
        # Verify result structure matches PolicyLLMOutput schema
        assert result["policy_decision"] == "BLOCK"
        assert "applied_guardrails" in result
        assert "violated_rules" in result
        assert "reasoning_steps" in result
        assert "evidence_references" in result
        assert "natural_language_summary" in result
        assert len(result["reasoning_steps"]) > 0

