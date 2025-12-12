"""
Domain pack repository for versioned domain pack management.

Phase 6 P6-11: DomainPackRepository with version management.

Note: Domain packs are global (not tenant-specific), so this repository
does not enforce tenant isolation. Domain packs are shared across all tenants.
"""

import logging
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DomainPackVersion
from src.repository.base import AbstractBaseRepository

logger = logging.getLogger(__name__)


class DomainPackRepository(AbstractBaseRepository[DomainPackVersion]):
    """
    Repository for domain pack version management.
    
    Provides:
    - Get domain pack by domain and version
    - Get latest domain pack for a domain
    - Create new domain pack version
    - List domain packs (optionally filtered by domain)
    
    Note: Domain packs are global resources, not tenant-specific.
    The AbstractBaseRepository interface requires tenant_id, but for
    DomainPackRepository, tenant_id is ignored (domain packs are shared).
    """

    async def get_domain_pack(
        self,
        domain: str,
        version: int,
    ) -> Optional[DomainPackVersion]:
        """
        Get a domain pack by domain and version.
        
        Args:
            domain: Domain name (e.g., "Finance", "Healthcare")
            version: Version number
            
        Returns:
            DomainPackVersion instance or None if not found
            
        Raises:
            ValueError: If domain is None or empty, or version < 1
        """
        if not domain or not domain.strip():
            raise ValueError("domain is required")
        if version < 1:
            raise ValueError("version must be >= 1")
        
        query = select(DomainPackVersion).where(
            DomainPackVersion.domain == domain,
            DomainPackVersion.version == version,
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_latest_domain_pack(
        self,
        domain: str,
    ) -> Optional[DomainPackVersion]:
        """
        Get the latest domain pack for a domain.
        
        Latest is determined by:
        1. Highest version number (primary)
        2. Most recent created_at (tiebreaker if versions are equal)
        
        Args:
            domain: Domain name (e.g., "Finance", "Healthcare")
            
        Returns:
            DomainPackVersion instance or None if no packs exist for domain
            
        Raises:
            ValueError: If domain is None or empty
        """
        if not domain or not domain.strip():
            raise ValueError("domain is required")
        
        query = (
            select(DomainPackVersion)
            .where(DomainPackVersion.domain == domain)
            .order_by(desc(DomainPackVersion.version), desc(DomainPackVersion.created_at))
            .limit(1)
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_domain_pack_version(
        self,
        domain: str,
        version: int,
        pack_json: dict,
    ) -> DomainPackVersion:
        """
        Create a new domain pack version.
        
        Args:
            domain: Domain name (e.g., "Finance", "Healthcare")
            version: Version number (must be unique for the domain)
            pack_json: Domain pack JSON as a dictionary
            
        Returns:
            Created DomainPackVersion instance
            
        Raises:
            ValueError: If domain is None/empty, version < 1, or pack_json is empty
            ValueError: If a pack with the same domain and version already exists
        """
        if not domain or not domain.strip():
            raise ValueError("domain is required")
        if version < 1:
            raise ValueError("version must be >= 1")
        if not pack_json:
            raise ValueError("pack_json is required and cannot be empty")
        
        # Check if version already exists
        existing = await self.get_domain_pack(domain, version)
        if existing:
            raise ValueError(
                f"Domain pack version already exists: domain={domain}, version={version}"
            )
        
        # Create new version
        domain_pack_version = DomainPackVersion(
            domain=domain,
            version=version,
            pack_json=pack_json,
        )
        
        self.session.add(domain_pack_version)
        await self.session.flush()
        await self.session.refresh(domain_pack_version)
        
        logger.info(f"Created domain pack version: domain={domain}, version={version}")
        return domain_pack_version

    async def list_domain_packs(
        self,
        domain: Optional[str] = None,
    ) -> list[DomainPackVersion]:
        """
        List domain packs, optionally filtered by domain.
        
        Results are ordered by:
        1. Domain name (ascending)
        2. Version number (descending, newest first)
        
        Args:
            domain: Optional domain name filter. If None, returns all domain packs.
            
        Returns:
            List of DomainPackVersion instances
            
        Raises:
            ValueError: If domain is provided but empty
        """
        query = select(DomainPackVersion)
        
        if domain is not None:
            if not domain.strip():
                raise ValueError("domain cannot be empty if provided")
            query = query.where(DomainPackVersion.domain == domain)
        
        # Order by domain (ascending), then version (descending)
        query = query.order_by(
            DomainPackVersion.domain.asc(),
            desc(DomainPackVersion.version),
        )
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    # AbstractBaseRepository implementations
    # Note: Domain packs are global, so tenant_id is ignored for these methods

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[DomainPackVersion]:
        """
        Get domain pack by ID (implements AbstractBaseRepository interface).
        
        For DomainPackRepository, the id parameter is the domain pack's database ID.
        The tenant_id parameter is ignored (domain packs are global).
        
        Args:
            id: Domain pack database ID (as string)
            tenant_id: Ignored (domain packs are global)
            
        Returns:
            DomainPackVersion instance or None if not found
        """
        try:
            pack_id = int(id)
        except (ValueError, TypeError):
            return None
        
        query = select(DomainPackVersion).where(DomainPackVersion.id == pack_id)
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
        List domain packs (implements AbstractBaseRepository interface).
        
        For DomainPackRepository, tenant_id is ignored (domain packs are global).
        This method delegates to list_domain_packs() with optional domain filter.
        
        Args:
            tenant_id: Ignored (domain packs are global)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (domain can be passed here)
            
        Returns:
            PaginatedResult with domain packs
        """
        from src.repository.base import PaginatedResult
        
        # Extract domain filter if provided
        domain = filters.get("domain")
        
        # Get all domain packs (with optional domain filter)
        all_packs = await self.list_domain_packs(domain=domain)
        
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


