"""
Tenant repository for tenant management operations.

Phase 6 P6-10: TenantRepository with full CRUD operations and filtering.

Note: Tenant isolation for TenantRepository is different from other repositories
because tenants are top-level entities. The tenant_id IS the primary key.
Tenant isolation here means ensuring operations are safe and validated.
"""

import logging
from datetime import datetime
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import Tenant, TenantStatus
from src.repository.base import AbstractBaseRepository
from src.repository.dto import TenantFilter

logger = logging.getLogger(__name__)


class TenantRepository(AbstractBaseRepository[Tenant]):
    """
    Repository for tenant operations.
    
    Provides:
    - Get tenant by ID
    - List tenants with filtering
    - Update tenant status
    - Tenant isolation enforcement
    
    Note: For TenantRepository, "tenant isolation" means ensuring operations
    are scoped correctly. Since tenant_id is the primary key, operations
    are naturally isolated by the tenant_id itself.
    """

    async def create_tenant(
        self,
        tenant_id: str,
        name: str,
        created_by: str,
    ) -> Tenant:
        """
        Create a new tenant.
        
        Args:
            tenant_id: Tenant identifier (primary key)
            name: Tenant name
            created_by: User identifier who created the tenant
            
        Returns:
            Created Tenant model instance
            
        Raises:
            ValueError: If tenant_id/name/created_by is invalid
            ValueError: If tenant with same tenant_id already exists
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not name or not name.strip():
            raise ValueError("name is required")
        if not created_by or not created_by.strip():
            raise ValueError("created_by is required")
        
        # Check if tenant already exists
        existing = await self.get_tenant(tenant_id)
        if existing:
            raise ValueError(f"Tenant already exists: tenant_id={tenant_id}")
        
        # Create new tenant
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            status=TenantStatus.ACTIVE,
            created_by=created_by,
        )
        
        self.session.add(tenant)
        await self.session.flush()
        await self.session.refresh(tenant)
        
        logger.info(f"Created tenant: tenant_id={tenant_id}, name={name}")
        return tenant

    async def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """
        Get a tenant by ID.
        
        Args:
            tenant_id: Tenant identifier (primary key)
            
        Returns:
            Tenant model instance or None if not found
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        query = select(Tenant).where(Tenant.tenant_id == tenant_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_tenants(self, filters: Optional[TenantFilter] = None) -> list[Tenant]:
        """
        List tenants with optional filtering.
        
        Args:
            filters: Optional TenantFilter for filtering tenants
            
        Returns:
            List of Tenant model instances
            
        Note: This method does not enforce tenant isolation in the traditional
        sense because tenants are top-level entities. However, it provides
        filtering capabilities for administrative queries.
        """
        query = select(Tenant)
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            # Filter by name (partial match, case-insensitive)
            if filters.name:
                conditions.append(Tenant.name.ilike(f"%{filters.name}%"))
            
            # Filter by status
            if filters.status:
                conditions.append(Tenant.status == filters.status)
            
            # Filter by created_from
            if filters.created_from:
                conditions.append(Tenant.created_at >= filters.created_from)
            
            # Filter by created_to
            if filters.created_to:
                conditions.append(Tenant.created_at <= filters.created_to)
            
            # Apply all conditions
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by created_at descending (newest first)
        query = query.order_by(Tenant.created_at.desc())
        
        # Execute query
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_tenant_status(
        self,
        tenant_id: str,
        status: TenantStatus,
    ) -> Tenant:
        """
        Update tenant status.
        
        Enforces allowed statuses: active, suspended, archived.
        
        Args:
            tenant_id: Tenant identifier
            status: New tenant status (must be one of: active, suspended, archived)
            
        Returns:
            Updated Tenant model instance
            
        Raises:
            ValueError: If tenant_id is None/empty, or status is invalid
            ValueError: If tenant not found
        """
        if not tenant_id:
            raise ValueError("tenant_id is required")
        
        # Validate status is one of the allowed values
        allowed_statuses = {TenantStatus.ACTIVE, TenantStatus.SUSPENDED, TenantStatus.ARCHIVED}
        if status not in allowed_statuses:
            raise ValueError(
                f"Invalid status: {status}. Must be one of: {[s.value for s in allowed_statuses]}"
            )
        
        # Get tenant
        tenant = await self.get_tenant(tenant_id)
        if tenant is None:
            raise ValueError(f"Tenant not found: {tenant_id}")
        
        # Update status
        logger.info(f"Updating tenant {tenant_id} status from {tenant.status.value} to {status.value}")
        tenant.status = status
        
        # Update updated_at timestamp (handled by database onupdate trigger, but we can set it explicitly)
        tenant.updated_at = datetime.utcnow()
        
        await self.session.flush()
        await self.session.refresh(tenant)
        
        return tenant

    # AbstractBaseRepository implementations
    # Note: These are required by the base class but have different semantics for TenantRepository

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[Tenant]:
        """
        Get tenant by ID (implements AbstractBaseRepository interface).
        
        For TenantRepository, the id parameter is the tenant_id itself.
        The tenant_id parameter is ignored (tenants are top-level entities).
        
        Args:
            id: Tenant identifier (primary key)
            tenant_id: Ignored (tenants are top-level entities)
            
        Returns:
            Tenant model instance or None if not found
        """
        # For TenantRepository, id is the tenant_id itself
        return await self.get_tenant(id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ):
        """
        List tenants (implements AbstractBaseRepository interface).
        
        For TenantRepository, this method is not tenant-scoped in the traditional
        sense. The tenant_id parameter is ignored, and this method lists all tenants
        (optionally filtered). Use list_tenants() for a cleaner API.
        
        Args:
            tenant_id: Ignored (tenants are top-level entities)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (converted to TenantFilter)
            
        Returns:
            PaginatedResult with tenants
        """
        from src.repository.base import PaginatedResult
        
        # Convert filters to TenantFilter if provided
        tenant_filter = None
        if filters:
            tenant_filter = TenantFilter(**filters)
        
        # Get all tenants (with filters)
        all_tenants = await self.list_tenants(tenant_filter)
        
        # Apply pagination manually
        total = len(all_tenants)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tenants = all_tenants[start_idx:end_idx]
        
        return PaginatedResult(
            items=paginated_tenants,
            total=total,
            page=page,
            page_size=page_size,
        )

