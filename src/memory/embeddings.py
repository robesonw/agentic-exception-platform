"""
Embedding Provider Integration for Phase 2.

Provides:
- EmbeddingProvider interface
- OpenAIEmbeddingProvider (config driven)
- HuggingFaceEmbeddingProvider stub
- EmbeddingCache (LRU + disk optional)
- Quality metrics (latency, cache hit rate)

Matches specification from phase2-mvp-issues.md Issue 29.
"""

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    """
    Abstract interface for text embedding providers.
    
    Implementations can use various embedding models (OpenAI, HuggingFace, etc.)
    """

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """
        Generate embedding vector for text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        pass

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def dimension(self) -> int:
        """
        Get the dimension of embedding vectors.
        
        Returns:
            Dimension of embedding vectors
        """
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """
        Get the name of the embedding provider.
        
        Returns:
            Provider name (e.g., "openai", "huggingface")
        """
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """
        Get the name of the embedding model.
        
        Returns:
            Model name (e.g., "text-embedding-ada-002", "sentence-transformers/all-MiniLM-L6-v2")
        """
        pass


class EmbeddingCache:
    """
    LRU cache for embeddings with optional disk persistence.
    
    Reduces API costs by caching embeddings based on text content.
    """

    def __init__(self, max_size: int = 1000, disk_cache_path: Optional[Path] = None):
        """
        Initialize embedding cache.
        
        Args:
            max_size: Maximum number of embeddings to cache in memory (LRU)
            disk_cache_path: Optional path to disk cache directory
        """
        self.max_size = max_size
        self.disk_cache_path = disk_cache_path
        self._cache: OrderedDict[str, list[float]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        
        # Create disk cache directory if specified
        if self.disk_cache_path:
            self.disk_cache_path.mkdir(parents=True, exist_ok=True)
            self._load_disk_cache()

    def _get_cache_key(self, text: str) -> str:
        """
        Generate cache key from text.
        
        Args:
            text: Text to generate key for
            
        Returns:
            Cache key (hash of text)
        """
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, text: str) -> Optional[list[float]]:
        """
        Get embedding from cache.
        
        Args:
            text: Text to look up
            
        Returns:
            Cached embedding or None if not found
        """
        cache_key = self._get_cache_key(text)
        
        # Check memory cache
        if cache_key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
            self._hits += 1
            return self._cache[cache_key]
        
        # Check disk cache if available
        if self.disk_cache_path:
            embedding = self._load_from_disk(cache_key)
            if embedding:
                # Add to memory cache
                self._add_to_memory(cache_key, embedding)
                self._hits += 1
                return embedding
        
        self._misses += 1
        return None

    def put(self, text: str, embedding: list[float]) -> None:
        """
        Store embedding in cache.
        
        Args:
            text: Text that was embedded
            embedding: Embedding vector
        """
        cache_key = self._get_cache_key(text)
        
        # Add to memory cache
        self._add_to_memory(cache_key, embedding)
        
        # Save to disk cache if available
        if self.disk_cache_path:
            self._save_to_disk(cache_key, embedding)

    def _add_to_memory(self, cache_key: str, embedding: list[float]) -> None:
        """Add embedding to memory cache (LRU eviction)."""
        if cache_key in self._cache:
            # Move to end (most recently used)
            self._cache.move_to_end(cache_key)
        else:
            # Add new entry
            self._cache[cache_key] = embedding
            
            # Evict oldest if cache is full
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)  # Remove oldest (first item)

    def _save_to_disk(self, cache_key: str, embedding: list[float]) -> None:
        """Save embedding to disk cache."""
        try:
            cache_file = self.disk_cache_path / f"{cache_key}.npy"
            np.save(cache_file, np.array(embedding))
        except Exception as e:
            logger.warning(f"Failed to save embedding to disk cache: {e}")

    def _load_from_disk(self, cache_key: str) -> Optional[list[float]]:
        """Load embedding from disk cache."""
        try:
            cache_file = self.disk_cache_path / f"{cache_key}.npy"
            if cache_file.exists():
                embedding = np.load(cache_file).tolist()
                return embedding
        except Exception as e:
            logger.warning(f"Failed to load embedding from disk cache: {e}")
        
        return None

    def _load_disk_cache(self) -> None:
        """Load disk cache metadata (for stats, not full embeddings)."""
        # For MVP, we just ensure the directory exists
        # Full loading would be expensive, so we load on-demand
        pass

    def get_cache_stats(self) -> dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dictionary with cache statistics
        """
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
        
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "size": len(self._cache),
            "max_size": self.max_size,
        }

    def clear(self) -> None:
        """Clear all caches."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        
        # Clear disk cache if available
        if self.disk_cache_path:
            try:
                for cache_file in self.disk_cache_path.glob("*.npy"):
                    cache_file.unlink()
            except Exception as e:
                logger.warning(f"Failed to clear disk cache: {e}")


class OpenAIEmbeddingProvider(EmbeddingProvider):
    """
    OpenAI embedding provider.
    
    Uses OpenAI's embedding API (e.g., text-embedding-ada-002, text-embedding-3-small).
    """

    def __init__(
        self,
        api_key: str,
        model: str = "text-embedding-ada-002",
        dimension: Optional[int] = None,
        timeout: float = 30.0,
    ):
        """
        Initialize OpenAI embedding provider.
        
        Args:
            api_key: OpenAI API key
            model: Model name (default: "text-embedding-ada-002")
            dimension: Optional dimension override (for text-embedding-3 models)
            timeout: Request timeout in seconds
        """
        try:
            import openai
        except ImportError:
            raise ImportError(
                "openai package is required for OpenAIEmbeddingProvider. "
                "Install it with: pip install openai"
            )
        
        self._client = openai.OpenAI(api_key=api_key, timeout=timeout)
        self._model = model
        self._dimension = dimension
        self._timeout = timeout
        
        # Cache for dimension (avoid API call on first embed)
        self._cached_dimension: Optional[int] = None

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding using OpenAI API.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=text,
                dimensions=self._dimension,
            )
            
            # Cache dimension from first response
            if self._cached_dimension is None:
                self._cached_dimension = len(response.data[0].embedding)
            
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"OpenAI embedding generation failed: {e}")
            raise

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        try:
            response = self._client.embeddings.create(
                model=self._model,
                input=texts,
                dimensions=self._dimension,
            )
            
            # Cache dimension from first response
            if self._cached_dimension is None and response.data:
                self._cached_dimension = len(response.data[0].embedding)
            
            return [item.embedding for item in response.data]
        except Exception as e:
            logger.error(f"OpenAI batch embedding generation failed: {e}")
            raise

    @property
    def dimension(self) -> int:
        """Get the dimension of embedding vectors."""
        if self._cached_dimension is not None:
            return self._cached_dimension
        
        # Default dimensions for common models
        if "ada-002" in self._model:
            return 1536
        elif "3-small" in self._model:
            return 1536
        elif "3-large" in self._model:
            return 3072
        
        # Fallback: try to get from API
        if self._dimension:
            return self._dimension
        
        # Default fallback
        return 1536

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "openai"

    @property
    def model_name(self) -> str:
        """Get model name."""
        return self._model


class HuggingFaceEmbeddingProvider(EmbeddingProvider):
    """
    HuggingFace embedding provider stub.
    
    For MVP, this is a stub that can be extended later.
    Uses sentence-transformers library.
    """

    def __init__(
        self,
        model: str = "sentence-transformers/all-MiniLM-L6-v2",
        device: str = "cpu",
    ):
        """
        Initialize HuggingFace embedding provider.
        
        Args:
            model: Model name from HuggingFace (default: "sentence-transformers/all-MiniLM-L6-v2")
            device: Device to run on ("cpu" or "cuda")
        """
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers package is required for HuggingFaceEmbeddingProvider. "
                "Install it with: pip install sentence-transformers"
            )
        
        self._model_name = model
        self._device = device
        self._model: Optional[SentenceTransformer] = None
        self._dimension: Optional[int] = None

    def _load_model(self) -> None:
        """Lazy load the model."""
        if self._model is None:
            from sentence_transformers import SentenceTransformer
            
            self._model = SentenceTransformer(self._model_name, device=self._device)
            # Get dimension from model
            self._dimension = self._model.get_sentence_embedding_dimension()

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding using HuggingFace model.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        self._load_model()
        
        if self._model is None:
            raise RuntimeError("Model not loaded")
        
        embedding = self._model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        self._load_model()
        
        if self._model is None:
            raise RuntimeError("Model not loaded")
        
        embeddings = self._model.encode(texts, normalize_embeddings=True)
        return embeddings.tolist()

    @property
    def dimension(self) -> int:
        """Get the dimension of embedding vectors."""
        self._load_model()
        
        if self._dimension is None:
            raise RuntimeError("Model dimension not available")
        
        return self._dimension

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return "huggingface"

    @property
    def model_name(self) -> str:
        """Get model name."""
        return self._model_name


class CachedEmbeddingProvider(EmbeddingProvider):
    """
    Wrapper around an EmbeddingProvider that adds caching and metrics.
    
    Tracks latency and cache hit rate for quality metrics.
    """

    def __init__(
        self,
        provider: EmbeddingProvider,
        cache: Optional[EmbeddingCache] = None,
    ):
        """
        Initialize cached embedding provider.
        
        Args:
            provider: Underlying embedding provider
            cache: Optional embedding cache (creates default if None)
        """
        self._provider = provider
        self._cache = cache or EmbeddingCache()
        self._total_latency = 0.0
        self._total_requests = 0

    def embed(self, text: str) -> list[float]:
        """
        Generate embedding with caching and latency tracking.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        start_time = time.time()
        
        # Check cache first
        cached_embedding = self._cache.get(text)
        if cached_embedding is not None:
            latency = time.time() - start_time
            self._total_latency += latency
            self._total_requests += 1
            logger.debug(f"Embedding cache hit for text (length: {len(text)})")
            return cached_embedding
        
        # Generate embedding
        embedding = self._provider.embed(text)
        
        # Cache result
        self._cache.put(text, embedding)
        
        # Track latency
        latency = time.time() - start_time
        self._total_latency += latency
        self._total_requests += 1
        
        logger.debug(f"Embedding generated in {latency:.3f}s (cache miss)")
        
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts with caching.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        start_time = time.time()
        
        # Check cache for each text
        embeddings = []
        texts_to_embed = []
        text_indices = []
        
        for idx, text in enumerate(texts):
            cached_embedding = self._cache.get(text)
            if cached_embedding is not None:
                embeddings.append((idx, cached_embedding))
            else:
                texts_to_embed.append(text)
                text_indices.append(idx)
        
        # Generate embeddings for cache misses
        if texts_to_embed:
            new_embeddings = self._provider.embed_batch(texts_to_embed)
            
            # Cache new embeddings
            for text, embedding in zip(texts_to_embed, new_embeddings):
                self._cache.put(text, embedding)
            
            # Add to results
            for idx, embedding in zip(text_indices, new_embeddings):
                embeddings.append((idx, embedding))
        
        # Sort by original index and extract embeddings
        embeddings.sort(key=lambda x: x[0])
        result = [emb for _, emb in embeddings]
        
        # Track latency
        latency = time.time() - start_time
        self._total_latency += latency
        self._total_requests += 1
        
        logger.debug(f"Batch embedding generated in {latency:.3f}s ({len(texts_to_embed)} cache misses)")
        
        return result

    @property
    def dimension(self) -> int:
        """Get the dimension of embedding vectors."""
        return self._provider.dimension

    @property
    def provider_name(self) -> str:
        """Get provider name."""
        return self._provider.provider_name

    @property
    def model_name(self) -> str:
        """Get model name."""
        return self._provider.model_name

    def get_metrics(self) -> dict[str, Any]:
        """
        Get quality metrics for embedding generation.
        
        Returns:
            Dictionary with metrics (latency, cache hit rate, etc.)
        """
        avg_latency = (
            self._total_latency / self._total_requests if self._total_requests > 0 else 0.0
        )
        cache_stats = self._cache.get_cache_stats()
        
        return {
            "total_requests": self._total_requests,
            "average_latency_seconds": avg_latency,
            "total_latency_seconds": self._total_latency,
            "cache_hit_rate": cache_stats["hit_rate"],
            "cache_hits": cache_stats["hits"],
            "cache_misses": cache_stats["misses"],
            "cache_size": cache_stats["size"],
        }

