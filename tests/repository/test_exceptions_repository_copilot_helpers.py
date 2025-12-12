"""
Tests for ExceptionRepository Co-Pilot query helpers.

Tests Phase 6 P6-7: Co-Pilot query helpers for contextual retrieval.
"""

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infrastructure.db.models import Exception, ExceptionSeverity, ExceptionStatus
from src.repository.dto import ExceptionCreateDTO
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
    """Create comprehensive test data for Co-Pilot query helpers."""
    repo = ExceptionRepository(test_session)
    
    now = datetime.now(timezone.utc)
    
    # Create exceptions for tenant_1 with various domains, types, entities, and source systems
    exceptions = [
        # Finance domain, TradeException type
        ExceptionCreateDTO(
            exception_id="EX-FIN-TRADE-1",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            entity="CPTY-001",
        ),
        ExceptionCreateDTO(
            exception_id="EX-FIN-TRADE-2",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.RESOLVED,
            source_system="Murex",
            entity="CPTY-001",
        ),
        ExceptionCreateDTO(
            exception_id="EX-FIN-TRADE-3",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            entity="CPTY-002",
        ),
        # Finance domain, SettlementException type
        ExceptionCreateDTO(
            exception_id="EX-FIN-SETTLE-1",
            tenant_id="tenant_1",
            domain="Finance",
            type="SettlementException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.ANALYZING,
            source_system="Murex",
            entity="CPTY-001",
        ),
        # Healthcare domain, ClaimException type
        ExceptionCreateDTO(
            exception_id="EX-HC-CLAIM-1",
            tenant_id="tenant_1",
            domain="Healthcare",
            type="ClaimException",
            severity=ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.OPEN,
            source_system="ClaimsApp",
            entity="PATIENT-001",
        ),
        ExceptionCreateDTO(
            exception_id="EX-HC-CLAIM-2",
            tenant_id="tenant_1",
            domain="Healthcare",
            type="ClaimException",
            severity=ExceptionSeverity.LOW,
            status=ExceptionStatus.RESOLVED,
            source_system="ClaimsApp",
            entity="PATIENT-001",
        ),
        # Exceptions for tenant_2 (for tenant isolation testing)
        ExceptionCreateDTO(
            exception_id="EX-T2-1",
            tenant_id="tenant_2",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            entity="CPTY-003",
        ),
    ]
    
    created = []
    for exc_data in exceptions:
        exc = await repo.create_exception(exc_data.tenant_id, exc_data)
        created.append(exc)
    
    await test_session.commit()
    
    return created


@pytest.fixture
async def test_data_with_sla(test_session):
    """Create test data with SLA deadlines for imminent breach testing."""
    repo = ExceptionRepository(test_session)
    
    now = datetime.now(timezone.utc)
    
    # Create exceptions with various SLA deadlines
    exceptions = [
        # Imminent breach (within 60 minutes)
        ExceptionCreateDTO(
            exception_id="EX-SLA-1",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            sla_deadline=now + timedelta(minutes=30),  # 30 minutes from now
        ),
        ExceptionCreateDTO(
            exception_id="EX-SLA-2",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.CRITICAL,
            status=ExceptionStatus.ANALYZING,
            source_system="Murex",
            sla_deadline=now + timedelta(minutes=45),  # 45 minutes from now
        ),
        # Not imminent (too far in future)
        ExceptionCreateDTO(
            exception_id="EX-SLA-3",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            sla_deadline=now + timedelta(hours=2),  # 2 hours from now
        ),
        # Resolved (should not appear)
        ExceptionCreateDTO(
            exception_id="EX-SLA-4",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.RESOLVED,
            source_system="Murex",
            sla_deadline=now + timedelta(minutes=20),  # 20 minutes from now
        ),
        # No SLA deadline (should not appear)
        ExceptionCreateDTO(
            exception_id="EX-SLA-5",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            sla_deadline=None,
        ),
    ]
    
    created = []
    for exc_data in exceptions:
        exc = await repo.create_exception(exc_data.tenant_id, exc_data)
        created.append(exc)
    
    # Manually set sla_deadline after creation (SQLite compatibility)
    for i, exc_data in enumerate(exceptions):
        if exc_data.sla_deadline:
            created[i].sla_deadline = exc_data.sla_deadline
    
    await test_session.commit()
    
    # Refresh to ensure sla_deadline is persisted
    for exc in created:
        await test_session.refresh(exc)
    
    return created


class TestFindSimilarExceptions:
    """Test find_similar_exceptions method."""

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_by_domain(self, test_session, test_data):
        """Test finding similar exceptions by domain."""
        repo = ExceptionRepository(test_session)
        
        # Find Finance domain exceptions
        results = await repo.find_similar_exceptions("tenant_1", domain="Finance", limit=100)
        
        assert len(results) == 4  # 4 Finance exceptions for tenant_1
        assert all(ex.domain == "Finance" for ex in results)
        assert all(ex.tenant_id == "tenant_1" for ex in results)

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_by_type(self, test_session, test_data):
        """Test finding similar exceptions by exception type."""
        repo = ExceptionRepository(test_session)
        
        # Find TradeException type
        results = await repo.find_similar_exceptions("tenant_1", exception_type="TradeException", limit=100)
        
        assert len(results) == 3  # 3 TradeException exceptions for tenant_1
        assert all(ex.type == "TradeException" for ex in results)
        assert all(ex.tenant_id == "tenant_1" for ex in results)

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_by_domain_and_type(self, test_session, test_data):
        """Test finding similar exceptions by both domain and type."""
        repo = ExceptionRepository(test_session)
        
        # Find Finance domain + TradeException type
        results = await repo.find_similar_exceptions(
            "tenant_1",
            domain="Finance",
            exception_type="TradeException",
            limit=100,
        )
        
        assert len(results) == 3
        assert all(ex.domain == "Finance" and ex.type == "TradeException" for ex in results)
        assert all(ex.tenant_id == "tenant_1" for ex in results)

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_no_filters(self, test_session, test_data):
        """Test finding similar exceptions without filters."""
        repo = ExceptionRepository(test_session)
        
        # Find all exceptions (no filters)
        results = await repo.find_similar_exceptions("tenant_1", limit=100)
        
        assert len(results) == 6  # All 6 exceptions for tenant_1
        assert all(ex.tenant_id == "tenant_1" for ex in results)

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_limit(self, test_session, test_data):
        """Test that limit is respected."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.find_similar_exceptions("tenant_1", limit=2)
        
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_tenant_isolation(self, test_session, test_data):
        """Test that find_similar_exceptions respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        # Query for tenant_1
        results1 = await repo.find_similar_exceptions("tenant_1", limit=100)
        
        # Query for tenant_2
        results2 = await repo.find_similar_exceptions("tenant_2", limit=100)
        
        assert len(results1) == 6
        assert len(results2) == 1
        assert all(ex.tenant_id == "tenant_1" for ex in results1)
        assert all(ex.tenant_id == "tenant_2" for ex in results2)

    @pytest.mark.asyncio
    async def test_find_similar_exceptions_ordering(self, test_session, test_data):
        """Test that results are ordered by created_at DESC."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.find_similar_exceptions("tenant_1", limit=100)
        
        # Verify ordering (newest first)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].created_at >= results[i + 1].created_at


class TestGetExceptionsByEntity:
    """Test get_exceptions_by_entity method."""

    @pytest.mark.asyncio
    async def test_get_exceptions_by_entity_success(self, test_session, test_data):
        """Test getting exceptions by entity."""
        repo = ExceptionRepository(test_session)
        
        # Get exceptions for CPTY-001
        results = await repo.get_exceptions_by_entity("tenant_1", "CPTY-001", limit=100)
        
        assert len(results) == 2  # 2 exceptions for CPTY-001
        assert all(ex.entity == "CPTY-001" for ex in results)
        assert all(ex.tenant_id == "tenant_1" for ex in results)

    @pytest.mark.asyncio
    async def test_get_exceptions_by_entity_different_entity(self, test_session, test_data):
        """Test getting exceptions for a different entity."""
        repo = ExceptionRepository(test_session)
        
        # Get exceptions for CPTY-002
        results = await repo.get_exceptions_by_entity("tenant_1", "CPTY-002", limit=100)
        
        assert len(results) == 1
        assert results[0].entity == "CPTY-002"

    @pytest.mark.asyncio
    async def test_get_exceptions_by_entity_limit(self, test_session, test_data):
        """Test that limit is respected."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_exceptions_by_entity("tenant_1", "CPTY-001", limit=1)
        
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_get_exceptions_by_entity_tenant_isolation(self, test_session, test_data):
        """Test that get_exceptions_by_entity respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        # Query for tenant_1
        results1 = await repo.get_exceptions_by_entity("tenant_1", "CPTY-001", limit=100)
        
        # Query for tenant_2 (same entity name but different tenant)
        results2 = await repo.get_exceptions_by_entity("tenant_2", "CPTY-001", limit=100)
        
        assert len(results1) == 2
        assert len(results2) == 0  # No CPTY-001 for tenant_2
        assert all(ex.tenant_id == "tenant_1" for ex in results1)

    @pytest.mark.asyncio
    async def test_get_exceptions_by_entity_ordering(self, test_session, test_data):
        """Test that results are ordered by created_at DESC."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_exceptions_by_entity("tenant_1", "CPTY-001", limit=100)
        
        # Verify ordering (newest first)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].created_at >= results[i + 1].created_at


class TestGetExceptionsBySourceSystem:
    """Test get_exceptions_by_source_system method."""

    @pytest.mark.asyncio
    async def test_get_exceptions_by_source_system_success(self, test_session, test_data):
        """Test getting exceptions by source system."""
        repo = ExceptionRepository(test_session)
        
        # Get exceptions from Murex
        results = await repo.get_exceptions_by_source_system("tenant_1", "Murex", limit=100)
        
        assert len(results) == 4  # 4 Murex exceptions for tenant_1
        assert all(ex.source_system == "Murex" for ex in results)
        assert all(ex.tenant_id == "tenant_1" for ex in results)

    @pytest.mark.asyncio
    async def test_get_exceptions_by_source_system_different_system(self, test_session, test_data):
        """Test getting exceptions from a different source system."""
        repo = ExceptionRepository(test_session)
        
        # Get exceptions from ClaimsApp
        results = await repo.get_exceptions_by_source_system("tenant_1", "ClaimsApp", limit=100)
        
        assert len(results) == 2
        assert all(ex.source_system == "ClaimsApp" for ex in results)

    @pytest.mark.asyncio
    async def test_get_exceptions_by_source_system_limit(self, test_session, test_data):
        """Test that limit is respected."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_exceptions_by_source_system("tenant_1", "Murex", limit=2)
        
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_get_exceptions_by_source_system_tenant_isolation(self, test_session, test_data):
        """Test that get_exceptions_by_source_system respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        # Query for tenant_1
        results1 = await repo.get_exceptions_by_source_system("tenant_1", "Murex", limit=100)
        
        # Query for tenant_2
        results2 = await repo.get_exceptions_by_source_system("tenant_2", "Murex", limit=100)
        
        assert len(results1) == 4
        assert len(results2) == 1
        assert all(ex.tenant_id == "tenant_1" for ex in results1)
        assert all(ex.tenant_id == "tenant_2" for ex in results2)

    @pytest.mark.asyncio
    async def test_get_exceptions_by_source_system_ordering(self, test_session, test_data):
        """Test that results are ordered by created_at DESC."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_exceptions_by_source_system("tenant_1", "Murex", limit=100)
        
        # Verify ordering (newest first)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].created_at >= results[i + 1].created_at


class TestGetImminentSlaBreaches:
    """Test get_imminent_sla_breaches method."""

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_success(self, test_session, test_data_with_sla):
        """Test getting exceptions with imminent SLA breaches."""
        repo = ExceptionRepository(test_session)
        
        # Get exceptions with SLA breaches within 60 minutes
        results = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=100)
        
        # Should return 2 exceptions (EX-SLA-1 and EX-SLA-2)
        # EX-SLA-3 is too far in future, EX-SLA-4 is resolved, EX-SLA-5 has no SLA
        assert len(results) == 2
        assert all(ex.tenant_id == "tenant_1" for ex in results)
        assert all(ex.status in [ExceptionStatus.OPEN, ExceptionStatus.ANALYZING] for ex in results)
        assert all(ex.sla_deadline is not None for ex in results)

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_only_open_or_analyzing(self, test_session, test_data_with_sla):
        """Test that only OPEN or ANALYZING exceptions are returned."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=100)
        
        # Verify all have correct status
        assert all(
            ex.status == ExceptionStatus.OPEN or ex.status == ExceptionStatus.ANALYZING
            for ex in results
        )
        
        # Verify resolved exceptions are not included
        exception_ids = [ex.exception_id for ex in results]
        assert "EX-SLA-4" not in exception_ids  # Resolved exception

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_time_window(self, test_session, test_data_with_sla):
        """Test that time window filtering works correctly."""
        repo = ExceptionRepository(test_session)
        
        # Get exceptions within 30 minutes
        results_30min = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=30, limit=100)
        
        # Get exceptions within 60 minutes
        results_60min = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=100)
        
        # 60 minutes should return more or equal results
        assert len(results_60min) >= len(results_30min)

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_ordering(self, test_session, test_data_with_sla):
        """Test that results are ordered by sla_deadline ASC (most urgent first)."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=100)
        
        # Verify ordering (most urgent first)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].sla_deadline <= results[i + 1].sla_deadline

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_limit(self, test_session, test_data_with_sla):
        """Test that limit is respected."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=1)
        
        assert len(results) <= 1

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_tenant_isolation(self, test_session):
        """Test that get_imminent_sla_breaches respects tenant isolation."""
        repo = ExceptionRepository(test_session)
        
        now = datetime.now(timezone.utc)
        
        # Create exceptions for both tenants
        exc1_data = ExceptionCreateDTO(
            exception_id="EX-T1-SLA",
            tenant_id="tenant_1",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            sla_deadline=now + timedelta(minutes=30),
        )
        exc1 = await repo.create_exception("tenant_1", exc1_data)
        exc1.sla_deadline = exc1_data.sla_deadline
        
        exc2_data = ExceptionCreateDTO(
            exception_id="EX-T2-SLA",
            tenant_id="tenant_2",
            domain="Finance",
            type="TradeException",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="Murex",
            sla_deadline=now + timedelta(minutes=30),
        )
        exc2 = await repo.create_exception("tenant_2", exc2_data)
        exc2.sla_deadline = exc2_data.sla_deadline
        
        await test_session.flush()
        await test_session.refresh(exc1)
        await test_session.refresh(exc2)
        await test_session.commit()
        
        # Query for tenant_1
        results1 = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=100)
        
        # Query for tenant_2
        results2 = await repo.get_imminent_sla_breaches("tenant_2", within_minutes=60, limit=100)
        
        assert len(results1) == 1
        assert len(results2) == 1
        assert results1[0].tenant_id == "tenant_1"
        assert results2[0].tenant_id == "tenant_2"

    @pytest.mark.asyncio
    async def test_get_imminent_sla_breaches_no_sla_deadline(self, test_session, test_data_with_sla):
        """Test that exceptions without SLA deadline are not returned."""
        repo = ExceptionRepository(test_session)
        
        results = await repo.get_imminent_sla_breaches("tenant_1", within_minutes=60, limit=100)
        
        # Verify all have SLA deadlines
        assert all(ex.sla_deadline is not None for ex in results)
        
        # Verify exception without SLA is not included
        exception_ids = [ex.exception_id for ex in results]
        assert "EX-SLA-5" not in exception_ids  # No SLA deadline

