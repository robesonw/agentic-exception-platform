"""
Memory Index Registry for per-tenant exception storage and retrieval.
Provides in-memory storage with similarity search capabilities.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.rag import DummyEmbeddingProvider, EmbeddingProvider, cosine_similarity
from src.models.exception_record import ExceptionRecord

logger = logging.getLogger(__name__)


@dataclass
class ExceptionMemoryEntry:
    """Single entry in the memory index."""

    exception_id: str
    tenant_id: str
    exception_record: ExceptionRecord
    resolution_summary: str
    embedding: list[float]
    timestamp: datetime


class MemoryIndex:
    """
    Per-tenant memory index for exception storage and retrieval.
    
    Stores exception records with embeddings for similarity search.
    """

    def __init__(self, tenant_id: str, embedding_provider: EmbeddingProvider):
        """
        Initialize memory index for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            embedding_provider: Embedding provider for generating embeddings
        """
        self.tenant_id = tenant_id
        self.embedding_provider = embedding_provider
        self._entries: list[ExceptionMemoryEntry] = []

    def add_exception(
        self, exception_record: ExceptionRecord, resolution_summary: str
    ) -> None:
        """
        Add exception to memory index.
        
        Args:
            exception_record: ExceptionRecord to store
            resolution_summary: Summary of resolution outcome
        """
        # Generate text representation for embedding
        text = self._generate_text_representation(exception_record, resolution_summary)
        
        # Generate embedding
        embedding = self.embedding_provider.embed(text)
        
        # Create memory entry
        entry = ExceptionMemoryEntry(
            exception_id=exception_record.exception_id,
            tenant_id=self.tenant_id,
            exception_record=exception_record,
            resolution_summary=resolution_summary,
            embedding=embedding,
            timestamp=datetime.now(timezone.utc),
        )
        
        self._entries.append(entry)
        logger.info(f"Added exception {exception_record.exception_id} to memory index for tenant {self.tenant_id}")

    def search_similar(
        self, exception_record: ExceptionRecord, k: int = 5
    ) -> list[tuple[ExceptionMemoryEntry, float]]:
        """
        Search for similar exceptions in the index.
        
        Args:
            exception_record: ExceptionRecord to find similar exceptions for
            k: Number of similar exceptions to return
            
        Returns:
            List of tuples (ExceptionMemoryEntry, similarity_score) sorted by similarity (descending)
        """
        if not self._entries:
            return []
        
        # Generate text representation for query
        query_text = self._generate_text_representation(exception_record, "")
        
        # Generate embedding for query
        query_embedding = self.embedding_provider.embed(query_text)
        
        # Calculate similarities
        similarities = []
        for entry in self._entries:
            similarity = cosine_similarity(query_embedding, entry.embedding)
            similarities.append((entry, similarity))
        
        # Sort by similarity (descending) and return top k
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:k]

    def _generate_text_representation(
        self, exception_record: ExceptionRecord, resolution_summary: str
    ) -> str:
        """
        Generate text representation of exception for embedding.
        
        Args:
            exception_record: ExceptionRecord to represent
            resolution_summary: Optional resolution summary
            
        Returns:
            Text representation string
        """
        parts = []
        
        if exception_record.exception_type:
            parts.append(f"Exception type: {exception_record.exception_type}")
        
        if exception_record.severity:
            parts.append(f"Severity: {exception_record.severity.value}")
        
        if exception_record.source_system:
            parts.append(f"Source system: {exception_record.source_system}")
        
        # Include key fields from raw payload
        if exception_record.raw_payload:
            # Extract common error fields
            error_msg = exception_record.raw_payload.get("error", "")
            error_code = exception_record.raw_payload.get("errorCode", "")
            if error_msg:
                parts.append(f"Error: {error_msg}")
            if error_code:
                parts.append(f"Error code: {error_code}")
        
        if resolution_summary:
            parts.append(f"Resolution: {resolution_summary}")
        
        return " | ".join(parts)

    def get_count(self) -> int:
        """
        Get number of entries in the index.
        
        Returns:
            Number of entries
        """
        return len(self._entries)

    def clear(self) -> None:
        """Clear all entries from the index."""
        self._entries.clear()
        logger.info(f"Cleared memory index for tenant {self.tenant_id}")


class MemoryIndexRegistry:
    """
    Registry for managing per-tenant memory indexes.
    
    Ensures strict tenant isolation - each tenant has its own isolated index.
    """

    def __init__(self, embedding_provider: Optional[EmbeddingProvider] = None):
        """
        Initialize memory index registry.
        
        Args:
            embedding_provider: Optional embedding provider (defaults to DummyEmbeddingProvider)
        """
        if embedding_provider is None:
            embedding_provider = DummyEmbeddingProvider()
        
        self.embedding_provider = embedding_provider
        self._indexes: dict[str, MemoryIndex] = {}

    def get_or_create_index(self, tenant_id: str) -> MemoryIndex:
        """
        Get or create memory index for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            MemoryIndex instance for the tenant
        """
        if tenant_id not in self._indexes:
            self._indexes[tenant_id] = MemoryIndex(tenant_id, self.embedding_provider)
            logger.info(f"Created memory index for tenant {tenant_id}")
        
        return self._indexes[tenant_id]

    def add_exception(
        self, tenant_id: str, exception_record: ExceptionRecord, resolution_summary: str
    ) -> None:
        """
        Add exception to tenant's memory index.
        
        Args:
            tenant_id: Tenant identifier
            exception_record: ExceptionRecord to store
            resolution_summary: Summary of resolution outcome
        """
        index = self.get_or_create_index(tenant_id)
        index.add_exception(exception_record, resolution_summary)

    def search_similar(
        self, tenant_id: str, exception_record: ExceptionRecord, k: int = 5
    ) -> list[tuple[ExceptionMemoryEntry, float]]:
        """
        Search for similar exceptions in tenant's memory index.
        
        Args:
            tenant_id: Tenant identifier
            exception_record: ExceptionRecord to find similar exceptions for
            k: Number of similar exceptions to return
            
        Returns:
            List of tuples (ExceptionMemoryEntry, similarity_score) sorted by similarity (descending)
            Returns empty list if index doesn't exist or is empty
        """
        if tenant_id not in self._indexes:
            logger.debug(f"No memory index found for tenant {tenant_id}, returning empty results")
            return []
        
        index = self._indexes[tenant_id]
        return index.search_similar(exception_record, k)

    def get_index(self, tenant_id: str) -> Optional[MemoryIndex]:
        """
        Get memory index for tenant (returns None if doesn't exist).
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            MemoryIndex instance or None
        """
        return self._indexes.get(tenant_id)

    def has_index(self, tenant_id: str) -> bool:
        """
        Check if memory index exists for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if index exists, False otherwise
        """
        return tenant_id in self._indexes

    def clear_index(self, tenant_id: str) -> None:
        """
        Clear memory index for tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._indexes:
            self._indexes[tenant_id].clear()

    def remove_index(self, tenant_id: str) -> None:
        """
        Remove memory index for tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._indexes:
            del self._indexes[tenant_id]
            logger.info(f"Removed memory index for tenant {tenant_id}")

