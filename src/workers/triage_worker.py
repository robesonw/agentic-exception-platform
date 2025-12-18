"""
TriageWorker for Phase 9.

Subscribes to ExceptionNormalized events, performs triage analysis using TriageAgent,
updates exception triage fields, and emits TriageRequested and TriageCompleted events.

Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2
"""

import logging
from typing import Any, Optional

from src.agents.triage import TriageAgent
from src.audit.logger import AuditLogger
from src.events.schema import CanonicalEvent
from src.events.types import ExceptionNormalized, TriageCompleted, TriageRequested
from src.infrastructure.db.models import ExceptionSeverity
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.llm.provider import LLMClient
from src.memory.index import MemoryIndexRegistry
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord
from src.repository.dto import ExceptionUpdateDTO
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.base import AgentWorker

logger = logging.getLogger(__name__)


class TriageWorker(AgentWorker):
    """
    Worker that processes ExceptionNormalized events and performs triage analysis.
    
    Responsibilities:
    - Subscribe to ExceptionNormalized events
    - Perform triage analysis using TriageAgent
    - Update exception triage fields (severity, exception_type)
    - Emit TriageRequested and TriageCompleted events
    - Ensure idempotency (via base worker)
    - Enforce tenant isolation
    """
    
    def __init__(
        self,
        broker: Broker,
        topics: list[str],
        group_id: str,
        event_publisher: EventPublisherService,
        exception_repository: ExceptionRepository,
        domain_pack: DomainPack,
        audit_logger: Optional[AuditLogger] = None,
        memory_index: Optional[MemoryIndexRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        event_processing_repo: Optional[EventProcessingRepository] = None,
    ):
        """
        Initialize TriageWorker.
        
        Args:
            broker: Message broker instance
            topics: List of topic names (should include "exceptions" or similar)
            group_id: Consumer group ID
            event_publisher: EventPublisherService for emitting events
            exception_repository: ExceptionRepository for updating exceptions
            domain_pack: Domain Pack for triage rules
            audit_logger: Optional AuditLogger for audit logging
            memory_index: Optional MemoryIndexRegistry for RAG similarity search
            llm_client: Optional LLMClient for LLM-enhanced reasoning
            event_processing_repo: Optional EventProcessingRepository for idempotency
        """
        super().__init__(
            broker=broker,
            topics=topics,
            group_id=group_id,
            worker_name="TriageWorker",
            event_processing_repo=event_processing_repo,
        )
        
        self.event_publisher = event_publisher
        self.exception_repository = exception_repository
        self.domain_pack = domain_pack
        self.audit_logger = audit_logger
        self.memory_index = memory_index
        self.llm_client = llm_client
        
        # Initialize TriageAgent
        self.triage_agent = TriageAgent(
            domain_pack=domain_pack,
            audit_logger=audit_logger,
            memory_index=memory_index,
            llm_client=llm_client,
        )
        
        logger.info(
            f"Initialized TriageWorker: topics={topics}, group_id={group_id}"
        )
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process ExceptionNormalized event.
        
        Args:
            event: CanonicalEvent (should be ExceptionNormalized)
            
        Raises:
            ValueError: If event is not ExceptionNormalized
            Exception: If triage processing or persistence fails
        """
        # Skip events that are not ExceptionNormalized
        if event.event_type != "ExceptionNormalized":
            logger.debug(
                f"TriageWorker skipping event {event.event_id} of type {event.event_type} "
                f"(only processes ExceptionNormalized events)"
            )
            return
        
        # Cast to ExceptionNormalized for type safety
        normalized_event = ExceptionNormalized.model_validate(event.model_dump())
        
        tenant_id = normalized_event.tenant_id
        exception_id = normalized_event.exception_id
        payload = normalized_event.payload
        normalized_exception_data = payload.get("normalized_exception", {})
        
        logger.info(
            f"TriageWorker processing ExceptionNormalized: "
            f"tenant_id={tenant_id}, exception_id={exception_id}"
        )
        
        # Reconstruct ExceptionRecord from normalized_exception data
        try:
            exception = ExceptionRecord.model_validate(normalized_exception_data)
        except Exception as e:
            logger.error(
                f"TriageWorker failed to reconstruct ExceptionRecord: {e}",
                exc_info=True,
            )
            raise
        
        # Emit TriageRequested event
        try:
            await self._emit_triage_requested_event(
                exception=exception,
                correlation_id=normalized_event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"TriageWorker failed to emit TriageRequested event: {e}",
                exc_info=True,
            )
            # Continue processing even if event emission fails
        
        # Perform triage analysis using TriageAgent
        try:
            decision = await self.triage_agent.process(exception)
        except Exception as e:
            logger.error(
                f"TriageWorker failed to perform triage analysis: {e}",
                exc_info=True,
            )
            raise
        
        # Update exception with triage results
        try:
            await self._update_exception_triage(
                exception_id=exception_id,
                tenant_id=tenant_id,
                decision=decision,
            )
        except Exception as e:
            logger.error(
                f"TriageWorker failed to update exception triage: {e}",
                exc_info=True,
            )
            raise
        
        # Emit TriageCompleted event
        try:
            await self._emit_triage_completed_event(
                exception=exception,
                decision=decision,
                correlation_id=normalized_event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"TriageWorker failed to emit TriageCompleted event: {e}",
                exc_info=True,
            )
            raise
        
        logger.info(
            f"TriageWorker completed processing: exception_id={exception_id}"
        )
    
    async def _emit_triage_requested_event(
        self,
        exception: ExceptionRecord,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit TriageRequested event.
        
        Args:
            exception: ExceptionRecord to triage
            correlation_id: Optional correlation ID
        """
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception.exception_id
        
        triage_requested_event = TriageRequested.create(
            tenant_id=exception.tenant_id,
            exception_id=exception.exception_id,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
            metadata={"requested_by": "TriageWorker"},  # Put requested_by in metadata
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=triage_requested_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted TriageRequested event: exception_id={exception.exception_id}"
        )
    
    async def _update_exception_triage(
        self,
        exception_id: str,
        tenant_id: str,
        decision: Any,  # AgentDecision
    ) -> None:
        """
        Update exception with triage results.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            decision: AgentDecision from TriageAgent
        """
        from src.models.agent_contracts import AgentDecision
        
        # Ensure decision is AgentDecision
        if isinstance(decision, AgentDecision):
            decision_dict = decision.model_dump()
        elif isinstance(decision, dict):
            decision_dict = decision
        else:
            decision_dict = decision.model_dump() if hasattr(decision, "model_dump") else {}
        
        # Extract severity from decision (may be in decision string or evidence)
        severity = None
        exception_type = None
        
        # Try to extract from decision string
        decision_str = decision_dict.get("decision", "")
        if isinstance(decision_str, str):
            decision_upper = decision_str.upper()
            # Look for severity keywords (check in order of priority)
            if "CRITICAL" in decision_upper:
                severity = ExceptionSeverity.CRITICAL
            elif "HIGH" in decision_upper:
                severity = ExceptionSeverity.HIGH
            elif "MEDIUM" in decision_upper:
                severity = ExceptionSeverity.MEDIUM
            elif "LOW" in decision_upper:
                severity = ExceptionSeverity.LOW
        
        # Try to extract from evidence
        evidence = decision_dict.get("evidence", [])
        if isinstance(evidence, list):
            for item in evidence:
                if isinstance(item, str):
                    item_upper = item.upper()
                    # Extract severity (only if not already found)
                    if severity is None:
                        if "CRITICAL" in item_upper:
                            severity = ExceptionSeverity.CRITICAL
                        elif "HIGH" in item_upper:
                            severity = ExceptionSeverity.HIGH
                        elif "MEDIUM" in item_upper:
                            severity = ExceptionSeverity.MEDIUM
                        elif "LOW" in item_upper:
                            severity = ExceptionSeverity.LOW
                    
                    # Look for exception type patterns
                    if exception_type is None:
                        if "type:" in item.lower() or "exception type:" in item.lower():
                            # Extract type from evidence
                            parts = item.split(":")
                            if len(parts) > 1:
                                exception_type = parts[-1].strip()
                        elif "classified as" in item.lower():
                            # Extract from "classified as X" pattern
                            parts = item.lower().split("classified as")
                            if len(parts) > 1:
                                exception_type = parts[-1].strip()
        
        # Default severity if not found
        if severity is None:
            severity = ExceptionSeverity.MEDIUM
        
        # Build update DTO (only include fields that have values)
        update_fields = {}
        if severity:
            update_fields["severity"] = severity
        if exception_type:
            update_fields["type"] = exception_type
        
        if not update_fields:
            logger.warning(
                f"No triage fields to update for exception {exception_id}"
            )
            return
        
        update_dto = ExceptionUpdateDTO(**update_fields)
        
        # Update exception (create repository per-operation to avoid asyncpg concurrency issues)
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
            exception_repository = ExceptionRepository(session=session)
            await exception_repository.update_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                updates=update_dto,
            )
        
        logger.debug(
            f"Updated exception {exception_id} with triage results: "
            f"severity={severity.value if severity else None}, type={exception_type}"
        )
    
    async def _emit_triage_completed_event(
        self,
        exception: ExceptionRecord,
        decision: Any,  # AgentDecision
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit TriageCompleted event.
        
        Args:
            exception: ExceptionRecord that was triaged
            decision: AgentDecision from TriageAgent
            correlation_id: Optional correlation ID
        """
        # Extract triage results
        decision_dict = decision.model_dump() if hasattr(decision, "model_dump") else decision
        
        # Extract severity and exception type
        severity = None
        exception_type = None
        
        # Try to extract from decision
        decision_str = decision_dict.get("decision", "")
        if isinstance(decision_str, str):
            if "CRITICAL" in decision_str.upper():
                severity = "CRITICAL"
            elif "HIGH" in decision_str.upper():
                severity = "HIGH"
            elif "MEDIUM" in decision_str.upper():
                severity = "MEDIUM"
            elif "LOW" in decision_str.upper():
                severity = "LOW"
        
        # Default severity
        if severity is None:
            severity = "MEDIUM"
        
        # Use exception type from exception if available
        if exception.exception_type:
            exception_type = exception.exception_type
        
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception.exception_id
        
        # Include severity and exception_type in triage_result or metadata
        enhanced_triage_result = decision_dict.copy() if isinstance(decision_dict, dict) else {}
        if severity:
            enhanced_triage_result["severity"] = severity
        if exception_type:
            enhanced_triage_result["exception_type"] = exception_type
        
        # Create TriageCompleted event
        triage_completed_event = TriageCompleted.create(
            tenant_id=exception.tenant_id,
            exception_id=exception.exception_id,
            triage_result=enhanced_triage_result,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=triage_completed_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted TriageCompleted event: exception_id={exception.exception_id}"
        )

