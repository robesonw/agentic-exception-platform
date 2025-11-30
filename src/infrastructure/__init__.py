"""
Infrastructure module for Phase 3.

Provides resource pooling, caching, and multi-tenant scaling infrastructure.
"""

from src.infrastructure.cache import DomainPackCache, get_domain_pack_cache
from src.infrastructure.partitioning import (
    IndexHint,
    PartitioningHelper,
    PartitionKey,
    REQUIRED_INDEXES,
)
from src.infrastructure.resources import (
    TenantResourcePool,
    TenantResourcePoolRegistry,
    get_resource_pool,
    get_resource_pool_registry,
)

__all__ = [
    # Cache
    "DomainPackCache",
    "get_domain_pack_cache",
    # Resource pools
    "TenantResourcePool",
    "TenantResourcePoolRegistry",
    "get_resource_pool",
    "get_resource_pool_registry",
    # Partitioning
    "PartitionKey",
    "IndexHint",
    "PartitioningHelper",
    "REQUIRED_INDEXES",
]

