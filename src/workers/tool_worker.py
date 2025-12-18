"""
ToolWorker for Phase 9.

Subscribes to ToolExecutionRequested events, executes tools via ToolExecutionService,
updates tool execution records, and emits ToolExecutionCompleted or ToolExecutionFailed events.

Reference: docs/phase9-async-scale-mvp.md Section 5.1, Section 5.2
"""

import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from src.events.schema import CanonicalEvent
from src.events.types import ToolExecutionCompleted, ToolExecutionRequested
from src.infrastructure.db.models import ActorType, ToolExecutionStatus
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.event_processing_repository import (
    EventProcessingRepository,
)
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.messaging.broker import Broker
from src.messaging.event_publisher import EventPublisherService
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError
from src.workers.base import AgentWorker

logger = logging.getLogger(__name__)


class ToolWorker(AgentWorker):
    """
    Worker that processes ToolExecutionRequested events and executes tools.
    
    Responsibilities:
    - Subscribe to ToolExecutionRequested events
    - Execute tools via ToolExecutionService
    - Update tool execution records (via ToolExecutionService)
    - Emit ToolExecutionCompleted or ToolExecutionFailed events
    - Ensure idempotency (via base worker)
    - Enforce tenant isolation
    """
    
    def __init__(
        self,
        broker: Broker,
        topics: list[str],
        group_id: str,
        event_publisher: EventPublisherService,
        tool_execution_service: Optional[ToolExecutionService] = None,
        event_processing_repo: Optional[EventProcessingRepository] = None,
    ):
        """
        Initialize ToolWorker.
        
        Args:
            broker: Message broker instance
            topics: List of topic names (should include "exceptions" or similar)
            group_id: Consumer group ID
            event_publisher: EventPublisherService for emitting events
            tool_execution_service: Optional ToolExecutionService (created per-operation if None)
            event_processing_repo: Optional EventProcessingRepository for idempotency
        """
        super().__init__(
            broker=broker,
            topics=topics,
            group_id=group_id,
            worker_name="ToolWorker",
            event_processing_repo=event_processing_repo,
        )
        
        self.event_publisher = event_publisher
        self.tool_execution_service = tool_execution_service  # Optional - created per-operation
        
        logger.info(
            f"Initialized ToolWorker: topics={topics}, group_id={group_id}"
        )
    
    async def process_event(self, event: CanonicalEvent) -> None:
        """
        Process ToolExecutionRequested event.
        
        Phase 9: Hardened idempotency checks:
        - Checks if tool_execution record already exists with SUCCEEDED/FAILED status
        - Skips duplicate ToolExecutionRequested events safely
        - Base worker handles event-level idempotency
        
        Args:
            event: CanonicalEvent (should be ToolExecutionRequested)
            
        Raises:
            ValueError: If event is not ToolExecutionRequested
            Exception: If tool execution fails
        """
        # Validate event type
        if event.event_type != "ToolExecutionRequested":
            raise ValueError(
                f"ToolWorker expects ToolExecutionRequested events, got {event.event_type}"
            )
        
        # Cast to ToolExecutionRequested for type safety
        tool_requested_event = ToolExecutionRequested.model_validate(event.model_dump())
        
        tenant_id = tool_requested_event.tenant_id
        exception_id = tool_requested_event.exception_id
        payload = tool_requested_event.payload
        
        # Extract execution_id from payload (required for idempotency check)
        execution_id_str = payload.get("execution_id")
        if not execution_id_str:
            raise ValueError("ToolExecutionRequested event missing execution_id in payload")
        
        tool_id_str = payload.get("tool_id")
        tool_name = payload.get("tool_name")
        tool_params = payload.get("tool_params") or payload.get("input_payload", {})
        execution_context = payload.get("execution_context", {})
        
        logger.info(
            f"ToolWorker processing ToolExecutionRequested: "
            f"tenant_id={tenant_id}, exception_id={exception_id}, "
            f"execution_id={execution_id_str}, tool_id={tool_id_str}"
        )
        
        # Idempotency check: Check if tool_execution already completed (SUCCEEDED or FAILED)
        async with get_db_session_context() as session:
            tool_exec_repo = ToolExecutionRepository(session)
            is_completed = await tool_exec_repo.is_execution_completed(
                execution_id=execution_id_str,
                tenant_id=tenant_id,
            )
            
            if is_completed:
                logger.info(
                    f"ToolWorker skipping duplicate ToolExecutionRequested: "
                    f"execution_id={execution_id_str} already completed (tenant_id={tenant_id})"
                )
                # Get existing execution to emit completion event with correct status
                existing_execution = await tool_exec_repo.get_execution_by_execution_id(
                    execution_id=execution_id_str,
                    tenant_id=tenant_id,
                )
                
                if existing_execution:
                    # Emit ToolExecutionCompleted event with existing result
                    status = "success" if existing_execution.status == ToolExecutionStatus.SUCCEEDED else "failure"
                    result = existing_execution.output_payload or {} if existing_execution.status == ToolExecutionStatus.SUCCEEDED else {}
                    error_message = existing_execution.error_message if existing_execution.status == ToolExecutionStatus.FAILED else None
                    
                    await self._emit_tool_execution_completed_event(
                        tenant_id=tenant_id,
                        exception_id=exception_id,
                        tool_id=str(existing_execution.tool_id),
                        execution_id=execution_id_str,
                        result=result,
                        status=status,
                        error_message=error_message,
                        correlation_id=tool_requested_event.correlation_id,
                    )
                
                # Skip execution - already completed
                return
        
        # Convert tool_id to integer
        try:
            tool_id = int(tool_id_str) if isinstance(tool_id_str, str) else tool_id_str
        except (ValueError, TypeError):
            raise ValueError(f"Invalid tool_id: {tool_id_str}")
        
        # Execute tool via ToolExecutionService
        # Create service per-operation with session-based repositories
        from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
        from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
        from src.repository.exception_events_repository import ExceptionEventRepository
        from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
        from src.tools.validation import ToolValidationService
        from src.tools.execution_service import ToolExecutionService
        from src.tools.providers import HttpToolProvider, DummyToolProvider
        
        execution_result = None
        execution_id = execution_id_str  # Use execution_id from event
        error_message = None
        
        try:
            # Create service with session-based repositories per-operation
            async with get_db_session_context() as session:
                tool_def_repo = ToolDefinitionRepository(session)
                tool_exec_repo = ToolExecutionRepository(session)
                event_repo = ExceptionEventRepository(session)
                enablement_repo = ToolEnablementRepository(session)
                
                # Create validation service
                validation_service = ToolValidationService(
                    tool_repository=tool_def_repo,
                    enablement_repository=enablement_repo,
                )
                
                tool_execution_service = ToolExecutionService(
                    tool_definition_repository=tool_def_repo,
                    tool_execution_repository=tool_exec_repo,
                    exception_event_repository=event_repo,
                    validation_service=validation_service,
                    http_provider=HttpToolProvider(
                        allowed_schemes=['https'],
                    ),
                    dummy_provider=DummyToolProvider(),
                )
                
                execution = await tool_execution_service.execute_tool(
                    tenant_id=tenant_id,
                    tool_id=tool_id,
                    payload=tool_params,
                    actor_type=ActorType.AGENT,
                    actor_id="ToolWorker",
                    exception_id=exception_id,
                )
            
            execution_result = execution
            # Use execution_id from event (should match existing execution)
            # ToolExecutionService creates a new execution, but we use the event's execution_id
            # for consistency and idempotency
            execution_id = execution_id_str
            
            # Determine status from execution
            if execution.status == ToolExecutionStatus.SUCCEEDED:
                status = "success"
                result = execution.output_payload or {}
            elif execution.status == ToolExecutionStatus.FAILED:
                status = "failure"
                result = {}
                error_message = execution.error_message
            else:
                # Handle other statuses (RUNNING, REQUESTED)
                status = "pending"
                result = {}
            
        except ToolExecutionServiceError as e:
            logger.error(
                f"ToolWorker tool execution service error: {e}",
                exc_info=True,
            )
            status = "error"
            result = {}
            error_message = str(e)
            # Generate execution_id for failed execution
            execution_id = str(uuid4())
        except Exception as e:
            logger.error(
                f"ToolWorker tool execution failed: {e}",
                exc_info=True,
            )
            status = "error"
            result = {}
            error_message = str(e)
            # Generate execution_id for failed execution
            execution_id = str(uuid4())
        
        # Emit ToolExecutionCompleted event (includes both success and failure)
        try:
            await self._emit_tool_execution_completed_event(
                tenant_id=tenant_id,
                exception_id=exception_id,
                tool_id=str(tool_id),
                execution_id=execution_id,
                result=result,
                status=status,
                error_message=error_message,
                correlation_id=tool_requested_event.correlation_id,
            )
        except Exception as e:
            logger.error(
                f"ToolWorker failed to emit ToolExecutionCompleted event: {e}",
                exc_info=True,
            )
            raise
        
        logger.info(
            f"ToolWorker completed processing: exception_id={exception_id}, "
            f"tool_id={tool_id}, status={status}"
        )
    
    async def _emit_tool_execution_completed_event(
        self,
        tenant_id: str,
        exception_id: str,
        tool_id: str,
        execution_id: str,
        result: dict[str, Any],
        status: str,
        error_message: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> None:
        """
        Emit ToolExecutionCompleted event.
        
        Note: ToolExecutionCompleted is used for both success and failure cases.
        The status field indicates the outcome.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            tool_id: Tool identifier
            execution_id: Execution identifier
            result: Execution result
            status: Execution status (success, failure, error)
            error_message: Optional error message
            correlation_id: Optional correlation ID
        """
        # Create ToolExecutionCompleted event
        # Phase 9 P9-21: Ensure correlation_id = exception_id
        final_correlation_id = correlation_id or exception_id
        
        tool_completed_event = ToolExecutionCompleted.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            tool_id=tool_id,
            execution_id=execution_id,
            result=result,
            status=status,
            error_message=error_message,
            correlation_id=final_correlation_id,  # Use exception_id if correlation_id not provided
        )
        
        # Publish event
        await self.event_publisher.publish_event(
            topic="exceptions",
            event=tool_completed_event.model_dump(by_alias=True),
        )
        
        logger.debug(
            f"Emitted ToolExecutionCompleted event: exception_id={exception_id}, "
            f"tool_id={tool_id}, execution_id={execution_id}, status={status}"
        )

