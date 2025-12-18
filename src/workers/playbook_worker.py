"""
PlaybookWorker for Phase 9.

Subscribes to PlaybookMatched events, loads playbooks, emits StepExecutionRequested
for next steps, and updates exception playbook progress as steps complete.

Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2
"""

import logging
from typing import Any, Optional

from src.events.schema import CanonicalEvent
from src.events.types import PlaybookMatched, StepExecutionRequested
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.models.domain_pack import DomainPack, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord
from src.models.tenant_policy import TenantPolicyPack
from src.playbooks.manager import PlaybookManager
from src.repository.dto import ExceptionUpdateDTO
from src.repository.exceptions_repository import ExceptionRepository
from src.workers.base import AgentWorker

logger = logging.getLogger(__name__)


class PlaybookWorker(AgentWorker):
    """
    Worker that processes PlaybookMatched events and drives playbook step execution.
    
    Responsibilities:
    - Subscribe to PlaybookMatched events
    - Load playbook from domain pack
    - Emit StepExecutionRequested for next step (one-at-a-time for MVP)
    - Update exception playbook progress (current_step) as steps complete
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
        playbook_manager: Optional[PlaybookManager] = None,
        event_processing_repo: Optional[EventProcessingRepository] = None,
    ):
        """
        Initialize PlaybookWorker.
        
        Args:
            broker: Message broker instance
            topics: List of topic names (should include "exceptions" or similar)
            group_id: Consumer group ID
            event_publisher: EventPublisherService for emitting events
            exception_repository: ExceptionRepository for updating exceptions
            domain_pack: Domain Pack containing playbooks
            tenant_policy: Tenant Policy Pack
            playbook_manager: Optional PlaybookManager for playbook selection
            event_processing_repo: Optional EventProcessingRepository for idempotency
        """
        super().__init__(
            broker=broker,
            topics=topics,
            group_id=group_id,
            worker_name="PlaybookWorker",
            event_processing_repo=event_processing_repo,
        )
        
        self.event_publisher = event_publisher
        self.exception_repository = exception_repository
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.playbook_manager = playbook_manager or PlaybookManager()
        
        # Load playbooks into manager
        if domain_pack:
            try:
                self.playbook_manager.load_playbooks(
                    domain_pack=domain_pack,
                    tenant_id=tenant_policy.tenant_id if tenant_policy else "default",
                )
            except Exception as e:
                logger.warning(f"Failed to load playbooks into manager: {e}")
        
        logger.info(
            f"Initialized PlaybookWorker: topics={topics}, group_id={group_id}"
        )
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process PlaybookMatched event.
        
        Args:
            event: CanonicalEvent (should be PlaybookMatched)
            
        Raises:
            ValueError: If event is not PlaybookMatched
            Exception: If playbook loading or step emission fails
        """
        # Validate event type
        if event.event_type != "PlaybookMatched":
            raise ValueError(
                f"PlaybookWorker expects PlaybookMatched events, got {event.event_type}"
            )
        
        # Cast to PlaybookMatched for type safety
        playbook_matched_event = PlaybookMatched.model_validate(event.model_dump())
        
        tenant_id = playbook_matched_event.tenant_id
        exception_id = playbook_matched_event.exception_id
        payload = playbook_matched_event.payload
        playbook_id = payload.get("playbook_id")
        playbook_name = payload.get("playbook_name")
        
        logger.info(
            f"PlaybookWorker processing PlaybookMatched: "
            f"tenant_id={tenant_id}, exception_id={exception_id}, "
            f"playbook_id={playbook_id}"
        )
        
        # Get exception from database to get current step
        try:
            exception_db = await self.exception_repository.get_by_id(
                exception_id, tenant_id
            )
            if not exception_db:
                raise ValueError(
                    f"Exception {exception_id} not found for tenant {tenant_id}"
                )
            
            current_step = exception_db.current_step or 1
        except Exception as e:
            logger.error(
                f"PlaybookWorker failed to get exception from database: {e}",
                exc_info=True,
            )
            raise
        
        # Load playbook
        try:
            playbook = await self._load_playbook(
                playbook_id=playbook_id,
                playbook_name=playbook_name,
                exception_id=exception_id,
                tenant_id=tenant_id,
            )
            if not playbook:
                raise ValueError(
                    f"Playbook {playbook_id} not found for exception {exception_id}"
                )
        except Exception as e:
            logger.error(
                f"PlaybookWorker failed to load playbook: {e}",
                exc_info=True,
            )
            raise
        
        # Get next step to execute
        try:
            next_step, next_step_number = self._get_next_step(playbook, current_step)
            if not next_step:
                logger.info(
                    f"PlaybookWorker: No more steps for exception {exception_id}, "
                    f"playbook {playbook_id} is complete"
                )
                return
        except Exception as e:
            logger.error(
                f"PlaybookWorker failed to get next step: {e}",
                exc_info=True,
            )
            raise
        
        # Emit StepExecutionRequested for next step
        try:
            await self._emit_step_execution_requested(
                exception_id=exception_id,
                tenant_id=tenant_id,
                playbook_id=playbook_id,
                step=next_step,
                step_number=next_step_number,
                correlation_id=playbook_matched_event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"PlaybookWorker failed to emit StepExecutionRequested event: {e}",
                exc_info=True,
            )
            raise
        
        logger.info(
            f"PlaybookWorker completed processing: exception_id={exception_id}, "
            f"emitted step {next_step_number}"
        )
    
    async def _load_playbook(
        self,
        playbook_id: str,
        playbook_name: Optional[str],
        exception_id: str,
        tenant_id: str,
    ) -> Optional[Playbook]:
        """
        Load playbook from domain pack or manager.
        
        Args:
            playbook_id: Playbook identifier
            playbook_name: Optional playbook name
            exception_id: Exception identifier (for context)
            tenant_id: Tenant identifier
            
        Returns:
            Playbook instance or None if not found
        """
        # Try to find playbook by ID or name in domain pack
        if self.domain_pack and self.domain_pack.playbooks:
            for playbook in self.domain_pack.playbooks:
                # Match by exception_type (which is used as playbook_id in MVP)
                if playbook.exception_type == playbook_id:
                    return playbook
                # Match by name if available
                if playbook_name and hasattr(playbook, "name") and playbook.name == playbook_name:
                    return playbook
        
        # Try to find via playbook manager
        if self.playbook_manager:
            try:
                # Get exception record for playbook selection
                exception_db = await self.exception_repository.get_by_id(
                    exception_id, tenant_id
                )
                if exception_db:
                    # Reconstruct ExceptionRecord
                    from src.models.exception_record import ResolutionStatus, Severity
                    
                    severity = None
                    if exception_db.severity:
                        try:
                            severity = Severity(exception_db.severity.value.upper())
                        except (ValueError, AttributeError):
                            pass
                    
                    resolution_status = ResolutionStatus.OPEN
                    if exception_db.status:
                        try:
                            resolution_status = ResolutionStatus(exception_db.status.value.upper())
                        except (ValueError, AttributeError):
                            pass
                    
                    exception_record = ExceptionRecord(
                        exceptionId=exception_db.exception_id,
                        tenantId=exception_db.tenant_id,
                        sourceSystem=exception_db.source_system,
                        exceptionType=exception_db.type,
                        severity=severity,
                        timestamp=exception_db.created_at,
                        rawPayload={},
                        normalizedContext={"domain": exception_db.domain} if exception_db.domain else {},
                        resolutionStatus=resolution_status,
                    )
                    
                    # Select playbook via manager
                    playbook = self.playbook_manager.select_playbook(
                        exception_record=exception_record,
                        tenant_policy=self.tenant_policy,
                        domain_pack=self.domain_pack,
                    )
                    if playbook:
                        return playbook
            except Exception as e:
                logger.warning(f"Failed to load playbook via manager: {e}")
        
        return None
    
    def _get_next_step(
        self, playbook: Playbook, current_step: int
    ) -> tuple[Optional[PlaybookStep], Optional[int]]:
        """
        Get next step to execute from playbook.
        
        Args:
            playbook: Playbook instance
            current_step: Current step number (1-indexed)
            
        Returns:
            Tuple of (Next PlaybookStep to execute, step_number) or (None, None) if playbook is complete
        """
        if not playbook.steps:
            return None, None
        
        # Get steps sorted by step_order if available, otherwise by list position
        sorted_steps = []
        for idx, step in enumerate(playbook.steps):
            # Check if step has step_order attribute
            if hasattr(step, "step_order") and step.step_order is not None:
                sorted_steps.append((step.step_order, step))
            else:
                # Use list index + 1 as step_order (1-indexed)
                sorted_steps.append((idx + 1, step))
        
        # Sort by step_order
        sorted_steps.sort(key=lambda x: x[0])
        
        # Find next step (current_step is 1-indexed, so next is current_step + 1)
        next_step_order = current_step + 1
        
        for step_order, step in sorted_steps:
            if step_order == next_step_order:
                return step, step_order
        
        # No more steps
        return None, None
    
    async def _emit_step_execution_requested(
        self,
        exception_id: str,
        tenant_id: str,
        playbook_id: str,
        step: PlaybookStep,
        step_number: int,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit StepExecutionRequested event.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            playbook_id: Playbook identifier
            step: PlaybookStep to execute
            step_number: Step number (1-indexed)
            correlation_id: Optional correlation ID
        """
        # Build step action details
        step_action = {
            "step_order": step_number,
            "name": step.name if hasattr(step, "name") else f"Step {step_number}",
            "action": step.action,
            "parameters": step.parameters or {},
        }
        
        # Add optional fields if available
        if hasattr(step, "action_type"):
            step_action["action_type"] = step.action_type
        if hasattr(step, "description") and step.description:
            step_action["description"] = step.description
        if hasattr(step, "step_id") and step.step_id:
            step_action["step_id"] = step.step_id
        
        # Create StepExecutionRequested event
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception_id
        
        step_requested_event = StepExecutionRequested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            playbook_id=playbook_id,
            step_number=step_number,
            step_action=step_action,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=step_requested_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted StepExecutionRequested event: exception_id={exception_id}, "
            f"playbook_id={playbook_id}, step_number={step_number}"
        )
    
    async def handle_step_completion(
        self,
        exception_id: str,
        tenant_id: str,
        step_number: int,
    ) -> None:
        """
        Handle step completion by updating exception progress.
        
        This method can be called when StepExecutionCompleted events are received.
        For MVP, this updates the current_step to the next step number.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            step_number: Completed step number
        """
        try:
            # Update exception to mark step as completed
            # Set current_step to the completed step number
            update_dto = ExceptionUpdateDTO(
                current_step=step_number,
            )
            
            await self.exception_repository.update_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                updates=update_dto,
            )
            
            logger.debug(
                f"Updated exception {exception_id} playbook progress: current_step={step_number}"
            )
        except Exception as e:
            logger.error(
                f"PlaybookWorker failed to update exception progress: {e}",
                exc_info=True,
            )
            raise

