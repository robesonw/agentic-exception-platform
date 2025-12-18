"""
Tests for SLA Monitor Worker (P9-22).

Tests verify:
- SLAImminent events emitted at threshold
- SLAExpired events emitted at breach
- Tenant-configurable thresholds
- Duplicate event prevention
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from src.workers.sla_monitor_worker import SLAMonitorWorker
from src.events.types import SLAImminent, SLAExpired
from src.infrastructure.db.models import Exception, ExceptionStatus


class TestSLAMonitorWorker:
    """Tests for SLAMonitorWorker."""

    @pytest.fixture
    def mock_event_publisher(self):
        """Create mock event publisher."""
        return AsyncMock()

    @pytest.fixture
    def worker(self, mock_event_publisher):
        """Create SLAMonitorWorker instance."""
        return SLAMonitorWorker(
            event_publisher=mock_event_publisher,
            check_interval_seconds=60,
            default_threshold_percentage=0.8,
            tenant_thresholds={},
        )

    @pytest.fixture
    def worker_with_custom_thresholds(self, mock_event_publisher):
        """Create SLAMonitorWorker with custom tenant thresholds."""
        return SLAMonitorWorker(
            event_publisher=mock_event_publisher,
            check_interval_seconds=60,
            default_threshold_percentage=0.8,
            tenant_thresholds={
                "TENANT_001": 0.7,  # 70% threshold
                "TENANT_002": 0.9,  # 90% threshold
            },
        )

    @pytest.mark.asyncio
    async def test_sla_imminent_emission(self, worker, mock_event_publisher):
        """Test that SLAImminent event is emitted when threshold is reached."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create exception with SLA deadline approaching threshold
        # SLA duration: 100 minutes
        # Threshold: 80% = 80 minutes elapsed
        # Current: 85 minutes elapsed (past threshold)
        created_at = now - timedelta(minutes=85)
        sla_deadline = now + timedelta(minutes=15)  # 15 minutes remaining
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.created_at = created_at
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA imminent
        await worker._check_sla_imminent(exception, now, threshold=0.8)
        
        # Verify event was published
        assert mock_event_publisher.publish_event.called
        
        # Verify event details
        call_args = mock_event_publisher.publish_event.call_args
        published_event = call_args[1]["event"]
        
        assert published_event["event_type"] == "SLAImminent"
        assert published_event["exception_id"] == exception_id
        assert published_event["tenant_id"] == tenant_id
        assert published_event["payload"]["exception_id"] == exception_id
        assert published_event["payload"]["threshold_percentage"] == 0.8
        assert published_event["payload"]["time_remaining_seconds"] > 0

    @pytest.mark.asyncio
    async def test_sla_imminent_not_emitted_before_threshold(self, worker, mock_event_publisher):
        """Test that SLAImminent event is NOT emitted before threshold is reached."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create exception with SLA deadline NOT yet at threshold
        # SLA duration: 100 minutes
        # Threshold: 80% = 80 minutes elapsed
        # Current: 70 minutes elapsed (before threshold)
        created_at = now - timedelta(minutes=70)
        sla_deadline = now + timedelta(minutes=30)  # 30 minutes remaining
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.created_at = created_at
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA imminent
        await worker._check_sla_imminent(exception, now, threshold=0.8)
        
        # Verify event was NOT published
        assert not mock_event_publisher.publish_event.called

    @pytest.mark.asyncio
    async def test_sla_expired_emission(self, worker, mock_event_publisher):
        """Test that SLAExpired event is emitted when SLA is breached."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create exception with SLA deadline already passed
        sla_deadline = now - timedelta(minutes=10)  # 10 minutes past deadline
        breach_duration = 10 * 60  # 10 minutes in seconds
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA expired
        await worker._check_sla_expired(exception, now)
        
        # Verify event was published
        assert mock_event_publisher.publish_event.called
        
        # Verify event details
        call_args = mock_event_publisher.publish_event.call_args
        published_event = call_args[1]["event"]
        
        assert published_event["event_type"] == "SLAExpired"
        assert published_event["exception_id"] == exception_id
        assert published_event["tenant_id"] == tenant_id
        assert published_event["payload"]["exception_id"] == exception_id
        assert published_event["payload"]["breach_duration_seconds"] > 0

    @pytest.mark.asyncio
    async def test_tenant_custom_threshold(self, worker_with_custom_thresholds, mock_event_publisher):
        """Test that tenant-specific thresholds are used."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"  # Has 0.7 threshold
        now = datetime.now(timezone.utc)
        
        # Create exception with SLA deadline approaching tenant-specific threshold
        # SLA duration: 100 minutes
        # Tenant threshold: 70% = 70 minutes elapsed
        # Current: 75 minutes elapsed (past threshold)
        created_at = now - timedelta(minutes=75)
        sla_deadline = now + timedelta(minutes=25)  # 25 minutes remaining
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.created_at = created_at
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA imminent with tenant threshold (0.7)
        await worker_with_custom_thresholds._check_sla_imminent(exception, now, threshold=0.7)
        
        # Verify event was published with tenant threshold
        assert mock_event_publisher.publish_event.called
        
        call_args = mock_event_publisher.publish_event.call_args
        published_event = call_args[1]["event"]
        
        assert published_event["payload"]["threshold_percentage"] == 0.7

    @pytest.mark.asyncio
    async def test_duplicate_imminent_prevention(self, worker, mock_event_publisher):
        """Test that SLAImminent is only emitted once per exception."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create exception past threshold
        created_at = now - timedelta(minutes=85)
        sla_deadline = now + timedelta(minutes=15)
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.created_at = created_at
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA imminent twice
        await worker._check_sla_imminent(exception, now, threshold=0.8)
        await worker._check_sla_imminent(exception, now, threshold=0.8)
        
        # Verify event was published only once
        assert mock_event_publisher.publish_event.call_count == 1

    @pytest.mark.asyncio
    async def test_duplicate_expired_prevention(self, worker, mock_event_publisher):
        """Test that SLAExpired is only emitted once per exception."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create exception with expired SLA
        sla_deadline = now - timedelta(minutes=10)
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA expired twice
        await worker._check_sla_expired(exception, now)
        await worker._check_sla_expired(exception, now)
        
        # Verify event was published only once
        assert mock_event_publisher.publish_event.call_count == 1

    @pytest.mark.asyncio
    async def test_resolved_exceptions_skipped(self, worker, mock_event_publisher):
        """Test that resolved exceptions are skipped."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create resolved exception with expired SLA
        sla_deadline = now - timedelta(minutes=10)
        
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = sla_deadline
        exception.status = ExceptionStatus.RESOLVED  # Resolved, should be skipped
        
        # Mock the query to return empty (resolved exceptions filtered out)
        with patch("src.workers.sla_monitor_worker.get_db_session_context") as mock_session:
            mock_session.return_value.__aenter__.return_value.execute.return_value.scalars.return_value.all.return_value = []
            
            await worker._check_sla_deadlines()
        
        # Verify no events were published
        assert not mock_event_publisher.publish_event.called

    @pytest.mark.asyncio
    async def test_exception_without_sla_deadline_skipped(self, worker, mock_event_publisher):
        """Test that exceptions without SLA deadline are skipped."""
        exception_id = str(uuid4())
        tenant_id = "TENANT_001"
        now = datetime.now(timezone.utc)
        
        # Create exception without SLA deadline
        exception = Mock(spec=Exception)
        exception.exception_id = exception_id
        exception.tenant_id = tenant_id
        exception.sla_deadline = None  # No SLA deadline
        exception.status = ExceptionStatus.OPEN
        
        # Check SLA imminent
        await worker._check_sla_imminent(exception, now, threshold=0.8)
        
        # Verify no events were published
        assert not mock_event_publisher.publish_event.called

    @pytest.mark.asyncio
    async def test_get_threshold_for_tenant(self, worker_with_custom_thresholds):
        """Test getting threshold for tenant."""
        # Custom threshold
        assert worker_with_custom_thresholds.get_threshold_for_tenant("TENANT_001") == 0.7
        assert worker_with_custom_thresholds.get_threshold_for_tenant("TENANT_002") == 0.9
        
        # Default threshold for unknown tenant
        assert worker_with_custom_thresholds.get_threshold_for_tenant("TENANT_999") == 0.8



