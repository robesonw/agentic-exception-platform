"""
Unit tests for LLM Provider Configuration Registry.

Tests caching, invalidation, and versioning functionality.
"""

import pytest

from src.llm.base import LLMClient, LLMResponse
from src.llm.dummy_llm import DummyLLMClient
from src.llm.registry import (
    LLMProviderRegistry,
    ProviderConfigEntry,
    ProviderKey,
    registry,
)


class TestProviderKey:
    """Test cases for ProviderKey dataclass."""
    
    def test_provider_key_creation(self):
        """Test creating ProviderKey instances."""
        # Global key (no tenant, no domain)
        key1 = ProviderKey(tenant_id=None, domain=None)
        assert key1.tenant_id is None
        assert key1.domain is None
        
        # Domain-only key
        key2 = ProviderKey(tenant_id=None, domain="Finance")
        assert key2.tenant_id is None
        assert key2.domain == "Finance"
        
        # Tenant-only key
        key3 = ProviderKey(tenant_id="TENANT_001", domain=None)
        assert key3.tenant_id == "TENANT_001"
        assert key3.domain is None
        
        # Tenant + domain key
        key4 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        assert key4.tenant_id == "TENANT_001"
        assert key4.domain == "Finance"
    
    def test_provider_key_immutability(self):
        """Test that ProviderKey is immutable (frozen dataclass)."""
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        
        # Attempting to modify should raise AttributeError
        with pytest.raises(AttributeError):
            key.tenant_id = "TENANT_002"
        
        with pytest.raises(AttributeError):
            key.domain = "Healthcare"
    
    def test_provider_key_hashable(self):
        """Test that ProviderKey is hashable (can be used as dict key)."""
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key3 = ProviderKey(tenant_id="TENANT_002", domain="Finance")
        
        # Same values should be equal and have same hash
        assert key1 == key2
        assert hash(key1) == hash(key2)
        
        # Different values should be different
        assert key1 != key3
        assert hash(key1) != hash(key3)
        
        # Can be used as dict key
        d = {key1: "value1", key3: "value3"}
        assert d[key1] == "value1"
        assert d[key2] == "value1"  # Same key
        assert d[key3] == "value3"


class TestProviderConfigEntry:
    """Test cases for ProviderConfigEntry dataclass."""
    
    def test_config_entry_creation(self):
        """Test creating ProviderConfigEntry instances."""
        entry = ProviderConfigEntry(
            provider="openrouter",
            model="gpt-4.1-mini",
            version=1
        )
        assert entry.provider == "openrouter"
        assert entry.model == "gpt-4.1-mini"
        assert entry.version == 1
    
    def test_config_entry_default_version(self):
        """Test that version defaults to 1."""
        entry = ProviderConfigEntry(provider="openrouter", model="gpt-4.1-mini")
        assert entry.version == 1


class TestLLMProviderRegistry:
    """Test cases for LLMProviderRegistry class."""
    
    def test_registry_initialization(self):
        """Test that registry initializes with empty caches."""
        reg = LLMProviderRegistry()
        assert len(reg._config_by_key) == 0
        assert len(reg._client_by_key) == 0
        assert reg._global_version == 1
    
    def test_set_client_and_get_client(self):
        """Test setting and getting clients from registry."""
        reg = LLMProviderRegistry()
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        config = ProviderConfigEntry(
            provider="openrouter",
            model="gpt-4.1-mini",
            version=1
        )
        client = DummyLLMClient()
        
        # Initially, no client should be cached
        assert reg.get_client(key) is None
        assert reg.get_config(key) is None
        
        # Set client
        reg.set_client(key, config, client)
        
        # Should be able to retrieve it
        cached_client = reg.get_client(key)
        assert cached_client is not None
        assert cached_client == client
        
        # Should also be able to retrieve config
        cached_config = reg.get_config(key)
        assert cached_config is not None
        assert cached_config.provider == "openrouter"
        assert cached_config.model == "gpt-4.1-mini"
        assert cached_config.version == 1
    
    def test_set_client_validation(self):
        """Test that set_client validates configuration."""
        reg = LLMProviderRegistry()
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        client = DummyLLMClient()
        
        # Empty provider should raise ValueError
        with pytest.raises(ValueError, match="Provider name cannot be empty"):
            config = ProviderConfigEntry(provider="", model="gpt-4.1-mini")
            reg.set_client(key, config, client)
        
        # Empty model should raise ValueError
        with pytest.raises(ValueError, match="Model name cannot be empty"):
            config = ProviderConfigEntry(provider="openrouter", model="")
            reg.set_client(key, config, client)
        
        # Invalid version should raise ValueError
        with pytest.raises(ValueError, match="Version must be >= 1"):
            config = ProviderConfigEntry(
                provider="openrouter",
                model="gpt-4.1-mini",
                version=0
            )
            reg.set_client(key, config, client)
    
    def test_invalidate_by_key(self):
        """Test invalidating a specific key."""
        reg = LLMProviderRegistry()
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_002", domain="Healthcare")
        
        config1 = ProviderConfigEntry(provider="openrouter", model="gpt-4.1-mini")
        config2 = ProviderConfigEntry(provider="openrouter", model="gpt-4o-mini")
        client1 = DummyLLMClient()
        client2 = DummyLLMClient()
        
        # Set both clients
        reg.set_client(key1, config1, client1)
        reg.set_client(key2, config2, client2)
        
        # Both should be cached
        assert reg.get_client(key1) is not None
        assert reg.get_client(key2) is not None
        
        # Invalidate key1
        reg.invalidate(key1)
        
        # key1 should be gone, key2 should still be there
        assert reg.get_client(key1) is None
        assert reg.get_config(key1) is None
        assert reg.get_client(key2) is not None
        assert reg.get_config(key2) is not None
    
    def test_invalidate_all(self):
        """Test invalidating all cached entries."""
        reg = LLMProviderRegistry()
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_002", domain="Healthcare")
        
        config1 = ProviderConfigEntry(provider="openrouter", model="gpt-4.1-mini")
        config2 = ProviderConfigEntry(provider="openrouter", model="gpt-4o-mini")
        client1 = DummyLLMClient()
        client2 = DummyLLMClient()
        
        # Set both clients
        reg.set_client(key1, config1, client1)
        reg.set_client(key2, config2, client2)
        
        # Both should be cached
        assert reg.get_client(key1) is not None
        assert reg.get_client(key2) is not None
        
        # Invalidate all
        reg.invalidate(None)
        
        # Both should be gone
        assert reg.get_client(key1) is None
        assert reg.get_config(key1) is None
        assert reg.get_client(key2) is None
        assert reg.get_config(key2) is None
    
    def test_bump_global_version(self):
        """Test bumping global version."""
        reg = LLMProviderRegistry()
        assert reg.get_global_version() == 1
        
        # Bump version
        new_version = reg.bump_global_version()
        assert new_version == 2
        assert reg.get_global_version() == 2
        
        # Bump again
        new_version = reg.bump_global_version()
        assert new_version == 3
        assert reg.get_global_version() == 3
    
    def test_get_cache_stats(self):
        """Test getting cache statistics."""
        reg = LLMProviderRegistry()
        
        # Initially empty
        stats = reg.get_cache_stats()
        assert stats["cached_clients"] == 0
        assert stats["cached_configs"] == 0
        assert stats["global_version"] == 1
        
        # Add some entries
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_002", domain="Healthcare")
        
        config1 = ProviderConfigEntry(provider="openrouter", model="gpt-4.1-mini")
        config2 = ProviderConfigEntry(provider="openrouter", model="gpt-4o-mini")
        client1 = DummyLLMClient()
        client2 = DummyLLMClient()
        
        reg.set_client(key1, config1, client1)
        reg.set_client(key2, config2, client2)
        
        # Check stats
        stats = reg.get_cache_stats()
        assert stats["cached_clients"] == 2
        assert stats["cached_configs"] == 2
        assert stats["global_version"] == 1
        
        # Invalidate one
        reg.invalidate(key1)
        stats = reg.get_cache_stats()
        assert stats["cached_clients"] == 1
        assert stats["cached_configs"] == 1
    
    def test_multiple_keys_same_client(self):
        """Test that same client can be cached under different keys."""
        reg = LLMProviderRegistry()
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_002", domain="Finance")
        
        config = ProviderConfigEntry(provider="openrouter", model="gpt-4.1-mini")
        client = DummyLLMClient()
        
        # Set same client for both keys
        reg.set_client(key1, config, client)
        reg.set_client(key2, config, client)
        
        # Both should return the same client instance
        assert reg.get_client(key1) == client
        assert reg.get_client(key2) == client
        assert reg.get_client(key1) == reg.get_client(key2)
    
    def test_version_tracking(self):
        """Test that version is tracked per configuration entry."""
        reg = LLMProviderRegistry()
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        
        # Set initial config with version 1
        config1 = ProviderConfigEntry(
            provider="openrouter",
            model="gpt-4.1-mini",
            version=1
        )
        client1 = DummyLLMClient()
        reg.set_client(key, config1, client1)
        
        # Bump global version
        reg.bump_global_version()
        
        # Set new config with version 2
        config2 = ProviderConfigEntry(
            provider="openrouter",
            model="gpt-4o",
            version=2
        )
        client2 = DummyLLMClient()
        reg.set_client(key, config2, client2)
        
        # Should have latest config
        cached_config = reg.get_config(key)
        assert cached_config.version == 2
        assert cached_config.model == "gpt-4o"


class TestModuleLevelRegistry:
    """Test cases for module-level singleton registry."""
    
    def test_registry_singleton(self):
        """Test that module-level registry is a singleton."""
        from src.llm.registry import registry as reg1
        from src.llm.registry import registry as reg2
        
        # Should be the same instance
        assert reg1 is reg2
    
    def test_registry_isolation(self):
        """Test that registry operations don't interfere with each other in tests."""
        # Clear registry before test
        registry.invalidate(None)
        
        key = ProviderKey(tenant_id="TEST_TENANT", domain="TestDomain")
        config = ProviderConfigEntry(provider="dummy", model="dummy-model")
        client = DummyLLMClient()
        
        # Set client
        registry.set_client(key, config, client)
        
        # Should be retrievable
        assert registry.get_client(key) is not None
        
        # Clean up after test
        registry.invalidate(key)

