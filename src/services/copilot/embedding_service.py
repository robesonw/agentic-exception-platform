"""
EmbeddingService for Phase 13 Copilot Intelligence.

Provides provider-agnostic embedding generation with:
- Multiple provider support (OpenAI, mock, extensible)
- Batch embedding generation
- Caching to avoid regenerating for unchanged content
- Retry logic and error handling
- Configurable embedding dimensions

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/ISSUE_TEMPLATE/phase13-copilot-intelligence-issues.md P13-2
"""

import asyncio
import hashlib
import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class EmbeddingProvider(str, Enum):
    """Supported embedding providers."""
    OPENAI = "openai"
    MOCK = "mock"
    # Future providers:
    # ANTHROPIC = "anthropic"
    # COHERE = "cohere"
    # LOCAL = "local"


@dataclass
class EmbeddingConfig:
    """Configuration for embedding service."""
    provider: EmbeddingProvider = EmbeddingProvider.MOCK
    model: str = "text-embedding-3-small"
    dimension: int = 1536
    api_key: Optional[str] = None
    api_base_url: Optional[str] = None
    batch_size: int = 100
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    cache_enabled: bool = True

    @classmethod
    def from_env(cls) -> "EmbeddingConfig":
        """Load configuration from environment variables."""
        provider_str = os.getenv("EMBEDDING_PROVIDER", "mock").lower()
        try:
            provider = EmbeddingProvider(provider_str)
        except ValueError:
            logger.warning(f"Unknown embedding provider '{provider_str}', using mock")
            provider = EmbeddingProvider.MOCK

        return cls(
            provider=provider,
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
            dimension=int(os.getenv("EMBEDDING_DIMENSION", "1536")),
            api_key=os.getenv("OPENAI_API_KEY") or os.getenv("EMBEDDING_API_KEY"),
            api_base_url=os.getenv("EMBEDDING_API_BASE_URL"),
            batch_size=int(os.getenv("EMBEDDING_BATCH_SIZE", "100")),
            max_retries=int(os.getenv("EMBEDDING_MAX_RETRIES", "3")),
            retry_delay=float(os.getenv("EMBEDDING_RETRY_DELAY", "1.0")),
            timeout=float(os.getenv("EMBEDDING_TIMEOUT", "30.0")),
            cache_enabled=os.getenv("EMBEDDING_CACHE_ENABLED", "true").lower() == "true",
        )


@dataclass
class EmbeddingResult:
    """Result of embedding generation."""
    text: str
    embedding: list[float]
    model: str
    dimension: int
    cached: bool = False
    content_hash: Optional[str] = None


class EmbeddingProviderBase(ABC):
    """Base class for embedding providers."""

    @abstractmethod
    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding for a single text."""
        pass

    @abstractmethod
    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the model name."""
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """Return the embedding dimension."""
        pass


class MockEmbeddingProvider(EmbeddingProviderBase):
    """
    Mock embedding provider for testing.

    Generates deterministic embeddings based on text hash.
    """

    def __init__(self, dimension: int = 1536):
        self._dimension = dimension
        self._model = "mock-embedding-model"

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate a deterministic mock embedding."""
        # Create deterministic embedding from text hash
        text_hash = hashlib.sha256(text.encode()).hexdigest()

        # Use hash to seed pseudo-random values
        embedding = []
        for i in range(self._dimension):
            # Generate value between -1 and 1 based on hash
            chunk = text_hash[(i * 2) % len(text_hash):((i * 2) + 2) % len(text_hash) or None]
            if not chunk:
                chunk = "00"
            value = (int(chunk, 16) / 255.0) * 2 - 1
            embedding.append(value)

        # Normalize to unit vector
        norm = sum(x ** 2 for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        return [await self.generate_embedding(text) for text in texts]


class OpenAIEmbeddingProvider(EmbeddingProviderBase):
    """
    OpenAI embedding provider.

    Uses OpenAI's text-embedding-3-small or text-embedding-3-large models.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        base_url: Optional[str] = None,
        timeout: float = 30.0,
    ):
        if not api_key:
            raise ValueError("OpenAI API key is required")

        self._api_key = api_key
        self._model = model
        self._dimension = dimension
        self._base_url = base_url or "https://api.openai.com/v1"
        self._timeout = timeout
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def model_name(self) -> str:
        return self._model

    @property
    def dimension(self) -> int:
        return self._dimension

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=self._timeout,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def generate_embedding(self, text: str) -> list[float]:
        """Generate embedding using OpenAI API."""
        embeddings = await self.generate_embeddings_batch([text])
        return embeddings[0]

    async def generate_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts using OpenAI API."""
        if not texts:
            return []

        client = await self._get_client()

        request_body: dict[str, Any] = {
            "model": self._model,
            "input": texts,
        }

        # Some models support dimension parameter
        if "3-small" in self._model or "3-large" in self._model:
            request_body["dimensions"] = self._dimension

        response = await client.post(
            f"{self._base_url}/embeddings",
            json=request_body,
        )
        response.raise_for_status()

        data = response.json()

        # Sort by index to maintain order
        embeddings_data = sorted(data["data"], key=lambda x: x["index"])
        return [item["embedding"] for item in embeddings_data]


class EmbeddingService:
    """
    Provider-agnostic embedding service.

    Features:
    - Multiple provider support (OpenAI, mock, extensible)
    - Batch embedding generation for efficiency
    - In-memory caching to avoid regenerating unchanged content
    - Retry logic with exponential backoff
    - Configurable via environment or explicit config
    """

    def __init__(self, config: Optional[EmbeddingConfig] = None):
        """
        Initialize embedding service.

        Args:
            config: Optional configuration (loads from env if not provided)
        """
        self.config = config or EmbeddingConfig.from_env()
        self._provider: Optional[EmbeddingProviderBase] = None
        self._cache: dict[str, list[float]] = {}
        self._cache_hits = 0
        self._cache_misses = 0

    def _get_provider(self) -> EmbeddingProviderBase:
        """Get or create the embedding provider."""
        if self._provider is None:
            if self.config.provider == EmbeddingProvider.OPENAI:
                if not self.config.api_key:
                    raise ValueError("OpenAI API key required for OpenAI provider")
                self._provider = OpenAIEmbeddingProvider(
                    api_key=self.config.api_key,
                    model=self.config.model,
                    dimension=self.config.dimension,
                    base_url=self.config.api_base_url,
                    timeout=self.config.timeout,
                )
            elif self.config.provider == EmbeddingProvider.MOCK:
                self._provider = MockEmbeddingProvider(dimension=self.config.dimension)
            else:
                raise ValueError(f"Unsupported provider: {self.config.provider}")

        return self._provider

    @staticmethod
    def compute_content_hash(text: str) -> str:
        """Compute hash for cache key."""
        return hashlib.sha256(text.encode()).hexdigest()

    def _get_from_cache(self, content_hash: str) -> Optional[list[float]]:
        """Get embedding from cache."""
        if not self.config.cache_enabled:
            return None

        embedding = self._cache.get(content_hash)
        if embedding:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

        return embedding

    def _put_in_cache(self, content_hash: str, embedding: list[float]):
        """Store embedding in cache."""
        if self.config.cache_enabled:
            self._cache[content_hash] = embedding

    async def generate_embedding(
        self,
        text: str,
        use_cache: bool = True,
    ) -> EmbeddingResult:
        """
        Generate embedding for a single text.

        Args:
            text: Text to embed
            use_cache: Whether to use caching

        Returns:
            EmbeddingResult with embedding and metadata
        """
        content_hash = self.compute_content_hash(text)

        # Check cache
        if use_cache:
            cached_embedding = self._get_from_cache(content_hash)
            if cached_embedding:
                return EmbeddingResult(
                    text=text,
                    embedding=cached_embedding,
                    model=self.config.model,
                    dimension=self.config.dimension,
                    cached=True,
                    content_hash=content_hash,
                )

        # Generate with retries
        provider = self._get_provider()
        embedding = await self._with_retry(
            lambda: provider.generate_embedding(text)
        )

        # Cache result
        self._put_in_cache(content_hash, embedding)

        return EmbeddingResult(
            text=text,
            embedding=embedding,
            model=provider.model_name,
            dimension=provider.dimension,
            cached=False,
            content_hash=content_hash,
        )

    async def generate_embeddings_batch(
        self,
        texts: list[str],
        use_cache: bool = True,
    ) -> list[EmbeddingResult]:
        """
        Generate embeddings for multiple texts.

        Uses batching for efficiency and caching where possible.

        Args:
            texts: List of texts to embed
            use_cache: Whether to use caching

        Returns:
            List of EmbeddingResult in same order as input
        """
        if not texts:
            return []

        results: list[Optional[EmbeddingResult]] = [None] * len(texts)
        texts_to_embed: list[tuple[int, str, str]] = []  # (index, text, hash)

        # Check cache for each text
        for i, text in enumerate(texts):
            content_hash = self.compute_content_hash(text)

            if use_cache:
                cached_embedding = self._get_from_cache(content_hash)
                if cached_embedding:
                    results[i] = EmbeddingResult(
                        text=text,
                        embedding=cached_embedding,
                        model=self.config.model,
                        dimension=self.config.dimension,
                        cached=True,
                        content_hash=content_hash,
                    )
                    continue

            texts_to_embed.append((i, text, content_hash))

        # Generate embeddings for non-cached texts in batches
        if texts_to_embed:
            provider = self._get_provider()

            for batch_start in range(0, len(texts_to_embed), self.config.batch_size):
                batch = texts_to_embed[batch_start:batch_start + self.config.batch_size]
                batch_texts = [item[1] for item in batch]

                embeddings = await self._with_retry(
                    lambda bt=batch_texts: provider.generate_embeddings_batch(bt)
                )

                for (idx, text, content_hash), embedding in zip(batch, embeddings):
                    self._put_in_cache(content_hash, embedding)
                    results[idx] = EmbeddingResult(
                        text=text,
                        embedding=embedding,
                        model=provider.model_name,
                        dimension=provider.dimension,
                        cached=False,
                        content_hash=content_hash,
                    )

        return [r for r in results if r is not None]

    async def _with_retry(self, func):
        """Execute function with retry logic."""
        last_error = None

        for attempt in range(self.config.max_retries):
            try:
                return await func()
            except Exception as e:
                last_error = e
                if attempt < self.config.max_retries - 1:
                    delay = self.config.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Embedding generation failed (attempt {attempt + 1}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Embedding generation failed after {self.config.max_retries} attempts: {e}")

        raise last_error

    def clear_cache(self):
        """Clear the embedding cache."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        logger.info("Embedding cache cleared")

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total = self._cache_hits + self._cache_misses
        hit_rate = self._cache_hits / total if total > 0 else 0.0

        return {
            "cache_size": len(self._cache),
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "hit_rate": hit_rate,
        }

    async def close(self):
        """Close any resources."""
        if self._provider and hasattr(self._provider, "close"):
            await self._provider.close()
