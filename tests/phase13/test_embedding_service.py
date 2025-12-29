"""
Unit tests for Phase 13 EmbeddingService.

Tests:
- Mock embedding provider
- Embedding generation
- Batch embedding
- Caching behavior
- Configuration
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.services.copilot.embedding_service import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
    MockEmbeddingProvider,
    OpenAIEmbeddingProvider,
)


class TestEmbeddingConfig:
    """Tests for EmbeddingConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = EmbeddingConfig()

        assert config.provider == EmbeddingProvider.MOCK
        assert config.model == "text-embedding-3-small"
        assert config.dimension == 1536
        assert config.batch_size == 100
        assert config.max_retries == 3
        assert config.cache_enabled == True

    def test_custom_config(self):
        """Test custom configuration."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.OPENAI,
            model="text-embedding-3-large",
            dimension=3072,
            api_key="test-key",
            batch_size=50,
        )

        assert config.provider == EmbeddingProvider.OPENAI
        assert config.model == "text-embedding-3-large"
        assert config.dimension == 3072
        assert config.api_key == "test-key"
        assert config.batch_size == 50

    def test_from_env_defaults(self):
        """Test loading from environment with defaults."""
        with patch.dict('os.environ', {}, clear=True):
            config = EmbeddingConfig.from_env()

        assert config.provider == EmbeddingProvider.MOCK
        assert config.model == "text-embedding-3-small"
        assert config.dimension == 1536

    def test_from_env_custom(self):
        """Test loading from environment with custom values."""
        env = {
            "EMBEDDING_PROVIDER": "openai",
            "EMBEDDING_MODEL": "text-embedding-3-large",
            "EMBEDDING_DIMENSION": "3072",
            "OPENAI_API_KEY": "sk-test-key",
            "EMBEDDING_BATCH_SIZE": "50",
            "EMBEDDING_CACHE_ENABLED": "false",
        }

        with patch.dict('os.environ', env, clear=True):
            config = EmbeddingConfig.from_env()

        assert config.provider == EmbeddingProvider.OPENAI
        assert config.model == "text-embedding-3-large"
        assert config.dimension == 3072
        assert config.api_key == "sk-test-key"
        assert config.batch_size == 50
        assert config.cache_enabled == False


class TestMockEmbeddingProvider:
    """Tests for MockEmbeddingProvider."""

    @pytest.fixture
    def provider(self):
        """Create mock provider."""
        return MockEmbeddingProvider(dimension=1536)

    @pytest.mark.asyncio
    async def test_generate_embedding(self, provider):
        """Test single embedding generation."""
        embedding = await provider.generate_embedding("test text")

        assert isinstance(embedding, list)
        assert len(embedding) == 1536
        assert all(isinstance(x, float) for x in embedding)

    @pytest.mark.asyncio
    async def test_embedding_is_normalized(self, provider):
        """Test that embedding is normalized to unit vector."""
        embedding = await provider.generate_embedding("test text")

        # Check L2 norm is approximately 1
        norm = sum(x ** 2 for x in embedding) ** 0.5
        assert abs(norm - 1.0) < 0.001

    @pytest.mark.asyncio
    async def test_deterministic_embeddings(self, provider):
        """Test that same text produces same embedding."""
        text = "The quick brown fox jumps over the lazy dog."

        emb1 = await provider.generate_embedding(text)
        emb2 = await provider.generate_embedding(text)

        assert emb1 == emb2

    @pytest.mark.asyncio
    async def test_different_texts_different_embeddings(self, provider):
        """Test that different texts produce different embeddings."""
        emb1 = await provider.generate_embedding("Hello world")
        emb2 = await provider.generate_embedding("Goodbye world")

        assert emb1 != emb2

    @pytest.mark.asyncio
    async def test_batch_embeddings(self, provider):
        """Test batch embedding generation."""
        texts = ["text 1", "text 2", "text 3"]
        embeddings = await provider.generate_embeddings_batch(texts)

        assert len(embeddings) == 3
        assert all(len(e) == 1536 for e in embeddings)

    def test_model_name(self, provider):
        """Test model name property."""
        assert provider.model_name == "mock-embedding-model"

    def test_dimension(self, provider):
        """Test dimension property."""
        assert provider.dimension == 1536


class TestEmbeddingService:
    """Tests for EmbeddingService."""

    @pytest.fixture
    def service(self):
        """Create embedding service with mock provider."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            dimension=1536,
            cache_enabled=True,
        )
        return EmbeddingService(config)

    @pytest.mark.asyncio
    async def test_generate_single_embedding(self, service):
        """Test single embedding generation."""
        result = await service.generate_embedding("test text")

        assert isinstance(result, EmbeddingResult)
        assert result.text == "test text"
        assert len(result.embedding) == 1536
        assert result.model == "mock-embedding-model"
        assert result.dimension == 1536
        assert result.cached == False

    @pytest.mark.asyncio
    async def test_caching(self, service):
        """Test embedding caching."""
        text = "test caching"

        # First call - cache miss
        result1 = await service.generate_embedding(text)
        assert result1.cached == False

        # Second call - cache hit
        result2 = await service.generate_embedding(text)
        assert result2.cached == True
        assert result1.embedding == result2.embedding

    @pytest.mark.asyncio
    async def test_cache_disabled(self):
        """Test with caching disabled."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            cache_enabled=False,
        )
        service = EmbeddingService(config)

        result1 = await service.generate_embedding("test")
        result2 = await service.generate_embedding("test")

        # Both should be cache misses
        assert result1.cached == False
        assert result2.cached == False

    @pytest.mark.asyncio
    async def test_batch_generation(self, service):
        """Test batch embedding generation."""
        texts = ["text 1", "text 2", "text 3"]
        results = await service.generate_embeddings_batch(texts)

        assert len(results) == 3
        assert all(isinstance(r, EmbeddingResult) for r in results)
        assert [r.text for r in results] == texts

    @pytest.mark.asyncio
    async def test_batch_with_caching(self, service):
        """Test batch with some cached and some new."""
        # Pre-cache one text
        await service.generate_embedding("cached text")

        texts = ["cached text", "new text 1", "new text 2"]
        results = await service.generate_embeddings_batch(texts)

        assert len(results) == 3
        assert results[0].cached == True  # Was pre-cached
        assert results[1].cached == False
        assert results[2].cached == False

    @pytest.mark.asyncio
    async def test_empty_batch(self, service):
        """Test empty batch returns empty list."""
        results = await service.generate_embeddings_batch([])
        assert results == []

    def test_content_hash(self, service):
        """Test content hash generation."""
        hash1 = service.compute_content_hash("test")
        hash2 = service.compute_content_hash("test")
        hash3 = service.compute_content_hash("different")

        assert hash1 == hash2
        assert hash1 != hash3
        assert len(hash1) == 64  # SHA-256 hex

    def test_clear_cache(self, service):
        """Test cache clearing."""
        # Add something to cache
        service._cache["test"] = [0.1, 0.2, 0.3]
        service._cache_hits = 5
        service._cache_misses = 10

        service.clear_cache()

        assert len(service._cache) == 0
        assert service._cache_hits == 0
        assert service._cache_misses == 0

    def test_cache_stats(self, service):
        """Test cache statistics."""
        # Simulate some cache activity
        service._cache["test1"] = [0.1]
        service._cache["test2"] = [0.2]
        service._cache_hits = 3
        service._cache_misses = 7

        stats = service.get_cache_stats()

        assert stats["cache_size"] == 2
        assert stats["cache_hits"] == 3
        assert stats["cache_misses"] == 7
        assert abs(stats["hit_rate"] - 0.3) < 0.001

    @pytest.mark.asyncio
    async def test_close(self, service):
        """Test service cleanup."""
        # Generate embedding to initialize provider
        await service.generate_embedding("test")

        # Close should not raise
        await service.close()


class TestOpenAIProvider:
    """Tests for OpenAI provider (unit tests with mocks)."""

    def test_requires_api_key(self):
        """Test that API key is required."""
        with pytest.raises(ValueError, match="API key"):
            OpenAIEmbeddingProvider(api_key="")

    def test_create_with_key(self):
        """Test provider creation with API key."""
        provider = OpenAIEmbeddingProvider(
            api_key="sk-test-key",
            model="text-embedding-3-small",
            dimension=1536,
        )

        assert provider.model_name == "text-embedding-3-small"
        assert provider.dimension == 1536

    @pytest.mark.asyncio
    async def test_generate_embedding_calls_api(self):
        """Test that generate_embedding calls the API."""
        provider = OpenAIEmbeddingProvider(
            api_key="sk-test-key",
            model="text-embedding-3-small",
        )

        # Mock the HTTP client
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = MagicMock(return_value={
            "data": [{"index": 0, "embedding": [0.1, 0.2, 0.3]}]
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        provider._client = mock_client

        embedding = await provider.generate_embedding("test")

        assert embedding == [0.1, 0.2, 0.3]
        mock_client.post.assert_called_once()

    @pytest.mark.asyncio
    async def test_batch_maintains_order(self):
        """Test that batch results maintain order."""
        provider = OpenAIEmbeddingProvider(
            api_key="sk-test-key",
        )

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        # Return in different order than requested
        mock_response.json = MagicMock(return_value={
            "data": [
                {"index": 2, "embedding": [0.5, 0.6]},
                {"index": 0, "embedding": [0.1, 0.2]},
                {"index": 1, "embedding": [0.3, 0.4]},
            ]
        })

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.is_closed = False

        provider._client = mock_client

        embeddings = await provider.generate_embeddings_batch(["a", "b", "c"])

        # Should be sorted by index
        assert embeddings[0] == [0.1, 0.2]
        assert embeddings[1] == [0.3, 0.4]
        assert embeddings[2] == [0.5, 0.6]


class TestEmbeddingServiceRetry:
    """Tests for retry logic."""

    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        """Test retry on transient failure."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            max_retries=3,
            retry_delay=0.01,  # Fast for testing
        )
        service = EmbeddingService(config)

        # Replace provider with one that fails first then succeeds
        call_count = 0

        async def failing_then_succeeding(text):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return [0.1, 0.2, 0.3]

        provider = service._get_provider()
        provider.generate_embedding = failing_then_succeeding

        result = await service.generate_embedding("test", use_cache=False)

        assert call_count == 3
        assert result.embedding == [0.1, 0.2, 0.3]

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test that we give up after max retries."""
        config = EmbeddingConfig(
            provider=EmbeddingProvider.MOCK,
            max_retries=2,
            retry_delay=0.01,
        )
        service = EmbeddingService(config)

        async def always_fails(text):
            raise Exception("Permanent error")

        provider = service._get_provider()
        provider.generate_embedding = always_fails

        with pytest.raises(Exception, match="Permanent error"):
            await service.generate_embedding("test", use_cache=False)
