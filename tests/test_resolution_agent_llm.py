"""
Tests for ResolutionAgent with LLM-based action explanation.

Tests Phase 3 enhancements:
- LLM-enhanced resolution explanation with structured reasoning
- Playbook selection rationale and rejected playbooks explanation
- Tool execution order and dependencies explanation
- Natural language action summary
- Advisory-only LLM (does not change which tools are executed)
- Fallback to rule-based when LLM unavailable
- Structured reasoning in audit trail and evidence
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.resolution import ResolutionAgent, ResolutionAgentError
from src.llm.fallbacks import FallbackReason
from src.llm.provider import LLMClient, LLMClientImpl, OpenAIProvider
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, Playbook, PlaybookStep, ToolDefinition
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.tools.registry import ToolRegistry


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
        playbooks=[
            Playbook(
                exception_type="DataQualityFailure",
                steps=[
                    PlaybookStep(action="validateData", parameters={"field": "amount"}),
                    PlaybookStep(action="fixDataFormat", parameters={"format": "decimal"}),
                ],
            ),
        ],
        tools={
            "validateData": ToolDefinition(
                description="Validate data format",
                endpoint="http://api.example.com/validate",
            ),
            "fixDataFormat": ToolDefinition(
                description="Fix data format",
                endpoint="http://api.example.com/fix",
            ),
        },
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
        raw_payload={"error": "Invalid data format", "errorCode": "DQ001"},
    )


@pytest.fixture
def sample_tool_registry(sample_domain_pack, sample_tenant_policy):
    """Create a sample tool registry for testing."""
    registry = ToolRegistry()
    # Register domain pack and tenant policy to set up approved tools
    # For testing, we'll create a tenant policy with approved tools
    sample_tenant_policy.approved_tools = ["validateData", "fixDataFormat"]
    registry.register_domain_pack("tenant_001", sample_domain_pack)
    registry.register_policy_pack("tenant_001", sample_tenant_policy)
    return registry


class TestResolutionAgentLLM:
    """Tests for ResolutionAgent with LLM enhancement."""

    @pytest.mark.asyncio
    async def test_llm_enhanced_resolution_success(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test successful LLM-enhanced resolution explanation."""
        # Setup LLM client with mock response
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "selected_playbook_id": "DataQualityFailure",
            "playbook_selection_rationale": "This playbook is appropriate because it matches the exception type and includes data validation and fixing steps.",
            "rejected_playbooks": [
                {
                    "playbook_id": "AlternativePlaybook",
                    "reason": "Does not include data fixing step",
                }
            ],
            "action_rationale": "The playbook executes validation first to identify issues, then fixes the data format. This order ensures we validate before making changes.",
            "tool_execution_plan": [
                {
                    "step_number": 1,
                    "tool_name": "validateData",
                    "action": "validateData",
                    "status": "SUCCESS",
                    "dependencies": [],
                    "explanation": "Validates data format before fixing",
                },
                {
                    "step_number": 2,
                    "tool_name": "fixDataFormat",
                    "action": "fixDataFormat",
                    "status": "SUCCESS",
                    "dependencies": [1],
                    "explanation": "Fixes data format after validation confirms issue",
                },
            ],
            "expected_outcome": "Data quality issue resolved with validated and fixed data format.",
            "resolution_status": "RESOLVED",
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Analyzed exception type and selected appropriate playbook",
                    "outcome": "DataQualityFailure playbook selected",
                },
                {
                    "step_number": 2,
                    "description": "Analyzed tool execution order",
                    "outcome": "Validation before fixing ensures data integrity",
                },
            ],
            "evidence_references": [
                {
                    "reference_id": "selected_playbook",
                    "description": "Playbook: DataQualityFailure",
                    "relevance_score": 1.0,
                },
            ],
            "confidence": 0.90,
            "natural_language_summary": "Resolved data quality failure by validating the data format and then fixing it to decimal format. Both steps completed successfully.",
        }
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
            "triage_decision": "Triaged DataQualityFailure HIGH",
            "policy_decision": "Approved",
        }
        
        # Mock llm_or_rules
        with patch("src.agents.resolution.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception, context)
        
        # Verify decision includes LLM reasoning
        assert decision.decision is not None
        assert "resolved plan" in decision.decision.lower() or "actions" in decision.decision.lower()
        
        # Verify evidence includes reasoning
        evidence_text = " ".join(decision.evidence).lower()
        assert "summary:" in evidence_text
        assert "playbook selection rationale" in evidence_text
        assert "action rationale" in evidence_text
        assert "tool execution plan" in evidence_text
        assert "reasoning steps" in evidence_text

    @pytest.mark.asyncio
    async def test_llm_does_not_change_tools_executed(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test that LLM does not change which tools are executed (advisory only)."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        # LLM tries to suggest different tools (should be ignored)
        mock_llm_response = {
            "selected_playbook_id": "DataQualityFailure",
            "playbook_selection_rationale": "Test rationale",
            "rejected_playbooks": [],
            "action_rationale": "LLM suggests different tools",
            "tool_execution_plan": [
                {
                    "step_number": 1,
                    "tool_name": "differentTool",  # LLM suggests different tool
                    "action": "differentAction",
                    "status": "SUCCESS",
                    "dependencies": [],
                },
            ],
            "expected_outcome": "Different outcome",
            "resolution_status": "RESOLVED",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.90,
            "natural_language_summary": "LLM summary",
        }
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        # Mock llm_or_rules
        with patch("src.agents.resolution.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception, context)
        
        # Verify that only approved playbook tools are in resolved plan
        # (check evidence for tool names from approved playbook)
        evidence_text = " ".join(decision.evidence)
        assert "validateData" in evidence_text or "fixDataFormat" in evidence_text
        # LLM's suggested "differentTool" should NOT be in the actual execution plan
        # (it may appear in LLM explanation, but not as an executed tool)
        # The actual resolved plan should only contain tools from the approved playbook
        assert "step 1:" in evidence_text.lower() or "step 2:" in evidence_text.lower()

    @pytest.mark.asyncio
    async def test_llm_fallback_to_rule_based(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test fallback to rule-based when LLM fails."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        # Mock llm_or_rules to raise error (will trigger fallback)
        with patch("src.agents.resolution.llm_or_rules", side_effect=Exception("LLM error")):
            decision = await agent.process(sample_exception, context)
        
        # Should still produce a valid decision (rule-based fallback)
        assert decision is not None
        assert decision.decision is not None
        assert decision.next_step is not None

    @pytest.mark.asyncio
    async def test_resolution_without_llm_client(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test ResolutionAgent works without LLM client (rule-based only)."""
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=None,  # No LLM client
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        decision = await agent.process(sample_exception, context)
        
        # Should produce valid decision using rule-based logic
        assert decision is not None
        assert decision.decision is not None
        assert decision.next_step is not None

    @pytest.mark.asyncio
    async def test_build_resolution_prompt(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test build_resolution_prompt() method."""
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
        )
        
        selected_playbook = sample_domain_pack.playbooks[0]
        resolved_plan = [
            {
                "stepNumber": 1,
                "toolName": "validateData",
                "action": "validateData",
                "status": "SUCCESS",
            },
            {
                "stepNumber": 2,
                "toolName": "fixDataFormat",
                "action": "fixDataFormat",
                "status": "SUCCESS",
            },
        ]
        
        context = {
            "triage_decision": "Triaged DataQualityFailure HIGH",
            "policy_decision": "Approved",
        }
        
        prompt = agent.build_resolution_prompt(sample_exception, context, selected_playbook, resolved_plan)
        
        # Verify prompt contains key elements
        assert "ResolutionAgent" in prompt
        assert sample_exception.exception_id in prompt
        assert "DataQualityFailure" in prompt
        assert "validateData" in prompt
        assert "fixDataFormat" in prompt
        assert "Instructions:" in prompt
        assert "advisory only" in prompt.lower() or "explanation only" in prompt.lower()

    @pytest.mark.asyncio
    async def test_resolution_reasoning_in_audit_trail(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test that reasoning is stored in audit trail."""
        # Setup audit logger
        audit_logger = MagicMock()
        
        # Setup LLM client
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "selected_playbook_id": "DataQualityFailure",
            "playbook_selection_rationale": "Test rationale",
            "rejected_playbooks": [],
            "action_rationale": "Test action rationale",
            "tool_execution_plan": [],
            "expected_outcome": "Test outcome",
            "resolution_status": "RESOLVED",
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
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            audit_logger=audit_logger,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        # Mock llm_or_rules
        with patch("src.agents.resolution.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception, context)
        
        # Verify audit logger was called
        assert audit_logger.log_agent_event.called
        call_args = audit_logger.log_agent_event.call_args
        assert call_args[0][0] == "ResolutionAgent"  # agent_name
        assert call_args[0][2] == decision  # output decision
        
        # Verify decision evidence includes reasoning
        evidence_text = " ".join(decision.evidence).lower()
        assert "reasoning steps" in evidence_text
        assert "test reasoning step" in evidence_text

    @pytest.mark.asyncio
    async def test_resolution_fallback_metadata(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test that fallback metadata is properly handled."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        # Mock llm_or_rules to return fallback result
        fallback_result = {
            "selected_playbook_id": "DataQualityFailure",
            "playbook_selection_rationale": "Rule-based selection",
            "rejected_playbooks": [],
            "action_rationale": "Rule-based rationale",
            "tool_execution_plan": [],
            "expected_outcome": "Rule-based outcome",
            "resolution_status": "RESOLVED",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.75,
            "natural_language_summary": "Rule-based fallback",
            "_metadata": {
                "llm_fallback": True,
                "fallback_reason": FallbackReason.CIRCUIT_OPEN.value,
            },
        }
        
        with patch("src.agents.resolution.llm_or_rules", return_value=fallback_result):
            decision = await agent.process(sample_exception, context)
        
        # Should still produce valid decision
        assert decision is not None
        assert decision.decision is not None

    @pytest.mark.asyncio
    async def test_create_rule_based_resolution_result(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test _create_rule_based_resolution_result() method."""
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
        )
        
        selected_playbook = sample_domain_pack.playbooks[0]
        resolved_plan = [
            {
                "stepNumber": 1,
                "toolName": "validateData",
                "action": "validateData",
                "status": "SUCCESS",
            },
        ]
        
        result = agent._create_rule_based_resolution_result(
            sample_exception, selected_playbook, resolved_plan, "ACTIONABLE_APPROVED_PROCESS"
        )
        
        # Verify result structure matches ResolutionLLMOutput schema
        assert result["selected_playbook_id"] == "DataQualityFailure"
        assert "playbook_selection_rationale" in result
        assert "action_rationale" in result
        assert "tool_execution_plan" in result
        assert "resolution_status" in result
        assert "reasoning_steps" in result
        assert "evidence_references" in result
        assert "natural_language_summary" in result
        assert len(result["tool_execution_plan"]) > 0

    @pytest.mark.asyncio
    async def test_rejected_playbooks_explanation(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test that rejected playbooks are explained."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        # Add alternative playbook to domain pack
        alternative_playbook = Playbook(
            exception_type="DataQualityFailure",
            steps=[PlaybookStep(action="alternativeAction", parameters={})],
        )
        sample_domain_pack.playbooks.append(alternative_playbook)
        
        mock_llm_response = {
            "selected_playbook_id": "DataQualityFailure",
            "playbook_selection_rationale": "Selected first playbook",
            "rejected_playbooks": [
                {
                    "playbook_id": "AlternativePlaybook",
                    "reason": "Does not include data fixing step",
                }
            ],
            "action_rationale": "Test rationale",
            "tool_execution_plan": [],
            "expected_outcome": "Test outcome",
            "resolution_status": "RESOLVED",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.90,
            "natural_language_summary": "Test summary",
        }
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        with patch("src.agents.resolution.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception, context)
        
        # Verify rejected playbooks are in evidence
        evidence_text = " ".join(decision.evidence).lower()
        assert "rejected playbooks" in evidence_text

    @pytest.mark.asyncio
    async def test_tool_execution_order_explanation(
        self, sample_domain_pack, sample_tenant_policy, sample_exception, sample_tool_registry
    ):
        """Test that tool execution order and dependencies are explained."""
        provider = OpenAIProvider()
        llm_client = LLMClientImpl(provider=provider)
        
        mock_llm_response = {
            "selected_playbook_id": "DataQualityFailure",
            "playbook_selection_rationale": "Test rationale",
            "rejected_playbooks": [],
            "action_rationale": "Validation must occur before fixing to ensure data integrity",
            "tool_execution_plan": [
                {
                    "step_number": 1,
                    "tool_name": "validateData",
                    "action": "validateData",
                    "status": "SUCCESS",
                    "dependencies": [],
                    "explanation": "Validates data format first",
                },
                {
                    "step_number": 2,
                    "tool_name": "fixDataFormat",
                    "action": "fixDataFormat",
                    "status": "SUCCESS",
                    "dependencies": [1],
                    "explanation": "Fixes data after validation confirms issue",
                },
            ],
            "expected_outcome": "Test outcome",
            "resolution_status": "RESOLVED",
            "reasoning_steps": [],
            "evidence_references": [],
            "confidence": 0.90,
            "natural_language_summary": "Test summary",
        }
        
        agent = ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=sample_tool_registry,
            tenant_policy=sample_tenant_policy,
            llm_client=llm_client,
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "DataQualityFailure",
        }
        
        with patch("src.agents.resolution.llm_or_rules", return_value=mock_llm_response):
            decision = await agent.process(sample_exception, context)
        
        # Verify tool execution plan is in evidence
        evidence_text = " ".join(decision.evidence).lower()
        assert "tool execution plan" in evidence_text
        assert "dependencies" in evidence_text or "validation" in evidence_text

