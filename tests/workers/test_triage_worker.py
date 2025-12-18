"""
Unit tests for TriageWorker.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from src.agents.triage import TriageAgent
from src.events.types import ExceptionNormalized, TriageCompleted, TriageRequested
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.triage_worker import TriageWorker


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


class TestTriageWorker:
    """Test TriageWorker."""
    
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
        repo.update_exception = AsyncMock()
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
    def mock_domain_pack(self):
        """Create mock domain pack."""
        return Mock(spec=DomainPack)
    
    @pytest.fixture
    def triage_worker(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_domain_pack,
        mock_event_processing_repo,
    ):
        """Create TriageWorker instance."""
        return TriageWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="triage-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            domain_pack=mock_domain_pack,
            event_processing_repo=mock_event_processing_repo,
        )
    
    @pytest.mark.asyncio
    async def test_process_exception_normalized_event(
        self,
        triage_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing ExceptionNormalized event."""
        # Create ExceptionNormalized event
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            severity=Severity.MEDIUM,
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        normalized_event = ExceptionNormalized.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            normalized_exception=exception.model_dump(by_alias=True),
        )
        
        # Mock TriageAgent to return decision
        decision = AgentDecision(
            decision="Classified as DataQualityFailure with HIGH severity",
            confidence=0.85,
            evidence=["Rule matched: invalid_format", "Severity: HIGH"],
            nextStep="ProceedToPolicy",
        )
        triage_worker.triage_agent.process = AsyncMock(return_value=decision)
        
        # Process event
        await triage_worker.process_event(normalized_event)
        
        # Verify TriageRequested event was emitted
        assert mock_event_publisher.publish_event.call_count >= 1
        
        # Verify exception was updated
        mock_exception_repository.update_exception.assert_called_once()
        
        # Verify TriageCompleted event was emitted
        # Should have 2 calls: TriageRequested + TriageCompleted
        assert mock_event_publisher.publish_event.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_process_event_wrong_type(self, triage_worker):
        """Test processing wrong event type raises error."""
        from src.events.schema import CanonicalEvent
        
        # Create wrong event type
        wrong_event = CanonicalEvent.create(
            event_type="WrongEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="TriageWorker expects ExceptionNormalized"):
            await triage_worker.process_event(wrong_event)
    
    @pytest.mark.asyncio
    async def test_emit_triage_requested_event(
        self,
        triage_worker,
        mock_event_publisher,
    ):
        """Test TriageRequested event emission."""
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        # Emit event
        await triage_worker._emit_triage_requested_event(
            exception=exception,
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "TriageRequested"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["requested_by"] == "TriageWorker"
    
    @pytest.mark.asyncio
    async def test_update_exception_triage(
        self,
        triage_worker,
        mock_exception_repository,
    ):
        """Test exception triage update."""
        decision = AgentDecision(
            decision="Classified as DataQualityFailure with HIGH severity",
            confidence=0.85,
            evidence=["Rule matched: invalid_format", "Severity: HIGH", "Type: DataQualityFailure"],
            nextStep="ProceedToPolicy",
        )
        
        # Update exception
        await triage_worker._update_exception_triage(
            exception_id="exc_001",
            tenant_id="tenant_001",
            decision=decision,
        )
        
        # Verify update was called
        mock_exception_repository.update_exception.assert_called_once()
        call_args = mock_exception_repository.update_exception.call_args
        assert call_args[1]["tenant_id"] == "tenant_001"
        assert call_args[1]["exception_id"] == "exc_001"
        updates = call_args[1]["updates"]
        assert updates.severity is not None
        # Severity should be HIGH based on decision string
    
    @pytest.mark.asyncio
    async def test_emit_triage_completed_event(
        self,
        triage_worker,
        mock_event_publisher,
    ):
        """Test TriageCompleted event emission."""
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        decision = AgentDecision(
            decision="Classified as DataQualityFailure with HIGH severity",
            confidence=0.85,
            evidence=["Rule matched: invalid_format"],
            nextStep="ProceedToPolicy",
        )
        
        # Emit event
        await triage_worker._emit_triage_completed_event(
            exception=exception,
            decision=decision,
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "TriageCompleted"
        assert event_data["exception_id"] == "exc_001"
        assert "triage_result" in event_data["payload"]
        assert "severity" in event_data["payload"]
    
    @pytest.mark.asyncio
    async def test_error_handling_triage_failure(
        self,
        triage_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test error handling when triage fails."""
        # Mock TriageAgent to raise error
        triage_worker.triage_agent.process = AsyncMock(side_effect=Exception("Triage failed"))
        
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        normalized_event = ExceptionNormalized.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            normalized_exception=exception.model_dump(by_alias=True),
        )
        
        # Process event should raise error
        with pytest.raises(Exception, match="Triage failed"):
            await triage_worker.process_event(normalized_event)
        
        # Verify exception was NOT updated
        mock_exception_repository.update_exception.assert_not_called()
        
        # Verify TriageCompleted was NOT emitted (but TriageRequested might have been)
        # Check that update_exception was not called, which means we didn't get to completion


class TestTriageWorkerIntegration:
    """Integration tests for TriageWorker."""
    
    @pytest.mark.asyncio
    async def test_normalized_to_triage_completed_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_domain_pack,
        mock_event_processing_repo,
    ):
        """Test complete flow from ExceptionNormalized to TriageCompleted."""
        # Create worker
        worker = TriageWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="triage-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            domain_pack=mock_domain_pack,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create ExceptionNormalized event
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="DataQualityFailure",
            severity=Severity.MEDIUM,
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Invalid data format"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        normalized_event = ExceptionNormalized.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            normalized_exception=exception.model_dump(by_alias=True),
        )
        
        # Mock TriageAgent
        decision = AgentDecision(
            decision="Classified as DataQualityFailure with HIGH severity",
            confidence=0.85,
            evidence=["Rule matched: invalid_format", "Severity: HIGH"],
            nextStep="ProceedToPolicy",
        )
        worker.triage_agent.process = AsyncMock(return_value=decision)
        
        # Process event
        await worker.process_event(normalized_event)
        
        # Verify TriageRequested event was emitted
        assert mock_event_publisher.publish_event.call_count >= 1
        
        # Verify exception was updated with triage results
        assert mock_exception_repository.update_exception.called
        call_args = mock_exception_repository.update_exception.call_args
        updates = call_args[1]["updates"]
        assert updates.severity is not None
        
        # Verify TriageCompleted event was emitted
        assert mock_event_publisher.publish_event.call_count >= 2
        # Check last call was TriageCompleted
        last_call = mock_event_publisher.publish_event.call_args_list[-1]
        event_data = last_call[1]["event"]
        assert event_data["event_type"] == "TriageCompleted"
        assert event_data["exception_id"] == "exc_001"



