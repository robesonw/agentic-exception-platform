"""
Comprehensive tests for Phase 2 Domain Pack storage and caching.

Tests:
- Store and retrieve packs
- Version management
- Rollback functionality
- Cache behavior
- Tenant segregation
- Usage tracking
"""

import json
import time
from pathlib import Path

import pytest

from src.domainpack.loader import DomainPackValidationError
from src.domainpack.storage import DomainPackStorage, LRUCache, PackMetadata
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition


class TestLRUCache:
    """Tests for LRU cache implementation."""

    def test_cache_basic_operations(self):
        """Test basic cache get/put operations."""
        cache = LRUCache(max_size=3)
        
        pack1 = DomainPack(
            domainName="Domain1",
            exceptionTypes={
                "E1": ExceptionTypeDefinition(description="E1", detectionRules=[])
            },
        )
        pack2 = DomainPack(
            domainName="Domain2",
            exceptionTypes={
                "E2": ExceptionTypeDefinition(description="E2", detectionRules=[])
            },
        )
        
        # Put items
        cache.put("key1", pack1)
        cache.put("key2", pack2)
        
        # Get items
        assert cache.get("key1") is not None
        assert cache.get("key1").domain_name == "Domain1"
        assert cache.get("key2") is not None
        assert cache.get("key2").domain_name == "Domain2"
        
        # Get non-existent key
        assert cache.get("key3") is None

    def test_cache_eviction(self):
        """Test that cache evicts least recently used items."""
        cache = LRUCache(max_size=2)
        
        pack1 = DomainPack(
            domainName="Domain1",
            exceptionTypes={
                "E1": ExceptionTypeDefinition(description="E1", detectionRules=[])
            },
        )
        pack2 = DomainPack(
            domainName="Domain2",
            exceptionTypes={
                "E2": ExceptionTypeDefinition(description="E2", detectionRules=[])
            },
        )
        pack3 = DomainPack(
            domainName="Domain3",
            exceptionTypes={
                "E3": ExceptionTypeDefinition(description="E3", detectionRules=[])
            },
        )
        
        # Fill cache to capacity
        cache.put("key1", pack1)
        cache.put("key2", pack2)
        
        # Access key1 to make it most recently used
        cache.get("key1")
        
        # Add third item - should evict key2 (least recently used)
        cache.put("key3", pack3)
        
        # key1 and key3 should be in cache
        assert cache.get("key1") is not None
        assert cache.get("key3") is not None
        
        # key2 should be evicted
        assert cache.get("key2") is None

    def test_cache_remove(self):
        """Test removing items from cache."""
        cache = LRUCache()
        
        pack = DomainPack(
            domainName="Domain1",
            exceptionTypes={
                "E1": ExceptionTypeDefinition(description="E1", detectionRules=[])
            },
        )
        
        cache.put("key1", pack)
        assert cache.get("key1") is not None
        
        cache.remove("key1")
        assert cache.get("key1") is None

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = LRUCache()
        
        pack = DomainPack(
            domainName="Domain1",
            exceptionTypes={
                "E1": ExceptionTypeDefinition(description="E1", detectionRules=[])
            },
        )
        
        cache.put("key1", pack)
        assert cache.size() == 1
        
        cache.clear()
        assert cache.size() == 0
        assert cache.get("key1") is None


class TestDomainPackStorage:
    """Tests for Domain Pack storage."""

    @pytest.fixture
    def storage(self, tmp_path):
        """Create a storage instance with temporary directory."""
        storage_dir = tmp_path / "domainpacks"
        return DomainPackStorage(storage_root=str(storage_dir))

    @pytest.fixture
    def sample_pack(self):
        """Create a sample Domain Pack."""
        return DomainPack(
            domainName="TestDomain",
            exceptionTypes={
                "TestException": ExceptionTypeDefinition(
                    description="Test exception", detectionRules=[]
                )
            },
        )

    def test_store_and_retrieve_pack(self, storage, sample_pack):
        """Test storing and retrieving a pack."""
        # Store pack
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # Retrieve pack
        retrieved = storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        
        assert retrieved is not None
        assert retrieved.domain_name == "TestDomain"
        assert "TestException" in retrieved.exception_types

    def test_store_creates_directory_structure(self, storage, sample_pack, tmp_path):
        """Test that storage creates necessary directory structure."""
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        pack_path = tmp_path / "domainpacks" / "tenant1" / "TestDomain" / "1.0.0.json"
        assert pack_path.exists()

    def test_retrieve_nonexistent_pack(self, storage):
        """Test retrieving a pack that doesn't exist."""
        result = storage.get_pack("tenant1", "NonExistent", version="1.0.0")
        assert result is None

    def test_list_versions(self, storage, sample_pack):
        """Test listing versions for a domain."""
        # Store multiple versions
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        storage.store_pack("tenant1", sample_pack, version="1.1.0")
        storage.store_pack("tenant1", sample_pack, version="2.0.0")
        
        versions = storage.list_versions("tenant1", "TestDomain")
        
        assert "1.0.0" in versions
        assert "1.1.0" in versions
        assert "2.0.0" in versions
        assert len(versions) == 3

    def test_list_versions_empty(self, storage):
        """Test listing versions when none exist."""
        versions = storage.list_versions("tenant1", "NonExistent")
        assert versions == []

    def test_get_latest_version(self, storage, sample_pack):
        """Test retrieving latest version when version not specified."""
        # Store multiple versions
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # Modify pack for new version
        pack2 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={
                "TestException2": ExceptionTypeDefinition(
                    description="Test exception 2", detectionRules=[]
                )
            },
        )
        storage.store_pack("tenant1", pack2, version="2.0.0")
        
        # Get latest (should be 2.0.0)
        latest = storage.get_pack("tenant1", "TestDomain")
        
        assert latest is not None
        assert "TestException2" in latest.exception_types

    def test_rollback_version(self, storage, sample_pack):
        """Test rolling back to a previous version."""
        # Store initial version
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # Store modified version
        pack2 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={
                "TestException2": ExceptionTypeDefinition(
                    description="Test exception 2", detectionRules=[]
                )
            },
        )
        storage.store_pack("tenant1", pack2, version="2.0.0")
        
        # Rollback to version 1.0.0
        success = storage.rollback_version("tenant1", "TestDomain", "1.0.0")
        
        assert success is True
        
        # Verify rollback created new version
        versions = storage.list_versions("tenant1", "TestDomain")
        assert len(versions) >= 3  # Original 2 + rollback
        
        # Get latest should return rollback version
        latest = storage.get_pack("tenant1", "TestDomain")
        assert latest is not None
        assert "TestException" in latest.exception_types  # Original exception type

    def test_rollback_nonexistent_version(self, storage, sample_pack):
        """Test rolling back to a version that doesn't exist."""
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        success = storage.rollback_version("tenant1", "TestDomain", "9.9.9")
        assert success is False

    def test_cache_hit_behavior(self, storage, sample_pack):
        """Test that cache is used on subsequent retrievals."""
        # Store pack
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # First retrieval (cache miss)
        pack1 = storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        assert pack1 is not None
        
        # Delete file to verify cache is used
        pack_path = (
            Path(storage.storage_root) / "tenant1" / "TestDomain" / "1.0.0.json"
        )
        pack_path.unlink()
        
        # Second retrieval (should use cache)
        pack2 = storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        assert pack2 is not None
        assert pack2.domain_name == pack1.domain_name

    def test_tenant_segregation(self, storage, sample_pack):
        """Test that tenants cannot access each other's packs."""
        # Store pack for tenant1
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # Store different pack for tenant2
        pack2 = DomainPack(
            domainName="TestDomain",
            exceptionTypes={
                "DifferentException": ExceptionTypeDefinition(
                    description="Different", detectionRules=[]
                )
            },
        )
        storage.store_pack("tenant2", pack2, version="1.0.0")
        
        # tenant1 should see their pack
        pack1_retrieved = storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        assert pack1_retrieved is not None
        assert "TestException" in pack1_retrieved.exception_types
        
        # tenant2 should see their pack
        pack2_retrieved = storage.get_pack("tenant2", "TestDomain", version="1.0.0")
        assert pack2_retrieved is not None
        assert "DifferentException" in pack2_retrieved.exception_types
        
        # tenant1 should not see tenant2's pack (different content)
        assert "DifferentException" not in pack1_retrieved.exception_types

    def test_tenant_segregation_list_versions(self, storage, sample_pack):
        """Test that version listing is tenant-scoped."""
        # Store versions for tenant1
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        storage.store_pack("tenant1", sample_pack, version="2.0.0")
        
        # Store versions for tenant2
        storage.store_pack("tenant2", sample_pack, version="1.5.0")
        
        # tenant1 should only see their versions
        versions1 = storage.list_versions("tenant1", "TestDomain")
        assert "1.0.0" in versions1
        assert "2.0.0" in versions1
        assert "1.5.0" not in versions1
        
        # tenant2 should only see their versions
        versions2 = storage.list_versions("tenant2", "TestDomain")
        assert "1.5.0" in versions2
        assert "1.0.0" not in versions2
        assert "2.0.0" not in versions2

    def test_usage_tracking(self, storage, sample_pack):
        """Test that usage is tracked per pack."""
        # Store pack
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # Retrieve pack multiple times
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        time.sleep(0.01)  # Small delay to ensure timestamp difference
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        
        # Get usage stats
        stats = storage.get_usage_stats("tenant1", "TestDomain")
        
        assert "TestDomain:1.0.0" in stats
        assert stats["TestDomain:1.0.0"]["usage_count"] == 3
        assert "last_used" in stats["TestDomain:1.0.0"]

    def test_usage_tracking_multiple_versions(self, storage, sample_pack):
        """Test usage tracking for multiple versions."""
        # Store multiple versions
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        storage.store_pack("tenant1", sample_pack, version="2.0.0")
        
        # Use different versions
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        storage.get_pack("tenant1", "TestDomain", version="2.0.0")
        storage.get_pack("tenant1", "TestDomain", version="2.0.0")
        
        # Get usage stats
        stats = storage.get_usage_stats("tenant1", "TestDomain")
        
        assert stats["TestDomain:1.0.0"]["usage_count"] == 1
        assert stats["TestDomain:2.0.0"]["usage_count"] == 2

    def test_usage_tracking_tenant_scoped(self, storage, sample_pack):
        """Test that usage tracking is tenant-scoped."""
        # Store packs for different tenants
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        storage.store_pack("tenant2", sample_pack, version="1.0.0")
        
        # Use packs
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        storage.get_pack("tenant2", "TestDomain", version="1.0.0")
        storage.get_pack("tenant2", "TestDomain", version="1.0.0")
        
        # Get stats for tenant1
        stats1 = storage.get_usage_stats("tenant1")
        assert "TestDomain:1.0.0" in stats1
        assert stats1["TestDomain:1.0.0"]["usage_count"] == 1
        
        # Get stats for tenant2
        stats2 = storage.get_usage_stats("tenant2")
        assert "TestDomain:1.0.0" in stats2
        assert stats2["TestDomain:1.0.0"]["usage_count"] == 2

    def test_invalid_tenant_id(self, storage, sample_pack):
        """Test that invalid tenant_id raises ValueError."""
        with pytest.raises(ValueError, match="tenant_id must be a non-empty string"):
            storage.store_pack("", sample_pack)
        
        with pytest.raises(ValueError, match="tenant_id must be a non-empty string"):
            storage.get_pack("", "TestDomain")
        
        with pytest.raises(ValueError, match="tenant_id must be a non-empty string"):
            storage.list_versions("", "TestDomain")

    def test_invalid_version(self, storage, sample_pack):
        """Test that invalid version raises ValueError."""
        with pytest.raises(ValueError, match="version must be a non-empty string"):
            storage.store_pack("tenant1", sample_pack, version="")
        
        with pytest.raises(ValueError, match="target_version must be a non-empty string"):
            storage.rollback_version("tenant1", "TestDomain", "")

    def test_delete_pack(self, storage, sample_pack):
        """Test deleting a pack."""
        # Store pack
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        
        # Verify it exists
        assert storage.get_pack("tenant1", "TestDomain", version="1.0.0") is not None
        
        # Delete it
        success = storage.delete_pack("tenant1", "TestDomain", "1.0.0")
        assert success is True
        
        # Verify it's gone
        assert storage.get_pack("tenant1", "TestDomain", version="1.0.0") is None
        
        # Verify file is deleted
        pack_path = (
            Path(storage.storage_root) / "tenant1" / "TestDomain" / "1.0.0.json"
        )
        assert not pack_path.exists()

    def test_delete_nonexistent_pack(self, storage):
        """Test deleting a pack that doesn't exist."""
        success = storage.delete_pack("tenant1", "NonExistent", "1.0.0")
        assert success is False

    def test_clear_cache(self, storage, sample_pack):
        """Test clearing cache."""
        # Store and retrieve to populate cache
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        
        # Clear cache for tenant
        storage.clear_cache("tenant1")
        
        # Delete file to verify cache is cleared
        pack_path = (
            Path(storage.storage_root) / "tenant1" / "TestDomain" / "1.0.0.json"
        )
        pack_path.unlink()
        
        # Should not be able to retrieve (cache cleared, file deleted)
        result = storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        assert result is None

    def test_clear_all_caches(self, storage, sample_pack):
        """Test clearing all caches."""
        # Store packs for multiple tenants
        storage.store_pack("tenant1", sample_pack, version="1.0.0")
        storage.store_pack("tenant2", sample_pack, version="1.0.0")
        
        # Retrieve to populate caches
        storage.get_pack("tenant1", "TestDomain", version="1.0.0")
        storage.get_pack("tenant2", "TestDomain", version="1.0.0")
        
        # Clear all caches
        storage.clear_cache()
        
        # Verify caches are cleared (by checking cache size)
        # This is indirect verification since we can't directly access cache size
        # But if we delete files and try to retrieve, we should get None
        pack_path1 = (
            Path(storage.storage_root) / "tenant1" / "TestDomain" / "1.0.0.json"
        )
        pack_path2 = (
            Path(storage.storage_root) / "tenant2" / "TestDomain" / "1.0.0.json"
        )
        
        pack_path1.unlink()
        pack_path2.unlink()
        
        assert storage.get_pack("tenant1", "TestDomain", version="1.0.0") is None
        assert storage.get_pack("tenant2", "TestDomain", version="1.0.0") is None


class TestPackMetadata:
    """Tests for PackMetadata class."""

    def test_metadata_creation(self):
        """Test creating metadata."""
        metadata = PackMetadata(
            tenant_id="tenant1",
            domain_name="TestDomain",
            version="1.0.0",
        )
        
        assert metadata.tenant_id == "tenant1"
        assert metadata.domain_name == "TestDomain"
        assert metadata.version == "1.0.0"
        assert metadata.usage_count == 0
        assert metadata.last_used_timestamp is not None

    def test_metadata_serialization(self):
        """Test metadata serialization to/from dict."""
        metadata = PackMetadata(
            tenant_id="tenant1",
            domain_name="TestDomain",
            version="1.0.0",
            usage_count=5,
        )
        
        # Convert to dict
        data = metadata.to_dict()
        
        assert data["tenant_id"] == "tenant1"
        assert data["domain_name"] == "TestDomain"
        assert data["version"] == "1.0.0"
        assert data["usage_count"] == 5
        assert "last_used_timestamp" in data
        
        # Convert back from dict
        restored = PackMetadata.from_dict(data)
        
        assert restored.tenant_id == metadata.tenant_id
        assert restored.domain_name == metadata.domain_name
        assert restored.version == metadata.version
        assert restored.usage_count == metadata.usage_count

