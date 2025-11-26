"""
Domain Pack persistent storage and caching layer.

Phase 2 implementation:
- Filesystem-based storage with versioning
- LRU cache per tenant for performance
- Usage tracking (last_used_timestamp, usage_count)
- Rollback capability

Storage structure:
./runtime/domainpacks/{tenantId}/{domainName}/{version}.json
"""

import json
import logging
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Optional

from src.domainpack.loader import DomainPackValidationError, load_domain_pack
from src.models.domain_pack import DomainPack

logger = logging.getLogger(__name__)


class PackMetadata:
    """Metadata for a stored Domain Pack."""

    def __init__(
        self,
        tenant_id: str,
        domain_name: str,
        version: str,
        last_used_timestamp: Optional[datetime] = None,
        usage_count: int = 0,
    ):
        self.tenant_id = tenant_id
        self.domain_name = domain_name
        self.version = version
        self.last_used_timestamp = last_used_timestamp or datetime.now(timezone.utc)
        self.usage_count = usage_count

    def to_dict(self) -> dict:
        """Convert metadata to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "domain_name": self.domain_name,
            "version": self.version,
            "last_used_timestamp": self.last_used_timestamp.isoformat(),
            "usage_count": self.usage_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "PackMetadata":
        """Create metadata from dictionary."""
        last_used = data.get("last_used_timestamp")
        if isinstance(last_used, str):
            last_used = datetime.fromisoformat(last_used.replace("Z", "+00:00"))
        
        return cls(
            tenant_id=data["tenant_id"],
            domain_name=data["domain_name"],
            version=data["version"],
            last_used_timestamp=last_used,
            usage_count=data.get("usage_count", 0),
        )


class LRUCache:
    """
    Simple LRU (Least Recently Used) cache implementation.
    Thread-safe with locks.
    """

    def __init__(self, max_size: int = 100):
        """
        Initialize LRU cache.
        
        Args:
            max_size: Maximum number of items to cache (default: 100)
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, DomainPack] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> Optional[DomainPack]:
        """
        Get item from cache, moving it to end (most recently used).
        
        Args:
            key: Cache key
            
        Returns:
            Cached DomainPack or None if not found
        """
        with self._lock:
            if key not in self._cache:
                return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            return self._cache[key]

    def put(self, key: str, value: DomainPack) -> None:
        """
        Put item in cache, evicting least recently used if at capacity.
        
        Args:
            key: Cache key
            value: DomainPack to cache
        """
        with self._lock:
            if key in self._cache:
                # Update existing item and move to end
                self._cache[key] = value
                self._cache.move_to_end(key)
            else:
                # Add new item
                if len(self._cache) >= self.max_size:
                    # Evict least recently used (first item)
                    self._cache.popitem(last=False)
                self._cache[key] = value

    def remove(self, key: str) -> None:
        """
        Remove item from cache.
        
        Args:
            key: Cache key
        """
        with self._lock:
            self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all items from cache."""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """Get current cache size."""
        with self._lock:
            return len(self._cache)


class DomainPackStorage:
    """
    Persistent storage for Domain Packs with caching and versioning.
    
    Storage structure:
    ./runtime/domainpacks/{tenantId}/{domainName}/{version}.json
    """

    def __init__(self, storage_root: str = "runtime/domainpacks", cache_size: int = 100):
        """
        Initialize Domain Pack storage.
        
        Args:
            storage_root: Root directory for storage (default: "runtime/domainpacks")
            cache_size: Maximum cache size per tenant (default: 100)
        """
        self.storage_root = Path(storage_root)
        self.cache_size = cache_size
        # Per-tenant LRU caches
        self._caches: dict[str, LRUCache] = {}
        self._cache_lock = Lock()
        # Metadata storage (in-memory for MVP, could be persisted)
        self._metadata: dict[tuple[str, str, str], PackMetadata] = {}
        self._metadata_lock = Lock()
        # Thread safety for storage operations
        self._storage_lock = Lock()

    def _get_cache(self, tenant_id: str) -> LRUCache:
        """
        Get or create LRU cache for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            LRU cache for the tenant
        """
        with self._cache_lock:
            if tenant_id not in self._caches:
                self._caches[tenant_id] = LRUCache(max_size=self.cache_size)
            return self._caches[tenant_id]

    def _get_pack_path(self, tenant_id: str, domain_name: str, version: str) -> Path:
        """
        Get filesystem path for a Domain Pack.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Version string
            
        Returns:
            Path to pack file
        """
        return self.storage_root / tenant_id / domain_name / f"{version}.json"

    def _get_cache_key(self, tenant_id: str, domain_name: str, version: str) -> str:
        """
        Generate cache key for a pack.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Version string
            
        Returns:
            Cache key string
        """
        return f"{tenant_id}:{domain_name}:{version}"

    def _update_usage(self, tenant_id: str, domain_name: str, version: str) -> None:
        """
        Update usage tracking for a pack.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Version string
        """
        key = (tenant_id, domain_name, version)
        with self._metadata_lock:
            if key in self._metadata:
                metadata = self._metadata[key]
                metadata.usage_count += 1
                metadata.last_used_timestamp = datetime.now(timezone.utc)
            else:
                self._metadata[key] = PackMetadata(
                    tenant_id=tenant_id,
                    domain_name=domain_name,
                    version=version,
                    last_used_timestamp=datetime.now(timezone.utc),
                    usage_count=1,
                )

    def store_pack(
        self, tenant_id: str, pack: DomainPack, version: str = "1.0.0"
    ) -> None:
        """
        Store a Domain Pack persistently.
        
        Args:
            tenant_id: Tenant identifier
            pack: DomainPack instance to store
            version: Version string (default: "1.0.0")
            
        Raises:
            ValueError: If tenant_id or version is invalid
            DomainPackValidationError: If pack validation fails
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        if not version or not isinstance(version, str):
            raise ValueError("version must be a non-empty string")
        
        pack_path = self._get_pack_path(tenant_id, pack.domain_name, version)
        
        with self._storage_lock:
            # Create directory structure
            pack_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Serialize pack to JSON
            pack_json = pack.model_dump_json(exclude_none=False)
            
            # Write to file
            with open(pack_path, "w", encoding="utf-8") as f:
                f.write(pack_json)
            
            logger.info(
                f"Stored Domain Pack '{pack.domain_name}' version {version} "
                f"for tenant '{tenant_id}' at {pack_path}"
            )
            
            # Update cache
            cache_key = self._get_cache_key(tenant_id, pack.domain_name, version)
            cache = self._get_cache(tenant_id)
            cache.put(cache_key, pack)
            
            # Initialize metadata
            key = (tenant_id, pack.domain_name, version)
            with self._metadata_lock:
                if key not in self._metadata:
                    self._metadata[key] = PackMetadata(
                        tenant_id=tenant_id,
                        domain_name=pack.domain_name,
                        version=version,
                        last_used_timestamp=datetime.now(timezone.utc),
                        usage_count=0,
                    )

    def get_pack(
        self, tenant_id: str, domain_name: str, version: Optional[str] = None
    ) -> Optional[DomainPack]:
        """
        Retrieve a Domain Pack from storage or cache.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Optional version string. If None, returns latest version.
            
        Returns:
            DomainPack instance or None if not found
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        # If version not specified, find latest version
        if version is None:
            versions = self.list_versions(tenant_id, domain_name)
            if not versions:
                return None
            version = versions[-1]  # Latest version (sorted)
        
        cache_key = self._get_cache_key(tenant_id, domain_name, version)
        cache = self._get_cache(tenant_id)
        
        # Try cache first
        cached_pack = cache.get(cache_key)
        if cached_pack is not None:
            self._update_usage(tenant_id, domain_name, version)
            logger.debug(f"Cache hit for {cache_key}")
            return cached_pack
        
        # Cache miss - load from filesystem
        pack_path = self._get_pack_path(tenant_id, domain_name, version)
        
        if not pack_path.exists():
            logger.debug(f"Pack not found at {pack_path}")
            return None
        
        try:
            pack = load_domain_pack(str(pack_path))
            
            # Update cache
            cache.put(cache_key, pack)
            
            # Update usage tracking
            self._update_usage(tenant_id, domain_name, version)
            
            logger.debug(f"Loaded pack from storage: {cache_key}")
            return pack
            
        except Exception as e:
            logger.error(f"Failed to load pack from {pack_path}: {e}", exc_info=True)
            return None

    def list_versions(self, tenant_id: str, domain_name: str) -> list[str]:
        """
        List all versions for a domain within a tenant namespace.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            
        Returns:
            List of version strings, sorted (oldest to newest)
            
        Raises:
            ValueError: If tenant_id is invalid
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        domain_dir = self.storage_root / tenant_id / domain_name
        
        if not domain_dir.exists():
            return []
        
        versions = []
        for file_path in domain_dir.glob("*.json"):
            version = file_path.stem  # Filename without extension
            versions.append(version)
        
        # Sort versions (simple string sort for MVP)
        # In production, could use semantic versioning comparison
        return sorted(versions)

    def rollback_version(
        self, tenant_id: str, domain_name: str, target_version: str
    ) -> bool:
        """
        Rollback to a specific version by making it the latest.
        
        This creates a new version entry pointing to the target version's content.
        The original versions are preserved.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            target_version: Version to rollback to
            
        Returns:
            True if rollback successful, False otherwise
            
        Raises:
            ValueError: If tenant_id or target_version is invalid
        """
        if not tenant_id or not isinstance(tenant_id, str):
            raise ValueError("tenant_id must be a non-empty string")
        
        if not target_version or not isinstance(target_version, str):
            raise ValueError("target_version must be a non-empty string")
        
        # Check if target version exists
        target_path = self._get_pack_path(tenant_id, domain_name, target_version)
        if not target_path.exists():
            logger.warning(
                f"Target version {target_version} not found for "
                f"tenant '{tenant_id}', domain '{domain_name}'"
            )
            return False
        
        # Load the target version pack
        try:
            pack = load_domain_pack(str(target_path))
        except Exception as e:
            logger.error(
                f"Failed to load target version {target_version} for rollback: {e}",
                exc_info=True,
            )
            return False
        
        # Get current latest version to determine new version number
        versions = self.list_versions(tenant_id, domain_name)
        if versions:
            # Increment patch version of latest
            latest_version = versions[-1]
            try:
                parts = latest_version.split(".")
                if len(parts) >= 3:
                    patch = int(parts[2])
                    parts[2] = str(patch + 1)
                    new_version = ".".join(parts)
                else:
                    new_version = f"{latest_version}.rollback"
            except ValueError:
                new_version = f"{latest_version}.rollback"
        else:
            new_version = f"{target_version}.rollback"
        
        # Store as new version (rollback)
        try:
            self.store_pack(tenant_id, pack, new_version)
            logger.info(
                f"Rolled back tenant '{tenant_id}', domain '{domain_name}' "
                f"to version {target_version} (stored as {new_version})"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to store rollback version: {e}", exc_info=True)
            return False

    def get_usage_stats(
        self, tenant_id: str, domain_name: Optional[str] = None
    ) -> dict:
        """
        Get usage statistics for packs.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Optional domain name filter. If None, returns stats for all domains.
            
        Returns:
            Dictionary with usage statistics
        """
        with self._metadata_lock:
            stats = {}
            for (t_id, d_name, version), metadata in self._metadata.items():
                if t_id != tenant_id:
                    continue
                if domain_name and d_name != domain_name:
                    continue
                
                key = f"{d_name}:{version}"
                stats[key] = {
                    "domain_name": d_name,
                    "version": version,
                    "usage_count": metadata.usage_count,
                    "last_used": metadata.last_used_timestamp.isoformat(),
                }
            
            return stats

    def clear_cache(self, tenant_id: Optional[str] = None) -> None:
        """
        Clear cache for a tenant or all tenants.
        
        Args:
            tenant_id: Optional tenant ID. If None, clears all caches.
        """
        with self._cache_lock:
            if tenant_id is None:
                self._caches.clear()
            elif tenant_id in self._caches:
                self._caches[tenant_id].clear()

    def delete_pack(
        self, tenant_id: str, domain_name: str, version: str
    ) -> bool:
        """
        Delete a specific version of a Domain Pack.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name
            version: Version to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        pack_path = self._get_pack_path(tenant_id, domain_name, version)
        
        if not pack_path.exists():
            return False
        
        try:
            with self._storage_lock:
                pack_path.unlink()
                
                # Remove from cache
                cache_key = self._get_cache_key(tenant_id, domain_name, version)
                cache = self._get_cache(tenant_id)
                cache.remove(cache_key)
                
                # Remove metadata
                key = (tenant_id, domain_name, version)
                with self._metadata_lock:
                    self._metadata.pop(key, None)
                
                logger.info(
                    f"Deleted Domain Pack '{domain_name}' version {version} "
                    f"for tenant '{tenant_id}'"
                )
                return True
                
        except Exception as e:
            logger.error(f"Failed to delete pack: {e}", exc_info=True)
            return False

