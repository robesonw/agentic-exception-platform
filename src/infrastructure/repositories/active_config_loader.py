"""
Active Configuration Loader (P12-14).

Loads active domain packs and tenant packs from database based on tenant_active_config.
Provides TTL caching and backward compatibility with file-based packs.

Reference: docs/phase12-onboarding-packs-mvp.md Section 10
"""

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domainpack.loader import load_domain_pack
from src.infrastructure.db.models import DomainPack as DomainPackModel
from src.infrastructure.db.models import TenantActiveConfig, TenantPack as TenantPackModel
from src.infrastructure.repositories.onboarding_domain_pack_repository import (
    DomainPackRepository,
)
from src.infrastructure.repositories.onboarding_tenant_pack_repository import (
    TenantPackRepository,
)
from src.infrastructure.repositories.tenant_active_config_repository import (
    TenantActiveConfigRepository,
)
from src.models.domain_pack import DomainPack as DomainPackPydantic
from src.models.tenant_policy import TenantPolicyPack
from src.tenantpack.loader import load_tenant_policy

logger = logging.getLogger(__name__)

# Default TTL for cache (30 seconds)
DEFAULT_CACHE_TTL = timedelta(seconds=30)


class CachedPack:
    """Cached pack with expiration."""

    def __init__(self, pack: DomainPackPydantic | TenantPolicyPack, expires_at: datetime):
        self.pack = pack
        self.expires_at = expires_at

    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.now(timezone.utc) > self.expires_at


class ActiveConfigLoader:
    """
    Loader for active configuration from database.
    
    Provides:
    - Load active domain pack for tenant
    - Load active tenant pack for tenant
    - TTL caching to reduce database queries
    - Backward compatibility with file-based packs
    """

    def __init__(
        self,
        session: AsyncSession,
        cache_ttl: timedelta = DEFAULT_CACHE_TTL,
        fallback_domain_pack_path: Optional[str] = None,
        fallback_tenant_pack_path: Optional[str] = None,
    ):
        """
        Initialize active config loader.
        
        Args:
            session: Database session
            cache_ttl: Cache TTL (default: 30 seconds)
            fallback_domain_pack_path: Optional fallback path for domain pack file
            fallback_tenant_pack_path: Optional fallback path for tenant pack file
        """
        self.session = session
        self.cache_ttl = cache_ttl
        self.fallback_domain_pack_path = fallback_domain_pack_path
        self.fallback_tenant_pack_path = fallback_tenant_pack_path
        
        # Cache: tenant_id -> (domain_pack, tenant_pack)
        self._cache: dict[str, tuple[CachedPack | None, CachedPack | None]] = {}
        
        # Repositories
        self._active_config_repo = TenantActiveConfigRepository(session)
        self._domain_pack_repo = DomainPackRepository(session)
        self._tenant_pack_repo = TenantPackRepository(session)

    async def load_domain_pack(self, tenant_id: str) -> Optional[DomainPackPydantic]:
        """
        Load active domain pack for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            DomainPack instance or None if not found
        """
        # Check cache first
        cached = self._cache.get(tenant_id)
        if cached:
            domain_pack_cached, _ = cached
            if domain_pack_cached and not domain_pack_cached.is_expired():
                logger.debug(f"Returning cached domain pack for tenant {tenant_id}")
                return domain_pack_cached.pack
            # Cache expired, remove it
            if domain_pack_cached and domain_pack_cached.is_expired():
                self._cache[tenant_id] = (None, cached[1] if cached else None)
        
        # Load from database
        active_config = await self._active_config_repo.get_active_config(tenant_id)
        
        if active_config and active_config.active_domain_pack_version:
            # Load domain pack from database
            # Note: We need to know the domain. For MVP, we'll try to find it
            # In a real implementation, we'd store domain in active_config or require it
            domain_pack_model = await self._find_domain_pack_by_version(
                active_config.active_domain_pack_version
            )
            
            if domain_pack_model:
                try:
                    domain_pack = DomainPackPydantic.model_validate(domain_pack_model.content_json)
                    # Cache it
                    expires_at = datetime.now(timezone.utc) + self.cache_ttl
                    self._cache[tenant_id] = (CachedPack(domain_pack, expires_at), cached[1] if cached else None)
                    logger.info(
                        f"Loaded domain pack from database: tenant={tenant_id}, "
                        f"version={active_config.active_domain_pack_version}"
                    )
                    return domain_pack
                except Exception as e:
                    logger.error(f"Failed to parse domain pack from database: {e}")
        
        # Fallback to file-based loading
        if self.fallback_domain_pack_path:
            try:
                domain_pack = load_domain_pack(self.fallback_domain_pack_path)
                logger.info(
                    f"Loaded domain pack from file (fallback): tenant={tenant_id}, "
                    f"path={self.fallback_domain_pack_path}"
                )
                return domain_pack
            except Exception as e:
                logger.warning(f"Failed to load domain pack from file: {e}")
        
        logger.warning(f"No domain pack found for tenant {tenant_id}")
        return None

    async def load_tenant_pack(self, tenant_id: str) -> Optional[TenantPolicyPack]:
        """
        Load active tenant pack for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantPolicyPack instance or None if not found
        """
        # Check cache first
        cached = self._cache.get(tenant_id)
        if cached:
            _, tenant_pack_cached = cached
            if tenant_pack_cached and not tenant_pack_cached.is_expired():
                logger.debug(f"Returning cached tenant pack for tenant {tenant_id}")
                return tenant_pack_cached.pack
            # Cache expired, remove it
            if tenant_pack_cached and tenant_pack_cached.is_expired():
                self._cache[tenant_id] = (cached[0] if cached else None, None)
        
        # Load from database
        active_config = await self._active_config_repo.get_active_config(tenant_id)
        
        if active_config and active_config.active_tenant_pack_version:
            # Load tenant pack from database
            tenant_pack_model = await self._tenant_pack_repo.get_tenant_pack(
                tenant_id, active_config.active_tenant_pack_version
            )
            
            if tenant_pack_model:
                try:
                    tenant_pack = TenantPolicyPack.model_validate(tenant_pack_model.content_json)
                    # Cache it
                    expires_at = datetime.now(timezone.utc) + self.cache_ttl
                    self._cache[tenant_id] = (cached[0] if cached else None, CachedPack(tenant_pack, expires_at))
                    logger.info(
                        f"Loaded tenant pack from database: tenant={tenant_id}, "
                        f"version={active_config.active_tenant_pack_version}"
                    )
                    return tenant_pack
                except Exception as e:
                    logger.error(f"Failed to parse tenant pack from database: {e}")
        
        # Fallback to file-based loading
        if self.fallback_tenant_pack_path:
            try:
                tenant_pack = load_tenant_policy(self.fallback_tenant_pack_path)
                logger.info(
                    f"Loaded tenant pack from file (fallback): tenant={tenant_id}, "
                    f"path={self.fallback_tenant_pack_path}"
                )
                return tenant_pack
            except Exception as e:
                logger.warning(f"Failed to load tenant pack from file: {e}")
        
        logger.warning(f"No tenant pack found for tenant {tenant_id}")
        return None

    async def _find_domain_pack_by_version(
        self, version: str
    ) -> Optional[DomainPackModel]:
        """
        Find domain pack by version (helper method).
        
        For MVP, we search all domains. In production, we'd store domain in active_config.
        
        Args:
            version: Version string
            
        Returns:
            DomainPackModel instance or None if not found
        """
        # List all domain packs and find one with matching version
        all_packs = await self._domain_pack_repo.list_domain_packs()
        for pack in all_packs:
            if pack.version == version:
                return pack
        return None

    def clear_cache(self, tenant_id: Optional[str] = None) -> None:
        """
        Clear cache for tenant or all tenants.
        
        Args:
            tenant_id: Optional tenant ID. If None, clears all cache.
        """
        if tenant_id:
            self._cache.pop(tenant_id, None)
            logger.debug(f"Cleared cache for tenant {tenant_id}")
        else:
            self._cache.clear()
            logger.debug("Cleared all cache")

