"""
Unit tests for Playbook Execution Service.

Tests playbook execution lifecycle, step validation, state updates, and event emission.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from src.infrastructure.db.models import ActorType, Exception, ExceptionStatus, ExceptionSeverity
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
from src.infrastructure.db.models import Playbook, PlaybookStep
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.playbooks.execution_service import PlaybookExecutionService, PlaybookExecutionError


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
    exception.current_playbook_id = None
    exception.current_step = None
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
def sample_steps():
    """Create sample PlaybookStep instances for testing."""
    step1 = MagicMock(spec=PlaybookStep)
    step1.step_id = 1
    step1.playbook_id = 1
    step1.step_order = 1
    step1.name = "Step 1"
    step1.action_type = "notify"
    
    step2 = MagicMock(spec=PlaybookStep)
    step2.step_id = 2
    step2.playbook_id = 1
    step2.step_order = 2
    step2.name = "Step 2"
    step2.action_type = "assign_owner"
    
    return [step1, step2]


class TestPlaybookExecutionService:
    """Test suite for PlaybookExecutionService."""
    
    @pytest.mark.asyncio
    async def test_start_playbook_for_exception_success(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test successfully starting a playbook."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = sample_playbook
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.start_playbook_for_exception(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            actor_type=ActorType.AGENT,
            actor_id="PolicyAgent",
        )
        
        # Verify exception was updated
        execution_service.exception_repository.update_exception.assert_called_once()
        call_args = execution_service.exception_repository.update_exception.call_args
        assert call_args[1]["updates"].current_playbook_id == 1
        assert call_args[1]["updates"].current_step == 1
        
        # Verify event was emitted
        execution_service.event_repository.append_event.assert_called_once()
        event_call = execution_service.event_repository.append_event.call_args
        assert event_call[0][1].event_type == "PlaybookStarted"
        assert event_call[0][1].payload["playbook_id"] == 1
    
    @pytest.mark.asyncio
    async def test_start_playbook_for_exception_idempotent(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test that starting an already-started playbook is idempotent."""
        sample_exception.current_playbook_id = 1
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = sample_playbook
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        # Mock existing PlaybookStarted event
        existing_event = MagicMock()
        existing_event.event_type = "PlaybookStarted"
        existing_event.payload = {"playbook_id": 1}
        execution_service.event_repository.get_events_for_exception.return_value = [existing_event]
        
        await execution_service.start_playbook_for_exception(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            actor_type=ActorType.AGENT,
        )
        
        # Should not update exception or emit event
        execution_service.exception_repository.update_exception.assert_not_called()
        execution_service.event_repository.append_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_start_playbook_for_exception_not_found(
        self, execution_service
    ):
        """Test that starting playbook fails if exception not found."""
        execution_service.exception_repository.get_exception.return_value = None
        
        with pytest.raises(PlaybookExecutionError, match="not found"):
            await execution_service.start_playbook_for_exception(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                actor_type=ActorType.AGENT,
            )
    
    @pytest.mark.asyncio
    async def test_start_playbook_for_exception_playbook_not_found(
        self, execution_service, sample_exception
    ):
        """Test that starting playbook fails if playbook not found."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = None
        
        with pytest.raises(PlaybookExecutionError, match="Playbook.*not found"):
            await execution_service.start_playbook_for_exception(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=999,
                actor_type=ActorType.AGENT,
            )
    
    @pytest.mark.asyncio
    async def test_start_playbook_for_exception_no_steps(
        self, execution_service, sample_exception, sample_playbook
    ):
        """Test that starting playbook fails if playbook has no steps."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = sample_playbook
        execution_service.step_repository.get_steps.return_value = []
        
        with pytest.raises(PlaybookExecutionError, match="has no steps"):
            await execution_service.start_playbook_for_exception(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                actor_type=ActorType.AGENT,
            )
    
    @pytest.mark.asyncio
    async def test_complete_step_success(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test successfully completing a step."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
            notes="Step completed manually",
        )
        
        # Verify exception was updated to next step
        execution_service.exception_repository.update_exception.assert_called_once()
        call_args = execution_service.exception_repository.update_exception.call_args
        assert call_args[1]["updates"].current_step == 2
        
        # Verify event was emitted
        execution_service.event_repository.append_event.assert_called_once()
        event_call = execution_service.event_repository.append_event.call_args
        assert event_call[0][1].event_type == "PlaybookStepCompleted"
        assert event_call[0][1].payload["step_order"] == 1
    
    @pytest.mark.asyncio
    async def test_complete_step_last_step(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test completing the last step emits PlaybookCompleted event."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 2  # Last step
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=2,
            actor_type=ActorType.USER,
        )
        
        # Verify exception current_step set to None (playbook complete)
        call_args = execution_service.exception_repository.update_exception.call_args
        assert call_args[1]["updates"].current_step is None
        
        # Verify both events were emitted
        assert execution_service.event_repository.append_event.call_count == 2
        event_calls = execution_service.event_repository.append_event.call_args_list
        
        # Check PlaybookStepCompleted
        assert event_calls[0][0][1].event_type == "PlaybookStepCompleted"
        
        # Check PlaybookCompleted
        assert event_calls[1][0][1].event_type == "PlaybookCompleted"
    
    @pytest.mark.asyncio
    async def test_complete_step_wrong_playbook(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that completing step fails if wrong playbook is active."""
        sample_exception.current_playbook_id = 2  # Different playbook
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        with pytest.raises(PlaybookExecutionError, match="is not active"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,  # Trying to complete step for playbook 1
                step_order=1,
                actor_type=ActorType.USER,
            )
    
    @pytest.mark.asyncio
    async def test_complete_step_wrong_step_order(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that completing step fails if step order doesn't match current step."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1  # Current step is 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        with pytest.raises(PlaybookExecutionError, match="is not the next expected step"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=2,  # Trying to complete step 2, but current is 1
                actor_type=ActorType.USER,
            )
    
    @pytest.mark.asyncio
    async def test_complete_step_step_not_found(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that completing step fails if step doesn't exist."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        with pytest.raises(PlaybookExecutionError, match="not found"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=999,  # Step doesn't exist
                actor_type=ActorType.USER,
            )
    
    @pytest.mark.asyncio
    async def test_complete_step_idempotent(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that completing the same step twice is idempotent."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        # Mock existing PlaybookStepCompleted event
        existing_event = MagicMock()
        existing_event.event_type = "PlaybookStepCompleted"
        existing_event.payload = {"playbook_id": 1, "step_order": 1}
        execution_service.event_repository.get_events_for_exception.return_value = [existing_event]
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
        )
        
        # Should not update exception or emit event
        execution_service.exception_repository.update_exception.assert_not_called()
        execution_service.event_repository.append_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_complete_step_no_current_step(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that completing step fails if exception has no current step."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = None
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        with pytest.raises(PlaybookExecutionError, match="has no current step"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
            )
    
    @pytest.mark.asyncio
    async def test_skip_step_success(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test successfully skipping a step."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.skip_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            notes="Step not applicable",
        )
        
        # Verify exception was updated to next step
        execution_service.exception_repository.update_exception.assert_called_once()
        call_args = execution_service.exception_repository.update_exception.call_args
        assert call_args[1]["updates"].current_step == 2
        
        # Verify event was emitted
        execution_service.event_repository.append_event.assert_called_once()
        event_call = execution_service.event_repository.append_event.call_args
        assert event_call[0][1].event_type == "PlaybookStepSkipped"
        assert event_call[0][1].payload["step_order"] == 1
    
    @pytest.mark.asyncio
    async def test_skip_step_last_step(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test skipping the last step emits PlaybookCompleted event."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 2
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.skip_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=2,
            actor_type=ActorType.USER,
        )
        
        # Verify both events were emitted
        assert execution_service.event_repository.append_event.call_count == 2
        event_calls = execution_service.event_repository.append_event.call_args_list
        
        assert event_calls[0][0][1].event_type == "PlaybookStepSkipped"
        assert event_calls[1][0][1].event_type == "PlaybookCompleted"
    
    @pytest.mark.asyncio
    async def test_skip_step_validation(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that skip_step validates same conditions as complete_step."""
        sample_exception.current_playbook_id = 2  # Wrong playbook
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        with pytest.raises(PlaybookExecutionError, match="is not active"):
            await execution_service.skip_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
            )
    
    @pytest.mark.asyncio
    async def test_skip_step_idempotent(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that skipping the same step twice is idempotent."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        # Mock existing PlaybookStepSkipped event
        existing_event = MagicMock()
        existing_event.event_type = "PlaybookStepSkipped"
        existing_event.payload = {"playbook_id": 1, "step_order": 1}
        execution_service.event_repository.get_events_for_exception.return_value = [existing_event]
        
        await execution_service.skip_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
        )
        
        # Should not update exception or emit event
        execution_service.exception_repository.update_exception.assert_not_called()
        execution_service.event_repository.append_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self, execution_service, sample_exception
    ):
        """Test that tenant isolation is enforced."""
        execution_service.exception_repository.get_exception.return_value = None
        
        with pytest.raises(PlaybookExecutionError, match="not found"):
            await execution_service.start_playbook_for_exception(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                actor_type=ActorType.AGENT,
            )
        
        # Verify get_exception was called with correct tenant
        execution_service.exception_repository.get_exception.assert_called_once_with(
            "tenant_001", "exc_001"
        )
    
    @pytest.mark.asyncio
    async def test_invalid_step_order(
        self, execution_service
    ):
        """Test that invalid step_order values are rejected."""
        with pytest.raises(ValueError, match="step_order must be >= 1"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=0,  # Invalid
                actor_type=ActorType.USER,
            )
    
    @pytest.mark.asyncio
    async def test_empty_tenant_id(
        self, execution_service
    ):
        """Test that empty tenant_id is rejected."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await execution_service.start_playbook_for_exception(
                tenant_id="",
                exception_id="exc_001",
                playbook_id=1,
                actor_type=ActorType.AGENT,
            )

    @pytest.mark.asyncio
    async def test_complete_step_risky_action_requires_user(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that risky steps require USER actor_type."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        # Make step risky (call_tool)
        risky_step = sample_steps[0]
        risky_step.action_type = "call_tool"
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [risky_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Try with AGENT actor_type (should fail)
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,  # Not USER
                actor_id="PolicyAgent",
            )
        
        # Try with SYSTEM actor_type (should fail)
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.SYSTEM,  # Not USER
            )
        
        # Try with USER actor_type (should succeed)
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,  # Correct
            actor_id="user_123",
        )
        
        # Verify it succeeded
        execution_service.exception_repository.update_exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_step_safe_action_allows_any_actor(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that safe actions allow any actor_type."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        # Make step safe (notify)
        safe_step = sample_steps[0]
        safe_step.action_type = "notify"
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [safe_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Should work with AGENT
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.AGENT,
            actor_id="PolicyAgent",
        )
        
        execution_service.exception_repository.update_exception.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_step_notes_tracked_in_event(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that notes are tracked in PlaybookStepCompleted event."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        notes = "Step completed with custom notes"
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
            notes=notes,
        )
        
        # Verify notes in event payload
        execution_service.event_repository.append_event.assert_called_once()
        event_call = execution_service.event_repository.append_event.call_args
        assert event_call[0][1].payload["notes"] == notes
        assert event_call[0][1].payload["actor_type"] == "user"
        assert event_call[0][1].payload["actor_id"] == "user_123"

    @pytest.mark.asyncio
    async def test_complete_step_actor_type_tracked(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that actor_type and actor_id are tracked in events."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Test with AGENT
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.AGENT,
            actor_id="PolicyAgent",
        )
        
        event_call = execution_service.event_repository.append_event.call_args
        # actor_type is stored as string in DTO
        assert event_call[0][1].actor_type == "agent"
        assert event_call[0][1].actor_id == "PolicyAgent"
        assert event_call[0][1].payload["actor_type"] == "agent"
        assert event_call[0][1].payload["actor_id"] == "PolicyAgent"

    @pytest.mark.asyncio
    async def test_start_playbook_actor_tracking(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test that actor_type and actor_id are tracked in PlaybookStarted event."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = sample_playbook
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.start_playbook_for_exception(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            actor_type=ActorType.USER,
            actor_id="user_456",
        )
        
        event_call = execution_service.event_repository.append_event.call_args
        # actor_type is stored as string in DTO
        assert event_call[0][1].actor_type == "user"
        assert event_call[0][1].actor_id == "user_456"

    @pytest.mark.asyncio
    async def test_complete_step_completion_detection_single_step(
        self, execution_service, sample_exception
    ):
        """Test completion detection for single-step playbook."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        # Single step playbook
        single_step = MagicMock(spec=PlaybookStep)
        single_step.step_id = 1
        single_step.playbook_id = 1
        single_step.step_order = 1
        single_step.name = "Only Step"
        single_step.action_type = "notify"
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [single_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
        )
        
        # Should emit both PlaybookStepCompleted and PlaybookCompleted
        assert execution_service.event_repository.append_event.call_count == 2
        event_calls = execution_service.event_repository.append_event.call_args_list
        
        assert event_calls[0][0][1].event_type == "PlaybookStepCompleted"
        assert event_calls[0][0][1].payload["is_last_step"] is True
        assert event_calls[1][0][1].event_type == "PlaybookCompleted"
        
        # current_step should be None (playbook complete)
        call_args = execution_service.exception_repository.update_exception.call_args
        assert call_args[1]["updates"].current_step is None

    @pytest.mark.asyncio
    async def test_complete_step_completion_detection_multi_step(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test completion detection for multi-step playbook."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 2  # Last step
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=2,
            actor_type=ActorType.USER,
            notes="Final step completed",
        )
        
        # Should emit both events
        assert execution_service.event_repository.append_event.call_count == 2
        event_calls = execution_service.event_repository.append_event.call_args_list
        
        # First event: step completed
        assert event_calls[0][0][1].event_type == "PlaybookStepCompleted"
        assert event_calls[0][0][1].payload["is_last_step"] is True
        assert event_calls[0][0][1].payload["notes"] == "Final step completed"
        
        # Second event: playbook completed
        assert event_calls[1][0][1].event_type == "PlaybookCompleted"
        assert event_calls[1][0][1].payload["total_steps"] == 2
        assert event_calls[1][0][1].payload["notes"] == "Final step completed"

    @pytest.mark.asyncio
    async def test_complete_step_not_last_step_no_completion_event(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that non-last step doesn't emit PlaybookCompleted event."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1  # First step, not last
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
        )
        
        # Should only emit PlaybookStepCompleted, not PlaybookCompleted
        assert execution_service.event_repository.append_event.call_count == 1
        event_call = execution_service.event_repository.append_event.call_args
        assert event_call[0][1].event_type == "PlaybookStepCompleted"
        assert event_call[0][1].payload["is_last_step"] is False
        
        # current_step should advance to 2
        call_args = execution_service.exception_repository.update_exception.call_args
        assert call_args[1]["updates"].current_step == 2

    @pytest.mark.asyncio
    async def test_complete_step_risky_action_types(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that various risky action types require USER actor."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Test call_tool (always risky)
        risky_step1 = MagicMock(spec=PlaybookStep)
        risky_step1.step_id = 1
        risky_step1.step_order = 1
        risky_step1.action_type = "call_tool"
        execution_service.step_repository.get_steps.return_value = [risky_step1]
        
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,
            )
        
        # Test unknown action type (risky)
        risky_step2 = MagicMock(spec=PlaybookStep)
        risky_step2.step_id = 1
        risky_step2.step_order = 1
        risky_step2.action_type = "unknown_action"
        execution_service.step_repository.get_steps.return_value = [risky_step2]
        sample_exception.current_step = 1  # Reset
        
        with pytest.raises(PlaybookExecutionError, match="requires human approval"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,
            )

    @pytest.mark.asyncio
    async def test_complete_step_safe_action_types(
        self, execution_service, sample_exception
    ):
        """Test that safe action types allow any actor."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        safe_actions = ["notify", "add_comment", "set_status", "assign_owner"]
        
        for action_type in safe_actions:
            safe_step = MagicMock(spec=PlaybookStep)
            safe_step.step_id = 1
            safe_step.step_order = 1
            safe_step.action_type = action_type
            execution_service.step_repository.get_steps.return_value = [safe_step]
            sample_exception.current_step = 1  # Reset for each iteration
            
            # Should work with AGENT
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.AGENT,
                actor_id="PolicyAgent",
            )
            
            # Reset mocks for next iteration
            execution_service.exception_repository.update_exception.reset_mock()
            execution_service.event_repository.append_event.reset_mock()

    @pytest.mark.asyncio
    async def test_complete_step_next_step_validation_strict(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test strict next-step validation (cannot skip steps)."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1  # Current step is 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        
        # Try to complete step 2 when current_step is 1 (should fail)
        with pytest.raises(PlaybookExecutionError, match="is not the next expected step"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=2,  # Trying to skip step 1
                actor_type=ActorType.USER,
            )
        
        # Try to complete step 1 when current_step is 2 (should fail - already past)
        sample_exception.current_step = 2
        with pytest.raises(PlaybookExecutionError, match="is not the next expected step"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,  # Trying to go back
                actor_type=ActorType.USER,
            )

    @pytest.mark.asyncio
    async def test_start_playbook_event_already_exists_handling(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test handling when PlaybookStarted event already exists (idempotency edge case)."""
        sample_exception.current_playbook_id = 1
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = sample_playbook
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Mock append_event to raise ValueError (event already exists)
        execution_service.event_repository.append_event.side_effect = ValueError("Event already exists")
        
        # Should handle gracefully (idempotent)
        await execution_service.start_playbook_for_exception(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            actor_type=ActorType.AGENT,
        )
        
        # Should have tried to append event
        execution_service.event_repository.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_step_event_already_exists_handling(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test handling when PlaybookStepCompleted event already exists."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Mock append_event to raise ValueError (event already exists)
        execution_service.event_repository.append_event.side_effect = ValueError("Event already exists")
        
        # Should handle gracefully (idempotent)
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
        )
        
        # Should have tried to append event
        execution_service.event_repository.append_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_complete_step_notes_none_handled(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that None notes are handled correctly."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            notes=None,  # Explicit None
        )
        
        event_call = execution_service.event_repository.append_event.call_args
        # Notes should be None in payload
        assert event_call[0][1].payload["notes"] is None

    @pytest.mark.asyncio
    async def test_complete_step_actor_id_none_handled(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that None actor_id is handled correctly."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        await execution_service.complete_step(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.SYSTEM,
            actor_id=None,  # Explicit None
        )
        
        event_call = execution_service.event_repository.append_event.call_args
        assert event_call[0][1].actor_id is None
        assert event_call[0][1].payload["actor_id"] is None

    @pytest.mark.asyncio
    async def test_start_playbook_value_error_not_already_exists(
        self, execution_service, sample_exception, sample_playbook, sample_steps
    ):
        """Test that ValueError without 'already exists' is re-raised."""
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.playbook_repository.get_playbook.return_value = sample_playbook
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Mock append_event to raise ValueError without "already exists"
        execution_service.event_repository.append_event.side_effect = ValueError("Different error")
        
        with pytest.raises(ValueError, match="Different error"):
            await execution_service.start_playbook_for_exception(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                actor_type=ActorType.AGENT,
            )

    @pytest.mark.asyncio
    async def test_complete_step_value_error_not_already_exists(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that ValueError without 'already exists' is re-raised."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Mock append_event to raise ValueError without "already exists"
        execution_service.event_repository.append_event.side_effect = ValueError("Different error")
        
        with pytest.raises(ValueError, match="Different error"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
            )

    @pytest.mark.asyncio
    async def test_complete_step_playbook_completed_value_error_not_already_exists(
        self, execution_service, sample_exception
    ):
        """Test that ValueError in PlaybookCompleted event without 'already exists' is re-raised."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1  # Last step (single step playbook)
        
        single_step = MagicMock(spec=PlaybookStep)
        single_step.step_id = 1
        single_step.step_order = 1
        single_step.name = "Only Step"
        single_step.action_type = "notify"
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = [single_step]
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # First call succeeds (PlaybookStepCompleted), second call fails (PlaybookCompleted)
        call_count = 0
        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second call (PlaybookCompleted)
                raise ValueError("Different error")
            return None
        
        execution_service.event_repository.append_event.side_effect = side_effect
        
        with pytest.raises(ValueError, match="Different error"):
            await execution_service.complete_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
            )

    @pytest.mark.asyncio
    async def test_skip_step_value_error_not_already_exists(
        self, execution_service, sample_exception, sample_steps
    ):
        """Test that ValueError in skip_step without 'already exists' is re-raised."""
        sample_exception.current_playbook_id = 1
        sample_exception.current_step = 1
        
        execution_service.exception_repository.get_exception.return_value = sample_exception
        execution_service.step_repository.get_steps.return_value = sample_steps
        execution_service.event_repository.get_events_for_exception.return_value = []
        
        # Mock append_event to raise ValueError without "already exists"
        execution_service.event_repository.append_event.side_effect = ValueError("Different error")
        
        with pytest.raises(ValueError, match="Different error"):
            await execution_service.skip_step(
                tenant_id="tenant_001",
                exception_id="exc_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
            )

