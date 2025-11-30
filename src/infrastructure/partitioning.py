"""
DB Partitioning and Indexing Hooks (P3-24).

Provides partitioning and indexing support for storage layers to optimize
queries across many tenants and domains.

For MVP, provides hooks and metadata. Actual DB partitioning/indexing
would be implemented when migrating to a real database.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PartitionKey:
    """
    Partition key for multi-tenant data.
    
    Used to organize data by tenant and optionally domain for efficient querying.
    """

    tenant_id: str
    domain: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert partition key to dictionary."""
        result = {"tenant_id": self.tenant_id}
        if self.domain:
            result["domain"] = self.domain
        return result

    def to_string(self) -> str:
        """Convert partition key to string representation."""
        if self.domain:
            return f"{self.tenant_id}:{self.domain}"
        return self.tenant_id


@dataclass
class IndexHint:
    """
    Index hint for query optimization.
    
    Provides metadata about which indexes should be used for a query.
    """

    # Compound indexes
    tenant_domain_created: bool = False  # (tenant_id, domain, created_at)
    tenant_status_severity: bool = False  # (tenant_id, status, severity)
    tenant_created: bool = False  # (tenant_id, created_at)
    domain_created: bool = False  # (domain, created_at)

    def to_dict(self) -> dict[str, Any]:
        """Convert index hint to dictionary."""
        return {
            "tenant_domain_created": self.tenant_domain_created,
            "tenant_status_severity": self.tenant_status_severity,
            "tenant_created": self.tenant_created,
            "domain_created": self.domain_created,
        }


class PartitioningHelper:
    """
    Helper class for partitioning and indexing operations.
    
    Provides utilities for:
    - Generating partition keys
    - Creating index hints
    - Organizing data by tenant/domain
    """

    @staticmethod
    def create_partition_key(tenant_id: str, domain: Optional[str] = None) -> PartitionKey:
        """
        Create partition key from tenant_id and optional domain.
        
        Args:
            tenant_id: Tenant identifier
            domain: Optional domain name
            
        Returns:
            PartitionKey instance
        """
        return PartitionKey(tenant_id=tenant_id, domain=domain)

    @staticmethod
    def create_index_hint(
        tenant_domain_created: bool = False,
        tenant_status_severity: bool = False,
        tenant_created: bool = False,
        domain_created: bool = False,
    ) -> IndexHint:
        """
        Create index hint for query optimization.
        
        Args:
            tenant_domain_created: Use (tenant_id, domain, created_at) index
            tenant_status_severity: Use (tenant_id, status, severity) index
            tenant_created: Use (tenant_id, created_at) index
            domain_created: Use (domain, created_at) index
            
        Returns:
            IndexHint instance
        """
        return IndexHint(
            tenant_domain_created=tenant_domain_created,
            tenant_status_severity=tenant_status_severity,
            tenant_created=tenant_created,
            domain_created=domain_created,
        )

    @staticmethod
    def get_partition_path(base_path: str, partition_key: PartitionKey) -> str:
        """
        Get filesystem path for a partition (for file-based storage).
        
        Args:
            base_path: Base storage path
            partition_key: Partition key
            
        Returns:
            Partition path string
        """
        if partition_key.domain:
            return f"{base_path}/{partition_key.tenant_id}/{partition_key.domain}"
        return f"{base_path}/{partition_key.tenant_id}"

    @staticmethod
    def extract_partition_key(data: dict[str, Any]) -> Optional[PartitionKey]:
        """
        Extract partition key from data dictionary.
        
        Args:
            data: Data dictionary with tenant_id and optionally domain
            
        Returns:
            PartitionKey or None if tenant_id not found
        """
        tenant_id = data.get("tenant_id")
        if not tenant_id:
            return None
        
        domain = data.get("domain") or data.get("normalized_context", {}).get("domain")
        return PartitionKey(tenant_id=tenant_id, domain=domain)


# Index definitions for documentation and future DB implementation
REQUIRED_INDEXES = {
    "exceptions": [
        {
            "name": "idx_tenant_domain_created",
            "fields": ["tenant_id", "domain", "created_at"],
            "description": "Compound index for tenant + domain + time range queries",
        },
        {
            "name": "idx_tenant_status_severity",
            "fields": ["tenant_id", "status", "severity"],
            "description": "Compound index for tenant + status + severity filtering",
        },
        {
            "name": "idx_tenant_created",
            "fields": ["tenant_id", "created_at"],
            "description": "Index for tenant + time range queries",
        },
    ],
    "audit_logs": [
        {
            "name": "idx_tenant_timestamp",
            "fields": ["tenant_id", "timestamp"],
            "description": "Index for tenant + time range audit queries",
        },
        {
            "name": "idx_tenant_event_type",
            "fields": ["tenant_id", "event_type"],
            "description": "Index for tenant + event type filtering",
        },
    ],
    "metrics": [
        {
            "name": "idx_tenant_timestamp",
            "fields": ["tenant_id", "timestamp"],
            "description": "Index for tenant + time range metrics queries",
        },
    ],
}

