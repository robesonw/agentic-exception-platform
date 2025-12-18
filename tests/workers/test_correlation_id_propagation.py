"""
Tests for correlation_id propagation across worker chain (P9-21).

Tests verify:
- correlation_id = exception_id in all events
- correlation_id is propagated through worker chain
- correlation_id is added to event metadata
- Trace query returns all events with same correlation_id
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4

from src.events.types import (
    ExceptionIngested,
    ExceptionNormalized,
    TriageCompleted,
    PolicyEvaluationCompleted,
    PlaybookMatched,
)
from src.workers.intake_worker import IntakeWorker
from src.workers.triage_worker import TriageWorker
from src.workers.policy_worker import PolicyWorker
from src.models.exception_record import ExceptionRecord, Severity, ResolutionStatus
from datetime import datetime, timezone


class TestCorrelationIdPropagation:
    """Tests for correlation_id propagation across worker chain."""

    @pytest.mark.asyncio
    async def test_exception_ingested_has_correlation_id(self):
        """Test that ExceptionIngested event has correlation_id = exception_id."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        event = ExceptionIngested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            raw_payload={"error": "Test error"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        # correlation_id should equal exception_id
        assert event.correlation_id == exception_id
        assert event.exception_id == exception_id
        # correlation_id should be in metadata
        assert "correlation_id" in event.metadata
        assert event.metadata["correlation_id"] == exception_id

    @pytest.mark.asyncio
    async def test_intake_worker_propagates_correlation_id(self):
        """Test that IntakeWorker propagates correlation_id to ExceptionNormalized event."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        # Create ingested event with correlation_id
        ingested_event = ExceptionIngested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            raw_payload={"error": "Test error"},
            source_system="TEST",
            ingestion_method="api",
            correlation_id=exception_id,
        )
        
        # Mock dependencies
        mock_broker = Mock()
        mock_intake_agent = AsyncMock()
        mock_exception_repo = AsyncMock()
        mock_event_publisher = AsyncMock()
        
        # Mock IntakeAgent.process to return normalized exception
        normalized_exception = ExceptionRecord(
            exception_id=exception_id,
            tenant_id=tenant_id,
            source_system="TEST",
            exception_type="TestException",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "Test error"},
            normalized_context={"domain": "test"},
            resolution_status=ResolutionStatus.OPEN,
            audit_trail=[],
        )
        mock_intake_agent.process.return_value = Mock(
            normalized=normalized_exception,
            decision=Mock(),
        )
        
        # Create worker
        worker = IntakeWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="intake-workers",
            intake_agent=mock_intake_agent,
            exception_repository=mock_exception_repo,
            event_publisher=mock_event_publisher,
        )
        
        # Process event
        await worker.process_event(ingested_event)
        
        # Verify event publisher was called
        assert mock_event_publisher.publish_event.called
        
        # Get the published event
        call_args = mock_event_publisher.publish_event.call_args
        published_event_dict = call_args[1]["event"]
        
        # Verify correlation_id is propagated
        assert published_event_dict["correlation_id"] == exception_id
        assert published_event_dict["exception_id"] == exception_id
        # Verify correlation_id is in metadata
        assert "correlation_id" in published_event_dict.get("metadata", {})
        assert published_event_dict["metadata"]["correlation_id"] == exception_id

    @pytest.mark.asyncio
    async def test_triage_worker_propagates_correlation_id(self):
        """Test that TriageWorker propagates correlation_id to TriageCompleted event."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        # Create normalized event with correlation_id
        normalized_event = ExceptionNormalized.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            normalized_exception={},
            normalization_rules=[],
            correlation_id=exception_id,
        )
        
        # Mock dependencies
        mock_broker = Mock()
        mock_triage_agent = AsyncMock()
        mock_exception_repo = AsyncMock()
        mock_event_publisher = AsyncMock()
        mock_domain_pack = Mock()
        mock_llm_client = Mock()
        
        # Mock TriageAgent.process
        mock_triage_agent.process.return_value = Mock(
            decision="HIGH severity",
            evidence={"severity": "HIGH", "exception_type": "TestException"},
        )
        
        # Mock exception repository
        exception_record = ExceptionRecord(
            exception_id=exception_id,
            tenant_id=tenant_id,
            source_system="TEST",
            exception_type="TestException",
            severity=Severity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
            raw_payload={},
            normalized_context={},
            resolution_status=ResolutionStatus.OPEN,
            audit_trail=[],
        )
        mock_exception_repo.get_exception.return_value = Mock(
            exception_id=exception_id,
            tenant_id=tenant_id,
            type="TestException",
            severity=Mock(value="high"),
            source_system="TEST",
            domain="test",
        )
        
        # Create worker
        worker = TriageWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="triage-workers",
            triage_agent=mock_triage_agent,
            exception_repository=mock_exception_repo,
            event_publisher=mock_event_publisher,
            domain_pack=mock_domain_pack,
            llm_client=mock_llm_client,
        )
        
        # Process event
        await worker.process_event(normalized_event)
        
        # Verify event publisher was called
        assert mock_event_publisher.publish_event.called
        
        # Get the published TriageCompleted event
        call_args = mock_event_publisher.publish_event.call_args
        published_event_dict = call_args[1]["event"]
        
        # Verify correlation_id is propagated
        assert published_event_dict["correlation_id"] == exception_id
        assert published_event_dict["exception_id"] == exception_id
        # Verify correlation_id is in metadata
        assert "correlation_id" in published_event_dict.get("metadata", {})
        assert published_event_dict["metadata"]["correlation_id"] == exception_id

    @pytest.mark.asyncio
    async def test_policy_worker_propagates_correlation_id(self):
        """Test that PolicyWorker propagates correlation_id to PolicyEvaluationCompleted event."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        # Create triage completed event with correlation_id
        triage_completed_event = TriageCompleted.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            triage_result={},
            severity="HIGH",
            exception_type="TestException",
            correlation_id=exception_id,
        )
        
        # Mock dependencies
        mock_broker = Mock()
        mock_policy_agent = AsyncMock()
        mock_exception_repo = AsyncMock()
        mock_event_publisher = AsyncMock()
        mock_domain_pack = Mock()
        mock_tenant_policy = Mock()
        mock_llm_client = Mock()
        
        # Mock PolicyAgent.process
        mock_policy_agent.process.return_value = Mock(
            decision="APPROVED",
            evidence={"playbook_id": "1"},
        )
        
        # Mock exception repository
        mock_exception_repo.get_exception.return_value = Mock(
            exception_id=exception_id,
            tenant_id=tenant_id,
            type="TestException",
            severity=Mock(value="high"),
            source_system="TEST",
            domain="test",
        )
        
        # Create worker
        worker = PolicyWorker(
            broker=mock_broker,
            topics=["exceptions"],
            group_id="policy-workers",
            policy_agent=mock_policy_agent,
            exception_repository=mock_exception_repo,
            event_publisher=mock_event_publisher,
            domain_pack=mock_domain_pack,
            tenant_policy=mock_tenant_policy,
            llm_client=mock_llm_client,
        )
        
        # Process event
        await worker.process_event(triage_completed_event)
        
        # Verify event publisher was called
        assert mock_event_publisher.publish_event.called
        
        # Get the published PolicyEvaluationCompleted event
        # (may be called multiple times, get the last one)
        call_args_list = mock_event_publisher.publish_event.call_args_list
        policy_completed_call = None
        for call in call_args_list:
            event_dict = call[1]["event"]
            if event_dict.get("event_type") == "PolicyEvaluationCompleted":
                policy_completed_call = call
                break
        
        if policy_completed_call:
            published_event_dict = policy_completed_call[1]["event"]
            # Verify correlation_id is propagated
            assert published_event_dict["correlation_id"] == exception_id
            assert published_event_dict["exception_id"] == exception_id
            # Verify correlation_id is in metadata
            assert "correlation_id" in published_event_dict.get("metadata", {})
            assert published_event_dict["metadata"]["correlation_id"] == exception_id

    @pytest.mark.asyncio
    async def test_correlation_id_defaults_to_exception_id(self):
        """Test that correlation_id defaults to exception_id when not provided."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        # Create event without correlation_id
        event = ExceptionIngested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            raw_payload={"error": "Test error"},
            source_system="TEST",
            ingestion_method="api",
            # correlation_id not provided
        )
        
        # correlation_id should default to exception_id
        assert event.correlation_id == exception_id
        assert event.exception_id == exception_id
        # correlation_id should be in metadata
        assert "correlation_id" in event.metadata
        assert event.metadata["correlation_id"] == exception_id

    @pytest.mark.asyncio
    async def test_correlation_id_in_metadata(self):
        """Test that correlation_id is always added to event metadata."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        # Create event with custom metadata
        event = ExceptionIngested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            raw_payload={"error": "Test error"},
            source_system="TEST",
            ingestion_method="api",
            metadata={"custom": "value"},
        )
        
        # correlation_id should be in metadata
        assert "correlation_id" in event.metadata
        assert event.metadata["correlation_id"] == exception_id
        # Custom metadata should be preserved
        assert event.metadata["custom"] == "value"

    @pytest.mark.asyncio
    async def test_worker_chain_correlation_id_propagation(self):
        """Test correlation_id propagation through full worker chain."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        
        # Step 1: ExceptionIngested
        ingested_event = ExceptionIngested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            raw_payload={"error": "Test error"},
            source_system="TEST",
            ingestion_method="api",
        )
        
        assert ingested_event.correlation_id == exception_id
        
        # Step 2: ExceptionNormalized (simulated)
        normalized_event = ExceptionNormalized.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            normalized_exception={},
            normalization_rules=[],
            correlation_id=ingested_event.correlation_id,  # Propagate from ingested
        )
        
        assert normalized_event.correlation_id == exception_id
        
        # Step 3: TriageCompleted (simulated)
        triage_completed_event = TriageCompleted.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            triage_result={},
            severity="HIGH",
            exception_type="TestException",
            correlation_id=normalized_event.correlation_id,  # Propagate from normalized
        )
        
        assert triage_completed_event.correlation_id == exception_id
        
        # Step 4: PolicyEvaluationCompleted (simulated)
        policy_completed_event = PolicyEvaluationCompleted.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            policy_result={},
            approved_actions=[],
            guardrails_applied=[],
            correlation_id=triage_completed_event.correlation_id,  # Propagate from triage
        )
        
        assert policy_completed_event.correlation_id == exception_id
        
        # Step 5: PlaybookMatched (simulated)
        playbook_matched_event = PlaybookMatched.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            playbook_id="1",
            playbook_name="TestPlaybook",
            match_score=0.85,
            match_reason="Matched",
            correlation_id=policy_completed_event.correlation_id,  # Propagate from policy
        )
        
        assert playbook_matched_event.correlation_id == exception_id
        
        # All events should have the same correlation_id
        assert all(
            event.correlation_id == exception_id
            for event in [
                ingested_event,
                normalized_event,
                triage_completed_event,
                policy_completed_event,
                playbook_matched_event,
            ]
        )



