"""
Comprehensive tests for Phase 2 Partial Automation for Resolution Actions.

Tests:
- Auto-execution when conditions are met
- Confidence threshold checking
- CRITICAL severity never auto-executes
- Step execution status tracking
- Rollback on failure
- Escalation on failure
- Audit logging for each step
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.resolution import ResolutionAgent, ResolutionAgentError, StepExecutionStatus
from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, Playbook, PlaybookStep, ToolDefinition
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.tools.execution_engine import ToolExecutionEngine, ToolExecutionError
from src.tools.registry import ToolRegistry


class TestPartialAutomationExecution:
    """Tests for partial automation execution."""

    @pytest.fixture
    def sample_domain_pack(self):
        """Create sample domain pack with tools."""
        return DomainPack(
            domainName="TestDomain",
            tools={
                "tool1": ToolDefinition(
                    description="Test tool 1",
                    parameters={},
                    endpoint="https://api.example.com/tool1",
                ),
                "tool2": ToolDefinition(
                    description="Test tool 2",
                    parameters={},
                    endpoint="https://api.example.com/tool2",
                ),
                "rollback": ToolDefinition(
                    description="Rollback tool",
                    parameters={},
                    endpoint="https://api.example.com/rollback",
                ),
                "escalate": ToolDefinition(
                    description="Escalation tool",
                    parameters={},
                    endpoint="https://api.example.com/escalate",
                ),
            },
            playbooks=[
                Playbook(
                    exceptionType="TestException",
                    steps=[
                        PlaybookStep(action="invokeTool", parameters={"tool": "tool1"}),
                        PlaybookStep(action="invokeTool", parameters={"tool": "tool2"}),
                    ],
                ),
            ],
        )

    @pytest.fixture
    def sample_tenant_policy(self):
        """Create sample tenant policy."""
        return TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["tool1", "tool2", "rollback", "escalate"],
            humanApprovalRules=[
                {"severity": "CRITICAL", "requireApproval": True},
                {"severity": "HIGH", "requireApproval": False},
                {"severity": "MEDIUM", "requireApproval": False},
                {"severity": "LOW", "requireApproval": False},
            ],
        )

    @pytest.fixture
    def sample_exception(self):
        """Create sample exception record."""
        return ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant1",
            sourceSystem="TestSystem",
            exceptionType="TestException",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )

    @pytest.fixture
    def audit_logger(self):
        """Create mock audit logger."""
        return MagicMock(spec=AuditLogger)

    @pytest.fixture
    def execution_engine(self, audit_logger):
        """Create execution engine with mocked execution."""
        engine = ToolExecutionEngine(audit_logger=audit_logger)
        return engine

    @pytest.fixture
    def tool_registry(self, sample_domain_pack, sample_tenant_policy):
        """Create tool registry."""
        registry = ToolRegistry()
        registry.register_domain_pack("tenant1", sample_domain_pack)
        registry.register_policy_pack("tenant1", sample_tenant_policy)
        return registry

    @pytest.fixture
    def resolution_agent(
        self, sample_domain_pack, tool_registry, audit_logger, sample_tenant_policy, execution_engine
    ):
        """Create resolution agent."""
        return ResolutionAgent(
            domain_pack=sample_domain_pack,
            tool_registry=tool_registry,
            audit_logger=audit_logger,
            tenant_policy=sample_tenant_policy,
            execution_engine=execution_engine,
        )

    @pytest.mark.asyncio
    async def test_auto_execution_when_conditions_met(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that tools are auto-executed when conditions are met."""
        # Mock successful execution
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            }
            
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify both steps were executed
            assert len(resolved_plan) == 2
            assert resolved_plan[0]["status"] == StepExecutionStatus.SUCCESS.value
            assert resolved_plan[1]["status"] == StepExecutionStatus.SUCCESS.value
            assert mock_execute.call_count == 2

    @pytest.mark.asyncio
    async def test_critical_severity_never_auto_executes(
        self, resolution_agent, execution_engine
    ):
        """Test that CRITICAL severity exceptions never auto-execute."""
        critical_exception = ExceptionRecord(
            exceptionId="exc_critical",
            tenantId="tenant1",
            sourceSystem="TestSystem",
            exceptionType="TestException",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                critical_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify no execution occurred
            mock_execute.assert_not_called()
            assert resolved_plan[0]["status"] == StepExecutionStatus.NEEDS_APPROVAL.value
            assert "CRITICAL" in resolved_plan[0].get("reason", "")

    @pytest.mark.asyncio
    async def test_confidence_threshold_blocks_execution(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that low confidence blocks execution."""
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.5,  # Below default threshold of 0.8
            )
            
            # Verify no execution occurred
            mock_execute.assert_not_called()
            assert resolved_plan[0]["status"] == StepExecutionStatus.NEEDS_APPROVAL.value
            assert "Confidence" in resolved_plan[0].get("reason", "")

    @pytest.mark.asyncio
    async def test_step_execution_status_tracking(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that step execution status is properly tracked."""
        # Mock first step success, second step failure, then rollback success
        execution_results = [
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            },
            ToolExecutionError("Tool execution failed"),
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "rollback_success"},
            },
        ]
        
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = execution_results
            
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify status tracking
            assert resolved_plan[0]["status"] == StepExecutionStatus.SUCCESS.value
            assert resolved_plan[1]["status"] == StepExecutionStatus.FAILED.value
            assert "error" in resolved_plan[1]

    @pytest.mark.asyncio
    async def test_rollback_on_failure(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that rollback is attempted when a step fails."""
        # Mock first step success, second step failure, then rollback success
        execution_results = [
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            },
            ToolExecutionError("Tool execution failed"),
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "rollback_success"},
            },
        ]
        
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = execution_results
            
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify rollback was called
            assert mock_execute.call_count == 3  # 2 steps + 1 rollback
            # Last call should be rollback
            last_call = mock_execute.call_args_list[-1]
            assert last_call[1]["tool_name"] == "rollback"

    @pytest.mark.asyncio
    async def test_escalation_when_rollback_unavailable(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that escalation occurs when rollback tool is not available."""
        # Remove rollback tool from domain pack
        resolution_agent.domain_pack.tools.pop("rollback", None)
        
        # Mock first step success, second step failure
        execution_results = [
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            },
            ToolExecutionError("Tool execution failed"),
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "escalation_success"},
            },
        ]
        
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = execution_results
            
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify escalation was called (rollback not available)
            assert mock_execute.call_count == 3  # 2 steps + 1 escalation
            # Last call should be escalation
            last_call = mock_execute.call_args_list[-1]
            assert last_call[1]["tool_name"] == "escalate"

    @pytest.mark.asyncio
    async def test_audit_logging_for_each_step(
        self, resolution_agent, sample_exception, execution_engine, audit_logger
    ):
        """Test that each step execution is audit logged."""
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            }
            
            await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify audit logging was called for each step
            assert audit_logger.log_decision.call_count == 2
            calls = audit_logger.log_decision.call_args_list
            
            # Check first step audit
            assert calls[0][0][0] == "ResolutionAgent - Step Execution"
            assert calls[0][0][1]["stepNumber"] == 1
            assert calls[0][0][1]["status"] == StepExecutionStatus.SUCCESS.value
            
            # Check second step audit
            assert calls[1][0][1]["stepNumber"] == 2
            assert calls[1][0][1]["status"] == StepExecutionStatus.SUCCESS.value

    @pytest.mark.asyncio
    async def test_skipped_step_status(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that steps are marked as SKIPPED when conditions not met."""
        # Use non-actionable actionability
        resolved_plan = await resolution_agent._resolve_playbook_steps(
            sample_exception,
            resolution_agent.domain_pack.playbooks[0],
            actionability="NON_ACTIONABLE_INFO_ONLY",
            confidence=0.9,
        )
        
        # Verify steps are skipped
        assert resolved_plan[0]["status"] == StepExecutionStatus.SKIPPED.value
        assert resolved_plan[1]["status"] == StepExecutionStatus.SKIPPED.value

    @pytest.mark.asyncio
    async def test_non_approved_actionability_does_not_execute(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that non-approved actionability does not trigger execution."""
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_NON_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify no execution occurred
            mock_execute.assert_not_called()
            assert resolved_plan[0]["status"] == StepExecutionStatus.SKIPPED.value

    @pytest.mark.asyncio
    async def test_rollback_failure_triggers_escalation(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that escalation occurs when rollback fails."""
        # Mock first step success, second step failure, rollback failure, then escalation
        execution_results = [
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            },
            ToolExecutionError("Tool execution failed"),
            ToolExecutionError("Rollback failed"),
            {
                "status": "success",
                "http_status": 200,
                "response": {"result": "escalation_success"},
            },
        ]
        
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.side_effect = execution_results
            
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.9,
            )
            
            # Verify escalation was called after rollback failure
            assert mock_execute.call_count == 4  # 2 steps + 1 rollback + 1 escalation
            # Last call should be escalation
            last_call = mock_execute.call_args_list[-1]
            assert last_call[1]["tool_name"] == "escalate"

    @pytest.mark.asyncio
    async def test_confidence_threshold_from_tenant_policy(
        self, resolution_agent, sample_exception, execution_engine
    ):
        """Test that confidence threshold is read from tenant policy."""
        # Set custom guardrails with lower threshold
        from src.models.domain_pack import Guardrails
        
        resolution_agent.tenant_policy.custom_guardrails = Guardrails(
            humanApprovalThreshold=0.6
        )
        
        with patch.object(execution_engine, "execute", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {
                "status": "success",
                "http_status": 200,
                "response": {"result": "success"},
            }
            
            # Confidence 0.7 should now pass (above 0.6 threshold)
            resolved_plan = await resolution_agent._resolve_playbook_steps(
                sample_exception,
                resolution_agent.domain_pack.playbooks[0],
                actionability="ACTIONABLE_APPROVED_PROCESS",
                confidence=0.7,
            )
            
            # Verify execution occurred
            assert mock_execute.call_count == 2
            assert resolved_plan[0]["status"] == StepExecutionStatus.SUCCESS.value

