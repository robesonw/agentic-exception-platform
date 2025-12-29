"""
RetrievalService for Phase 13 Copilot Intelligence.

Provides structured evidence retrieval with tenant isolation and similarity search.
"""

from dataclasses import dataclass
from typing import List, Optional


from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.services.copilot.embedding_service import EmbeddingService


@dataclass
class EvidenceItem:
    """Structured evidence item for Copilot responses with citations."""
    
    source_type: str  # 'PolicyDoc', 'ResolvedException', 'AuditEvent', 'ToolRegistry'
    source_id: str    # UUID or identifier of the source document
    source_version: Optional[str]  # Version/hash for cacheability
    title: str        # Human-readable title
    snippet: str      # Relevant excerpt (200-400 chars)
    url: Optional[str]  # Deep link if available
    similarity_score: float  # Cosine similarity score (0-1)
    chunk_text: str   # Full chunk text for context


class RetrievalService:
    """
    Tenant-isolated evidence retrieval service for Copilot Intelligence.
    
    Bridges EmbeddingService and CopilotDocumentRepository to provide 
    structured evidence retrieval with proper tenant isolation.
    """
    
    def __init__(
        self,
        embedding_service: EmbeddingService,
        document_repository: CopilotDocumentRepository
    ):
        self.embedding_service = embedding_service
        self.document_repository = document_repository
    
    async def retrieve_evidence(
        self,
        tenant_id: str,
        query_text: str,
        domain: Optional[str] = None,
        source_types: Optional[List[str]] = None,
        top_k: int = 5
    ) -> List[EvidenceItem]:
        """
        Retrieve relevant evidence for a query with tenant isolation.
        
        Args:
            tenant_id: UUID of the tenant (enforces isolation)
            query_text: User's natural language query
            domain: Optional domain filter (e.g., 'finance', 'healthcare')
            source_types: Optional list of source types to filter by
            top_k: Maximum number of results to return (default: 5)
            
        Returns:
            List of EvidenceItem objects with similarity scores and citations
            
        Raises:
            ValueError: If query_text is empty or tenant_id is invalid
        """
        if not query_text or not query_text.strip():
            raise ValueError("query_text cannot be empty")
        
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Generate embedding for the query
        embedding_result = await self.embedding_service.generate_embedding(query_text)
        query_embedding = embedding_result.embedding
        
        # Collect evidence from all requested source types
        all_evidence_items = []
        
        # If source_types not specified, search all available types
        search_source_types = source_types or [
            "PolicyDoc", "ResolvedException", "AuditEvent", "ToolRegistry", "playbook"
        ]
        
        for source_type in search_source_types:
            try:
                # Search documents of this type
                similar_docs = await self.document_repository.similarity_search(
                    tenant_id=tenant_id,
                    query_embedding=query_embedding,
                    limit=top_k,
                    source_type=source_type,
                    domain=domain,
                    threshold=0.1  # Minimum similarity threshold
                )
                
                # Convert SimilarDocument objects to EvidenceItem objects
                for doc in similar_docs:
                    # Extract metadata from document
                    metadata = doc.document.metadata_json or {}
                    title = metadata.get('title') or f"{doc.document.source_type} Document"
                    url = metadata.get('url')
                    
                    evidence_item = EvidenceItem(
                        source_type=doc.document.source_type,
                        source_id=str(doc.document.source_id),
                        source_version=doc.document.version,
                        title=title,
                        snippet=self._extract_snippet(doc.document.content, query_text),
                        url=url,
                        similarity_score=doc.similarity_score,
                        chunk_text=doc.document.content
                    )
                    all_evidence_items.append(evidence_item)
                    
            except Exception as e:
                # Log error but continue with other source types
                # In production, use proper logging
                continue
        
        # Sort by similarity score (highest first) and return top_k
        all_evidence_items.sort(key=lambda x: x.similarity_score, reverse=True)
        return all_evidence_items[:top_k]
    
    def _extract_snippet(self, full_text: str, query_text: str, max_length: int = 300) -> str:
        """
        Extract a relevant snippet from the full text based on the query.
        
        Args:
            full_text: Complete text content
            query_text: Original query for context
            max_length: Maximum snippet length (default: 300)
            
        Returns:
            Relevant text snippet with query context
        """
        if not full_text:
            return ""
        
        # Simple extraction - in production, use more sophisticated NLP
        if len(full_text) <= max_length:
            return full_text
        
        # Try to find query terms in the text
        query_words = [word.lower().strip() for word in query_text.split() if word.strip()]
        full_text_lower = full_text.lower()
        
        # Find best position to extract snippet by looking for query term positions
        best_pos = 0
        max_score = 0
        
        # Look for the best position containing the most query words
        for i in range(0, len(full_text) - max_length + 1, max(1, len(full_text) // 20)):
            snippet_text = full_text_lower[i:i + max_length]
            
            # Score based on query word matches and their positions
            score = 0
            for word in query_words:
                if word in snippet_text:
                    # Find position of word in snippet - earlier is better
                    word_pos = snippet_text.find(word)
                    if word_pos >= 0:
                        # Higher score for words found earlier in snippet
                        score += 10 - (word_pos / max_length) * 5
            
            if score > max_score:
                max_score = score
                best_pos = i
        
        # If no query words found, try to find an interesting part
        if max_score == 0:
            # Look for sentences with periods, or use beginning
            sentences = full_text.split('. ')
            if len(sentences) > 1:
                # Take first complete sentence(s) that fit
                snippet = ""
                for sentence in sentences:
                    if len(snippet + sentence + ". ") <= max_length:
                        snippet += sentence + ". "
                    else:
                        break
                if snippet:
                    return snippet.strip()
            
            # Fallback to beginning
            best_pos = 0
        
        # Extract snippet and clean up
        snippet = full_text[best_pos:best_pos + max_length]
        
        # Try to break at word boundaries
        if best_pos > 0 and not snippet.startswith(' '):
            space_pos = snippet.find(' ')
            if space_pos > 0 and space_pos < 50:  # Don't skip too much
                snippet = snippet[space_pos + 1:]
        
        # Clean up ending
        if len(snippet) >= max_length - 5 and best_pos + max_length < len(full_text):
            last_space = snippet.rfind(' ')
            if last_space > max_length - 50:  # Don't cut too much
                snippet = snippet[:last_space] + "..."
            else:
                snippet = snippet + "..."
        
        return snippet.strip()