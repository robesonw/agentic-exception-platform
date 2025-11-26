"""
Memory and RAG layer for per-tenant exception knowledge storage and retrieval.
Matches specification from docs/master_project_instruction_full.md
"""

from src.memory.embeddings import (
    CachedEmbeddingProvider,
    EmbeddingCache,
    HuggingFaceEmbeddingProvider,
    OpenAIEmbeddingProvider,
)
from src.memory.index import MemoryIndexRegistry
from src.memory.rag import EmbeddingProvider, DummyEmbeddingProvider
from src.memory.vector_store import (
    InMemoryVectorStore,
    QdrantVectorStore,
    SearchResult,
    VectorPoint,
    VectorStore,
)

__all__ = [
    "MemoryIndexRegistry",
    "EmbeddingProvider",
    "DummyEmbeddingProvider",
    # Phase 2 embedding providers
    "OpenAIEmbeddingProvider",
    "HuggingFaceEmbeddingProvider",
    "CachedEmbeddingProvider",
    "EmbeddingCache",
    # Phase 2 vector store
    "VectorStore",
    "QdrantVectorStore",
    "InMemoryVectorStore",
    "VectorPoint",
    "SearchResult",
]

