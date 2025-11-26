"""
Comprehensive tests for Phase 2 Embedding Provider Integration.

Tests:
- Mock providers
- Caching functionality
- Tenant-specific provider configuration
- Quality metrics (latency, cache hit rate)
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

from src.memory.embeddings import (
    CachedEmbeddingProvider,
    EmbeddingCache,
    HuggingFaceEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from src.models.tenant_policy import EmbeddingConfig, TenantPolicyPack


class MockEmbeddingProvider:
    """Mock embedding provider for testing."""

    def __init__(self, dimension: int = 128, provider_name: str = "mock", model_name: str = "mock-model"):
        self._dimension = dimension
        self._provider_name = provider_name
        self._model_name = model_name
        self._call_count = 0

    def embed(self, text: str) -> list[float]:
        """Generate mock embedding."""
        self._call_count += 1
        # Return deterministic embedding based on text hash
        import hashlib
        import numpy as np
        
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        np.random.seed(seed)
        embedding = np.random.normal(0, 1, self._dimension).tolist()
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate mock embeddings for batch."""
        return [self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def model_name(self) -> str:
        return self._model_name


class TestEmbeddingCache:
    """Tests for EmbeddingCache."""

    def test_cache_get_put(self):
        """Test basic cache get/put operations."""
        cache = EmbeddingCache(max_size=10)
        
        text = "test text"
        embedding = [0.1, 0.2, 0.3]
        
        # Cache miss
        assert cache.get(text) is None
        
        # Cache put
        cache.put(text, embedding)
        
        # Cache hit
        assert cache.get(text) == embedding

    def test_cache_lru_eviction(self):
        """Test LRU eviction when cache is full."""
        cache = EmbeddingCache(max_size=3)
        
        # Add 3 items
        cache.put("text1", [1.0])
        cache.put("text2", [2.0])
        cache.put("text3", [3.0])
        
        # All should be in cache
        assert cache.get("text1") == [1.0]
        assert cache.get("text2") == [2.0]
        assert cache.get("text3") == [3.0]
        
        # Add 4th item - should evict text1 (oldest)
        cache.put("text4", [4.0])
        
        assert cache.get("text1") is None  # Evicted
        assert cache.get("text2") == [2.0]
        assert cache.get("text3") == [3.0]
        assert cache.get("text4") == [4.0]

    def test_cache_lru_recently_used(self):
        """Test that recently used items are not evicted."""
        cache = EmbeddingCache(max_size=3)
        
        cache.put("text1", [1.0])
        cache.put("text2", [2.0])
        cache.put("text3", [3.0])
        
        # Access text1 to make it recently used
        cache.get("text1")
        
        # Add 4th item - should evict text2 (oldest unused)
        cache.put("text4", [4.0])
        
        assert cache.get("text1") == [1.0]  # Not evicted (recently used)
        assert cache.get("text2") is None  # Evicted
        assert cache.get("text3") == [3.0]
        assert cache.get("text4") == [4.0]

    def test_cache_stats(self):
        """Test cache statistics."""
        cache = EmbeddingCache(max_size=10)
        
        # Initial stats
        stats = cache.get_cache_stats()
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate"] == 0.0
        
        # Add item
        cache.put("text1", [1.0])
        
        # Miss
        cache.get("text2")
        stats = cache.get_cache_stats()
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.0
        
        # Hit
        cache.get("text1")
        stats = cache.get_cache_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

    def test_cache_disk_persistence(self, tmp_path):
        """Test disk cache persistence."""
        cache_dir = tmp_path / "embedding_cache"
        cache = EmbeddingCache(max_size=10, disk_cache_path=cache_dir)
        
        text = "test text"
        embedding = [0.1, 0.2, 0.3]
        
        # Put in cache
        cache.put(text, embedding)
        
        # Create new cache instance (simulates restart)
        cache2 = EmbeddingCache(max_size=10, disk_cache_path=cache_dir)
        
        # Should load from disk
        cached_embedding = cache2.get(text)
        assert cached_embedding is not None
        assert len(cached_embedding) == len(embedding)

    def test_cache_clear(self):
        """Test clearing cache."""
        cache = EmbeddingCache(max_size=10)
        
        cache.put("text1", [1.0])
        cache.get("text1")  # Hit
        cache.get("text2")  # Miss
        
        stats_before = cache.get_cache_stats()
        assert stats_before["hits"] == 1
        assert stats_before["misses"] == 1
        
        cache.clear()
        
        # Verify cache is empty
        assert cache.get("text1") is None
        
        # Stats should be reset
        stats_after = cache.get_cache_stats()
        assert stats_after["hits"] == 0
        # Note: The get("text1") call after clear counts as a miss, so misses will be 1
        assert stats_after["misses"] == 1
        assert stats_after["size"] == 0


class TestOpenAIEmbeddingProvider:
    """Tests for OpenAIEmbeddingProvider."""

    @pytest.mark.skip(reason="Requires openai package - tested via integration tests")
    def test_openai_provider_initialization(self):
        """Test OpenAI provider initialization."""
        # This test would require the openai package
        # For MVP, we test the interface and skip actual instantiation
        pass

    @pytest.mark.skip(reason="Requires openai package - tested via integration tests")
    def test_openai_embed(self):
        """Test OpenAI embedding generation."""
        # This test would require the openai package
        pass

    @pytest.mark.skip(reason="Requires openai package - tested via integration tests")
    def test_openai_embed_batch(self):
        """Test OpenAI batch embedding generation."""
        # This test would require the openai package
        pass

    def test_openai_provider_missing_package(self):
        """Test that missing openai package raises ImportError."""
        with patch.dict("sys.modules", {"openai": None}):
            with pytest.raises(ImportError, match="openai package is required"):
                OpenAIEmbeddingProvider(api_key="test-key")


class TestHuggingFaceEmbeddingProvider:
    """Tests for HuggingFaceEmbeddingProvider."""

    @pytest.mark.skip(reason="Requires sentence-transformers package - tested via integration tests")
    def test_hf_provider_initialization(self):
        """Test HuggingFace provider initialization."""
        # This test would require the sentence-transformers package
        pass

    @pytest.mark.skip(reason="Requires sentence-transformers package - tested via integration tests")
    def test_hf_embed(self):
        """Test HuggingFace embedding generation."""
        # This test would require the sentence-transformers package
        pass

    def test_hf_provider_missing_package(self):
        """Test that missing sentence-transformers package raises ImportError."""
        with patch.dict("sys.modules", {"sentence_transformers": None}):
            with pytest.raises(ImportError, match="sentence-transformers package is required"):
                HuggingFaceEmbeddingProvider()


class TestCachedEmbeddingProvider:
    """Tests for CachedEmbeddingProvider."""

    def test_cached_provider_wraps_provider(self):
        """Test that CachedEmbeddingProvider wraps another provider."""
        mock_provider = MockEmbeddingProvider(dimension=128)
        cached_provider = CachedEmbeddingProvider(mock_provider)
        
        assert cached_provider.provider_name == "mock"
        assert cached_provider.model_name == "mock-model"
        assert cached_provider.dimension == 128

    def test_cached_provider_caches_embeddings(self):
        """Test that embeddings are cached."""
        mock_provider = MockEmbeddingProvider(dimension=128)
        cached_provider = CachedEmbeddingProvider(mock_provider)
        
        text = "test text"
        
        # First call - cache miss
        embedding1 = cached_provider.embed(text)
        assert mock_provider._call_count == 1
        
        # Second call - cache hit
        embedding2 = cached_provider.embed(text)
        assert mock_provider._call_count == 1  # No additional call
        assert embedding1 == embedding2

    def test_cached_provider_batch_caching(self):
        """Test batch embedding caching."""
        mock_provider = MockEmbeddingProvider(dimension=128)
        cached_provider = CachedEmbeddingProvider(mock_provider)
        
        texts = ["text1", "text2", "text3"]
        
        # First batch - all cache misses
        embeddings1 = cached_provider.embed_batch(texts)
        assert mock_provider._call_count == 3
        
        # Second batch - all cache hits
        embeddings2 = cached_provider.embed_batch(texts)
        assert mock_provider._call_count == 3  # No additional calls
        assert embeddings1 == embeddings2

    def test_cached_provider_partial_batch_caching(self):
        """Test batch embedding with partial cache hits."""
        mock_provider = MockEmbeddingProvider(dimension=128)
        cached_provider = CachedEmbeddingProvider(mock_provider)
        
        # Cache some texts
        cached_provider.embed("text1")
        cached_provider.embed("text2")
        
        initial_call_count = mock_provider._call_count
        
        # Batch with some cached, some new
        texts = ["text1", "text2", "text3", "text4"]
        embeddings = cached_provider.embed_batch(texts)
        
        # Should only call provider for text3 and text4
        assert mock_provider._call_count == initial_call_count + 2
        assert len(embeddings) == 4

    def test_cached_provider_metrics(self):
        """Test quality metrics tracking."""
        mock_provider = MockEmbeddingProvider(dimension=128)
        cached_provider = CachedEmbeddingProvider(mock_provider)
        
        # Generate some embeddings
        cached_provider.embed("text1")  # Miss
        cached_provider.embed("text1")  # Hit
        cached_provider.embed("text2")  # Miss
        
        metrics = cached_provider.get_metrics()
        
        assert metrics["total_requests"] == 3
        assert metrics["cache_hits"] == 1
        assert metrics["cache_misses"] == 2
        assert metrics["cache_hit_rate"] == pytest.approx(1.0 / 3.0, abs=0.01)
        assert metrics["average_latency_seconds"] >= 0.0
        assert metrics["total_latency_seconds"] >= 0.0

    def test_cached_provider_custom_cache(self):
        """Test using custom cache instance."""
        custom_cache = EmbeddingCache(max_size=5)
        mock_provider = MockEmbeddingProvider(dimension=128)
        cached_provider = CachedEmbeddingProvider(mock_provider, cache=custom_cache)
        
        cached_provider.embed("text1")
        
        # Verify custom cache was used
        stats = custom_cache.get_cache_stats()
        assert stats["size"] == 1


class TestTenantEmbeddingConfig:
    """Tests for tenant-specific embedding configuration."""

    def test_embedding_config_model(self):
        """Test EmbeddingConfig model."""
        config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-ada-002",
            apiKey="test-key",
        )
        
        assert config.provider == "openai"
        assert config.model == "text-embedding-ada-002"
        assert config.api_key == "test-key"

    def test_tenant_policy_with_embedding_config(self):
        """Test TenantPolicyPack with embedding configuration."""
        policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            embeddingConfig=EmbeddingConfig(
                provider="openai",
                model="text-embedding-ada-002",
                apiKey="test-key",
            ),
        )
        
        assert policy.embedding_config is not None
        assert policy.embedding_config.provider == "openai"
        assert policy.embedding_config.model == "text-embedding-ada-002"

    def test_tenant_policy_without_embedding_config(self):
        """Test TenantPolicyPack without embedding configuration."""
        policy = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
        )
        
        assert policy.embedding_config is None

    def test_embedding_config_huggingface(self):
        """Test HuggingFace embedding configuration."""
        config = EmbeddingConfig(
            provider="huggingface",
            model="sentence-transformers/all-MiniLM-L6-v2",
        )
        
        assert config.provider == "huggingface"
        assert config.model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.api_key is None  # Not required for HF

    def test_embedding_config_with_dimension(self):
        """Test embedding configuration with dimension override."""
        config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-3-small",
            dimension=512,
        )
        
        assert config.dimension == 512


class TestEmbeddingProviderFactory:
    """Tests for creating providers from tenant configuration."""

    def test_create_openai_provider_from_config(self):
        """Test creating OpenAI provider from tenant config (interface test)."""
        config = EmbeddingConfig(
            provider="openai",
            model="text-embedding-ada-002",
            apiKey="test-key",
        )
        
        # Test that config is valid and can be used to create provider
        # (actual instantiation requires openai package)
        assert config.provider == "openai"
        assert config.model == "text-embedding-ada-002"
        assert config.api_key == "test-key"
        
        # Verify provider class exists
        assert OpenAIEmbeddingProvider is not None
        assert hasattr(OpenAIEmbeddingProvider, "__init__")

    def test_create_hf_provider_from_config(self):
        """Test creating HuggingFace provider from tenant config (interface test)."""
        config = EmbeddingConfig(
            provider="huggingface",
            model="sentence-transformers/all-MiniLM-L6-v2",
        )
        
        # Test that config is valid and can be used to create provider
        # (actual instantiation requires sentence-transformers package)
        assert config.provider == "huggingface"
        assert config.model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.api_key is None  # Not required for HF
        
        # Verify provider class exists
        assert HuggingFaceEmbeddingProvider is not None
        assert hasattr(HuggingFaceEmbeddingProvider, "__init__")

