"""
Playbook Execution Service for Phase 7 MVP.

Handles playbook execution lifecycle: starting playbooks, completing steps, and tracking state.
Reference: docs/phase7-playbooks-mvp.md Sections 4 & 5.2
"""

import logging
from typing import Any, Optional
from uuid import uuid4

from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError

from src.infrastructure.db.models import ActorType
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
from src.repository.dto import ExceptionEventCreateDTO, ExceptionUpdateDTO
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError

logger = logging.getLogger(__name__)


class PlaybookExecutionError(Exception):
    """Raised when playbook execution operations fail."""
    pass


class PlaybookExecutionService:
    """
    Service for executing playbooks and managing playbook state.
    
    Handles:
    - Starting playbooks for exceptions
    - Completing playbook steps
    - Skipping playbook steps (optional)
    - Tracking execution state via exception fields
    - Emitting events for playbook lifecycle
    
    Reference: docs/phase7-playbooks-mvp.md Sections 4 & 5.2
    """
    
    def __init__(
        self,
        exception_repository: ExceptionRepository,
        event_repository: ExceptionEventRepository,
        playbook_repository: PlaybookRepository,
        step_repository: PlaybookStepRepository,
        tool_execution_service: Optional[ToolExecutionService] = None,
    ):
        """
        Initialize the playbook execution service.
        
        Args:
            exception_repository: Repository for exception operations
            event_repository: Repository for event operations
            playbook_repository: Repository for playbook operations
            step_repository: Repository for playbook step operations
            tool_execution_service: Optional tool execution service (required for call_tool steps)
        """
        self.exception_repository = exception_repository
        self.event_repository = event_repository
        self.playbook_repository = playbook_repository
        self.step_repository = step_repository
        self.tool_execution_service = tool_execution_service
    
    def _is_risky_step(self, step: Any) -> bool:
        """
        Determine if a playbook step is risky and requires human approval.
        
        For MVP, risky steps are:
        - call_tool action type (external tool execution)
        - Any action type not in the safe list (notify, add_comment, set_status, assign_owner)
        
        Args:
            step: PlaybookStep instance
            
        Returns:
            True if step is risky and requires human approval, False otherwise
        """
        safe_action_types = {"notify", "add_comment", "set_status", "assign_owner"}
        action_type = step.action_type.lower() if hasattr(step, "action_type") else ""
        
        # call_tool is always risky
        if action_type == "call_tool":
            return True
        
        # Any action not in safe list is considered risky for MVP
        return action_type not in safe_action_types
    
    async def start_playbook_for_exception(
        self,
        tenant_id: str,
        exception_id: str,
        playbook_id: int,
        actor_type: ActorType,
        actor_id: Optional[str] = None,
    ) -> None:
        """
        Start a playbook for an exception.
        
        Sets exception.current_playbook_id and current_step = 1.
        Emits PlaybookStarted event.
        
        This operation is idempotent: if the playbook is already started for this exception,
        it will be a no-op (no duplicate events).
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            playbook_id: Playbook identifier to start
            actor_type: Type of actor starting the playbook (agent/user/system)
            actor_id: Optional actor identifier (user ID or agent name)
            
        Raises:
            PlaybookExecutionError: If exception or playbook not found, or tenant mismatch
            ValueError: If playbook doesn't belong to tenant
        """
        # Validate tenant isolation
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        # Get exception
        exception = await self.exception_repository.get_exception(tenant_id, exception_id)
        if not exception:
            raise PlaybookExecutionError(
                f"Exception {exception_id} not found for tenant {tenant_id}"
            )
        
        # Validate playbook exists and belongs to tenant
        playbook = await self.playbook_repository.get_playbook(playbook_id, tenant_id)
        if not playbook:
            raise PlaybookExecutionError(
                f"Playbook {playbook_id} not found or does not belong to tenant {tenant_id}"
            )
        
        # Check if playbook is already started (idempotency)
        if exception.current_playbook_id == playbook_id:
            # Playbook already started - check if we should emit event
            # Check if PlaybookStarted event already exists
            events = await self.event_repository.get_events_for_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
            )
            playbook_started_exists = any(
                e.event_type == "PlaybookStarted" and e.payload.get("playbook_id") == playbook_id
                for e in events
            )
            
            if playbook_started_exists:
                logger.info(
                    f"Playbook {playbook_id} already started for exception {exception_id}, "
                    "skipping (idempotent)"
                )
                return
        
        # Get playbook steps to validate playbook has steps
        steps = await self.step_repository.get_steps(playbook_id, tenant_id)
        if not steps:
            raise PlaybookExecutionError(
                f"Playbook {playbook_id} has no steps"
            )
        
        # Update exception state
        await self.exception_repository.update_exception(
            tenant_id=tenant_id,
            exception_id=exception_id,
            updates=ExceptionUpdateDTO(
                current_playbook_id=playbook_id,
                current_step=1,
            ),
        )
        
        # Emit PlaybookStarted event
        event_id = uuid4()
        event = ExceptionEventCreateDTO(
            event_id=event_id,
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="PlaybookStarted",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "playbook_id": playbook_id,
                "playbook_name": playbook.name,
                "playbook_version": playbook.version,
                "total_steps": len(steps),
            },
        )
        
        try:
            await self.event_repository.append_event(tenant_id, event)
        except ValueError as e:
            # Event already exists (idempotency check)
            if "already exists" in str(e):
                logger.info(f"PlaybookStarted event already exists for {exception_id}, skipping")
            else:
                raise
        
        logger.info(
            f"Started playbook {playbook_id} for exception {exception_id} "
            f"(actor: {actor_type.value}/{actor_id})"
        )
    
    async def complete_step(
        self,
        tenant_id: str,
        exception_id: str,
        playbook_id: int,
        step_order: int,
        actor_type: ActorType,
        actor_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Complete a playbook step.
        
        Validates that:
        - The step is the next expected step
        - The playbook is currently active for the exception
        - The step exists in the playbook
        
        Updates exception.current_step to the next step (or None if last step).
        Emits PlaybookStepCompleted event.
        If last step, emits PlaybookCompleted event.
        
        This operation is idempotent: completing the same step twice is a no-op.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            playbook_id: Playbook identifier
            step_order: Step order number to complete
            actor_type: Type of actor completing the step (agent/user/system)
            actor_id: Optional actor identifier
            notes: Optional notes about step completion
            
        Raises:
            PlaybookExecutionError: If validation fails or step already completed
            ValueError: If tenant mismatch or invalid parameters
        """
        # Validate tenant isolation
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        if step_order < 1:
            raise ValueError("step_order must be >= 1")
        
        # Get exception
        exception = await self.exception_repository.get_exception(tenant_id, exception_id)
        if not exception:
            raise PlaybookExecutionError(
                f"Exception {exception_id} not found for tenant {tenant_id}"
            )
        
        # Validate playbook is active
        if exception.current_playbook_id != playbook_id:
            raise PlaybookExecutionError(
                f"Playbook {playbook_id} is not active for exception {exception_id}. "
                f"Current playbook: {exception.current_playbook_id}"
            )
        
        # Get playbook steps
        steps = await self.step_repository.get_steps(playbook_id, tenant_id)
        if not steps:
            raise PlaybookExecutionError(f"Playbook {playbook_id} has no steps")
        
        # Validate step exists
        step = next((s for s in steps if s.step_order == step_order), None)
        if not step:
            raise PlaybookExecutionError(
                f"Step {step_order} not found in playbook {playbook_id}"
            )
        
        # Validate step is next expected step
        expected_step = exception.current_step
        if expected_step is None:
            raise PlaybookExecutionError(
                f"Exception {exception_id} has no current step set"
            )
        
        if step_order != expected_step:
            raise PlaybookExecutionError(
                f"Step {step_order} is not the next expected step. "
                f"Expected step: {expected_step}"
            )
        
        # Enforce human approval for risky steps
        if self._is_risky_step(step):
            if actor_type != ActorType.USER:
                raise PlaybookExecutionError(
                    f"Step {step_order} requires human approval (risky action: {step.action_type}). "
                    f"Only human actors (actor_type=USER) can complete risky steps. "
                    f"Received actor_type: {actor_type.value}"
                )
        
        # Handle call_tool step execution (Phase 8 P8-9)
        tool_execution_result = None
        if step.action_type == "call_tool":
            tool_execution_result = await self._execute_tool_step(
                tenant_id=tenant_id,
                exception_id=exception_id,
                step=step,
                actor_type=actor_type,
                actor_id=actor_id,
            )
        
        # Check if step already completed (idempotency)
        events = await self.event_repository.get_events_for_exception(
            tenant_id=tenant_id,
            exception_id=exception_id,
        )
        step_completed_exists = any(
            e.event_type == "PlaybookStepCompleted"
            and e.payload.get("playbook_id") == playbook_id
            and e.payload.get("step_order") == step_order
            for e in events
        )
        
        if step_completed_exists:
            logger.info(
                f"Step {step_order} already completed for exception {exception_id}, "
                "skipping (idempotent)"
            )
            return
        
        # Determine next step
        is_last_step = step_order == len(steps)
        next_step = step_order + 1 if not is_last_step else None
        
        # Update exception state
        await self.exception_repository.update_exception(
            tenant_id=tenant_id,
            exception_id=exception_id,
            updates=ExceptionUpdateDTO(
                current_step=next_step,
            ),
        )
        
        # Emit PlaybookStepCompleted event
        event_id = uuid4()
        event_payload = {
            "playbook_id": playbook_id,
            "step_id": step.step_id,
            "step_order": step_order,
            "step_name": step.name,
            "action_type": step.action_type,
            "is_last_step": is_last_step,
            "is_risky": self._is_risky_step(step),
            "notes": notes,
            "actor_type": actor_type.value,
            "actor_id": actor_id,
        }
        
        # Include tool execution result if this was a call_tool step
        if tool_execution_result:
            event_payload["tool_execution"] = {
                "execution_id": str(tool_execution_result.id),
                "tool_id": tool_execution_result.tool_id,
                "status": tool_execution_result.status.value,
                "success": tool_execution_result.status.value == "succeeded",
                "error_message": tool_execution_result.error_message,
            }
        
        event = ExceptionEventCreateDTO(
            event_id=event_id,
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="PlaybookStepCompleted",
            actor_type=actor_type,
            actor_id=actor_id,
            payload=event_payload,
        )
        
        try:
            await self.event_repository.append_event(tenant_id, event)
        except ValueError as e:
            if "already exists" in str(e):
                logger.info(f"PlaybookStepCompleted event already exists, skipping")
            else:
                raise
        
        # If last step, emit PlaybookCompleted event
        if is_last_step:
            completed_event_id = uuid4()
            completed_event = ExceptionEventCreateDTO(
                event_id=completed_event_id,
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type="PlaybookCompleted",
                actor_type=actor_type,
                actor_id=actor_id,
                payload={
                    "playbook_id": playbook_id,
                    "total_steps": len(steps),
                    "notes": notes,
                    "actor_type": actor_type.value,
                    "actor_id": actor_id,
                },
            )
            
            try:
                await self.event_repository.append_event(tenant_id, completed_event)
            except ValueError as e:
                if "already exists" in str(e):
                    logger.info(f"PlaybookCompleted event already exists, skipping")
                else:
                    raise
            
            logger.info(
                f"Completed playbook {playbook_id} for exception {exception_id} "
                f"(actor: {actor_type.value}/{actor_id})"
            )
        else:
            logger.info(
                f"Completed step {step_order}/{len(steps)} for exception {exception_id} "
                f"(actor: {actor_type.value}/{actor_id})"
            )
    
    async def skip_step(
        self,
        tenant_id: str,
        exception_id: str,
        playbook_id: int,
        step_order: int,
        actor_type: ActorType,
        actor_id: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> None:
        """
        Skip a playbook step.
        
        Similar to complete_step, but marks the step as skipped rather than completed.
        Still advances to the next step.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            playbook_id: Playbook identifier
            step_order: Step order number to skip
            actor_type: Type of actor skipping the step
            actor_id: Optional actor identifier
            notes: Optional notes about why step was skipped
            
        Raises:
            PlaybookExecutionError: If validation fails
            ValueError: If tenant mismatch or invalid parameters
        """
        # Validate tenant isolation
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        if step_order < 1:
            raise ValueError("step_order must be >= 1")
        
        # Get exception
        exception = await self.exception_repository.get_exception(tenant_id, exception_id)
        if not exception:
            raise PlaybookExecutionError(
                f"Exception {exception_id} not found for tenant {tenant_id}"
            )
        
        # Validate playbook is active
        if exception.current_playbook_id != playbook_id:
            raise PlaybookExecutionError(
                f"Playbook {playbook_id} is not active for exception {exception_id}. "
                f"Current playbook: {exception.current_playbook_id}"
            )
        
        # Get playbook steps
        steps = await self.step_repository.get_steps(playbook_id, tenant_id)
        if not steps:
            raise PlaybookExecutionError(f"Playbook {playbook_id} has no steps")
        
        # Validate step exists
        step = next((s for s in steps if s.step_order == step_order), None)
        if not step:
            raise PlaybookExecutionError(
                f"Step {step_order} not found in playbook {playbook_id}"
            )
        
        # Validate step is next expected step
        expected_step = exception.current_step
        if expected_step is None:
            raise PlaybookExecutionError(
                f"Exception {exception_id} has no current step set"
            )
        
        if step_order != expected_step:
            raise PlaybookExecutionError(
                f"Step {step_order} is not the next expected step. "
                f"Expected step: {expected_step}"
            )
        
        # Check if step already skipped (idempotency)
        events = await self.event_repository.get_events_for_exception(
            tenant_id=tenant_id,
            exception_id=exception_id,
        )
        step_skipped_exists = any(
            e.event_type == "PlaybookStepSkipped"
            and e.payload.get("playbook_id") == playbook_id
            and e.payload.get("step_order") == step_order
            for e in events
        )
        
        if step_skipped_exists:
            logger.info(
                f"Step {step_order} already skipped for exception {exception_id}, "
                "skipping (idempotent)"
            )
            return
        
        # Determine next step
        is_last_step = step_order == len(steps)
        next_step = step_order + 1 if not is_last_step else None
        
        # Update exception state
        await self.exception_repository.update_exception(
            tenant_id=tenant_id,
            exception_id=exception_id,
            updates=ExceptionUpdateDTO(
                current_step=next_step,
            ),
        )
        
        # Emit PlaybookStepSkipped event
        event_id = uuid4()
        event = ExceptionEventCreateDTO(
            event_id=event_id,
            exception_id=exception_id,
            tenant_id=tenant_id,
            event_type="PlaybookStepSkipped",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "playbook_id": playbook_id,
                "step_id": step.step_id,
                "step_order": step_order,
                "step_name": step.name,
                "action_type": step.action_type,
                "is_last_step": is_last_step,
                "notes": notes or "Step skipped",
            },
        )
        
        try:
            await self.event_repository.append_event(tenant_id, event)
        except ValueError as e:
            if "already exists" in str(e):
                logger.info(f"PlaybookStepSkipped event already exists, skipping")
            else:
                raise
        
        # If last step, emit PlaybookCompleted event
        if is_last_step:
            completed_event_id = uuid4()
            completed_event = ExceptionEventCreateDTO(
                event_id=completed_event_id,
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type="PlaybookCompleted",
                actor_type=actor_type,
                actor_id=actor_id,
                payload={
                    "playbook_id": playbook_id,
                    "total_steps": len(steps),
                    "notes": notes or "Playbook completed (with skipped steps)",
                },
            )
            
            try:
                await self.event_repository.append_event(tenant_id, completed_event)
            except ValueError as e:
                if "already exists" in str(e):
                    logger.info(f"PlaybookCompleted event already exists, skipping")
                else:
                    raise
        
        logger.info(
            f"Skipped step {step_order}/{len(steps)} for exception {exception_id} "
            f"(actor: {actor_type.value}/{actor_id})"
        )
    
    async def _execute_tool_step(
        self,
        tenant_id: str,
        exception_id: str,
        step: Any,
        actor_type: ActorType,
        actor_id: Optional[str],
    ) -> Optional[Any]:
        """
        Execute a call_tool step by invoking ToolExecutionService.
        
        Phase 8 P8-9: Integrates tool execution into playbook step completion.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            step: PlaybookStep instance with action_type="call_tool"
            actor_type: Type of actor completing the step
            actor_id: Actor identifier
            
        Returns:
            ToolExecution instance if execution succeeded, None if skipped
            
        Raises:
            PlaybookExecutionError: If tool execution service is not available or execution fails
        """
        if not self.tool_execution_service:
            raise PlaybookExecutionError(
                "ToolExecutionService is required for call_tool steps. "
                "Please provide tool_execution_service when initializing PlaybookExecutionService."
            )
        
        # Extract tool_id and payload from step params
        step_params = step.params if isinstance(step.params, dict) else {}
        tool_id = step_params.get("tool_id")
        # Payload can be in "payload" or "payload_template" field
        payload = step_params.get("payload") or step_params.get("payload_template", {})
        
        if not tool_id:
            raise PlaybookExecutionError(
                f"call_tool step requires 'tool_id' in params. "
                f"Step params: {step_params}"
            )
        
        # Validate tool_id is an integer
        try:
            tool_id_int = int(tool_id)
        except (ValueError, TypeError):
            raise PlaybookExecutionError(
                f"Invalid tool_id in step params: {tool_id}. Must be an integer."
            )
        
        # Validate payload is a dictionary
        if not isinstance(payload, dict):
            raise PlaybookExecutionError(
                f"Invalid payload in step params: {payload}. Must be a dictionary."
            )
        
        # Ensure actor_id is not None
        if actor_id is None:
            actor_id = "unknown"
        
        logger.info(
            f"Executing tool {tool_id_int} for exception {exception_id} "
            f"(step: {step.step_order}, actor: {actor_type.value}/{actor_id})"
        )
        
        try:
            # Execute tool via ToolExecutionService
            tool_execution = await self.tool_execution_service.execute_tool(
                tenant_id=tenant_id,
                tool_id=tool_id_int,
                payload=payload,
                actor_type=actor_type,
                actor_id=actor_id,
                exception_id=exception_id,
            )
            
            logger.info(
                f"Tool execution {tool_execution.id} completed with status {tool_execution.status.value} "
                f"for exception {exception_id}"
            )
            
            return tool_execution
            
        except ToolExecutionServiceError as e:
            error_msg = f"Tool execution failed for tool {tool_id_int}: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PlaybookExecutionError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error during tool execution: {str(e)}"
            logger.error(error_msg, exc_info=True)
            raise PlaybookExecutionError(error_msg) from e

