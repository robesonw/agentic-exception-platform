"""
Unit tests for retry scheduler.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timezone

from src.events.schema import CanonicalEvent
from src.events.types import RetryScheduled
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.messaging.retry_policy import RetryPolicy, RetryPolicyRegistry
from src.messaging.retry_scheduler import RetryScheduler, RetrySchedulerError


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


class TestRetryScheduler:
    """Test RetryScheduler."""
    
    @pytest.fixture
    def mock_event_processing_repo(self):
        """Create mock event processing repository."""
        repo = AsyncMock(spec=EventProcessingRepository)
        repo.session = AsyncMock()
        repo.mark_failed = AsyncMock()
        repo.get_processing_status = AsyncMock(return_value=None)
        return repo
    
    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        publisher = AsyncMock(spec=EventPublisherService)
        publisher.publish_event = AsyncMock()
        return publisher
    
    @pytest.fixture
    def mock_broker(self):
        """Create mock broker."""
        return MockBroker()
    
    @pytest.fixture
    def retry_policy_registry(self):
        """Create retry policy registry with test policies."""
        registry = RetryPolicyRegistry()
        # Set a simple policy for testing
        registry.set_policy(
            "TestEvent",
            RetryPolicy(
                max_retries=3,
                initial_delay_seconds=1.0,
                backoff_multiplier=2.0,
                max_delay_seconds=100.0,
                jitter=False,  # Disable jitter for predictable tests
            ),
        )
        return registry
    
    @pytest.fixture
    def retry_scheduler(
        self,
        mock_event_processing_repo,
        mock_event_publisher,
        mock_broker,
        retry_policy_registry,
    ):
        """Create RetryScheduler instance."""
        return RetryScheduler(
            event_processing_repo=mock_event_processing_repo,
            event_publisher=mock_event_publisher,
            broker=mock_broker,
            retry_policy_registry=retry_policy_registry,
        )
    
    @pytest.fixture
    def test_event(self):
        """Create test event."""
        return CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={"data": "test"},
        )
    
    @pytest.mark.asyncio
    async def test_schedule_retry_first_attempt(
        self,
        retry_scheduler,
        test_event,
        mock_event_processing_repo,
        mock_event_publisher,
    ):
        """Test scheduling first retry attempt."""
        # Mock no existing processing record
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        # Schedule retry
        scheduled = await retry_scheduler.schedule_retry(
            event=test_event,
            worker_type="TestWorker",
            error_message="Test error",
        )
        
        # Verify retry was scheduled
        assert scheduled is True
        
        # Verify mark_failed was called
        mock_event_processing_repo.mark_failed.assert_called_once()
        
        # Verify RetryScheduled event was emitted
        mock_event_publisher.publish_event.assert_called()
        call_args = mock_event_publisher.publish_event.call_args_list
        # Find RetryScheduled event
        retry_event_called = False
        for call in call_args:
            event_data = call[1]["event"]
            if event_data.get("event_type") == "RetryScheduled":
                retry_event_called = True
                assert event_data["payload"]["retry_count"] == 1
                assert event_data["payload"]["retry_delay_seconds"] == 1.0
                break
        assert retry_event_called
    
    @pytest.mark.asyncio
    async def test_schedule_retry_exponential_backoff(
        self,
        retry_scheduler,
        test_event,
        mock_event_processing_repo,
        mock_event_publisher,
    ):
        """Test exponential backoff in retry delays."""
        # Mock existing processing record with retry count 1
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing, EventProcessingStatus
        
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = Mock()
        mock_processing.status.value = "failed"
        mock_processing.error_message = "Error (retry 1/3)"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        # Schedule retry (attempt 2)
        scheduled = await retry_scheduler.schedule_retry(
            event=test_event,
            worker_type="TestWorker",
            error_message="Test error",
        )
        
        assert scheduled is True
        
        # Verify RetryScheduled event has correct delay (2.0 for attempt 2)
        call_args = mock_event_publisher.publish_event.call_args_list
        for call in call_args:
            event_data = call[1]["event"]
            if event_data.get("event_type") == "RetryScheduled":
                assert event_data["payload"]["retry_count"] == 2
                assert event_data["payload"]["retry_delay_seconds"] == 2.0
                break
    
    @pytest.mark.asyncio
    async def test_schedule_retry_max_retries_exceeded(
        self,
        retry_scheduler,
        test_event,
        mock_event_processing_repo,
    ):
        """Test that retry is not scheduled when max retries exceeded."""
        # Mock existing processing record with retry count at max
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = Mock()
        mock_processing.status.value = "failed"
        mock_processing.error_message = "Error (retry 3/3)"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        # Schedule retry (should fail due to max retries)
        scheduled = await retry_scheduler.schedule_retry(
            event=test_event,
            worker_type="TestWorker",
            error_message="Test error",
        )
        
        # Verify retry was NOT scheduled
        assert scheduled is False
        
        # Verify mark_failed was NOT called (already at max)
        mock_event_processing_repo.mark_failed.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_get_retry_count_no_record(self, retry_scheduler):
        """Test getting retry count when no record exists."""
        # Mock no existing record
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        retry_scheduler.event_processing_repo.session.execute = AsyncMock(
            return_value=mock_result
        )
        
        retry_count = await retry_scheduler._get_retry_count("event_001", "TestWorker")
        
        assert retry_count == 0
    
    @pytest.mark.asyncio
    async def test_get_retry_count_from_error_message(self, retry_scheduler):
        """Test extracting retry count from error message."""
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = Mock()
        mock_processing.status.value = "failed"
        mock_processing.error_message = "Error (retry 2/3)"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        retry_scheduler.event_processing_repo.session.execute = AsyncMock(
            return_value=mock_result
        )
        
        retry_count = await retry_scheduler._get_retry_count("event_001", "TestWorker")
        
        assert retry_count == 2
    
    @pytest.mark.asyncio
    async def test_emit_retry_scheduled_event(
        self,
        retry_scheduler,
        test_event,
        mock_event_publisher,
    ):
        """Test RetryScheduled event emission."""
        await retry_scheduler._emit_retry_scheduled_event(
            event=test_event,
            worker_type="TestWorker",
            retry_count=1,
            delay_seconds=2.0,
            error_message="Test error",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "RetryScheduled"
        assert event_data["payload"]["retry_count"] == 1
        assert event_data["payload"]["retry_delay_seconds"] == 2.0
        assert event_data["payload"]["original_event_id"] == test_event.event_id
    
    @pytest.mark.asyncio
    async def test_schedule_republish(
        self,
        retry_scheduler,
        test_event,
        mock_event_publisher,
    ):
        """Test scheduling event re-publish after delay."""
        # Use a very short delay for testing
        await retry_scheduler._schedule_republish(
            event=test_event,
            worker_type="TestWorker",
            delay_seconds=0.1,  # 100ms for fast test
        )
        
        # Wait for re-publish
        await asyncio.sleep(0.2)
        
        # Verify event was re-published
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_id"] == test_event.event_id


class TestRetrySchedulerIntegration:
    """Integration tests for retry scheduler."""
    
    @pytest.mark.asyncio
    async def test_retry_backoff_sequence(
        self,
        mock_event_processing_repo,
        mock_event_publisher,
        mock_broker,
    ):
        """Test exponential backoff sequence across multiple retries."""
        # Create registry with known policy
        registry = RetryPolicyRegistry()
        registry.set_policy(
            "TestEvent",
            RetryPolicy(
                max_retries=3,
                initial_delay_seconds=1.0,
                backoff_multiplier=2.0,
                max_delay_seconds=100.0,
                jitter=False,
            ),
        )
        
        scheduler = RetryScheduler(
            event_processing_repo=mock_event_processing_repo,
            event_publisher=mock_event_publisher,
            broker=mock_broker,
            retry_policy_registry=registry,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={},
        )
        
        # Mock retry count progression
        from src.infrastructure.db.models import EventProcessing
        
        retry_counts = [0, 1, 2]
        delays_expected = [1.0, 2.0, 4.0]
        
        for attempt, (retry_count, expected_delay) in enumerate(
            zip(retry_counts, delays_expected), start=1
        ):
            # Mock processing record
            mock_processing = Mock(spec=EventProcessing)
            mock_processing.status = Mock()
            mock_processing.status.value = "failed" if retry_count > 0 else "processing"
            mock_processing.error_message = (
                f"Error (retry {retry_count}/3)" if retry_count > 0 else None
            )
            
            mock_result = Mock()
            mock_result.scalar_one_or_none.return_value = (
                mock_processing if retry_count > 0 else None
            )
            mock_event_processing_repo.session.execute = AsyncMock(
                return_value=mock_result
            )
            
            # Schedule retry
            scheduled = await scheduler.schedule_retry(
                event=event,
                worker_type="TestWorker",
                error_message=f"Attempt {attempt} failed",
            )
            
            assert scheduled is True
            
            # Verify delay in RetryScheduled event
            call_args = mock_event_publisher.publish_event.call_args_list
            retry_event = None
            for call in call_args:
                event_data = call[1]["event"]
                if event_data.get("event_type") == "RetryScheduled":
                    if event_data["payload"]["retry_count"] == attempt:
                        retry_event = event_data
                        break
            
            assert retry_event is not None
            assert retry_event["payload"]["retry_delay_seconds"] == expected_delay
    
    @pytest.mark.asyncio
    async def test_max_retries_enforcement(
        self,
        mock_event_processing_repo,
        mock_event_publisher,
        mock_broker,
    ):
        """Test that max retries are enforced."""
        registry = RetryPolicyRegistry()
        registry.set_policy(
            "TestEvent",
            RetryPolicy(max_retries=2, initial_delay_seconds=1.0, jitter=False),
        )
        
        scheduler = RetryScheduler(
            event_processing_repo=mock_event_processing_repo,
            event_publisher=mock_event_publisher,
            broker=mock_broker,
            retry_policy_registry=registry,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={},
        )
        
        # Mock processing record at max retries
        from src.infrastructure.db.models import EventProcessing
        
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = Mock()
        mock_processing.status.value = "failed"
        mock_processing.error_message = "Error (retry 2/2)"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        # Try to schedule retry (should fail)
        scheduled = await scheduler.schedule_retry(
            event=event,
            worker_type="TestWorker",
            error_message="Max retries reached",
        )
        
        assert scheduled is False



