"""
PlaybookIndexer for Phase 13 Copilot Intelligence.

Implements indexing of playbook definitions from Domain Packs and Tenant Packs:
- Converts playbook definitions to text for semantic search
- Generates embeddings using EmbeddingService
- Stores indexed content with proper tenant isolation
- Supports incremental indexing with content hash change detection

Playbooks are indexed with structured metadata for:
- playbook_id: Unique playbook identifier
- domain: Domain classification (finance, healthcare, etc.)
- tenant_id: Tenant identifier for isolation
- exception_type: Exception types this playbook handles
- pack_version: Version of the source pack

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2 (Playbook indexing)
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.infrastructure.db.models import CopilotDocumentSourceType, Playbook, PlaybookStep
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
from .utils import content_hash, document_fingerprint, validate_tenant_id

logger = logging.getLogger(__name__)


@dataclass
class PlaybookDefinition:
    """Playbook definition extracted from Domain/Tenant Packs or DB."""
    
    playbook_id: str  # Unique playbook identifier
    name: str
    description: Optional[str] = None
    
    # Playbook steps
    steps: list[dict[str, Any]] = field(default_factory=list)
    
    # Conditions/matching rules
    conditions: dict[str, Any] = field(default_factory=dict)
    
    # Optional metadata
    domain: Optional[str] = None
    version: Optional[int] = None
    pack_version: Optional[str] = None
    exception_types: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    
    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_db_playbook(
        cls,
        playbook: Playbook,
        steps: list[PlaybookStep],
        domain: Optional[str] = None,
        pack_version: Optional[str] = None,
    ) -> "PlaybookDefinition":
        """Create PlaybookDefinition from database model."""
        conditions = playbook.conditions or {}
        exception_types = conditions.get("exception_types", [])
        
        step_defs = [
            {
                "step": step.step_order,
                "name": step.name,
                "action_type": step.action_type,
                "params": step.params or {},
            }
            for step in sorted(steps, key=lambda s: s.step_order)
        ]
        
        return cls(
            playbook_id=str(playbook.playbook_id),
            name=playbook.name,
            description=conditions.get("description", ""),
            steps=step_defs,
            conditions=conditions,
            domain=domain,
            version=playbook.version,
            pack_version=pack_version,
            exception_types=exception_types,
            tags=conditions.get("tags", []),
        )
    
    def to_indexable_text(self) -> str:
        """
        Convert playbook definition to searchable text content.
        
        Creates a comprehensive text representation including:
        - Playbook name and description
        - Exception types handled
        - Step-by-step instructions
        - Tags and conditions
        """
        lines = [
            f"Playbook: {self.name}",
            f"Playbook ID: {self.playbook_id}",
        ]
        
        if self.description:
            lines.append(f"Description: {self.description}")
        
        if self.domain:
            lines.append(f"Domain: {self.domain}")
        
        if self.exception_types:
            lines.append(f"Handles exception types: {', '.join(self.exception_types)}")
        
        if self.tags:
            lines.append(f"Tags: {', '.join(self.tags)}")
        
        # Add step details
        if self.steps:
            lines.append("\nPlaybook Steps:")
            for step in self.steps:
                step_num = step.get("step", step.get("step_order", "?"))
                step_name = step.get("name", step.get("text", "Unknown step"))
                action_type = step.get("action_type", "")
                lines.append(f"  Step {step_num}: {step_name}")
                if action_type:
                    lines.append(f"    Action: {action_type}")
                params = step.get("params", {})
                if params:
                    for key, value in params.items():
                        lines.append(f"    {key}: {value}")
        
        # Add condition info
        if self.conditions:
            severities = self.conditions.get("severities", [])
            if severities:
                lines.append(f"\nApplicable severities: {', '.join(severities)}")
        
        return "\n".join(lines)
    
    def to_source_document(self) -> SourceDocument:
        """Convert to SourceDocument for chunking."""
        return SourceDocument(
            source_type=CopilotDocumentSourceType.PLAYBOOK.value,
            source_id=self.playbook_id,
            content=self.to_indexable_text(),
            domain=self.domain,
            version=self.pack_version or str(self.version or "1"),
            title=self.name,
            metadata={
                "playbook_id": self.playbook_id,
                "name": self.name,
                "description": self.description,
                "exception_types": self.exception_types,
                "tags": self.tags,
                "steps_count": len(self.steps),
                "steps": self.steps,
                "conditions": self.conditions,
            },
        )


class PlaybookIndexer(BaseIndexer):
    """
    Indexer for playbook definitions from Domain and Tenant Packs.
    
    Features:
    - Domain-agnostic indexing (not hardcoded to finance/healthcare)
    - Incremental indexing with content hash change detection
    - Tenant isolation enforcement
    - Rich metadata for playbook retrieval and citation
    - Batch embedding generation and storage
    """

    def __init__(
        self,
        document_repository: CopilotDocumentRepository,
        embedding_service: EmbeddingService,
        chunking_service: Optional[DocumentChunkingService] = None,
    ):
        """
        Initialize PlaybookIndexer.
        
        Args:
            document_repository: Repository for vector document storage
            embedding_service: Service for generating embeddings
            chunking_service: Optional service for document chunking
                            (defaults to playbook-optimized configuration)
        """
        # Use playbook-optimized chunking config if not provided
        if chunking_service is None:
            # Playbooks are typically not very long, so use smaller chunks
            config = ChunkingConfig(
                chunk_size=500,
                chunk_overlap=100,
                min_chunk_size=50,
            )
            chunking_service = DocumentChunkingService(config)
            
        super().__init__(document_repository, embedding_service, chunking_service)
        
    @property
    def source_type(self) -> CopilotDocumentSourceType:
        """Return the source type for playbooks."""
        return CopilotDocumentSourceType.PLAYBOOK
    
    def supports_tenant(self, tenant_id: str) -> bool:
        """
        Check if this indexer supports the given tenant.
        
        Args:
            tenant_id: Tenant identifier to check
            
        Returns:
            True if tenant ID is valid, False otherwise
        """
        return validate_tenant_id(tenant_id)
    
    async def index_playbooks(
        self,
        tenant_id: str,
        playbooks: list[PlaybookDefinition],
        domain: Optional[str] = None,
        pack_version: Optional[str] = None,
        force_reindex: bool = False,
    ) -> IndexingResult:
        """
        Index a list of playbook definitions for a tenant.
        
        Args:
            tenant_id: Tenant identifier for isolation
            playbooks: List of playbook definitions to index
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
            
            if not playbooks:
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id="bulk-playbooks",
                    start_time=start_time,
                    chunks_processed=0,
                    chunks_indexed=0,
                    chunks_skipped=0,
                )
            
            logger.info(
                f"Starting playbook indexing: tenant={tenant_id}, "
                f"playbooks={len(playbooks)}, domain={domain}, version={pack_version}"
            )
            
            total_processed = 0
            total_indexed = 0
            total_skipped = 0
            total_failed = 0
            
            # Process each playbook
            for playbook in playbooks:
                try:
                    result = await self._index_single_playbook(
                        tenant_id=tenant_id,
                        playbook=playbook,
                        domain=domain or playbook.domain,
                        pack_version=pack_version or playbook.pack_version,
                        force_reindex=force_reindex,
                    )
                    
                    total_processed += result.chunks_processed
                    total_indexed += result.chunks_indexed
                    total_skipped += result.chunks_skipped
                    total_failed += result.chunks_failed
                    
                except Exception as e:
                    logger.error(
                        f"Failed to index playbook {playbook.playbook_id} "
                        f"(tenant: {tenant_id}): {e}"
                    )
                    total_failed += 1
            
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="bulk-playbooks",
                start_time=start_time,
                chunks_processed=total_processed,
                chunks_indexed=total_indexed,
                chunks_skipped=total_skipped,
                chunks_failed=total_failed,
            )
            
        except TenantIsolationError:
            raise
        except Exception as e:
            logger.error(f"Playbook indexing failed (tenant: {tenant_id}): {e}")
            raise IndexingError(f"Playbook indexing failed: {e}") from e
    
    async def _index_single_playbook(
        self,
        tenant_id: str,
        playbook: PlaybookDefinition,
        domain: Optional[str] = None,
        pack_version: Optional[str] = None,
        force_reindex: bool = False,
    ) -> IndexingResult:
        """
        Index a single playbook definition.
        
        Args:
            tenant_id: Tenant identifier
            playbook: Playbook definition to index
            domain: Domain classification
            pack_version: Pack version for tracking
            force_reindex: Force reindex even if unchanged
            
        Returns:
            IndexingResult for this playbook
        """
        start_time = datetime.utcnow()
        source_id = playbook.playbook_id
        
        # Convert to source document for chunking
        source_doc = playbook.to_source_document()
        if domain:
            source_doc.domain = domain
        if pack_version:
            source_doc.version = pack_version
        
        # Calculate content hash for change detection
        playbook_content = playbook.to_indexable_text()
        current_hash = content_hash(playbook_content)
        
        # Check if playbook needs reindexing
        if not force_reindex:
            existing_doc = await self.document_repository.get_by_source(
                tenant_id=tenant_id,
                source_type=self.source_type.value,
                source_id=source_id,
            )
            
            if existing_doc and existing_doc.content_hash == current_hash:
                logger.debug(
                    f"Playbook {source_id} unchanged, skipping (tenant: {tenant_id})"
                )
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    start_time=start_time,
                    chunks_processed=0,
                    chunks_indexed=0,
                    chunks_skipped=1,
                )
        
        # Chunk the document
        chunks = self.chunking_service.chunk_document(source_doc)
        
        if not chunks:
            logger.warning(
                f"No chunks generated for playbook {source_id} (tenant: {tenant_id})"
            )
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=source_id,
                start_time=start_time,
                chunks_processed=0,
                chunks_indexed=0,
                chunks_skipped=0,
            )
        
        # Generate embeddings
        chunk_texts = [chunk.content for chunk in chunks]
        embedding_results = await self.embedding_service.generate_embeddings_batch(
            texts=chunk_texts,
            use_cache=True,
        )
        
        if len(embedding_results) != len(chunks):
            raise IndexingError(
                f"Embedding count mismatch: {len(embedding_results)} vs {len(chunks)} chunks"
            )
        
        # Delete existing chunks before inserting new ones
        await self.document_repository.delete_by_source(
            tenant_id=tenant_id,
            source_type=self.source_type.value,
            source_id=source_id,
        )
        
        # Prepare chunks for storage
        repo_chunks = []
        for i, (chunk, embedding_result) in enumerate(zip(chunks, embedding_results)):
            # Generate a stable chunk_id 
            chunk_id = f"{source_id}:chunk:{i}"
            
            metadata = {
                **chunk.metadata,
                "chunk_index": i,
                "total_chunks": len(chunks),
            }
            
            repo_chunk = RepositoryDocumentChunk(
                source_type=self.source_type.value,
                source_id=source_id,
                chunk_id=chunk_id,
                chunk_index=i,
                content=chunk.content,
                embedding=embedding_result.embedding,
                embedding_model=embedding_result.model,
                embedding_dimension=embedding_result.dimension,
                domain=domain,
                version=pack_version,
                metadata=metadata,
            )
            repo_chunks.append(repo_chunk)
        
        # Store chunks in repository with tenant isolation
        stored_count = await self.document_repository.upsert_chunks_batch(tenant_id, repo_chunks)
        
        logger.info(
            f"Indexed playbook {source_id}: {stored_count} chunks "
            f"(tenant: {tenant_id}, domain: {domain})"
        )
        
        return self._create_indexing_result(
            tenant_id=tenant_id,
            source_id=source_id,
            start_time=start_time,
            chunks_processed=len(chunks),
            chunks_indexed=stored_count,
            chunks_skipped=0,
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
        Perform incremental indexing of a single playbook.
        
        Creates a PlaybookDefinition from the provided content and indexes it.
        """
        start_time = datetime.utcnow()
        
        try:
            self._validate_tenant_access(tenant_id)
            
            # Create minimal playbook definition
            metadata = metadata or {}
            playbook = PlaybookDefinition(
                playbook_id=source_id,
                name=metadata.get("name", source_id),
                description=metadata.get("description"),
                steps=metadata.get("steps", []),
                conditions=metadata.get("conditions", {}),
                domain=domain,
                pack_version=source_version,
                exception_types=metadata.get("exception_types", []),
            )
            
            return await self._index_single_playbook(
                tenant_id=tenant_id,
                playbook=playbook,
                domain=domain,
                pack_version=source_version,
                force_reindex=False,
            )
            
        except TenantIsolationError:
            raise
        except Exception as e:
            logger.error(
                f"Incremental playbook indexing failed for {source_id} "
                f"(tenant: {tenant_id}): {e}"
            )
            raise IndexingError(f"Incremental indexing failed: {e}") from e
    
    async def index_full(
        self,
        tenant_id: str,
        force_reindex: bool = False,
    ) -> list[IndexingResult]:
        """
        Perform full indexing of all playbooks for tenant.
        
        This method should be called with playbooks from the caller.
        Use index_playbooks() for bulk indexing.
        """
        # Full indexing requires playbooks to be provided externally
        # Return empty result indicating no playbooks were discovered
        logger.info(
            f"Full playbook indexing called for tenant {tenant_id}. "
            "Use index_playbooks() with PlaybookDefinition list for bulk indexing."
        )
        return []
    
    async def index_from_db(
        self,
        tenant_id: str,
        playbooks: list[tuple[Playbook, list[PlaybookStep]]],
        domain: Optional[str] = None,
        pack_version: Optional[str] = None,
        force_reindex: bool = False,
    ) -> IndexingResult:
        """
        Index playbooks from database models.
        
        Args:
            tenant_id: Tenant identifier
            playbooks: List of (Playbook, list[PlaybookStep]) tuples from DB
            domain: Domain classification
            pack_version: Pack version for tracking
            force_reindex: Force reindex even if unchanged
            
        Returns:
            IndexingResult with operation details
        """
        # Convert DB models to PlaybookDefinition
        definitions = [
            PlaybookDefinition.from_db_playbook(pb, steps, domain, pack_version)
            for pb, steps in playbooks
        ]
        
        return await self.index_playbooks(
            tenant_id=tenant_id,
            playbooks=definitions,
            domain=domain,
            pack_version=pack_version,
            force_reindex=force_reindex,
        )
