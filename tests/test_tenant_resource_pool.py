"""
Tests for Tenant Resource Pool (P3-24).

Tests resource pooling, tenant isolation, and cleanup.
"""

import pytest

from src.infrastructure.resources import (
    TenantResourcePool,
    TenantResourcePoolRegistry,
    get_resource_pool,
    get_resource_pool_registry,
)


class TestTenantResourcePool:
    """Tests for TenantResourcePool."""

    def test_pool_initialization(self):
        """Test pool initialization."""
        pool = TenantResourcePool(tenant_id="tenant_001")
        
        assert pool.tenant_id == "tenant_001"
        assert len(pool.db_connections) == 0
        assert len(pool.vector_db_clients) == 0
        assert pool.tool_client_limiter is None
        assert pool.usage_count == 0

    def test_db_connection_management(self):
        """Test DB connection management."""
        pool = TenantResourcePool(tenant_id="tenant_001")
        
        # Mock connection
        mock_conn = {"type": "db_connection", "name": "default"}
        
        pool.set_db_connection("default", mock_conn)
        
        retrieved = pool.get_db_connection("default")
        assert retrieved == mock_conn
        
        # Non-existent connection
        assert pool.get_db_connection("nonexistent") is None

    def test_vector_db_client_management(self):
        """Test vector DB client management."""
        pool = TenantResourcePool(tenant_id="tenant_001")
        
        # Mock client
        mock_client = {"type": "vector_db", "name": "default"}
        
        pool.set_vector_db_client("default", mock_client)
        
        retrieved = pool.get_vector_db_client("default")
        assert retrieved == mock_client
        
        # Non-existent client
        assert pool.get_vector_db_client("nonexistent") is None

    def test_usage_tracking(self):
        """Test usage tracking."""
        pool = TenantResourcePool(tenant_id="tenant_001")
        
        assert pool.usage_count == 0
        assert pool.created_at is None
        assert pool.last_used is None
        
        pool.record_usage()
        
        assert pool.usage_count == 1
        assert pool.created_at is not None
        assert pool.last_used is not None
        
        pool.record_usage()
        
        assert pool.usage_count == 2
        assert pool.last_used > pool.created_at


class TestTenantResourcePoolRegistry:
    """Tests for TenantResourcePoolRegistry."""

    def test_registry_initialization(self):
        """Test registry initialization."""
        registry = TenantResourcePoolRegistry()
        
        assert len(registry.list_tenants()) == 0

    def test_get_or_create_pool(self):
        """Test getting or creating a pool."""
        registry = TenantResourcePoolRegistry()
        
        pool1 = registry.get_pool("tenant_001")
        pool2 = registry.get_pool("tenant_001")
        
        # Should return same instance
        assert pool1 is pool2
        assert pool1.tenant_id == "tenant_001"
        assert pool1.usage_count > 0

    def test_multiple_tenants(self):
        """Test multiple tenants."""
        registry = TenantResourcePoolRegistry()
        
        pool1 = registry.get_pool("tenant_001")
        pool2 = registry.get_pool("tenant_002")
        
        assert pool1 is not pool2
        assert pool1.tenant_id == "tenant_001"
        assert pool2.tenant_id == "tenant_002"
        
        tenants = registry.list_tenants()
        assert "tenant_001" in tenants
        assert "tenant_002" in tenants
        assert len(tenants) == 2

    def test_remove_pool(self):
        """Test removing a pool."""
        registry = TenantResourcePoolRegistry()
        
        pool = registry.get_pool("tenant_001")
        pool.set_db_connection("default", {"mock": "connection"})
        
        assert "tenant_001" in registry.list_tenants()
        
        removed = registry.remove_pool("tenant_001")
        assert removed is True
        
        assert "tenant_001" not in registry.list_tenants()
        
        # Removing again should return False
        removed2 = registry.remove_pool("tenant_001")
        assert removed2 is False

    def test_cleanup_resources(self):
        """Test that resources are cleaned up when pool is removed."""
        registry = TenantResourcePoolRegistry()
        
        pool = registry.get_pool("tenant_001")
        
        # Mock connection with close method
        class MockConnection:
            def __init__(self):
                self.closed = False
            
            def close(self):
                self.closed = True
        
        conn = MockConnection()
        pool.set_db_connection("default", conn)
        
        # Mock vector DB client with close method
        class MockClient:
            def __init__(self):
                self.closed = False
            
            def close(self):
                self.closed = True
        
        client = MockClient()
        pool.set_vector_db_client("default", client)
        
        # Remove pool (should cleanup)
        registry.remove_pool("tenant_001")
        
        assert conn.closed is True
        assert client.closed is True

    def test_registry_stats(self):
        """Test registry statistics."""
        registry = TenantResourcePoolRegistry()
        
        registry.get_pool("tenant_001")
        registry.get_pool("tenant_002")
        
        stats = registry.get_stats()
        
        assert stats["total_pools"] == 2
        assert "tenant_001" in stats["tenant_ids"]
        assert "tenant_002" in stats["tenant_ids"]

    def test_clear_all(self):
        """Test clearing all pools."""
        registry = TenantResourcePoolRegistry()
        
        pool1 = registry.get_pool("tenant_001")
        pool2 = registry.get_pool("tenant_002")
        
        # Add resources
        pool1.set_db_connection("default", {"mock": "conn1"})
        pool2.set_db_connection("default", {"mock": "conn2"})
        
        assert len(registry.list_tenants()) == 2
        
        registry.clear_all()
        
        assert len(registry.list_tenants()) == 0


class TestTenantResourcePoolGlobal:
    """Tests for global resource pool functions."""

    def test_get_resource_pool_registry(self):
        """Test getting global registry instance."""
        registry1 = get_resource_pool_registry()
        registry2 = get_resource_pool_registry()
        
        # Should return same instance
        assert registry1 is registry2

    def test_get_resource_pool(self):
        """Test getting resource pool via global function."""
        pool1 = get_resource_pool("tenant_001")
        pool2 = get_resource_pool("tenant_001")
        
        # Should return same pool instance
        assert pool1 is pool2
        assert pool1.tenant_id == "tenant_001"

    def test_tenant_isolation(self):
        """Test that pools are isolated per tenant."""
        pool1 = get_resource_pool("tenant_001")
        pool2 = get_resource_pool("tenant_002")
        
        assert pool1 is not pool2
        assert pool1.tenant_id == "tenant_001"
        assert pool2.tenant_id == "tenant_002"
        
        # Set resources in one pool
        pool1.set_db_connection("default", {"tenant": "001"})
        pool2.set_db_connection("default", {"tenant": "002"})
        
        # Verify isolation
        assert pool1.get_db_connection("default")["tenant"] == "001"
        assert pool2.get_db_connection("default")["tenant"] == "002"

