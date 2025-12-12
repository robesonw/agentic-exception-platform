"""
Tenant policy pack repository for versioned tenant policy pack management.

Phase 6 P6-12: TenantPolicyPackRepository with version management and tenant isolation.

Note: Tenant policy packs are tenant-specific, so this repository enforces
strict tenant isolation on all operations.
"""

import logging
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import TenantPolicyPackVersion
from src.repository.base import AbstractBaseRepository

logger = logging.getLogger(__name__)


class TenantPolicyPackRepository(AbstractBaseRepository[TenantPolicyPackVersion]):
    """
    Repository for tenant policy pack version management.
    
    Provides:
    - Get tenant policy pack by tenant_id and version
    - Get latest tenant policy pack for a tenant
    - Create new tenant policy pack version
    - List tenant policy packs for a tenant
    
    All operations enforce strict tenant isolation - queries are always
    filtered by tenant_id to ensure data separation.
    """

    async def get_tenant_policy_pack(
        self,
        tenant_id: str,
        version: int,
    ) -> Optional[TenantPolicyPackVersion]:
        """
        Get a tenant policy pack by tenant_id and version.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            version: Version number
            
        Returns:
            TenantPolicyPackVersion instance or None if not found
            
        Raises:
            ValueError: If tenant_id is None/empty, or version < 1
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if version < 1:
            raise ValueError("version must be >= 1")
        
        query = select(TenantPolicyPackVersion).where(
            TenantPolicyPackVersion.tenant_id == tenant_id,
            TenantPolicyPackVersion.version == version,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_tenant_policy_pack(
        self,
        tenant_id: str,
    ) -> Optional[TenantPolicyPackVersion]:
        """
        Get the latest tenant policy pack for a tenant.
        
        Latest is determined by:
        1. Highest version number (primary)
        2. Most recent created_at (tiebreaker if versions are equal)
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            TenantPolicyPackVersion instance or None if no packs exist for tenant
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(TenantPolicyPackVersion)
            .where(TenantPolicyPackVersion.tenant_id == tenant_id)
            .order_by(desc(TenantPolicyPackVersion.version), desc(TenantPolicyPackVersion.created_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_tenant_policy_pack_version(
        self,
        tenant_id: str,
        version: int,
        pack_json: dict,
    ) -> TenantPolicyPackVersion:
        """
        Create a new tenant policy pack version.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            version: Version number (must be unique for the tenant)
            pack_json: Tenant policy pack JSON as a dictionary
            
        Returns:
            Created TenantPolicyPackVersion instance
            
        Raises:
            ValueError: If tenant_id is None/empty, version < 1, or pack_json is empty
            ValueError: If a pack with the same tenant_id and version already exists
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        if version < 1:
            raise ValueError("version must be >= 1")
        if not pack_json:
            raise ValueError("pack_json is required and cannot be empty")
        
        # Check if version already exists for this tenant
        existing = await self.get_tenant_policy_pack(tenant_id, version)
        if existing:
            raise ValueError(
                f"Tenant policy pack version already exists: tenant_id={tenant_id}, version={version}"
            )
        
        # Create new version
        tenant_policy_pack_version = TenantPolicyPackVersion(
            tenant_id=tenant_id,
            version=version,
            pack_json=pack_json,
        )
        
        self.session.add(tenant_policy_pack_version)
        await self.session.flush()
        await self.session.refresh(tenant_policy_pack_version)
        
        logger.info(f"Created tenant policy pack version: tenant_id={tenant_id}, version={version}")
        return tenant_policy_pack_version

    async def list_tenant_policy_packs(
        self,
        tenant_id: str,
    ) -> list[TenantPolicyPackVersion]:
        """
        List all tenant policy packs for a tenant.
        
        Results are ordered by version number (descending, newest first).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            List of TenantPolicyPackVersion instances for the tenant
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(TenantPolicyPackVersion)
            .where(TenantPolicyPackVersion.tenant_id == tenant_id)
            .order_by(desc(TenantPolicyPackVersion.version))
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # AbstractBaseRepository implementations
    # Note: These methods enforce tenant isolation

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[TenantPolicyPackVersion]:
        """
        Get tenant policy pack by ID with tenant isolation.
        
        Args:
            id: Tenant policy pack database ID (as string)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            TenantPolicyPackVersion instance or None if not found or tenant mismatch
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            pack_id = int(id)
        except (ValueError, TypeError):
            return None
        
        # Enforce tenant isolation - must match both id and tenant_id
        query = select(TenantPolicyPackVersion).where(
            TenantPolicyPackVersion.id == pack_id,
            TenantPolicyPackVersion.tenant_id == tenant_id,
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
        List tenant policy packs for a tenant with pagination.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (currently unused)
            
        Returns:
            PaginatedResult with tenant policy packs
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        from src.repository.base import PaginatedResult
        
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Get all tenant policy packs for this tenant
        all_packs = await self.list_tenant_policy_packs(tenant_id)
        
        # Apply pagination manually
        total = len(all_packs)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_packs = all_packs[start_idx:end_idx]
        
        return PaginatedResult(
            items=paginated_packs,
            total=total,
            page=page,
            page_size=page_size,
        )


