"""
Comprehensive audit tests for tool execution lifecycle (P8-15).

Tests verify:
- All executions emit lifecycle events (requested, completed/failed)
- tool_execution records are persisted to database
- Executions are linked to exception events via exception_id
- Tenant-safe querying via APIs (tenant isolation)
- Event payloads contain correct execution_id references
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from src.infrastructure.db.models import ActorType, ToolDefinition, ToolExecutionStatus
from src.repository.exception_events_repository import ExceptionEventRepository
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError
from src.tools.provider import DummyToolProvider, ToolProviderError
from src.tools.validation import ToolValidationService


@pytest.fixture
def sample_tool_definition():
    """Create a sample tool definition for testing."""
    tool_def = ToolDefinition()
    tool_def.tool_id = 1
    tool_def.name = "test_tool"
    tool_def.type = "dummy"
    tool_def.tenant_id = "tenant_001"
    tool_def.config = {
        "description": "Test tool",
        "inputSchema": {"type": "object", "properties": {"param": {"type": "string"}}},
        "outputSchema": {"type": "object"},
        "authType": "none",
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


class TestLifecycleEvents:
    """Tests for lifecycle event emission."""

    @pytest.mark.asyncio
    async def test_execution_emits_requested_event(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that ToolExecutionRequested event is emitted."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        # Setup mocks
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        execution_requested.status = ToolExecutionStatus.REQUESTED
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
        
        # Mock provider
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.USER,
                actor_id="user_123",
                exception_id="exc_001",
            )
        
        # Verify ToolExecutionRequested event was emitted
        assert event_repo.append_event_if_new.call_count >= 1
        
        # Check first call (ToolExecutionRequested)
        first_call = event_repo.append_event_if_new.call_args_list[0]
        event_dto = first_call[0][0]
        
        assert event_dto.event_type == "ToolExecutionRequested"
        assert event_dto.tenant_id == "tenant_001"
        assert event_dto.exception_id == "exc_001"
        assert event_dto.actor_type == ActorType.USER.value
        assert event_dto.actor_id == "user_123"
        assert "execution_id" in event_dto.payload
        assert event_dto.payload["execution_id"] == str(execution_id)
        assert event_dto.payload["tool_id"] == 1
        assert event_dto.payload["status"] == "requested"

    @pytest.mark.asyncio
    async def test_execution_emits_completed_event(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that ToolExecutionCompleted event is emitted on success."""
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
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        execution_succeeded.output_payload = {"result": "success"}
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="ResolutionAgent",
                exception_id="exc_001",
            )
        
        # Verify both Requested and Completed events were emitted
        assert event_repo.append_event_if_new.call_count == 2
        
        # Check second call (ToolExecutionCompleted)
        completed_call = event_repo.append_event_if_new.call_args_list[1]
        event_dto = completed_call[0][0]
        
        assert event_dto.event_type == "ToolExecutionCompleted"
        assert event_dto.tenant_id == "tenant_001"
        assert event_dto.exception_id == "exc_001"
        assert event_dto.actor_type == ActorType.SYSTEM.value
        assert event_dto.actor_id == "ToolExecutionService"
        assert "execution_id" in event_dto.payload
        assert event_dto.payload["execution_id"] == str(execution_id)
        assert event_dto.payload["tool_id"] == 1
        assert event_dto.payload["status"] == "succeeded"
        assert "output" in event_dto.payload

    @pytest.mark.asyncio
    async def test_execution_emits_failed_event(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that ToolExecutionFailed event is emitted on failure."""
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
        execution_failed.error_message = "Tool execution failed"
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_failed]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.side_effect = ToolProviderError("Tool execution failed")
            
            with pytest.raises(ToolExecutionServiceError):
                await execution_service.execute_tool(
                    tenant_id="tenant_001",
                    tool_id=1,
                    payload={"param": "value"},
                    actor_type=ActorType.SYSTEM,
                    actor_id="System",
                    exception_id="exc_001",
                )
        
        # Verify both Requested and Failed events were emitted
        assert event_repo.append_event_if_new.call_count == 2
        
        # Check second call (ToolExecutionFailed)
        failed_call = event_repo.append_event_if_new.call_args_list[1]
        event_dto = failed_call[0][0]
        
        assert event_dto.event_type == "ToolExecutionFailed"
        assert event_dto.tenant_id == "tenant_001"
        assert event_dto.exception_id == "exc_001"
        assert event_dto.actor_type == ActorType.SYSTEM.value
        assert event_dto.actor_id == "ToolExecutionService"
        assert "execution_id" in event_dto.payload
        assert event_dto.payload["execution_id"] == str(execution_id)
        assert event_dto.payload["tool_id"] == 1
        assert event_dto.payload["status"] == "failed"
        assert "error" in event_dto.payload
        assert event_dto.payload["error"] == "Tool execution failed"

    @pytest.mark.asyncio
    async def test_execution_without_exception_id_still_emits_events(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that events are emitted even when exception_id is None."""
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
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.USER,
                actor_id="user_123",
                exception_id=None,  # No exception ID
            )
        
        # Verify events were emitted with fallback exception_id
        assert event_repo.append_event_if_new.call_count == 2
        
        # Check that exception_id uses execution_id as fallback
        requested_call = event_repo.append_event_if_new.call_args_list[0]
        event_dto = requested_call[0][0]
        
        assert event_dto.exception_id == f"tool_exec_{execution_id}"


class TestExecutionPersistence:
    """Tests for tool execution record persistence."""

    @pytest.mark.asyncio
    async def test_execution_record_created(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that execution record is created in database."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        execution_requested.status = ToolExecutionStatus.REQUESTED
        execution_requested.tenant_id = "tenant_001"
        execution_requested.tool_id = 1
        execution_requested.exception_id = "exc_001"
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
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            result = await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.USER,
                actor_id="user_123",
                exception_id="exc_001",
            )
        
        # Verify execution record was created
        tool_exec_repo.create_execution.assert_called_once()
        create_call = tool_exec_repo.create_execution.call_args[0][0]
        
        assert create_call.tenant_id == "tenant_001"
        assert create_call.tool_id == 1
        assert create_call.exception_id == "exc_001"
        assert create_call.status == ToolExecutionStatus.REQUESTED.value
        assert create_call.requested_by_actor_type == ActorType.USER.value
        assert create_call.requested_by_actor_id == "user_123"
        assert create_call.input_payload == {"param": "value"}
        
        # Verify execution record was updated (RUNNING, then SUCCEEDED)
        assert tool_exec_repo.update_execution.call_count == 2
        
        # Verify final result
        assert result.status == ToolExecutionStatus.SUCCEEDED

    @pytest.mark.asyncio
    async def test_execution_record_updated_on_status_change(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that execution record is updated through status transitions."""
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
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        execution_succeeded.output_payload = {"result": "success"}
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="ResolutionAgent",
            )
        
        # Verify status transitions: REQUESTED -> RUNNING -> SUCCEEDED
        assert tool_exec_repo.update_execution.call_count == 2
        
        # First update: RUNNING
        first_update = tool_exec_repo.update_execution.call_args_list[0]
        assert first_update[1]["update_data"].status == ToolExecutionStatus.RUNNING.value
        
        # Second update: SUCCEEDED with output
        second_update = tool_exec_repo.update_execution.call_args_list[1]
        assert second_update[1]["update_data"].status == ToolExecutionStatus.SUCCEEDED.value
        assert second_update[1]["update_data"].output_payload == {"result": "success"}


class TestExceptionEventLinking:
    """Tests for linking tool executions to exception events."""

    @pytest.mark.asyncio
    async def test_execution_linked_to_exception_via_exception_id(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that execution is linked to exception via exception_id."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        execution_requested.status = ToolExecutionStatus.REQUESTED
        execution_requested.exception_id = "exc_001"
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_running = MagicMock()
        execution_running.id = execution_id
        execution_running.status = ToolExecutionStatus.RUNNING
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        execution_succeeded.exception_id = "exc_001"
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            result = await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="ResolutionAgent",
                exception_id="exc_001",
            )
        
        # Verify execution record has exception_id
        create_call = tool_exec_repo.create_execution.call_args[0][0]
        assert create_call.exception_id == "exc_001"
        
        # Verify events reference the exception_id
        requested_call = event_repo.append_event_if_new.call_args_list[0]
        requested_event = requested_call[0][0]
        assert requested_event.exception_id == "exc_001"
        assert requested_event.payload["execution_id"] == str(execution_id)
        
        completed_call = event_repo.append_event_if_new.call_args_list[1]
        completed_event = completed_call[0][0]
        assert completed_event.exception_id == "exc_001"
        assert completed_event.payload["execution_id"] == str(execution_id)
        
        # Verify final execution has exception_id
        assert result.exception_id == "exc_001"

    @pytest.mark.asyncio
    async def test_execution_events_contain_execution_id_reference(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that exception events contain execution_id in payload for linking."""
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
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.USER,
                actor_id="user_123",
                exception_id="exc_001",
            )
        
        # Verify all events contain execution_id in payload
        for call in event_repo.append_event_if_new.call_args_list:
            event_dto = call[0][0]
            assert "execution_id" in event_dto.payload
            assert event_dto.payload["execution_id"] == str(execution_id)
            assert event_dto.payload["tool_id"] == 1


class TestTenantIsolation:
    """Tests for tenant isolation in execution queries."""

    @pytest.mark.asyncio
    async def test_execution_queries_enforce_tenant_isolation(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that execution queries enforce tenant isolation."""
        tool_def_repo, tool_exec_repo, event_repo = mock_repositories
        
        tool_def_repo.get_tool = AsyncMock(return_value=sample_tool_definition)
        
        execution_id = uuid4()
        execution_requested = MagicMock()
        execution_requested.id = execution_id
        execution_requested.status = ToolExecutionStatus.REQUESTED
        execution_requested.tenant_id = "tenant_001"
        tool_exec_repo.create_execution = AsyncMock(return_value=execution_requested)
        
        execution_running = MagicMock()
        execution_running.id = execution_id
        execution_running.status = ToolExecutionStatus.RUNNING
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        execution_succeeded.tenant_id = "tenant_001"
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            result = await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.USER,
                actor_id="user_123",
            )
        
        # Verify all repository calls include tenant_id
        tool_exec_repo.create_execution.assert_called_once()
        create_call = tool_exec_repo.create_execution.call_args[0][0]
        assert create_call.tenant_id == "tenant_001"
        
        # Verify update calls include tenant_id
        for update_call in tool_exec_repo.update_execution.call_args_list:
            assert update_call[1]["tenant_id"] == "tenant_001"
        
        # Verify events include tenant_id
        for call in event_repo.append_event_if_new.call_args_list:
            event_dto = call[0][0]
            assert event_dto.tenant_id == "tenant_001"
        
        # Verify final result has correct tenant_id
        assert result.tenant_id == "tenant_001"


class TestAuditTrailCompleteness:
    """Tests for complete audit trail coverage."""

    @pytest.mark.asyncio
    async def test_all_execution_stages_audited(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that all execution stages generate audit trail."""
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
        execution_succeeded = MagicMock()
        execution_succeeded.id = execution_id
        execution_succeeded.status = ToolExecutionStatus.SUCCEEDED
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_succeeded]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.return_value = {"result": "success"}
            
            await execution_service.execute_tool(
                tenant_id="tenant_001",
                tool_id=1,
                payload={"param": "value"},
                actor_type=ActorType.AGENT,
                actor_id="ResolutionAgent",
                exception_id="exc_001",
            )
        
        # Verify complete audit trail:
        # 1. Execution record created (REQUESTED)
        tool_exec_repo.create_execution.assert_called_once()
        
        # 2. ToolExecutionRequested event emitted
        assert event_repo.append_event_if_new.call_count >= 1
        requested_event = event_repo.append_event_if_new.call_args_list[0][0][0]
        assert requested_event.event_type == "ToolExecutionRequested"
        
        # 3. Execution record updated (RUNNING)
        assert tool_exec_repo.update_execution.call_count >= 1
        
        # 4. Execution record updated (SUCCEEDED)
        assert tool_exec_repo.update_execution.call_count == 2
        
        # 5. ToolExecutionCompleted event emitted
        assert event_repo.append_event_if_new.call_count == 2
        completed_event = event_repo.append_event_if_new.call_args_list[1][0][0]
        assert completed_event.event_type == "ToolExecutionCompleted"

    @pytest.mark.asyncio
    async def test_failed_execution_audit_trail(
        self, execution_service, sample_tool_definition, mock_repositories, mock_validation_service
    ):
        """Test that failed executions generate complete audit trail."""
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
        execution_failed.error_message = "Execution failed"
        tool_exec_repo.update_execution = AsyncMock(
            side_effect=[execution_running, execution_failed]
        )
        
        event_repo.append_event_if_new = AsyncMock(return_value=True)
        
        with patch.object(execution_service.dummy_provider, "execute") as mock_execute:
            mock_execute.side_effect = ToolProviderError("Execution failed")
            
            with pytest.raises(ToolExecutionServiceError):
                await execution_service.execute_tool(
                    tenant_id="tenant_001",
                    tool_id=1,
                    payload={"param": "value"},
                    actor_type=ActorType.AGENT,
                    actor_id="ResolutionAgent",
                    exception_id="exc_001",
                )
        
        # Verify complete audit trail for failed execution:
        # 1. Execution record created (REQUESTED)
        tool_exec_repo.create_execution.assert_called_once()
        
        # 2. ToolExecutionRequested event emitted
        assert event_repo.append_event_if_new.call_count >= 1
        requested_event = event_repo.append_event_if_new.call_args_list[0][0][0]
        assert requested_event.event_type == "ToolExecutionRequested"
        
        # 3. Execution record updated (RUNNING)
        assert tool_exec_repo.update_execution.call_count >= 1
        
        # 4. Execution record updated (FAILED with error)
        assert tool_exec_repo.update_execution.call_count == 2
        failed_update = tool_exec_repo.update_execution.call_args_list[1]
        assert failed_update[1]["update_data"].status == ToolExecutionStatus.FAILED.value
        assert failed_update[1]["update_data"].error_message == "Execution failed"
        
        # 5. ToolExecutionFailed event emitted
        assert event_repo.append_event_if_new.call_count == 2
        failed_event = event_repo.append_event_if_new.call_args_list[1][0][0]
        assert failed_event.event_type == "ToolExecutionFailed"
        assert "error" in failed_event.payload

