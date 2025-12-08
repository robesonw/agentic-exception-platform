"""
LLM Provider Configuration Registry for Phase 5 - LLM Routing.

Provides caching and management of LLM provider configurations and client instances
per tenant/domain combination. Supports hot-reloading and version tracking.

Reference: docs/phase5-llm-routing.md Section 2 (Config-driven routing)
"""

import logging
from dataclasses import dataclass
from typing import Dict, Optional

from src.llm.base import LLMClient

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ProviderKey:
    """
    Immutable key for identifying a provider configuration.
    
    Used as a dictionary key to cache provider configs and clients
    per tenant/domain combination.
    
    Attributes:
        tenant_id: Optional tenant ID (None for global/domain-only configs)
        domain: Optional domain name (None for global/tenant-only configs)
    
    Example:
        # Global config (no tenant, no domain)
        key = ProviderKey(tenant_id=None, domain=None)
        
        # Domain-specific config
        key = ProviderKey(tenant_id=None, domain="Finance")
        
        # Tenant-specific config
        key = ProviderKey(tenant_id="TENANT_001", domain=None)
        
        # Tenant + domain specific config
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
    """
    tenant_id: Optional[str]
    domain: Optional[str]


@dataclass
class ProviderConfigEntry:
    """
    Provider configuration entry with version tracking.
    
    Stores the resolved provider and model configuration along with
    a version number for tracking changes and rollback support.
    
    Attributes:
        provider: Provider name (e.g., "openrouter", "openai", "dummy")
        model: Model identifier (e.g., "gpt-4.1-mini", "gpt-4")
        version: Version number for this configuration (default: 1)
    """
    provider: str
    model: str
    version: int = 1


class LLMProviderRegistry:
    """
    Registry for caching LLM provider configurations and client instances.
    
    This registry provides:
    - Caching of provider configs and client instances per (tenant, domain)
    - Hot-reloading support via invalidation
    - Version tracking for rollback support
    
    Phase 5: In-memory implementation
    TODO (Future phases): Distributed cache integration (Redis, etc.)
    
    Example:
        registry = LLMProviderRegistry()
        
        # Store a client
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        config = ProviderConfigEntry(provider="openrouter", model="gpt-4.1-mini")
        client = OpenRouterLLMClient(...)
        registry.set_client(key, config, client)
        
        # Retrieve a client
        cached_client = registry.get_client(key)
    """
    
    def __init__(self):
        """Initialize the registry with empty caches."""
        # Cache of provider configurations by key
        self._config_by_key: Dict[ProviderKey, ProviderConfigEntry] = {}
        
        # Cache of client instances by key
        self._client_by_key: Dict[ProviderKey, LLMClient] = {}
        
        # Global version counter for tracking configuration changes
        self._global_version: int = 1
    
    def get_client(self, key: ProviderKey) -> Optional[LLMClient]:
        """
        Get cached client instance for a given key.
        
        Args:
            key: ProviderKey identifying the tenant/domain combination
        
        Returns:
            Cached LLMClient instance if found, None otherwise
        """
        return self._client_by_key.get(key)
    
    def set_client(
        self,
        key: ProviderKey,
        config: ProviderConfigEntry,
        client: LLMClient,
    ) -> None:
        """
        Cache a client instance with its configuration.
        
        Validates the configuration before caching and logs the operation.
        
        Args:
            key: ProviderKey identifying the tenant/domain combination
            config: ProviderConfigEntry with provider, model, and version
            client: LLMClient instance to cache
        
        Raises:
            ValueError: If config validation fails
        """
        # Validate config
        if not config.provider or not config.provider.strip():
            raise ValueError("Provider name cannot be empty")
        
        if not config.model or not config.model.strip():
            raise ValueError("Model name cannot be empty")
        
        if config.version < 1:
            raise ValueError("Version must be >= 1")
        
        # Store config and client
        self._config_by_key[key] = config
        self._client_by_key[key] = client
        
        # Log caching operation
        logger.debug(
            f"Cached LLM client: key={key}, provider={config.provider}, "
            f"model={config.model}, version={config.version}"
        )
    
    def invalidate(self, key: Optional[ProviderKey] = None) -> None:
        """
        Invalidate cached client and config for a specific key or all keys.
        
        This is used for hot-reloading when configurations change.
        
        Args:
            key: Optional ProviderKey to invalidate. If None, invalidates all entries.
        
        Example:
            # Invalidate specific tenant/domain
            registry.invalidate(ProviderKey(tenant_id="TENANT_001", domain="Finance"))
            
            # Invalidate all cached entries (hot reload)
            registry.invalidate(None)
        """
        if key is None:
            # Clear all entries
            count = len(self._client_by_key)
            self._config_by_key.clear()
            self._client_by_key.clear()
            logger.info(f"Invalidated all cached LLM clients ({count} entries)")
        else:
            # Clear specific entry
            if key in self._client_by_key:
                del self._client_by_key[key]
                logger.debug(f"Invalidated cached LLM client for key={key}")
            
            if key in self._config_by_key:
                del self._config_by_key[key]
    
    def bump_global_version(self) -> int:
        """
        Increment global version counter and return new version.
        
        This is used to track configuration changes across the system.
        When configs are reloaded, bumping the version allows tracking
        which clients were created with which configuration version.
        
        Returns:
            New global version number
        
        Example:
            version = registry.bump_global_version()  # Returns 2, 3, 4, etc.
        """
        self._global_version += 1
        logger.debug(f"Bumped global version to {self._global_version}")
        return self._global_version
    
    def get_config(self, key: ProviderKey) -> Optional[ProviderConfigEntry]:
        """
        Get cached configuration entry for a given key.
        
        Args:
            key: ProviderKey identifying the tenant/domain combination
        
        Returns:
            Cached ProviderConfigEntry if found, None otherwise
        """
        return self._config_by_key.get(key)
    
    def get_global_version(self) -> int:
        """
        Get current global version number.
        
        Returns:
            Current global version
        """
        return self._global_version
    
    def get_cache_stats(self) -> dict:
        """
        Get statistics about the registry cache.
        
        Returns:
            Dictionary with cache statistics:
            - cached_clients: Number of cached client instances
            - cached_configs: Number of cached configurations
            - global_version: Current global version
        """
        return {
            "cached_clients": len(self._client_by_key),
            "cached_configs": len(self._config_by_key),
            "global_version": self._global_version,
        }
    
    # TODO (Future phases): External config store integration
    # - Support loading configs from external stores (database, Redis, etc.)
    # - Sync registry with external config changes
    # - Support distributed caching across multiple instances
    
    # TODO (Future phases): Versioned snapshots / rollback
    # - Store versioned snapshots of configurations
    # - Support rollback to previous configuration versions
    # - Track configuration history per key


# Module-level singleton registry instance
# This is the global registry used by the factory and other components
registry = LLMProviderRegistry()

