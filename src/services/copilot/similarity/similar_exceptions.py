"""
Similar Exceptions Finder for Phase 13 Copilot Intelligence MVP.

This service finds similar resolved exceptions for a given exception by:
1. Building a query from the exception's type, description, and attributes
2. Using vector similarity search against resolved exceptions only
3. Returning ranked similar cases with outcome summaries and metadata

Phase 13 Prompt 3.3: Cross-reference similar cases with tenant isolation.
"""

import logging
from dataclasses import dataclass
from typing import List, Optional

from src.infrastructure.db.models import Exception as ExceptionModel, ExceptionStatus
from src.repository.exceptions_repository import ExceptionRepository
from src.services.copilot.retrieval.retrieval_service import RetrievalService
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository

logger = logging.getLogger(__name__)


@dataclass
class SimilarException:
    """
    Similar exception result with outcome information.
    
    Represents a resolved exception that is similar to the current exception,
    with metadata about the resolution and similarity score.
    """
    exception_id: str
    similarity_score: float
    outcome_summary: str
    closed_at: Optional[str] = None  # ISO format timestamp
    link_url: Optional[str] = None


class SimilarExceptionsFinder:
    """
    Service for finding similar resolved exceptions using vector similarity search.
    
    Builds contextual queries from exception metadata and searches the vector store
    for similar resolved exceptions within the same tenant.
    
    Usage:
        finder = SimilarExceptionsFinder(exception_repo, retrieval_service)
        similar = await finder.find_similar(tenant_id="tenant-123", 
                                           exception_id="EX-2024-1234", 
                                           top_n=5)
    """

    def __init__(
        self,
        exception_repository: ExceptionRepository,
        retrieval_service: RetrievalService
    ):
        """
        Initialize the SimilarExceptionsFinder.

        Args:
            exception_repository: Repository for fetching exception data
            retrieval_service: Service for vector similarity retrieval
        """
        self.exception_repository = exception_repository
        self.retrieval_service = retrieval_service

    async def find_similar(
        self,
        tenant_id: str,
        exception_id: str,
        top_n: int = 5
    ) -> List[SimilarException]:
        """
        Find similar resolved exceptions for a given exception.

        Args:
            tenant_id: Tenant identifier for isolation
            exception_id: Exception identifier to find similar cases for
            top_n: Maximum number of similar exceptions to return (default: 5)

        Returns:
            List of SimilarException objects sorted by similarity score (highest first)

        Raises:
            ValueError: If exception_id not found or invalid parameters
            Exception: If retrieval service fails
        """
        # Input validation
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        
        if not exception_id or not exception_id.strip():
            raise ValueError("exception_id cannot be empty")
        
        if top_n <= 0:
            raise ValueError("top_n must be greater than 0")

        # Fetch the source exception
        exception = await self.exception_repository.get_exception(tenant_id, exception_id)
        if not exception:
            raise ValueError(f"Exception {exception_id} not found for tenant {tenant_id}")

        logger.info(
            f"Finding similar exceptions for {exception_id} in tenant {tenant_id}, "
            f"top_n={top_n}"
        )

        try:
            # Build query text from exception fields
            query_text = self._build_query_text(exception)
            
            logger.debug(f"Built query text: {query_text[:200]}...")

            # Retrieve similar exceptions using vector search
            # Only search for resolved exceptions (source_type="resolved_exception")
            evidence_items = await self.retrieval_service.retrieve_evidence(
                tenant_id=tenant_id,
                query_text=query_text,
                domain=exception.domain,  # Scope to same domain for better relevance
                source_types=["resolved_exception"],  # Only resolved exceptions
                top_k=top_n
            )

            # Convert evidence items to SimilarException objects
            similar_exceptions = []
            for evidence in evidence_items:
                # Extract exception_id from source_id (assuming it's stored as exception_id)
                similar_exception_id = evidence.source_id
                
                # Create outcome summary from the snippet
                outcome_summary = self._create_outcome_summary(evidence.snippet)
                
                # Build URL for the exception
                link_url = f"/exceptions/{similar_exception_id}"
                
                similar_exceptions.append(SimilarException(
                    exception_id=similar_exception_id,
                    similarity_score=evidence.similarity_score,
                    outcome_summary=outcome_summary,
                    closed_at=evidence.source_version,  # Assuming source_version contains timestamp
                    link_url=link_url
                ))

            logger.info(
                f"Found {len(similar_exceptions)} similar exceptions for {exception_id}"
            )

            return similar_exceptions

        except Exception as e:
            logger.error(f"Error finding similar exceptions for {exception_id}: {str(e)}")
            raise

    def _build_query_text(self, exception: ExceptionModel) -> str:
        """
        Build a search query from exception fields.

        Combines type, description-like attributes, and key metadata
        to create a comprehensive search query for finding similar cases.

        Args:
            exception: Exception object to build query from

        Returns:
            Combined query text for similarity search
        """
        query_parts = []
        
        # Start with exception type - most important for similarity
        if exception.type:
            query_parts.append(f"Exception type: {exception.type}")
        
        # Add domain for context
        if exception.domain:
            query_parts.append(f"Domain: {exception.domain}")
        
        # Add source system context
        if exception.source_system:
            query_parts.append(f"Source system: {exception.source_system}")
        
        # Add entity if present (helps with contextual similarity)
        if exception.entity:
            query_parts.append(f"Entity: {exception.entity}")
        
        # Add severity for matching similar impact levels
        if exception.severity:
            query_parts.append(f"Severity: {exception.severity.value}")
        
        # Add amount context if present (financial exceptions)
        if exception.amount:
            query_parts.append(f"Amount: {exception.amount}")
        
        # Combine all parts with spaces
        query_text = " ".join(query_parts)
        
        # Ensure we have a meaningful query
        if not query_text.strip():
            query_text = f"Exception in {exception.domain or 'unknown'} domain"
        
        return query_text

    def _create_outcome_summary(self, snippet: str) -> str:
        """
        Create a concise outcome summary from the evidence snippet.

        Extracts key outcome information from the retrieved text snippet
        to provide a brief summary of how the similar case was resolved.

        Args:
            snippet: Text snippet from the similar exception

        Returns:
            Concise outcome summary (max ~150 characters)
        """
        if not snippet:
            return "Resolution details not available"
        
        # Clean up the snippet
        clean_snippet = snippet.strip()
        
        # If snippet is short enough, return as-is
        if len(clean_snippet) <= 150:
            return clean_snippet
        
        # Try to find sentence boundaries for better truncation
        sentences = clean_snippet.split('. ')
        if len(sentences) > 1 and len(sentences[0]) <= 130:
            return sentences[0] + '.'
        
        # Fallback to simple truncation with ellipsis
        truncated = clean_snippet[:147]
        
        # Try to end at a word boundary
        last_space = truncated.rfind(' ')
        if last_space > 100:  # Only if we can preserve reasonable length
            truncated = truncated[:last_space]
        
        return truncated + "..."

    async def find_similar_by_query(
        self,
        tenant_id: str,
        query: str,
        top_n: int = 5
    ) -> List[SimilarException]:
        """
        Find similar resolved exceptions based on a query string.

        Args:
            tenant_id: Tenant identifier for isolation
            query: Query string to search for similar exceptions
            top_n: Maximum number of similar exceptions to return (default: 5)

        Returns:
            List of SimilarException objects sorted by similarity score (highest first)

        Raises:
            ValueError: If invalid parameters
            Exception: If retrieval service fails
        """
        # Input validation
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id cannot be empty")
        
        if not query or not query.strip():
            raise ValueError("query cannot be empty")
        
        if top_n <= 0:
            raise ValueError("top_n must be greater than 0")

        logger.info(
            f"Finding similar exceptions by query in tenant {tenant_id}, "
            f"query: {query[:100]}..., top_n={top_n}"
        )

        try:
            # Use the query directly for vector search
            # Only search for resolved exceptions (source_type="resolved_exception")
            evidence_items = await self.retrieval_service.retrieve_evidence(
                tenant_id=tenant_id,
                query_text=query.strip(),
                source_types=["resolved_exception"],
                top_k=top_n * 3  # Get more candidates for better filtering
            )
            
            if not evidence_items:
                logger.info(f"No evidence found for query in tenant {tenant_id}")
                return []

            # Group evidence by exception_id and calculate aggregate scores
            exception_groups = {}
            for item in evidence_items:
                exc_id = item.exception_id
                if exc_id not in exception_groups:
                    exception_groups[exc_id] = {
                        'items': [],
                        'max_score': 0.0,
                        'total_score': 0.0
                    }
                
                exception_groups[exc_id]['items'].append(item)
                exception_groups[exc_id]['max_score'] = max(
                    exception_groups[exc_id]['max_score'], 
                    item.similarity_score
                )
                exception_groups[exc_id]['total_score'] += item.similarity_score

            # Convert to SimilarException objects
            similar_exceptions = []
            for exc_id, group in exception_groups.items():
                # Get the best evidence snippet from this exception
                best_item = max(group['items'], key=lambda x: x.similarity_score)
                
                similar_exception = SimilarException(
                    exception_id=exc_id,
                    similarity_score=group['max_score'],  # Use max score as primary metric
                    outcome_summary=self._create_outcome_summary(best_item.content)
                )
                similar_exceptions.append(similar_exception)

            # Sort by similarity score (highest first) and limit results
            similar_exceptions.sort(key=lambda x: x.similarity_score, reverse=True)
            limited_results = similar_exceptions[:top_n]

            logger.info(
                f"Found {len(limited_results)} similar exceptions for query in tenant {tenant_id}"
            )
            
            return limited_results

        except Exception as e:
            logger.error(f"Error finding similar exceptions by query: {str(e)}")
            raise Exception(f"Failed to find similar exceptions: {str(e)}")