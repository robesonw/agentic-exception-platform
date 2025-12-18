"""
Unit tests for PlaybookWorker.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from src.events.types import PlaybookMatched, StepExecutionRequested
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.domain_pack import DomainPack, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.playbooks.manager import PlaybookManager
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.playbook_worker import PlaybookWorker


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


class TestPlaybookWorker:
    """Test PlaybookWorker."""
    
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
        mock_exception.status.value = "OPEN"
        mock_exception.domain = "finance"
        mock_exception.created_at = "2024-01-15T10:30:00Z"
        mock_exception.current_step = 1  # Start at step 1
        mock_exception.current_playbook_id = None
        
        repo.get_by_id = AsyncMock(return_value=mock_exception)
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
        """Create mock domain pack with playbook."""
        pack = Mock(spec=DomainPack)
        
        # Create mock playbook with steps
        step1 = PlaybookStep(
            action="notify",
            parameters={"recipient": "team@example.com"},
            description="Notify team",
        )
        step2 = PlaybookStep(
            action="call_tool",
            parameters={"tool": "validateData", "params": {}},
            description="Validate data",
        )
        
        playbook = Playbook(
            exceptionType="DataQualityFailure",
            steps=[step1, step2],
        )
        
        pack.playbooks = [playbook]
        return pack
    
    @pytest.fixture
    def mock_tenant_policy(self):
        """Create mock tenant policy."""
        policy = Mock(spec=TenantPolicyPack)
        policy.tenant_id = "tenant_001"
        return policy
    
    @pytest.fixture
    def playbook_worker(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_domain_pack,
        mock_tenant_policy,
        mock_event_processing_repo,
    ):
        """Create PlaybookWorker instance."""
        return PlaybookWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="playbook-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            domain_pack=mock_domain_pack,
            tenant_policy=mock_tenant_policy,
            event_processing_repo=mock_event_processing_repo,
        )
    
    @pytest.mark.asyncio
    async def test_process_playbook_matched_event(
        self,
        playbook_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing PlaybookMatched event."""
        # Create PlaybookMatched event
        playbook_matched_event = PlaybookMatched.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id="DataQualityFailure",
            playbook_name="DataQualityFailurePlaybook",
            match_score=0.85,
            match_reason="Matched by exception type",
        )
        
        # Process event
        await playbook_worker.process_event(playbook_matched_event)
        
        # Verify StepExecutionRequested event was emitted
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "StepExecutionRequested"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["playbook_id"] == "DataQualityFailure"
        assert event_data["payload"]["step_number"] == 2  # Next step after current_step=1
    
    @pytest.mark.asyncio
    async def test_process_event_wrong_type(self, playbook_worker):
        """Test processing wrong event type raises error."""
        from src.events.schema import CanonicalEvent
        
        # Create wrong event type
        wrong_event = CanonicalEvent.create(
            event_type="WrongEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="PlaybookWorker expects PlaybookMatched"):
            await playbook_worker.process_event(wrong_event)
    
    @pytest.mark.asyncio
    async def test_get_next_step(self, playbook_worker):
        """Test getting next step from playbook."""
        step1 = PlaybookStep(
            action="notify",
            parameters={},
        )
        step2 = PlaybookStep(
            action="call_tool",
            parameters={},
        )
        step3 = PlaybookStep(
            action="escalate",
            parameters={},
        )
        
        playbook = Playbook(
            exceptionType="TestException",
            steps=[step1, step2, step3],
        )
        
        # Test getting next step
        next_step, step_num = playbook_worker._get_next_step(playbook, current_step=1)
        assert next_step is not None
        assert step_num == 2
        assert next_step.action == "call_tool"  # Step 2
        
        # Test getting step 3
        next_step, step_num = playbook_worker._get_next_step(playbook, current_step=2)
        assert next_step is not None
        assert step_num == 3
        assert next_step.action == "escalate"  # Step 3
        
        # Test no more steps
        next_step, step_num = playbook_worker._get_next_step(playbook, current_step=3)
        assert next_step is None
        assert step_num is None
    
    @pytest.mark.asyncio
    async def test_emit_step_execution_requested(
        self,
        playbook_worker,
        mock_event_publisher,
    ):
        """Test StepExecutionRequested event emission."""
        step = PlaybookStep(
            action="notify",
            parameters={"recipient": "team@example.com"},
            description="Notify team",
        )
        
        # Emit event
        await playbook_worker._emit_step_execution_requested(
            exception_id="exc_001",
            tenant_id="tenant_001",
            playbook_id="DataQualityFailure",
            step=step,
            step_number=1,
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "StepExecutionRequested"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["playbook_id"] == "DataQualityFailure"
        assert "step_action" in event_data["payload"]
        assert event_data["payload"]["step_action"]["action"] == "notify"
    
    @pytest.mark.asyncio
    async def test_handle_step_completion(
        self,
        playbook_worker,
        mock_exception_repository,
    ):
        """Test handling step completion."""
        # Handle step completion
        await playbook_worker.handle_step_completion(
            exception_id="exc_001",
            tenant_id="tenant_001",
            step_number=2,
        )
        
        # Verify exception was updated
        mock_exception_repository.update_exception.assert_called_once()
        call_args = mock_exception_repository.update_exception.call_args
        assert call_args[1]["tenant_id"] == "tenant_001"
        assert call_args[1]["exception_id"] == "exc_001"
        updates = call_args[1]["updates"]
        assert updates.current_step == 2
    
    @pytest.mark.asyncio
    async def test_load_playbook_from_domain_pack(
        self,
        playbook_worker,
        mock_domain_pack,
    ):
        """Test loading playbook from domain pack."""
        playbook = await playbook_worker._load_playbook(
            playbook_id="DataQualityFailure",
            playbook_name=None,
            exception_id="exc_001",
            tenant_id="tenant_001",
        )
        
        assert playbook is not None
        assert playbook.exception_type == "DataQualityFailure"
        assert len(playbook.steps) == 2
    
    @pytest.mark.asyncio
    async def test_no_more_steps_handling(
        self,
        playbook_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test handling when no more steps are available."""
        # Mock exception at last step
        mock_exception = Mock()
        mock_exception.exception_id = "exc_001"
        mock_exception.tenant_id = "tenant_001"
        mock_exception.current_step = 2  # At last step
        mock_exception_repository.get_by_id = AsyncMock(return_value=mock_exception)
        
        # Create PlaybookMatched event
        playbook_matched_event = PlaybookMatched.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id="DataQualityFailure",
            playbook_name="DataQualityFailurePlaybook",
        )
        
        # Process event (should not emit step since no more steps)
        await playbook_worker.process_event(playbook_matched_event)
        
        # Verify no StepExecutionRequested was emitted
        mock_event_publisher.publish_event.assert_not_called()


class TestPlaybookWorkerIntegration:
    """Integration tests for PlaybookWorker."""
    
    @pytest.mark.asyncio
    async def test_playbook_matched_to_step_requested_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_domain_pack,
        mock_tenant_policy,
        mock_event_processing_repo,
    ):
        """Test complete flow from PlaybookMatched to StepExecutionRequested."""
        # Create worker
        worker = PlaybookWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="playbook-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            domain_pack=mock_domain_pack,
            tenant_policy=mock_tenant_policy,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create PlaybookMatched event
        playbook_matched_event = PlaybookMatched.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            playbook_id="DataQualityFailure",
            playbook_name="DataQualityFailurePlaybook",
            match_score=0.85,
            match_reason="Matched by exception type",
        )
        
        # Process event
        await worker.process_event(playbook_matched_event)
        
        # Verify StepExecutionRequested event was emitted
        assert mock_event_publisher.publish_event.called
        call_args = mock_event_publisher.publish_event.call_args
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "StepExecutionRequested"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["playbook_id"] == "DataQualityFailure"
        assert "step_action" in event_data["payload"]
        assert "action" in event_data["payload"]["step_action"]

