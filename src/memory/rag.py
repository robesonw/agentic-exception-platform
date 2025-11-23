"""
RAG (Retrieval-Augmented Generation) components for exception similarity search.
Provides embedding provider interface and implementations.
"""

from abc import ABC, abstractmethod
from typing import Any

import numpy as np


class EmbeddingProvider(ABC):
    """
    Abstract interface for text embedding providers.
    
    Implementations can use various embedding models (OpenAI, sentence-transformers, etc.)
    For MVP, we provide a dummy implementation.
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


class DummyEmbeddingProvider(EmbeddingProvider):
    """
    Dummy embedding provider for MVP.
    
    Uses simple hash-based embeddings for demonstration.
    In production, this would be replaced with a real embedding model.
    """

    def __init__(self, dimension: int = 128):
        """
        Initialize dummy embedding provider.
        
        Args:
            dimension: Dimension of embedding vectors (default: 128)
        """
        self._dimension = dimension

    def embed(self, text: str) -> list[float]:
        """
        Generate dummy embedding using hash-based approach.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        # Simple hash-based embedding for MVP
        # In production, use actual embedding model
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.normal(0, 1, self._dimension).tolist()
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        return embedding

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embedding vectors
        """
        return [self.embed(text) for text in texts]

    @property
    def dimension(self) -> int:
        """
        Get the dimension of embedding vectors.
        
        Returns:
            Dimension of embedding vectors
        """
        return self._dimension


def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate cosine similarity between two vectors.
    
    Args:
        vec1: First vector
        vec2: Second vector
        
    Returns:
        Cosine similarity score between -1 and 1
    """
    vec1_array = np.array(vec1)
    vec2_array = np.array(vec2)
    
    dot_product = np.dot(vec1_array, vec2_array)
    norm1 = np.linalg.norm(vec1_array)
    norm2 = np.linalg.norm(vec2_array)
    
    if norm1 == 0 or norm2 == 0:
        return 0.0
    
    return float(dot_product / (norm1 * norm2))

