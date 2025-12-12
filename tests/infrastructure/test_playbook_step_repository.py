"""
Unit tests for PlaybookStepRepository.

Tests cover:
- Creating steps
- Reordering steps
- Preventing cross-tenant leakage
- Step ordering stability
"""

import pytest
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

from src.infrastructure.db.models import Playbook, PlaybookStep
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
from src.repository.dto import PlaybookStepCreateDTO

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


class TestPlaybookStep(TestBase):
    __tablename__ = "playbook_step"
    step_id = Column(Integer, primary_key=True, autoincrement=True)
    playbook_id = Column(Integer, ForeignKey("playbook.playbook_id", ondelete="CASCADE"), nullable=False, index=True)
    step_order = Column(Integer, nullable=False, index=True)
    name = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    params = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    
    playbook = relationship("TestPlaybook", backref="steps")


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
            CREATE INDEX IF NOT EXISTS ix_playbook_step_playbook_id ON playbook_step(playbook_id);
            CREATE INDEX IF NOT EXISTS ix_playbook_step_step_order ON playbook_step(step_order);
            """
            )
        )
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
async def setup_playbooks(test_session: AsyncSession):
    """Set up sample playbooks for testing."""
    playbook1 = Playbook(
        tenant_id="tenant_001",
        name="PaymentFailurePlaybook",
        version=1,
        conditions={"exception_type": "PaymentFailure"},
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    playbook2 = Playbook(
        tenant_id="tenant_002",
        name="PatientDataMismatchPlaybook",
        version=1,
        conditions={"exception_type": "PatientDataMismatch"},
        created_at=datetime(2023, 1, 1, tzinfo=timezone.utc),
    )
    test_session.add_all([playbook1, playbook2])
    await test_session.commit()
    await test_session.refresh(playbook1)
    await test_session.refresh(playbook2)
    return {"playbook1": playbook1, "playbook2": playbook2}


@pytest.fixture
async def playbook_step_repo(test_session: AsyncSession) -> PlaybookStepRepository:
    """Provide a PlaybookStepRepository instance for tests."""
    return PlaybookStepRepository(test_session)


class TestPlaybookStepRepositoryCreate:
    """Test step creation."""

    @pytest.mark.asyncio
    async def test_create_step(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test creating a new step."""
        playbook = setup_playbooks["playbook1"]
        
        step_data = PlaybookStepCreateDTO(
            name="NotifyUser",
            action_type="notify",
            params={"recipient": "user@example.com", "message": "Payment failed"},
        )
        
        created = await playbook_step_repo.create_step(playbook.playbook_id, step_data, "tenant_001")
        
        assert created is not None
        assert created.playbook_id == playbook.playbook_id
        assert created.name == "NotifyUser"
        assert created.action_type == "notify"
        assert created.params == {"recipient": "user@example.com", "message": "Payment failed"}
        assert created.step_order == 1  # First step should have order 1
        assert created.step_id is not None

    @pytest.mark.asyncio
    async def test_create_multiple_steps_auto_order(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that step_order is automatically assigned correctly."""
        playbook = setup_playbooks["playbook1"]
        
        # Create first step
        step1_data = PlaybookStepCreateDTO(
            name="Step1",
            action_type="notify",
            params={},
        )
        step1 = await playbook_step_repo.create_step(playbook.playbook_id, step1_data, "tenant_001")
        assert step1.step_order == 1
        
        # Create second step
        step2_data = PlaybookStepCreateDTO(
            name="Step2",
            action_type="call_tool",
            params={"tool": "retry"},
        )
        step2 = await playbook_step_repo.create_step(playbook.playbook_id, step2_data, "tenant_001")
        assert step2.step_order == 2
        
        # Create third step
        step3_data = PlaybookStepCreateDTO(
            name="Step3",
            action_type="escalate",
            params={},
        )
        step3 = await playbook_step_repo.create_step(playbook.playbook_id, step3_data, "tenant_001")
        assert step3.step_order == 3
        
        # Verify all steps are retrieved in order
        all_steps = await playbook_step_repo.get_steps(playbook.playbook_id, "tenant_001")
        assert len(all_steps) == 3
        assert all_steps[0].step_order == 1
        assert all_steps[1].step_order == 2
        assert all_steps[2].step_order == 3

    @pytest.mark.asyncio
    async def test_create_step_invalid_playbook(self, playbook_step_repo: PlaybookStepRepository, setup_tenants):
        """Test that creating a step for non-existent playbook raises error."""
        step_data = PlaybookStepCreateDTO(
            name="Step1",
            action_type="notify",
            params={},
        )
        
        with pytest.raises(ValueError, match="Playbook not found"):
            await playbook_step_repo.create_step(99999, step_data, "tenant_001")

    @pytest.mark.asyncio
    async def test_create_step_validation(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test validation errors when creating steps."""
        playbook = setup_playbooks["playbook1"]
        step_data = PlaybookStepCreateDTO(
            name="Step1",
            action_type="notify",
            params={},
        )
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await playbook_step_repo.create_step(playbook.playbook_id, step_data, "")


class TestPlaybookStepRepositoryGetSteps:
    """Test getting steps."""

    @pytest.mark.asyncio
    async def test_get_steps(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test retrieving steps for a playbook."""
        playbook = setup_playbooks["playbook1"]
        
        # Create some steps
        step1_data = PlaybookStepCreateDTO(name="Step1", action_type="notify", params={})
        step2_data = PlaybookStepCreateDTO(name="Step2", action_type="call_tool", params={})
        step3_data = PlaybookStepCreateDTO(name="Step3", action_type="escalate", params={})
        
        await playbook_step_repo.create_step(playbook.playbook_id, step1_data, "tenant_001")
        await playbook_step_repo.create_step(playbook.playbook_id, step2_data, "tenant_001")
        await playbook_step_repo.create_step(playbook.playbook_id, step3_data, "tenant_001")
        
        # Get all steps
        steps = await playbook_step_repo.get_steps(playbook.playbook_id, "tenant_001")
        
        assert len(steps) == 3
        assert all(step.playbook_id == playbook.playbook_id for step in steps)
        # Should be ordered by step_order
        assert steps[0].step_order == 1
        assert steps[1].step_order == 2
        assert steps[2].step_order == 3

    @pytest.mark.asyncio
    async def test_get_steps_empty(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test getting steps for a playbook with no steps."""
        playbook = setup_playbooks["playbook1"]
        
        steps = await playbook_step_repo.get_steps(playbook.playbook_id, "tenant_001")
        assert len(steps) == 0

    @pytest.mark.asyncio
    async def test_get_steps_invalid_playbook(self, playbook_step_repo: PlaybookStepRepository, setup_tenants):
        """Test that getting steps for non-existent playbook raises error."""
        with pytest.raises(ValueError, match="Playbook not found"):
            await playbook_step_repo.get_steps(99999, "tenant_001")


class TestPlaybookStepRepositoryReorder:
    """Test step reordering."""

    @pytest.mark.asyncio
    async def test_update_step_order(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test reordering steps."""
        playbook = setup_playbooks["playbook1"]
        
        # Create steps
        step1_data = PlaybookStepCreateDTO(name="Step1", action_type="notify", params={})
        step2_data = PlaybookStepCreateDTO(name="Step2", action_type="call_tool", params={})
        step3_data = PlaybookStepCreateDTO(name="Step3", action_type="escalate", params={})
        
        step1 = await playbook_step_repo.create_step(playbook.playbook_id, step1_data, "tenant_001")
        step2 = await playbook_step_repo.create_step(playbook.playbook_id, step2_data, "tenant_001")
        step3 = await playbook_step_repo.create_step(playbook.playbook_id, step3_data, "tenant_001")
        
        # Reorder: 3, 1, 2
        ordered_step_ids = [step3.step_id, step1.step_id, step2.step_id]
        updated_steps = await playbook_step_repo.update_step_order(
            playbook.playbook_id, ordered_step_ids, "tenant_001"
        )
        
        assert len(updated_steps) == 3
        assert updated_steps[0].step_id == step3.step_id
        assert updated_steps[0].step_order == 1
        assert updated_steps[1].step_id == step1.step_id
        assert updated_steps[1].step_order == 2
        assert updated_steps[2].step_id == step2.step_id
        assert updated_steps[2].step_order == 3
        
        # Verify order persisted
        all_steps = await playbook_step_repo.get_steps(playbook.playbook_id, "tenant_001")
        assert all_steps[0].step_id == step3.step_id
        assert all_steps[1].step_id == step1.step_id
        assert all_steps[2].step_id == step2.step_id

    @pytest.mark.asyncio
    async def test_update_step_order_reverse(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test reversing step order."""
        playbook = setup_playbooks["playbook1"]
        
        # Create steps
        step1 = await playbook_step_repo.create_step(
            playbook.playbook_id,
            PlaybookStepCreateDTO(name="Step1", action_type="notify", params={}),
            "tenant_001",
        )
        step2 = await playbook_step_repo.create_step(
            playbook.playbook_id,
            PlaybookStepCreateDTO(name="Step2", action_type="call_tool", params={}),
            "tenant_001",
        )
        
        # Reverse order
        updated_steps = await playbook_step_repo.update_step_order(
            playbook.playbook_id, [step2.step_id, step1.step_id], "tenant_001"
        )
        
        assert updated_steps[0].step_id == step2.step_id
        assert updated_steps[0].step_order == 1
        assert updated_steps[1].step_id == step1.step_id
        assert updated_steps[1].step_order == 2

    @pytest.mark.asyncio
    async def test_update_step_order_missing_steps(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that reordering must include all steps."""
        playbook = setup_playbooks["playbook1"]
        
        step1 = await playbook_step_repo.create_step(
            playbook.playbook_id,
            PlaybookStepCreateDTO(name="Step1", action_type="notify", params={}),
            "tenant_001",
        )
        step2 = await playbook_step_repo.create_step(
            playbook.playbook_id,
            PlaybookStepCreateDTO(name="Step2", action_type="call_tool", params={}),
            "tenant_001",
        )
        
        # Try to reorder with only one step (should fail)
        with pytest.raises(ValueError, match="All steps must be included"):
            await playbook_step_repo.update_step_order(
                playbook.playbook_id, [step1.step_id], "tenant_001"
            )

    @pytest.mark.asyncio
    async def test_update_step_order_invalid_step_id(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that reordering with invalid step_id raises error."""
        playbook = setup_playbooks["playbook1"]
        
        step1 = await playbook_step_repo.create_step(
            playbook.playbook_id,
            PlaybookStepCreateDTO(name="Step1", action_type="notify", params={}),
            "tenant_001",
        )
        
        # Try to reorder with non-existent step_id
        with pytest.raises(ValueError, match="do not belong to playbook"):
            await playbook_step_repo.update_step_order(
                playbook.playbook_id, [99999], "tenant_001"
            )

    @pytest.mark.asyncio
    async def test_update_step_order_empty_list(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that reordering with empty list raises error."""
        playbook = setup_playbooks["playbook1"]
        
        with pytest.raises(ValueError, match="cannot be empty"):
            await playbook_step_repo.update_step_order(
                playbook.playbook_id, [], "tenant_001"
            )


class TestPlaybookStepRepositoryTenantIsolation:
    """Test tenant isolation enforcement."""

    @pytest.mark.asyncio
    async def test_tenant_isolation_get_steps(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that tenants can only get steps from their own playbooks."""
        playbook1 = setup_playbooks["playbook1"]  # tenant_001
        playbook2 = setup_playbooks["playbook2"]  # tenant_002
        
        # Create steps for both playbooks
        await playbook_step_repo.create_step(
            playbook1.playbook_id,
            PlaybookStepCreateDTO(name="Step1", action_type="notify", params={}),
            "tenant_001",
        )
        await playbook_step_repo.create_step(
            playbook2.playbook_id,
            PlaybookStepCreateDTO(name="Step2", action_type="notify", params={}),
            "tenant_002",
        )
        
        # Tenant 001 should only see their own steps
        tenant1_steps = await playbook_step_repo.get_steps(playbook1.playbook_id, "tenant_001")
        assert len(tenant1_steps) == 1
        assert tenant1_steps[0].playbook_id == playbook1.playbook_id
        
        # Tenant 001 should not be able to get tenant_002's playbook steps
        with pytest.raises(ValueError, match="Playbook not found"):
            await playbook_step_repo.get_steps(playbook2.playbook_id, "tenant_001")

    @pytest.mark.asyncio
    async def test_tenant_isolation_create_step(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that tenants cannot create steps for other tenants' playbooks."""
        playbook2 = setup_playbooks["playbook2"]  # tenant_002
        
        step_data = PlaybookStepCreateDTO(
            name="Step1",
            action_type="notify",
            params={},
        )
        
        # Tenant 001 should not be able to create steps for tenant_002's playbook
        with pytest.raises(ValueError, match="Playbook not found"):
            await playbook_step_repo.create_step(playbook2.playbook_id, step_data, "tenant_001")

    @pytest.mark.asyncio
    async def test_tenant_isolation_update_order(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test that tenants cannot reorder steps for other tenants' playbooks."""
        playbook2 = setup_playbooks["playbook2"]  # tenant_002
        
        step = await playbook_step_repo.create_step(
            playbook2.playbook_id,
            PlaybookStepCreateDTO(name="Step1", action_type="notify", params={}),
            "tenant_002",
        )
        
        # Tenant 001 should not be able to reorder tenant_002's steps
        with pytest.raises(ValueError, match="Playbook not found"):
            await playbook_step_repo.update_step_order(
                playbook2.playbook_id, [step.step_id], "tenant_001"
            )

    @pytest.mark.asyncio
    async def test_tenant_isolation_get_by_id(self, playbook_step_repo: PlaybookStepRepository, setup_tenants, setup_playbooks):
        """Test get_by_id with tenant isolation."""
        playbook1 = setup_playbooks["playbook1"]  # tenant_001
        playbook2 = setup_playbooks["playbook2"]  # tenant_002
        
        step1 = await playbook_step_repo.create_step(
            playbook1.playbook_id,
            PlaybookStepCreateDTO(name="Step1", action_type="notify", params={}),
            "tenant_001",
        )
        step2 = await playbook_step_repo.create_step(
            playbook2.playbook_id,
            PlaybookStepCreateDTO(name="Step2", action_type="notify", params={}),
            "tenant_002",
        )
        
        # Tenant 001 should be able to get their own step
        retrieved = await playbook_step_repo.get_by_id(str(step1.step_id), "tenant_001")
        assert retrieved is not None
        assert retrieved.step_id == step1.step_id
        
        # Tenant 001 should not be able to get tenant_002's step
        retrieved = await playbook_step_repo.get_by_id(str(step2.step_id), "tenant_001")
        assert retrieved is None  # Should return None due to tenant isolation


