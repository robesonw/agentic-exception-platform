"""
Unit tests for DomainPackRepository.

Tests cover:
- Version creation
- Listing by domain
- Retrieving latest version
- Version ordering logic
"""

import pytest
from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.infrastructure.db.models import DomainPackVersion
from src.infrastructure.repositories.domain_pack_repository import DomainPackRepository

# Create test base
TestBase = declarative_base()


# Define a minimal DomainPackVersion model for SQLite testing
class TestDomainPackVersion(TestBase):
    __tablename__ = "domain_pack_version"
    id = Column(Integer, primary_key=True, autoincrement=True)
    domain = Column(String, nullable=False, index=True)
    version = Column(Integer, nullable=False)
    pack_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)


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
            CREATE TABLE IF NOT EXISTS domain_pack_version (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                domain TEXT NOT NULL,
                version INTEGER NOT NULL,
                pack_json TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                UNIQUE(domain, version)
            );
            CREATE INDEX IF NOT EXISTS ix_domain_pack_version_domain ON domain_pack_version(domain);
            """
            )
        )
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS domain_pack_version;"))
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
async def domain_pack_repo(test_session: AsyncSession) -> DomainPackRepository:
    """Provide a DomainPackRepository instance for tests."""
    return DomainPackRepository(test_session)


@pytest.fixture
async def setup_domain_packs(domain_pack_repo: DomainPackRepository):
    """Set up sample domain packs for testing."""
    # Finance domain packs
    pack1 = DomainPackVersion(
        domain="Finance",
        version=1,
        pack_json={"domainName": "Finance", "version": "1.0.0", "entities": {}},
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    pack2 = DomainPackVersion(
        domain="Finance",
        version=2,
        pack_json={"domainName": "Finance", "version": "2.0.0", "entities": {}},
        created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
    )
    pack3 = DomainPackVersion(
        domain="Finance",
        version=3,
        pack_json={"domainName": "Finance", "version": "3.0.0", "entities": {}},
        created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
    )
    
    # Healthcare domain packs
    pack4 = DomainPackVersion(
        domain="Healthcare",
        version=1,
        pack_json={"domainName": "Healthcare", "version": "1.0.0", "entities": {}},
        created_at=datetime(2023, 1, 15, tzinfo=timezone.utc),
    )
    pack5 = DomainPackVersion(
        domain="Healthcare",
        version=2,
        pack_json={"domainName": "Healthcare", "version": "2.0.0", "entities": {}},
        created_at=datetime(2023, 2, 15, tzinfo=timezone.utc),
    )
    
    domain_pack_repo.session.add_all([pack1, pack2, pack3, pack4, pack5])
    await domain_pack_repo.session.commit()
    
    # Refresh all packs to ensure they're loaded
    for pack in [pack1, pack2, pack3, pack4, pack5]:
        await domain_pack_repo.session.refresh(pack)


class TestDomainPackRepository:
    @pytest.mark.asyncio
    async def test_get_domain_pack(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test retrieving a domain pack by domain and version."""
        pack = await domain_pack_repo.get_domain_pack("Finance", 2)
        assert pack is not None
        assert pack.domain == "Finance"
        assert pack.version == 2
        assert pack.pack_json["version"] == "2.0.0"

        not_found = await domain_pack_repo.get_domain_pack("Finance", 99)
        assert not_found is None

        with pytest.raises(ValueError, match="domain is required"):
            await domain_pack_repo.get_domain_pack("", 1)

        with pytest.raises(ValueError, match="version must be >= 1"):
            await domain_pack_repo.get_domain_pack("Finance", 0)

    @pytest.mark.asyncio
    async def test_get_latest_domain_pack(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test retrieving the latest domain pack for a domain."""
        latest = await domain_pack_repo.get_latest_domain_pack("Finance")
        assert latest is not None
        assert latest.domain == "Finance"
        assert latest.version == 3  # Highest version
        assert latest.pack_json["version"] == "3.0.0"

        latest_healthcare = await domain_pack_repo.get_latest_domain_pack("Healthcare")
        assert latest_healthcare is not None
        assert latest_healthcare.domain == "Healthcare"
        assert latest_healthcare.version == 2

        not_found = await domain_pack_repo.get_latest_domain_pack("NonExistent")
        assert not_found is None

        with pytest.raises(ValueError, match="domain is required"):
            await domain_pack_repo.get_latest_domain_pack("")

    @pytest.mark.asyncio
    async def test_get_latest_domain_pack_version_ordering(self, domain_pack_repo: DomainPackRepository):
        """Test that latest pack uses highest version number (not created_at)."""
        # Create packs with same version but different created_at
        # This shouldn't happen in practice, but tests the ordering logic
        pack1 = DomainPackVersion(
            domain="TestDomain",
            version=1,
            pack_json={"domainName": "TestDomain", "version": "1.0.0"},
            created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
        )
        pack2 = DomainPackVersion(
            domain="TestDomain",
            version=2,
            pack_json={"domainName": "TestDomain", "version": "2.0.0"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),  # Older than pack1
        )
        
        domain_pack_repo.session.add_all([pack1, pack2])
        await domain_pack_repo.session.commit()

        # Latest should be version 2 (higher version), not version 1 (newer created_at)
        latest = await domain_pack_repo.get_latest_domain_pack("TestDomain")
        assert latest is not None
        assert latest.version == 2

    @pytest.mark.asyncio
    async def test_create_domain_pack_version(self, domain_pack_repo: DomainPackRepository):
        """Test creating a new domain pack version."""
        pack_json = {
            "domainName": "Finance",
            "version": "1.0.0",
            "entities": {"TradeOrder": {"keys": ["orderId"]}},
        }
        
        created = await domain_pack_repo.create_domain_pack_version(
            domain="Finance",
            version=1,
            pack_json=pack_json,
        )
        
        assert created is not None
        assert created.domain == "Finance"
        assert created.version == 1
        assert created.pack_json == pack_json
        assert created.id is not None

        # Verify it can be retrieved
        retrieved = await domain_pack_repo.get_domain_pack("Finance", 1)
        assert retrieved is not None
        assert retrieved.pack_json == pack_json

    @pytest.mark.asyncio
    async def test_create_domain_pack_version_duplicate(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test that creating a duplicate version raises an error."""
        pack_json = {"domainName": "Finance", "version": "2.0.0"}

        with pytest.raises(ValueError, match="already exists"):
            await domain_pack_repo.create_domain_pack_version(
                domain="Finance",
                version=2,  # Already exists
                pack_json=pack_json,
            )

    @pytest.mark.asyncio
    async def test_create_domain_pack_version_validation(self, domain_pack_repo: DomainPackRepository):
        """Test validation errors when creating domain pack version."""
        with pytest.raises(ValueError, match="domain is required"):
            await domain_pack_repo.create_domain_pack_version("", 1, {})

        with pytest.raises(ValueError, match="version must be >= 1"):
            await domain_pack_repo.create_domain_pack_version("Finance", 0, {})

        with pytest.raises(ValueError, match="pack_json is required"):
            await domain_pack_repo.create_domain_pack_version("Finance", 1, {})

    @pytest.mark.asyncio
    async def test_list_domain_packs_all(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test listing all domain packs."""
        packs = await domain_pack_repo.list_domain_packs()
        
        assert len(packs) == 5
        # Should be ordered by domain (ascending), then version (descending)
        assert packs[0].domain == "Finance"
        assert packs[0].version == 3  # Latest Finance version first
        assert packs[1].domain == "Finance"
        assert packs[1].version == 2
        assert packs[2].domain == "Finance"
        assert packs[2].version == 1
        assert packs[3].domain == "Healthcare"
        assert packs[3].version == 2
        assert packs[4].domain == "Healthcare"
        assert packs[4].version == 1

    @pytest.mark.asyncio
    async def test_list_domain_packs_by_domain(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test listing domain packs filtered by domain."""
        finance_packs = await domain_pack_repo.list_domain_packs(domain="Finance")
        
        assert len(finance_packs) == 3
        assert all(pack.domain == "Finance" for pack in finance_packs)
        # Should be ordered by version (descending)
        assert finance_packs[0].version == 3
        assert finance_packs[1].version == 2
        assert finance_packs[2].version == 1

        healthcare_packs = await domain_pack_repo.list_domain_packs(domain="Healthcare")
        assert len(healthcare_packs) == 2
        assert all(pack.domain == "Healthcare" for pack in healthcare_packs)

        non_existent = await domain_pack_repo.list_domain_packs(domain="NonExistent")
        assert len(non_existent) == 0

    @pytest.mark.asyncio
    async def test_list_domain_packs_validation(self, domain_pack_repo: DomainPackRepository):
        """Test validation errors when listing domain packs."""
        with pytest.raises(ValueError, match="domain cannot be empty"):
            await domain_pack_repo.list_domain_packs(domain="")

    @pytest.mark.asyncio
    async def test_get_by_id(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test get_by_id method (AbstractBaseRepository interface)."""
        # Get a pack to find its ID
        pack = await domain_pack_repo.get_domain_pack("Finance", 1)
        assert pack is not None
        pack_id = pack.id

        retrieved = await domain_pack_repo.get_by_id(str(pack_id), tenant_id="ignored")
        assert retrieved is not None
        assert retrieved.id == pack_id
        assert retrieved.domain == "Finance"
        assert retrieved.version == 1

        not_found = await domain_pack_repo.get_by_id("99999", tenant_id="ignored")
        assert not_found is None

        invalid_id = await domain_pack_repo.get_by_id("not_a_number", tenant_id="ignored")
        assert invalid_id is None

    @pytest.mark.asyncio
    async def test_list_by_tenant(self, domain_pack_repo: DomainPackRepository, setup_domain_packs):
        """Test list_by_tenant method (AbstractBaseRepository interface)."""
        # Domain packs are global, so tenant_id is ignored
        result = await domain_pack_repo.list_by_tenant(
            tenant_id="any_tenant",
            page=1,
            page_size=3,
        )
        
        assert result.total == 5
        assert len(result.items) == 3
        assert result.page == 1
        assert result.page_size == 3
        assert result.total_pages == 2

        # Test with domain filter
        result_filtered = await domain_pack_repo.list_by_tenant(
            tenant_id="any_tenant",
            page=1,
            page_size=10,
            domain="Finance",
        )
        
        assert result_filtered.total == 3
        assert all(pack.domain == "Finance" for pack in result_filtered.items)

