"""
PolicyWorker for Phase 9.

Subscribes to TriageCompleted events, performs policy evaluation using PolicyAgent,
updates exception with playbook assignment, and emits policy and playbook events.

Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2
"""

import logging
from typing import Any, Optional

from src.agents.policy import PolicyAgent
from src.audit.logger import AuditLogger
from src.events.schema import CanonicalEvent
from src.events.types import (
    PlaybookMatched,
    PolicyEvaluationCompleted,
    PolicyEvaluationRequested,
    TriageCompleted,
)
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.llm.provider import LLMClient
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord
from src.models.tenant_policy import TenantPolicyPack
from src.repository.dto import ExceptionUpdateDTO
from src.repository.exceptions_repository import ExceptionRepository
from src.safety.violation_detector import ViolationDetector
from src.workers.base import AgentWorker

logger = logging.getLogger(__name__)


class PolicyWorker(AgentWorker):
    """
    Worker that processes TriageCompleted events and performs policy evaluation.
    
    Responsibilities:
    - Subscribe to TriageCompleted events
    - Perform policy evaluation using PolicyAgent
    - Update exception with playbook assignment (playbook_id, current_step)
    - Emit PolicyEvaluationRequested and PolicyEvaluationCompleted events
    - Emit PlaybookMatched event when playbook is assigned
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
        tenant_policy: TenantPolicyPack,
        audit_logger: Optional[AuditLogger] = None,
        llm_client: Optional[LLMClient] = None,
        violation_detector: Optional[ViolationDetector] = None,
        event_processing_repo: Optional[EventProcessingRepository] = None,
    ):
        """
        Initialize PolicyWorker.
        
        Args:
            broker: Message broker instance
            topics: List of topic names (should include "exceptions" or similar)
            group_id: Consumer group ID
            event_publisher: EventPublisherService for emitting events
            exception_repository: ExceptionRepository for updating exceptions
            domain_pack: Domain Pack for playbooks
            tenant_policy: Tenant Policy Pack for guardrails
            audit_logger: Optional AuditLogger for audit logging
            llm_client: Optional LLMClient for LLM-enhanced reasoning
            violation_detector: Optional ViolationDetector for violation detection
            event_processing_repo: Optional EventProcessingRepository for idempotency
        """
        super().__init__(
            broker=broker,
            topics=topics,
            group_id=group_id,
            worker_name="PolicyWorker",
            event_processing_repo=event_processing_repo,
        )
        
        self.event_publisher = event_publisher
        self.exception_repository = exception_repository
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.audit_logger = audit_logger
        self.llm_client = llm_client
        self.violation_detector = violation_detector
        
        # Initialize PolicyAgent
        self.policy_agent = PolicyAgent(
            domain_pack=domain_pack,
            tenant_policy=tenant_policy,
            audit_logger=audit_logger,
            llm_client=llm_client,
            violation_detector=violation_detector,
        )
        
        logger.info(
            f"Initialized PolicyWorker: topics={topics}, group_id={group_id}"
        )
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process TriageCompleted event.
        
        Args:
            event: CanonicalEvent (should be TriageCompleted)
            
        Raises:
            ValueError: If event is not TriageCompleted
            Exception: If policy evaluation or persistence fails
        """
        # Skip events that are not TriageCompleted
        if event.event_type != "TriageCompleted":
            logger.debug(
                f"PolicyWorker skipping event {event.event_id} of type {event.event_type} "
                f"(only processes TriageCompleted events)"
            )
            return
        
        # Cast to TriageCompleted for type safety
        triage_completed_event = TriageCompleted.model_validate(event.model_dump())
        
        tenant_id = triage_completed_event.tenant_id
        exception_id = triage_completed_event.exception_id
        payload = triage_completed_event.payload
        triage_result = payload.get("triage_result", {})
        
        logger.info(
            f"PolicyWorker processing TriageCompleted: "
            f"tenant_id={tenant_id}, exception_id={exception_id}"
        )
        
        # Get exception from database to reconstruct ExceptionRecord
        # Create repository per-operation to ensure fresh session
        try:
            from src.infrastructure.db.session import get_db_session_context
            from src.repository.exceptions_repository import ExceptionRepository
            
            async with get_db_session_context() as session:
                exception_repository = ExceptionRepository(session=session)
                exception_db = await exception_repository.get_exception(
                    tenant_id=tenant_id,
                    exception_id=exception_id,
                )
                if not exception_db:
                    raise ValueError(
                        f"Exception {exception_id} not found for tenant {tenant_id}"
                    )
                
                # Reconstruct ExceptionRecord from database model
                exception = self._reconstruct_exception_record(exception_db)
        except Exception as e:
            logger.error(
                f"PolicyWorker failed to get exception from database: {e}",
                exc_info=True,
            )
            raise
        
        # Emit PolicyEvaluationRequested event
        try:
            await self._emit_policy_evaluation_requested_event(
                exception=exception,
                correlation_id=triage_completed_event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"PolicyWorker failed to emit PolicyEvaluationRequested event: {e}",
                exc_info=True,
            )
            # Continue processing even if event emission fails
        
        # Build context from triage result
        context = {
            "triage": triage_result,
            "confidence": triage_result.get("confidence", 0.0),
        }
        
        # Perform policy evaluation using PolicyAgent
        try:
            decision = await self.policy_agent.process(exception, context)
        except Exception as e:
            logger.error(
                f"PolicyWorker failed to perform policy evaluation: {e}",
                exc_info=True,
            )
            raise
        
        # Extract playbook information from decision/context
        playbook_id = None
        playbook_name = None
        match_reason = None
        
        # Try to extract from decision evidence
        decision_dict = decision.model_dump() if hasattr(decision, "model_dump") else decision
        evidence = decision_dict.get("evidence", [])
        
        for item in evidence:
            if isinstance(item, str):
                # Look for playbook ID patterns
                if "playbook_id:" in item.lower() or "playbook:" in item.lower():
                    parts = item.split(":")
                    if len(parts) > 1:
                        playbook_id = parts[-1].strip()
                if "playbook_name:" in item.lower():
                    parts = item.split(":")
                    if len(parts) > 1:
                        playbook_name = parts[-1].strip()
                if "match_reason:" in item.lower() or "reasoning:" in item.lower():
                    parts = item.split(":")
                    if len(parts) > 1:
                        match_reason = parts[-1].strip()
        
        # Try to find playbook from domain pack if we have exception type
        if not playbook_id and exception.exception_type:
            for playbook in self.domain_pack.playbooks:
                if playbook.exception_type == exception.exception_type:
                    # Use exception_type as playbook_id for MVP
                    playbook_id = playbook.exception_type
                    playbook_name = playbook.exception_type  # Use type as name for MVP
                    match_reason = f"Matched by exception type: {exception.exception_type}"
                    break
        
        # Update exception with policy results and playbook assignment
        try:
            await self._update_exception_policy(
                exception_id=exception_id,
                tenant_id=tenant_id,
                decision=decision,
                playbook_id=playbook_id,
            )
        except Exception as e:
            logger.error(
                f"PolicyWorker failed to update exception policy: {e}",
                exc_info=True,
            )
            raise
        
        # Emit PlaybookMatched event if playbook was assigned
        if playbook_id:
            try:
                await self._emit_playbook_matched_event(
                    exception=exception,
                    playbook_id=playbook_id,
                    playbook_name=playbook_name or playbook_id,
                    match_reason=match_reason,
                    correlation_id=triage_completed_event.correlation_id,
                )
            except Exception as e:
                logger.error(
                    f"PolicyWorker failed to emit PlaybookMatched event: {e}",
                    exc_info=True,
                )
                # Continue even if event emission fails
        
        # Emit PolicyEvaluationCompleted event
        try:
            await self._emit_policy_evaluation_completed_event(
                exception=exception,
                decision=decision,
                correlation_id=triage_completed_event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"PolicyWorker failed to emit PolicyEvaluationCompleted event: {e}",
                exc_info=True,
            )
            raise
        
        logger.info(
            f"PolicyWorker completed processing: exception_id={exception_id}"
        )
    
    def _reconstruct_exception_record(self, exception_db: Any) -> ExceptionRecord:
        """
        Reconstruct ExceptionRecord from database model.
        
        Args:
            exception_db: Exception database model
            
        Returns:
            ExceptionRecord instance
        """
        from src.models.exception_record import ResolutionStatus, Severity
        
        # Map database severity to ExceptionRecord Severity
        severity = None
        if exception_db.severity:
            try:
                severity = Severity(exception_db.severity.value.upper())
            except (ValueError, AttributeError):
                pass
        
        # Map database status to ResolutionStatus
        resolution_status = ResolutionStatus.OPEN
        if exception_db.status:
            try:
                resolution_status = ResolutionStatus(exception_db.status.value.upper())
            except (ValueError, AttributeError):
                pass
        
        return ExceptionRecord(
            exceptionId=exception_db.exception_id,
            tenantId=exception_db.tenant_id,
            sourceSystem=exception_db.source_system,
            exceptionType=exception_db.type,
            severity=severity,
            timestamp=exception_db.created_at,
            rawPayload={},  # Not stored in exception table
            normalizedContext={"domain": exception_db.domain} if exception_db.domain else {},
            resolutionStatus=resolution_status,
        )
    
    async def _emit_policy_evaluation_requested_event(
        self,
        exception: ExceptionRecord,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit PolicyEvaluationRequested event.
        
        Args:
            exception: ExceptionRecord to evaluate
            correlation_id: Optional correlation ID
        """
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception.exception_id
        
        policy_requested_event = PolicyEvaluationRequested.create(
            tenant_id=exception.tenant_id,
            exception_id=exception.exception_id,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
            metadata={"requested_by": "PolicyWorker"},  # Put requested_by in metadata
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=policy_requested_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted PolicyEvaluationRequested event: exception_id={exception.exception_id}"
        )
    
    async def _update_exception_policy(
        self,
        exception_id: str,
        tenant_id: str,
        decision: Any,  # AgentDecision
        playbook_id: Optional[str] = None,
    ) -> None:
        """
        Update exception with policy results and playbook assignment.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            decision: AgentDecision from PolicyAgent
            playbook_id: Optional playbook identifier
        """
        from src.models.agent_contracts import AgentDecision
        
        # Ensure decision is AgentDecision
        if isinstance(decision, AgentDecision):
            decision_dict = decision.model_dump()
        elif isinstance(decision, dict):
            decision_dict = decision
        else:
            decision_dict = decision.model_dump() if hasattr(decision, "model_dump") else {}
        
        # Build update DTO
        update_fields = {}
        
        # Set playbook_id and current_step if playbook is assigned
        if playbook_id:
            # For MVP, playbook_id might be a string (exception_type) or integer
            # Try to convert to integer if it's numeric, otherwise leave as None
            # In production, this would query the playbook repository to get the actual ID
            try:
                # If playbook_id is numeric string, convert to int
                playbook_id_int = int(playbook_id) if playbook_id.isdigit() else None
                update_fields["current_playbook_id"] = playbook_id_int
            except (ValueError, AttributeError):
                # If not numeric, we can't set the database ID
                # For MVP, we'll set current_step but not playbook_id
                logger.warning(
                    f"Playbook ID {playbook_id} is not numeric, cannot set current_playbook_id"
                )
            
            update_fields["current_step"] = 1  # Start at step 1
        
        # Build update DTO (only include fields that have values)
        if not update_fields:
            logger.warning(
                f"No policy fields to update for exception {exception_id}"
            )
            return
        
        update_dto = ExceptionUpdateDTO(**update_fields)
        
        # Update exception - create repository per-operation to ensure fresh session
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
            f"Updated exception {exception_id} with policy results: "
            f"playbook_id={playbook_id}, current_step=1"
        )
    
    async def _emit_playbook_matched_event(
        self,
        exception: ExceptionRecord,
        playbook_id: str,
        playbook_name: str,
        match_reason: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit PlaybookMatched event.
        
        Args:
            exception: ExceptionRecord that was matched
            playbook_id: Matched playbook identifier
            playbook_name: Playbook name
            match_reason: Optional match reason
            correlation_id: Optional correlation ID
        """
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception.exception_id
        
        # PlaybookMatched.create expects playbook_id as int, but we may have string
        # For MVP, use 1 as default if playbook_id is not numeric
        try:
            playbook_id_int = int(playbook_id) if isinstance(playbook_id, str) and playbook_id.isdigit() else 1
        except (ValueError, TypeError):
            playbook_id_int = 1
        
        playbook_matched_event = PlaybookMatched.create(
            tenant_id=exception.tenant_id,
            exception_id=exception.exception_id,
            playbook_id=playbook_id_int,
            playbook_name=playbook_name,
            match_reason=match_reason or f"Matched by exception type: {exception.exception_type}",
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=playbook_matched_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted PlaybookMatched event: exception_id={exception.exception_id}, "
            f"playbook_id={playbook_id}"
        )
    
    async def _emit_policy_evaluation_completed_event(
        self,
        exception: ExceptionRecord,
        decision: Any,  # AgentDecision
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit PolicyEvaluationCompleted event.
        
        Args:
            exception: ExceptionRecord that was evaluated
            decision: AgentDecision from PolicyAgent
            correlation_id: Optional correlation ID
        """
        # Extract policy results
        decision_dict = decision.model_dump() if hasattr(decision, "model_dump") else decision
        
        # Extract approved actions and guardrails from evidence
        approved_actions = []
        guardrails_applied = []
        
        evidence = decision_dict.get("evidence", [])
        for item in evidence:
            if isinstance(item, str):
                if "approved" in item.lower() or "actionable" in item.lower():
                    approved_actions.append(item)
                if "guardrail" in item.lower() or "blocked" in item.lower():
                    guardrails_applied.append(item)
        
        # Create PolicyEvaluationCompleted event
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception.exception_id
        
        # Build policy_result dict with all relevant information
        policy_result_dict = decision_dict.copy()
        if approved_actions:
            policy_result_dict["approved_actions"] = approved_actions
        if guardrails_applied:
            policy_result_dict["guardrails_applied"] = guardrails_applied
        
        policy_completed_event = PolicyEvaluationCompleted.create(
            tenant_id=exception.tenant_id,
            exception_id=exception.exception_id,
            policy_result=policy_result_dict,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=policy_completed_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted PolicyEvaluationCompleted event: exception_id={exception.exception_id}"
        )

