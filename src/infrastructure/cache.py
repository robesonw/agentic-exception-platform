"""
Domain Pack Caching Layer (P3-24).

Provides LRU cache with lazy loading for domain packs to support
many domains per tenant and many tenants on shared infrastructure.
"""

import logging
from collections import OrderedDict
from threading import Lock
from typing import Callable, Optional

from src.models.domain_pack import DomainPack

logger = logging.getLogger(__name__)


class DomainPackCache:
    """
    LRU cache for Domain Packs with lazy loading.
    
    Phase 3: Supports many domains per tenant and many tenants on shared infrastructure.
    Thread-safe with locks.
    """

    def __init__(
        self,
        max_size: int = 1000,
        loader_fn: Optional[Callable[[str, str, Optional[str]], Optional[DomainPack]]] = None,
    ):
        """
        Initialize domain pack cache.
        
        Args:
            max_size: Maximum number of packs to cache (default: 1000)
            loader_fn: Optional function to load packs when cache misses.
                       Signature: (tenant_id, domain_name, version) -> DomainPack | None
        """
        self.max_size = max_size
        self.loader_fn = loader_fn
        # LRU cache: OrderedDict where most recently used is at the end
        # Key: (tenant_id, domain_name, version or "latest")
        self._cache: OrderedDict[tuple[str, str, str], DomainPack] = OrderedDict()
        self._lock = Lock()
        # Track cache hits/misses for metrics
        self._hits = 0
        self._misses = 0

    def get_pack(
        self, tenant_id: str, domain_name: str, version: Optional[str] = None
    ) -> Optional[DomainPack]:
        """
        Get domain pack from cache or load lazily.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Optional version string. If None, uses "latest"
            
        Returns:
            DomainPack instance or None if not found
        """
        cache_key = (tenant_id, domain_name, version or "latest")
        
        with self._lock:
            # Check cache first
            if cache_key in self._cache:
                # Move to end (most recently used)
                pack = self._cache.pop(cache_key)
                self._cache[cache_key] = pack
                self._hits += 1
                logger.debug(f"Cache hit for {tenant_id}:{domain_name}:{version or 'latest'}")
                return pack
            
            # Cache miss
            self._misses += 1
            logger.debug(f"Cache miss for {tenant_id}:{domain_name}:{version or 'latest'}")
        
        # Try lazy loading if loader function provided
        if self.loader_fn:
            try:
                pack = self.loader_fn(tenant_id, domain_name, version)
                if pack is not None:
                    # Add to cache
                    self._put_pack(tenant_id, domain_name, version, pack)
                    return pack
            except Exception as e:
                logger.error(
                    f"Failed to lazy load pack {tenant_id}:{domain_name}:{version}: {e}",
                    exc_info=True,
                )
        
        return None

    def _put_pack(
        self, tenant_id: str, domain_name: str, version: Optional[str], pack: DomainPack
    ) -> None:
        """
        Put pack in cache, evicting least recently used if at capacity.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Optional version string
            pack: DomainPack to cache
        """
        cache_key = (tenant_id, domain_name, version or "latest")
        
        with self._lock:
            if cache_key in self._cache:
                # Update existing and move to end
                self._cache.pop(cache_key)
            elif len(self._cache) >= self.max_size:
                # Evict least recently used (first item)
                evicted_key, evicted_pack = self._cache.popitem(last=False)
                logger.debug(
                    f"Evicted pack from cache: {evicted_key[0]}:{evicted_key[1]}:{evicted_key[2]}"
                )
            
            self._cache[cache_key] = pack

    def put_pack(
        self, tenant_id: str, domain_name: str, version: Optional[str], pack: DomainPack
    ) -> None:
        """
        Explicitly put pack in cache.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Optional version string
            pack: DomainPack to cache
        """
        self._put_pack(tenant_id, domain_name, version, pack)

    def invalidate(
        self, tenant_id: str, domain_name: str, version: Optional[str] = None
    ) -> None:
        """
        Invalidate cache entry.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Optional version string. If None, invalidates all versions for domain.
        """
        with self._lock:
            if version is None:
                # Invalidate all versions for this domain
                keys_to_remove = [
                    key
                    for key in self._cache.keys()
                    if key[0] == tenant_id and key[1] == domain_name
                ]
                for key in keys_to_remove:
                    self._cache.pop(key, None)
                logger.debug(f"Invalidated all versions for {tenant_id}:{domain_name}")
            else:
                # Invalidate specific version
                cache_key = (tenant_id, domain_name, version)
                if cache_key in self._cache:
                    self._cache.pop(cache_key)
                    logger.debug(f"Invalidated {tenant_id}:{domain_name}:{version}")
                # Also invalidate "latest" if it matches
                latest_key = (tenant_id, domain_name, "latest")
                if latest_key in self._cache:
                    self._cache.pop(latest_key)
                    logger.debug(f"Invalidated latest for {tenant_id}:{domain_name}")

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
        logger.info("Cleared domain pack cache")

    def get_stats(self) -> dict[str, int]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache stats (size, hits, misses, hit_rate)
        """
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0.0
            
            return {
                "size": len(self._cache),
                "max_size": self.max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate_percent": round(hit_rate, 2),
            }

    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)


# Global cache instance
_domain_pack_cache: Optional[DomainPackCache] = None


def get_domain_pack_cache() -> DomainPackCache:
    """
    Get global domain pack cache instance.
    
    Returns:
        DomainPackCache instance
    """
    global _domain_pack_cache
    if _domain_pack_cache is None:
        from src.domainpack.storage import DomainPackStorage
        
        storage = DomainPackStorage()
        
        # Create loader function that uses storage
        def loader(tenant_id: str, domain_name: str, version: Optional[str]) -> Optional[DomainPack]:
            return storage.get_pack(tenant_id, domain_name, version)
        
        _domain_pack_cache = DomainPackCache(max_size=1000, loader_fn=loader)
    return _domain_pack_cache

