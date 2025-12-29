"""
PolicyDocsIndexer for Phase 13 Copilot Intelligence.

Implements indexing of policy documents from Domain Packs and Tenant Packs:
- Converts policy docs to text chunks using DocumentChunkingService
- Generates embeddings using EmbeddingService
- Stores indexed content with proper tenant isolation
- Supports incremental indexing with content hash change detection

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2 (PolicyDocs indexing)
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-4, P13-8
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.infrastructure.db.models import CopilotDocumentSourceType
from src.infrastructure.repositories.copilot_document_repository import (
    CopilotDocumentRepository,
    DocumentChunk as RepositoryDocumentChunk,
)
from src.services.copilot.chunking_service import (
    ChunkingConfig,
    DocumentChunkingService,
    SourceDocument,
)
from src.services.copilot.embedding_service import EmbeddingService

from .base import BaseIndexer, IndexingError, TenantIsolationError
from .types import IndexingResult
from .utils import content_hash, document_fingerprint, stable_chunk_key, validate_tenant_id

logger = logging.getLogger(__name__)


@dataclass
class PolicyDoc:
    """Policy document extracted from Domain/Tenant Packs."""
    
    doc_id: str  # Unique document identifier
    title: str
    content: str
    
    # Optional metadata
    description: Optional[str] = None
    url: Optional[str] = None
    category: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_source_document(
        self,
        domain: Optional[str] = None,
        pack_version: Optional[str] = None,
    ) -> SourceDocument:
        """Convert to SourceDocument for chunking."""
        return SourceDocument(
            source_type=CopilotDocumentSourceType.POLICY_DOC.value,
            source_id=self.doc_id,
            content=self.content,
            domain=domain,
            version=pack_version,
            title=self.title,
            metadata={
                "description": self.description,
                "url": self.url,
                "category": self.category,
                "tags": self.tags,
                **self.metadata,
            },
        )


class PolicyDocsIndexer(BaseIndexer):
    """
    Indexer for policy documents from Domain and Tenant Packs.
    
    Features:
    - Domain-agnostic indexing (not hardcoded to finance/healthcare)
    - Incremental indexing with content hash change detection
    - Tenant isolation enforcement
    - Optimized chunking configuration for policy documents
    - Batch embedding generation and storage
    """

    def __init__(
        self,
        document_repository: CopilotDocumentRepository,
        embedding_service: EmbeddingService,
        chunking_service: Optional[DocumentChunkingService] = None,
    ):
        """
        Initialize PolicyDocsIndexer.
        
        Args:
            document_repository: Repository for vector document storage
            embedding_service: Service for generating embeddings
            chunking_service: Optional service for document chunking
                            (defaults to policy-optimized configuration)
        """
        # Use policy-optimized chunking config if not provided
        if chunking_service is None:
            config = ChunkingConfig.for_policy_docs()
            chunking_service = DocumentChunkingService(config)
            
        super().__init__(document_repository, embedding_service, chunking_service)
        
    @property
    def source_type(self) -> CopilotDocumentSourceType:
        """Return the source type for policy documents."""
        return CopilotDocumentSourceType.POLICY_DOC
    
    def supports_tenant(self, tenant_id: str) -> bool:
        """
        Check if this indexer supports the given tenant.
        
        Args:
            tenant_id: Tenant identifier to check
            
        Returns:
            True if tenant ID is valid, False otherwise
        """
        return validate_tenant_id(tenant_id)
    
    async def index_policy_docs(
        self,
        tenant_id: str,
        policy_docs: list[PolicyDoc],
        domain: Optional[str] = None,
        pack_version: Optional[str] = None,
        force_reindex: bool = False,
    ) -> IndexingResult:
        """
        Index a list of policy documents for a tenant.
        
        Args:
            tenant_id: Tenant identifier for isolation
            policy_docs: List of policy documents to index
            domain: Optional domain classification
            pack_version: Optional pack version for change tracking
            force_reindex: If True, reindex even unchanged documents
            
        Returns:
            IndexingResult with operation details
            
        Raises:
            TenantIsolationError: If tenant isolation is violated
            IndexingError: If indexing fails
        """
        start_time = datetime.utcnow()
        
        try:
            self._validate_tenant_access(tenant_id)
            
            if not policy_docs:
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id="bulk-policy-docs",
                    start_time=start_time,
                    chunks_processed=0,
                    chunks_indexed=0,
                    chunks_skipped=0,
                )
            
            logger.info(
                f"Starting policy docs indexing: tenant={tenant_id}, "
                f"docs={len(policy_docs)}, domain={domain}, version={pack_version}"
            )
            
            total_processed = 0
            total_indexed = 0
            total_skipped = 0
            total_failed = 0
            
            # Process each policy document
            for doc in policy_docs:
                try:
                    result = await self._index_single_policy_doc(
                        tenant_id=tenant_id,
                        policy_doc=doc,
                        domain=domain,
                        pack_version=pack_version,
                        force_reindex=force_reindex,
                    )
                    
                    total_processed += result.chunks_processed
                    total_indexed += result.chunks_indexed
                    total_skipped += result.chunks_skipped
                    total_failed += result.chunks_failed
                    
                except Exception as e:
                    logger.error(
                        f"Failed to index policy doc {doc.doc_id} "
                        f"(tenant: {tenant_id}): {e}"
                    )
                    total_failed += 1
                    
            end_time = datetime.utcnow()
            
            logger.info(
                f"Completed policy docs indexing: tenant={tenant_id}, "
                f"processed={total_processed}, indexed={total_indexed}, "
                f"skipped={total_skipped}, failed={total_failed}"
            )
            
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="bulk-policy-docs",
                start_time=start_time,
                end_time=end_time,
                chunks_processed=total_processed,
                chunks_indexed=total_indexed,
                chunks_skipped=total_skipped,
                chunks_failed=total_failed,
                source_version=pack_version,
                metadata={
                    "domain": domain,
                    "total_documents": len(policy_docs),
                },
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            error_msg = f"Policy docs indexing failed: {e}"
            logger.error(f"{error_msg} (tenant: {tenant_id})")
            
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="bulk-policy-docs",
                success=False,
                start_time=start_time,
                end_time=end_time,
                error_message=error_msg,
                metadata={"domain": domain, "total_documents": len(policy_docs)},
            )
    
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
        Perform incremental indexing of a single policy document.
        
        Args:
            tenant_id: Tenant identifier for isolation
            source_id: Policy document identifier
            content: Document content to index
            metadata: Optional metadata dictionary
            domain: Optional domain classification
            source_version: Optional version for cache invalidation
            
        Returns:
            IndexingResult with operation details
        """
        # Create PolicyDoc from parameters
        title = metadata.get("title", source_id) if metadata else source_id
        
        policy_doc = PolicyDoc(
            doc_id=source_id,
            title=title,
            content=content,
            description=metadata.get("description") if metadata else None,
            url=metadata.get("url") if metadata else None,
            category=metadata.get("category") if metadata else None,
            tags=metadata.get("tags", []) if metadata else [],
            metadata=metadata or {},
        )
        
        return await self._index_single_policy_doc(
            tenant_id=tenant_id,
            policy_doc=policy_doc,
            domain=domain,
            pack_version=source_version,
            force_reindex=False,
        )
    
    async def index_full(
        self,
        tenant_id: str,
        force_reindex: bool = False,
    ) -> list[IndexingResult]:
        """
        Perform full indexing of all policy documents for tenant.
        
        Note: This is a placeholder implementation. In practice, this would
        need to discover policy documents from Domain Packs and Tenant Packs.
        
        Args:
            tenant_id: Tenant identifier for isolation
            force_reindex: If True, reindex even unchanged documents
            
        Returns:
            List of IndexingResult for each processed pack
        """
        self._validate_tenant_access(tenant_id)
        
        # TODO: Implement full discovery of policy documents from packs
        # This would involve:
        # 1. Loading active domain packs for tenant
        # 2. Loading active tenant packs
        # 3. Extracting policy documents from packs
        # 4. Calling index_policy_docs for each discovered set
        
        logger.warning(
            f"Full indexing not yet implemented for PolicyDocsIndexer "
            f"(tenant: {tenant_id}). Use index_policy_docs directly."
        )
        
        return []
    
    async def _index_single_policy_doc(
        self,
        tenant_id: str,
        policy_doc: PolicyDoc,
        domain: Optional[str],
        pack_version: Optional[str],
        force_reindex: bool,
    ) -> IndexingResult:
        """
        Index a single policy document.
        
        Args:
            tenant_id: Tenant identifier
            policy_doc: Policy document to index
            domain: Domain classification
            pack_version: Pack version
            force_reindex: Whether to force reindexing
            
        Returns:
            IndexingResult for the document
        """
        start_time = datetime.utcnow()
        
        try:
            # Check if document needs indexing (incremental mode)
            if not force_reindex:
                fingerprint = document_fingerprint(
                    content=policy_doc.content,
                    metadata=policy_doc.metadata,
                    source_version=pack_version,
                )
                
                # Check if document exists with same fingerprint
                existing_docs = await self.document_repository.find_by_source(
                    tenant_id=tenant_id,
                    source_type=self.source_type,
                    source_id=policy_doc.doc_id,
                )
                
                if existing_docs:
                    # Check if any existing document has same fingerprint
                    existing_fingerprint = document_fingerprint(
                        content=existing_docs[0].content,
                        metadata=existing_docs[0].metadata_json or {},
                        source_version=existing_docs[0].version,
                    )
                    
                    if fingerprint == existing_fingerprint:
                        logger.debug(
                            f"Skipping unchanged policy doc {policy_doc.doc_id} "
                            f"(tenant: {tenant_id})"
                        )
                        return self._create_indexing_result(
                            tenant_id=tenant_id,
                            source_id=policy_doc.doc_id,
                            start_time=start_time,
                            chunks_processed=1,
                            chunks_skipped=1,
                        )
            
            # Convert to source document for chunking
            source_doc = policy_doc.to_source_document(
                domain=domain,
                pack_version=pack_version,
            )
            
            # Generate document chunks
            chunks = self.chunking_service.chunk_document(source_doc)
            
            if not chunks:
                logger.warning(
                    f"No chunks generated for policy doc {policy_doc.doc_id} "
                    f"(tenant: {tenant_id})"
                )
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id=policy_doc.doc_id,
                    start_time=start_time,
                    chunks_processed=0,
                )
            
            # Extract text content for embedding generation
            chunk_texts = [chunk.content for chunk in chunks]
            
            # Generate embeddings in batch
            embedding_results = await self.embedding_service.generate_embeddings_batch(
                texts=chunk_texts,
                use_cache=True,
            )
            
            # Convert to repository document chunks
            repo_chunks = []
            for chunk, embedding_result in zip(chunks, embedding_results):
                # Generate stable chunk key
                chunk_key = stable_chunk_key(
                    tenant_id=tenant_id,
                    source_type=self.source_type,
                    source_id=policy_doc.doc_id,
                    chunk_id=chunk.chunk_id,
                    source_version=pack_version,
                )
                
                repo_chunk = RepositoryDocumentChunk(
                    source_type=self.source_type.value,
                    source_id=policy_doc.doc_id,
                    chunk_id=chunk_key,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    embedding=embedding_result.embedding,
                    embedding_model=embedding_result.model,
                    embedding_dimension=embedding_result.dimension,
                    domain=domain,
                    version=pack_version,
                    metadata={
                        "title": policy_doc.title,
                        "description": policy_doc.description,
                        "url": policy_doc.url,
                        "category": policy_doc.category,
                        "tags": policy_doc.tags,
                        "chunk_index": chunk.chunk_index,
                        "total_chunks": chunk.total_chunks,
                        **chunk.metadata,
                    },
                )
                repo_chunks.append(repo_chunk)
            
            # Batch upsert chunks
            upserted_count = await self.document_repository.upsert_chunks_batch(
                tenant_id=tenant_id,
                chunks=repo_chunks,
            )
            
            end_time = datetime.utcnow()
            
            logger.debug(
                f"Indexed policy doc {policy_doc.doc_id}: {upserted_count} chunks "
                f"(tenant: {tenant_id})"
            )
            
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=policy_doc.doc_id,
                start_time=start_time,
                end_time=end_time,
                chunks_processed=len(chunks),
                chunks_indexed=upserted_count,
                content_hash=content_hash(policy_doc.content),
                source_version=pack_version,
                embedding_model=embedding_results[0].model if embedding_results else None,
                embedding_dimension=embedding_results[0].dimension if embedding_results else None,
                metadata={
                    "title": policy_doc.title,
                    "domain": domain,
                    "total_chunks": len(chunks),
                },
            )
            
        except Exception as e:
            end_time = datetime.utcnow()
            error_msg = f"Failed to index policy doc {policy_doc.doc_id}: {e}"
            logger.error(f"{error_msg} (tenant: {tenant_id})")
            
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=policy_doc.doc_id,
                success=False,
                start_time=start_time,
                end_time=end_time,
                error_message=error_msg,
                chunks_failed=1,
            )
