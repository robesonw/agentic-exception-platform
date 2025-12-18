"""
Unit tests for DeadLetterEventRepository.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DeadLetterEvent
from src.infrastructure.repositories.dead_letter_repository import (
    DeadLetterEventRepository,
)


class TestDeadLetterEventRepository:
    """Test DeadLetterEventRepository."""
    
    @pytest.fixture
    def mock_session(self):
        """Create mock async session."""
        session = AsyncMock(spec=AsyncSession)
        session.add = Mock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.execute = AsyncMock()
        return session
    
    @pytest.fixture
    def repository(self, mock_session):
        """Create DeadLetterEventRepository instance."""
        return DeadLetterEventRepository(session=mock_session)
    
    @pytest.mark.asyncio
    async def test_create_dlq_entry(self, repository, mock_session):
        """Test creating DLQ entry."""
        # Mock refresh to set ID
        mock_dlq_entry = Mock(spec=DeadLetterEvent)
        mock_dlq_entry.id = 1
        mock_dlq_entry.event_id = "event_001"
        mock_dlq_entry.tenant_id = "tenant_001"
        mock_dlq_entry.retry_count = 3
        
        async def mock_refresh(obj):
            obj.id = 1
        
        mock_session.refresh = AsyncMock(side_effect=mock_refresh)
        
        # Create DLQ entry
        dlq_entry = await repository.create_dlq_entry(
            event_id="event_001",
            event_type="TestEvent",
            tenant_id="tenant_001",
            original_topic="exceptions",
            failure_reason="Test error",
            retry_count=3,
            worker_type="TestWorker",
            payload={"data": "test"},
            exception_id="exc_001",
        )
        
        # Verify entry was created
        assert dlq_entry.event_id == "event_001"
        assert dlq_entry.tenant_id == "tenant_001"
        assert dlq_entry.retry_count == 3
        mock_session.add.assert_called_once()
        mock_session.flush.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_dlq_entry(self, repository, mock_session):
        """Test getting DLQ entry by event_id."""
        # Mock query result
        mock_dlq_entry = Mock(spec=DeadLetterEvent)
        mock_dlq_entry.event_id = "event_001"
        mock_dlq_entry.tenant_id = "tenant_001"
        
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_dlq_entry
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Get DLQ entry
        entry = await repository.get_dlq_entry("event_001", "tenant_001")
        
        # Verify entry was retrieved
        assert entry is not None
        assert entry.event_id == "event_001"
        assert entry.tenant_id == "tenant_001"
    
    @pytest.mark.asyncio
    async def test_get_dlq_entry_not_found(self, repository, mock_session):
        """Test getting DLQ entry that doesn't exist."""
        # Mock query result (None)
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Get DLQ entry
        entry = await repository.get_dlq_entry("event_001", "tenant_001")
        
        # Verify entry was not found
        assert entry is None
    
    @pytest.mark.asyncio
    async def test_list_dlq_entries(self, repository, mock_session):
        """Test listing DLQ entries with filtering."""
        # Mock query results
        mock_dlq_entry1 = Mock(spec=DeadLetterEvent)
        mock_dlq_entry1.event_id = "event_001"
        mock_dlq_entry2 = Mock(spec=DeadLetterEvent)
        mock_dlq_entry2.event_id = "event_002"
        
        # Mock count query
        mock_count_result = Mock()
        mock_count_result.scalar.return_value = 2
        
        # Mock list query
        mock_list_result = Mock()
        mock_list_result.scalars.return_value.all.return_value = [
            mock_dlq_entry1,
            mock_dlq_entry2,
        ]
        
        # Setup execute to return different results for count vs list
        call_count = 0
        
        async def mock_execute(query):
            nonlocal call_count
            call_count += 1
            if "count" in str(query).lower():
                return mock_count_result
            return mock_list_result
        
        mock_session.execute = AsyncMock(side_effect=mock_execute)
        
        # List DLQ entries
        result = await repository.list_dlq_entries(
            tenant_id="tenant_001",
            event_type="TestEvent",
            limit=10,
            offset=0,
        )
        
        # Verify results
        assert result.total == 2
        assert len(result.items) == 2
        assert result.items[0].event_id == "event_001"
    
    @pytest.mark.asyncio
    async def test_get_dlq_entries_by_exception(self, repository, mock_session):
        """Test getting DLQ entries by exception_id."""
        # Mock query results
        mock_dlq_entry = Mock(spec=DeadLetterEvent)
        mock_dlq_entry.event_id = "event_001"
        mock_dlq_entry.exception_id = "exc_001"
        
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [mock_dlq_entry]
        mock_session.execute = AsyncMock(return_value=mock_result)
        
        # Get DLQ entries by exception
        entries = await repository.get_dlq_entries_by_exception(
            exception_id="exc_001",
            tenant_id="tenant_001",
        )
        
        # Verify results
        assert len(entries) == 1
        assert entries[0].event_id == "event_001"
        assert entries[0].exception_id == "exc_001"
    
    @pytest.mark.asyncio
    async def test_create_dlq_entry_validation(self, repository):
        """Test DLQ entry creation validation."""
        # Should raise ValueError for missing event_id
        with pytest.raises(ValueError, match="event_id and tenant_id are required"):
            await repository.create_dlq_entry(
                event_id="",
                event_type="TestEvent",
                tenant_id="tenant_001",
                original_topic="exceptions",
                failure_reason="Test error",
                retry_count=0,
                worker_type="TestWorker",
                payload={},
            )
        
        # Should raise ValueError for missing tenant_id
        with pytest.raises(ValueError, match="event_id and tenant_id are required"):
            await repository.create_dlq_entry(
                event_id="event_001",
                event_type="TestEvent",
                tenant_id="",
                original_topic="exceptions",
                failure_reason="Test error",
                retry_count=0,
                worker_type="TestWorker",
                payload={},
            )
    
    @pytest.mark.asyncio
    async def test_get_dlq_entry_tenant_isolation(self, repository):
        """Test tenant isolation in get_dlq_entry."""
        # Should raise ValueError for empty tenant_id
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repository.get_dlq_entry("event_001", "")
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repository.get_dlq_entry("event_001", "   ")



