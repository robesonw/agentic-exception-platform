"""
Unit tests for PlaybookExecutionService tool execution integration (P8-9).

Tests verify:
- call_tool step handling
- Tool execution on human step completion
- Execution result storage in events
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.infrastructure.db.models import ActorType, ToolExecutionStatus
from src.playbooks.execution_service import PlaybookExecutionService, PlaybookExecutionError
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError


@pytest.fixture
def mock_repositories():
    """Create mock repositories."""
    return {
        "exception_repo": MagicMock(spec=ExceptionRepository),
        "event_repo": MagicMock(spec=ExceptionEventRepository),
        "playbook_repo": MagicMock(spec=PlaybookRepository),
        "step_repo": MagicMock(spec=PlaybookStepRepository),
    }


@pytest.fixture
def mock_tool_execution_service():
    """Create mock tool execution service."""
    service = MagicMock(spec=ToolExecutionService)
    return service


@pytest.fixture
def execution_service(mock_repositories, mock_tool_execution_service):
    """Create PlaybookExecutionService instance."""
    return PlaybookExecutionService(
        exception_repository=mock_repositories["exception_repo"],
        event_repository=mock_repositories["event_repo"],
        playbook_repository=mock_repositories["playbook_repo"],
        step_repository=mock_repositories["step_repo"],
        tool_execution_service=mock_tool_execution_service,
    )


@pytest.fixture
def mock_exception():
    """Create mock exception."""
    exception = MagicMock()
    exception.exception_id = "EXC_001"
    exception.current_playbook_id = 1
    exception.current_step = 1
    return exception


@pytest.fixture
def mock_playbook():
    """Create mock playbook."""
    playbook = MagicMock()
    playbook.playbook_id = 1
    playbook.name = "Test Playbook"
    playbook.version = 1
    return playbook


@pytest.fixture
def mock_step_call_tool():
    """Create mock call_tool step."""
    step = MagicMock()
    step.step_id = 10
    step.step_order = 1
    step.name = "Call Tool Step"
    step.action_type = "call_tool"
    step.params = {
        "tool_id": 5,
        "payload": {"param1": "value1", "param2": 123},
    }
    return step


@pytest.fixture
def mock_tool_execution():
    """Create mock tool execution result."""
    execution = MagicMock()
    execution.id = uuid4()
    execution.tool_id = 5
    execution.status = ToolExecutionStatus.SUCCEEDED
    execution.error_message = None
    execution.output_payload = {"result": "success", "data": {"key": "value"}}
    return execution


class TestPlaybookExecutionServiceToolIntegration:
    """Tests for tool execution integration in playbook execution."""

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_executes_tool(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
        mock_step_call_tool,
        mock_tool_execution,
    ):
        """Test that completing a call_tool step executes the tool."""
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[mock_step_call_tool])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        mock_repositories["exception_repo"].update_exception = AsyncMock()
        mock_repositories["event_repo"].append_event = AsyncMock()
        
        mock_tool_execution_service.execute_tool = AsyncMock(return_value=mock_tool_execution)
        
        # Complete step
        await execution_service.complete_step(
            tenant_id="TENANT_001",
            exception_id="EXC_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
        )
        
        # Verify tool execution was called
        mock_tool_execution_service.execute_tool.assert_called_once_with(
            tenant_id="TENANT_001",
            tool_id=5,
            payload={"param1": "value1", "param2": 123},
            actor_type=ActorType.USER,
            actor_id="user_123",
            exception_id="EXC_001",
        )
        
        # Verify event was emitted with tool execution result
        mock_repositories["event_repo"].append_event.assert_called()
        # Get all calls to find PlaybookStepCompleted event
        all_calls = mock_repositories["event_repo"].append_event.call_args_list
        step_completed_event = None
        for call in all_calls:
            event_dto = call[0][1]  # Second argument is the event DTO
            if event_dto.event_type == "PlaybookStepCompleted":
                step_completed_event = event_dto
                break
        
        assert step_completed_event is not None, "PlaybookStepCompleted event not found"
        assert "tool_execution" in step_completed_event.payload
        assert step_completed_event.payload["tool_execution"]["execution_id"] == str(mock_tool_execution.id)
        assert step_completed_event.payload["tool_execution"]["tool_id"] == 5
        assert step_completed_event.payload["tool_execution"]["status"] == "succeeded"
        assert step_completed_event.payload["tool_execution"]["success"] is True

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_handles_failed_execution(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
        mock_step_call_tool,
    ):
        """Test that failed tool execution is handled and stored."""
        # Create failed execution
        failed_execution = MagicMock()
        failed_execution.id = uuid4()
        failed_execution.tool_id = 5
        failed_execution.status = ToolExecutionStatus.FAILED
        failed_execution.error_message = "Tool execution failed: connection timeout"
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[mock_step_call_tool])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        mock_repositories["exception_repo"].update_exception = AsyncMock()
        mock_repositories["event_repo"].append_event = AsyncMock()
        
        mock_tool_execution_service.execute_tool = AsyncMock(return_value=failed_execution)
        
        # Complete step (should still succeed even if tool execution fails)
        await execution_service.complete_step(
            tenant_id="TENANT_001",
            exception_id="EXC_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
        )
        
        # Verify event includes failed execution result
        all_calls = mock_repositories["event_repo"].append_event.call_args_list
        step_completed_event = None
        for call in all_calls:
            event_dto = call[0][1]
            if event_dto.event_type == "PlaybookStepCompleted":
                step_completed_event = event_dto
                break
        
        assert step_completed_event is not None
        assert step_completed_event.payload["tool_execution"]["status"] == "failed"
        assert step_completed_event.payload["tool_execution"]["success"] is False
        assert step_completed_event.payload["tool_execution"]["error_message"] == "Tool execution failed: connection timeout"

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_requires_tool_execution_service(
        self,
        mock_repositories,
        mock_exception,
        mock_playbook,
        mock_step_call_tool,
    ):
        """Test that call_tool step requires ToolExecutionService."""
        # Create service without tool_execution_service
        service = PlaybookExecutionService(
            exception_repository=mock_repositories["exception_repo"],
            event_repository=mock_repositories["event_repo"],
            playbook_repository=mock_repositories["playbook_repo"],
            step_repository=mock_repositories["step_repo"],
            tool_execution_service=None,  # Not provided
        )
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[mock_step_call_tool])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        
        # Attempt to complete call_tool step should fail
        with pytest.raises(PlaybookExecutionError) as exc_info:
            await service.complete_step(
                tenant_id="TENANT_001",
                exception_id="EXC_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        assert "ToolExecutionService is required" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_missing_tool_id(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
    ):
        """Test that call_tool step with missing tool_id raises error."""
        # Create step without tool_id
        step = MagicMock()
        step.step_id = 10
        step.step_order = 1
        step.name = "Call Tool Step"
        step.action_type = "call_tool"
        step.params = {
            "payload": {"param1": "value1"},
            # Missing tool_id
        }
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[step])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        
        # Attempt to complete step should fail
        with pytest.raises(PlaybookExecutionError) as exc_info:
            await execution_service.complete_step(
                tenant_id="TENANT_001",
                exception_id="EXC_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        assert "tool_id" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_invalid_tool_id(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
    ):
        """Test that call_tool step with invalid tool_id raises error."""
        # Create step with invalid tool_id
        step = MagicMock()
        step.step_id = 10
        step.step_order = 1
        step.name = "Call Tool Step"
        step.action_type = "call_tool"
        step.params = {
            "tool_id": "not_an_integer",
            "payload": {"param1": "value1"},
        }
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[step])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        
        # Attempt to complete step should fail
        with pytest.raises(PlaybookExecutionError) as exc_info:
            await execution_service.complete_step(
                tenant_id="TENANT_001",
                exception_id="EXC_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        assert "Invalid tool_id" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_invalid_payload(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
    ):
        """Test that call_tool step with invalid payload raises error."""
        # Create step with invalid payload (not a dict)
        step = MagicMock()
        step.step_id = 10
        step.step_order = 1
        step.name = "Call Tool Step"
        step.action_type = "call_tool"
        step.params = {
            "tool_id": 5,
            "payload": "not_a_dictionary",  # Invalid
        }
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[step])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        
        # Attempt to complete step should fail
        with pytest.raises(PlaybookExecutionError) as exc_info:
            await execution_service.complete_step(
                tenant_id="TENANT_001",
                exception_id="EXC_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        assert "Invalid payload" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_handles_tool_execution_error(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
        mock_step_call_tool,
    ):
        """Test that ToolExecutionServiceError is properly handled."""
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[mock_step_call_tool])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        
        # Mock tool execution service to raise error
        mock_tool_execution_service.execute_tool = AsyncMock(
            side_effect=ToolExecutionServiceError("Tool not enabled for tenant")
        )
        
        # Attempt to complete step should fail
        with pytest.raises(PlaybookExecutionError) as exc_info:
            await execution_service.complete_step(
                tenant_id="TENANT_001",
                exception_id="EXC_001",
                playbook_id=1,
                step_order=1,
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        assert "Tool execution failed" in str(exc_info.value)
        assert "Tool not enabled for tenant" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_complete_step_non_call_tool_does_not_execute_tool(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
    ):
        """Test that non-call_tool steps do not trigger tool execution."""
        # Create non-call_tool step
        step = MagicMock()
        step.step_id = 10
        step.step_order = 1
        step.name = "Notify Step"
        step.action_type = "notify"
        step.params = {"message": "Test notification"}
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[step])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        mock_repositories["exception_repo"].update_exception = AsyncMock()
        mock_repositories["event_repo"].append_event = AsyncMock()
        
        # Complete step
        await execution_service.complete_step(
            tenant_id="TENANT_001",
            exception_id="EXC_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
        )
        
        # Verify tool execution was NOT called
        mock_tool_execution_service.execute_tool.assert_not_called()
        
        # Verify event does not include tool_execution
        all_calls = mock_repositories["event_repo"].append_event.call_args_list
        step_completed_event = None
        for call in all_calls:
            event_dto = call[0][1]
            if event_dto.event_type == "PlaybookStepCompleted":
                step_completed_event = event_dto
                break
        
        assert step_completed_event is not None
        assert "tool_execution" not in step_completed_event.payload

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_with_empty_payload(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
        mock_tool_execution,
    ):
        """Test that call_tool step with empty payload works."""
        # Create step with empty payload
        step = MagicMock()
        step.step_id = 10
        step.step_order = 1
        step.name = "Call Tool Step"
        step.action_type = "call_tool"
        step.params = {
            "tool_id": 5,
            "payload": {},  # Empty payload
        }
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[step])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        mock_repositories["exception_repo"].update_exception = AsyncMock()
        mock_repositories["event_repo"].append_event = AsyncMock()
        
        mock_tool_execution_service.execute_tool = AsyncMock(return_value=mock_tool_execution)
        
        # Complete step
        await execution_service.complete_step(
            tenant_id="TENANT_001",
            exception_id="EXC_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
        )
        
        # Verify tool execution was called with empty payload
        mock_tool_execution_service.execute_tool.assert_called_once_with(
            tenant_id="TENANT_001",
            tool_id=5,
            payload={},
            actor_type=ActorType.USER,
            actor_id="user_123",
            exception_id="EXC_001",
        )

    @pytest.mark.asyncio
    async def test_complete_step_call_tool_with_missing_payload_defaults_to_empty(
        self,
        execution_service,
        mock_repositories,
        mock_tool_execution_service,
        mock_exception,
        mock_playbook,
        mock_tool_execution,
    ):
        """Test that call_tool step without payload defaults to empty dict."""
        # Create step without payload
        step = MagicMock()
        step.step_id = 10
        step.step_order = 1
        step.name = "Call Tool Step"
        step.action_type = "call_tool"
        step.params = {
            "tool_id": 5,
            # No payload
        }
        
        # Setup mocks
        mock_repositories["exception_repo"].get_exception = AsyncMock(return_value=mock_exception)
        mock_repositories["playbook_repo"].get_playbook = AsyncMock(return_value=mock_playbook)
        mock_repositories["step_repo"].get_steps = AsyncMock(return_value=[step])
        mock_repositories["event_repo"].get_events_for_exception = AsyncMock(return_value=[])
        mock_repositories["exception_repo"].update_exception = AsyncMock()
        mock_repositories["event_repo"].append_event = AsyncMock()
        
        mock_tool_execution_service.execute_tool = AsyncMock(return_value=mock_tool_execution)
        
        # Complete step
        await execution_service.complete_step(
            tenant_id="TENANT_001",
            exception_id="EXC_001",
            playbook_id=1,
            step_order=1,
            actor_type=ActorType.USER,
            actor_id="user_123",
        )
        
        # Verify tool execution was called with empty payload
        mock_tool_execution_service.execute_tool.assert_called_once()
        call_kwargs = mock_tool_execution_service.execute_tool.call_args[1]
        assert call_kwargs["payload"] == {}

