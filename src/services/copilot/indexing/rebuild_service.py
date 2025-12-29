"""Index rebuild service for managing Copilot document indexing operations.

Handles orchestration of index rebuild jobs with job tracking, progress monitoring,
and execution of multiple indexer types (policy_doc, resolved_exception, audit_event, tool_registry).

Phase 13 Prompt 2.5 - IndexRebuildService implementation.
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    CopilotDocumentSourceType,
    CopilotIndexJob,
    CopilotIndexJobStatus,
)
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.services.copilot.chunking_service import DocumentChunkingService
from src.services.copilot.embedding_service import EmbeddingService
from src.services.copilot.indexing.audit_events_indexer import AuditEventsIndexer
from src.services.copilot.indexing.policy_docs_indexer import PolicyDocsIndexer
from src.services.copilot.indexing.resolved_exceptions_indexer import ResolvedExceptionsIndexer
from src.services.copilot.indexing.tool_registry_indexer import ToolRegistryIndexer

logger = logging.getLogger(__name__)


class IndexRebuildError(Exception):
    """Exception raised during index rebuild operations."""
    pass


class IndexRebuildService:
    """
    Service for managing copilot index rebuild operations.
    
    Provides job tracking, progress monitoring, and orchestration of multiple
    indexer types for comprehensive document indexing operations.
    """
    
    def __init__(
        self,
        db_session: AsyncSession,
        embedding_service: EmbeddingService,
        chunking_service: DocumentChunkingService,
        document_repository: CopilotDocumentRepository,
    ):
        """
        Initialize the rebuild service.
        
        Args:
            db_session: Database session for job tracking
            embedding_service: Service for creating document embeddings
            chunking_service: Service for document chunking
            document_repository: Repository for copilot documents
        """
        self.db_session = db_session
        self.embedding_service = embedding_service
        self.chunking_service = chunking_service
        self.document_repository = document_repository
        
        # Initialize all indexers
        self._indexers = {
            CopilotDocumentSourceType.POLICY_DOC: PolicyDocsIndexer(
                document_repository, embedding_service, chunking_service
            ),
            CopilotDocumentSourceType.RESOLVED_EXCEPTION: ResolvedExceptionsIndexer(
                db_session, embedding_service, chunking_service, document_repository
            ),
            CopilotDocumentSourceType.AUDIT_EVENT: AuditEventsIndexer(
                db_session, embedding_service, chunking_service, document_repository
            ),
            CopilotDocumentSourceType.TOOL_REGISTRY: ToolRegistryIndexer(
                db_session, embedding_service, chunking_service, document_repository
            ),
        }
    
    async def start_rebuild(
        self,
        tenant_id: Optional[str],
        sources: List[str],
        full_rebuild: bool = False,
    ) -> str:
        """
        Start a new index rebuild job.
        
        Args:
            tenant_id: Tenant to rebuild for (None for global rebuild)
            sources: List of source types to rebuild
            full_rebuild: Whether to do full or incremental rebuild
            
        Returns:
            Job ID for tracking progress
            
        Raises:
            IndexRebuildError: If job creation fails
        """
        logger.info(f"Starting index rebuild: tenant={tenant_id}, sources={sources}, full={full_rebuild}")
        
        # Validate source types
        valid_sources = {s.value for s in CopilotDocumentSourceType}
        invalid_sources = set(sources) - valid_sources
        if invalid_sources:
            raise IndexRebuildError(f"Invalid source types: {invalid_sources}. Valid sources: {valid_sources}")
        
        try:
            # Create job record
            job = CopilotIndexJob(
                id=uuid4(),
                tenant_id=tenant_id,
                sources=sources,
                full_rebuild=full_rebuild,
                status=CopilotIndexJobStatus.PENDING,
                progress_current=0,
                documents_processed=0,
                documents_failed=0,
                chunks_indexed=0,
            )
            
            self.db_session.add(job)
            await self.db_session.commit()
            
            job_id = str(job.id)
            
            # Start background processing (fire and forget)
            asyncio.create_task(self._run_rebuild_job(job_id))
            
            logger.info(f"Index rebuild job created: {job_id}")
            return job_id
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to create index rebuild job: {str(e)}")
            raise IndexRebuildError(f"Failed to create rebuild job: {str(e)}") from e

    async def get_status(self, job_id: str) -> Dict[str, Any]:
        """
        Get status and progress of a rebuild job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            Dictionary with job status information:
            {
                "state": "running",
                "progress": {"current": 50, "total": 100},
                "counts": {"processed": 45, "failed": 5, "chunks_indexed": 230},
                "last_error": "Error message if any",
                "created_at": "2024-01-15T10:30:00Z",
                "started_at": "2024-01-15T10:30:01Z",
                "completed_at": null
            }
            
        Raises:
            IndexRebuildError: If job not found
        """
        try:
            query = select(CopilotIndexJob).where(CopilotIndexJob.id == job_id)
            result = await self.db_session.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                raise IndexRebuildError(f"Job not found: {job_id}")
            
            return {
                "id": str(job.id),
                "tenant_id": job.tenant_id,
                "sources": job.sources,
                "full_rebuild": job.full_rebuild,
                "state": job.status.value,
                "progress": {
                    "current": job.progress_current,
                    "total": job.progress_total,
                    "percentage": (
                        round(100.0 * job.progress_current / job.progress_total, 1)
                        if job.progress_total and job.progress_total > 0
                        else None
                    ),
                },
                "counts": {
                    "documents_processed": job.documents_processed,
                    "documents_failed": job.documents_failed,
                    "chunks_indexed": job.chunks_indexed,
                },
                "last_error": job.error_message,
                "error_details": job.error_details,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "started_at": job.started_at.isoformat() if job.started_at else None,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            }
            
        except IndexRebuildError:
            raise
        except Exception as e:
            logger.error(f"Failed to get job status: {str(e)}")
            raise IndexRebuildError(f"Failed to get status for job {job_id}: {str(e)}") from e

    async def cancel_job(self, job_id: str) -> bool:
        """
        Cancel a running or pending rebuild job.
        
        Args:
            job_id: Job identifier
            
        Returns:
            True if job was cancelled, False if job was not cancellable
            
        Raises:
            IndexRebuildError: If job not found
        """
        try:
            query = select(CopilotIndexJob).where(CopilotIndexJob.id == job_id)
            result = await self.db_session.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                raise IndexRebuildError(f"Job not found: {job_id}")
            
            if job.status in (CopilotIndexJobStatus.COMPLETED, CopilotIndexJobStatus.FAILED, CopilotIndexJobStatus.CANCELLED):
                return False  # Job already finished
            
            # Update job status to cancelled
            await self.db_session.execute(
                update(CopilotIndexJob)
                .where(CopilotIndexJob.id == job_id)
                .values(
                    status=CopilotIndexJobStatus.CANCELLED,
                    completed_at=datetime.now(timezone.utc),
                    error_message="Job cancelled by user",
                )
            )
            await self.db_session.commit()
            
            logger.info(f"Index rebuild job cancelled: {job_id}")
            return True
            
        except IndexRebuildError:
            raise
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to cancel job: {str(e)}")
            raise IndexRebuildError(f"Failed to cancel job {job_id}: {str(e)}") from e

    async def _run_rebuild_job(self, job_id: str) -> None:
        """
        Run the actual rebuild job in the background.
        
        This method runs the indexing operations and updates job progress.
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Mark job as running
            await self._update_job_status(
                job_id,
                CopilotIndexJobStatus.RUNNING,
                started_at=start_time,
            )
            
            # Get job details
            query = select(CopilotIndexJob).where(CopilotIndexJob.id == job_id)
            result = await self.db_session.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                logger.error(f"Job not found during execution: {job_id}")
                return
            
            logger.info(f"Running rebuild job {job_id}: tenant={job.tenant_id}, sources={job.sources}")
            
            total_processed = 0
            total_failed = 0
            total_chunks = 0
            
            # Process each source type
            for i, source_type_str in enumerate(job.sources):
                try:
                    # Check if job was cancelled
                    if await self._is_job_cancelled(job_id):
                        logger.info(f"Job {job_id} was cancelled, stopping execution")
                        return
                    
                    source_type = CopilotDocumentSourceType(source_type_str)
                    indexer = self._indexers.get(source_type)
                    
                    if not indexer:
                        logger.error(f"No indexer found for source type: {source_type_str}")
                        total_failed += 1
                        continue
                    
                    logger.info(f"Processing source {source_type_str} for job {job_id}")
                    
                    # Update progress
                    await self._update_job_progress(
                        job_id,
                        current=i,
                        total=len(job.sources),
                        processed=total_processed,
                        failed=total_failed,
                        chunks=total_chunks,
                    )
                    
                    # Run indexing based on type
                    if job.full_rebuild:
                        if job.tenant_id:
                            # Tenant-specific full rebuild
                            if hasattr(indexer, 'index_for_tenant'):
                                result = await indexer.index_for_tenant(job.tenant_id)
                                results = [result] if result else []
                            else:
                                results = []
                        else:
                            # Global full rebuild
                            if hasattr(indexer, 'index_all'):
                                result = await indexer.index_all()
                                results = [result] if result else []
                            else:
                                results = []
                    else:
                        # Incremental rebuild
                        if job.tenant_id:
                            # Tenant-specific incremental rebuild
                            if hasattr(indexer, 'index_incremental_for_tenant'):
                                result = await indexer.index_incremental_for_tenant(job.tenant_id)
                                results = [result] if result else []
                            else:
                                results = []
                        else:
                            # Global incremental rebuild
                            if hasattr(indexer, 'index_incremental_all'):
                                result = await indexer.index_incremental_all()
                                results = [result] if result else []
                            else:
                                results = []
                    
                    # Aggregate results
                    for result in results:
                        if hasattr(result, 'success') and result.success:
                            total_processed += 1
                            if hasattr(result, 'chunks_indexed'):
                                total_chunks += result.chunks_indexed
                        else:
                            total_failed += 1
                    
                    logger.info(f"Completed {source_type_str} for job {job_id}: {len(results)} operations")
                    
                except Exception as e:
                    logger.error(f"Failed to process source {source_type_str} for job {job_id}: {str(e)}")
                    total_failed += 1
                    continue
            
            # Mark job as completed
            await self._update_job_status(
                job_id,
                CopilotIndexJobStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
                progress_current=len(job.sources),
                progress_total=len(job.sources),
                documents_processed=total_processed,
                documents_failed=total_failed,
                chunks_indexed=total_chunks,
            )
            
            logger.info(
                f"Rebuild job {job_id} completed: {total_processed} processed, "
                f"{total_failed} failed, {total_chunks} chunks indexed"
            )
            
        except Exception as e:
            logger.error(f"Rebuild job {job_id} failed: {str(e)}")
            
            # Mark job as failed
            await self._update_job_status(
                job_id,
                CopilotIndexJobStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error_message=str(e),
                error_details={"exception_type": type(e).__name__, "details": str(e)},
            )

    async def _update_job_status(
        self,
        job_id: str,
        status: CopilotIndexJobStatus,
        **kwargs,
    ) -> None:
        """Update job status and other fields."""
        try:
            update_values = {"status": status}
            update_values.update(kwargs)
            
            await self.db_session.execute(
                update(CopilotIndexJob)
                .where(CopilotIndexJob.id == job_id)
                .values(**update_values)
            )
            await self.db_session.commit()
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update job status: {str(e)}")

    async def _update_job_progress(
        self,
        job_id: str,
        current: int,
        total: Optional[int] = None,
        processed: int = 0,
        failed: int = 0,
        chunks: int = 0,
    ) -> None:
        """Update job progress counters."""
        try:
            update_values = {
                "progress_current": current,
                "documents_processed": processed,
                "documents_failed": failed,
                "chunks_indexed": chunks,
            }
            
            if total is not None:
                update_values["progress_total"] = total
            
            await self.db_session.execute(
                update(CopilotIndexJob)
                .where(CopilotIndexJob.id == job_id)
                .values(**update_values)
            )
            await self.db_session.commit()
            
        except Exception as e:
            await self.db_session.rollback()
            logger.error(f"Failed to update job progress: {str(e)}")

    async def _is_job_cancelled(self, job_id: str) -> bool:
        """Check if job was cancelled."""
        try:
            query = select(CopilotIndexJob.status).where(CopilotIndexJob.id == job_id)
            result = await self.db_session.execute(query)
            status = result.scalar_one_or_none()
            
            return status == CopilotIndexJobStatus.CANCELLED
            
        except Exception:
            # If we can't check, assume not cancelled
            return False