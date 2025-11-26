"""
RAG (Retrieval-Augmented Generation) components for exception similarity search.
Provides embedding provider interface and implementations.

Phase 2: Advanced semantic search with hybrid search (vector + keyword).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Optional

import numpy as np

from src.models.exception_record import ExceptionRecord, Severity


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


@dataclass
class HybridSearchFilters:
    """Filters for hybrid search."""

    exception_type: Optional[str] = None
    severity: Optional[Severity] = None
    domain_name: Optional[str] = None
    source_system: Optional[str] = None


@dataclass
class HybridSearchResult:
    """Result from hybrid search with explanation."""

    exception_id: str
    tenant_id: str
    vector_score: float
    keyword_score: float
    combined_score: float
    explanation: str
    metadata: dict[str, Any]


def hybrid_search(
    exception_record: ExceptionRecord,
    memory_index_registry: Any,  # MemoryIndexRegistry
    embedding_provider: Any,  # EmbeddingProvider
    k: int = 5,
    filters: Optional[HybridSearchFilters] = None,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
) -> list[HybridSearchResult]:
    """
    Perform hybrid search combining vector similarity and keyword matching.
    
    Phase 2: Advanced semantic search with:
    - Vector search via VectorStore
    - Keyword match against stored metadata
    - Merge and rerank results
    - Filtering by exceptionType, severity, domainName
    - Relevance scores + explanation
    
    Args:
        exception_record: ExceptionRecord to search for
        memory_index_registry: MemoryIndexRegistry instance
        embedding_provider: EmbeddingProvider for generating query embedding
        k: Number of results to return
        filters: Optional filters for exceptionType, severity, domainName
        vector_weight: Weight for vector similarity score (default: 0.7)
        keyword_weight: Weight for keyword match score (default: 0.3)
        
    Returns:
        List of HybridSearchResult sorted by combined score (descending)
    """
    if not memory_index_registry:
        return []
    
    tenant_id = exception_record.tenant_id
    
    # Step 1: Vector search via VectorStore
    vector_results = _vector_search(
        exception_record, memory_index_registry, embedding_provider, tenant_id, k * 2
    )  # Get more candidates for reranking
    
    # Step 2: Keyword matching against metadata
    keyword_results = _keyword_search(
        exception_record, memory_index_registry, tenant_id, k * 2, filters
    )
    
    # Step 3: Merge and deduplicate results
    merged_results = _merge_results(vector_results, keyword_results, exception_record)
    
    # Step 4: Apply filters
    if filters:
        merged_results = _apply_filters(merged_results, filters)
    
    # Step 5: Calculate combined scores and explanations
    scored_results = []
    for result in merged_results:
        combined_score = (
            result["vector_score"] * vector_weight + result["keyword_score"] * keyword_weight
        )
        explanation = _generate_explanation(result, vector_weight, keyword_weight)
        
        scored_results.append(
            HybridSearchResult(
                exception_id=result["exception_id"],
                tenant_id=result["tenant_id"],
                vector_score=result["vector_score"],
                keyword_score=result["keyword_score"],
                combined_score=combined_score,
                explanation=explanation,
                metadata=result.get("metadata", {}),
            )
        )
    
    # Step 6: Rerank by combined score and return top k
    scored_results.sort(key=lambda x: x.combined_score, reverse=True)
    return scored_results[:k]


def _vector_search(
    exception_record: ExceptionRecord,
    memory_index_registry: Any,
    embedding_provider: Any,
    tenant_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    """
    Perform vector similarity search.
    
    Args:
        exception_record: ExceptionRecord to search for
        memory_index_registry: MemoryIndexRegistry instance
        embedding_provider: EmbeddingProvider
        tenant_id: Tenant identifier
        limit: Maximum number of results
        
    Returns:
        List of result dictionaries with vector scores
    """
    try:
        # Get memory index for tenant
        memory_index = memory_index_registry.get_or_create_index(tenant_id)
        
        # Generate query embedding
        query_text = memory_index._generate_text_representation(exception_record, "")
        query_embedding = embedding_provider.embed(query_text)
        
        # Search using VectorStore if available
        if hasattr(memory_index, "vector_store") and memory_index.vector_store:
            search_results = memory_index.vector_store.search(
                tenant_id=tenant_id,
                query_vector=query_embedding,
                limit=limit,
            )
            
            vector_results = []
            for result in search_results:
                vector_results.append({
                    "exception_id": result.id,
                    "tenant_id": result.payload.get("tenant_id", tenant_id),
                    "vector_score": result.score,
                    "keyword_score": 0.0,  # Will be calculated in merge
                    "metadata": result.payload,
                })
            
            return vector_results
        else:
            # Fallback to in-memory search
            similar_exceptions = memory_index.search_similar(exception_record, k=limit)
            vector_results = []
            for entry, score in similar_exceptions:
                vector_results.append({
                    "exception_id": entry.exception_id,
                    "tenant_id": entry.tenant_id,
                    "vector_score": score,
                    "keyword_score": 0.0,
                    "metadata": {
                        "exception_type": entry.exception_record.exception_type,
                        "severity": entry.exception_record.severity.value if entry.exception_record.severity else None,
                        "source_system": entry.exception_record.source_system,
                        "resolution_summary": entry.resolution_summary,
                    },
                })
            
            return vector_results
    except Exception as e:
        # Gracefully handle search failures
        return []


def _keyword_search(
    exception_record: ExceptionRecord,
    memory_index_registry: Any,
    tenant_id: str,
    limit: int,
    filters: Optional[HybridSearchFilters],
) -> list[dict[str, Any]]:
    """
    Perform keyword matching against stored metadata.
    
    Args:
        exception_record: ExceptionRecord to search for
        memory_index_registry: MemoryIndexRegistry instance
        tenant_id: Tenant identifier
        limit: Maximum number of results
        filters: Optional filters
        
    Returns:
        List of result dictionaries with keyword scores
    """
    try:
        memory_index = memory_index_registry.get_or_create_index(tenant_id)
        
        # Extract keywords from exception record
        keywords = []
        if exception_record.exception_type:
            keywords.append(exception_record.exception_type.lower())
        if exception_record.source_system:
            keywords.append(exception_record.source_system.lower())
        if exception_record.raw_payload:
            error_msg = str(exception_record.raw_payload.get("error", "")).lower()
            error_code = str(exception_record.raw_payload.get("errorCode", "")).lower()
            if error_msg:
                keywords.extend(error_msg.split())
            if error_code:
                keywords.append(error_code)
        
        # Get all entries from memory index (for keyword matching)
        # In production, this would use a proper keyword index
        keyword_results = []
        
        # For MVP, we'll search through in-memory entries
        if hasattr(memory_index, "_entries"):
            for entry in memory_index._entries:
                # Calculate keyword match score
                score = _calculate_keyword_score(keywords, entry, exception_record)
                
                if score > 0:
                    keyword_results.append({
                        "exception_id": entry.exception_id,
                        "tenant_id": entry.tenant_id,
                        "vector_score": 0.0,  # Will be calculated in merge
                        "keyword_score": score,
                        "metadata": {
                            "exception_type": entry.exception_record.exception_type,
                            "severity": entry.exception_record.severity.value if entry.exception_record.severity else None,
                            "source_system": entry.exception_record.source_system,
                            "resolution_summary": entry.resolution_summary,
                        },
                    })
        
        # Sort by keyword score and return top results
        keyword_results.sort(key=lambda x: x["keyword_score"], reverse=True)
        return keyword_results[:limit]
    except Exception as e:
        return []


def _calculate_keyword_score(
    keywords: list[str], entry: Any, query_exception: ExceptionRecord
) -> float:
    """
    Calculate keyword match score.
    
    Args:
        keywords: List of keywords from query
        entry: ExceptionMemoryEntry to score
        query_exception: Query ExceptionRecord
        
    Returns:
        Keyword match score (0.0 to 1.0)
    """
    if not keywords:
        return 0.0
    
    score = 0.0
    matches = 0
    
    # Match against exception type
    if query_exception.exception_type and entry.exception_record.exception_type:
        if query_exception.exception_type.lower() == entry.exception_record.exception_type.lower():
            score += 0.4
            matches += 1
    
    # Match against source system
    if query_exception.source_system and entry.exception_record.source_system:
        if query_exception.source_system.lower() == entry.exception_record.source_system.lower():
            score += 0.3
            matches += 1
    
    # Match against error message/code in raw payload
    query_error = str(query_exception.raw_payload.get("error", "")).lower()
    entry_error = str(entry.exception_record.raw_payload.get("error", "")).lower()
    if query_error and entry_error:
        # Simple word overlap
        query_words = set(query_error.split())
        entry_words = set(entry_error.split())
        overlap = len(query_words & entry_words)
        if overlap > 0:
            score += min(0.3, overlap * 0.1)
            matches += 1
    
    # Normalize score
    if matches > 0:
        return min(1.0, score)
    
    return 0.0


def _merge_results(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    query_exception: ExceptionRecord,
) -> list[dict[str, Any]]:
    """
    Merge vector and keyword results, deduplicating by exception_id.
    
    Args:
        vector_results: Results from vector search
        keyword_results: Results from keyword search
        query_exception: Query ExceptionRecord
        
    Returns:
        Merged and deduplicated results
    """
    merged = {}
    
    # Add vector results
    for result in vector_results:
        exc_id = result["exception_id"]
        if exc_id not in merged:
            merged[exc_id] = result.copy()
        else:
            # Update vector score if higher
            if result["vector_score"] > merged[exc_id]["vector_score"]:
                merged[exc_id]["vector_score"] = result["vector_score"]
            # Merge metadata
            merged[exc_id]["metadata"].update(result.get("metadata", {}))
    
    # Add keyword results
    for result in keyword_results:
        exc_id = result["exception_id"]
        if exc_id not in merged:
            merged[exc_id] = result.copy()
        else:
            # Update keyword score if higher
            if result["keyword_score"] > merged[exc_id]["keyword_score"]:
                merged[exc_id]["keyword_score"] = result["keyword_score"]
            # Merge metadata
            merged[exc_id]["metadata"].update(result.get("metadata", {}))
    
    return list(merged.values())


def _apply_filters(
    results: list[dict[str, Any]], filters: HybridSearchFilters
) -> list[dict[str, Any]]:
    """
    Apply filters to search results.
    
    Args:
        results: Search results
        filters: Filters to apply
        
    Returns:
        Filtered results
    """
    filtered = []
    
    for result in results:
        metadata = result.get("metadata", {})
        
        # Filter by exception type
        if filters.exception_type:
            if metadata.get("exception_type") != filters.exception_type:
                continue
        
        # Filter by severity
        if filters.severity:
            result_severity = metadata.get("severity")
            if result_severity != filters.severity.value:
                continue
        
        # Filter by source system
        if filters.source_system:
            if metadata.get("source_system") != filters.source_system:
                continue
        
        # Filter by domain name (if available in metadata)
        if filters.domain_name:
            if metadata.get("domain_name") != filters.domain_name:
                continue
        
        filtered.append(result)
    
    return filtered


def _generate_explanation(
    result: dict[str, Any], vector_weight: float, keyword_weight: float
) -> str:
    """
    Generate explanation for search result.
    
    Args:
        result: Search result dictionary
        vector_weight: Weight for vector similarity
        keyword_weight: Weight for keyword matching
        
    Returns:
        Explanation string
    """
    parts = []
    
    vector_score = result.get("vector_score", 0.0)
    keyword_score = result.get("keyword_score", 0.0)
    
    if vector_score > 0:
        parts.append(f"Vector similarity: {vector_score:.2f} (weight: {vector_weight:.1f})")
    
    if keyword_score > 0:
        parts.append(f"Keyword match: {keyword_score:.2f} (weight: {keyword_weight:.1f})")
    
    metadata = result.get("metadata", {})
    if metadata.get("exception_type"):
        parts.append(f"Type: {metadata['exception_type']}")
    
    if metadata.get("severity"):
        parts.append(f"Severity: {metadata['severity']}")
    
    if not parts:
        return "No match details available"
    
    return " | ".join(parts)

