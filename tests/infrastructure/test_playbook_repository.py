"""
Unit tests for PlaybookRepository.

Tests cover:
- CRUD operations
- Filtering (name, version, created_from/created_to)
- Multi-tenant isolation
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.infrastructure.db.models import Playbook
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.repository.dto import PlaybookCreateDTO, PlaybookFilter

# Create test base
TestBase = declarative_base()


# Define minimal models for SQLite testing
class TestTenant(TestBase):
    __tablename__ = "tenant"
    tenant_id = Column(String, primary_key=True)
    name = Column(String, nullable=False)


class TestPlaybook(TestBase):
    __tablename__ = "playbook"
    playbook_id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    version = Column(Integer, nullable=False)
    conditions = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    tenant = relationship("TestTenant", backref="playbooks")


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
            text(
                """
            CREATE TABLE IF NOT EXISTS tenant (
                tenant_id TEXT PRIMARY KEY,
                name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS playbook (
                playbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                conditions TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            CREATE INDEX IF NOT EXISTS ix_playbook_tenant_id ON playbook(tenant_id);
            """
            )
        )
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS playbook;"))
        await conn.execute(text("DROP TABLE IF EXISTS tenant;"))
    await engine.dispose()


@pytest.fixture
async def test_session(test_engine):
    """Create an async session for tests."""
    async_session = sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )
    async with async_session() as session:
        yield session


@pytest.fixture
async def setup_tenants(test_session: AsyncSession):
    """Set up sample tenants for testing."""
    from sqlalchemy import text
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('tenant_001', 'Finance Tenant')")
    )
    await test_session.execute(
        text("INSERT INTO tenant (tenant_id, name) VALUES ('tenant_002', 'Healthcare Tenant')")
    )
    await test_session.commit()


@pytest.fixture
async def playbook_repo(test_session: AsyncSession) -> PlaybookRepository:
    """Provide a PlaybookRepository instance for tests."""
    return PlaybookRepository(test_session)


@pytest.fixture
async def setup_playbooks(playbook_repo: PlaybookRepository, setup_tenants):
    """Set up sample playbooks for testing."""
    # Tenant 001 playbooks
    playbook1 = Playbook(
        tenant_id="tenant_001",
        name="PaymentFailurePlaybook",
        version=1,
        conditions={"exception_type": "PaymentFailure"},
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    playbook2 = Playbook(
        tenant_id="tenant_001",
        name="FraudAlertPlaybook",
        version=1,
        conditions={"exception_type": "FraudAlert"},
        created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
    )
    playbook3 = Playbook(
        tenant_id="tenant_001",
        name="PaymentFailurePlaybook",
        version=2,
        conditions={"exception_type": "PaymentFailure", "severity": "HIGH"},
        created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
    )
    
    # Tenant 002 playbooks
    playbook4 = Playbook(
        tenant_id="tenant_002",
        name="PatientDataMismatchPlaybook",
        version=1,
        conditions={"exception_type": "PatientDataMismatch"},
        created_at=datetime(2023, 1, 15, tzinfo=timezone.utc),
    )
    playbook5 = Playbook(
        tenant_id="tenant_002",
        name="MedicationErrorPlaybook",
        version=1,
        conditions={"exception_type": "MedicationError"},
        created_at=datetime(2023, 2, 15, tzinfo=timezone.utc),
    )
    
    playbook_repo.session.add_all([playbook1, playbook2, playbook3, playbook4, playbook5])
    await playbook_repo.session.commit()
    
    # Refresh all playbooks to ensure they're loaded
    for playbook in [playbook1, playbook2, playbook3, playbook4, playbook5]:
        await playbook_repo.session.refresh(playbook)


class TestPlaybookRepositoryCRUD:
    """Test CRUD operations."""

    @pytest.mark.asyncio
    async def test_create_playbook(self, playbook_repo: PlaybookRepository, setup_tenants):
        """Test creating a new playbook."""
        playbook_data = PlaybookCreateDTO(
            name="TestPlaybook",
            version=1,
            conditions={"exception_type": "TestException"},
        )
        
        created = await playbook_repo.create_playbook("tenant_001", playbook_data)
        
        assert created is not None
        assert created.tenant_id == "tenant_001"
        assert created.name == "TestPlaybook"
        assert created.version == 1
        assert created.conditions == {"exception_type": "TestException"}
        assert created.playbook_id is not None

    @pytest.mark.asyncio
    async def test_get_playbook(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test retrieving a playbook by ID."""
        # Get a playbook to find its ID
        all_playbooks = await playbook_repo.list_playbooks("tenant_001")
        assert len(all_playbooks) > 0
        playbook_id = all_playbooks[0].playbook_id

        retrieved = await playbook_repo.get_playbook(playbook_id, "tenant_001")
        assert retrieved is not None
        assert retrieved.playbook_id == playbook_id
        assert retrieved.tenant_id == "tenant_001"

        not_found = await playbook_repo.get_playbook(99999, "tenant_001")
        assert not_found is None

        with pytest.raises(ValueError, match="tenant_id is required"):
            await playbook_repo.get_playbook(1, "")

        with pytest.raises(ValueError, match="playbook_id must be >= 1"):
            await playbook_repo.get_playbook(0, "tenant_001")

    @pytest.mark.asyncio
    async def test_list_playbooks(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test listing playbooks for a tenant."""
        tenant1_playbooks = await playbook_repo.list_playbooks("tenant_001")
        
        assert len(tenant1_playbooks) == 3
        assert all(pb.tenant_id == "tenant_001" for pb in tenant1_playbooks)
        # Should be ordered by created_at descending
        assert tenant1_playbooks[0].created_at >= tenant1_playbooks[1].created_at

        tenant2_playbooks = await playbook_repo.list_playbooks("tenant_002")
        assert len(tenant2_playbooks) == 2
        assert all(pb.tenant_id == "tenant_002" for pb in tenant2_playbooks)

        non_existent = await playbook_repo.list_playbooks("non_existent_tenant")
        assert len(non_existent) == 0

        with pytest.raises(ValueError, match="tenant_id is required"):
            await playbook_repo.list_playbooks("")


class TestPlaybookRepositoryFiltering:
    """Test filtering capabilities."""

    @pytest.mark.asyncio
    async def test_filter_by_name(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test filtering playbooks by name."""
        filters = PlaybookFilter(name="Payment")
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 2
        assert all("Payment" in pb.name for pb in playbooks)

        filters = PlaybookFilter(name="Fraud")
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 1
        assert playbooks[0].name == "FraudAlertPlaybook"

        filters = PlaybookFilter(name="NonExistent")
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        assert len(playbooks) == 0

    @pytest.mark.asyncio
    async def test_filter_by_version(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test filtering playbooks by version."""
        filters = PlaybookFilter(version=1)
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 2
        assert all(pb.version == 1 for pb in playbooks)

        filters = PlaybookFilter(version=2)
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 1
        assert playbooks[0].version == 2

    @pytest.mark.asyncio
    async def test_filter_by_created_from(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test filtering playbooks by created_from date."""
        from_date = datetime(2023, 2, 1, tzinfo=timezone.utc)
        filters = PlaybookFilter(created_from=from_date)
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 2
        assert all(pb.created_at >= from_date for pb in playbooks)

    @pytest.mark.asyncio
    async def test_filter_by_created_to(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test filtering playbooks by created_to date."""
        to_date = datetime(2023, 2, 1, tzinfo=timezone.utc)
        filters = PlaybookFilter(created_to=to_date)
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 2
        assert all(pb.created_at <= to_date for pb in playbooks)

    @pytest.mark.asyncio
    async def test_filter_combined(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test combining multiple filters."""
        filters = PlaybookFilter(
            name="Payment",
            version=1,
        )
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 1
        assert playbooks[0].name == "PaymentFailurePlaybook"
        assert playbooks[0].version == 1

        filters = PlaybookFilter(
            name="Payment",
            created_from=datetime(2023, 2, 1, tzinfo=timezone.utc),
        )
        playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        
        assert len(playbooks) == 1
        assert playbooks[0].version == 2  # Only the newer Payment playbook


class TestPlaybookRepositoryTenantIsolation:
    """Test tenant isolation enforcement."""

    @pytest.mark.asyncio
    async def test_tenant_isolation_list(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test that tenants can only see their own playbooks."""
        tenant1_playbooks = await playbook_repo.list_playbooks("tenant_001")
        assert len(tenant1_playbooks) == 3
        assert all(pb.tenant_id == "tenant_001" for pb in tenant1_playbooks)
        
        tenant2_playbooks = await playbook_repo.list_playbooks("tenant_002")
        assert len(tenant2_playbooks) == 2
        assert all(pb.tenant_id == "tenant_002" for pb in tenant2_playbooks)

    @pytest.mark.asyncio
    async def test_tenant_isolation_get(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test that tenants cannot access other tenants' playbooks."""
        # Get tenant_002's playbook ID
        tenant2_playbooks = await playbook_repo.list_playbooks("tenant_002")
        assert len(tenant2_playbooks) > 0
        tenant2_playbook_id = tenant2_playbooks[0].playbook_id

        # Tenant 001 should not be able to retrieve Tenant 002's playbook
        retrieved = await playbook_repo.get_playbook(tenant2_playbook_id, "tenant_001")
        assert retrieved is None  # Should return None due to tenant isolation

        # Tenant 002 should be able to retrieve their own playbook
        retrieved = await playbook_repo.get_playbook(tenant2_playbook_id, "tenant_002")
        assert retrieved is not None
        assert retrieved.tenant_id == "tenant_002"

    @pytest.mark.asyncio
    async def test_tenant_isolation_get_by_id(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test get_by_id method with tenant isolation."""
        # Get tenant_001's playbook ID
        tenant1_playbooks = await playbook_repo.list_playbooks("tenant_001")
        assert len(tenant1_playbooks) > 0
        playbook_id = tenant1_playbooks[0].playbook_id

        # Should retrieve with correct tenant_id
        retrieved = await playbook_repo.get_by_id(str(playbook_id), tenant_id="tenant_001")
        assert retrieved is not None
        assert retrieved.tenant_id == "tenant_001"

        # Should return None with wrong tenant_id (tenant isolation)
        retrieved_wrong_tenant = await playbook_repo.get_by_id(str(playbook_id), tenant_id="tenant_002")
        assert retrieved_wrong_tenant is None

    @pytest.mark.asyncio
    async def test_tenant_isolation_list_by_tenant(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test list_by_tenant method with tenant isolation."""
        # Tenant 001 should only see their own playbooks
        result = await playbook_repo.list_by_tenant(
            tenant_id="tenant_001",
            page=1,
            page_size=10,
        )
        
        assert result.total == 3
        assert all(pb.tenant_id == "tenant_001" for pb in result.items)

        # Tenant 002 should only see their own playbooks
        result = await playbook_repo.list_by_tenant(
            tenant_id="tenant_002",
            page=1,
            page_size=10,
        )
        
        assert result.total == 2
        assert all(pb.tenant_id == "tenant_002" for pb in result.items)

    @pytest.mark.asyncio
    async def test_tenant_isolation_filtering(self, playbook_repo: PlaybookRepository, setup_playbooks):
        """Test that filters are applied within tenant scope."""
        # Both tenants have playbooks, but filters should only return tenant_001's
        filters = PlaybookFilter(name="Payment")
        tenant1_playbooks = await playbook_repo.list_playbooks("tenant_001", filters=filters)
        assert len(tenant1_playbooks) == 2
        assert all(pb.tenant_id == "tenant_001" for pb in tenant1_playbooks)

        # Tenant 002 should have no Payment playbooks
        tenant2_playbooks = await playbook_repo.list_playbooks("tenant_002", filters=filters)
        assert len(tenant2_playbooks) == 0

