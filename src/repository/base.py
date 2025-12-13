"""
Base repository interface and abstract implementation for Phase 6.

Provides a shared repository abstraction to keep domain logic decoupled from raw DB access.
All repositories must enforce tenant isolation and use dependency injection.
"""

import logging
from abc import ABC, abstractmethod
from typing import Generic, Optional, Protocol, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Type variable for model types
ModelType = TypeVar("ModelType")


class RepositoryError(Exception):
    """
    Base exception for repository operations.
    
    Phase 7 P7-7: Well-defined exception for repository errors.
    Used to distinguish repository-level errors from other exceptions.
    """
    
    def __init__(self, message: str, entity_type: Optional[str] = None, entity_id: Optional[str] = None):
        """
        Initialize repository error.
        
        Args:
            message: Error message
            entity_type: Optional entity type (e.g., "Playbook", "PlaybookStep")
            entity_id: Optional entity identifier
        """
        super().__init__(message)
        self.message = message
        self.entity_type = entity_type
        self.entity_id = entity_id


class PaginatedResult(Generic[ModelType]):
    """
    Paginated query result.
    
    Attributes:
        items: List of items in the current page
        total: Total number of items across all pages
        page: Current page number (1-indexed)
        page_size: Number of items per page
        total_pages: Total number of pages
    """

    def __init__(
        self,
        items: list[ModelType],
        total: int,
        page: int,
        page_size: int,
    ):
        """
        Initialize paginated result.
        
        Args:
            items: List of items in the current page
            total: Total number of items across all pages
            page: Current page number (1-indexed)
            page_size: Number of items per page
        """
        self.items = items
        self.total = total
        self.page = page
        self.page_size = page_size
        self.total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0


class BaseRepository(Protocol, Generic[ModelType]):
    """
    Protocol defining the interface for all repositories.
    
    This protocol ensures all repositories follow a consistent pattern:
    - Async operations
    - Tenant isolation
    - Dependency injection via session
    """

    @abstractmethod
    async def get_by_id(self, id: str, tenant_id: str) -> Optional[ModelType]:
        """
        Get entity by ID with tenant isolation.
        
        Args:
            id: Entity identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Entity instance or None if not found
        """
        ...

    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[ModelType]:
        """
        List entities for a tenant with pagination.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria
            
        Returns:
            PaginatedResult with items and pagination metadata
        """
        ...


class AbstractBaseRepository(ABC, Generic[ModelType]):
    """
    Abstract base repository implementation.
    
    Provides common functionality for all repositories:
    - Tenant isolation enforcement
    - Pagination helpers
    - Session management via dependency injection
    
    This base class will be extended by:
    - ExceptionRepository
    - ExceptionEventRepository
    - TenantRepository
    - DomainPackRepository
    - TenantPolicyPackRepository
    - PlaybookRepository
    - PlaybookStepRepository
    - ToolDefinitionRepository
    
    IMPORTANT: Repositories must be instantiated per-request using the AsyncSession
    from get_db_session(). Do NOT use global singletons for repositories.
    
    Example usage:
        # In FastAPI route:
        @router.get("/exceptions")
        async def list_exceptions(
            tenant_id: str,
            session: AsyncSession = Depends(get_db_session),
        ):
            repo = ExceptionRepository(session)
            return await repo.list_by_tenant(tenant_id, page=1, page_size=50)
    """

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with injected session.
        
        Args:
            session: AsyncSession instance (injected, NOT global)
            
        Raises:
            ValueError: If session is None
        """
        if session is None:
            raise ValueError("Session must be provided (dependency injection required)")
        self.session = session

    def _tenant_filter(
        self,
        query: Select,
        tenant_id: str,
        tenant_column,
    ) -> Select:
        """
        Apply tenant filter to a query.
        
        This helper ensures tenant isolation is enforced on all queries.
        All list-style queries MUST use this helper.
        
        Args:
            query: SQLAlchemy Select query
            tenant_id: Tenant identifier (required)
            tenant_column: SQLAlchemy column reference for tenant_id
                (e.g., ModelClass.tenant_id)
            
        Returns:
            Query with tenant filter applied
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        return query.where(tenant_column == tenant_id)

    def _paginate(
        self,
        query: Select,
        page: int = 1,
        page_size: int = 50,
    ) -> Select:
        """
        Apply pagination to a query.
        
        Args:
            query: SQLAlchemy Select query
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            Paginated query with offset and limit applied
            
        Raises:
            ValueError: If page < 1 or page_size < 1
        """
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        # Calculate offset
        offset = (page - 1) * page_size
        
        # Apply pagination to main query
        return query.offset(offset).limit(page_size)

    async def _execute_paginated(
        self,
        query: Select,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[ModelType]:
        """
        Execute a paginated query and return PaginatedResult.
        
        This helper executes both the paginated query and count query,
        then constructs a PaginatedResult.
        
        Args:
            query: SQLAlchemy Select query
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with items and pagination metadata
        """
        # Calculate offset
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        offset = (page - 1) * page_size
        
        # Create count query - count all rows matching the query
        # We need to get the first column from the original query for counting
        count_query = select(func.count()).select_from(query.subquery())
        
        # Create paginated query
        paginated_query = query.offset(offset).limit(page_size)
        
        # Execute count query
        count_result = await self.session.execute(count_query)
        total = count_result.scalar_one() or 0
        
        # Execute paginated query
        result = await self.session.execute(paginated_query)
        items = list(result.scalars().all())
        
        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    @abstractmethod
    async def get_by_id(self, id: str, tenant_id: str) -> Optional[ModelType]:
        """
        Get entity by ID with tenant isolation.
        
        Args:
            id: Entity identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Entity instance or None if not found
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        ...

    @abstractmethod
    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[ModelType]:
        """
        List entities for a tenant with pagination.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (implementation-specific)
            
        Returns:
            PaginatedResult with items and pagination metadata
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        ...

