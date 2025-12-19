"""
Tests for Dead Letter Queue Repository (P10-4).

Tests DLQ CRUD operations, status management, and statistics.
Uses mocking to avoid database dependency.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.repositories.dead_letter_repository import (
    DeadLetterEventRepository,
    DLQStats,
)


class TestDLQStats:
    """Test DLQStats dataclass."""

    def test_dlq_stats_creation(self):
        """Test DLQStats dataclass creation."""
        stats = DLQStats(
            tenant_id="tenant_1",
            total=100,
            pending=50,
            retrying=10,
            discarded=30,
            succeeded=10,
            by_event_type={"test.event": 80, "other.event": 20},
            by_worker_type={"intake": 60, "triage": 40},
        )

        assert stats.tenant_id == "tenant_1"
        assert stats.total == 100
        assert stats.pending == 50
        assert stats.retrying == 10
        assert stats.discarded == 30
        assert stats.succeeded == 10
        assert stats.by_event_type["test.event"] == 80
        assert stats.by_worker_type["intake"] == 60

    def test_dlq_stats_empty(self):
        """Test DLQStats with empty values."""
        stats = DLQStats(
            tenant_id="tenant_1",
            total=0,
            pending=0,
            retrying=0,
            discarded=0,
            succeeded=0,
            by_event_type={},
            by_worker_type={},
        )

        assert stats.total == 0
        assert len(stats.by_event_type) == 0
        assert len(stats.by_worker_type) == 0


class TestDeadLetterEventRepositoryValidation:
    """Test DeadLetterEventRepository validation without database."""

    @pytest.fixture
    def mock_session(self):
        """Create a mock session."""
        session = MagicMock()
        session.execute = AsyncMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture
    def repo(self, mock_session):
        """Create repository with mock session."""
        return DeadLetterEventRepository(mock_session)

    @pytest.mark.asyncio
    async def test_create_dlq_entry_requires_event_id(self, repo):
        """Test that create_dlq_entry requires event_id."""
        with pytest.raises(ValueError, match="event_id and tenant_id are required"):
            await repo.create_dlq_entry(
                event_id="",
                event_type="test.event",
                tenant_id="tenant_1",
                original_topic="test.topic",
                failure_reason="test failure",
                retry_count=0,
                worker_type="intake",
                payload={},
            )

    @pytest.mark.asyncio
    async def test_create_dlq_entry_requires_tenant_id(self, repo):
        """Test that create_dlq_entry requires tenant_id."""
        with pytest.raises(ValueError, match="event_id and tenant_id are required"):
            await repo.create_dlq_entry(
                event_id="event_001",
                event_type="test.event",
                tenant_id="",
                original_topic="test.topic",
                failure_reason="test failure",
                retry_count=0,
                worker_type="intake",
                payload={},
            )

    @pytest.mark.asyncio
    async def test_get_dlq_entry_requires_tenant_id(self, repo):
        """Test that get_dlq_entry enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.get_dlq_entry("event_001", "")

        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.get_dlq_entry("event_001", "   ")

    @pytest.mark.asyncio
    async def test_list_dlq_entries_requires_tenant_id(self, repo):
        """Test that list_dlq_entries enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.list_dlq_entries("")

        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.list_dlq_entries("   ")

    @pytest.mark.asyncio
    async def test_get_dlq_entries_by_exception_requires_tenant_id(self, repo):
        """Test that get_dlq_entries_by_exception enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.get_dlq_entries_by_exception("exc_001", "")

    @pytest.mark.asyncio
    async def test_get_dlq_entry_by_id_requires_tenant_id(self, repo):
        """Test that get_dlq_entry_by_id enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.get_dlq_entry_by_id(1, "")

    @pytest.mark.asyncio
    async def test_batch_update_status_empty_list(self, repo):
        """Test that batch_update_status handles empty list."""
        count = await repo.batch_update_status([], "tenant_1", "retrying")
        assert count == 0

    @pytest.mark.asyncio
    async def test_batch_update_status_requires_tenant_id(self, repo):
        """Test that batch_update_status enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.batch_update_status([1, 2, 3], "", "retrying")

    @pytest.mark.asyncio
    async def test_get_stats_requires_tenant_id(self, repo):
        """Test that get_stats enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.get_stats("")

    @pytest.mark.asyncio
    async def test_list_dlq_entries_with_status_requires_tenant_id(self, repo):
        """Test that list_dlq_entries_with_status enforces tenant isolation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.list_dlq_entries_with_status("")

    @pytest.mark.asyncio
    async def test_update_status_not_found_returns_none(self, repo):
        """Test that update_status returns None when entry not found."""
        # Mock get_dlq_entry_by_id to return None
        with patch.object(repo, "get_dlq_entry_by_id", return_value=None):
            result = await repo.update_status(999, "tenant_1", "retrying")
            assert result is None

    @pytest.mark.asyncio
    async def test_mark_retrying_calls_update_status(self, repo):
        """Test that mark_retrying calls update_status correctly."""
        with patch.object(repo, "update_status", return_value=None) as mock_update:
            await repo.mark_retrying(1, "tenant_1")
            mock_update.assert_called_once_with(1, "tenant_1", "retrying")

    @pytest.mark.asyncio
    async def test_mark_succeeded_calls_update_status(self, repo):
        """Test that mark_succeeded calls update_status correctly."""
        with patch.object(repo, "update_status", return_value=None) as mock_update:
            await repo.mark_succeeded(1, "tenant_1")
            mock_update.assert_called_once_with(1, "tenant_1", "succeeded")

    @pytest.mark.asyncio
    async def test_mark_discarded_calls_update_status_with_actor(self, repo):
        """Test that mark_discarded calls update_status with actor."""
        with patch.object(repo, "update_status", return_value=None) as mock_update:
            await repo.mark_discarded(1, "tenant_1", "admin@test.com")
            mock_update.assert_called_once_with(
                1, "tenant_1", "discarded", "admin@test.com"
            )
