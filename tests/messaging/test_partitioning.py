"""
Unit tests for event partitioning.
"""

import pytest

from src.messaging.partitioning import (
    get_partition_key,
    get_partition_key_hash,
    get_partition_number,
)


class TestPartitionKey:
    """Test partition key generation."""
    
    def test_get_partition_key_with_both_ids(self):
        """Test partition key with both tenant_id and exception_id."""
        key = get_partition_key("tenant_001", "exc_001")
        
        assert key == "tenant_001:exc_001"
        
    def test_get_partition_key_with_tenant_only(self):
        """Test partition key with only tenant_id."""
        key = get_partition_key("tenant_001")
        
        assert key == "tenant_001"
        
    def test_get_partition_key_with_none_exception_id(self):
        """Test partition key with None exception_id."""
        key = get_partition_key("tenant_001", None)
        
        assert key == "tenant_001"
        
    def test_get_partition_key_with_empty_exception_id(self):
        """Test partition key with empty exception_id."""
        key = get_partition_key("tenant_001", "")
        
        assert key == "tenant_001"
        
    def test_get_partition_key_with_whitespace_exception_id(self):
        """Test partition key with whitespace-only exception_id."""
        key = get_partition_key("tenant_001", "   ")
        
        assert key == "tenant_001"
        
    def test_get_partition_key_validation_tenant_id_required(self):
        """Test partition key validation requires tenant_id."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            get_partition_key("")
            
        with pytest.raises(ValueError, match="tenant_id is required"):
            get_partition_key(None)
            
    def test_get_partition_key_stable(self):
        """Test partition key generation is stable (deterministic)."""
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_001", "exc_001")
        key3 = get_partition_key("tenant_001", "exc_001")
        
        # Same inputs should produce same output
        assert key1 == key2 == key3
        
    def test_get_partition_key_different_exceptions(self):
        """Test different exceptions produce different partition keys."""
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_001", "exc_002")
        
        assert key1 != key2
        assert key1 == "tenant_001:exc_001"
        assert key2 == "tenant_001:exc_002"
        
    def test_get_partition_key_different_tenants(self):
        """Test different tenants produce different partition keys."""
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_002", "exc_001")
        
        assert key1 != key2
        assert key1 == "tenant_001:exc_001"
        assert key2 == "tenant_002:exc_001"
        
    def test_get_partition_key_same_exception_same_key(self):
        """Test same exception always produces same partition key."""
        # Multiple calls with same inputs
        keys = [
            get_partition_key("tenant_001", "exc_001"),
            get_partition_key("tenant_001", "exc_001"),
            get_partition_key("tenant_001", "exc_001"),
        ]
        
        # All should be identical
        assert len(set(keys)) == 1
        assert keys[0] == "tenant_001:exc_001"


class TestPartitionKeyHash:
    """Test hash-based partition key generation."""
    
    def test_get_partition_key_hash_with_both_ids(self):
        """Test hash partition key with both tenant_id and exception_id."""
        key = get_partition_key_hash("tenant_001", "exc_001")
        
        # MD5 produces 32-character hex string
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)
        
    def test_get_partition_key_hash_with_tenant_only(self):
        """Test hash partition key with only tenant_id."""
        key = get_partition_key_hash("tenant_001")
        
        assert len(key) == 32
        assert all(c in "0123456789abcdef" for c in key)
        
    def test_get_partition_key_hash_stable(self):
        """Test hash partition key generation is stable."""
        key1 = get_partition_key_hash("tenant_001", "exc_001")
        key2 = get_partition_key_hash("tenant_001", "exc_001")
        key3 = get_partition_key_hash("tenant_001", "exc_001")
        
        # Same inputs should produce same hash
        assert key1 == key2 == key3
        
    def test_get_partition_key_hash_different_inputs(self):
        """Test different inputs produce different hashes."""
        key1 = get_partition_key_hash("tenant_001", "exc_001")
        key2 = get_partition_key_hash("tenant_001", "exc_002")
        key3 = get_partition_key_hash("tenant_002", "exc_001")
        
        # All should be different
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3
        
    def test_get_partition_key_hash_validation(self):
        """Test hash partition key validation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            get_partition_key_hash("")
            
        with pytest.raises(ValueError, match="tenant_id is required"):
            get_partition_key_hash(None)


class TestPartitionNumber:
    """Test partition number calculation."""
    
    def test_get_partition_number_with_both_ids(self):
        """Test partition number with both tenant_id and exception_id."""
        partition = get_partition_number("tenant_001", "exc_001", num_partitions=10)
        
        assert 0 <= partition < 10
        
    def test_get_partition_number_with_tenant_only(self):
        """Test partition number with only tenant_id."""
        partition = get_partition_number("tenant_001", num_partitions=5)
        
        assert 0 <= partition < 5
        
    def test_get_partition_number_stable(self):
        """Test partition number is stable (deterministic)."""
        partition1 = get_partition_number("tenant_001", "exc_001", num_partitions=10)
        partition2 = get_partition_number("tenant_001", "exc_001", num_partitions=10)
        partition3 = get_partition_number("tenant_001", "exc_001", num_partitions=10)
        
        # Same inputs should produce same partition number
        assert partition1 == partition2 == partition3
        
    def test_get_partition_number_range(self):
        """Test partition number is within valid range."""
        for num_partitions in [1, 5, 10, 100]:
            partition = get_partition_number("tenant_001", "exc_001", num_partitions=num_partitions)
            assert 0 <= partition < num_partitions
            
    def test_get_partition_number_distribution(self):
        """Test partition numbers are reasonably distributed."""
        partitions = set()
        for i in range(100):
            partition = get_partition_number(f"tenant_{i}", f"exc_{i}", num_partitions=10)
            partitions.add(partition)
        
        # With 100 different inputs and 10 partitions, we should get multiple partitions
        # (exact distribution depends on hash, but should be > 1)
        assert len(partitions) > 1
        
    def test_get_partition_number_validation(self):
        """Test partition number validation."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            get_partition_number("", num_partitions=10)
            
        with pytest.raises(ValueError, match="num_partitions must be > 0"):
            get_partition_number("tenant_001", num_partitions=0)
            
        with pytest.raises(ValueError, match="num_partitions must be > 0"):
            get_partition_number("tenant_001", num_partitions=-1)
            
    def test_get_partition_number_single_partition(self):
        """Test partition number with single partition."""
        partition = get_partition_number("tenant_001", "exc_001", num_partitions=1)
        
        assert partition == 0


class TestPartitionKeyOrdering:
    """Test partition key ordering guarantees."""
    
    def test_same_exception_same_partition_key(self):
        """Test same exception produces same partition key (ordering guarantee)."""
        # Multiple events for same exception
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_001", "exc_001")
        key3 = get_partition_key("tenant_001", "exc_001")
        
        # All should be identical (ensures ordering)
        assert key1 == key2 == key3
        
    def test_different_exceptions_different_partition_keys(self):
        """Test different exceptions produce different partition keys (allows parallel processing)."""
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_001", "exc_002")
        key3 = get_partition_key("tenant_001", "exc_003")
        
        # All should be different (allows parallel processing)
        assert key1 != key2
        assert key1 != key3
        assert key2 != key3
        
    def test_same_tenant_different_exceptions(self):
        """Test same tenant with different exceptions produces different keys."""
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_001", "exc_002")
        
        # Different keys allow parallel processing
        assert key1 != key2
        
    def test_different_tenants_same_exception(self):
        """Test different tenants with same exception_id produces different keys."""
        key1 = get_partition_key("tenant_001", "exc_001")
        key2 = get_partition_key("tenant_002", "exc_001")
        
        # Different keys (tenant isolation)
        assert key1 != key2



