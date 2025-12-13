"""
Unit tests for Human-in-the-loop Approval Workflow.

Tests enforcement of human approval for risky playbook steps.
Reference: docs/phase7-playbooks-mvp.md Section 4.2
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.infrastructure.db.models import ActorType, Exception, ExceptionStatus, ExceptionSeverity
from src.infrastructure.db.models import Playbook, PlaybookStep
from src.playbooks.execution_service import PlaybookExecutionError, PlaybookExecutionService
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository


@pytest.fixture
def mock_exception_repository():
    """Create a mock ExceptionRepository."""
    return AsyncMock(spec=ExceptionRepository)


@pytest.fixture
def mock_event_repository():
    """Create a mock ExceptionEventRepository."""
    return AsyncMock(spec=ExceptionEventRepository)


@pytest.fixture
def mock_playbook_repository():
    """Create a mock PlaybookRepository."""
    return AsyncMock(spec=PlaybookRepository)


@pytest.fixture
def mock_step_repository():
    """Create a mock PlaybookStepRepository."""
    return AsyncMock(spec=PlaybookStepRepository)


@pytest.fixture
def execution_service(
    mock_exception_repository,
    mock_event_repository,
    mock_playbook_repository,
    mock_step_repository,
):
    """Create a PlaybookExecutionService instance."""
    return PlaybookExecutionService(
        exception_repository=mock_exception_repository,
        event_repository=mock_event_repository,
        playbook_repository=mock_playbook_repository,
        step_repository=mock_step_repository,
    )


@pytest.fixture
def sample_exception():
    """Create a sample Exception for testing."""
    exception = MagicMock(spec=Exception)
    exception.exception_id = "exc_001"
    exception.tenant_id = "tenant_001"
    exception.current_playbook_id = 1
    exception.current_step = 1
    return exception


@pytest.fixture
def sample_playbook():
    """Create a sample Playbook for testing."""
    playbook = MagicMock(spec=Playbook)
    playbook.playbook_id = 1
    playbook.tenant_id = "tenant_001"
    playbook.name = "Test Playbook"
    playbook.version = 1
    return playbook


@pytest.fixture
def safe_step():
    """Create a safe step (notify action)."""
    step = MagicMock(spec=PlaybookStep)
    step.step_id = 1
    step.playbook_id = 1
    step.step_order = 1
    step.name = "Notify Team"
    step.action_type = "notify"
    return step


@pytest.fixture
def risky_step():
    """Create a risky step (call_tool action)."""
    step = MagicMock(spec=PlaybookStep)
    step.step_id = 2
    step.playbook_id = 1
    step.step_order = 1  # Changed to 1 to match current_step
    step.name = "Call External Tool"
    step.action_type = "call_tool"
    return step


@pytest.fixture
def unknown_risky_step():
    """Create a step with unknown action type (considered risky)."""
    step = MagicMock(spec=PlaybookStep)
    step.step_id = 3
    step.playbook_id = 1
    step.step_order = 1  # Changed to 1 to match current_step
    step.name = "Unknown Action"
    step.action_type = "unknown_action"
    return step


class TestHumanApprovalFlow:
    """Test suite for human approval workflow."""
    
    @pytest.mark.asyncio
    async def test_human_completes_valid_safe_step(
        self, execution_service, sample_exception, sample_playbook, safe_step
    ):
        """Test that human can complete a valid safe step."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [safe_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
            notes="Step completed by human operator",
        )
        
        # Verify exception was updated
        execution_service.exception_repository.update_exception.assert_called_once()
        
        # Verify event was emitted (may be 2 if it's the last step)
        assert execution_service.event_repository.append_event.call_count >= 1
        event_calls = execution_service.event_repository.append_event.call_args_list
        step_event = event_calls[0][0][1]
        assert step_event.event_type == "PlaybookStepCompleted"
        assert step_event.actor_type == ActorType.USER or step_event.actor_type == "user"
        assert step_event.actor_id == "user_123"
        assert step_event.payload["notes"] == "Step completed by human operator"
        assert step_event.payload["is_risky"] is False
    
    @pytest.mark.asyncio
    async def test_human_completes_valid_risky_step(
        self, execution_service, sample_exception, sample_playbook, risky_step
    ):
        """Test that human can complete a valid risky step."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [risky_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
            notes="Risky step approved and completed",
        )
        
        # Verify exception was updated
        execution_service.exception_repository.update_exception.assert_called_once()
        
        # Verify event was emitted with risky flag (may be 2 if it's the last step)
        assert execution_service.event_repository.append_event.call_count >= 1
        event_calls = execution_service.event_repository.append_event.call_args_list
        step_event = event_calls[0][0][1]
        assert step_event.event_type == "PlaybookStepCompleted"
        assert step_event.payload["is_risky"] is True
        assert step_event.payload["action_type"] == "call_tool"
    
    @pytest.mark.asyncio
    async def test_agent_tries_to_execute_risky_step_rejected(
        self, execution_service, sample_exception, risky_step
    ):
        """Test that agent cannot execute risky step (rejected)."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [risky_step]
        
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,
                actor_id="PolicyAgent",
            )
        
        # Verify exception was NOT updated
        execution_service.exception_repository.update_exception.assert_not_called()
        
        # Verify event was NOT emitted
        execution_service.event_repository.append_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_system_tries_to_execute_risky_step_rejected(
        self, execution_service, sample_exception, risky_step
    ):
        """Test that system cannot execute risky step (rejected)."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [risky_step]
        
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.SYSTEM,
                actor_id="AutoExecutor",
            )
        
        # Verify exception was NOT updated
        execution_service.exception_repository.update_exception.assert_not_called()
        
        # Verify event was NOT emitted
        execution_service.event_repository.append_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_agent_can_execute_safe_step(
        self, execution_service, sample_exception, safe_step
    ):
        """Test that agent can execute safe steps."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [safe_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.AGENT,
            actor_id="PolicyAgent",
        )
        
        # Verify exception was updated
        execution_service.exception_repository.update_exception.assert_called_once()
        
        # Verify event was emitted (may be 2 if it's the last step)
        assert execution_service.event_repository.append_event.call_count >= 1
    
    @pytest.mark.asyncio
    async def test_human_tries_to_skip_ahead_rejected(
        self, execution_service, sample_exception, safe_step, risky_step
    ):
        """Test that human cannot skip ahead to a later step."""
        sample_exception.current_step = 1  # Currently on step 1
        
        # Create step 2 with step_order=2
        step2 = MagicMock(spec=PlaybookStep)
        step2.step_id = 2
        step2.playbook_id = 1
        step2.step_order = 2
        step2.name = "Step 2"
        step2.action_type = "call_tool"
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [safe_step, step2]
        
        # Try to complete step 2 when current step is 1
        with pytest.raises(PlaybookExecutionError, match="is not the next expected step"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=2,  # Trying to skip ahead
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        # Verify exception was NOT updated
        execution_service.exception_repository.update_exception.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_last_step_triggers_playbook_completed(
        self, execution_service, sample_exception, safe_step
    ):
        """Test that completing last step triggers PlaybookCompleted event."""
        sample_exception.current_step = 1  # Last step
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [safe_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
            notes="Final step completed",
        )
        
        # Verify both events were emitted
        assert execution_service.event_repository.append_event.call_count == 2
        event_calls = execution_service.event_repository.append_event.call_args_list
        
        # Check PlaybookStepCompleted
        assert event_calls[0][0][1].event_type == "PlaybookStepCompleted"
        
        # Check PlaybookCompleted
        assert event_calls[1][0][1].event_type == "PlaybookCompleted"
        assert event_calls[1][0][1].payload["notes"] == "Final step completed"
        assert event_calls[1][0][1].actor_type == ActorType.USER or event_calls[1][0][1].actor_type == "user"
        assert event_calls[1][0][1].actor_id == "user_123"
    
    @pytest.mark.asyncio
    async def test_unknown_action_type_considered_risky(
        self, execution_service, sample_exception, unknown_risky_step
    ):
        """Test that unknown action types are considered risky."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [unknown_risky_step]
        
        # Agent should be rejected
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,
                actor_id="PolicyAgent",
            )
        
        # Human should be allowed
        execution_service.event_repository.get_events_for_exception.return_value = []
        # Reset mocks to clear previous calls
        execution_service.event_repository.reset_mock()
        execution_service.exception_repository.reset_mock()
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
        )
        
        # Verify event was emitted with risky flag
        assert execution_service.event_repository.append_event.call_count >= 1
        event_calls = execution_service.event_repository.append_event.call_args_list
        step_event = event_calls[0][0][1]
        assert step_event.payload["is_risky"] is True
    
    @pytest.mark.asyncio
    async def test_actor_metadata_stored_in_events(
        self, execution_service, sample_exception, safe_step
    ):
        """Test that actor metadata (actor_type, actor_id, notes) is stored in events."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [safe_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_456",
            notes="Custom notes from operator",
        )
        
        # Verify event contains all actor metadata
        event_calls = execution_service.event_repository.append_event.call_args_list
        step_event = event_calls[0][0][1]  # First event is PlaybookStepCompleted
        
        assert step_event.actor_type == ActorType.USER or step_event.actor_type == "user"
        assert step_event.actor_id == "user_456"
        assert step_event.payload["actor_type"] == "user"
        assert step_event.payload["actor_id"] == "user_456"
        assert step_event.payload["notes"] == "Custom notes from operator"
    
    @pytest.mark.asyncio
    async def test_safe_action_types_allowed_for_agents(
        self, execution_service, sample_exception
    ):
        """Test that all safe action types can be executed by agents."""
        safe_actions = ["notify", "add_comment", "set_status", "assign_owner"]
        
        for action_type in safe_actions:
            step = MagicMock(spec=PlaybookStep)
            step.step_id = 1
            step.playbook_id = 1
            step.step_order = 1
            step.name = f"Step {action_type}"
            step.action_type = action_type
            
            execution_service.exception_repository.get_exception.return_value = sample_exception
            execution_service.step_repository.get_steps.return_value = [step]
            execution_service.event_repository.get_events_for_exception.return_value = []
            
            # Reset mocks
            execution_service.exception_repository.reset_mock()
            execution_service.event_repository.reset_mock()
            
            # Agent should be able to execute
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,
                actor_id="PolicyAgent",
            )
            
            # Verify it was executed (may be 2 calls if it's the last step)
            execution_service.exception_repository.update_exception.assert_called_once()
            assert execution_service.event_repository.append_event.call_count >= 1
            
            # Reset for next iteration
            execution_service.exception_repository.reset_mock()
            execution_service.event_repository.reset_mock()

