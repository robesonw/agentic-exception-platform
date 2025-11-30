"""
Tenant-Specific Resource Pools (P3-24).

Provides resource pooling and isolation for:
- Database connections
- Vector DB clients
- Tool HTTP clients

Supports many tenants on shared infrastructure with proper isolation.
"""

import logging
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class TenantResourcePool:
    """
    Resource pool for a single tenant.
    
    Manages isolated resources per tenant to support multi-tenant scaling.
    """

    tenant_id: str
    # Database connections (placeholder - actual implementation depends on DB choice)
    db_connections: dict[str, Any] = field(default_factory=dict)
    # Vector DB clients (per tenant namespace)
    vector_db_clients: dict[str, Any] = field(default_factory=dict)
    # Tool HTTP client limiters (rate limiting per tenant)
    tool_client_limiter: Optional[Any] = None
    # Metadata
    created_at: Optional[float] = None
    last_used: Optional[float] = None
    usage_count: int = 0

    def get_db_connection(self, connection_name: str = "default") -> Optional[Any]:
        """
        Get database connection for tenant.
        
        Args:
            connection_name: Name of connection (default: "default")
            
        Returns:
            Database connection object or None if not available
        """
        return self.db_connections.get(connection_name)

    def set_db_connection(self, connection_name: str, connection: Any) -> None:
        """
        Set database connection for tenant.
        
        Args:
            connection_name: Name of connection
            connection: Database connection object
        """
        self.db_connections[connection_name] = connection

    def get_vector_db_client(self, client_name: str = "default") -> Optional[Any]:
        """
        Get vector DB client for tenant.
        
        Args:
            client_name: Name of client (default: "default")
            
        Returns:
            Vector DB client object or None if not available
        """
        return self.vector_db_clients.get(client_name)

    def set_vector_db_client(self, client_name: str, client: Any) -> None:
        """
        Set vector DB client for tenant.
        
        Args:
            client_name: Name of client
            client: Vector DB client object
        """
        self.vector_db_clients[client_name] = client

    def record_usage(self) -> None:
        """Record usage of this resource pool."""
        import time
        
        self.usage_count += 1
        self.last_used = time.time()
        if self.created_at is None:
            self.created_at = time.time()


class TenantResourcePoolRegistry:
    """
    Registry for tenant resource pools.
    
    Provides thread-safe access to tenant-specific resource pools.
    """

    def __init__(self):
        """Initialize the registry."""
        # Key: tenant_id -> TenantResourcePool
        self._pools: dict[str, TenantResourcePool] = {}
        self._lock = Lock()

    def get_pool(self, tenant_id: str) -> TenantResourcePool:
        """
        Get or create resource pool for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantResourcePool instance
        """
        with self._lock:
            if tenant_id not in self._pools:
                self._pools[tenant_id] = TenantResourcePool(tenant_id=tenant_id)
                logger.debug(f"Created resource pool for tenant {tenant_id}")
            
            pool = self._pools[tenant_id]
            pool.record_usage()
            return pool

    def remove_pool(self, tenant_id: str) -> bool:
        """
        Remove resource pool for tenant (cleanup).
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if pool was removed, False if not found
        """
        with self._lock:
            if tenant_id in self._pools:
                pool = self._pools.pop(tenant_id)
                # Cleanup resources
                self._cleanup_pool(pool)
                logger.info(f"Removed resource pool for tenant {tenant_id}")
                return True
            return False

    def _cleanup_pool(self, pool: TenantResourcePool) -> None:
        """
        Cleanup resources in a pool.
        
        Args:
            pool: TenantResourcePool to cleanup
        """
        # Close DB connections
        for conn_name, conn in pool.db_connections.items():
            try:
                if hasattr(conn, "close"):
                    conn.close()
                logger.debug(f"Closed DB connection {conn_name} for tenant {pool.tenant_id}")
            except Exception as e:
                logger.warning(f"Error closing DB connection {conn_name}: {e}")
        
        # Close vector DB clients
        for client_name, client in pool.vector_db_clients.items():
            try:
                if hasattr(client, "close"):
                    client.close()
                logger.debug(f"Closed vector DB client {client_name} for tenant {pool.tenant_id}")
            except Exception as e:
                logger.warning(f"Error closing vector DB client {client_name}: {e}")
        
        pool.db_connections.clear()
        pool.vector_db_clients.clear()

    def list_tenants(self) -> list[str]:
        """
        List all tenant IDs with active resource pools.
        
        Returns:
            List of tenant IDs
        """
        with self._lock:
            return list(self._pools.keys())

    def get_stats(self) -> dict[str, Any]:
        """
        Get registry statistics.
        
        Returns:
            Dictionary with stats (total_pools, tenant_ids, etc.)
        """
        with self._lock:
            return {
                "total_pools": len(self._pools),
                "tenant_ids": list(self._pools.keys()),
            }

    def clear_all(self) -> None:
        """Clear all resource pools (cleanup)."""
        with self._lock:
            for pool in list(self._pools.values()):
                self._cleanup_pool(pool)
            self._pools.clear()
        logger.info("Cleared all resource pools")


# Global registry instance
_resource_pool_registry: Optional[TenantResourcePoolRegistry] = None


def get_resource_pool_registry() -> TenantResourcePoolRegistry:
    """
    Get global resource pool registry instance.
    
    Returns:
        TenantResourcePoolRegistry instance
    """
    global _resource_pool_registry
    if _resource_pool_registry is None:
        _resource_pool_registry = TenantResourcePoolRegistry()
    return _resource_pool_registry


def get_resource_pool(tenant_id: str) -> TenantResourcePool:
    """
    Get resource pool for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        TenantResourcePool instance
    """
    registry = get_resource_pool_registry()
    return registry.get_pool(tenant_id)

