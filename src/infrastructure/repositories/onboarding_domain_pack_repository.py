"""
Domain Pack Repository for onboarding (P12-6).

Provides CRUD operations for domain packs with versioning, checksum, and status management.
All operations enforce tenant isolation where applicable.

Reference: docs/phase12-onboarding-packs-mvp.md Section 5.2
"""

import logging
from typing import Optional

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DomainPack, PackStatus
from src.infrastructure.repositories.pack_checksum_utils import calculate_checksum
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


class DomainPackRepository(AbstractBaseRepository[DomainPack]):
    """
    Repository for domain pack management.
    
    Provides:
    - Create domain pack version
    - Get domain pack by domain and version
    - List domain packs with filters
    - Get latest version for domain
    - Update pack status
    
    Note: Domain packs are global (not tenant-specific), but this repository
    follows the AbstractBaseRepository pattern for consistency.
    """

    async def create_domain_pack(
        self,
        domain: str,
        version: str,
        content_json: dict,
        created_by: str,
        skip_existence_check: bool = False,
    ) -> DomainPack:
        """
        Create a new domain pack version.
        
        Args:
            domain: Domain name (e.g., "Finance", "Healthcare")
            version: Version string (e.g., "v1.0", "v2.3")
            content_json: Domain pack JSON content as dict
            created_by: User identifier who created the pack
            skip_existence_check: If True, skip checking if pack already exists
                                 (use when caller has already verified it doesn't exist)
            
        Returns:
            Created DomainPack instance
            
        Raises:
            ValueError: If domain/version/content_json/created_by is invalid
            ValueError: If pack with same domain+version already exists (when skip_existence_check=False)
        """
        # Normalize inputs by stripping whitespace
        domain = domain.strip() if domain else domain
        version = version.strip() if version else version
        created_by = created_by.strip() if created_by else created_by
        
        if not domain:
            raise ValueError("domain is required")
        if not version:
            raise ValueError("version is required")
        if not content_json:
            raise ValueError("content_json is required and cannot be empty")
        if not created_by:
            raise ValueError("created_by is required")
        
        # Check if a pack with this (domain AND version) combination already exists
        # (unless caller has already verified it doesn't exist)
        # Note: We check the COMBINATION of domain+version, not domain OR version
        if not skip_existence_check:
            existing = await self.get_domain_pack(domain, version)
            if existing:
                raise ValueError(
                    f"Domain pack with domain={domain} AND version={version} already exists. "
                    f"Please use a different version number (e.g., v1.1, v2.0) or delete the existing pack first."
                )
        
        # Calculate checksum
        checksum = calculate_checksum(content_json)
        
        # Create new pack
        domain_pack = DomainPack(
            domain=domain,
            version=version,
            content_json=content_json,
            checksum=checksum,
            status=PackStatus.DRAFT,
            created_by=created_by,
        )
        
        self.session.add(domain_pack)
        await self.session.flush()
        await self.session.refresh(domain_pack)
        
        logger.info(f"Created domain pack: domain={domain}, version={version}, checksum={checksum[:8]}...")
        return domain_pack

    async def get_domain_pack(
        self,
        domain: str,
        version: str,
    ) -> Optional[DomainPack]:
        """
        Get a domain pack by domain AND version (both must match).
        
        IMPORTANT: This checks for the COMBINATION of domain AND version together.
        Multiple packs can have the same domain (with different versions) or
        the same version (with different domains). The uniqueness constraint is
        on (domain, version) as a pair.
        
        Args:
            domain: Domain name (will be stripped of whitespace)
            version: Version string (will be stripped of whitespace)
            
        Returns:
            DomainPack instance or None if not found
            
        Raises:
            ValueError: If domain or version is invalid
        """
        # Normalize inputs by stripping whitespace
        domain = domain.strip() if domain else domain
        version = version.strip() if version else version
        
        if not domain:
            raise ValueError("domain is required")
        if not version:
            raise ValueError("version is required")
        
        # Query uses AND logic: both domain AND version must match together
        query = select(DomainPack).where(
            DomainPack.domain == domain,
            DomainPack.version == version,
        )
        result = await self.session.execute(query)
        pack = result.scalar_one_or_none()
        
        # Debug logging to help diagnose issues
        if pack:
            logger.debug(f"Found existing pack: id={pack.id}, domain='{pack.domain}', version='{pack.version}'")
        else:
            logger.debug(f"No pack found for domain='{domain}' AND version='{version}' combination")
        
        return pack

    async def list_domain_packs(
        self,
        domain: Optional[str] = None,
        status: Optional[PackStatus] = None,
    ) -> list[DomainPack]:
        """
        List domain packs with optional filters.
        
        Results are ordered by:
        1. Domain name (ascending)
        2. Created at (descending, newest first)
        
        Args:
            domain: Optional domain name filter
            status: Optional status filter
            
        Returns:
            List of DomainPack instances
        """
        query = select(DomainPack)
        
        conditions = []
        if domain:
            conditions.append(DomainPack.domain == domain)
        if status:
            conditions.append(DomainPack.status == status)
        
        if conditions:
            query = query.where(and_(*conditions))
        
        # Order by domain (ascending), then created_at (descending)
        query = query.order_by(
            DomainPack.domain.asc(),
            desc(DomainPack.created_at),
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_latest_version(self, domain: str) -> Optional[DomainPack]:
        """
        Get the latest version for a domain.
        
        Latest is determined by:
        1. Most recent created_at timestamp
        
        Args:
            domain: Domain name
            
        Returns:
            DomainPack instance or None if no packs exist for domain
            
        Raises:
            ValueError: If domain is invalid
        """
        if not domain or not domain.strip():
            raise ValueError("domain is required")
        
        query = (
            select(DomainPack)
            .where(DomainPack.domain == domain)
            .order_by(desc(DomainPack.created_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def update_domain_pack(
        self,
        domain: str,
        version: str,
        content_json: dict,
        updated_by: str,
    ) -> DomainPack:
        """
        Update an existing domain pack version.
        
        Args:
            domain: Domain name (will be normalized)
            version: Version string (will be normalized)
            content_json: New Domain pack JSON content as dict
            updated_by: User identifier who updated the pack
            
        Returns:
            Updated DomainPack instance
            
        Raises:
            ValueError: If domain/version/content_json/updated_by is invalid
            ValueError: If pack with domain+version not found
        """
        # Normalize inputs by stripping whitespace
        domain = domain.strip() if domain else domain
        version = version.strip() if version else version
        updated_by = updated_by.strip() if updated_by else updated_by
        
        if not domain:
            raise ValueError("domain is required")
        if not version:
            raise ValueError("version is required")
        if not content_json:
            raise ValueError("content_json is required and cannot be empty")
        if not updated_by:
            raise ValueError("updated_by is required")
        
        # Get existing pack
        existing = await self.get_domain_pack(domain, version)
        if not existing:
            raise ValueError(
                f"Domain pack not found: domain={domain}, version={version}. "
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
        
        logger.info(f"Updated domain pack: domain={domain}, version={version}, checksum={checksum[:8]}...")
        return existing
    
    async def update_pack_status(
        self,
        pack_id: int,
        status: PackStatus,
    ) -> DomainPack:
        """
        Update pack status.
        
        Args:
            pack_id: Pack database ID
            status: New status
            
        Returns:
            Updated DomainPack instance
            
        Raises:
            ValueError: If pack not found
        """
        query = select(DomainPack).where(DomainPack.id == pack_id)
        result = await self.session.execute(query)
        pack = result.scalar_one_or_none()
        
        if not pack:
            raise ValueError(f"Domain pack not found: id={pack_id}")
        
        pack.status = status
        await self.session.flush()
        await self.session.refresh(pack)
        
        logger.info(f"Updated domain pack status: id={pack_id}, status={status.value}")
        return pack

    # AbstractBaseRepository implementations
    # Note: Domain packs are global, so tenant_id is ignored for these methods

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[DomainPack]:
        """
        Get domain pack by ID (implements AbstractBaseRepository interface).
        
        Args:
            id: Domain pack database ID (as string)
            tenant_id: Ignored (domain packs are global)
            
        Returns:
            DomainPack instance or None if not found
        """
        try:
            pack_id = int(id)
        except (ValueError, TypeError):
            return None
        
        query = select(DomainPack).where(DomainPack.id == pack_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[DomainPack]:
        """
        List domain packs (implements AbstractBaseRepository interface).
        
        For DomainPackRepository, tenant_id is ignored (domain packs are global).
        This method delegates to list_domain_packs() with optional filters.
        
        Args:
            tenant_id: Ignored (domain packs are global)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (domain, status can be passed here)
            
        Returns:
            PaginatedResult with domain packs
        """
        # Extract filters
        domain = filters.get("domain")
        status = filters.get("status")
        
        # Get all domain packs (with optional filters)
        all_packs = await self.list_domain_packs(domain=domain, status=status)
        
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

