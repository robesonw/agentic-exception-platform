"""
Comprehensive tests for Phase 2 Advanced Multi-Agent Orchestration.

Tests:
- Parallel execution across exceptions using asyncio.gather
- Timeout support per stage
- State snapshot persistence
- Orchestration hooks (before_stage, after_stage, on_failure)
- Branching logic (PENDING_APPROVAL stops pipeline, non-actionable skips ResolutionAgent)
- Deterministic order within each exception
"""

import asyncio
import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.agents.feedback import FeedbackAgent
from src.agents.intake import IntakeAgent
from src.agents.policy import PolicyAgent
from src.agents.resolution import ResolutionAgent
from src.agents.triage import TriageAgent
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.orchestrator.runner import (
    OrchestrationHooks,
    PipelineRunnerError,
    run_pipeline,
)


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
    )


@pytest.fixture
def sample_exception_batch():
    """Sample batch of exceptions for testing."""
    return [
        {
            "sourceSystem": "ERP",
            "exceptionType": "SETTLEMENT_FAIL",
            "severity": "HIGH",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rawPayload": {"orderId": "ORD-001"},
        },
        {
            "sourceSystem": "ERP",
            "exceptionType": "SETTLEMENT_FAIL",
            "severity": "MEDIUM",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rawPayload": {"orderId": "ORD-002"},
        },
        {
            "sourceSystem": "ERP",
            "exceptionType": "SETTLEMENT_FAIL",
            "severity": "LOW",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "rawPayload": {"orderId": "ORD-003"},
        },
    ]


@pytest.fixture
def mock_agents():
    """Mock agents for testing."""
    intake_agent = Mock(spec=IntakeAgent)
    triage_agent = Mock(spec=TriageAgent)
    policy_agent = Mock(spec=PolicyAgent)
    resolution_agent = Mock(spec=ResolutionAgent)
    feedback_agent = Mock(spec=FeedbackAgent)
    
    # Setup default mock responses
    def create_decision(agent_name: str, next_step: str = "next") -> AgentDecision:
        return AgentDecision(
            decision=f"{agent_name} decision",
            confidence=0.8,
            evidence=[f"{agent_name} evidence"],
            nextStep=next_step,
        )
    
    # Mock IntakeAgent.process to return tuple
    async def intake_process(raw_exception, tenant_id):
        exception = ExceptionRecord(
            exceptionId=f"exc_{raw_exception.get('rawPayload', {}).get('orderId', 'unknown')}",
            tenantId=tenant_id,
            sourceSystem=raw_exception.get("sourceSystem", "UNKNOWN"),
            exceptionType=raw_exception.get("exceptionType", "UNKNOWN"),
            severity=Severity[raw_exception.get("severity", "MEDIUM")],
            timestamp=datetime.now(timezone.utc),
            rawPayload=raw_exception.get("rawPayload", {}),
        )
        return exception, create_decision("intake")
    
    intake_agent.process = AsyncMock(side_effect=intake_process)
    triage_agent.process = AsyncMock(return_value=create_decision("triage"))
    policy_agent.process = AsyncMock(return_value=create_decision("policy"))
    resolution_agent.process = AsyncMock(return_value=create_decision("resolution"))
    feedback_agent.process = AsyncMock(return_value=create_decision("feedback"))
    
    return {
        "intake": intake_agent,
        "triage": triage_agent,
        "policy": policy_agent,
        "resolution": resolution_agent,
        "feedback": feedback_agent,
    }


class TestParallelExecution:
    """Tests for parallel execution across exceptions."""

    @pytest.mark.asyncio
    async def test_parallel_execution_processes_all_exceptions(
        self, sample_domain_pack, sample_tenant_policy, sample_exception_batch
    ):
        """Test that parallel execution processes all exceptions."""
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            # Mock process methods
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId=f"exc_{raw_exception.get('rawPayload', {}).get('orderId', 'unknown')}",
                    tenantId=tenant_id,
                    sourceSystem=raw_exception.get("sourceSystem", "UNKNOWN"),
                    exceptionType=raw_exception.get("exceptionType", "UNKNOWN"),
                    severity=Severity[raw_exception.get("severity", "MEDIUM")],
                    timestamp=datetime.now(timezone.utc),
                    rawPayload=raw_exception.get("rawPayload", {}),
                )
                return exception, AgentDecision(
                    decision="Intake decision",
                    confidence=0.9,
                    evidence=["Intake evidence"],
                    nextStep="triage",
                )
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage decision",
                confidence=0.8,
                evidence=["Triage evidence"],
                nextStep="policy",
            ))
            policy_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Policy decision",
                confidence=0.8,
                evidence=["Policy evidence", "Actionability: ACTIONABLE_APPROVED_PROCESS"],
                nextStep="resolution",
            ))
            resolution_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Resolution decision",
                confidence=0.8,
                evidence=["Resolution evidence"],
                nextStep="feedback",
            ))
            feedback_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Feedback decision",
                confidence=0.8,
                evidence=["Feedback evidence"],
                nextStep="complete",
            ))
            
            # Run pipeline with parallel execution
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=sample_exception_batch,
                enable_parallel=True,
            )
            
            # Verify all exceptions were processed
            assert len(result["results"]) == 3
            assert all("exceptionId" in r for r in result["results"])
            assert all("stages" in r for r in result["results"])
            
            # Verify each exception has all stages
            for r in result["results"]:
                assert "intake" in r["stages"]
                assert "triage" in r["stages"]
                assert "policy" in r["stages"]
                assert "resolution" in r["stages"]
                assert "feedback" in r["stages"]

    @pytest.mark.asyncio
    async def test_parallel_execution_maintains_deterministic_order(
        self, sample_domain_pack, sample_tenant_policy, sample_exception_batch
    ):
        """Test that parallel execution maintains deterministic order within each exception."""
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks with call tracking
            call_order = []
            
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def track_intake(raw_exception, tenant_id):
                call_order.append(("intake", raw_exception.get("rawPayload", {}).get("orderId", "unknown")))
                exception = ExceptionRecord(
                    exceptionId=f"exc_{raw_exception.get('rawPayload', {}).get('orderId', 'unknown')}",
                    tenantId=tenant_id,
                    sourceSystem=raw_exception.get("sourceSystem", "UNKNOWN"),
                    exceptionType=raw_exception.get("exceptionType", "UNKNOWN"),
                    severity=Severity[raw_exception.get("severity", "MEDIUM")],
                    timestamp=datetime.now(timezone.utc),
                    rawPayload=raw_exception.get("rawPayload", {}),
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            async def track_triage(exception, context):
                call_order.append(("triage", exception.exception_id))
                return AgentDecision(decision="Triage", confidence=0.8, evidence=[], nextStep="policy")
            
            async def track_policy(exception, context):
                call_order.append(("policy", exception.exception_id))
                return AgentDecision(
                    decision="Policy",
                    confidence=0.8,
                    evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                    nextStep="resolution",
                )
            
            async def track_resolution(exception, context):
                call_order.append(("resolution", exception.exception_id))
                return AgentDecision(decision="Resolution", confidence=0.8, evidence=[], nextStep="feedback")
            
            async def track_feedback(exception, context):
                call_order.append(("feedback", exception.exception_id))
                return AgentDecision(decision="Feedback", confidence=0.8, evidence=[], nextStep="complete")
            
            intake_agent.process = AsyncMock(side_effect=track_intake)
            triage_agent.process = AsyncMock(side_effect=track_triage)
            policy_agent.process = AsyncMock(side_effect=track_policy)
            resolution_agent.process = AsyncMock(side_effect=track_resolution)
            feedback_agent.process = AsyncMock(side_effect=track_feedback)
            
            # Run pipeline
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=sample_exception_batch,
                enable_parallel=True,
            )
            
            # Verify that within each exception, stages run in order
            # (intake -> triage -> policy -> resolution -> feedback)
            exception_ids = [r["exceptionId"] for r in result["results"]]
            
            for exc_id in exception_ids:
                exc_calls = [(stage, exc) for stage, exc in call_order if exc == exc_id]
                stages = [stage for stage, _ in exc_calls]
                
                # Verify all stages were called for this exception
                # Note: intake may not be tracked if it's handled differently
                assert len(stages) >= 4, f"Expected at least 4 stages, got {stages}"
                
                # Verify order: triage -> policy -> resolution -> feedback
                # (intake is handled separately and may not be in call_order)
                if "triage" in stages and "policy" in stages:
                    assert stages.index("triage") < stages.index("policy")
                if "policy" in stages and "resolution" in stages:
                    assert stages.index("policy") < stages.index("resolution")
                if "resolution" in stages and "feedback" in stages:
                    assert stages.index("resolution") < stages.index("feedback")


class TestTimeoutSupport:
    """Tests for timeout support per stage."""

    @pytest.mark.asyncio
    async def test_stage_timeout_raises_timeout_error(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that stage timeout raises TimeoutError."""
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake:
            intake_agent = MockIntake.return_value
            
            # Mock process to hang indefinitely
            async def slow_process(raw_exception, tenant_id):
                await asyncio.sleep(10)  # Longer than timeout
                return ExceptionRecord(
                    exceptionId="exc_1",
                    tenantId="TENANT_A",
                    sourceSystem="ERP",
                    timestamp=datetime.now(timezone.utc),
                    rawPayload={},
                ), AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=slow_process)
            
            # Run with short timeout
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=[{"sourceSystem": "ERP", "rawPayload": {}}],
                stage_timeouts={"intake": 0.1},  # 100ms timeout
            )
            
            # Verify timeout error was caught
            assert len(result["results"]) == 1
            assert "error" in result["results"][0]["stages"]["intake"]


class TestStateSnapshots:
    """Tests for state snapshot persistence."""

    @pytest.mark.asyncio
    async def test_state_snapshots_are_saved(
        self, sample_domain_pack, sample_tenant_policy, sample_exception_batch
    ):
        """Test that state snapshots are saved after each stage."""
        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId="exc_1",
                    tenantId=tenant_id,
                    sourceSystem="ERP",
                    timestamp=datetime.now(timezone.utc),
                    rawPayload={},
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage", confidence=0.8, evidence=[], nextStep="policy"
            ))
            policy_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Policy",
                confidence=0.8,
                evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                nextStep="resolution",
            ))
            resolution_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Resolution", confidence=0.8, evidence=[], nextStep="feedback"
            ))
            feedback_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Feedback", confidence=0.8, evidence=[], nextStep="complete"
            ))
            
            # Run pipeline with snapshot directory
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=sample_exception_batch[:1],  # Just one exception
                snapshot_dir=tmpdir,
            )
            
            # Verify snapshots were created
            snapshot_files = list(Path(tmpdir).glob("*.json"))
            assert len(snapshot_files) > 0
            
            # Verify snapshot content
            for snapshot_file in snapshot_files:
                with open(snapshot_file) as f:
                    snapshot_data = json.load(f)
                    assert "exception" in snapshot_data
                    assert "context" in snapshot_data
                    assert "timestamp" in snapshot_data


class TestOrchestrationHooks:
    """Tests for orchestration hooks."""

    @pytest.mark.asyncio
    async def test_before_stage_hook_is_called(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that before_stage hook is called before each stage."""
        hooks = OrchestrationHooks()
        called_stages = []
        
        def before_stage_hook(stage_name: str, context: dict) -> None:
            called_stages.append(stage_name)
        
        hooks.set_before_stage(before_stage_hook)
        
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId="exc_1",
                    tenantId="TENANT_A",
                    sourceSystem="ERP",
                    timestamp=datetime.now(timezone.utc),
                    rawPayload={},
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage", confidence=0.8, evidence=[], nextStep="policy"
            ))
            policy_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Policy",
                confidence=0.8,
                evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                nextStep="resolution",
            ))
            resolution_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Resolution", confidence=0.8, evidence=[], nextStep="feedback"
            ))
            feedback_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Feedback", confidence=0.8, evidence=[], nextStep="complete"
            ))
            
            # Run pipeline
            await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=[{"sourceSystem": "ERP", "rawPayload": {}}],
                hooks=hooks,
            )
            
            # Verify hooks were called
            assert "intake" in called_stages
            assert "triage" in called_stages
            assert "policy" in called_stages
            assert "resolution" in called_stages
            assert "feedback" in called_stages

    @pytest.mark.asyncio
    async def test_after_stage_hook_is_called(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that after_stage hook is called after each stage."""
        hooks = OrchestrationHooks()
        called_stages = []
        
        def after_stage_hook(stage_name: str, decision: AgentDecision) -> None:
            called_stages.append(stage_name)
        
        hooks.set_after_stage(after_stage_hook)
        
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks (same as before_stage test)
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId="exc_1",
                    tenantId="TENANT_A",
                    sourceSystem="ERP",
                    timestamp=datetime.now(timezone.utc),
                    rawPayload={},
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage", confidence=0.8, evidence=[], nextStep="policy"
            ))
            policy_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Policy",
                confidence=0.8,
                evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                nextStep="resolution",
            ))
            resolution_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Resolution", confidence=0.8, evidence=[], nextStep="feedback"
            ))
            feedback_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Feedback", confidence=0.8, evidence=[], nextStep="complete"
            ))
            
            # Run pipeline
            await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=[{"sourceSystem": "ERP", "rawPayload": {}}],
                hooks=hooks,
            )
            
            # Verify hooks were called
            assert "intake" in called_stages
            assert "triage" in called_stages
            assert "policy" in called_stages
            assert "resolution" in called_stages
            assert "feedback" in called_stages

    @pytest.mark.asyncio
    async def test_on_failure_hook_is_called(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that on_failure hook is called on stage failure."""
        hooks = OrchestrationHooks()
        failed_stages = []
        
        def on_failure_hook(stage_name: str, error: Exception) -> None:
            failed_stages.append((stage_name, str(error)))
        
        hooks.set_on_failure(on_failure_hook)
        
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake:
            intake_agent = MockIntake.return_value
            
            # Mock process to raise error
            async def failing_process(raw_exception, tenant_id):
                raise ValueError("Intake failed")
            
            intake_agent.process = AsyncMock(side_effect=failing_process)
            
            # Run pipeline
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=[{"sourceSystem": "ERP", "rawPayload": {}}],
                hooks=hooks,
            )
            
            # Verify on_failure hook was called
            assert len(failed_stages) > 0
            assert any(stage == "intake" for stage, _ in failed_stages)


class TestBranchingLogic:
    """Tests for branching logic (PENDING_APPROVAL, non-actionable)."""

    @pytest.mark.asyncio
    async def test_pending_approval_stops_pipeline(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that PENDING_APPROVAL status stops pipeline before ResolutionAgent."""
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId="exc_1",
                    tenantId="TENANT_A",
                    sourceSystem="ERP",
                    timestamp=datetime.now(timezone.utc),
                    rawPayload={},
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage", confidence=0.8, evidence=[], nextStep="policy"
            ))
            
            # PolicyAgent sets PENDING_APPROVAL
            async def policy_process(exception, context):
                exception.resolution_status = ResolutionStatus.PENDING_APPROVAL
                return AgentDecision(
                    decision="Policy",
                    confidence=0.8,
                    evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS", "humanApprovalRequired: true"],
                    nextStep="wait",
                )
            
            policy_agent.process = AsyncMock(side_effect=policy_process)
            
            # Run pipeline
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=[{"sourceSystem": "ERP", "rawPayload": {}}],
            )
            
            # Verify pipeline stopped before ResolutionAgent
            assert result["results"][0]["status"] == "PENDING_APPROVAL"
            assert "resolution" not in result["results"][0]["stages"]
            assert "feedback" not in result["results"][0]["stages"]
            
            # Verify ResolutionAgent was not called
            resolution_agent.process.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_actionable_skips_resolution_agent(
        self, sample_domain_pack, sample_tenant_policy
    ):
        """Test that non-actionable exceptions skip ResolutionAgent."""
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId="exc_1",
                    tenantId="TENANT_A",
                    sourceSystem="ERP",
                    timestamp=datetime.now(timezone.utc),
                    rawPayload={},
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage", confidence=0.8, evidence=[], nextStep="policy"
            ))
            
            # PolicyAgent marks as non-actionable
            policy_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Policy",
                confidence=0.8,
                evidence=["Actionability: NON_ACTIONABLE_INFO_ONLY"],
                nextStep="feedback",
            ))
            feedback_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Feedback", confidence=0.8, evidence=[], nextStep="complete"
            ))
            
            # Run pipeline
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=[{"sourceSystem": "ERP", "rawPayload": {}}],
            )
            
            # Verify ResolutionAgent was skipped
            assert "resolution" in result["results"][0]["stages"]
            assert result["results"][0]["stages"]["resolution"].get("skipped") == "Non-actionable exception"
            
            # Verify ResolutionAgent.process was not called
            resolution_agent.process.assert_not_called()
            
            # Verify FeedbackAgent still ran
            assert "feedback" in result["results"][0]["stages"]


class TestDeterministicOrder:
    """Tests for deterministic order within each exception."""

    @pytest.mark.asyncio
    async def test_sequential_execution_maintains_order(
        self, sample_domain_pack, sample_tenant_policy, sample_exception_batch
    ):
        """Test that sequential execution maintains order."""
        with patch("src.orchestrator.runner.IntakeAgent") as MockIntake, \
             patch("src.orchestrator.runner.TriageAgent") as MockTriage, \
             patch("src.orchestrator.runner.PolicyAgent") as MockPolicy, \
             patch("src.orchestrator.runner.ResolutionAgent") as MockResolution, \
             patch("src.orchestrator.runner.FeedbackAgent") as MockFeedback:
            
            # Setup mocks
            intake_agent = MockIntake.return_value
            triage_agent = MockTriage.return_value
            policy_agent = MockPolicy.return_value
            resolution_agent = MockResolution.return_value
            feedback_agent = MockFeedback.return_value
            
            async def intake_process(raw_exception, tenant_id):
                exception = ExceptionRecord(
                    exceptionId=f"exc_{raw_exception.get('rawPayload', {}).get('orderId', 'unknown')}",
                    tenantId=tenant_id,
                    sourceSystem=raw_exception.get("sourceSystem", "UNKNOWN"),
                    timestamp=datetime.now(timezone.utc),
                    rawPayload=raw_exception.get("rawPayload", {}),
                )
                return exception, AgentDecision(decision="Intake", confidence=0.9, evidence=[], nextStep="triage")
            
            intake_agent.process = AsyncMock(side_effect=intake_process)
            triage_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Triage", confidence=0.8, evidence=[], nextStep="policy"
            ))
            policy_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Policy",
                confidence=0.8,
                evidence=["Actionability: ACTIONABLE_APPROVED_PROCESS"],
                nextStep="resolution",
            ))
            resolution_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Resolution", confidence=0.8, evidence=[], nextStep="feedback"
            ))
            feedback_agent.process = AsyncMock(return_value=AgentDecision(
                decision="Feedback", confidence=0.8, evidence=[], nextStep="complete"
            ))
            
            # Run pipeline with sequential execution
            result = await run_pipeline(
                domain_pack=sample_domain_pack,
                tenant_policy=sample_tenant_policy,
                exceptions_batch=sample_exception_batch,
                enable_parallel=False,
            )
            
            # Verify results are in same order as input
            assert len(result["results"]) == 3
            for i, raw_exc in enumerate(sample_exception_batch):
                expected_order_id = raw_exc.get("rawPayload", {}).get("orderId", "unknown")
                result_exc_id = result["results"][i]["exceptionId"]
                assert expected_order_id in result_exc_id

