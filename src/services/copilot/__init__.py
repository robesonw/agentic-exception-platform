"""
Phase 13 Copilot Intelligence Services.

Provides:
- EmbeddingService: Provider-agnostic embedding generation
- DocumentChunkingService: Semantic document chunking
- IndexingFoundation: Base classes and utilities for document indexing
"""

from src.services.copilot.embedding_service import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
)
from src.services.copilot.chunking_service import (
    ChunkingConfig,
    ChunkingStrategy,
    DocumentChunk,
    DocumentChunkingService,
)
from src.services.copilot.indexing import (
    BaseIndexer,
    IndexingError,
    TenantIsolationError,
    IndexingResult,
    IndexJobStatus,
    PolicyDocsIndexer,
    PolicyDoc,
    stable_chunk_key,
    content_hash,
    document_fingerprint,
)

__all__ = [
    # Embedding
    "EmbeddingConfig",
    "EmbeddingProvider",
    "EmbeddingResult",
    "EmbeddingService",
    # Chunking
    "ChunkingConfig",
    "ChunkingStrategy",
    "DocumentChunk",
    "DocumentChunkingService",
]
