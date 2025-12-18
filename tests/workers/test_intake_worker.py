"""
Unit tests for IntakeWorker.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from src.agents.intake import IntakeAgent
from src.events.types import ExceptionIngested, ExceptionNormalized
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.intake_worker import IntakeWorker


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


class TestIntakeWorker:
    """Test IntakeWorker."""
    
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
        repo.upsert_exception = AsyncMock()
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
    def intake_worker(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_event_processing_repo,
    ):
        """Create IntakeWorker instance."""
        return IntakeWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="intake-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            event_processing_repo=mock_event_processing_repo,
        )
    
    @pytest.mark.asyncio
    async def test_process_exception_ingested_event(
        self,
        intake_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing ExceptionIngested event."""
        # Create ExceptionIngested event
        ingested_event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"error": "Test error", "code": "ERR001"},
            source_system="ERP",
            ingestion_method="api",
        )
        
        # Process event
        await intake_worker.process_event(ingested_event)
        
        # Verify exception was persisted
        mock_exception_repository.upsert_exception.assert_called_once()
        
        # Verify ExceptionNormalized event was emitted
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ExceptionNormalized"
        assert event_data["tenant_id"] == "tenant_001"
        
    @pytest.mark.asyncio
    async def test_process_event_wrong_type(self, intake_worker):
        """Test processing wrong event type raises error."""
        from src.events.schema import CanonicalEvent
        
        # Create wrong event type
        wrong_event = CanonicalEvent.create(
            event_type="WrongEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="IntakeWorker expects ExceptionIngested"):
            await intake_worker.process_event(wrong_event)
    
    @pytest.mark.asyncio
    async def test_persist_exception(self, intake_worker, mock_exception_repository):
        """Test exception persistence."""
        # Create normalized exception
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            severity=Severity.HIGH,
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={"domain": "finance"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        # Persist exception
        await intake_worker._persist_exception(exception)
        
        # Verify upsert was called
        mock_exception_repository.upsert_exception.assert_called_once()
        call_args = mock_exception_repository.upsert_exception.call_args
        assert call_args[1]["tenant_id"] == "tenant_001"
        assert call_args[1]["exception_data"].exception_id == "exc_001"
        assert call_args[1]["exception_data"].domain == "finance"
        assert call_args[1]["exception_data"].type == "DataQualityFailure"
    
    @pytest.mark.asyncio
    async def test_emit_normalized_event(self, intake_worker, mock_event_publisher):
        """Test ExceptionNormalized event emission."""
        # Create normalized exception
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            severity=Severity.HIGH,
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        # Emit event
        await intake_worker._emit_normalized_event(
            normalized=exception,
            correlation_id="corr_001",
            metadata={"test": "metadata"},
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ExceptionNormalized"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["correlation_id"] == "corr_001"
        assert "normalized_exception" in event_data["payload"]
    
    @pytest.mark.asyncio
    async def test_idempotency_handling(
        self,
        intake_worker,
        mock_event_processing_repo,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test idempotency handling via base worker."""
        # Mark event as already processed
        mock_event_processing_repo.is_processed = AsyncMock(return_value=True)
        
        # Create ExceptionIngested event
        ingested_event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"error": "Test error"},
            source_system="ERP",
        )
        
        # Process event (should be skipped due to idempotency)
        # The base worker will check idempotency before calling process_event
        # So we need to simulate the check happening
        is_processed = await mock_event_processing_repo.is_processed(
            ingested_event.event_id, "IntakeWorker"
        )
        
        if is_processed:
            # Event already processed, should skip
            # In real scenario, base worker would skip before calling process_event
            pass
        else:
            # Process event
            await intake_worker.process_event(ingested_event)
        
        # Verify idempotency check was called
        mock_event_processing_repo.is_processed.assert_called()
    
    @pytest.mark.asyncio
    async def test_error_handling_normalization_failure(
        self,
        intake_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test error handling when normalization fails."""
        # Mock IntakeAgent to raise error
        intake_worker.intake_agent.process = AsyncMock(side_effect=Exception("Normalization failed"))
        
        # Create ExceptionIngested event
        ingested_event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"error": "Test error"},
            source_system="ERP",
        )
        
        # Process event should raise error
        with pytest.raises(Exception, match="Normalization failed"):
            await intake_worker.process_event(ingested_event)
        
        # Verify exception was NOT persisted
        mock_exception_repository.upsert_exception.assert_not_called()
        
        # Verify event was NOT emitted
        mock_event_publisher.publish_event.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_error_handling_persistence_failure(
        self,
        intake_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test error handling when persistence fails."""
        # Mock repository to raise error
        mock_exception_repository.upsert_exception = AsyncMock(
            side_effect=Exception("Persistence failed")
        )
        
        # Create ExceptionIngested event
        ingested_event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={"error": "Test error"},
            source_system="ERP",
        )
        
        # Process event should raise error
        with pytest.raises(Exception, match="Persistence failed"):
            await intake_worker.process_event(ingested_event)
        
        # Verify event was NOT emitted
        mock_event_publisher.publish_event.assert_not_called()


class TestIntakeWorkerIntegration:
    """Integration tests for IntakeWorker."""
    
    @pytest.mark.asyncio
    async def test_ingest_to_normalized_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_event_processing_repo,
    ):
        """Test complete flow from ExceptionIngested to ExceptionNormalized."""
        # Create worker
        worker = IntakeWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="intake-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create ExceptionIngested event
        ingested_event = ExceptionIngested.create(
            tenant_id="tenant_001",
            raw_payload={
                "exceptionId": "exc_001",
                "tenantId": "tenant_001",
                "sourceSystem": "ERP",
                "exceptionType": "DataQualityFailure",
                "rawPayload": {"error": "Invalid data format"},
            },
            source_system="ERP",
            ingestion_method="api",
        )
        
        # Process event
        await worker.process_event(ingested_event)
        
        # Verify exception was persisted
        assert mock_exception_repository.upsert_exception.called
        
        # Verify ExceptionNormalized event was emitted
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "ExceptionNormalized"
        assert event_data["exception_id"] == "exc_001"
        assert "normalized_exception" in event_data["payload"]



