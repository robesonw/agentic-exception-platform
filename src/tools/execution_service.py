"""
Tool Execution Service for Phase 8.

Orchestrates tool execution with validation, persistence, and event emission.
Reference: docs/phase8-tools-mvp.md Section 4.2
"""

import logging
from typing import Any, Optional
from uuid import UUID, uuid4

from src.infrastructure.db.models import ActorType, ToolDefinition, ToolExecution, ToolExecutionStatus
from src.repository.exception_events_repository import ExceptionEventRepository
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.repository.dto import ExceptionEventCreateDTO, ToolExecutionCreateDTO, ToolExecutionUpdateDTO
from src.tools.provider import (
    DummyToolProvider,
    HttpToolProvider,
    ToolProvider,
    ToolProviderError,
)
from src.tools.validation import ToolValidationService, ToolValidationError

logger = logging.getLogger(__name__)


class ToolExecutionServiceError(Exception):
    """Base exception for tool execution service errors."""

    pass


class ToolExecutionService:
    """
    Service for executing tools with full lifecycle management.
    
    Responsibilities:
    - Load and validate tool definitions
    - Validate payloads and tenant access
    - Create and update execution records
    - Route to appropriate providers
    - Emit execution events
    - Handle errors gracefully
    """

    def __init__(
        self,
        tool_definition_repository: ToolDefinitionRepository,
        tool_execution_repository: ToolExecutionRepository,
        exception_event_repository: ExceptionEventRepository,
        validation_service: ToolValidationService,
        http_provider: Optional[HttpToolProvider] = None,
        dummy_provider: Optional[DummyToolProvider] = None,
    ):
        """
        Initialize tool execution service.
        
        Args:
            tool_definition_repository: Repository for tool definitions
            tool_execution_repository: Repository for execution records
            exception_event_repository: Repository for exception events
            validation_service: Service for validation (should have enablement_repository configured)
            http_provider: HTTP tool provider (created if None)
            dummy_provider: Dummy tool provider (created if None)
        """
        self.tool_definition_repository = tool_definition_repository
        self.tool_execution_repository = tool_execution_repository
        self.exception_event_repository = exception_event_repository
        self.validation_service = validation_service
        
        # Initialize providers
        # P8-14: HttpToolProvider with security settings (URL allow-list enforcement)
        # For production, allowed_domains should be configured via environment or config
        allowed_domains = self._get_allowed_domains()
        self.http_provider = http_provider or HttpToolProvider(
            allowed_domains=allowed_domains,
            allowed_schemes=['https'],  # Enforce HTTPS by default
        )
        self.dummy_provider = dummy_provider or DummyToolProvider()
        
        # Map tool types to providers
        self._provider_map: dict[str, ToolProvider] = {
            "http": self.http_provider,
            "rest": self.http_provider,
            "webhook": self.http_provider,
            "https": self.http_provider,
        }
    
    def _get_allowed_domains(self) -> Optional[list[str]]:
        """
        Get allowed domains for HTTP tool endpoints from environment.
        
        P8-14: Reads TOOL_ALLOWED_DOMAINS env var (comma-separated list).
        If not set, returns None (allows any domain - not recommended for production).
        
        Returns:
            List of allowed domains or None if not configured
        """
        import os
        allowed_domains_str = os.getenv("TOOL_ALLOWED_DOMAINS")
        if allowed_domains_str:
            return [domain.strip() for domain in allowed_domains_str.split(",") if domain.strip()]
        return None
    
    def _get_provider(self, tool_type: str) -> ToolProvider:
        """
        Get appropriate provider for tool type.
        
        Args:
            tool_type: Tool type string
            
        Returns:
            ToolProvider instance
            
        Raises:
            ToolExecutionServiceError: If no provider supports the tool type
        """
        tool_type_lower = tool_type.lower()
        
        # Check provider map first
        if tool_type_lower in self._provider_map:
            return self._provider_map[tool_type_lower]
        
        # Check if any provider supports this type
        for provider in [self.http_provider, self.dummy_provider]:
            if provider.supports_tool_type(tool_type):
                return provider
        
        # Fallback to dummy provider (supports all types)
        logger.warning(
            f"No specific provider found for tool type '{tool_type}', using DummyToolProvider"
        )
        return self.dummy_provider

    async def execute_tool(
        self,
        tenant_id: str,
        tool_id: int,
        payload: dict[str, Any],
        actor_type: ActorType,
        actor_id: str,
        exception_id: Optional[str] = None,
    ) -> ToolExecution:
        """
        Execute a tool with full lifecycle management.
        
        Workflow:
        1. Load tool definition
        2. Validate via ToolValidationService (payload, enablement, scope)
        3. Create tool_execution record (status: REQUESTED)
        4. Emit ToolExecutionRequested event
        5. Update status to RUNNING
        6. Route to appropriate provider
        7. Update status to SUCCEEDED/FAILED with output/error
        8. Emit ToolExecutionCompleted/Failed event
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool definition identifier
            payload: Input payload for the tool
            actor_type: Type of actor requesting execution
            actor_id: Identifier of the actor
            exception_id: Optional exception identifier (if linked to exception)
            
        Returns:
            ToolExecution instance with final status
            
        Raises:
            ToolExecutionServiceError: If execution fails
        """
        # Step 1: Load tool definition
        tool_definition = await self.tool_definition_repository.get_tool(
            tool_id=tool_id, tenant_id=tenant_id
        )
        if tool_definition is None:
            raise ToolExecutionServiceError(
                f"Tool {tool_id} not found or not accessible to tenant {tenant_id}"
            )
        
        # Step 2: Validate via ToolValidationService
        try:
            # Validate payload against input schema
            await self.validation_service.validate_payload(tool_id, payload, tenant_id=tenant_id)
            
            # Check tool is enabled for tenant
            is_enabled = await self.validation_service.check_tool_enabled(tenant_id, tool_id)
            if not is_enabled:
                raise ToolExecutionServiceError(
                    f"Tool {tool_id} is disabled for tenant {tenant_id}"
                )
            
            # Check tenant scope
            await self.validation_service.check_tenant_scope(tenant_id, tool_id)
            
        except ToolValidationError as e:
            raise ToolExecutionServiceError(f"Tool validation failed: {e}") from e
        
        # Step 3: Create tool_execution record (status: REQUESTED)
        execution_create_dto = ToolExecutionCreateDTO(
            tenant_id=tenant_id,
            tool_id=tool_id,
            exception_id=exception_id,
            status=ToolExecutionStatus.REQUESTED,
            requested_by_actor_type=actor_type,
            requested_by_actor_id=actor_id,
            input_payload=payload,
        )
        
        execution = await self.tool_execution_repository.create_execution(execution_create_dto)
        execution_id = execution.id
        
        logger.info(
            f"Created tool execution {execution_id} for tool {tool_id} "
            f"(tenant: {tenant_id}, status: REQUESTED)"
        )
        
        # Step 4: Emit ToolExecutionRequested event
        await self._emit_execution_requested_event(
            tenant_id=tenant_id,
            execution_id=execution_id,
            tool_id=tool_id,
            exception_id=exception_id,
            actor_type=actor_type,
            actor_id=actor_id,
        )
        
        # Step 5: Update status to RUNNING
        execution = await self.tool_execution_repository.update_execution(
            execution_id=execution_id,
            tenant_id=tenant_id,
            update_data=ToolExecutionUpdateDTO(status=ToolExecutionStatus.RUNNING),
        )
        if execution is None:
            raise ToolExecutionServiceError(
                f"Failed to update execution {execution_id} to RUNNING status"
            )
        
        logger.debug(f"Updated tool execution {execution_id} to RUNNING status")
        
        # Step 6: Route to appropriate provider and execute
        try:
            provider = self._get_provider(tool_definition.type)
            logger.debug(
                f"Executing tool {tool_id} via {provider.__class__.__name__} "
                f"(type: {tool_definition.type})"
            )
            
            # P8-14: Redact secrets from payload for logging
            from src.tools.security import redact_secrets_from_dict, safe_log_payload
            redacted_payload = redact_secrets_from_dict(payload)
            logger.debug(
                f"Executing tool {tool_id} with payload (secrets redacted): {safe_log_payload(redacted_payload)}"
            )
            
            # Execute tool
            output = await provider.execute(tool_definition, payload)
            
            # Step 7: Update status to SUCCEEDED with output
            execution = await self.tool_execution_repository.update_execution(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data=ToolExecutionUpdateDTO(
                    status=ToolExecutionStatus.SUCCEEDED,
                    output_payload=output,
                ),
            )
            if execution is None:
                raise ToolExecutionServiceError(
                    f"Failed to update execution {execution_id} to SUCCEEDED status"
                )
            
            logger.info(
                f"Tool execution {execution_id} completed successfully "
                f"(tool: {tool_id}, tenant: {tenant_id})"
            )
            
            # Step 8: Emit ToolExecutionCompleted event
            await self._emit_execution_completed_event(
                tenant_id=tenant_id,
                execution_id=execution_id,
                tool_id=tool_id,
                exception_id=exception_id,
                output=output,
            )
            
            return execution
        
        except ToolProviderError as e:
            # Step 7 (error case): Update status to FAILED with error message
            error_message = str(e)
            execution = await self.tool_execution_repository.update_execution(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data=ToolExecutionUpdateDTO(
                    status=ToolExecutionStatus.FAILED,
                    error_message=error_message,
                ),
            )
            if execution is None:
                raise ToolExecutionServiceError(
                    f"Failed to update execution {execution_id} to FAILED status"
                )
            
            logger.error(
                f"Tool execution {execution_id} failed "
                f"(tool: {tool_id}, tenant: {tenant_id}): {error_message}"
            )
            
            # Step 8 (error case): Emit ToolExecutionFailed event
            await self._emit_execution_failed_event(
                tenant_id=tenant_id,
                execution_id=execution_id,
                tool_id=tool_id,
                exception_id=exception_id,
                error_message=error_message,
            )
            
            raise ToolExecutionServiceError(f"Tool execution failed: {error_message}") from e
        
        except Exception as e:
            # Handle unexpected errors
            error_message = f"Unexpected error during tool execution: {str(e)}"
            logger.exception(
                f"Unexpected error in tool execution {execution_id} "
                f"(tool: {tool_id}, tenant: {tenant_id})"
            )
            
            # Update status to FAILED
            execution = await self.tool_execution_repository.update_execution(
                execution_id=execution_id,
                tenant_id=tenant_id,
                update_data=ToolExecutionUpdateDTO(
                    status=ToolExecutionStatus.FAILED,
                    error_message=error_message,
                ),
            )
            
            # Emit failed event
            await self._emit_execution_failed_event(
                tenant_id=tenant_id,
                execution_id=execution_id,
                tool_id=tool_id,
                exception_id=exception_id,
                error_message=error_message,
            )
            
            raise ToolExecutionServiceError(error_message) from e

    async def _emit_execution_requested_event(
        self,
        tenant_id: str,
        execution_id: UUID,
        tool_id: int,
        exception_id: Optional[str],
        actor_type: ActorType,
        actor_id: str,
    ) -> None:
        """Emit ToolExecutionRequested event."""
        event_dto = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id or f"tool_exec_{execution_id}",  # Use execution ID if no exception
            tenant_id=tenant_id,
            event_type="ToolExecutionRequested",
            actor_type=actor_type,
            actor_id=actor_id,
            payload={
                "execution_id": str(execution_id),
                "tool_id": tool_id,
                "status": "requested",
            },
        )
        
        await self.exception_event_repository.append_event_if_new(event_dto)
        logger.debug(f"Emitted ToolExecutionRequested event for execution {execution_id}")

    async def _emit_execution_completed_event(
        self,
        tenant_id: str,
        execution_id: UUID,
        tool_id: int,
        exception_id: Optional[str],
        output: dict[str, Any],
    ) -> None:
        """Emit ToolExecutionCompleted event."""
        # P8-14: Redact secrets from output using enhanced security utilities
        from src.tools.security import redact_secrets_from_dict
        redacted_output = redact_secrets_from_dict(output)
        
        event_dto = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id or f"tool_exec_{execution_id}",
            tenant_id=tenant_id,
            event_type="ToolExecutionCompleted",
            actor_type=ActorType.SYSTEM,
            actor_id="ToolExecutionService",
            payload={
                "execution_id": str(execution_id),
                "tool_id": tool_id,
                "status": "succeeded",
                "output": redacted_output,
            },
        )
        
        await self.exception_event_repository.append_event_if_new(event_dto)
        logger.debug(f"Emitted ToolExecutionCompleted event for execution {execution_id}")

    async def _emit_execution_failed_event(
        self,
        tenant_id: str,
        execution_id: UUID,
        tool_id: int,
        exception_id: Optional[str],
        error_message: str,
    ) -> None:
        """Emit ToolExecutionFailed event."""
        event_dto = ExceptionEventCreateDTO(
            event_id=uuid4(),
            exception_id=exception_id or f"tool_exec_{execution_id}",
            tenant_id=tenant_id,
            event_type="ToolExecutionFailed",
            actor_type=ActorType.SYSTEM,
            actor_id="ToolExecutionService",
            payload={
                "execution_id": str(execution_id),
                "tool_id": tool_id,
                "status": "failed",
                "error": error_message,
            },
        )
        
        await self.exception_event_repository.append_event_if_new(event_dto)
        logger.debug(f"Emitted ToolExecutionFailed event for execution {execution_id}")

    async def close(self) -> None:
        """Close providers and cleanup resources."""
        if hasattr(self.http_provider, "close"):
            await self.http_provider.close()
        # DummyToolProvider doesn't need cleanup

