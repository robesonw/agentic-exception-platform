"""
Tests for base repository interface and abstract implementation.

Tests Phase 6 P6-4: Base repository with tenant isolation and pagination.
"""

import pytest
from sqlalchemy import Column, Integer, String, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from src.repository.base import AbstractBaseRepository, PaginatedResult

# Create a test base and model
TestBase = declarative_base()


class TestModel(TestBase):
    """Test model for repository tests."""

    __tablename__ = "test_model"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tenant_id = Column(String, nullable=False, index=True)
    name = Column(String, nullable=False)
    value = Column(Integer, nullable=False)


class TestRepository(AbstractBaseRepository[TestModel]):
    """Concrete implementation of AbstractBaseRepository for testing."""

    async def get_by_id(self, id: str, tenant_id: str) -> TestModel | None:
        """Get test model by ID with tenant isolation."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            model_id = int(id)
        except (ValueError, TypeError):
            return None
        
        query = select(TestModel).where(TestModel.id == model_id)
        query = self._tenant_filter(query, tenant_id, TestModel.tenant_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[TestModel]:
        """List test models for a tenant with pagination."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(TestModel)
        query = self._tenant_filter(query, tenant_id, TestModel.tenant_id)
        
        # Apply additional filters if provided
        if "name" in filters:
            query = query.where(TestModel.name == filters["name"])
        if "min_value" in filters:
            query = query.where(TestModel.value >= filters["min_value"])
        
        return await self._execute_paginated(query, page, page_size)


@pytest.fixture
async def test_engine():
    """Create an in-memory SQLite test engine."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(TestBase.metadata.create_all)
    
    yield engine
    
    # Cleanup
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
    """Create test data."""
    # Create test models for different tenants
    models = [
        TestModel(tenant_id="tenant_1", name="Item 1", value=10),
        TestModel(tenant_id="tenant_1", name="Item 2", value=20),
        TestModel(tenant_id="tenant_1", name="Item 3", value=30),
        TestModel(tenant_id="tenant_2", name="Item 4", value=40),
        TestModel(tenant_id="tenant_2", name="Item 5", value=50),
        TestModel(tenant_id="tenant_1", name="Item 6", value=60),
    ]
    
    test_session.add_all(models)
    await test_session.commit()
    
    return models


class TestAbstractBaseRepository:
    """Test AbstractBaseRepository functionality."""

    @pytest.mark.asyncio
    async def test_repository_requires_session(self):
        """Test that repository raises error if session is None."""
        with pytest.raises(ValueError, match="Session must be provided"):
            TestRepository(None)

    @pytest.mark.asyncio
    async def test_tenant_filter_applies_isolation(self, test_session, test_data):
        """Test that tenant filter enforces tenant isolation."""
        repo = TestRepository(test_session)
        
        # Query for tenant_1
        query = select(TestModel)
        filtered_query = repo._tenant_filter(query, "tenant_1", TestModel.tenant_id)
        
        result = await test_session.execute(filtered_query)
        items = result.scalars().all()
        
        # Should only return items for tenant_1
        assert len(items) == 4
        assert all(item.tenant_id == "tenant_1" for item in items)

    @pytest.mark.asyncio
    async def test_tenant_filter_raises_on_empty_tenant_id(self, test_session):
        """Test that tenant filter raises error on empty tenant_id."""
        repo = TestRepository(test_session)
        query = select(TestModel)
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            repo._tenant_filter(query, "", TestModel.tenant_id)
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            repo._tenant_filter(query, None, TestModel.tenant_id)

    @pytest.mark.asyncio
    async def test_paginate_applies_offset_and_limit(self, test_session, test_data):
        """Test that pagination applies correct offset and limit."""
        repo = TestRepository(test_session)
        
        query = select(TestModel)
        query = repo._tenant_filter(query, "tenant_1", TestModel.tenant_id)
        
        # First page
        page1_query = repo._paginate(query, page=1, page_size=2)
        result1 = await test_session.execute(page1_query)
        page1_items = result1.scalars().all()
        
        assert len(page1_items) == 2
        
        # Second page
        page2_query = repo._paginate(query, page=2, page_size=2)
        result2 = await test_session.execute(page2_query)
        page2_items = result2.scalars().all()
        
        assert len(page2_items) == 2
        
        # Verify different items
        assert page1_items[0].id != page2_items[0].id

    @pytest.mark.asyncio
    async def test_paginate_raises_on_invalid_page(self, test_session):
        """Test that pagination raises error on invalid page numbers."""
        repo = TestRepository(test_session)
        query = select(TestModel)
        
        with pytest.raises(ValueError, match="page must be >= 1"):
            repo._paginate(query, page=0, page_size=10)
        
        with pytest.raises(ValueError, match="page_size must be >= 1"):
            repo._paginate(query, page=1, page_size=0)

    @pytest.mark.asyncio
    async def test_execute_paginated_returns_correct_result(self, test_session, test_data):
        """Test that _execute_paginated returns correct PaginatedResult."""
        repo = TestRepository(test_session)
        
        query = select(TestModel)
        query = repo._tenant_filter(query, "tenant_1", TestModel.tenant_id)
        
        result = await repo._execute_paginated(query, page=1, page_size=2)
        
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 2
        assert result.total == 4  # Total items for tenant_1
        assert result.page == 1
        assert result.page_size == 2
        assert result.total_pages == 2

    @pytest.mark.asyncio
    async def test_execute_paginated_last_page(self, test_session, test_data):
        """Test pagination on last page with partial results."""
        repo = TestRepository(test_session)
        
        query = select(TestModel)
        query = repo._tenant_filter(query, "tenant_1", TestModel.tenant_id)
        
        result = await repo._execute_paginated(query, page=2, page_size=2)
        
        assert len(result.items) == 2
        assert result.total == 4
        assert result.page == 2
        assert result.total_pages == 2

    @pytest.mark.asyncio
    async def test_get_by_id_with_tenant_isolation(self, test_session, test_data):
        """Test get_by_id enforces tenant isolation."""
        repo = TestRepository(test_session)
        
        # Get an item that belongs to tenant_1
        item = await repo.get_by_id(str(test_data[0].id), "tenant_1")
        
        assert item is not None
        assert item.tenant_id == "tenant_1"
        
        # Try to get same item as tenant_2 (should return None)
        item2 = await repo.get_by_id(str(test_data[0].id), "tenant_2")
        
        assert item2 is None

    @pytest.mark.asyncio
    async def test_list_by_tenant_with_pagination(self, test_session, test_data):
        """Test list_by_tenant with pagination."""
        repo = TestRepository(test_session)
        
        result = await repo.list_by_tenant("tenant_1", page=1, page_size=2)
        
        assert isinstance(result, PaginatedResult)
        assert len(result.items) == 2
        assert result.total == 4
        assert all(item.tenant_id == "tenant_1" for item in result.items)

    @pytest.mark.asyncio
    async def test_list_by_tenant_with_filters(self, test_session, test_data):
        """Test list_by_tenant with additional filters."""
        repo = TestRepository(test_session)
        
        # Filter by name
        result = await repo.list_by_tenant("tenant_1", name="Item 1")
        
        assert len(result.items) == 1
        assert result.items[0].name == "Item 1"
        
        # Filter by min_value
        result2 = await repo.list_by_tenant("tenant_1", min_value=30)
        
        assert len(result2.items) == 2
        assert all(item.value >= 30 for item in result2.items)

    @pytest.mark.asyncio
    async def test_list_by_tenant_raises_on_empty_tenant_id(self, test_session):
        """Test that list_by_tenant raises error on empty tenant_id."""
        repo = TestRepository(test_session)
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.list_by_tenant("", page=1, page_size=10)
        
        with pytest.raises(ValueError, match="tenant_id is required"):
            await repo.list_by_tenant(None, page=1, page_size=10)

    @pytest.mark.asyncio
    async def test_paginated_result_calculation(self):
        """Test PaginatedResult total_pages calculation."""
        # Exact division
        result1 = PaginatedResult([], total=10, page=1, page_size=5)
        assert result1.total_pages == 2
        
        # Partial last page
        result2 = PaginatedResult([], total=11, page=1, page_size=5)
        assert result2.total_pages == 3
        
        # Empty result
        result3 = PaginatedResult([], total=0, page=1, page_size=10)
        assert result3.total_pages == 0

