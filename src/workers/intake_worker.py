"""
IntakeWorker for Phase 9.

Subscribes to ExceptionIngested events, normalizes exceptions using IntakeAgent,
persists them to the database, and emits ExceptionNormalized events.

Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2
"""

import asyncio
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import DBAPIError

from src.agents.intake import IntakeAgent
from src.audit.logger import AuditLogger
from src.events.schema import CanonicalEvent
from src.events.types import ExceptionIngested, ExceptionNormalized
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord
from src.infrastructure.db.models import ExceptionSeverity, ExceptionStatus
from src.repository.dto import ExceptionCreateOrUpdateDTO
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.base import AgentWorker

logger = logging.getLogger(__name__)


class IntakeWorker(AgentWorker):
    """
    Worker that processes ExceptionIngested events and normalizes exceptions.
    
    Responsibilities:
    - Subscribe to ExceptionIngested events
    - Normalize raw exceptions using IntakeAgent
    - Persist normalized exceptions to database
    - Emit ExceptionNormalized events
    - Ensure idempotency (via base worker)
    - Enforce tenant isolation
    """
    
    def __init__(
        self,
        broker: Broker,
        topics: list[str],
        group_id: str,
        event_publisher: EventPublisherService,
        exception_repository: Optional[ExceptionRepository] = None,  # Optional - created per-operation
        domain_pack: Optional[DomainPack] = None,
        audit_logger: Optional[AuditLogger] = None,
        event_processing_repo: Optional[EventProcessingRepository] = None,
    ):
        """
        Initialize IntakeWorker.
        
        Args:
            broker: Message broker instance
            topics: List of topic names (should include "exceptions" or similar)
            group_id: Consumer group ID
            event_publisher: EventPublisherService for emitting events
            exception_repository: ExceptionRepository for persisting exceptions
            domain_pack: Optional Domain Pack for validation
            audit_logger: Optional AuditLogger for audit logging
            event_processing_repo: Optional EventProcessingRepository for idempotency
        """
        super().__init__(
            broker=broker,
            topics=topics,
            group_id=group_id,
            worker_name="IntakeWorker",
            event_processing_repo=event_processing_repo,
            concurrency=1,  # Default concurrency, can be overridden if needed
        )
        
        self.event_publisher = event_publisher
        self.exception_repository = exception_repository  # May be None - created per-operation
        self.domain_pack = domain_pack
        self.audit_logger = audit_logger
        
        # Initialize IntakeAgent
        self.intake_agent = IntakeAgent(
            domain_pack=domain_pack,
            audit_logger=audit_logger,
        )
        
        logger.info(
            f"Initialized IntakeWorker: topics={topics}, group_id={group_id}"
        )
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process ExceptionIngested event.
        
        Args:
            event: CanonicalEvent (should be ExceptionIngested)
            
        Raises:
            Exception: If normalization or persistence fails
            
        Note:
            Silently skips events that are not ExceptionIngested (e.g., ExceptionNormalized
            events emitted by this worker are ignored).
        """
        # Skip events that are not ExceptionIngested
        if event.event_type != "ExceptionIngested":
            logger.debug(
                f"IntakeWorker skipping event {event.event_id} of type {event.event_type} "
                f"(only processes ExceptionIngested events)"
            )
            return
        
        # Cast to ExceptionIngested for type safety
        ingested_event = ExceptionIngested.model_validate(event.model_dump())
        
        tenant_id = ingested_event.tenant_id
        payload = ingested_event.payload
        raw_payload = payload.get("raw_payload", {})
        source_system = payload.get("source_system", "UNKNOWN")
        ingestion_method = payload.get("ingestion_method", "api")
        
        logger.info(
            f"IntakeWorker processing ExceptionIngested: "
            f"tenant_id={tenant_id}, exception_id={ingested_event.exception_id}, "
            f"source_system={source_system}"
        )
        
        # Normalize exception using IntakeAgent
        try:
            normalized, decision = await self.intake_agent.process(
                raw_exception=raw_payload,
                tenant_id=tenant_id,
            )
        except Exception as e:
            logger.error(
                f"IntakeWorker failed to normalize exception: {e}",
                exc_info=True,
            )
            raise
        
        # Phase 9 P9-24: Store PII redaction metadata if available
        redaction_metadata = None
        if ingested_event.metadata and "redaction_metadata" in ingested_event.metadata:
            redaction_metadata = ingested_event.metadata["redaction_metadata"]
        
        # Persist normalized exception to database (with retry logic for connection errors)
        try:
            await self._persist_exception_with_retry(normalized, redaction_metadata=redaction_metadata)
        except Exception as e:
            logger.error(
                f"IntakeWorker failed to persist exception {normalized.exception_id} after retries: {e}",
                exc_info=True,
            )
            raise
        
        # Emit ExceptionNormalized event
        try:
            await self._emit_normalized_event(
                normalized=normalized,
                correlation_id=ingested_event.correlation_id,
                metadata={
                    "ingestion_method": ingestion_method,
                    "source_system": source_system,
                    "decision": decision.model_dump() if decision else None,
                },
            )
        except Exception as e:
            logger.error(
                f"IntakeWorker failed to emit ExceptionNormalized event: {e}",
                exc_info=True,
            )
            raise
        
        logger.info(
            f"IntakeWorker completed processing: exception_id={normalized.exception_id}"
        )
    
    async def _persist_exception_with_retry(
        self,
        exception: ExceptionRecord,
        redaction_metadata: Optional[dict] = None,
        max_retries: int = 3,
        initial_delay: float = 0.5,
    ) -> None:
        """
        Persist normalized exception to database with retry logic for connection errors.
        
        Retries on database connection errors (e.g., ConnectionDoesNotExistError)
        with exponential backoff.
        
        Phase 9 P9-24: Optionally stores PII redaction metadata.
        
        Args:
            exception: Normalized ExceptionRecord
            redaction_metadata: Optional PII redaction metadata
            max_retries: Maximum number of retry attempts (default: 3)
            initial_delay: Initial delay in seconds before retry (default: 0.5)
        """
        delay = initial_delay
        last_error = None
        
        for attempt in range(max_retries):
            try:
                await self._persist_exception(exception, redaction_metadata=redaction_metadata)
                return  # Success - exit retry loop
            except (DBAPIError, ConnectionError, OSError) as e:
                last_error = e
                error_msg = str(e)
                
                # Check if it's a connection error that we should retry
                is_connection_error = (
                    "ConnectionDoesNotExistError" in error_msg or
                    "connection was closed" in error_msg.lower() or
                    "connection does not exist" in error_msg.lower() or
                    isinstance(e, ConnectionError)
                )
                
                if is_connection_error and attempt < max_retries - 1:
                    logger.warning(
                        f"Database connection error while persisting exception {exception.exception_id} "
                        f"(attempt {attempt + 1}/{max_retries}): {error_msg}. "
                        f"Retrying in {delay}s..."
                    )
                    await asyncio.sleep(delay)
                    delay *= 2  # Exponential backoff
                else:
                    # Not a retryable error or max retries reached
                    logger.error(
                        f"Failed to persist exception {exception.exception_id} "
                        f"(attempt {attempt + 1}/{max_retries}): {error_msg}",
                        exc_info=True,
                    )
                    raise
            except Exception as e:
                # Non-connection errors - don't retry
                logger.error(
                    f"Non-retryable error while persisting exception {exception.exception_id}: {e}",
                    exc_info=True,
                )
                raise
        
        # If we exhausted all retries, raise the last error
        if last_error:
            raise last_error
    
    async def _persist_exception(
        self,
        exception: ExceptionRecord,
        redaction_metadata: Optional[dict] = None,
    ) -> None:
        """
        Persist normalized exception to database.
        
        Phase 9 P9-24: Optionally stores PII redaction metadata.
        
        Args:
            exception: Normalized ExceptionRecord
            redaction_metadata: Optional PII redaction metadata
        """
        # Convert ExceptionRecord to DTO
        # Extract domain from normalized_context or use default
        domain = (
            str(exception.normalized_context.get("domain"))
            if exception.normalized_context and exception.normalized_context.get("domain")
            else "default"
        )
        
        # Map ExceptionRecord severity to ExceptionSeverity enum
        severity = ExceptionSeverity.MEDIUM  # Default
        if exception.severity:
            try:
                severity = ExceptionSeverity(exception.severity.value)
            except (ValueError, AttributeError):
                # Fallback to MEDIUM if severity doesn't match
                severity = ExceptionSeverity.MEDIUM
        
        # Map ExceptionRecord to ExceptionCreateOrUpdateDTO
        exception_dto = ExceptionCreateOrUpdateDTO(
            exception_id=exception.exception_id,
            tenant_id=exception.tenant_id,
            domain=str(domain) if domain else "default",
            type=str(exception.exception_type) if exception.exception_type else "Unknown",
            severity=severity,
            status=ExceptionStatus.OPEN,  # Default status
            source_system=str(exception.source_system) if exception.source_system else None,
            entity=None,  # Extract from normalized_context if available
            amount=None,  # Extract from normalized_context if available
            sla_deadline=None,  # Extract from normalized_context if available
            owner=None,
            current_playbook_id=None,
            current_step=None,
        )
        
        # Upsert exception (idempotent)
        # Create repository with session per-operation
        # Use a single session context to avoid asyncpg concurrency issues
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            # Persist exception
            exception_repository = ExceptionRepository(session=session)
            await exception_repository.upsert_exception(
                tenant_id=exception.tenant_id,
                exception_data=exception_dto,
            )
            
            # Phase 9 P9-24: Store PII redaction metadata if available (in same session)
            if redaction_metadata:
                try:
                    await self._store_redaction_metadata(
                        exception_id=exception.exception_id,
                        tenant_id=exception.tenant_id,
                        redaction_metadata=redaction_metadata,
                        session=session,  # Use the same session
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to store PII redaction metadata for exception {exception.exception_id}: {e}",
                        exc_info=True,
                    )
                    # Don't fail exception persistence if metadata storage fails
            
            # Commit all changes together (session context manager handles commit/close)
        
        logger.debug(
            f"Persisted exception {exception.exception_id} to database"
        )
    
    async def _store_redaction_metadata(
        self,
        exception_id: str,
        tenant_id: str,
        redaction_metadata: dict,
        session: AsyncSession,
    ) -> None:
        """
        Store PII redaction metadata in database.
        
        Phase 9 P9-24: Persists metadata about which fields were redacted.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            redaction_metadata: Redaction metadata dictionary
            session: Database session (must be provided to avoid concurrency issues)
        """
        try:
            from src.infrastructure.db.models import PIIRedactionMetadata
            from sqlalchemy import select
            
            # Check if metadata already exists
            query = select(PIIRedactionMetadata).where(
                PIIRedactionMetadata.exception_id == exception_id
            )
            result = await session.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                # Update existing metadata
                existing.redacted_fields = redaction_metadata.get("redacted_fields", [])
                existing.redaction_count = redaction_metadata.get("redaction_count", 0)
                existing.redaction_placeholder = redaction_metadata.get(
                    "redaction_placeholder", "[REDACTED]"
                )
            else:
                # Create new metadata
                pii_metadata = PIIRedactionMetadata(
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    redacted_fields=redaction_metadata.get("redacted_fields", []),
                    redaction_count=redaction_metadata.get("redaction_count", 0),
                    redaction_placeholder=redaction_metadata.get(
                        "redaction_placeholder", "[REDACTED]"
                    ),
                )
                session.add(pii_metadata)
            
            # Note: Don't commit here - session is committed by caller
            logger.debug(
                f"Stored PII redaction metadata for exception {exception_id}: "
                f"{redaction_metadata.get('redaction_count', 0)} fields redacted"
            )
        except Exception as e:
            logger.warning(
                f"Failed to store PII redaction metadata for exception {exception_id}: {e}",
                exc_info=True,
            )
            # Don't fail exception persistence if metadata storage fails
    
    async def _emit_normalized_event(
        self,
        normalized: ExceptionRecord,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Emit ExceptionNormalized event.
        
        Args:
            normalized: Normalized ExceptionRecord
            correlation_id: Optional correlation ID
            metadata: Optional metadata
        """
        # Extract normalization rules from decision or metadata
        normalization_rules = []
        if metadata and "decision" in metadata and metadata["decision"]:
            decision = metadata["decision"]
            if "evidence" in decision:
                normalization_rules = decision.get("evidence", [])
        
        # Create ExceptionNormalized event
        # Phase 9 P9-21: Ensure correlation_id = exception_id (propagate from ingested event or use exception_id)
        final_correlation_id = correlation_id or normalized.exception_id
        
        # Create ExceptionNormalized event
        normalized_event = ExceptionNormalized.create(
            tenant_id=normalized.tenant_id,
            exception_id=normalized.exception_id,
            normalized_exception=normalized.model_dump(by_alias=True),
            normalization_rules=normalization_rules,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
            metadata=metadata,
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=normalized_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted ExceptionNormalized event: exception_id={normalized.exception_id}"
        )

