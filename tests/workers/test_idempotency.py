"""
Tests for idempotency handling in AgentWorker.
"""

import asyncio
import json
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock, patch

from src.events.schema import CanonicalEvent
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.workers.base import AgentWorker


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


class TestWorker(AgentWorker):
    """Test worker implementation."""
    
    def __init__(self, broker: Broker, topics: list[str], group_id: str, event_processing_repo=None):
        """Initialize test worker."""
        super().__init__(broker, topics, group_id, event_processing_repo=event_processing_repo)
        self.processed_events = []
        self.should_fail = False
        
    async def process_event(self, event: CanonicalEvent) -> None:
        """Process event."""
        if self.should_fail:
            raise Exception("Processing failed")
        self.processed_events.append(event)


class TestIdempotencyHandling:
    """Test idempotency handling in workers."""
    
    @pytest.mark.asyncio
    async def test_duplicate_event_skipped(self):
        """Test duplicate events are skipped."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        
        # First call: not processed
        # Second call: already processed
        mock_repo.is_processed = AsyncMock(side_effect=[False, True])
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_completed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        # Process first time
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Process second time (duplicate)
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify event was only processed once
        assert len(worker.processed_events) == 1
        assert worker._messages_processed == 1
        
        # Verify idempotency check was called twice
        assert mock_repo.is_processed.call_count == 2
        
    @pytest.mark.asyncio
    async def test_event_marked_as_processing(self):
        """Test event is marked as processing."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        mock_repo.is_processed = AsyncMock(return_value=False)
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_completed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify mark_processing was called
        mock_repo.mark_processing.assert_called_once()
        call_args = mock_repo.mark_processing.call_args
        assert call_args[1]["event_id"] == event.event_id
        assert call_args[1]["worker_type"] == "TestWorker"
        assert call_args[1]["tenant_id"] == "tenant_001"
        assert call_args[1]["exception_id"] == "exc_001"
        
    @pytest.mark.asyncio
    async def test_event_marked_as_completed(self):
        """Test event is marked as completed after successful processing."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        mock_repo.is_processed = AsyncMock(return_value=False)
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_completed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify mark_completed was called
        mock_repo.mark_completed.assert_called_once_with(
            event.event_id, "TestWorker"
        )
        
    @pytest.mark.asyncio
    async def test_event_marked_as_failed_on_error(self):
        """Test event is marked as failed when processing fails."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        mock_repo.is_processed = AsyncMock(return_value=False)
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_failed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        worker.should_fail = True
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify mark_failed was called
        mock_repo.mark_failed.assert_called_once()
        call_args = mock_repo.mark_failed.call_args
        assert call_args[0][0] == event.event_id
        assert call_args[0][1] == "TestWorker"
        assert "Processing failed" in call_args[0][2]
        
        # Verify error was recorded
        assert worker._errors_count == 1
        assert worker._last_error is not None


class TestStatusTransitions:
    """Test status transitions in event processing."""
    
    @pytest.mark.asyncio
    async def test_status_transition_processing_to_completed(self):
        """Test status transition from PROCESSING to COMPLETED."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        mock_repo.is_processed = AsyncMock(return_value=False)
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_completed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify status transitions: processing -> completed
        assert mock_repo.mark_processing.called
        assert mock_repo.mark_completed.called
        # mark_processing should be called before mark_completed
        assert mock_repo.mark_processing.call_count == 1
        assert mock_repo.mark_completed.call_count == 1
        
    @pytest.mark.asyncio
    async def test_status_transition_processing_to_failed(self):
        """Test status transition from PROCESSING to FAILED."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        mock_repo.is_processed = AsyncMock(return_value=False)
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_failed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        
        # Override process_event to fail
        async def failing_process_event(event: CanonicalEvent) -> None:
            raise Exception("Processing failed")
        
        worker.process_event = failing_process_event
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify status transitions: processing -> failed
        assert mock_repo.mark_processing.called
        assert mock_repo.mark_failed.called
        # mark_failed should be called, mark_completed should NOT be called
        assert mock_repo.mark_completed.call_count == 0
        
    @pytest.mark.asyncio
    async def test_duplicate_event_not_marked_processing(self):
        """Test duplicate events are not marked as processing."""
        broker = MockBroker()
        mock_repo = AsyncMock(spec=EventProcessingRepository)
        
        # First call: not processed, second call: already processed
        mock_repo.is_processed = AsyncMock(side_effect=[False, True])
        mock_repo.mark_processing = AsyncMock()
        mock_repo.mark_completed = AsyncMock()
        
        worker = TestWorker(
            broker=broker,
            topics=["test-topic"],
            group_id="test-group",
            event_processing_repo=mock_repo,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        event_json = event.to_json()
        
        # Process first time
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Process duplicate (should be skipped)
        worker._handle_message("test-topic", "key1", event_json.encode("utf-8"))
        
        # Verify mark_processing was only called once (for first event)
        assert mock_repo.mark_processing.call_count == 1
        # mark_completed should only be called once (for first event)
        assert mock_repo.mark_completed.call_count == 1

