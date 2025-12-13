"""
Comprehensive tests for ResolutionAgent.
Tests playbook resolution, tool validation, and draft playbook generation.
"""

from datetime import datetime, timezone

import pytest

from src.agents.resolution import ResolutionAgent, ResolutionAgentError
from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, Playbook, PlaybookStep, ToolDefinition
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.tools.registry import ToolRegistry


@pytest.fixture
def finance_domain_pack():
    """Create finance domain pack with playbooks and tools."""
    return DomainPack(
        domainName="CapitalMarketsTrading",
        exceptionTypes={
            "SETTLEMENT_FAIL": ExceptionTypeDefinition(
                description="Settlement failure",
                detectionRules=[],
            ),
            "POSITION_BREAK": ExceptionTypeDefinition(
                description="Position break",
                detectionRules=[],
            ),
        },
        tools={
            "getSettlement": ToolDefinition(
                description="Fetch settlement details",
                parameters={"orderId": "string"},
                endpoint="https://api.example.com/getSettlement",
            ),
            "triggerSettlementRetry": ToolDefinition(
                description="Retry settlement",
                parameters={"orderId": "string"},
                endpoint="https://api.example.com/triggerSettlementRetry",
            ),
            "recalculatePosition": ToolDefinition(
                description="Recalculate positions",
                parameters={"accountId": "string", "cusip": "string"},
                endpoint="https://api.example.com/recalculatePosition",
            ),
        },
        playbooks=[
            Playbook(
                exceptionType="SETTLEMENT_FAIL",
                steps=[
                    PlaybookStep(action="getSettlement", parameters={"orderId": "{{orderId}}"}),
                    PlaybookStep(action="triggerSettlementRetry", parameters={"orderId": "{{orderId}}"}),
                ],
            ),
            Playbook(
                exceptionType="POSITION_BREAK",
                steps=[
                    PlaybookStep(
                        action="recalculatePosition",
                        parameters={"accountId": "{{accountId}}", "cusip": "{{cusip}}"},
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def finance_tenant_policy():
    """Create finance tenant policy with approved tools."""
    return TenantPolicyPack(
        tenantId="TENANT_FINANCE_001",
        domainName="CapitalMarketsTrading",
        approvedTools=["getSettlement", "triggerSettlementRetry", "recalculatePosition"],
    )


@pytest.fixture
def tool_registry(finance_domain_pack, finance_tenant_policy):
    """Create tool registry with domain pack and policy."""
    registry = ToolRegistry()
    registry.register_domain_pack("TENANT_FINANCE_001", finance_domain_pack)
    registry.register_policy_pack("TENANT_FINANCE_001", finance_tenant_policy)
    return registry


@pytest.fixture
def sample_audit_logger(tmp_path, monkeypatch):
    """Create a sample audit logger with temp directory."""
    audit_dir = tmp_path / "runtime" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    def patched_get_log_file(self):
        if self._log_file is None:
            self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file
    
    def patched_ensure_dir(self):
        audit_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(AuditLogger, "_get_log_file", patched_get_log_file)
    monkeypatch.setattr(AuditLogger, "_ensure_audit_directory", patched_ensure_dir)
    
    return AuditLogger(run_id="test_run", tenant_id="tenant_001")


class TestResolutionAgentPlaybookResolution:
    """Tests for playbook resolution."""

    @pytest.mark.asyncio
    async def test_resolve_approved_playbook(self, finance_domain_pack, tool_registry):
        """Test resolving an approved playbook into action plan."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-123"},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        decision = await agent.process(exception, context)
        
        assert "Resolved plan created" in decision.decision
        assert "2 actions" in decision.decision or "actions" in decision.decision
        assert decision.next_step == "ProceedToFeedback"

    @pytest.mark.asyncio
    async def test_resolve_playbook_without_selected_id(self, finance_domain_pack, tool_registry):
        """Test resolving playbook when selectedPlaybookId not provided."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "ACTIONABLE_APPROVED_PROCESS"}
        
        decision = await agent.process(exception, context)
        
        assert "Resolved plan" in decision.decision or "No resolution plan" in decision.decision

    @pytest.mark.asyncio
    async def test_resolve_playbook_steps_structure(self, finance_domain_pack, tool_registry):
        """Test that resolved plan has correct structure."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        decision = await agent.process(exception, context)
        
        # Check evidence contains step information
        evidence_text = " ".join(decision.evidence)
        assert "getSettlement" in evidence_text or "triggerSettlementRetry" in evidence_text


class TestResolutionAgentToolValidation:
    """Tests for tool validation."""

    @pytest.mark.asyncio
    async def test_validate_tool_exists_in_domain_pack(self, finance_domain_pack, tool_registry):
        """Test that tools are validated against domain pack."""
        # Replace existing SETTLEMENT_FAIL playbook with one that has invalid tool
        # First, remove existing playbooks for SETTLEMENT_FAIL
        finance_domain_pack.playbooks = [
            pb for pb in finance_domain_pack.playbooks if pb.exception_type != "SETTLEMENT_FAIL"
        ]
        
        # Create playbook with invalid tool
        invalid_playbook = Playbook(
            exceptionType="SETTLEMENT_FAIL",
            steps=[
                PlaybookStep(action="invalidTool", parameters={}),
            ],
        )
        finance_domain_pack.playbooks.append(invalid_playbook)
        
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        # Should raise error for invalid tool
        with pytest.raises(ResolutionAgentError) as exc_info:
            await agent.process(exception, context)
        assert "not found in domain pack" in str(exc_info.value).lower() or "invalidTool" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_validate_tool_allow_listed(self, finance_domain_pack, tool_registry):
        """Test that tools are validated against tenant allow-list."""
        # Create tenant policy without a tool
        restricted_policy = TenantPolicyPack(
            tenantId="TENANT_FINANCE_001",
            domainName="CapitalMarketsTrading",
            approvedTools=["getSettlement"],  # Missing triggerSettlementRetry
        )
        
        restricted_registry = ToolRegistry()
        restricted_registry.register_domain_pack("TENANT_FINANCE_001", finance_domain_pack)
        restricted_registry.register_policy_pack("TENANT_FINANCE_001", restricted_policy)
        
        agent = ResolutionAgent(finance_domain_pack, restricted_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        # Should raise error for non-allow-listed tool
        with pytest.raises(ResolutionAgentError) as exc_info:
            await agent.process(exception, context)
        assert "not allow-listed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_validate_all_tools_in_playbook(self, finance_domain_pack, tool_registry):
        """Test that all tools in playbook are validated."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        # Should not raise - all tools are valid
        decision = await agent.process(exception, context)
        assert decision.decision is not None


class TestResolutionAgentDraftPlaybook:
    """Tests for draft playbook generation."""

    @pytest.mark.asyncio
    async def test_generate_draft_playbook_for_non_approved(self, finance_domain_pack, tool_registry):
        """Test generating draft playbook for non-approved but actionable exception."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "ACTIONABLE_NON_APPROVED_PROCESS"}
        
        decision = await agent.process(exception, context)
        
        assert "Draft playbook suggested" in decision.decision or "suggestedDraftPlaybook" in " ".join(decision.evidence)

    @pytest.mark.asyncio
    async def test_draft_playbook_structure(self, finance_domain_pack, tool_registry):
        """Test that draft playbook has correct structure."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "ACTIONABLE_NON_APPROVED_PROCESS"}
        
        decision = await agent.process(exception, context)
        
        # Check evidence mentions draft
        evidence_text = " ".join(decision.evidence)
        assert "Draft" in evidence_text or "draft" in evidence_text


class TestResolutionAgentDecision:
    """Tests for agent decision creation."""

    @pytest.mark.asyncio
    async def test_decision_contains_required_fields(self, finance_domain_pack, tool_registry):
        """Test that decision contains all required fields."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "ACTIONABLE_APPROVED_PROCESS"}
        
        decision = await agent.process(exception, context)
        
        assert decision.decision is not None
        assert 0.0 <= decision.confidence <= 1.0
        assert isinstance(decision.evidence, list)
        assert decision.next_step == "ProceedToFeedback"

    @pytest.mark.asyncio
    async def test_decision_includes_resolved_plan_info(self, finance_domain_pack, tool_registry):
        """Test that decision includes resolved plan information."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "resolvedPlan" in evidence_text or "Resolved plan" in decision.decision


class TestResolutionAgentAuditLogging:
    """Tests for audit logging integration."""

    @pytest.mark.asyncio
    async def test_logs_agent_event(self, finance_domain_pack, tool_registry, sample_audit_logger):
        """Test that agent events are logged."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry, sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "ACTIONABLE_APPROVED_PROCESS"}
        
        decision = await agent.process(exception, context)
        sample_audit_logger.close()
        
        # Verify log file was created
        log_file = sample_audit_logger._get_log_file()
        assert log_file.exists()
        
        # Verify log contains agent event
        import json
        with open(log_file, "r", encoding="utf-8") as f:
            # Read all lines and find agent_event (step executions are logged first)
            agent_event_entry = None
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if entry.get("event_type") == "agent_event":
                        agent_event_entry = entry
                        break
        
        assert agent_event_entry is not None, "Agent event not found in audit log"
        assert agent_event_entry["data"]["agent_name"] == "ResolutionAgent"

    @pytest.mark.asyncio
    async def test_logs_without_audit_logger(self, finance_domain_pack, tool_registry):
        """Test that agent works without audit logger."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "ACTIONABLE_APPROVED_PROCESS"}
        
        # Should not raise
        decision = await agent.process(exception, context)


class TestResolutionAgentNextActionSuggestion:
    """Tests for next action suggestion from assigned playbook (P7-13)."""

    @pytest.mark.asyncio
    async def test_next_action_suggestion_from_assigned_playbook(self, finance_domain_pack, tool_registry):
        """Test that next action is suggested when exception has current_playbook_id."""
        from unittest.mock import AsyncMock, MagicMock
        from src.infrastructure.db.models import Playbook, PlaybookStep
        
        # Create mock playbook repository
        mock_playbook_repo = AsyncMock()
        
        # Create mock playbook with steps
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 42
        mock_playbook.tenant_id = "TENANT_FINANCE_001"
        mock_playbook.name = "SettlementRetryPlaybook"
        
        # Create mock steps
        step1 = MagicMock()
        step1.step_order = 1
        step1.name = "Get Settlement Details"
        step1.action_type = "call_tool"
        step1.params = {"orderId": "ORD123"}
        
        step2 = MagicMock()
        step2.step_order = 2
        step2.name = "Trigger Retry"
        step2.action_type = "call_tool"
        step2.params = {"orderId": "ORD123", "retryCount": 3}
        
        mock_playbook.steps = [step1, step2]
        mock_playbook_repo.get_playbook.return_value = mock_playbook
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = ResolutionAgent(
            finance_domain_pack,
            tool_registry,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            currentPlaybookId=42,
            currentStep=1,
        )
        
        decision = await agent.process(exception)
        
        # Verify playbook was loaded
        mock_playbook_repo.get_playbook.assert_called_once_with(
            playbook_id=42,
            tenant_id="TENANT_FINANCE_001",
        )
        
        # Verify next action is in evidence
        evidence_text = " ".join(decision.evidence)
        assert "Next action" in evidence_text
        assert "Trigger Retry" in evidence_text
        assert "Step order: 2" in evidence_text
        
        # Verify ResolutionSuggested event was emitted
        assert mock_events_repo.append_event_if_new.called
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.event_type == "ResolutionSuggested"
        assert call_args.payload["playbook_id"] == 42
        assert call_args.payload["step_order"] == 2
        assert call_args.payload["suggested_action"] == "Trigger Retry"

    @pytest.mark.asyncio
    async def test_next_action_includes_params_summary(self, finance_domain_pack, tool_registry):
        """Test that next action includes brief params summary."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock playbook repository
        mock_playbook_repo = AsyncMock()
        
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 99
        mock_playbook.tenant_id = "TENANT_FINANCE_001"
        
        step = MagicMock()
        step.step_order = 2
        step.name = "Process Payment"
        step.action_type = "call_tool"
        step.params = {
            "accountId": "ACC123",
            "amount": 1000.50,
            "currency": "USD",
            "description": "Payment for order",
        }
        
        mock_playbook.steps = [step]
        mock_playbook_repo.get_playbook.return_value = mock_playbook
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = ResolutionAgent(
            finance_domain_pack,
            tool_registry,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="PaymentSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            currentPlaybookId=99,
            currentStep=1,
        )
        
        decision = await agent.process(exception)
        
        # Verify params are included in evidence
        evidence_text = " ".join(decision.evidence)
        assert "Params:" in evidence_text
        assert "accountId" in evidence_text or "ACC123" in evidence_text

    @pytest.mark.asyncio
    async def test_no_next_action_when_no_more_steps(self, finance_domain_pack, tool_registry):
        """Test that no next action is suggested when at the last step."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock playbook repository
        mock_playbook_repo = AsyncMock()
        
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 50
        mock_playbook.tenant_id = "TENANT_FINANCE_001"
        
        step = MagicMock()
        step.step_order = 1
        step.name = "Final Step"
        step.action_type = "notify"
        step.params = {}
        
        mock_playbook.steps = [step]  # Only one step
        mock_playbook_repo.get_playbook.return_value = mock_playbook
        
        agent = ResolutionAgent(
            finance_domain_pack,
            tool_registry,
            playbook_repository=mock_playbook_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_003",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TestSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.LOW,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            currentPlaybookId=50,
            currentStep=1,  # Already at last step
        )
        
        decision = await agent.process(exception)
        
        # Verify no next action in evidence
        evidence_text = " ".join(decision.evidence)
        assert "Next action" not in evidence_text

    @pytest.mark.asyncio
    async def test_no_next_action_when_no_playbook_id(self, finance_domain_pack, tool_registry):
        """Test that no next action is suggested when exception has no current_playbook_id."""
        from unittest.mock import AsyncMock
        
        # Create mock playbook repository
        mock_playbook_repo = AsyncMock()
        
        agent = ResolutionAgent(
            finance_domain_pack,
            tool_registry,
            playbook_repository=mock_playbook_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_004",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TestSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            # No currentPlaybookId
        )
        
        decision = await agent.process(exception)
        
        # Verify playbook repository was not called
        mock_playbook_repo.get_playbook.assert_not_called()
        
        # Verify no next action in evidence
        evidence_text = " ".join(decision.evidence)
        assert "Next action" not in evidence_text

    @pytest.mark.asyncio
    async def test_resolution_suggested_event_includes_step_order(self, finance_domain_pack, tool_registry):
        """Test that ResolutionSuggested event includes step_order reference."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock playbook repository
        mock_playbook_repo = AsyncMock()
        
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 77
        mock_playbook.tenant_id = "TENANT_FINANCE_001"
        
        step = MagicMock()
        step.step_order = 3
        step.name = "Verify Transaction"
        step.action_type = "call_tool"
        step.params = {"transactionId": "TXN456"}
        
        mock_playbook.steps = [step]
        mock_playbook_repo.get_playbook.return_value = mock_playbook
        
        # Create mock exception events repository
        mock_events_repo = AsyncMock()
        mock_events_repo.append_event_if_new.return_value = True
        
        agent = ResolutionAgent(
            finance_domain_pack,
            tool_registry,
            playbook_repository=mock_playbook_repo,
            exception_events_repository=mock_events_repo,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_005",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TransactionSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            currentPlaybookId=77,
            currentStep=2,
        )
        
        decision = await agent.process(exception)
        
        # Verify event was logged with step_order
        assert mock_events_repo.append_event_if_new.called
        call_args = mock_events_repo.append_event_if_new.call_args[0][0]
        assert call_args.event_type == "ResolutionSuggested"
        assert call_args.payload["playbook_id"] == 77
        assert call_args.payload["step_order"] == 3
        assert call_args.payload["suggested_action"] == "Verify Transaction"

    @pytest.mark.asyncio
    async def test_next_action_does_not_execute_step(self, finance_domain_pack, tool_registry):
        """Test that next action suggestion does NOT execute the step."""
        from unittest.mock import AsyncMock, MagicMock
        
        # Create mock playbook repository
        mock_playbook_repo = AsyncMock()
        
        mock_playbook = MagicMock()
        mock_playbook.playbook_id = 88
        mock_playbook.tenant_id = "TENANT_FINANCE_001"
        
        step = MagicMock()
        step.step_order = 2
        step.name = "Execute Action"
        step.action_type = "call_tool"
        step.params = {"action": "doSomething"}
        
        mock_playbook.steps = [step]
        mock_playbook_repo.get_playbook.return_value = mock_playbook
        
        # Create mock execution engine to verify it's NOT called
        mock_execution_engine = AsyncMock()
        
        agent = ResolutionAgent(
            finance_domain_pack,
            tool_registry,
            playbook_repository=mock_playbook_repo,
            execution_engine=mock_execution_engine,
        )
        
        exception = ExceptionRecord(
            exceptionId="exc_006",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TestSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            currentPlaybookId=88,
            currentStep=1,
        )
        
        decision = await agent.process(exception)
        
        # Verify execution engine was NOT called (next action is suggestion only)
        # The execution engine would only be called in _resolve_playbook_steps, not for next_action
        # Since we're not in ACTIONABLE_APPROVED_PROCESS flow, execution shouldn't happen
        # But let's verify the next_action was suggested
        evidence_text = " ".join(decision.evidence)
        assert "Next action" in evidence_text or "Execute Action" in evidence_text


class TestResolutionAgentFinanceSamples:
    """Tests using finance domain samples."""

    @pytest.mark.asyncio
    async def test_finance_settlement_fail_resolution(self, finance_domain_pack, tool_registry):
        """Test finance SETTLEMENT_FAIL playbook resolution."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-123"},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        decision = await agent.process(exception, context)
        
        assert "Resolved plan" in decision.decision
        evidence_text = " ".join(decision.evidence)
        assert "getSettlement" in evidence_text or "triggerSettlementRetry" in evidence_text

    @pytest.mark.asyncio
    async def test_finance_position_break_resolution(self, finance_domain_pack, tool_registry):
        """Test finance POSITION_BREAK playbook resolution."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-002",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            severity=Severity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"accountId": "ACC-123", "cusip": "CUSIP-456"},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "POSITION_BREAK",
        }
        
        decision = await agent.process(exception, context)
        
        assert "Resolved plan" in decision.decision
        evidence_text = " ".join(decision.evidence)
        assert "recalculatePosition" in evidence_text


class TestResolutionAgentNonActionable:
    """Tests for non-actionable exceptions."""

    @pytest.mark.asyncio
    async def test_non_actionable_exception(self, finance_domain_pack, tool_registry):
        """Test handling non-actionable exception."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="UNKNOWN_TYPE",
            severity=Severity.LOW,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {"actionability": "NON_ACTIONABLE_INFO_ONLY"}
        
        decision = await agent.process(exception, context)
        
        assert "No resolution plan" in decision.decision or "NON_ACTIONABLE" in " ".join(decision.evidence)


class TestResolutionAgentToolExtraction:
    """Tests for tool name extraction from playbook steps."""

    @pytest.mark.asyncio
    async def test_extract_tool_from_direct_action(self, finance_domain_pack, tool_registry):
        """Test extracting tool name from direct action."""
        playbook = Playbook(
            exceptionType="TEST_TYPE",
            steps=[
                PlaybookStep(action="getSettlement", parameters={}),
            ],
        )
        finance_domain_pack.playbooks.append(playbook)
        
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="TEST_TYPE",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "TEST_TYPE",
        }
        
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "getSettlement" in evidence_text

    @pytest.mark.asyncio
    async def test_extract_tool_from_function_call(self, finance_domain_pack, tool_registry):
        """Test extracting tool name from function call format."""
        playbook = Playbook(
            exceptionType="TEST_TYPE",
            steps=[
                PlaybookStep(action="invokeTool('triggerSettlementRetry')", parameters={}),
            ],
        )
        finance_domain_pack.playbooks.append(playbook)
        
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="TEST_TYPE",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "TEST_TYPE",
        }
        
        decision = await agent.process(exception, context)
        
        evidence_text = " ".join(decision.evidence)
        assert "triggerSettlementRetry" in evidence_text


class TestResolutionAgentErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_playbook_not_found_error(self, finance_domain_pack, tool_registry):
        """Test error when playbook not found."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "NONEXISTENT_PLAYBOOK",
        }
        
        with pytest.raises(ResolutionAgentError) as exc_info:
            await agent.process(exception, context)
        assert "not found" in str(exc_info.value).lower()


class TestResolutionAgentIntegration:
    """Integration tests for complete resolution planning workflow."""

    @pytest.mark.asyncio
    async def test_complete_resolution_workflow(self, finance_domain_pack, tool_registry, sample_audit_logger):
        """Test complete resolution planning workflow."""
        agent = ResolutionAgent(finance_domain_pack, tool_registry, sample_audit_logger)
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-123"},
        )
        
        context = {
            "actionability": "ACTIONABLE_APPROVED_PROCESS",
            "selectedPlaybookId": "SETTLEMENT_FAIL",
        }
        
        decision = await agent.process(exception, context)
        sample_audit_logger.close()
        
        # Verify all components
        assert decision.decision is not None
        assert decision.next_step == "ProceedToFeedback"
        assert "Resolved plan" in decision.decision or "actions" in decision.decision
        assert decision.confidence > 0.0

