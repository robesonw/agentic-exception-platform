"""
Data Transfer Objects (DTOs) for repository layer.

These DTOs separate domain types from ORM models and provide
type-safe interfaces for repository operations.
"""

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from src.infrastructure.db.models import (
    ActorType,
    ExceptionSeverity,
    ExceptionStatus,
    TenantStatus,
    ToolExecutionStatus,
)


class ExceptionCreateOrUpdateDTO(BaseModel):
    """
    DTO for creating or updating an exception.
    
    Used by upsert_exception to ensure idempotent writes.
    """

    exception_id: str = Field(..., description="Exception identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    domain: str = Field(..., description="Domain name")
    type: str = Field(..., description="Exception type")
    severity: ExceptionSeverity = Field(..., description="Exception severity level")
    status: ExceptionStatus = Field(default=ExceptionStatus.OPEN, description="Exception processing status")
    source_system: str = Field(..., description="Source system name")
    entity: Optional[str] = Field(None, description="Entity identifier")
    amount: Optional[float] = Field(None, description="Amount associated with exception")
    sla_deadline: Optional[datetime] = Field(None, description="SLA deadline timestamp")
    owner: Optional[str] = Field(None, description="Owner (user or agent identifier)")
    current_playbook_id: Optional[int] = Field(None, description="Current playbook identifier")
    current_step: Optional[int] = Field(None, description="Current step number in playbook")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ExceptionCreateDTO(BaseModel):
    """
    DTO for creating a new exception.
    
    Used by create_exception for explicit creation (non-idempotent).
    """

    exception_id: str = Field(..., description="Exception identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    domain: str = Field(..., description="Domain name")
    type: str = Field(..., description="Exception type")
    severity: ExceptionSeverity = Field(..., description="Exception severity level")
    status: ExceptionStatus = Field(default=ExceptionStatus.OPEN, description="Exception processing status")
    source_system: str = Field(..., description="Source system name")
    entity: Optional[str] = Field(None, description="Entity identifier")
    amount: Optional[float] = Field(None, description="Amount associated with exception")
    sla_deadline: Optional[datetime] = Field(None, description="SLA deadline timestamp")
    owner: Optional[str] = Field(None, description="Owner (user or agent identifier)")
    current_playbook_id: Optional[int] = Field(None, description="Current playbook identifier")
    current_step: Optional[int] = Field(None, description="Current step number in playbook")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ExceptionUpdateDTO(BaseModel):
    """
    DTO for updating an existing exception.
    
    Used by update_exception. All fields are optional.
    """

    domain: Optional[str] = Field(None, description="Domain name")
    type: Optional[str] = Field(None, description="Exception type")
    severity: Optional[ExceptionSeverity] = Field(None, description="Exception severity level")
    status: Optional[ExceptionStatus] = Field(None, description="Exception processing status")
    source_system: Optional[str] = Field(None, description="Source system name")
    entity: Optional[str] = Field(None, description="Entity identifier")
    amount: Optional[float] = Field(None, description="Amount associated with exception")
    sla_deadline: Optional[datetime] = Field(None, description="SLA deadline timestamp")
    owner: Optional[str] = Field(None, description="Owner (user or agent identifier)")
    current_playbook_id: Optional[int] = Field(None, description="Current playbook identifier")
    current_step: Optional[int] = Field(None, description="Current step number in playbook")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ExceptionFilter(BaseModel):
    """
    DTO for filtering exceptions in list queries.
    
    All fields are optional - multiple filters can be combined.
    """

    domain: Optional[str] = Field(None, description="Filter by domain name")
    status: Optional[ExceptionStatus] = Field(None, description="Filter by status")
    severity: Optional[ExceptionSeverity] = Field(None, description="Filter by severity")
    created_from: Optional[datetime] = Field(None, description="Filter by created_at >= created_from")
    created_to: Optional[datetime] = Field(None, description="Filter by created_at <= created_to")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ExceptionEventCreateDTO(BaseModel):
    """
    DTO for creating an exception event.
    
    Used by append_event for append-only event insertion.
    The payload field matches the expected JSON structure for later Kafka migration (Phase 9).
    """

    event_id: UUID = Field(..., description="Event identifier (UUID)")
    exception_id: str = Field(..., description="Exception identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    event_type: str = Field(..., description="Event type (e.g., ExceptionCreated, TriageCompleted)")
    actor_type: ActorType = Field(..., description="Actor type (agent, user, system)")
    actor_id: Optional[str] = Field(None, description="Actor identifier")
    payload: dict[str, Any] = Field(..., description="Event details (JSON) - structure compatible with Kafka migration")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class EventFilter(BaseModel):
    """
    DTO for filtering events in queries.
    
    All fields are optional - multiple filters can be combined.
    """

    event_types: Optional[list[str]] = Field(None, description="Filter by event types (list)")
    actor_type: Optional[ActorType] = Field(None, description="Filter by actor type")
    created_from: Optional[datetime] = Field(None, description="Filter by created_at >= created_from")
    created_to: Optional[datetime] = Field(None, description="Filter by created_at <= created_to")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ExceptionEventDTO(BaseModel):
    """
    DTO for creating an exception event (legacy, kept for backward compatibility).
    
    Used by append_event_if_new to ensure idempotent event insertion.
    For new code, use ExceptionEventCreateDTO.
    """

    event_id: UUID = Field(..., description="Event identifier (UUID)")
    exception_id: str = Field(..., description="Exception identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    event_type: str = Field(..., description="Event type (e.g., ExceptionCreated, TriageCompleted)")
    actor_type: ActorType = Field(..., description="Actor type (agent, user, system)")
    actor_id: Optional[str] = Field(None, description="Actor identifier")
    payload: dict[str, Any] = Field(..., description="Event details (JSON)")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class TenantFilter(BaseModel):
    """
    DTO for filtering tenants in list queries.
    
    All fields are optional - multiple filters can be combined.
    """

    name: Optional[str] = Field(None, description="Filter by tenant name (partial match)")
    status: Optional[TenantStatus] = Field(None, description="Filter by tenant status")
    created_from: Optional[datetime] = Field(None, description="Filter by created_at >= created_from")
    created_to: Optional[datetime] = Field(None, description="Filter by created_at <= created_to")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class PlaybookCreateDTO(BaseModel):
    """
    DTO for creating a new playbook.
    
    Used by create_playbook for playbook creation.
    """

    name: str = Field(..., min_length=1, description="Playbook name")
    version: int = Field(..., ge=1, description="Playbook version number")
    conditions: dict[str, Any] = Field(..., description="Matching rules (JSON)")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class PlaybookFilter(BaseModel):
    """
    DTO for filtering playbooks in list queries.
    
    All fields are optional - multiple filters can be combined.
    """

    name: Optional[str] = Field(None, description="Filter by playbook name (case-insensitive substring match)")
    version: Optional[int] = Field(None, ge=1, description="Filter by playbook version")
    created_from: Optional[datetime] = Field(None, description="Filter by created_at >= created_from")
    created_to: Optional[datetime] = Field(None, description="Filter by created_at <= created_to")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class PlaybookStepCreateDTO(BaseModel):
    """
    DTO for creating a new playbook step.
    
    Used by create_step for step creation.
    Note: step_order is automatically assigned based on existing steps.
    """

    name: str = Field(..., min_length=1, description="Step name")
    action_type: str = Field(..., min_length=1, description="Action type (e.g., 'notify', 'force_settle', 'call_tool', 'escalate')")
    params: dict[str, Any] = Field(..., description="Step parameters (JSON)")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ToolDefinitionCreateDTO(BaseModel):
    """
    DTO for creating a new tool definition.
    
    Used by create_tool for tool creation.
    Supports both global tools (tenant_id=None) and tenant-scoped tools.
    """

    name: str = Field(..., min_length=1, description="Tool name")
    type: str = Field(..., min_length=1, description="Tool type (e.g., 'webhook', 'rest', 'email', 'workflow')")
    config: dict[str, Any] = Field(..., description="Tool configuration (endpoint, auth, schema) as JSON")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ToolDefinitionFilter(BaseModel):
    """
    DTO for filtering tool definitions in list queries.
    
    All fields are optional - multiple filters can be combined.
    """

    name: Optional[str] = Field(None, description="Filter by tool name (case-insensitive substring match)")
    type: Optional[str] = Field(None, description="Filter by tool type (exact match)")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ToolExecutionCreateDTO(BaseModel):
    """
    DTO for creating a new tool execution record.
    
    Phase 8 P8-3: Used by ToolExecutionRepository.create_execution.
    """

    tenant_id: str = Field(..., description="Tenant identifier")
    tool_id: int = Field(..., ge=1, description="Tool definition identifier")
    exception_id: Optional[str] = Field(None, description="Exception identifier (nullable)")
    status: ToolExecutionStatus = Field(
        default=ToolExecutionStatus.REQUESTED, description="Execution status"
    )
    requested_by_actor_type: ActorType = Field(..., description="Actor type who requested execution")
    requested_by_actor_id: str = Field(..., min_length=1, description="Actor identifier who requested execution")
    input_payload: dict[str, Any] = Field(..., description="Input payload (JSON) passed to tool")
    output_payload: Optional[dict[str, Any]] = Field(None, description="Output payload (JSON) from tool execution")
    error_message: Optional[str] = Field(None, description="Error message if execution failed")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ToolExecutionUpdateDTO(BaseModel):
    """
    DTO for updating a tool execution record.
    
    Phase 8 P8-3: Used by ToolExecutionRepository.update_execution.
    """

    status: Optional[ToolExecutionStatus] = Field(None, description="Execution status")
    output_payload: Optional[dict[str, Any]] = Field(None, description="Output payload (JSON) from tool execution")
    error_message: Optional[str] = Field(None, description="Error message if execution failed")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True


class ToolExecutionFilter(BaseModel):
    """
    DTO for filtering tool executions in list queries.
    
    Phase 8 P8-3: All fields are optional - multiple filters can be combined.
    """

    tool_id: Optional[int] = Field(None, ge=1, description="Filter by tool ID")
    exception_id: Optional[str] = Field(None, description="Filter by exception ID")
    status: Optional[ToolExecutionStatus] = Field(None, description="Filter by execution status")
    actor_type: Optional[ActorType] = Field(None, description="Filter by actor type")
    actor_id: Optional[str] = Field(None, description="Filter by actor ID")

    class Config:
        """Pydantic configuration."""

        use_enum_values = True

