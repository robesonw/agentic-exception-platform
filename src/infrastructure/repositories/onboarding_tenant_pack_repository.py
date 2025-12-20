"""
Tenant Pack Repository for onboarding (P12-7).

Provides CRUD operations for tenant packs with versioning, checksum, and status management.
All operations enforce tenant isolation.

Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2
"""

import logging
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import PackStatus, TenantPack
from src.infrastructure.repositories.pack_checksum_utils import calculate_checksum
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


class TenantPackRepository(AbstractBaseRepository[TenantPack]):
    """
    Repository for tenant pack management.
    
    Provides:
    - Create tenant pack version
    - Get tenant pack by tenant and version
    - List tenant packs for tenant with status filter
    - Get latest version for tenant
    - Update pack status
    
    All operations enforce tenant isolation.
    """

    async def create_tenant_pack(
        self,
        tenant_id: str,
        version: str,
        content_json: dict,
        created_by: str,
        skip_existence_check: bool = False,
    ) -> TenantPack:
        """
        Create a new tenant pack version.
        
        Args:
            tenant_id: Tenant identifier
            version: Version string (e.g., "v1.0", "v2.3")
            content_json: Tenant pack JSON content as dict
            created_by: User identifier who created the pack
            skip_existence_check: If True, skip checking if pack already exists
                                 (use when caller has already verified it doesn't exist)
            
        Returns:
            Created TenantPack instance
            
        Raises:
            ValueError: If tenant_id/version/content_json/created_by is invalid
            ValueError: If pack with same tenant_id+version already exists (when skip_existence_check=False)
        """
        # Normalize inputs by stripping whitespace
        tenant_id = tenant_id.strip() if tenant_id else tenant_id
        version = version.strip() if version else version
        created_by = created_by.strip() if created_by else created_by
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not version:
            raise ValueError("version is required")
        if not content_json:
            raise ValueError("content_json is required and cannot be empty")
        if not created_by:
            raise ValueError("created_by is required")
        
        # Check if a pack with this (tenant_id AND version) combination already exists
        # (unless caller has already verified it doesn't exist)
        # Note: We check the COMBINATION of tenant_id+version, not tenant_id OR version
        if not skip_existence_check:
            existing = await self.get_tenant_pack(tenant_id, version)
            if existing:
                raise ValueError(
                    f"Tenant pack with tenant_id={tenant_id} AND version={version} already exists. "
                    f"Please use a different version number (e.g., v1.1, v2.0) or delete the existing pack first."
                )
        
        # Calculate checksum
        checksum = calculate_checksum(content_json)
        
        # Create new pack
        tenant_pack = TenantPack(
            tenant_id=tenant_id,
            version=version,
            content_json=content_json,
            checksum=checksum,
            status=PackStatus.DRAFT,
            created_by=created_by,
        )
        
        self.session.add(tenant_pack)
        await self.session.flush()
        await self.session.refresh(tenant_pack)
        
        logger.info(
            f"Created tenant pack: tenant_id={tenant_id}, version={version}, checksum={checksum[:8]}..."
        )
        return tenant_pack

    async def get_tenant_pack(
        self,
        tenant_id: str,
        version: str,
    ) -> Optional[TenantPack]:
        """
        Get a tenant pack by tenant and version.
        
        Args:
            tenant_id: Tenant identifier
            version: Version string
            
        Returns:
            TenantPack instance or None if not found
            
        Raises:
            ValueError: If tenant_id or version is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        if not version or not version.strip():
            raise ValueError("version is required")
        
        query = select(TenantPack).where(
            TenantPack.tenant_id == tenant_id,
            TenantPack.version == version,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_tenant_packs(
        self,
        tenant_id: str,
        status: Optional[PackStatus] = None,
    ) -> list[TenantPack]:
        """
        List tenant packs for a tenant with optional status filter.
        
        Results are ordered by created_at (descending, newest first).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            status: Optional status filter
            
        Returns:
            List of TenantPack instances
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        query = select(TenantPack).where(TenantPack.tenant_id == tenant_id)
        
        if status:
            query = query.where(TenantPack.status == status)
        
        # Order by created_at (descending)
        query = query.order_by(desc(TenantPack.created_at))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_version(self, tenant_id: str) -> Optional[TenantPack]:
        """
        Get the latest version for a tenant.
        
        Latest is determined by:
        1. Most recent created_at timestamp
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantPack instance or None if no packs exist for tenant
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        query = (
            select(TenantPack)
            .where(TenantPack.tenant_id == tenant_id)
            .order_by(desc(TenantPack.created_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_tenant_pack(
        self,
        tenant_id: str,
        version: str,
        content_json: dict,
        updated_by: str,
    ) -> TenantPack:
        """
        Update an existing tenant pack version.
        
        Args:
            tenant_id: Tenant identifier (will be normalized)
            version: Version string (will be normalized)
            content_json: New Tenant pack JSON content as dict
            updated_by: User identifier who updated the pack
            
        Returns:
            Updated TenantPack instance
            
        Raises:
            ValueError: If tenant_id/version/content_json/updated_by is invalid
            ValueError: If pack with tenant_id+version not found
        """
        # Normalize inputs by stripping whitespace
        tenant_id = tenant_id.strip() if tenant_id else tenant_id
        version = version.strip() if version else version
        updated_by = updated_by.strip() if updated_by else updated_by
        
        if not tenant_id:
            raise ValueError("tenant_id is required")
        if not version:
            raise ValueError("version is required")
        if not content_json:
            raise ValueError("content_json is required and cannot be empty")
        if not updated_by:
            raise ValueError("updated_by is required")
        
        # Get existing pack
        existing = await self.get_tenant_pack(tenant_id, version)
        if not existing:
            raise ValueError(
                f"Tenant pack not found: tenant_id={tenant_id}, version={version}. "
                f"Cannot update non-existent pack."
            )
        
        # Calculate new checksum
        checksum = calculate_checksum(content_json)
        
        # Update pack content and checksum
        existing.content_json = content_json
        existing.checksum = checksum
        # Note: We don't update created_by or created_at to preserve history
        # But we could add an updated_by/updated_at field in the future
        
        await self.session.flush()
        await self.session.refresh(existing)
        
        logger.info(f"Updated tenant pack: tenant_id={tenant_id}, version={version}, checksum={checksum[:8]}...")
        return existing
    
    async def update_pack_status(
        self,
        pack_id: int,
        status: PackStatus,
    ) -> TenantPack:
        """
        Update pack status.
        
        Args:
            pack_id: Pack database ID
            status: New status
            
        Returns:
            Updated TenantPack instance
            
        Raises:
            ValueError: If pack not found
        """
        query = select(TenantPack).where(TenantPack.id == pack_id)
        result = await self.session.execute(query)
        pack = result.scalar_one_or_none()
        
        if not pack:
            raise ValueError(f"Tenant pack not found: id={pack_id}")
        
        pack.status = status
        await self.session.flush()
        await self.session.refresh(pack)
        
        logger.info(f"Updated tenant pack status: id={pack_id}, status={status.value}")
        return pack

    # AbstractBaseRepository implementations

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[TenantPack]:
        """
        Get tenant pack by ID with tenant isolation.
        
        Args:
            id: Tenant pack database ID (as string)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            TenantPack instance or None if not found
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        try:
            pack_id = int(id)
        except (ValueError, TypeError):
            return None
        
        query = select(TenantPack).where(
            TenantPack.id == pack_id,
            TenantPack.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[TenantPack]:
        """
        List tenant packs for a tenant with pagination.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (status can be passed here)
            
        Returns:
            PaginatedResult with tenant packs
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Extract status filter
        status = filters.get("status")
        
        # Get all tenant packs (with optional status filter)
        all_packs = await self.list_tenant_packs(tenant_id=tenant_id, status=status)
        
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

