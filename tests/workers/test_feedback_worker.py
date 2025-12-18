"""
Unit tests for FeedbackWorker.
"""

import pytest
from unittest.mock import AsyncMock, Mock
from datetime import datetime, timezone

from src.events.schema import CanonicalEvent
from src.events.types import FeedbackCaptured
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.exception_record import ResolutionStatus
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.feedback_worker import FeedbackWorker


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


class TestFeedbackWorker:
    """Test FeedbackWorker."""
    
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
    def mock_exception_repository(self):
        """Create mock exception repository."""
        repo = AsyncMock(spec=ExceptionRepository)
        
        # Mock exception database model
        mock_exception = Mock()
        mock_exception.exception_id = "exc_001"
        mock_exception.tenant_id = "tenant_001"
        mock_exception.source_system = "ERP"
        mock_exception.type = "DataQualityFailure"
        mock_exception.severity = Mock()
        mock_exception.severity.value = "HIGH"
        mock_exception.status = Mock()
        mock_exception.status.value = "RESOLVED"
        mock_exception.created_at = datetime.now(timezone.utc)
        mock_exception.updated_at = datetime.now(timezone.utc)
        
        repo.get_by_id = AsyncMock(return_value=mock_exception)
        return repo
    
    @pytest.fixture
    def mock_event_processing_repo(self):
        """Create mock event processing repository."""
        repo = AsyncMock(spec=EventProcessingRepository)
        repo.is_processed = AsyncMock(return_value=False)
        repo.mark_processing = AsyncMock()
        repo.mark_completed = AsyncMock()
        return repo
    
    @pytest.fixture
    def feedback_worker(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_event_processing_repo,
    ):
        """Create FeedbackWorker instance."""
        return FeedbackWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="feedback-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            event_processing_repo=mock_event_processing_repo,
        )
    
    @pytest.mark.asyncio
    async def test_process_playbook_completed_event(
        self,
        feedback_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing PlaybookCompleted event."""
        # Create PlaybookCompleted event
        playbook_completed_event = CanonicalEvent.create(
            event_type="PlaybookCompleted",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={
                "playbook_id": "PB01",
                "total_steps": 5,
                "completed_steps": 5,
                "execution_time_seconds": 120.5,
                "status": "success",
            },
        )
        
        # Process event
        await feedback_worker.process_event(playbook_completed_event)
        
        # Verify FeedbackCaptured event was emitted
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "FeedbackCaptured"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["feedback_type"] == "positive"
        assert "feedback_data" in event_data["payload"]
        assert "metrics" in event_data["payload"]["feedback_data"]
        assert event_data["payload"]["feedback_data"]["metrics"]["playbook_id"] == "PB01"
    
    @pytest.mark.asyncio
    async def test_process_exception_resolved_event(
        self,
        feedback_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing ExceptionResolved event."""
        # Create ExceptionResolved event
        exception_resolved_event = CanonicalEvent.create(
            event_type="ExceptionResolved",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={
                "resolution_method": "playbook",
                "resolution_time_seconds": 300.0,
                "auto_resolved": True,
            },
        )
        
        # Process event
        await feedback_worker.process_event(exception_resolved_event)
        
        # Verify FeedbackCaptured event was emitted
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "FeedbackCaptured"
        assert event_data["payload"]["feedback_type"] == "positive"  # RESOLVED status
        assert "metrics" in event_data["payload"]["feedback_data"]
        assert event_data["payload"]["feedback_data"]["metrics"]["resolution_method"] == "playbook"
    
    @pytest.mark.asyncio
    async def test_process_tool_execution_completed_event(
        self,
        feedback_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing ToolExecutionCompleted event."""
        # Create ToolExecutionCompleted event
        tool_completed_event = CanonicalEvent.create(
            event_type="ToolExecutionCompleted",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={
                "tool_id": "1",
                "execution_id": "exec_001",
                "status": "success",
                "result": {"data": "test"},
            },
        )
        
        # Process event
        await feedback_worker.process_event(tool_completed_event)
        
        # Verify FeedbackCaptured event was emitted
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "FeedbackCaptured"
        assert event_data["payload"]["feedback_type"] == "positive"  # success status
        assert "metrics" in event_data["payload"]["feedback_data"]
        assert event_data["payload"]["feedback_data"]["metrics"]["tool_id"] == "1"
    
    @pytest.mark.asyncio
    async def test_process_event_wrong_type(self, feedback_worker):
        """Test processing wrong event type raises error."""
        # Create wrong event type
        wrong_event = CanonicalEvent.create(
            event_type="WrongEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="FeedbackWorker expects completion events"):
            await feedback_worker.process_event(wrong_event)
    
    @pytest.mark.asyncio
    async def test_compute_metrics_playbook_completed(
        self,
        feedback_worker,
        mock_exception_repository,
    ):
        """Test metrics computation for PlaybookCompleted event."""
        # Create event
        event = CanonicalEvent.create(
            event_type="PlaybookCompleted",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={
                "playbook_id": "PB01",
                "total_steps": 5,
                "completed_steps": 5,
                "execution_time_seconds": 120.5,
            },
        )
        
        # Get exception
        exception_db = await mock_exception_repository.get_by_id("exc_001", "tenant_001")
        
        # Compute metrics
        metrics = await feedback_worker._compute_metrics(event, exception_db)
        
        # Verify metrics
        assert metrics["playbook_id"] == "PB01"
        assert metrics["total_steps"] == 5
        assert metrics["completed_steps"] == 5
        assert metrics["execution_time_seconds"] == 120.5
        assert metrics["exception_type"] == "DataQualityFailure"
        assert "total_processing_time_seconds" in metrics
    
    @pytest.mark.asyncio
    async def test_determine_feedback_type(
        self,
        feedback_worker,
    ):
        """Test feedback type determination."""
        # Test RESOLVED status -> positive
        event = CanonicalEvent.create(
            event_type="ExceptionResolved",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={},
        )
        feedback_type = feedback_worker._determine_feedback_type(
            event, ResolutionStatus.RESOLVED
        )
        assert feedback_type == "positive"
        
        # Test ESCALATED status -> negative
        feedback_type = feedback_worker._determine_feedback_type(
            event, ResolutionStatus.ESCALATED
        )
        assert feedback_type == "negative"
        
        # Test PlaybookCompleted with success -> positive
        playbook_event = CanonicalEvent.create(
            event_type="PlaybookCompleted",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={"status": "success"},
        )
        feedback_type = feedback_worker._determine_feedback_type(
            playbook_event, None
        )
        assert feedback_type == "positive"
        
        # Test PlaybookCompleted with failure -> negative
        playbook_event_fail = CanonicalEvent.create(
            event_type="PlaybookCompleted",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={"status": "failed"},
        )
        feedback_type = feedback_worker._determine_feedback_type(
            playbook_event_fail, None
        )
        assert feedback_type == "negative"
    
    @pytest.mark.asyncio
    async def test_emit_feedback_captured_event(
        self,
        feedback_worker,
        mock_event_publisher,
    ):
        """Test FeedbackCaptured event emission."""
        # Emit event
        await feedback_worker._emit_feedback_captured_event(
            tenant_id="tenant_001",
            exception_id="exc_001",
            feedback_type="positive",
            feedback_data={"metrics": {"test": "data"}},
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "FeedbackCaptured"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["feedback_type"] == "positive"
        assert event_data["payload"]["captured_by"] == "FeedbackWorker"


class TestFeedbackWorkerIntegration:
    """Integration tests for FeedbackWorker."""
    
    @pytest.mark.asyncio
    async def test_completion_to_feedback_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_event_processing_repo,
    ):
        """Test complete flow from completion event to FeedbackCaptured."""
        # Create worker
        worker = FeedbackWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="feedback-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create PlaybookCompleted event
        playbook_completed_event = CanonicalEvent.create(
            event_type="PlaybookCompleted",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={
                "playbook_id": "PB01",
                "total_steps": 5,
                "completed_steps": 5,
                "execution_time_seconds": 120.5,
                "status": "success",
            },
        )
        
        # Process event
        await worker.process_event(playbook_completed_event)
        
        # Verify FeedbackCaptured event was emitted
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "FeedbackCaptured"
        assert event_data["exception_id"] == "exc_001"
        assert "feedback_data" in event_data["payload"]
        assert "metrics" in event_data["payload"]["feedback_data"]
        assert event_data["payload"]["feedback_data"]["metrics"]["playbook_id"] == "PB01"
    
    @pytest.mark.asyncio
    async def test_exception_resolved_to_feedback_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_event_processing_repo,
    ):
        """Test complete flow from ExceptionResolved to FeedbackCaptured."""
        # Create worker
        worker = FeedbackWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="feedback-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create ExceptionResolved event
        exception_resolved_event = CanonicalEvent.create(
            event_type="ExceptionResolved",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={
                "resolution_method": "playbook",
                "resolution_time_seconds": 300.0,
                "auto_resolved": True,
            },
        )
        
        # Process event
        await worker.process_event(exception_resolved_event)
        
        # Verify FeedbackCaptured event was emitted
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "FeedbackCaptured"
        assert event_data["payload"]["feedback_type"] == "positive"
        assert "metrics" in event_data["payload"]["feedback_data"]



