"""
Playbook repository for playbook management.

Phase 6 P6-13: PlaybookRepository with CRUD operations and filtering.

Note: Playbooks are tenant-specific, so this repository enforces
strict tenant isolation on all operations.
"""

import logging
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import Playbook
from src.repository.base import AbstractBaseRepository
from src.repository.dto import PlaybookCreateDTO, PlaybookFilter

logger = logging.getLogger(__name__)


class PlaybookRepository(AbstractBaseRepository[Playbook]):
    """
    Repository for playbook management.
    
    Provides:
    - Get playbook by ID with tenant isolation
    - List playbooks with filtering
    - Create new playbook
    - Tenant isolation enforcement
    
    All operations enforce strict tenant isolation - queries are always
    filtered by tenant_id to ensure data separation.
    """

    async def get_playbook(
        self,
        playbook_id: int,
        tenant_id: str,
    ) -> Optional[Playbook]:
        """
        Get a playbook by ID with tenant isolation.
        
        Args:
            playbook_id: Playbook identifier (primary key)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Playbook instance or None if not found or tenant mismatch
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_id < 1
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if playbook_id < 1:
            raise ValueError("playbook_id must be >= 1")
        
        query = select(Playbook).where(
            Playbook.playbook_id == playbook_id,
            Playbook.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_playbooks(
        self,
        tenant_id: str,
        filters: Optional[PlaybookFilter] = None,
    ) -> list[Playbook]:
        """
        List playbooks for a tenant with optional filtering.
        
        Results are ordered by created_at (descending, newest first).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            filters: Optional PlaybookFilter for filtering playbooks
            
        Returns:
            List of Playbook instances for the tenant
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(Playbook).where(Playbook.tenant_id == tenant_id)
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            # Filter by name (partial match, case-insensitive)
            if filters.name:
                conditions.append(Playbook.name.ilike(f"%{filters.name}%"))
            
            # Filter by version
            if filters.version is not None:
                conditions.append(Playbook.version == filters.version)
            
            # Filter by created_from
            if filters.created_from:
                conditions.append(Playbook.created_at >= filters.created_from)
            
            # Filter by created_to
            if filters.created_to:
                conditions.append(Playbook.created_at <= filters.created_to)
            
            # Apply all conditions
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by created_at descending (newest first)
        query = query.order_by(desc(Playbook.created_at))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_playbook(
        self,
        tenant_id: str,
        playbook_data: PlaybookCreateDTO,
    ) -> Playbook:
        """
        Create a new playbook.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            playbook_data: PlaybookCreateDTO with playbook details
            
        Returns:
            Created Playbook instance
            
        Raises:
            ValueError: If tenant_id is None/empty, or playbook_data is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Create new playbook
        playbook = Playbook(
            tenant_id=tenant_id,
            name=playbook_data.name,
            version=playbook_data.version,
            conditions=playbook_data.conditions,
        )
        
        self.session.add(playbook)
        await self.session.flush()
        await self.session.refresh(playbook)
        
        logger.info(f"Created playbook: playbook_id={playbook.playbook_id}, tenant_id={tenant_id}, name={playbook.name}")
        return playbook

    # AbstractBaseRepository implementations
    # Note: These methods enforce tenant isolation

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[Playbook]:
        """
        Get playbook by ID with tenant isolation.
        
        Args:
            id: Playbook database ID (as string)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Playbook instance or None if not found or tenant mismatch
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            playbook_id = int(id)
        except (ValueError, TypeError):
            return None
        
        # Enforce tenant isolation - must match both id and tenant_id
        query = select(Playbook).where(
            Playbook.playbook_id == playbook_id,
            Playbook.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ):
        """
        List playbooks for a tenant with pagination and filtering.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (converted to PlaybookFilter)
            
        Returns:
            PaginatedResult with playbooks
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        from src.repository.base import PaginatedResult
        
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Convert filters to PlaybookFilter if provided
        playbook_filter = None
        if filters:
            playbook_filter = PlaybookFilter(**filters)
        
        # Get all playbooks (with optional filters)
        all_playbooks = await self.list_playbooks(tenant_id, filters=playbook_filter)
        
        # Apply pagination manually
        total = len(all_playbooks)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_playbooks = all_playbooks[start_idx:end_idx]
        
        return PaginatedResult(
            items=paginated_playbooks,
            total=total,
            page=page,
            page_size=page_size,
        )


