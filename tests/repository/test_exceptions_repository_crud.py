"""
Tests for ExceptionRepository CRUD operations.

Tests Phase 6 P6-6: Full CRUD operations with filtering and pagination.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infrastructure.db.models import Exception, ExceptionSeverity, ExceptionStatus
from src.repository.dto import (
    ExceptionCreateDTO,
    ExceptionFilter,
    ExceptionUpdateDTO,
)
from src.repository.exceptions_repository import ExceptionRepository

# Create test base
TestBase = declarative_base()


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite test engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables manually for SQLite compatibility
    async with engine.begin() as conn:
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS exception (
                exception_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                domain TEXT NOT NULL,
                type TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                source_system TEXT NOT NULL,
                entity TEXT,
                amount NUMERIC,
                sla_deadline TIMESTAMP,
                owner TEXT,
                current_playbook_id INTEGER,
                current_step INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
    
    yield engine
    
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create a test session."""
    async_session = sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    
    async with async_session() as session:
        yield session


@pytest.fixture
async def test_data(test_session):
    """Create test data for multiple tenants and domains."""
    repo = ExceptionRepository(test_session)
    
    now = datetime.now(timezone.utc)
    
    # Create exceptions for tenant_1
    exceptions_tenant1 = [
        ExceptionCreateDTO(
            exception_id=f"EX-T1-{i}",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH if i % 2 == 0 else ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.OPEN if i < 3 else ExceptionStatus.RESOLVED,
            source_system="Murex",
        )
        for i in range(1, 6)
    ]
    
    # Create exceptions for tenant_2
    exceptions_tenant2 = [
        ExceptionCreateDTO(
            exception_id=f"EX-T2-{i}",
            tenant_id="tenant_2",
            domain="Healthcare",
            type="ClaimException",
            severity=ExceptionSeverity.CRITICAL if i == 1 else ExceptionSeverity.LOW,
            status=ExceptionStatus.ANALYZING if i < 2 else ExceptionStatus.OPEN,
            source_system="ClaimsApp",
        )
        for i in range(1, 4)
    ]
    
    created = []
    for exc_data in exceptions_tenant1 + exceptions_tenant2:
        exc = await repo.create_exception(exc_data.tenant_id, exc_data)
        created.append(exc)
    
    await test_session.commit()
    
    return created


class TestExceptionRepositoryCreate:
    """Test create_exception method."""

    @pytest.mark.asyncio
    async def test_create_exception_success(self, test_session):
        """Test successful exception creation."""
        repo = ExceptionRepository(test_session)
        
        data = ExceptionCreateDTO(
            exception_id="EX-001",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
        )
        
        result = await repo.create_exception("tenant_1", data)
        await test_session.commit()
        
        assert result is not None
        assert result.exception_id == "EX-001"
        assert result.tenant_id == "tenant_1"
        assert result.domain == "Finance"
        assert result.severity == ExceptionSeverity.HIGH

    @pytest.mark.asyncio
    async def test_create_exception_raises_on_duplicate(self, test_session):
        """Test that create_exception raises error on duplicate exception_id."""
        repo = ExceptionRepository(test_session)
        
        data = ExceptionCreateDTO(
            exception_id="EX-002",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
        )
        
        # First creation succeeds
        await repo.create_exception("tenant_1", data)
        await test_session.commit()
        
        # Second creation should fail
        with pytest.raises(ValueError, match="already exists"):
            await repo.create_exception("tenant_1", data)

    @pytest.mark.asyncio
    async def test_create_exception_raises_on_tenant_mismatch(self, test_session):
        """Test that create_exception raises error on tenant_id mismatch."""
        repo = ExceptionRepository(test_session)
        
        data = ExceptionCreateDTO(
            exception_id="EX-003",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
        )
        
        with pytest.raises(ValueError, match="must match"):
            await repo.create_exception("tenant_2", data)


class TestExceptionRepositoryGet:
    """Test get_exception method."""

    @pytest.mark.asyncio
    async def test_get_exception_success(self, test_session, test_data):
        """Test successful exception retrieval."""
        repo = ExceptionRepository(test_session)
        
        result = await repo.get_exception("tenant_1", "EX-T1-1")
        
        assert result is not None
        assert result.exception_id == "EX-T1-1"
        assert result.tenant_id == "tenant_1"

    @pytest.mark.asyncio
    async def test_get_exception_returns_none_for_nonexistent(self, test_session):
        """Test that get_exception returns None for non-existent exception."""
        repo = ExceptionRepository(test_session)
        
        result = await repo.get_exception("tenant_1", "EX-NONEXISTENT")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_get_exception_tenant_isolation(self, test_session, test_data):
        """Test that get_exception respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        # Exception exists for tenant_1
        result1 = await repo.get_exception("tenant_1", "EX-T1-1")
        assert result1 is not None
        
        # Same exception_id for tenant_2 should return None (different tenant)
        result2 = await repo.get_exception("tenant_2", "EX-T1-1")
        assert result2 is None


class TestExceptionRepositoryUpdate:
    """Test update_exception method."""

    @pytest.mark.asyncio
    async def test_update_exception_success(self, test_session, test_data):
        """Test successful exception update."""
        repo = ExceptionRepository(test_session)
        
        updates = ExceptionUpdateDTO(
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.RESOLVED,
            owner="agent_001",
        )
        
        result = await repo.update_exception("tenant_1", "EX-T1-1", updates)
        await test_session.commit()
        
        assert result is not None
        assert result.severity == ExceptionSeverity.CRITICAL
        assert result.status == ExceptionStatus.RESOLVED
        assert result.owner == "agent_001"
        
        # Verify other fields unchanged
        assert result.exception_id == "EX-T1-1"
        assert result.domain == "Finance"

    @pytest.mark.asyncio
    async def test_update_exception_partial_update(self, test_session, test_data):
        """Test that update_exception only updates provided fields."""
        repo = ExceptionRepository(test_session)
        
        # Get original
        original = await repo.get_exception("tenant_1", "EX-T1-1")
        original_severity = original.severity
        original_domain = original.domain
        
        # Update only status
        updates = ExceptionUpdateDTO(status=ExceptionStatus.RESOLVED)
        
        result = await repo.update_exception("tenant_1", "EX-T1-1", updates)
        await test_session.commit()
        
        assert result.status == ExceptionStatus.RESOLVED
        assert result.severity == original_severity  # Unchanged
        assert result.domain == original_domain  # Unchanged

    @pytest.mark.asyncio
    async def test_update_exception_returns_none_for_nonexistent(self, test_session):
        """Test that update_exception returns None for non-existent exception."""
        repo = ExceptionRepository(test_session)
        
        updates = ExceptionUpdateDTO(status=ExceptionStatus.RESOLVED)
        
        result = await repo.update_exception("tenant_1", "EX-NONEXISTENT", updates)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_update_exception_tenant_isolation(self, test_session, test_data):
        """Test that update_exception respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        updates = ExceptionUpdateDTO(status=ExceptionStatus.RESOLVED)
        
        # Try to update exception from tenant_1 as tenant_2 (should return None)
        result = await repo.update_exception("tenant_2", "EX-T1-1", updates)
        
        assert result is None


class TestExceptionRepositoryList:
    """Test list_exceptions method."""

    @pytest.mark.asyncio
    async def test_list_exceptions_tenant_isolation(self, test_session, test_data):
        """Test that list_exceptions only returns data for correct tenant."""
        repo = ExceptionRepository(test_session)
        
        # List for tenant_1
        result1 = await repo.list_exceptions("tenant_1", ExceptionFilter(), page=1, page_size=100)
        
        assert len(result1.items) == 5
        assert all(ex.tenant_id == "tenant_1" for ex in result1.items)
        
        # List for tenant_2
        result2 = await repo.list_exceptions("tenant_2", ExceptionFilter(), page=1, page_size=100)
        
        assert len(result2.items) == 3
        assert all(ex.tenant_id == "tenant_2" for ex in result2.items)

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_domain(self, test_session, test_data):
        """Test filtering exceptions by domain."""
        repo = ExceptionRepository(test_session)
        
        # Filter by Finance domain
        filters = ExceptionFilter(domain="Finance")
        result = await repo.list_exceptions("tenant_1", filters, page=1, page_size=100)
        
        assert len(result.items) == 5
        assert all(ex.domain == "Finance" for ex in result.items)
        
        # Filter by Healthcare domain (should return 0 for tenant_1)
        filters2 = ExceptionFilter(domain="Healthcare")
        result2 = await repo.list_exceptions("tenant_1", filters2, page=1, page_size=100)
        
        assert len(result2.items) == 0

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_status(self, test_session, test_data):
        """Test filtering exceptions by status."""
        repo = ExceptionRepository(test_session)
        
        # Filter by OPEN status
        filters = ExceptionFilter(status=ExceptionStatus.OPEN)
        result = await repo.list_exceptions("tenant_1", filters, page=1, page_size=100)
        
        assert len(result.items) == 3
        assert all(ex.status == ExceptionStatus.OPEN for ex in result.items)
        
        # Filter by RESOLVED status
        filters2 = ExceptionFilter(status=ExceptionStatus.RESOLVED)
        result2 = await repo.list_exceptions("tenant_1", filters2, page=1, page_size=100)
        
        assert len(result2.items) == 2
        assert all(ex.status == ExceptionStatus.RESOLVED for ex in result2.items)

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_severity(self, test_session, test_data):
        """Test filtering exceptions by severity."""
        repo = ExceptionRepository(test_session)
        
        # Filter by HIGH severity
        filters = ExceptionFilter(severity=ExceptionSeverity.HIGH)
        result = await repo.list_exceptions("tenant_1", filters, page=1, page_size=100)
        
        # Should have 2 HIGH severity items (EX-T1-2, EX-T1-4)
        assert len(result.items) == 2
        assert all(ex.severity == ExceptionSeverity.HIGH for ex in result.items)

    @pytest.mark.asyncio
    async def test_list_exceptions_filter_by_date_range(self, test_session):
        """Test filtering exceptions by date range."""
        repo = ExceptionRepository(test_session)
        
        # Create exceptions with different timestamps
        now = datetime.now(timezone.utc)
        yesterday = now - timedelta(days=1)
        tomorrow = now + timedelta(days=1)
        
        # Create exception with specific created_at (we'll need to set it manually)
        data1 = ExceptionCreateDTO(
            exception_id="EX-DATE-1",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
        )
        exc1 = await repo.create_exception("tenant_1", data1)
        await test_session.commit()
        
        # Filter by created_from
        filters = ExceptionFilter(created_from=yesterday)
        result = await repo.list_exceptions("tenant_1", filters, page=1, page_size=100)
        
        # Should include all exceptions created after yesterday
        assert len(result.items) >= 1
        
        # Filter by created_to
        filters2 = ExceptionFilter(created_to=tomorrow)
        result2 = await repo.list_exceptions("tenant_1", filters2, page=1, page_size=100)
        
        # Should include all exceptions created before tomorrow
        assert len(result2.items) >= 1

    @pytest.mark.asyncio
    async def test_list_exceptions_multiple_filters(self, test_session, test_data):
        """Test filtering with multiple criteria."""
        repo = ExceptionRepository(test_session)
        
        # Filter by domain AND status
        filters = ExceptionFilter(
            domain="Finance",
            status=ExceptionStatus.OPEN,
        )
        result = await repo.list_exceptions("tenant_1", filters, page=1, page_size=100)
        
        assert len(result.items) == 3
        assert all(ex.domain == "Finance" and ex.status == ExceptionStatus.OPEN for ex in result.items)

    @pytest.mark.asyncio
    async def test_list_exceptions_pagination(self, test_session, test_data):
        """Test pagination in list_exceptions."""
        repo = ExceptionRepository(test_session)
        
        # First page
        result1 = await repo.list_exceptions("tenant_1", ExceptionFilter(), page=1, page_size=2)
        
        assert len(result1.items) == 2
        assert result1.page == 1
        assert result1.page_size == 2
        assert result1.total == 5
        assert result1.total_pages == 3
        
        # Second page
        result2 = await repo.list_exceptions("tenant_1", ExceptionFilter(), page=2, page_size=2)
        
        assert len(result2.items) == 2
        assert result2.page == 2
        
        # Third page (partial)
        result3 = await repo.list_exceptions("tenant_1", ExceptionFilter(), page=3, page_size=2)
        
        assert len(result3.items) == 1
        assert result3.page == 3

    @pytest.mark.asyncio
    async def test_list_exceptions_ordering(self, test_session, test_data):
        """Test that list_exceptions orders by created_at DESC."""
        repo = ExceptionRepository(test_session)
        
        result = await repo.list_exceptions("tenant_1", ExceptionFilter(), page=1, page_size=100)
        
        # Verify ordering (newest first)
        if len(result.items) > 1:
            for i in range(len(result.items) - 1):
                assert result.items[i].created_at >= result.items[i + 1].created_at

    @pytest.mark.asyncio
    async def test_list_exceptions_empty_result(self, test_session):
        """Test list_exceptions with no matching results."""
        repo = ExceptionRepository(test_session)
        
        filters = ExceptionFilter(domain="NonExistentDomain")
        result = await repo.list_exceptions("tenant_1", filters, page=1, page_size=50)
        
        assert len(result.items) == 0
        assert result.total == 0
        assert result.page == 1
        assert result.page_size == 50

