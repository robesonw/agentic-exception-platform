"""
Unit tests for PolicyWorker.
"""

import pytest
from unittest.mock import AsyncMock, Mock

from src.agents.policy import PolicyAgent
from src.events.types import (
    PlaybookMatched,
    PolicyEvaluationCompleted,
    PolicyEvaluationRequested,
    TriageCompleted,
)
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.policy_worker import PolicyWorker


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


class TestPolicyWorker:
    """Test PolicyWorker."""
    
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
        """Create mock domain pack."""
        pack = Mock(spec=DomainPack)
        pack.playbooks = []
        return pack
    
    @pytest.fixture
    def mock_tenant_policy(self):
        """Create mock tenant policy."""
        return Mock(spec=TenantPolicyPack)
    
    @pytest.fixture
    def policy_worker(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_domain_pack,
        mock_tenant_policy,
        mock_event_processing_repo,
    ):
        """Create PolicyWorker instance."""
        return PolicyWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="policy-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            domain_pack=mock_domain_pack,
            tenant_policy=mock_tenant_policy,
            event_processing_repo=mock_event_processing_repo,
        )
    
    @pytest.mark.asyncio
    async def test_process_triage_completed_event(
        self,
        policy_worker,
        mock_event_publisher,
        mock_exception_repository,
    ):
        """Test processing TriageCompleted event."""
        # Create TriageCompleted event
        triage_completed_event = TriageCompleted.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            triage_result={
                "decision": "Classified as DataQualityFailure",
                "confidence": 0.85,
                "evidence": ["Rule matched"],
                "nextStep": "ProceedToPolicy",
            },
            severity="HIGH",
            exception_type="DataQualityFailure",
        )
        
        # Mock PolicyAgent to return decision
        decision = AgentDecision(
            decision="Approved for resolution",
            confidence=0.9,
            evidence=["Playbook approved", "Guardrails passed"],
            nextStep="ProceedToResolution",
        )
        policy_worker.policy_agent.process = AsyncMock(return_value=decision)
        
        # Process event
        await policy_worker.process_event(triage_completed_event)
        
        # Verify PolicyEvaluationRequested event was emitted
        assert mock_event_publisher.publish_event.call_count >= 1
        
        # Verify exception was updated
        mock_exception_repository.update_exception.assert_called()
        
        # Verify PolicyEvaluationCompleted event was emitted
        # Should have at least 2 calls: PolicyEvaluationRequested + PolicyEvaluationCompleted
        assert mock_event_publisher.publish_event.call_count >= 2
    
    @pytest.mark.asyncio
    async def test_process_event_wrong_type(self, policy_worker):
        """Test processing wrong event type raises error."""
        from src.events.schema import CanonicalEvent
        
        # Create wrong event type
        wrong_event = CanonicalEvent.create(
            event_type="WrongEvent",
            tenant_id="tenant_001",
            payload={"data": "test"},
        )
        
        # Should raise ValueError
        with pytest.raises(ValueError, match="PolicyWorker expects TriageCompleted"):
            await policy_worker.process_event(wrong_event)
    
    @pytest.mark.asyncio
    async def test_emit_policy_evaluation_requested_event(
        self,
        policy_worker,
        mock_event_publisher,
    ):
        """Test PolicyEvaluationRequested event emission."""
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
        await policy_worker._emit_policy_evaluation_requested_event(
            exception=exception,
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "PolicyEvaluationRequested"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["requested_by"] == "PolicyWorker"
    
    @pytest.mark.asyncio
    async def test_update_exception_policy(
        self,
        policy_worker,
        mock_exception_repository,
    ):
        """Test exception policy update."""
        decision = AgentDecision(
            decision="Approved for resolution",
            confidence=0.9,
            evidence=["Playbook approved"],
            nextStep="ProceedToResolution",
        )
        
        # Update exception
        await policy_worker._update_exception_policy(
            exception_id="exc_001",
            tenant_id="tenant_001",
            decision=decision,
            playbook_id="1",  # Numeric string
        )
        
        # Verify update was called
        mock_exception_repository.update_exception.assert_called_once()
        call_args = mock_exception_repository.update_exception.call_args
        assert call_args[1]["tenant_id"] == "tenant_001"
        assert call_args[1]["exception_id"] == "exc_001"
        updates = call_args[1]["updates"]
        assert updates.current_step == 1
    
    @pytest.mark.asyncio
    async def test_emit_playbook_matched_event(
        self,
        policy_worker,
        mock_event_publisher,
    ):
        """Test PlaybookMatched event emission."""
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
        
        # Emit event
        await policy_worker._emit_playbook_matched_event(
            exception=exception,
            playbook_id="1",
            playbook_name="DataQualityFailurePlaybook",
            match_reason="Matched by exception type",
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "PlaybookMatched"
        assert event_data["exception_id"] == "exc_001"
        assert event_data["payload"]["playbook_id"] == "1"
        assert event_data["payload"]["playbook_name"] == "DataQualityFailurePlaybook"
    
    @pytest.mark.asyncio
    async def test_emit_policy_evaluation_completed_event(
        self,
        policy_worker,
        mock_event_publisher,
    ):
        """Test PolicyEvaluationCompleted event emission."""
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp="2024-01-15T10:30:00Z",
            rawPayload={"error": "Test error"},
            normalizedContext={},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        decision = AgentDecision(
            decision="Approved for resolution",
            confidence=0.9,
            evidence=["Playbook approved", "Guardrails passed"],
            nextStep="ProceedToResolution",
        )
        
        # Emit event
        await policy_worker._emit_policy_evaluation_completed_event(
            exception=exception,
            decision=decision,
            correlation_id="corr_001",
        )
        
        # Verify event was published
        mock_event_publisher.publish_event.assert_called_once()
        call_args = mock_event_publisher.publish_event.call_args
        assert call_args[1]["topic"] == "exceptions"
        event_data = call_args[1]["event"]
        assert event_data["event_type"] == "PolicyEvaluationCompleted"
        assert event_data["exception_id"] == "exc_001"
        assert "policy_result" in event_data["payload"]


class TestPolicyWorkerIntegration:
    """Integration tests for PolicyWorker."""
    
    @pytest.mark.asyncio
    async def test_triage_to_policy_to_playbook_flow(
        self,
        mock_broker,
        mock_event_publisher,
        mock_exception_repository,
        mock_domain_pack,
        mock_tenant_policy,
        mock_event_processing_repo,
    ):
        """Test complete flow from TriageCompleted to PolicyEvaluationCompleted to PlaybookMatched."""
        # Create worker
        worker = PolicyWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="policy-worker-group",
            event_publisher=mock_event_publisher,
            exception_repository=mock_exception_repository,
            domain_pack=mock_domain_pack,
            tenant_policy=mock_tenant_policy,
            event_processing_repo=mock_event_processing_repo,
        )
        
        # Create TriageCompleted event
        triage_completed_event = TriageCompleted.create(
            tenant_id="tenant_001",
            exception_id="exc_001",
            triage_result={
                "decision": "Classified as DataQualityFailure with HIGH severity",
                "confidence": 0.85,
                "evidence": ["Rule matched: invalid_format", "Severity: HIGH"],
                "nextStep": "ProceedToPolicy",
            },
            severity="HIGH",
            exception_type="DataQualityFailure",
        )
        
        # Mock PolicyAgent
        decision = AgentDecision(
            decision="Approved for resolution with playbook",
            confidence=0.9,
            evidence=["Playbook approved", "playbook_id: DataQualityFailure", "Guardrails passed"],
            nextStep="ProceedToResolution",
        )
        worker.policy_agent.process = AsyncMock(return_value=decision)
        
        # Mock playbook in domain pack
        mock_playbook = Mock()
        mock_playbook.exception_type = "DataQualityFailure"
        mock_domain_pack.playbooks = [mock_playbook]
        
        # Process event
        await worker.process_event(triage_completed_event)
        
        # Verify PolicyEvaluationRequested event was emitted
        assert mock_event_publisher.publish_event.call_count >= 1
        
        # Verify exception was updated with playbook
        assert mock_exception_repository.update_exception.called
        call_args = mock_exception_repository.update_exception.call_args
        updates = call_args[1]["updates"]
        assert updates.current_step == 1
        
        # Verify PlaybookMatched event was emitted (if playbook was found)
        # Check all published events
        published_events = [call[1]["event"]["event_type"] for call in mock_event_publisher.publish_event.call_args_list]
        assert "PolicyEvaluationRequested" in published_events
        assert "PolicyEvaluationCompleted" in published_events
        # PlaybookMatched might be emitted if playbook_id was extracted
        if "PlaybookMatched" in published_events:
            # Verify it has correct structure
            playbook_call = next(
                call for call in mock_event_publisher.publish_event.call_args_list
                if call[1]["event"]["event_type"] == "PlaybookMatched"
            )
            event_data = playbook_call[1]["event"]
            assert event_data["exception_id"] == "exc_001"
            assert "playbook_id" in event_data["payload"]



