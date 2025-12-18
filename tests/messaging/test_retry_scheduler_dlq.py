"""
Integration tests for retry scheduler with DLQ.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, Mock

from src.events.schema import CanonicalEvent
from src.events.types import DeadLettered
from src.infrastructure.repositories.dead_letter_repository import (
    DeadLetterEventRepository,
)
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.messaging.retry_policy import RetryPolicy, RetryPolicyRegistry
from src.messaging.retry_scheduler import RetryScheduler


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


class TestRetrySchedulerDLQ:
    """Test RetryScheduler DLQ integration."""
    
    @pytest.fixture
    def mock_event_processing_repo(self):
        """Create mock event processing repository."""
        repo = AsyncMock(spec=EventProcessingRepository)
        repo.session = AsyncMock()
        repo.mark_failed = AsyncMock()
        repo.get_processing_status = AsyncMock(return_value=None)
        return repo
    
    @pytest.fixture
    def mock_dlq_repository(self):
        """Create mock DLQ repository."""
        repo = AsyncMock(spec=DeadLetterEventRepository)
        repo.create_dlq_entry = AsyncMock()
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
        """Create retry policy registry with max 2 retries."""
        registry = RetryPolicyRegistry()
        registry.set_policy(
            "TestEvent",
            RetryPolicy(
                max_retries=2,
                initial_delay_seconds=0.1,  # Short delay for testing
                jitter=False,
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
        mock_dlq_repository,
    ):
        """Create RetryScheduler instance with DLQ."""
        return RetryScheduler(
            event_processing_repo=mock_event_processing_repo,
            event_publisher=mock_event_publisher,
            broker=mock_broker,
            retry_policy_registry=retry_policy_registry,
            dlq_repository=mock_dlq_repository,
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
    async def test_move_to_dlq_on_max_retries(
        self,
        retry_scheduler,
        test_event,
        mock_event_processing_repo,
        mock_dlq_repository,
        mock_event_publisher,
    ):
        """Test that event is moved to DLQ when max retries exceeded."""
        # Mock processing record at max retries
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = Mock()
        mock_processing.status.value = "failed"
        mock_processing.error_message = "Error (retry 2/2)"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        # Try to schedule retry (should move to DLQ)
        scheduled = await retry_scheduler.schedule_retry(
            event=test_event,
            worker_type="TestWorker",
            error_message="Max retries reached",
        )
        
        # Verify retry was NOT scheduled
        assert scheduled is False
        
        # Verify DLQ entry was created
        mock_dlq_repository.create_dlq_entry.assert_called_once()
        call_args = mock_dlq_repository.create_dlq_entry.call_args
        assert call_args[1]["event_id"] == test_event.event_id
        assert call_args[1]["tenant_id"] == test_event.tenant_id
        assert call_args[1]["retry_count"] == 2
        assert call_args[1]["worker_type"] == "TestWorker"
        
        # Verify DeadLettered event was emitted
        mock_event_publisher.publish_event.assert_called()
        call_args_list = mock_event_publisher.publish_event.call_args_list
        dead_lettered_called = False
        for call in call_args_list:
            event_data = call[1]["event"]
            if event_data.get("event_type") == "DeadLettered":
                dead_lettered_called = True
                assert event_data["payload"]["original_event_id"] == test_event.event_id
                assert event_data["payload"]["retry_count"] == 2
                break
        assert dead_lettered_called
    
    @pytest.mark.asyncio
    async def test_dlq_without_repository(
        self,
        mock_event_processing_repo,
        mock_event_publisher,
        mock_broker,
        retry_policy_registry,
        test_event,
    ):
        """Test DLQ handling when repository is not configured."""
        # Create scheduler without DLQ repository
        scheduler = RetryScheduler(
            event_processing_repo=mock_event_processing_repo,
            event_publisher=mock_event_publisher,
            broker=mock_broker,
            retry_policy_registry=retry_policy_registry,
            dlq_repository=None,  # No DLQ repository
        )
        
        # Mock processing record at max retries
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = Mock()
        mock_processing.status.value = "failed"
        mock_processing.error_message = "Error (retry 2/2)"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        # Try to schedule retry (should still emit DeadLettered event)
        scheduled = await scheduler.schedule_retry(
            event=test_event,
            worker_type="TestWorker",
            error_message="Max retries reached",
        )
        
        assert scheduled is False
        
        # Verify DeadLettered event was still emitted
        mock_event_publisher.publish_event.assert_called()
        call_args_list = mock_event_publisher.publish_event.call_args_list
        dead_lettered_called = False
        for call in call_args_list:
            event_data = call[1]["event"]
            if event_data.get("event_type") == "DeadLettered":
                dead_lettered_called = True
                break
        assert dead_lettered_called


class TestRetrySchedulerDLQIntegration:
    """Integration tests for fail->retry->DLQ flow."""
    
    @pytest.mark.asyncio
    async def test_fail_retry_dlq_flow(
        self,
        mock_event_processing_repo,
        mock_event_publisher,
        mock_broker,
        mock_dlq_repository,
    ):
        """Test complete flow: fail -> retry -> DLQ."""
        # Create registry with max 2 retries
        registry = RetryPolicyRegistry()
        registry.set_policy(
            "TestEvent",
            RetryPolicy(
                max_retries=2,
                initial_delay_seconds=0.1,
                jitter=False,
            ),
        )
        
        scheduler = RetryScheduler(
            event_processing_repo=mock_event_processing_repo,
            event_publisher=mock_event_publisher,
            broker=mock_broker,
            retry_policy_registry=registry,
            dlq_repository=mock_dlq_repository,
        )
        
        event = CanonicalEvent.create(
            event_type="TestEvent",
            tenant_id="tenant_001",
            exception_id="exc_001",
            payload={"data": "test"},
        )
        
        # Simulate retry attempts
        from sqlalchemy import select
        from src.infrastructure.db.models import EventProcessing
        
        # Attempt 1: First failure (retry_count = 0)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_event_processing_repo.session.execute = AsyncMock(return_value=mock_result)
        
        scheduled1 = await scheduler.schedule_retry(
            event=event,
            worker_type="TestWorker",
            error_message="First failure",
        )
        assert scheduled1 is True  # Retry scheduled
        
        # Attempt 2: Second failure (retry_count = 1)
        mock_processing1 = Mock(spec=EventProcessing)
        mock_processing1.status = Mock()
        mock_processing1.status.value = "failed"
        mock_processing1.error_message = "Error (retry 1/2)"
        
        mock_result.scalar_one_or_none.return_value = mock_processing1
        scheduled2 = await scheduler.schedule_retry(
            event=event,
            worker_type="TestWorker",
            error_message="Second failure",
        )
        assert scheduled2 is True  # Retry scheduled
        
        # Attempt 3: Third failure (retry_count = 2, max exceeded)
        mock_processing2 = Mock(spec=EventProcessing)
        mock_processing2.status = Mock()
        mock_processing2.status.value = "failed"
        mock_processing2.error_message = "Error (retry 2/2)"
        
        mock_result.scalar_one_or_none.return_value = mock_processing2
        scheduled3 = await scheduler.schedule_retry(
            event=event,
            worker_type="TestWorker",
            error_message="Third failure - max retries",
        )
        assert scheduled3 is False  # Moved to DLQ
        
        # Verify DLQ entry was created
        mock_dlq_repository.create_dlq_entry.assert_called_once()
        call_args = mock_dlq_repository.create_dlq_entry.call_args
        assert call_args[1]["retry_count"] == 2
        
        # Verify DeadLettered event was emitted
        call_args_list = mock_event_publisher.publish_event.call_args_list
        dead_lettered_events = [
            call[1]["event"]
            for call in call_args_list
            if call[1]["event"].get("event_type") == "DeadLettered"
        ]
        assert len(dead_lettered_events) == 1
        assert dead_lettered_events[0]["payload"]["retry_count"] == 2



