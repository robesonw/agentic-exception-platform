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

from src.infrastructure.db.models import Playbook, PlaybookStep
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
    # SQLite requires separate execute calls for each statement
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE IF NOT EXISTS tenant (tenant_id TEXT PRIMARY KEY, name TEXT NOT NULL);"))
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS playbook (
                playbook_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                version INTEGER NOT NULL,
                conditions TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (tenant_id) REFERENCES tenant(tenant_id) ON DELETE CASCADE
            );
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_playbook_tenant_id ON playbook(tenant_id);"))
        await conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS playbook_step (
                step_id INTEGER PRIMARY KEY AUTOINCREMENT,
                playbook_id INTEGER NOT NULL,
                step_order INTEGER NOT NULL,
                name TEXT NOT NULL,
                action_type TEXT NOT NULL,
                params TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
                FOREIGN KEY (playbook_id) REFERENCES playbook(playbook_id) ON DELETE CASCADE
            );
            """
            )
        )
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_playbook_step_playbook_id ON playbook_step(playbook_id);"))
        await conn.execute(text("CREATE INDEX IF NOT EXISTS ix_playbook_step_step_order ON playbook_step(step_order);"))
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("DROP TABLE IF EXISTS playbook_step;"))
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


class TestPlaybookRepositoryP7_6:
    """Test Phase 7 P7-6 enhancements: get_candidate_playbooks and get_playbook_with_steps."""
    
    @pytest.fixture
    async def setup_playbooks_with_conditions(self, playbook_repo: PlaybookRepository, setup_tenants):
        """Set up playbooks with various conditions for testing."""
        # Playbooks with different condition structures
        playbook1 = Playbook(
            tenant_id="tenant_001",
            name="DomainSpecificPlaybook",
            version=1,
            conditions={
                "match": {
                    "domain": "Finance",
                    "exception_type": "PaymentFailure",
                    "severity_in": ["HIGH", "CRITICAL"],
                    "priority": 10
                }
            },
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        playbook2 = Playbook(
            tenant_id="tenant_001",
            name="RootConditionsPlaybook",
            version=1,
            conditions={
                "domain": "Finance",
                "exception_type": "FraudAlert",
                "severity": "CRITICAL",
                "priority": 5
            },
            created_at=datetime(2023, 2, 1, tzinfo=timezone.utc),
        )
        playbook3 = Playbook(
            tenant_id="tenant_001",
            name="SLAPlaybook",
            version=1,
            conditions={
                "match": {
                    "exception_type": "SettlementFail",
                    "sla_minutes_remaining_lt": 60,
                    "priority": 15
                }
            },
            created_at=datetime(2023, 3, 1, tzinfo=timezone.utc),
        )
        playbook4 = Playbook(
            tenant_id="tenant_001",
            name="PolicyTagsPlaybook",
            version=1,
            conditions={
                "match": {
                    "exception_type": "ComplianceIssue",
                    "policy_tags": ["regulatory", "audit"],
                    "priority": 8
                }
            },
            created_at=datetime(2023, 4, 1, tzinfo=timezone.utc),
        )
        playbook5 = Playbook(
            tenant_id="tenant_002",
            name="OtherTenantPlaybook",
            version=1,
            conditions={
                "match": {
                    "domain": "Healthcare",
                    "exception_type": "PatientDataMismatch"
                }
            },
            created_at=datetime(2023, 1, 15, tzinfo=timezone.utc),
        )
        
        playbook_repo.session.add_all([playbook1, playbook2, playbook3, playbook4, playbook5])
        await playbook_repo.session.commit()
        
        # Refresh all playbooks
        for playbook in [playbook1, playbook2, playbook3, playbook4, playbook5]:
            await playbook_repo.session.refresh(playbook)
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_no_filters(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test get_candidate_playbooks with no filters returns all playbooks."""
        candidates = await playbook_repo.get_candidate_playbooks("tenant_001")
        
        assert len(candidates) == 4
        assert all(pb.tenant_id == "tenant_001" for pb in candidates)
        # Should be ordered by priority desc, then created_at desc
        # playbook3 (priority 15) should be first, then playbook1 (priority 10), etc.
        assert candidates[0].name == "SLAPlaybook"  # priority 15
        assert candidates[1].name == "DomainSpecificPlaybook"  # priority 10
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_filter_by_domain(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test filtering candidate playbooks by domain."""
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            domain="Finance"
        )
        
        assert len(candidates) == 2
        assert all(pb.tenant_id == "tenant_001" for pb in candidates)
        names = [pb.name for pb in candidates]
        assert "DomainSpecificPlaybook" in names
        assert "RootConditionsPlaybook" in names
        assert "SLAPlaybook" not in names
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_filter_by_exception_type(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test filtering candidate playbooks by exception_type."""
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            exception_type="PaymentFailure"
        )
        
        assert len(candidates) == 1
        assert candidates[0].name == "DomainSpecificPlaybook"
        assert candidates[0].tenant_id == "tenant_001"
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_filter_by_severity(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test filtering candidate playbooks by severity."""
        # Filter by severity_in array
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            severity="HIGH"
        )
        
        assert len(candidates) == 1
        assert candidates[0].name == "DomainSpecificPlaybook"
        
        # Filter by single severity
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            severity="CRITICAL"
        )
        
        assert len(candidates) == 2
        names = [pb.name for pb in candidates]
        assert "DomainSpecificPlaybook" in names
        assert "RootConditionsPlaybook" in names
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_filter_by_sla(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test filtering candidate playbooks by SLA condition."""
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            sla_minutes_remaining=30
        )
        
        assert len(candidates) == 1
        assert candidates[0].name == "SLAPlaybook"
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_filter_by_policy_tags(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test filtering candidate playbooks by policy_tags."""
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            policy_tags=["regulatory", "audit"]
        )
        
        assert len(candidates) == 1
        assert candidates[0].name == "PolicyTagsPlaybook"
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_combined_filters(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test combining multiple filters."""
        candidates = await playbook_repo.get_candidate_playbooks(
            "tenant_001",
            domain="Finance",
            exception_type="PaymentFailure",
            severity="HIGH"
        )
        
        assert len(candidates) == 1
        assert candidates[0].name == "DomainSpecificPlaybook"
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_tenant_isolation(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test that get_candidate_playbooks respects tenant isolation."""
        tenant1_candidates = await playbook_repo.get_candidate_playbooks("tenant_001")
        tenant2_candidates = await playbook_repo.get_candidate_playbooks("tenant_002")
        
        assert len(tenant1_candidates) == 4
        assert len(tenant2_candidates) == 1
        assert all(pb.tenant_id == "tenant_001" for pb in tenant1_candidates)
        assert all(pb.tenant_id == "tenant_002" for pb in tenant2_candidates)
    
    @pytest.mark.asyncio
    async def test_get_candidate_playbooks_ordering(
        self, playbook_repo: PlaybookRepository, setup_playbooks_with_conditions
    ):
        """Test that candidates are ordered by priority desc, then created_at desc."""
        candidates = await playbook_repo.get_candidate_playbooks("tenant_001")
        
        # Extract priorities
        def get_priority(pb):
            conditions = pb.conditions or {}
            match_conditions = conditions.get("match", conditions)
            return match_conditions.get("priority", 0)
        
        # Verify ordering: priority desc, then created_at desc
        for i in range(len(candidates) - 1):
            priority_i = get_priority(candidates[i])
            priority_j = get_priority(candidates[i + 1])
            
            if priority_i == priority_j:
                # If priorities equal, created_at should be desc (newer first)
                assert candidates[i].created_at >= candidates[i + 1].created_at
            else:
                # Priority should be descending
                assert priority_i >= priority_j
    
    @pytest.fixture
    async def setup_playbook_with_steps(self, playbook_repo: PlaybookRepository, setup_tenants, test_session):
        """Set up a playbook with steps for testing."""
        # Create playbook
        playbook = Playbook(
            tenant_id="tenant_001",
            name="TestPlaybookWithSteps",
            version=1,
            conditions={"exception_type": "TestException"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        test_session.add(playbook)
        await test_session.commit()
        await test_session.refresh(playbook)
        
        # Create steps (out of order to test ordering)
        step1 = PlaybookStep(
            playbook_id=playbook.playbook_id,
            step_order=1,
            name="Step 1",
            action_type="notify",
            params={"message": "First step"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        step2 = PlaybookStep(
            playbook_id=playbook.playbook_id,
            step_order=2,
            name="Step 2",
            action_type="assign_owner",
            params={"user_id": "user_123"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        step3 = PlaybookStep(
            playbook_id=playbook.playbook_id,
            step_order=3,
            name="Step 3",
            action_type="set_status",
            params={"status": "RESOLVED"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        
        test_session.add_all([step1, step2, step3])
        await test_session.commit()
        
        return playbook.playbook_id
    
    @pytest.mark.asyncio
    async def test_get_playbook_with_steps(
        self, playbook_repo: PlaybookRepository, setup_playbook_with_steps
    ):
        """Test retrieving playbook with ordered steps."""
        playbook_id = setup_playbook_with_steps
        
        playbook, steps = await playbook_repo.get_playbook_with_steps(playbook_id, "tenant_001")
        
        assert playbook is not None
        assert playbook.playbook_id == playbook_id
        assert playbook.tenant_id == "tenant_001"
        assert playbook.name == "TestPlaybookWithSteps"
        
        assert len(steps) == 3
        # Steps should be ordered by step_order ascending
        assert steps[0].step_order == 1
        assert steps[0].name == "Step 1"
        assert steps[1].step_order == 2
        assert steps[1].name == "Step 2"
        assert steps[2].step_order == 3
        assert steps[2].name == "Step 3"
    
    @pytest.mark.asyncio
    async def test_get_playbook_with_steps_tenant_isolation(
        self, playbook_repo: PlaybookRepository, setup_playbook_with_steps
    ):
        """Test that get_playbook_with_steps respects tenant isolation."""
        playbook_id = setup_playbook_with_steps
        
        # Correct tenant should work
        playbook, steps = await playbook_repo.get_playbook_with_steps(playbook_id, "tenant_001")
        assert playbook is not None
        
        # Wrong tenant should raise ValueError
        with pytest.raises(ValueError, match="not found for tenant"):
            await playbook_repo.get_playbook_with_steps(playbook_id, "tenant_002")
    
    @pytest.mark.asyncio
    async def test_get_playbook_with_steps_not_found(
        self, playbook_repo: PlaybookRepository, setup_tenants
    ):
        """Test get_playbook_with_steps when playbook doesn't exist."""
        with pytest.raises(ValueError, match="not found for tenant"):
            await playbook_repo.get_playbook_with_steps(99999, "tenant_001")
    
    @pytest.mark.asyncio
    async def test_get_playbook_with_steps_no_steps(
        self, playbook_repo: PlaybookRepository, setup_tenants, test_session
    ):
        """Test get_playbook_with_steps when playbook has no steps."""
        # Create playbook without steps
        playbook = Playbook(
            tenant_id="tenant_001",
            name="EmptyPlaybook",
            version=1,
            conditions={"exception_type": "TestException"},
            created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
        )
        test_session.add(playbook)
        await test_session.commit()
        await test_session.refresh(playbook)
        
        playbook, steps = await playbook_repo.get_playbook_with_steps(playbook.playbook_id, "tenant_001")
        
        assert playbook is not None
        assert len(steps) == 0

