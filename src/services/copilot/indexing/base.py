"""
Base interface for Phase 13 Copilot Indexing.

Provides abstract base class for indexing implementations:
- BaseIndexer for consistent interface across source types
- Tenant-aware indexing operations
- Support for incremental and full indexing modes

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-4, P13-5
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

from src.infrastructure.db.models import CopilotDocumentSourceType
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.services.copilot.chunking_service import DocumentChunkingService
from src.services.copilot.embedding_service import EmbeddingService

from .types import IndexingResult

logger = logging.getLogger(__name__)


class IndexingError(Exception):
    """Base exception for indexing operations."""
    pass


class TenantIsolationError(IndexingError):
    """Raised when tenant isolation is violated."""
    pass


class BaseIndexer(ABC):
    """
    Abstract base class for document indexers.
    
    Provides common interface for indexing different source types
    while maintaining tenant isolation and consistent processing.
    
    All indexer implementations must:
    - Support tenant-scoped operations
    - Handle incremental and full indexing
    - Use provided embedding and chunking services
    - Return structured IndexingResult
    """

    def __init__(
        self,
        document_repository: CopilotDocumentRepository,
        embedding_service: EmbeddingService,
        chunking_service: DocumentChunkingService,
    ):
        """
        Initialize base indexer with required services.
        
        Args:
            document_repository: Repository for vector document storage
            embedding_service: Service for generating embeddings
            chunking_service: Service for document chunking
        """
        self.document_repository = document_repository
        self.embedding_service = embedding_service
        self.chunking_service = chunking_service
        
    @property
    @abstractmethod
    def source_type(self) -> CopilotDocumentSourceType:
        """
        Return the source type handled by this indexer.
        
        Returns:
            CopilotDocumentSourceType for this indexer
        """
        pass
    
    @abstractmethod
    def supports_tenant(self, tenant_id: str) -> bool:
        """
        Check if this indexer supports the given tenant.
        
        Args:
            tenant_id: Tenant identifier to check
            
        Returns:
            True if tenant is supported, False otherwise
        """
        pass
    
    @abstractmethod
    async def index_incremental(
        self,
        tenant_id: str,
        source_id: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        domain: Optional[str] = None,
        source_version: Optional[str] = None,
    ) -> IndexingResult:
        """
        Perform incremental indexing of a single document.
        
        Should check for existing content and only update if changed.
        
        Args:
            tenant_id: Tenant identifier for isolation
            source_id: Unique identifier of source document
            content: Document content to index
            metadata: Optional metadata dictionary
            domain: Optional domain classification
            source_version: Optional version for cache invalidation
            
        Returns:
            IndexingResult with operation details
            
        Raises:
            TenantIsolationError: If tenant isolation is violated
            IndexingError: If indexing fails
        """
        pass
    
    @abstractmethod
    async def index_full(
        self,
        tenant_id: str,
        force_reindex: bool = False,
    ) -> list[IndexingResult]:
        """
        Perform full indexing of all documents for tenant.
        
        Should discover all available documents and index them.
        
        Args:
            tenant_id: Tenant identifier for isolation
            force_reindex: If True, reindex even unchanged documents
            
        Returns:
            List of IndexingResult for each processed document
            
        Raises:
            TenantIsolationError: If tenant isolation is violated
            IndexingError: If indexing fails
        """
        pass
    
    async def remove_document(
        self,
        tenant_id: str,
        source_id: str,
    ) -> bool:
        """
        Remove indexed document and all its chunks.
        
        Args:
            tenant_id: Tenant identifier for isolation
            source_id: Source document identifier
            
        Returns:
            True if document was removed, False if not found
            
        Raises:
            TenantIsolationError: If tenant isolation is violated
        """
        try:
            self._validate_tenant_access(tenant_id)
            
            removed_count = await self.document_repository.delete_by_source(
                tenant_id=tenant_id,
                source_type=self.source_type,
                source_id=source_id,
            )
            
            if removed_count > 0:
                logger.info(
                    f"Removed {removed_count} chunks for {self.source_type.value}:{source_id} "
                    f"(tenant: {tenant_id})"
                )
                return True
            
            logger.debug(
                f"No chunks found to remove for {self.source_type.value}:{source_id} "
                f"(tenant: {tenant_id})"
            )
            return False
            
        except Exception as e:
            logger.error(
                f"Failed to remove document {self.source_type.value}:{source_id} "
                f"(tenant: {tenant_id}): {e}"
            )
            raise IndexingError(f"Failed to remove document: {e}") from e
    
    def _validate_tenant_access(self, tenant_id: str) -> None:
        """
        Validate tenant access and isolation.
        
        Args:
            tenant_id: Tenant identifier to validate
            
        Raises:
            TenantIsolationError: If tenant validation fails
        """
        if not tenant_id:
            raise TenantIsolationError("Tenant ID is required")
            
        if not self.supports_tenant(tenant_id):
            raise TenantIsolationError(
                f"Indexer {self.__class__.__name__} does not support tenant {tenant_id}"
            )
    
    def _create_indexing_result(
        self,
        tenant_id: str,
        source_id: str,
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs: Any,
    ) -> IndexingResult:
        """
        Create IndexingResult with common fields populated.
        
        Args:
            tenant_id: Tenant identifier
            source_id: Source document identifier
            success: Whether operation succeeded
            error_message: Optional error message
            **kwargs: Additional fields for IndexingResult
            
        Returns:
            Populated IndexingResult instance
        """
        return IndexingResult(
            source_type=self.source_type,
            source_id=source_id,
            tenant_id=tenant_id,
            success=success,
            error_message=error_message,
            start_time=kwargs.get("start_time"),
            end_time=kwargs.get("end_time", datetime.utcnow()),
            **{k: v for k, v in kwargs.items() if k not in ["start_time", "end_time"]},
        )
