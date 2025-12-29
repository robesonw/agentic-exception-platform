"""
AuditEventsIndexer for Phase 13 Copilot Intelligence.

Indexes governance audit events for Similar Cases RAG retrieval.
Supports incremental indexing via created_at watermark tracking.

Cross-reference:
- docs/phase13-copilot-intelligence-mvp.md (AuditEvents indexing)
- tasks: P13-6 (AuditEventsIndexer)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    GovernanceAuditEvent,
    IndexingState,
    CopilotDocumentSourceType,
)
from src.services.copilot.chunking_service import DocumentChunkingService, SourceDocument
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.services.copilot.indexing.base import BaseIndexer, IndexingError
from src.services.copilot.indexing.types import IndexingResult
from src.services.copilot.indexing.utils import content_hash, validate_tenant_id

logger = logging.getLogger(__name__)


@dataclass
class AuditEventDoc:
    """
    Audit event document for indexing.
    
    Extracts relevant audit information for Similar Cases RAG retrieval,
    focusing on event patterns and governance decisions.
    """
    event_id: str
    tenant_id: Optional[str]  # None for global events
    event_type: str
    entity_type: str
    entity_id: str
    action: str
    actor_id: str
    actor_role: Optional[str]
    diff_summary: Optional[str]
    correlation_id: Optional[str]
    created_at: datetime
    metadata: Optional[dict] = None

    def to_source_document(self) -> SourceDocument:
        """Convert audit event to source document for indexing."""
        # Build content text from audit event fields
        content_parts = [
            f"Event Type: {self.event_type}",
            f"Entity: {self.entity_type} ({self.entity_id})",
            f"Action: {self.action}",
            f"Actor: {self.actor_id}" + (f" ({self.actor_role})" if self.actor_role else ""),
        ]
        
        if self.diff_summary:
            content_parts.append(f"Changes: {self.diff_summary}")
        
        if self.correlation_id:
            content_parts.append(f"Correlation ID: {self.correlation_id}")
        
        content = " | ".join(content_parts)
        
        # Create metadata for the document
        doc_metadata = {
            "event_type": self.event_type,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "action": self.action,
            "actor_id": self.actor_id,
            "created_at": self.created_at.isoformat(),
        }
        
        if self.actor_role:
            doc_metadata["actor_role"] = self.actor_role
        
        if self.correlation_id:
            doc_metadata["correlation_id"] = self.correlation_id
        
        if self.metadata:
            doc_metadata.update(self.metadata)
        
        return SourceDocument(
            source_type=CopilotDocumentSourceType.AUDIT_EVENT,
            source_id=self.event_id,
            content=content,
            metadata=doc_metadata,
        )


class AuditEventsIndexer(BaseIndexer):
    """
    Indexes governance audit events for Copilot RAG retrieval.
    
    Features:
    - Incremental indexing via created_at watermark
    - Tenant isolation (global events stored with tenant_id=NULL)
    - Audit event content extraction and formatting
    - Integration with existing chunking and embedding services
    """

    def __init__(
        self,
        db_session: AsyncSession,
        embedding_service: EmbeddingService,
        chunking_service: DocumentChunkingService,
        document_repository: CopilotDocumentRepository,
    ):
        super().__init__(
            document_repository=document_repository,
            embedding_service=embedding_service,
            chunking_service=chunking_service,
        )
        self.db_session = db_session
        self._source_type = CopilotDocumentSourceType.AUDIT_EVENT

    @property
    def source_type(self) -> CopilotDocumentSourceType:
        """Return the source type handled by this indexer."""
        return self._source_type

    def supports_tenant(self, tenant_id: Optional[str]) -> bool:
        """
        Check if the indexer supports a given tenant.
        
        Args:
            tenant_id: Tenant ID to check (None for global)
            
        Returns:
            True if tenant is supported
        """
        # Support all valid tenant IDs and global events (None)
        if tenant_id is None:
            return True
        
        return validate_tenant_id(tenant_id)

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
        Perform incremental indexing of a single audit event.
        
        Note: This method supports single-event indexing, but the main
        entry point is index_audit_events_incremental() for batch processing.
        """
        # For single event indexing, we need to load the event from database
        # This is a simplified implementation for the interface compliance
        start_time = datetime.now(timezone.utc)
        
        try:
            # Get the specific audit event
            query = select(GovernanceAuditEvent).where(
                GovernanceAuditEvent.id == source_id
            )
            result = await self.db_session.execute(query)
            event = result.scalar_one_or_none()
            
            if not event:
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id=source_id,
                    start_time=start_time,
                    success=True,
                    chunks_processed=0,
                    chunks_indexed=0,
                    metadata={"message": "Audit event not found"},
                )
            
            # Convert to audit event document
            audit_doc = self._convert_event_to_doc(event)
            
            # Index the document
            result = await self.index_audit_events(tenant_id, [audit_doc])
            return result
            
        except Exception as e:
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=source_id,
                start_time=start_time,
                success=False,
                error_message=str(e),
            )

    async def index_full(
        self,
        tenant_id: str,
        force_reindex: bool = False,
    ) -> list[IndexingResult]:
        """
        Perform full indexing of all audit events for tenant.
        """
        # Full indexing delegates to index_audit_events_incremental
        result = await self.index_audit_events_incremental(tenant_id)
        return [result]

    async def index_audit_events_incremental(self, tenant_id: Optional[str] = None) -> IndexingResult:
        """
        Incrementally index new audit events since last watermark.
        
        Args:
            tenant_id: Tenant ID for scoping (None for global events only)
            
        Returns:
            IndexingResult with processing statistics
        """
        logger.info(f"Starting incremental audit events indexing for tenant: {tenant_id}")
        start_time = datetime.now(timezone.utc)

        try:
            # Get watermark for incremental indexing
            watermark = await self._get_indexing_watermark(tenant_id)
            logger.info(f"Retrieved watermark for tenant {tenant_id}: {watermark}")

            # Get new audit events since watermark
            audit_events = await self._get_new_audit_events(tenant_id, watermark)
            
            if not audit_events:
                logger.info(f"No new audit events found for tenant {tenant_id}")
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id=f"audit-events-incremental-{tenant_id or 'global'}",
                    start_time=start_time,
                    success=True,
                    chunks_processed=0,
                    chunks_indexed=0,
                    metadata={"audit_events_count": 0, "watermark": watermark},
                )

            # Convert to document format
            audit_docs = [self._convert_audit_event_to_doc(event) for event in audit_events]
            
            # Index the documents
            result = await self.index_audit_events(tenant_id, audit_docs)
            
            # Update watermark with latest event timestamp
            if audit_events:
                latest_timestamp = max(event.created_at for event in audit_events)
                await self._update_indexing_watermark(tenant_id, latest_timestamp)
                logger.info(f"Updated watermark for tenant {tenant_id} to {latest_timestamp}")
            
            return result
            
        except (ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Audit events incremental indexing failed for tenant {tenant_id}: {str(e)}")
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"audit-events-incremental-{tenant_id or 'global'}",
                start_time=start_time,
                success=False,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )

    async def index_audit_events(
        self,
        tenant_id: Optional[str],
        audit_events: List[AuditEventDoc],
    ) -> IndexingResult:
        """
        Index a list of audit event documents.

        Args:
            tenant_id: Tenant ID for isolation (None for global events)
            audit_events: List of audit event docs to index

        Returns:
            IndexingResult with processing statistics
        """
        logger.info(f"Indexing {len(audit_events)} audit events for tenant {tenant_id}")
        start_time = datetime.now(timezone.utc)

        if not audit_events:
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"audit-events-batch-{tenant_id or 'global'}",
                start_time=start_time,
                success=True,
                chunks_processed=0,
                chunks_indexed=0,
                metadata={"total_events": 0},
            )

        try:
            all_chunks = []
            processed_count = 0

            # Process each audit event
            for event_doc in audit_events:
                try:
                    # Convert to source document
                    source_doc = event_doc.to_source_document()

                    # Chunk the document
                    chunks = self.chunking_service.chunk_document(source_doc)

                    if not chunks:
                        logger.warning(f"No chunks generated for audit event {event_doc.event_id} (tenant: {tenant_id})")
                        continue

                    all_chunks.extend(chunks)
                    processed_count += len(chunks)

                except (IndexingError, ValueError, TypeError, RuntimeError) as e:
                    logger.error(f"Failed to process audit event {event_doc.event_id}: {str(e)}")
                    continue

            # Batch index all chunks
            if all_chunks:
                indexed_count = await self.document_repository.upsert_documents_batch(
                    tenant_id=tenant_id,
                    chunks=all_chunks,
                )
            else:
                indexed_count = 0

            end_time = datetime.now(timezone.utc)
            processing_time = (end_time - start_time).total_seconds()

            logger.info(
                f"Audit events indexing completed: "
                f"{processed_count} chunks processed, {indexed_count} indexed, "
                f"{processing_time:.2f}s"
            )

            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"audit-events-batch-{tenant_id or 'global'}",
                start_time=start_time,
                end_time=end_time,
                success=True,
                chunks_processed=processed_count,
                chunks_indexed=indexed_count,
                metadata={
                    "total_events": len(audit_events),
                    "processing_time_seconds": processing_time,
                },
            )

        except (IndexingError, ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Audit events indexing failed for tenant {tenant_id}: {str(e)}")
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id=f"audit-events-batch-{tenant_id or 'global'}",
                start_time=start_time,
                success=False,
                error_message=str(e),
                error_details={"exception_type": type(e).__name__},
            )

    async def _get_new_audit_events(
        self, 
        tenant_id: Optional[str], 
        watermark: Optional[datetime]
    ) -> List[GovernanceAuditEvent]:
        """Get new audit events since watermark for tenant."""
        try:
            query = select(GovernanceAuditEvent).order_by(GovernanceAuditEvent.created_at.asc())
            
            # Apply tenant filtering
            if tenant_id is not None:
                # For specific tenant, get only their events
                query = query.where(GovernanceAuditEvent.tenant_id == tenant_id)
            else:
                # For global indexing, get only truly global events (tenant_id is NULL)
                query = query.where(GovernanceAuditEvent.tenant_id.is_(None))
            
            # Apply watermark filtering
            if watermark:
                query = query.where(GovernanceAuditEvent.created_at > watermark)
            
            # Limit to reasonable batch size
            query = query.limit(1000)
            
            result = await self.db_session.execute(query)
            return result.scalars().all()
            
        except Exception as e:
            logger.error(f"Failed to fetch audit events for tenant {tenant_id}: {str(e)}")
            raise RuntimeError(f"Database query failed: {str(e)}")

    def _convert_audit_event_to_doc(self, event: GovernanceAuditEvent) -> AuditEventDoc:
        """Convert GovernanceAuditEvent to AuditEventDoc."""
        return AuditEventDoc(
            event_id=str(event.id),
            tenant_id=event.tenant_id,
            event_type=event.event_type,
            entity_type=event.entity_type,
            entity_id=event.entity_id,
            action=event.action,
            actor_id=event.actor_id,
            actor_role=event.actor_role,
            diff_summary=event.diff_summary,
            correlation_id=event.correlation_id,
            created_at=event.created_at,
            metadata={
                "domain": event.domain,
                "entity_version": event.entity_version,
                "request_id": event.request_id,
                "related_exception_id": event.related_exception_id,
                "related_change_request_id": event.related_change_request_id,
                "ip_address": event.ip_address,
                "user_agent": event.user_agent,
            } if any([
                event.domain, event.entity_version, event.request_id, 
                event.related_exception_id, event.related_change_request_id,
                event.ip_address, event.user_agent
            ]) else None,
        )

    async def _get_indexing_watermark(self, tenant_id: Optional[str]) -> Optional[datetime]:
        """Get last indexing watermark for tenant/global events."""
        try:
            # Use tenant_id or 'GLOBAL' for key
            watermark_key = tenant_id or "GLOBAL"
            
            query = select(IndexingState.last_indexed_at).where(
                and_(
                    IndexingState.tenant_id == watermark_key,
                    IndexingState.source_type == CopilotDocumentSourceType.AUDIT_EVENT
                )
            )
            
            result = await self.db_session.execute(query)
            watermark = result.scalar_one_or_none()
            
            return watermark
            
        except Exception as e:
            logger.error(f"Failed to get indexing watermark for tenant {tenant_id}: {str(e)}")
            return None

    async def _update_indexing_watermark(self, tenant_id: Optional[str], timestamp: datetime):
        """Update last indexing watermark for tenant/global events."""
        try:
            # Use tenant_id or 'GLOBAL' for key
            watermark_key = tenant_id or "GLOBAL"
            
            # Create or update watermark
            from sqlalchemy.dialects.postgresql import insert
            
            stmt = insert(IndexingState).values(
                tenant_id=watermark_key,
                source_type=CopilotDocumentSourceType.AUDIT_EVENT,
                last_indexed_at=timestamp,
            )
            
            stmt = stmt.on_conflict_do_update(
                index_elements=["tenant_id", "source_type"],
                set_={"last_indexed_at": stmt.excluded.last_indexed_at}
            )
            
            await self.db_session.execute(stmt)
            await self.db_session.commit()
            
        except Exception as e:
            logger.error(f"Failed to update indexing watermark for tenant {tenant_id}: {str(e)}")
            await self.db_session.rollback()
            raise RuntimeError(f"Watermark update failed: {str(e)}")

    def supports_tenant(self, tenant_id: Optional[str]) -> bool:
        """
        Check if the indexer supports a given tenant.
        
        Args:
            tenant_id: Tenant ID to check (None for global)
            
        Returns:
            True if tenant is supported
        """
        # Support all valid tenant IDs and global events (None)
        if tenant_id is None:
            return True
        
        return validate_tenant_id(tenant_id)