"""
Tests for Domain Pack Cache (P3-24).

Tests LRU caching, lazy loading, invalidation, and tenant isolation.
"""

import pytest

from src.infrastructure.cache import DomainPackCache
from src.models.domain_pack import DomainPack


class TestDomainPackCache:
    """Tests for DomainPackCache."""

    def test_cache_initialization(self):
        """Test cache initialization."""
        cache = DomainPackCache(max_size=100)
        assert cache.max_size == 100
        assert cache.size() == 0

    def test_cache_put_and_get(self):
        """Test putting and getting packs from cache."""
        cache = DomainPackCache(max_size=10)
        
        pack = DomainPack(domain_name="TestDomain")
        cache.put_pack("tenant_001", "TestDomain", "1.0.0", pack)
        
        assert cache.size() == 1
        
        retrieved = cache.get_pack("tenant_001", "TestDomain", "1.0.0")
        assert retrieved is not None
        assert retrieved.domain_name == "TestDomain"

    def test_cache_lru_eviction(self):
        """Test that least recently used items are evicted when cache is full."""
        cache = DomainPackCache(max_size=3)
        
        # Add 3 packs
        for i in range(3):
            pack = DomainPack(domain_name=f"Domain{i}")
            cache.put_pack("tenant_001", f"Domain{i}", "1.0.0", pack)
        
        assert cache.size() == 3
        
        # Access first pack (makes it most recently used)
        cache.get_pack("tenant_001", "Domain0", "1.0.0")
        
        # Add 4th pack (should evict Domain1, the least recently used)
        pack4 = DomainPack(domain_name="Domain3")
        cache.put_pack("tenant_001", "Domain3", "1.0.0", pack4)
        
        assert cache.size() == 3
        
        # Domain0 should still be in cache (was accessed)
        assert cache.get_pack("tenant_001", "Domain0", "1.0.0") is not None
        
        # Domain1 should be evicted
        assert cache.get_pack("tenant_001", "Domain1", "1.0.0") is None
        
        # Domain2 and Domain3 should be in cache
        assert cache.get_pack("tenant_001", "Domain2", "1.0.0") is not None
        assert cache.get_pack("tenant_001", "Domain3", "1.0.0") is not None

    def test_cache_lazy_loading(self):
        """Test lazy loading when cache misses."""
        loaded_packs = {}
        
        def loader(tenant_id: str, domain_name: str, version: str):
            key = (tenant_id, domain_name, version)
            return loaded_packs.get(key)
        
        cache = DomainPackCache(max_size=100, loader_fn=loader)
        
        # Pre-populate loader
        pack = DomainPack(domain_name="LazyDomain")
        loaded_packs[("tenant_001", "LazyDomain", "1.0.0")] = pack
        
        # Get pack (should lazy load)
        retrieved = cache.get_pack("tenant_001", "LazyDomain", "1.0.0")
        assert retrieved is not None
        assert retrieved.domain_name == "LazyDomain"
        
        # Should now be in cache
        assert cache.size() == 1
        
        # Second get should hit cache
        retrieved2 = cache.get_pack("tenant_001", "LazyDomain", "1.0.0")
        assert retrieved2 is not None

    def test_cache_invalidate_specific_version(self):
        """Test invalidating a specific version."""
        cache = DomainPackCache(max_size=10)
        
        pack1 = DomainPack(domain_name="TestDomain")
        pack2 = DomainPack(domain_name="TestDomain")
        
        cache.put_pack("tenant_001", "TestDomain", "1.0.0", pack1)
        cache.put_pack("tenant_001", "TestDomain", "2.0.0", pack2)
        
        assert cache.size() == 2
        
        # Invalidate version 1.0.0
        cache.invalidate("tenant_001", "TestDomain", "1.0.0")
        
        assert cache.get_pack("tenant_001", "TestDomain", "1.0.0") is None
        assert cache.get_pack("tenant_001", "TestDomain", "2.0.0") is not None
        assert cache.size() == 1

    def test_cache_invalidate_all_versions(self):
        """Test invalidating all versions for a domain."""
        cache = DomainPackCache(max_size=10)
        
        pack1 = DomainPack(domain_name="TestDomain")
        pack2 = DomainPack(domain_name="TestDomain")
        
        cache.put_pack("tenant_001", "TestDomain", "1.0.0", pack1)
        cache.put_pack("tenant_001", "TestDomain", "2.0.0", pack2)
        
        assert cache.size() == 2
        
        # Invalidate all versions
        cache.invalidate("tenant_001", "TestDomain")
        
        assert cache.get_pack("tenant_001", "TestDomain", "1.0.0") is None
        assert cache.get_pack("tenant_001", "TestDomain", "2.0.0") is None
        assert cache.size() == 0

    def test_cache_tenant_isolation(self):
        """Test that caches are isolated per tenant."""
        cache = DomainPackCache(max_size=10)
        
        pack1 = DomainPack(domain_name="TestDomain")
        pack2 = DomainPack(domain_name="TestDomain")
        
        cache.put_pack("tenant_001", "TestDomain", "1.0.0", pack1)
        cache.put_pack("tenant_002", "TestDomain", "1.0.0", pack2)
        
        # Each tenant should have their own pack
        retrieved1 = cache.get_pack("tenant_001", "TestDomain", "1.0.0")
        retrieved2 = cache.get_pack("tenant_002", "TestDomain", "1.0.0")
        
        assert retrieved1 is not None
        assert retrieved2 is not None
        assert retrieved1 is not retrieved2  # Different instances
        
        # Invalidate tenant_001 should not affect tenant_002
        cache.invalidate("tenant_001", "TestDomain")
        assert cache.get_pack("tenant_001", "TestDomain", "1.0.0") is None
        assert cache.get_pack("tenant_002", "TestDomain", "1.0.0") is not None

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = DomainPackCache(max_size=10)
        
        pack = DomainPack(domain_name="TestDomain")
        cache.put_pack("tenant_001", "TestDomain", "1.0.0", pack)
        
        # Miss
        cache.get_pack("tenant_001", "OtherDomain", "1.0.0")
        
        # Hit
        cache.get_pack("tenant_001", "TestDomain", "1.0.0")
        
        stats = cache.get_stats()
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0

    def test_cache_clear(self):
        """Test clearing the cache."""
        cache = DomainPackCache(max_size=10)
        
        pack = DomainPack(domain_name="TestDomain")
        cache.put_pack("tenant_001", "TestDomain", "1.0.0", pack)
        
        assert cache.size() == 1
        
        cache.clear()
        
        assert cache.size() == 0
        assert cache.get_pack("tenant_001", "TestDomain", "1.0.0") is None
        
        stats = cache.get_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_cache_latest_version(self):
        """Test caching with 'latest' version."""
        cache = DomainPackCache(max_size=10)
        
        pack = DomainPack(domain_name="TestDomain")
        cache.put_pack("tenant_001", "TestDomain", None, pack)
        
        retrieved = cache.get_pack("tenant_001", "TestDomain", None)
        assert retrieved is not None
        assert retrieved.domain_name == "TestDomain"


class TestDomainPackCacheGlobal:
    """Tests for global domain pack cache instance."""

    def test_get_domain_pack_cache(self):
        """Test getting global cache instance."""
        from src.infrastructure.cache import get_domain_pack_cache
        
        cache1 = get_domain_pack_cache()
        cache2 = get_domain_pack_cache()
        
        # Should return same instance
        assert cache1 is cache2

