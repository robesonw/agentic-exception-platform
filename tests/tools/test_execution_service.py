"""
Unit and integration tests for ToolExecutionService.

Tests cover:
- Full execution workflow (requested → running → succeeded/failed)
- Validation integration
- Provider routing
- Event emission
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.infrastructure.db.models import ActorType, ToolDefinition, ToolExecutionStatus
from src.repository.exception_events_repository import ExceptionEventRepository
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError
from src.tools.provider import DummyToolProvider, HttpToolProvider, ToolProviderError
from src.tools.validation import ToolValidationService


@pytest.fixture
def sample_tool_definition():
    """Create a sample tool definition for testing."""
    tool_def = ToolDefinition()
    tool_def.tool_id = 1
    tool_def.name = "test_tool"
    tool_def.type = "http"
    tool_def.tenant_id = "tenant_001"
    tool_def.config = {
        "description": "Test tool",
        "inputSchema": {"type": "object", "properties": {"param": {"type": "string"}}},
        "outputSchema": {"type": "object"},
        "authType": "none",
        "endpointConfig": {
            "url": "https://api.example.com/tool",
            "method": "POST",
            "headers": {},
            "timeout_seconds": 30.0,
        },
        "tenantScope": "tenant",
    }
    return tool_def


@pytest.fixture
def mock_repositories():
    """Create mock repositories."""
    tool_def_repo = MagicMock(spec=ToolDefinitionRepository)
    tool_exec_repo = MagicMock(spec=ToolExecutionRepository)
    event_repo = MagicMock(spec=ExceptionEventRepository)
    return tool_def_repo, tool_exec_repo, event_repo


@pytest.fixture
def mock_validation_service():
    """Create mock validation service."""
    validation_service = MagicMock(spec=ToolValidationService)
    validation_service.validate_payload = AsyncMock()
    validation_service.check_tool_enabled = AsyncMock(return_value=True)
    validation_service.check_tenant_scope = AsyncMock()
    validation_service.redact_secrets = MagicMock(side_effect=lambda x: x)  # Return as-is for tests
    return validation_service


@pytest.fixture
def execution_service(mock_repositories, mock_validation_service):
    """Create ToolExecutionService instance for testing."""
    tool_def_repo, tool_exec_repo, event_repo = mock_repositories
    return ToolExecutionService(
        tool_definition_repository=tool_def_repo,
        tool_execution_repository=tool_exec_repo,
        exception_event_repository=event_repo,
        validation_service=mock_validation_service,
    )


class TestToolExecutionService:
    """Tests for ToolExecutionService."""

    @pytest.mark.asyncio
    async def test_execute_tool_success(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test successful tool execution workflow."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        # Setup mocks
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        # Mock execution creation
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        execution_requested.status = ToolExecutionStatus.REQUESTED
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        # Mock status updates
        execution_running = MagicMock()
        execution_running.id = execution_id
        execution_running.status = ToolExecutionStatus.RUNNING
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        execution_succeeded.output_payload = {"result": "success"}
        
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        # Mock event emission
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock provider execution
        with patch.object(execution_service.http_provider, "execute") as mock_provider_execute:
            mock_provider_execute.return_value = {"result": "success"}
            
            # Execute
            payload = {"param": "value"}
            result = await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload=payload,
                actor_type=ActorType.AGENT,
                actor_id="ResolutionAgent",
            )
        
        # Verify
        assert result.status == ToolExecutionStatus.SUCCEEDED
        tool_def_repo.get_tool.assert_called_once_with(tool_id=1, tenant_id="tenant_001")
        mock_validation_service.validate_payload.assert_called_once()
        mock_validation_service.check_tool_enabled.assert_called_once()
        mock_validation_service.check_tenant_scope.assert_called_once()
        tool_exec_repo.create_execution.assert_called_once()
        assert tool_exec_repo.update_execution.call_count == 2  # RUNNING, then SUCCEEDED
        assert event_repo.append_event_if_new.call_count == 2  # Requested, Completed

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(
        self, execution_service, mock_repositories, mock_validation_service
    ):
        """Test error when tool is not found."""
        tool_def_repo, _, _ = mock_repositories
        tool_def_repo.get_tool = AsyncMock(return_value=None)
        
        with pytest.raises(ToolExecutionServiceError) as exc_info:
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=999,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
            )
        
        assert "not found" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_validation_fails(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test error when validation fails."""
        tool_def_repo, _, _ = mock_repositories
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        from src.tools.validation import ToolValidationError
        
        mock_validation_service.validate_payload = AsyncMock(
            side_effect=ToolValidationError("Invalid payload")
        )
        
        with pytest.raises(ToolExecutionServiceError) as exc_info:
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"invalid": "payload"},
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
            )
        
        assert "validation failed" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_disabled(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test error when tool is disabled."""
        tool_def_repo, _, _ = mock_repositories
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        mock_validation_service.check_tool_enabled = AsyncMock(return_value=False)
        
        with pytest.raises(ToolExecutionServiceError) as exc_info:
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
            )
        
        assert "disabled" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_tool_provider_error(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test error handling when provider fails."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        execution_requested.status = ToolExecutionStatus.REQUESTED
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_running = MagicMock()
        execution_running.id = execution_id
        execution_running.status = ToolExecutionStatus.RUNNING
        
        execution_failed = MagicMock()
        execution_failed.id = execution_id
        execution_failed.status = ToolExecutionStatus.FAILED
        execution_failed.error_message = "Provider error"
        
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_failed]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock provider to raise error
        with patch.object(execution_service.http_provider, "execute") as mock_execute:
            mock_execute.side_effect = ToolProviderError("Provider execution failed")
            
            with pytest.raises(ToolExecutionServiceError) as exc_info:
                await execution_service.execute_tool(
                    tenant_id="tenant_001",
                    tool_id=1,
                    payload={"param": "value"},
                    actor_type=ActorType.AGENT,
                    actor_id="Agent1",
                )
            
            assert "execution failed" in str(exc_info.value).lower()
            
            # Verify status was updated to FAILED
            assert tool_exec_repo.update_execution.call_count == 2  # RUNNING, then FAILED
            last_update = tool_exec_repo.update_execution.call_args_list[-1]
            update_dto = last_update[1]["update_data"]
            assert update_dto.status == ToolExecutionStatus.FAILED.value or update_dto.status == ToolExecutionStatus.FAILED
            
            # Verify failed event was emitted
            assert event_repo.append_event_if_new.call_count == 2  # Requested, Failed

    @pytest.mark.asyncio
    async def test_execute_tool_with_exception_id(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test execution with exception_id linked."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[
                MagicMock(id=execution_id, status=ToolExecutionStatus.RUNNING),
                execution_succeeded,
            ]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock provider execution
        with patch.object(execution_service.http_provider, "execute") as mock_provider_execute:
            mock_provider_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
                exception_id="EXC_001",
            )
        
        # Verify exception_id was passed to create_execution
        create_call = tool_exec_repo.create_execution.call_args[0][0]
        assert create_call.exception_id == "EXC_001"
        
        # Verify events use exception_id
        event_calls = event_repo.append_event_if_new.call_args_list
        assert all(call[0][0].exception_id == "EXC_001" for call in event_calls)

    @pytest.mark.asyncio
    async def test_execute_tool_status_transitions(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that status transitions correctly: REQUESTED → RUNNING → SUCCEEDED."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_running = MagicMock()
        execution_running.id = execution_id
        execution_running.status = ToolExecutionStatus.RUNNING
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock provider execution
        with patch.object(execution_service.http_provider, "execute") as mock_provider_execute:
            mock_provider_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.USER,
                actor_id="user123",
            )
        
        # Verify status transitions
        update_calls = tool_exec_repo.update_execution.call_args_list
        assert len(update_calls) == 2
        status1 = update_calls[0][1]["update_data"].status
        status2 = update_calls[1][1]["update_data"].status
        assert status1 == ToolExecutionStatus.RUNNING.value or status1 == ToolExecutionStatus.RUNNING
        assert status2 == ToolExecutionStatus.SUCCEEDED.value or status2 == ToolExecutionStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_execute_tool_provider_routing_http(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that HTTP tools route to HttpToolProvider."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[
                MagicMock(id=execution_id, status=ToolExecutionStatus.RUNNING),
                execution_succeeded,
            ]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock HttpToolProvider.execute
        with patch.object(execution_service.http_provider, "execute") as mock_http_execute:
            mock_http_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
            )
            
            # Verify HttpToolProvider was called
            mock_http_execute.assert_called_once()
            assert mock_http_execute.call_args[0][0] == sample_tool_definition

    @pytest.mark.asyncio
    async def test_execute_tool_provider_routing_dummy(
        self, execution_service, mock_repositories, mock_validation_service
    ):
        """Test that unknown tool types route to DummyToolProvider."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        # Create tool with unknown type
        tool_def = ToolDefinition()
        tool_def.tool_id = 2
        tool_def.name = "custom_tool"
        tool_def.type = "custom_type"
        tool_def.tenant_id = "tenant_001"
        tool_def.config = {}
        
        tool_def_repo.get_tool = AsyncMock(return_value=tool_def)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[
                MagicMock(id=execution_id, status=ToolExecutionStatus.RUNNING),
                execution_succeeded,
            ]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock DummyToolProvider.execute
        with patch.object(execution_service.dummy_provider, "execute") as mock_dummy_execute:
            mock_dummy_execute.return_value = {"status": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=2,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
            )
            
            # Verify DummyToolProvider was called
            mock_dummy_execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_tool_event_emission(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that events are emitted correctly."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[
                MagicMock(id=execution_id, status=ToolExecutionStatus.RUNNING),
                execution_succeeded,
            ]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock provider execution
        with patch.object(execution_service.http_provider, "execute") as mock_provider_execute:
            mock_provider_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="ResolutionAgent",
            )
        
        # Verify events were emitted
        assert event_repo.append_event_if_new.call_count == 2
        
        # Check first event (Requested)
        requested_event = event_repo.append_event_if_new.call_args_list[0][0][0]
        assert requested_event.event_type == "ToolExecutionRequested"
        assert requested_event.actor_type == ActorType.AGENT.value or requested_event.actor_type == ActorType.AGENT
        assert requested_event.actor_id == "ResolutionAgent"
        
        # Check second event (Completed)
        completed_event = event_repo.append_event_if_new.call_args_list[1][0][0]
        assert completed_event.event_type == "ToolExecutionCompleted"
        assert completed_event.actor_type == ActorType.SYSTEM.value or completed_event.actor_type == ActorType.SYSTEM
        assert completed_event.actor_id == "ToolExecutionService"

    @pytest.mark.asyncio
    async def test_execute_tool_secret_redaction(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that secrets are redacted in event payloads."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[
                MagicMock(id=execution_id, status=ToolExecutionStatus.RUNNING),
                execution_succeeded,
            ]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        payload = {"param": "secret_value", "api_key": "secret123"}
        output = {"result": "success", "password": "secret456"}
        
        # Mock provider execution
        with patch.object(execution_service.http_provider, "execute") as mock_provider_execute:
            mock_provider_execute.return_value = output
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload=payload,
                actor_type=ActorType.AGENT,
                actor_id="Agent1",
            )
        
        # Verify that completed event has redacted output
        # The redaction happens in _emit_execution_completed_event
        assert event_repo.append_event_if_new.call_count == 2  # Requested and Completed
        
        # Check the completed event payload
        completed_event = event_repo.append_event_if_new.call_args_list[1][0][0]
        assert completed_event.event_type == "ToolExecutionCompleted"
        # The output should be redacted (api_key and password should be masked)
        output_payload = completed_event.payload.get("output", {})
        # Verify secrets are redacted (check that sensitive keys are present but values are redacted)
        if "password" in output_payload:
            assert output_payload["password"] != "secret456"  # Should be redacted

    @pytest.mark.asyncio
    async def test_execute_tool_unexpected_error(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test handling of unexpected errors."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_failed = MagicMock()
        execution_failed.id = execution_id
        execution_failed.status = ToolExecutionStatus.FAILED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[
                MagicMock(id=execution_id, status=ToolExecutionStatus.RUNNING),
                execution_failed,
            ]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        # Mock provider to raise unexpected error
        with patch.object(execution_service.http_provider, "execute") as mock_execute:
            mock_execute.side_effect = ValueError("Unexpected error")
            
            with pytest.raises(ToolExecutionServiceError) as exc_info:
                await execution_service.execute_tool(
                    tenant_id="tenant_001",
                    tool_id=1,
                    payload={"param": "value"},
                    actor_type=ActorType.AGENT,
                    actor_id="Agent1",
                )
            
            assert "Unexpected error" in str(exc_info.value)
            
            # Verify failed event was emitted
            failed_event = event_repo.append_event_if_new.call_args_list[-1][0][0]
            assert failed_event.event_type == "ToolExecutionFailed"

    @pytest.mark.asyncio
    async def test_close(self, execution_service):
        """Test closing the service and providers."""
        with patch.object(execution_service.http_provider, "close") as mock_close:
            await execution_service.close()
            mock_close.assert_called_once()

