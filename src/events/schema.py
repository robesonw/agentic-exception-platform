"""
Canonical Event Schema for Phase 9.

Defines the base event schema that all events must conform to.
Events are immutable and versioned for schema evolution.
"""

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict


class CanonicalEvent(BaseModel):
    """
    Canonical event schema.
    
    All events in the system must conform to this schema. Events are immutable
    and versioned to support schema evolution.
    
    Fields:
        event_id: Unique event identifier (UUID)
        event_type: Type of event (e.g., "ExceptionIngested", "TriageCompleted")
        tenant_id: Tenant identifier (required for multi-tenant isolation)
        exception_id: Optional exception identifier (links event to exception)
        timestamp: Event timestamp (ISO datetime)
        correlation_id: Optional correlation ID for distributed tracing
        payload: Event payload (dict, contains event-specific data)
        metadata: Optional metadata (dict, contains system-level information)
        version: Event schema version (default: 1, for schema evolution)
    """
    
    model_config = ConfigDict(
        frozen=True,  # Immutability: events cannot be modified after creation
        extra="forbid",  # Reject extra fields
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
        json_encoders={
            datetime: lambda v: v.isoformat(),
        },
    )
    
    event_id: str = Field(
        ...,
        description="Unique event identifier (UUID)",
        examples=["550e8400-e29b-41d4-a716-446655440000"],
    )
    event_type: str = Field(
        ...,
        min_length=1,
        description="Type of event (e.g., 'ExceptionIngested', 'TriageCompleted')",
        examples=["ExceptionIngested"],
    )
    tenant_id: str = Field(
        ...,
        min_length=1,
        description="Tenant identifier (required for multi-tenant isolation)",
        examples=["tenant_001"],
    )
    exception_id: Optional[str] = Field(
        None,
        description="Optional exception identifier (links event to exception)",
        examples=["exc_001"],
    )
    timestamp: datetime = Field(
        ...,
        description="Event timestamp (ISO datetime)",
        examples=[datetime.now(timezone.utc)],
    )
    correlation_id: Optional[str] = Field(
        None,
        description="Optional correlation ID for distributed tracing",
        examples=["corr_123"],
    )
    payload: dict[str, Any] = Field(
        ...,
        description="Event payload (dict, contains event-specific data)",
        examples=[{"data": "example"}],
    )
    metadata: Optional[dict[str, Any]] = Field(
        default=None,
        description="Optional metadata (dict, contains system-level information)",
        examples=[{"source": "api", "user_id": "user_123"}],
    )
    version: int = Field(
        default=1,
        ge=1,
        description="Event schema version (for schema evolution)",
        examples=[1],
    )
    
    @classmethod
    def create(
        cls,
        event_type: str,
        tenant_id: str,
        payload: dict[str, Any],
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        version: int = 1,
        event_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
    ) -> "CanonicalEvent":
        """
        Factory method to create a canonical event with auto-generated fields.
        
        Phase 9 P9-21: correlation_id defaults to exception_id for distributed tracing.
        
        Args:
            event_type: Type of event
            tenant_id: Tenant identifier
            payload: Event payload
            exception_id: Optional exception identifier
            correlation_id: Optional correlation ID (defaults to exception_id if not provided)
            metadata: Optional metadata (correlation_id will be added to metadata)
            version: Event schema version (default: 1)
            event_id: Optional event ID (auto-generated if not provided)
            timestamp: Optional timestamp (set to now if not provided)
            
        Returns:
            CanonicalEvent instance
        """
        # Phase 9 P9-21: correlation_id = exception_id (primary) or event_id
        # If correlation_id not provided, use exception_id if available, otherwise use event_id
        final_correlation_id = correlation_id
        if not final_correlation_id:
            if exception_id:
                final_correlation_id = exception_id
            else:
                # Generate event_id if not provided, use it as correlation_id
                generated_event_id = event_id or str(uuid.uuid4())
                final_correlation_id = generated_event_id
        
        # Ensure metadata includes correlation_id for traceability
        final_metadata = metadata.copy() if metadata else {}
        if "correlation_id" not in final_metadata:
            final_metadata["correlation_id"] = final_correlation_id
        
        return cls(
            event_id=event_id or str(uuid.uuid4()),
            event_type=event_type,
            tenant_id=tenant_id,
            exception_id=exception_id,
            timestamp=timestamp or datetime.now(timezone.utc),
            correlation_id=final_correlation_id,
            payload=payload,
            metadata=final_metadata,
            version=version,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """
        Convert event to dictionary.
        
        Returns:
            Event as dictionary
        """
        return self.model_dump(mode="json")
    
    def to_json(self) -> str:
        """
        Convert event to JSON string.
        
        Returns:
            Event as JSON string
        """
        return self.model_dump_json()

