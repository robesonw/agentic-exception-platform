"""
ResolvedExceptionsIndexer for Phase 13 Copilot Intelligence.

Indexes resolved/closed exceptions with resolution notes for Similar Cases RAG retrieval.
Supports incremental indexing via watermark tracking.

Cross-reference:
- docs/phase13-copilot-intelligence-mvp.md (ResolvedExceptions indexing)
- tasks: P13-5 (ResolvedExceptionsIndexer)
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    Exception,
    ExceptionEvent,
    ExceptionStatus,
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
class ResolvedExceptionDoc:
    """
    Resolved exception document for indexing.
    
    Contains exception details and resolution information for RAG retrieval.
    """
    exception_id: str
    tenant_id: str
    domain: str
    type: str
    severity: str
    source_system: str
    entity: Optional[str]
    amount: Optional[float]
    owner: Optional[str]
    resolution_summary: str
    resolution_details: str
    status: str
    closed_at: datetime
    metadata: Optional[dict] = None

    def to_source_document(self) -> SourceDocument:
        """Convert to SourceDocument for processing."""
        # Combine exception context with resolution information
        content = f"""Exception Details:
- ID: {self.exception_id}
- Type: {self.type}
- Domain: {self.domain}
- Severity: {self.severity}
- Source System: {self.source_system}
- Entity: {self.entity or 'N/A'}
- Amount: {self.amount or 'N/A'}
- Owner: {self.owner or 'N/A'}

Resolution:
{self.resolution_summary}

Resolution Details:
{self.resolution_details}

Status: {self.status}
Closed: {self.closed_at.isoformat()}
"""

        metadata = {
            "exception_id": self.exception_id,
            "tenant_id": self.tenant_id,
            "domain": self.domain,
            "type": self.type,
            "severity": self.severity,
            "source_system": self.source_system,
            "entity": self.entity,
            "amount": str(self.amount) if self.amount else None,
            "owner": self.owner,
            "status": self.status,
            "closed_at": self.closed_at.isoformat(),
            "resolution_summary": self.resolution_summary,
            **(self.metadata or {}),
        }

        return SourceDocument(
            source_id=self.exception_id,
            source_type=CopilotDocumentSourceType.RESOLVED_EXCEPTION,
            content=content,
            metadata=metadata,
        )


class ResolvedExceptionsIndexer(BaseIndexer):
    """
    Indexer for resolved exceptions with resolution information.
    
    Pulls resolved exceptions that include resolution notes/outcomes,
    chunks them using the exception converter, and stores in vector DB
    for Similar Cases RAG retrieval.
    """

    def __init__(
        self,
        db_session: AsyncSession,
        embedding_service: EmbeddingService,
        chunking_service: DocumentChunkingService,
        document_repository: CopilotDocumentRepository,
    ):
        super().__init__(embedding_service, chunking_service, document_repository)
        self.db_session = db_session

    @property
    def source_type(self) -> CopilotDocumentSourceType:
        """Source type for resolved exceptions."""
        return CopilotDocumentSourceType.RESOLVED_EXCEPTION

    def supports_tenant(self, tenant_id: Optional[str]) -> bool:
        """Check if tenant ID is valid for indexing."""
        return validate_tenant_id(tenant_id)

    async def index_incremental(self, tenant_id: str, force_rebuild: bool = False) -> IndexingResult:
        """
        Index resolved exceptions incrementally from last watermark.
        
        Args:
            tenant_id: Tenant to index for
            force_rebuild: If True, ignore watermark and reindex all
            
        Returns:
            IndexingResult with processing stats
        """
        logger.info(f"Starting incremental resolved exceptions indexing for tenant {tenant_id}")
        start_time = datetime.now(timezone.utc)

        if not self.supports_tenant(tenant_id):
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="resolved-exceptions-incremental",
                success=False,
                error_message="Tenant ID is required",
                start_time=start_time,
            )

        try:
            # Get last indexed watermark
            last_indexed_at = None
            if not force_rebuild:
                last_indexed_at = await self._get_last_indexed_watermark(tenant_id)

            # Get resolved exceptions since watermark
            resolved_exceptions = await self._get_resolved_exceptions_since(tenant_id, last_indexed_at)
            
            if not resolved_exceptions:
                logger.info(f"No new resolved exceptions found for tenant {tenant_id}")
                return self._create_indexing_result(
                    tenant_id=tenant_id,
                    source_id="resolved-exceptions-incremental",
                    start_time=start_time,
                    success=True,
                    chunks_processed=0,
                    chunks_indexed=0,
                )

            # Process the exceptions
            result = await self.index_resolved_exceptions(
                tenant_id=tenant_id,
                resolved_exceptions=resolved_exceptions,
            )

            # Update watermark on success
            if result.success and resolved_exceptions:
                latest_update = max(exc.closed_at for exc in resolved_exceptions)
                await self._update_indexing_watermark(tenant_id, latest_update)

            return result

        except (IndexingError, ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Resolved exceptions incremental indexing failed: {str(e)}", exc_info=True)
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="resolved-exceptions-incremental",
                success=False,
                error_message=f"Incremental indexing failed: {str(e)}",
                start_time=start_time,
            )

    async def index_full(self, tenant_id: str) -> IndexingResult:
        """
        Index all resolved exceptions for a tenant.
        
        This is a placeholder for full discovery implementation.
        """
        logger.info(f"Starting full resolved exceptions indexing for tenant {tenant_id}")
        # Force rebuild all resolved exceptions
        return await self.index_incremental(tenant_id=tenant_id, force_rebuild=True)

    async def index_resolved_exceptions(
        self,
        tenant_id: str,
        resolved_exceptions: List[ResolvedExceptionDoc],
    ) -> IndexingResult:
        """
        Index a list of resolved exception documents.
        
        Args:
            tenant_id: Tenant ID for isolation
            resolved_exceptions: List of resolved exception docs to index
            
        Returns:
            IndexingResult with processing statistics
        """
        logger.info(f"Indexing {len(resolved_exceptions)} resolved exceptions for tenant {tenant_id}")
        start_time = datetime.now(timezone.utc)

        if not self.supports_tenant(tenant_id):
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="resolved-exceptions-batch",
                success=False,
                error_message="Tenant ID is required",
                start_time=start_time,
            )

        if not resolved_exceptions:
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="bulk-resolved-exceptions",
                start_time=start_time,
                success=True,
                chunks_processed=0,
                chunks_indexed=0,
                metadata={"total_exceptions": 0},
            )

        try:
            all_chunks = []
            processed_count = 0
            
            # Process each exception
            for exception_doc in resolved_exceptions:
                try:
                    # Convert to source document
                    source_doc = exception_doc.to_source_document()
                    
                    # Chunk the document
                    chunks = self.chunking_service.chunk_document(source_doc)

                    if not chunks:
                        logger.warning(f"No chunks generated for resolved exception {exception_doc.exception_id} (tenant: {tenant_id})")
                        continue
                    
                    all_chunks.extend(chunks)
                    processed_count += len(chunks)
                    
                except (IndexingError, ValueError, TypeError, RuntimeError) as e:
                    logger.error(f"Failed to process resolved exception {exception_doc.exception_id}: {str(e)}")
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
                f"Resolved exceptions indexing completed: "
                f"{processed_count} chunks processed, {indexed_count} indexed, "
                f"{processing_time:.2f}s"
            )

            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="bulk-resolved-exceptions",
                start_time=start_time,
                end_time=end_time,
                success=True,
                chunks_processed=processed_count,
                chunks_indexed=indexed_count,
                metadata={
                    "total_exceptions": len(resolved_exceptions),
                    "processing_time_seconds": processing_time,
                },
            )

        except (IndexingError, ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Resolved exceptions indexing failed: {str(e)}", exc_info=True)
            return self._create_indexing_result(
                tenant_id=tenant_id,
                source_id="resolved-exceptions-batch",
                success=False,
                error_message=f"Resolved exceptions indexing failed: {str(e)}",
                start_time=start_time,
            )

    async def remove_document(self, tenant_id: str, source_id: str) -> bool:
        """
        Remove a resolved exception document from the index.
        
        Args:
            tenant_id: Tenant ID for isolation
            source_id: Exception ID to remove
            
        Returns:
            True if removed, False if not found
        """
        try:
            removed_count = await self.document_repository.delete_by_source(
                tenant_id=tenant_id,
                source_type=self.source_type,
                source_id=source_id,
            )
            return removed_count > 0
        except (IndexingError, ValueError, TypeError, RuntimeError) as e:
            logger.error(f"Failed to remove resolved exception {source_id}: {str(e)}")
            return False

    async def _get_resolved_exceptions_since(
        self,
        tenant_id: str,
        since: Optional[datetime] = None,
    ) -> List[ResolvedExceptionDoc]:
        """
        Get resolved exceptions with resolution information since a timestamp.
        
        Args:
            tenant_id: Tenant ID for isolation
            since: Timestamp to filter from (None = all time)
            
        Returns:
            List of resolved exception documents with resolution info
        """
        try:
            # Query resolved exceptions
            query = select(Exception).where(
                and_(
                    Exception.tenant_id == tenant_id,
                    Exception.status == ExceptionStatus.RESOLVED,
                )
            )
            
            if since:
                query = query.where(Exception.updated_at > since)
                
            query = query.order_by(Exception.updated_at)
            result = await self.db_session.execute(query)
            exceptions = result.scalars().all()

            if not exceptions:
                return []

            # For each resolved exception, get resolution events
            resolved_docs = []
            for exception in exceptions:
                resolution_info = await self._get_resolution_info(exception.exception_id, tenant_id)
                
                if not resolution_info:
                    logger.warning(f"No resolution info found for resolved exception {exception.exception_id}")
                    continue

                resolved_doc = ResolvedExceptionDoc(
                    exception_id=exception.exception_id,
                    tenant_id=exception.tenant_id,
                    domain=exception.domain,
                    type=exception.type,
                    severity=exception.severity.value,
                    source_system=exception.source_system,
                    entity=exception.entity,
                    amount=float(exception.amount) if exception.amount else None,
                    owner=exception.owner,
                    resolution_summary=resolution_info["summary"],
                    resolution_details=resolution_info["details"],
                    status=exception.status.value,
                    closed_at=resolution_info["closed_at"],
                    metadata={
                        "sla_deadline": exception.sla_deadline.isoformat() if exception.sla_deadline else None,
                        "current_playbook_id": exception.current_playbook_id,
                        "current_step": exception.current_step,
                    },
                )
                resolved_docs.append(resolved_doc)

            logger.info(f"Found {len(resolved_docs)} resolved exceptions with resolution info for tenant {tenant_id}")
            return resolved_docs

        except (ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to get resolved exceptions: {str(e)}", exc_info=True)
            raise

    async def _get_resolution_info(
        self,
        exception_id: str,
        tenant_id: str,
    ) -> Optional[dict]:
        """
        Get resolution information from exception events.
        
        Looks for resolution-related events in the exception_event table
        and extracts resolution summary, details, and timestamp.
        
        Args:
            exception_id: Exception ID
            tenant_id: Tenant ID for isolation
            
        Returns:
            Dict with resolution info or None if not found
        """
        try:
            # Look for resolution events
            query = select(ExceptionEvent).where(
                and_(
                    ExceptionEvent.exception_id == exception_id,
                    ExceptionEvent.tenant_id == tenant_id,
                    ExceptionEvent.event_type.in_([
                        "ExceptionResolved",
                        "ExceptionClosed",
                        "ResolutionCompleted",
                        "FinalResolution",
                    ])
                )
            ).order_by(ExceptionEvent.created_at.desc())

            result = await self.db_session.execute(query)
            resolution_event = result.scalars().first()

            if not resolution_event:
                # Fallback: look for any event with resolution in the name or payload
                query = select(ExceptionEvent).where(
                    and_(
                        ExceptionEvent.exception_id == exception_id,
                        ExceptionEvent.tenant_id == tenant_id,
                    )
                ).order_by(ExceptionEvent.created_at.desc())

                result = await self.db_session.execute(query)
                events = result.scalars().all()

                for event in events:
                    if ("resolution" in event.event_type.lower() or
                        (event.payload and 
                         any(key.lower().find("resolution") != -1 for key in event.payload.keys()))):
                        resolution_event = event
                        break

            if not resolution_event:
                return None

            # Extract resolution information from payload
            payload = resolution_event.payload or {}
            
            # Try to extract resolution summary and details
            summary = (
                payload.get("resolution_summary") or
                payload.get("summary") or
                payload.get("outcome") or
                f"Resolved via {resolution_event.event_type}"
            )
            
            details = (
                payload.get("resolution_details") or
                payload.get("details") or
                payload.get("description") or
                payload.get("notes") or
                f"Event: {resolution_event.event_type}, Actor: {resolution_event.actor_id}"
            )

            return {
                "summary": str(summary),
                "details": str(details),
                "closed_at": resolution_event.created_at,
            }

        except (ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to get resolution info for {exception_id}: {str(e)}")
            return None

    async def _get_last_indexed_watermark(self, tenant_id: str) -> Optional[datetime]:
        """Get the last indexed watermark for this tenant and source type."""
        try:
            query = select(IndexingState).where(
                and_(
                    IndexingState.tenant_id == tenant_id,
                    IndexingState.source_type == self.source_type,
                )
            )
            result = await self.db_session.execute(query)
            state = result.scalars().first()
            
            return state.last_indexed_at if state else None
        except (ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to get indexing watermark: {str(e)}")
            return None

    async def _update_indexing_watermark(self, tenant_id: str, timestamp: datetime) -> None:
        """Update the last indexed watermark for this tenant and source type."""
        try:
            # Try to update existing state
            query = select(IndexingState).where(
                and_(
                    IndexingState.tenant_id == tenant_id,
                    IndexingState.source_type == self.source_type,
                )
            )
            result = await self.db_session.execute(query)
            state = result.scalars().first()

            if state:
                state.last_indexed_at = timestamp
                state.updated_at = datetime.now(timezone.utc)
            else:
                # Create new state
                state = IndexingState(
                    tenant_id=tenant_id,
                    source_type=self.source_type,
                    last_indexed_at=timestamp,
                )
                self.db_session.add(state)

            await self.db_session.commit()
            logger.info(f"Updated indexing watermark for {tenant_id}:{self.source_type.value} to {timestamp}")

        except (ValueError, TypeError, RuntimeError, AttributeError) as e:
            logger.error(f"Failed to update indexing watermark: {str(e)}")
            await self.db_session.rollback()
            raise