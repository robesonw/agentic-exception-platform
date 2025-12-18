"""
Unit tests for ToolWorker.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from src.events.types import ToolExecutionCompleted, ToolExecutionRequested
from src.infrastructure.db.models import ActorType, ToolExecution, ToolExecutionStatus
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError
from src.workers.tool_worker import ToolWorker


class MockBroker(Broker):
    """Mock broker for testing."""
    
    def publish(self, topic: str, key: str | None, value: bytes | str | dict) -> None:
        pass
        
    def subscribe(self, topics: list[str], group_id: str, handler: callable) -> None:
        pass
        
    def health(self) -> dict:
        return {"status": "healthy", "connected": True}
        
    def close(self) -> None:
        pass


class TestToolWorker:
    """Test ToolWorker."""
    
    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        return MockBroker()
    
    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        publisher = AsyncMock(spec=EventPublisherService)
        publisher.publish_event = AsyncMock()
        return publisher
    
    @pytest.fixture
    def mock_tool_execution_service(self):
        """Create mock tool execution service."""
        service = AsyncMock(spec=ToolExecutionService)
        
        # Mock successful execution
        mock_execution = Mock(spec=ToolExecution)
        mock_execution.id = uuid4()
        mock_execution.status = ToolExecutionStatus.SUCCEEDED
        mock_execution.output_payload = {"result": "success", "data": "test"}
        mock_execution.error_message = None
        
        service.execute_tool = AsyncMock(return_value=mock_execution)
        return service
    
    @pytest.fixture
    def mock_event_processing_repo(self):
        """Create mock event processing repository."""
        repo = AsyncMock(spec=EventProcessingRepository)
        repo.is_processed = AsyncMock(return_value=False)
        repo.mark_processing = AsyncMock()
        repo.mark_completed = AsyncMock()
        return repo
    
    @pytest.fixture
    def tool_worker(
        self,
        mock_broker,
        mock_event_publisher,
        mock_tool_execution_service,
        mock_event_processing_repo,
    ):
        """Create ToolWorker instance."""
        return ToolWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="tool-worker-group",
            event_publisher=mock_event_publisher,
            tool_execution_service=mock_tool_execution_service,
            event_processing_repo=mock_event_processing_repo,
        )
    
    @pytest.mark.asyncio
    async def test_process_tool_execution_requested_event_success(
        self,
        tool_worker,
        mock_event_publisher,
        mock_tool_execution_service,
    ):
        """Test processing ToolExecutionRequested event with successful execution."""
        # Create ToolExecutionRequested event
        tool_requested_event = ToolExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="1",
            tool_name="validateData",
            tool_params={"data": "test"},
            execution_context={"step": 1},
        )
        
        # Process event
        await tool_worker.process_event(tool_requested_event)
        
        # Verify tool was executed
        mock_tool_execution_service.execute_tool.assert_called_once()
        call_args = mock_tool_execution_service.execute_tool.call_args
        assert call_args[1]["tenant_id"] == "tenant_001"
        assert call_args[1]["tool_id"] == 1
        assert call_args[1]["exception_id"] == "exc_001"
        assert call_args[1]["actor_type"] == ActorType.AGENT
        assert call_args[1]["actor_id"] == "ToolWorker"
        
        # Verify ToolExecutionCompleted event was emitted
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ToolExecutionCompleted"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["status"] == "success"
        assert "result" in event_data["payload"]
    
    @pytest.mark.asyncio
    async def test_process_tool_execution_requested_event_failure(
        self,
        tool_worker,
        mock_event_publisher,
        mock_tool_execution_service,
    ):
        """Test processing ToolExecutionRequested event with failed execution."""
        # Mock failed execution
        mock_execution = Mock(spec=ToolExecution)
        mock_execution.id = uuid4()
        mock_execution.status = ToolExecutionStatus.FAILED
        mock_execution.output_payload = None
        mock_execution.error_message = "Tool execution failed"
        
        mock_tool_execution_service.execute_tool = AsyncMock(return_value=mock_execution)
        
        # Create ToolExecutionRequested event
        tool_requested_event = ToolExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="1",
            tool_name="validateData",
            tool_params={"data": "test"},
        )
        
        # Process event
        await tool_worker.process_event(tool_requested_event)
        
        # Verify ToolExecutionCompleted event was emitted with failure status
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ToolExecutionCompleted"
        assert event_data["payload"]["status"] == "failure"
        assert event_data["payload"]["error_message"] == "Tool execution failed"
    
    @pytest.mark.asyncio
    async def test_process_tool_execution_requested_event_error(
        self,
        tool_worker,
        mock_event_publisher,
        mock_tool_execution_service,
    ):
        """Test processing ToolExecutionRequested event with execution error."""
        # Mock execution service to raise error
        mock_tool_execution_service.execute_tool = AsyncMock(
            side_effect=ToolExecutionServiceError("Tool validation failed")
        )
        
        # Create ToolExecutionRequested event
        tool_requested_event = ToolExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="1",
            tool_name="validateData",
            tool_params={"data": "test"},
        )
        
        # Process event
        await tool_worker.process_event(tool_requested_event)
        
        # Verify ToolExecutionCompleted event was emitted with error status
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ToolExecutionCompleted"
        assert event_data["payload"]["status"] == "error"
        assert "error_message" in event_data["payload"]
        assert "Tool validation failed" in event_data["payload"]["error_message"]
    
    @pytest.mark.asyncio
    async def test_process_event_wrong_type(self, tool_worker):
        """Test processing wrong event type raises error."""
        from src.events.schema import CanonicalEvent
        
        # Create wrong event type
        wrong_event = CanonicalEvent.create(
            event_type="WrongEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="ToolWorker expects ToolExecutionRequested"):
            await tool_worker.process_event(wrong_event)
    
    @pytest.mark.asyncio
    async def test_emit_tool_execution_completed_event(
        self,
        tool_worker,
        mock_event_publisher,
    ):
        """Test ToolExecutionCompleted event emission."""
        # Emit event
        await tool_worker._emit_tool_execution_completed_event(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="1",
            execution_id=str(uuid4()),
            result={"data": "test"},
            status="success",
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ToolExecutionCompleted"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["tool_id"] == "1"
        assert event_data["payload"]["status"] == "success"
        assert "result" in event_data["payload"]


class TestToolWorkerIntegration:
    """Integration tests for ToolWorker."""
    
    @pytest.mark.asyncio
    async def test_requested_to_completed_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_tool_execution_service,
        mock_event_processing_repo,
    ):
        """Test complete flow from ToolExecutionRequested to ToolExecutionCompleted."""
        # Create worker
        worker = ToolWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="tool-worker-group",
            event_publisher=mock_event_publisher,
            tool_execution_service=mock_tool_execution_service,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create ToolExecutionRequested event
        tool_requested_event = ToolExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="1",
            tool_name="validateData",
            tool_params={"data": "test", "format": "json"},
            execution_context={"step": 1, "playbook_id": "PB01"},
        )
        
        # Process event
        await worker.process_event(tool_requested_event)
        
        # Verify tool was executed
        assert mock_tool_execution_service.execute_tool.called
        
        # Verify ToolExecutionCompleted event was emitted
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ToolExecutionCompleted"
        assert event_data["exception_id"] == "exc_001"
        assert "execution_id" in event_data["payload"]
        assert "status" in event_data["payload"]
    
    @pytest.mark.asyncio
    async def test_requested_to_failed_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_tool_execution_service,
        mock_event_processing_repo,
    ):
        """Test complete flow from ToolExecutionRequested to ToolExecutionCompleted (failed)."""
        # Mock failed execution
        mock_execution = Mock(spec=ToolExecution)
        mock_execution.id = uuid4()
        mock_execution.status = ToolExecutionStatus.FAILED
        mock_execution.output_payload = None
        mock_execution.error_message = "HTTP 500 error"
        
        mock_tool_execution_service.execute_tool = AsyncMock(return_value=mock_execution)
        
        # Create worker
        worker = ToolWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="tool-worker-group",
            event_publisher=mock_event_publisher,
            tool_execution_service=mock_tool_execution_service,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create ToolExecutionRequested event
        tool_requested_event = ToolExecutionRequested.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            tool_id="1",
            tool_name="validateData",
            tool_params={"data": "test"},
        )
        
        # Process event
        await worker.process_event(tool_requested_event)
        
        # Verify ToolExecutionCompleted event was emitted with failure
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ToolExecutionCompleted"
        assert event_data["payload"]["status"] == "failure"
        assert event_data["payload"]["error_message"] == "HTTP 500 error"



