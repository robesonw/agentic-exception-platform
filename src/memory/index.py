"""
Memory Index Registry for per-tenant exception storage and retrieval.
Phase 2: Migrated to use VectorStore for persistent storage.
Fallback mode available for local tests.

Provides persistent vector storage with similarity search capabilities.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.memory.rag import DummyEmbeddingProvider, EmbeddingProvider, cosine_similarity
from src.memory.vector_store import InMemoryVectorStore, SearchResult, VectorPoint, VectorStore
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
    
    Phase 2: Uses VectorStore for persistent storage.
    Stores exception records with embeddings for similarity search.
    """

    def __init__(
        self,
        tenant_id: str,
        embedding_provider: EmbeddingProvider,
        vector_store: Optional[VectorStore] = None,
    ):
        """
        Initialize memory index for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            embedding_provider: Embedding provider for generating embeddings
            vector_store: Optional VectorStore (defaults to InMemoryVectorStore for fallback)
        """
        self.tenant_id = tenant_id
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store or InMemoryVectorStore()
        
        # Legacy in-memory storage (for backward compatibility and fallback)
        self._entries: list[ExceptionMemoryEntry] = []
        self._use_vector_store = vector_store is not None

    def add_exception(
        self, exception_record: ExceptionRecord, resolution_summary: str
    ) -> None:
        """
        Add exception to memory index.
        
        Phase 2: Stores in VectorStore if available, otherwise uses in-memory fallback.
        
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
        
        # Store in VectorStore if available
        if self._use_vector_store:
            try:
                # Ensure collection exists
                self.vector_store.ensure_collection(self.tenant_id, len(embedding))
                
                # Create vector point
                point = VectorPoint(
                    id=exception_record.exception_id,
                    vector=embedding,
                    payload={
                        "exception_id": exception_record.exception_id,
                        "tenant_id": self.tenant_id,
                        "exception_type": exception_record.exception_type,
                        "severity": exception_record.severity.value if exception_record.severity else None,
                        "source_system": exception_record.source_system,
                        "resolution_summary": resolution_summary,
                        "timestamp": entry.timestamp.isoformat(),
                        "raw_payload": exception_record.raw_payload,
                    },
                )
                
                self.vector_store.upsert_points(self.tenant_id, [point])
                logger.info(
                    f"Added exception {exception_record.exception_id} to vector store "
                    f"for tenant {self.tenant_id}"
                )
            except Exception as e:
                logger.warning(
                    f"Failed to store in vector store, falling back to in-memory: {e}"
                )
                self._entries.append(entry)
        else:
            # Fallback to in-memory storage
            self._entries.append(entry)
            logger.info(
                f"Added exception {exception_record.exception_id} to memory index "
                f"for tenant {self.tenant_id} (in-memory mode)"
            )

    def search_similar(
        self, exception_record: ExceptionRecord, k: int = 5
    ) -> list[tuple[ExceptionMemoryEntry, float]]:
        """
        Search for similar exceptions in the index.
        
        Phase 2: Uses VectorStore if available, otherwise uses in-memory fallback.
        
        Args:
            exception_record: ExceptionRecord to find similar exceptions for
            k: Number of similar exceptions to return
            
        Returns:
            List of tuples (ExceptionMemoryEntry, similarity_score) sorted by similarity (descending)
        """
        # Generate text representation for query
        query_text = self._generate_text_representation(exception_record, "")
        
        # Generate embedding for query
        query_embedding = self.embedding_provider.embed(query_text)
        
        # Search in VectorStore if available
        if self._use_vector_store:
            try:
                search_results = self.vector_store.search(
                    tenant_id=self.tenant_id,
                    query_vector=query_embedding,
                    limit=k,
                )
                
                # Convert SearchResult to ExceptionMemoryEntry
                results = []
                for result in search_results:
                    # Reconstruct ExceptionMemoryEntry from payload
                    payload = result.payload
                    entry = ExceptionMemoryEntry(
                        exception_id=payload.get("exception_id", result.id),
                        tenant_id=payload.get("tenant_id", self.tenant_id),
                        exception_record=exception_record,  # Simplified - in production would deserialize
                        resolution_summary=payload.get("resolution_summary", ""),
                        embedding=query_embedding,  # Would need to store in payload or retrieve
                        timestamp=datetime.fromisoformat(payload.get("timestamp", datetime.now(timezone.utc).isoformat())),
                    )
                    results.append((entry, result.score))
                
                return results
            except Exception as e:
                logger.warning(
                    f"Vector store search failed, falling back to in-memory: {e}"
                )
                # Fall through to in-memory search
        
        # Fallback to in-memory search
        if not self._entries:
            return []
        
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
        if self._use_vector_store:
            # For VectorStore, we'd need to query count (not implemented in MVP)
            # Return in-memory count as fallback
            return len(self._entries)
        
        return len(self._entries)

    def clear(self) -> None:
        """Clear all entries from the index."""
        if self._use_vector_store:
            # For VectorStore, we'd need to delete all points (not implemented in MVP)
            # Clear in-memory as fallback
            logger.warning("Clear operation on VectorStore not fully implemented, clearing in-memory only")
        
        self._entries.clear()
        logger.info(f"Cleared memory index for tenant {self.tenant_id}")


class MemoryIndexRegistry:
    """
    Registry for managing per-tenant memory indexes.
    
    Phase 2: Supports VectorStore for persistent storage with fallback mode.
    Ensures strict tenant isolation - each tenant has its own isolated index/collection.
    """

    def __init__(
        self,
        embedding_provider: Optional[EmbeddingProvider] = None,
        vector_store: Optional[VectorStore] = None,
        use_vector_store: bool = True,
    ):
        """
        Initialize memory index registry.
        
        Args:
            embedding_provider: Optional embedding provider (defaults to DummyEmbeddingProvider)
            vector_store: Optional VectorStore (defaults to InMemoryVectorStore for fallback)
            use_vector_store: Whether to use VectorStore (default: True, falls back if None)
        """
        if embedding_provider is None:
            embedding_provider = DummyEmbeddingProvider()
        
        self.embedding_provider = embedding_provider
        self.vector_store = vector_store
        self.use_vector_store = use_vector_store and vector_store is not None
        self._indexes: dict[str, MemoryIndex] = {}

    def get_or_create_index(self, tenant_id: str) -> MemoryIndex:
        """
        Get or create memory index for a tenant.
        
        Phase 2: Creates index with VectorStore if available.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            MemoryIndex instance for the tenant
        """
        if tenant_id not in self._indexes:
            vector_store = self.vector_store if self.use_vector_store else None
            self._indexes[tenant_id] = MemoryIndex(
                tenant_id, self.embedding_provider, vector_store=vector_store
            )
            logger.info(
                f"Created memory index for tenant {tenant_id} "
                f"(vector_store={'enabled' if self.use_vector_store else 'disabled'})"
            )
        
        return self._indexes[tenant_id]
    
    def export_collection(self, tenant_id: str) -> dict[str, Any]:
        """
        Export collection data for backup.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with collection data
        """
        if not self.use_vector_store or not self.vector_store:
            logger.warning("Export not available without VectorStore")
            return {}
        
        try:
            return self.vector_store.export_collection(tenant_id)
        except Exception as e:
            logger.error(f"Failed to export collection for tenant {tenant_id}: {e}")
            raise
    
    def restore_collection(self, tenant_id: str, data: dict[str, Any]) -> None:
        """
        Restore collection from backup data.
        
        Args:
            tenant_id: Tenant identifier
            data: Collection data from export
        """
        if not self.use_vector_store or not self.vector_store:
            logger.warning("Restore not available without VectorStore")
            return
        
        try:
            self.vector_store.restore_collection(tenant_id, data)
            logger.info(f"Restored collection for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to restore collection for tenant {tenant_id}: {e}")
            raise

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

