"""
Event Partitioning for Phase 9.

Provides partition key generation for event ordering guarantees.
Events are partitioned by (tenant_id, exception_id) to ensure ordering
per exception while allowing parallel processing across exceptions.

Reference: docs/phase9-async-scale-mvp.md Section 6.2
"""

import hashlib
from typing import Optional


def get_partition_key(tenant_id: str, exception_id: Optional[str] = None) -> str:
    """
    Generate partition key for event ordering.
    
    Partition key ensures that events for the same (tenant_id, exception_id)
    are processed in order. Events are partitioned by:
    - tenant_id (required)
    - exception_id (optional, when available)
    
    Format:
    - If both tenant_id and exception_id are provided: "{tenant_id}:{exception_id}"
    - If only tenant_id is provided: "{tenant_id}"
    
    This ensures:
    - Events for the same exception are processed in order
    - Events for different exceptions can be processed in parallel
    - Tenant isolation is maintained
    
    Args:
        tenant_id: Tenant identifier (required)
        exception_id: Optional exception identifier
        
    Returns:
        Partition key string
        
    Raises:
        ValueError: If tenant_id is empty or None
        
    Example:
        >>> get_partition_key("tenant_001", "exc_001")
        "tenant_001:exc_001"
        >>> get_partition_key("tenant_001")
        "tenant_001"
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required and cannot be empty")
    
    if exception_id and exception_id.strip():
        # Both tenant_id and exception_id: concatenate with separator
        return f"{tenant_id}:{exception_id}"
    else:
        # Only tenant_id: use tenant_id as partition key
        return tenant_id


def get_partition_key_hash(tenant_id: str, exception_id: Optional[str] = None) -> str:
    """
    Generate partition key using consistent hashing.
    
    This alternative implementation uses MD5 hash for consistent partition
    assignment. Useful when you need to distribute events across a fixed
    number of partitions (e.g., Kafka partitions).
    
    Args:
        tenant_id: Tenant identifier (required)
        exception_id: Optional exception identifier
        
    Returns:
        Hash-based partition key (hex digest)
        
    Raises:
        ValueError: If tenant_id is empty or None
        
    Example:
        >>> key = get_partition_key_hash("tenant_001", "exc_001")
        >>> len(key) == 32  # MD5 produces 32-character hex string
        True
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required and cannot be empty")
    
    # Build key string
    if exception_id and exception_id.strip():
        key_string = f"{tenant_id}:{exception_id}"
    else:
        key_string = tenant_id
    
    # Generate MD5 hash for consistent partition assignment
    hash_obj = hashlib.md5(key_string.encode("utf-8"))
    return hash_obj.hexdigest()


def get_partition_number(
    tenant_id: str,
    exception_id: Optional[str] = None,
    num_partitions: int = 10,
) -> int:
    """
    Get partition number using consistent hashing.
    
    Maps partition key to a partition number in the range [0, num_partitions-1].
    Useful for Kafka partition assignment.
    
    Args:
        tenant_id: Tenant identifier (required)
        exception_id: Optional exception identifier
        num_partitions: Total number of partitions (default: 10)
        
    Returns:
        Partition number (0 to num_partitions-1)
        
    Raises:
        ValueError: If tenant_id is empty or num_partitions <= 0
        
    Example:
        >>> partition = get_partition_number("tenant_001", "exc_001", num_partitions=5)
        >>> 0 <= partition < 5
        True
    """
    if not tenant_id or not tenant_id.strip():
        raise ValueError("tenant_id is required and cannot be empty")
    if num_partitions <= 0:
        raise ValueError("num_partitions must be > 0")
    
    # Generate hash-based partition key
    partition_key = get_partition_key_hash(tenant_id, exception_id)
    
    # Convert hash to integer and modulo to get partition number
    # Use first 8 characters of hash for better distribution
    hash_int = int(partition_key[:8], 16)
    return hash_int % num_partitions



