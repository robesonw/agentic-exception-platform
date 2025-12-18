"""
Unit tests for Event Processing Repository.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from src.infrastructure.db.models import EventProcessing, EventProcessingStatus
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)


class TestEventProcessingRepository:
    """Test Event Processing Repository."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create repository instance."""
        return EventProcessingRepository(mock_session)
    
    @pytest.mark.asyncio
    async def test_is_processed_false_when_not_processed(self, repository, mock_session):
        """Test is_processed returns False when event not processed."""
        # Mock query result - no record found
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        result = await repository.is_processed("event_001", "TestWorker")
        
        assert result is False
        mock_session.execute.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_is_processed_true_when_completed(self, repository, mock_session):
        """Test is_processed returns True when event is completed."""
        # Mock query result - record found with COMPLETED status
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = EventProcessingStatus.COMPLETED
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        result = await repository.is_processed("event_001", "TestWorker")
        
        assert result is True
        
    @pytest.mark.asyncio
    async def test_is_processing_true_when_processing(self, repository, mock_session):
        """Test is_processing returns True when event is processing."""
        # Mock query result - record found with PROCESSING status
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = EventProcessingStatus.PROCESSING
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        result = await repository.is_processing("event_001", "TestWorker")
        
        assert result is True
        
    @pytest.mark.asyncio
    async def test_get_processing_status(self, repository, mock_session):
        """Test get_processing_status returns status."""
        # Mock query result
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = EventProcessingStatus.COMPLETED
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        status = await repository.get_processing_status("event_001", "TestWorker")
        
        assert status == EventProcessingStatus.COMPLETED
        
    @pytest.mark.asyncio
    async def test_get_processing_status_none_when_not_found(self, repository, mock_session):
        """Test get_processing_status returns None when not found."""
        # Mock query result - no record
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        status = await repository.get_processing_status("event_001", "TestWorker")
        
        assert status is None
        
    @pytest.mark.asyncio
    async def test_mark_processing_creates_new_record(self, repository, mock_session):
        """Test mark_processing creates new record."""
        # Mock query result - no existing record
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        # Mock flush and refresh
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        processing = await repository.mark_processing(
            event_id="event_001",
            worker_type="TestWorker",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        # Verify new record was created
        assert processing is not None
        assert processing.status == EventProcessingStatus.PROCESSING
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_mark_processing_updates_existing_record(self, repository, mock_session):
        """Test mark_processing updates existing record."""
        # Mock existing record
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = EventProcessingStatus.FAILED
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        # Mock flush and refresh
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        processing = await repository.mark_processing(
            event_id="event_001",
            worker_type="TestWorker",
            tenant_id="tenant_001",
        )
        
        # Verify record was updated
        assert processing.status == EventProcessingStatus.PROCESSING
        mock_session.add.assert_not_called()
        mock_session.flush.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_mark_completed_updates_status(self, repository, mock_session):
        """Test mark_completed updates status to COMPLETED."""
        # Mock existing record
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = EventProcessingStatus.PROCESSING
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        # Mock flush and refresh
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        processing = await repository.mark_completed("event_001", "TestWorker")
        
        # Verify status was updated
        assert processing is not None
        assert processing.status == EventProcessingStatus.COMPLETED
        assert processing.error_message is None
        mock_session.flush.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_mark_completed_returns_none_when_not_found(self, repository, mock_session):
        """Test mark_completed returns None when record not found."""
        # Mock query result - no record
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        processing = await repository.mark_completed("event_001", "TestWorker")
        
        assert processing is None
        
    @pytest.mark.asyncio
    async def test_mark_failed_updates_status(self, repository, mock_session):
        """Test mark_failed updates status to FAILED."""
        # Mock existing record
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.status = EventProcessingStatus.PROCESSING
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        # Mock flush and refresh
        mock_session.flush = AsyncMock()
        mock_session.refresh = AsyncMock()
        
        error_message = "Processing failed"
        processing = await repository.mark_failed(
            "event_001", "TestWorker", error_message
        )
        
        # Verify status was updated
        assert processing is not None
        assert processing.status == EventProcessingStatus.FAILED
        assert processing.error_message == error_message
        mock_session.flush.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_mark_failed_returns_none_when_not_found(self, repository, mock_session):
        """Test mark_failed returns None when record not found."""
        # Mock query result - no record
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result
        
        processing = await repository.mark_failed("event_001", "TestWorker", "error")
        
        assert processing is None
        
    @pytest.mark.asyncio
    async def test_get_processing_record(self, repository, mock_session):
        """Test get_processing_record retrieves record."""
        # Mock query result
        mock_processing = Mock(spec=EventProcessing)
        mock_processing.event_id = "event_001"
        mock_processing.worker_type = "TestWorker"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_processing
        mock_session.execute.return_value = mock_result
        
        processing = await repository.get_processing_record("event_001", "TestWorker")
        
        assert processing is not None
        assert processing.event_id == "event_001"
        assert processing.worker_type == "TestWorker"



