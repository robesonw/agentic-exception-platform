"""
SQLAlchemy database models for Phase 6 Persistence MVP.

This module defines all database tables and models as specified in
docs/phase6-persistence-mvp.md Section 4 (Schema Overview).

All models use async-friendly SQLAlchemy with PostgreSQL-specific types.
"""

from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgresUUID
from sqlalchemy.orm import declarative_base, relationship

# Async-friendly declarative base for SQLAlchemy
Base = declarative_base()


# ============================================================================
# Enums
# ============================================================================


class TenantStatus(PyEnum):
    """Tenant lifecycle status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class PackStatus(PyEnum):
    """Pack lifecycle status for Phase 12 onboarding."""

    DRAFT = "draft"
    ACTIVE = "active"
    DEPRECATED = "deprecated"


class ExceptionSeverity(PyEnum):
    """Exception severity levels (database enum)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ExceptionStatus(PyEnum):
    """Exception processing status (database enum)."""

    OPEN = "open"
    ANALYZING = "analyzing"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class ActorType(PyEnum):
    """Actor type for exception events."""

    AGENT = "agent"
    USER = "user"
    SYSTEM = "system"


class ToolExecutionStatus(PyEnum):
    """Tool execution status."""

    REQUESTED = "requested"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


# ============================================================================
# Models
# ============================================================================


class Tenant(Base):
    """
    Tenant metadata and lifecycle management.
    
    Matches docs/phase6-persistence-mvp.md Section 4.1 (tenant Table).
    """

    __tablename__ = "tenant"

    tenant_id = Column(String, primary_key=True, doc="Tenant identifier (UUID or human-readable)")
    name = Column(String, nullable=False, doc="Tenant name")
    status = Column(
        Enum(
            TenantStatus,
            name="tenant_status",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=TenantStatus.ACTIVE,
        doc="Tenant lifecycle status",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when tenant was created",
    )
    created_by = Column(
        String,
        nullable=True,
        doc="User identifier who created the tenant (Phase 12)",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when tenant was last updated",
    )

    # Relationships
    exceptions = relationship("Exception", back_populates="tenant", cascade="all, delete-orphan")
    tenant_policy_packs = relationship(
        "TenantPolicyPackVersion", back_populates="tenant", cascade="all, delete-orphan"
    )
    playbooks = relationship("Playbook", back_populates="tenant", cascade="all, delete-orphan")
    tool_definitions = relationship(
        "ToolDefinition", back_populates="tenant", cascade="all, delete-orphan"
    )
    tool_executions = relationship(
        "ToolExecution", back_populates="tenant", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Tenant(tenant_id={self.tenant_id!r}, name={self.name!r}, status={self.status.value})>"


class DomainPackVersion(Base):
    """
    Versioned domain packs for global logic.
    
    Matches docs/phase6-persistence-mvp.md Section 4.2 (domain_pack_version Table).
    """

    __tablename__ = "domain_pack_version"

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    domain = Column(String, nullable=False, index=True, doc="Domain name (e.g., Finance, Healthcare)")
    version = Column(Integer, nullable=False, doc="Domain pack version number")
    pack_json = Column(JSONB, nullable=False, doc="Actual Domain Pack JSON")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when this version was created",
    )

    # Unique constraint on domain + version
    __table_args__ = (UniqueConstraint("domain", "version", name="uq_domain_pack_version"),)

    def __repr__(self) -> str:
        return f"<DomainPackVersion(id={self.id}, domain={self.domain!r}, version={self.version})>"


class TenantPolicyPackVersion(Base):
    """
    Tenant-specific logic overlays.
    
    Matches docs/phase6-persistence-mvp.md Section 4.3 (tenant_policy_pack_version Table).
    """

    __tablename__ = "tenant_policy_pack_version"

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    version = Column(Integer, nullable=False, doc="Tenant policy pack version number")
    pack_json = Column(JSONB, nullable=False, doc="Tenant Policy Pack JSON")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when this version was created",
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="tenant_policy_packs")

    # Unique constraint on tenant_id + version
    __table_args__ = (UniqueConstraint("tenant_id", "version", name="uq_tenant_policy_pack_version"),)

    def __repr__(self) -> str:
        return f"<TenantPolicyPackVersion(id={self.id}, tenant_id={self.tenant_id!r}, version={self.version})>"


class Exception(Base):
    """
    System of record for all current exception information.
    
    Matches docs/phase6-persistence-mvp.md Section 4.4 (exception Table).
    """

    __tablename__ = "exception"

    exception_id = Column(String, primary_key=True, doc="Exception identifier (e.g., EX-2025-1234)")
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    domain = Column(String, nullable=False, index=True, doc="Domain name")
    type = Column(String, nullable=False, doc="Exception type")
    severity = Column(
        Enum(
            ExceptionSeverity,
            name="exception_severity",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        doc="Exception severity level",
    )
    status = Column(
        Enum(
            ExceptionStatus,
            name="exception_status",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ExceptionStatus.OPEN,
        doc="Exception processing status",
    )
    source_system = Column(String, nullable=False, doc="Source system name (e.g., Murex, ClaimsApp)")
    entity = Column(String, nullable=True, doc="Entity identifier (e.g., counterparty, patient, account)")
    amount = Column(Numeric(precision=18, scale=2), nullable=True, doc="Amount associated with exception")
    sla_deadline = Column(DateTime(timezone=True), nullable=True, doc="SLA deadline timestamp")
    owner = Column(String, nullable=True, doc="Owner (user or agent identifier)")
    current_playbook_id = Column(
        Integer,
        ForeignKey("playbook.playbook_id", ondelete="SET NULL"),
        nullable=True,
        doc="Current playbook identifier",
    )
    current_step = Column(Integer, nullable=True, doc="Current step number in playbook")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when exception was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when exception was last updated",
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="exceptions")
    current_playbook = relationship("Playbook", foreign_keys=[current_playbook_id])
    events = relationship("ExceptionEvent", back_populates="exception", cascade="all, delete-orphan")
    pii_redaction_metadata = relationship(
        "PIIRedactionMetadata",
        back_populates="exception",
        cascade="all, delete-orphan",
        uselist=False,
    )

    # Indexes as specified in docs/phase6-persistence-mvp.md Section 4.4
    __table_args__ = (
        Index("idx_exception_tenant_domain_created", "tenant_id", "domain", "created_at"),
        Index("idx_exception_status_severity", "status", "severity"),
        UniqueConstraint("exception_id", "tenant_id", name="uq_exception_tenant"),
    )

    def __repr__(self) -> str:
        return (
            f"<Exception(exception_id={self.exception_id!r}, tenant_id={self.tenant_id!r}, "
            f"domain={self.domain!r}, severity={self.severity.value}, status={self.status.value})>"
        )


class PIIRedactionMetadata(Base):
    """
    PII redaction metadata for exceptions.
    
    Phase 9 P9-24: Stores metadata about PII fields that were redacted at ingestion.
    """
    
    __tablename__ = "pii_redaction_metadata"
    
    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    exception_id = Column(
        String,
        ForeignKey("exception.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Exception identifier",
    )
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    redacted_fields = Column(
        JSONB,
        nullable=False,
        doc="List of field paths that were redacted (e.g., ['email', 'phone', 'address.street'])",
    )
    redaction_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Number of fields redacted",
    )
    redaction_placeholder = Column(
        String,
        nullable=False,
        default="[REDACTED]",
        doc="Placeholder used for redacted values",
    )
    redacted_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when redaction occurred",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    
    # Relationships
    exception = relationship("Exception", back_populates="pii_redaction_metadata")
    tenant = relationship("Tenant")
    
    __table_args__ = (
        Index("idx_pii_redaction_exception", "exception_id"),
        Index("idx_pii_redaction_tenant", "tenant_id"),
    )
    
    def __repr__(self) -> str:
        return (
            f"<PIIRedactionMetadata(exception_id={self.exception_id!r}, "
            f"tenant_id={self.tenant_id!r}, redaction_count={self.redaction_count})>"
        )


class ExceptionEvent(Base):
    """
    Append-only event log for all lifecycle, agent, user, and system events.
    
    Matches docs/phase6-persistence-mvp.md Section 4.5 (exception_event Table).
    """

    __tablename__ = "exception_event"

    event_id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Event identifier (UUID)",
    )
    exception_id = Column(
        String,
        ForeignKey("exception.exception_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Exception identifier",
    )
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    event_type = Column(
        String,
        nullable=False,
        index=True,
        doc="Event type (e.g., ExceptionCreated, TriageCompleted, LLMDecisionProposed)",
    )
    actor_type = Column(
        Enum(
            ActorType,
            name="actor_type",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        doc="Actor type (agent, user, system)",
    )
    actor_id = Column(String, nullable=True, doc="Actor identifier")
    payload = Column(JSONB, nullable=False, doc="Event details (JSON)")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        doc="Timestamp when event occurred",
    )

    # Relationships
    exception = relationship("Exception", back_populates="events")
    tenant = relationship("Tenant")

    # Indexes as specified in docs/phase6-persistence-mvp.md Section 4.5
    __table_args__ = (
        Index("idx_exception_event_exception_created", "exception_id", "created_at"),
        Index("idx_exception_event_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ExceptionEvent(event_id={self.event_id}, exception_id={self.exception_id!r}, "
            f"event_type={self.event_type!r}, actor_type={self.actor_type.value})>"
        )


class Playbook(Base):
    """
    Playbook definitions for exception resolution (Phase 7 preparation).
    
    Matches docs/phase6-persistence-mvp.md Section 4.6 (playbook Table).
    """

    __tablename__ = "playbook"

    playbook_id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    name = Column(String, nullable=False, doc="Playbook name")
    version = Column(Integer, nullable=False, doc="Playbook version number")
    conditions = Column(JSONB, nullable=False, doc="Matching rules (JSON)")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when playbook was created",
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="playbooks")
    steps = relationship("PlaybookStep", back_populates="playbook", cascade="all, delete-orphan")
    exceptions = relationship("Exception", foreign_keys="Exception.current_playbook_id")

    def __repr__(self) -> str:
        return (
            f"<Playbook(playbook_id={self.playbook_id}, tenant_id={self.tenant_id!r}, "
            f"name={self.name!r}, version={self.version})>"
        )


class PlaybookStep(Base):
    """
    Playbook step definitions (Phase 7 preparation).
    
    Matches docs/phase6-persistence-mvp.md Section 4.6 (playbook_step Table).
    """

    __tablename__ = "playbook_step"

    step_id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    playbook_id = Column(
        Integer,
        ForeignKey("playbook.playbook_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Playbook identifier",
    )
    step_order = Column(Integer, nullable=False, index=True, doc="Step order number")
    name = Column(String, nullable=False, doc="Step name")
    action_type = Column(
        String,
        nullable=False,
        doc="Action type (e.g., 'notify', 'force_settle', 'call_tool', 'escalate')",
    )
    params = Column(JSONB, nullable=False, doc="Step parameters (JSON)")
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when step was created",
    )

    # Relationships
    playbook = relationship("Playbook", back_populates="steps")

    def __repr__(self) -> str:
        return (
            f"<PlaybookStep(step_id={self.step_id}, playbook_id={self.playbook_id}, "
            f"step_order={self.step_order}, name={self.name!r}, action_type={self.action_type!r})>"
        )


class ToolDefinition(Base):
    """
    Tool definitions for Phase 8 preparation.
    
    Matches docs/phase6-persistence-mvp.md Section 4.7 (tool_definition Table).
    """

    __tablename__ = "tool_definition"

    tool_id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    name = Column(String, nullable=False, doc="Tool name")
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        doc="Tenant identifier (null for global tools)",
    )
    type = Column(
        String,
        nullable=False,
        doc="Tool type (e.g., 'webhook', 'rest', 'email', 'workflow')",
    )
    config = Column(
        JSONB,
        nullable=False,
        doc="Tool configuration (endpoint, auth, schema) as JSON",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when tool was created",
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="tool_definitions")

    def __repr__(self) -> str:
        return (
            f"<ToolDefinition(tool_id={self.tool_id}, name={self.name!r}, "
            f"tenant_id={self.tenant_id!r}, type={self.type!r})>"
        )


class ToolExecution(Base):
    """
    Tool execution records for Phase 8.
    
    Matches docs/phase8-tools-mvp.md Section 3.1 (tool_execution table).
    """

    __tablename__ = "tool_execution"

    id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Primary key (UUID)",
    )
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    tool_id = Column(
        Integer,
        ForeignKey("tool_definition.tool_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tool definition identifier",
    )
    exception_id = Column(
        String,
        ForeignKey("exception.exception_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        doc="Exception identifier (nullable, if execution is linked to exception)",
    )
    status = Column(
        Enum(
            ToolExecutionStatus,
            name="tool_execution_status",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=ToolExecutionStatus.REQUESTED,
        doc="Execution status",
    )
    requested_by_actor_type = Column(
        Enum(
            ActorType,
            name="actor_type",
            create_constraint=False,  # Reuse existing enum
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        doc="Actor type who requested execution",
    )
    requested_by_actor_id = Column(
        String,
        nullable=False,
        doc="Actor identifier who requested execution",
    )
    input_payload = Column(
        JSONB,
        nullable=False,
        doc="Input payload (JSON) passed to tool",
    )
    output_payload = Column(
        JSONB,
        nullable=True,
        doc="Output payload (JSON) from tool execution",
    )
    error_message = Column(
        String,
        nullable=True,
        doc="Error message if execution failed",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when execution was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when execution was last updated",
    )

    # Relationships
    tenant = relationship("Tenant", back_populates="tool_executions")
    tool_definition = relationship("ToolDefinition")
    exception = relationship("Exception")

    # Indexes for common query patterns
    __table_args__ = (
        Index("idx_tool_execution_tenant_tool", "tenant_id", "tool_id"),
        Index("idx_tool_execution_tenant_exception", "tenant_id", "exception_id"),
        Index("idx_tool_execution_tenant_status", "tenant_id", "status"),
        Index("idx_tool_execution_tenant_created", "tenant_id", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ToolExecution(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"tool_id={self.tool_id}, status={self.status.value})>"
        )


class EventLog(Base):
    """
    Canonical event log for event store (append-only).
    
    Phase 9 P9-4: Stores all canonical events for event sourcing and audit.
    """
    __tablename__ = "event_log"
    
    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    exception_id = Column(String, ForeignKey("exception.exception_id", ondelete="SET NULL"), nullable=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    correlation_id = Column(String, nullable=True, index=True)
    payload = Column(JSONB, nullable=False)
    event_metadata = Column("metadata", JSONB, nullable=True)
    version = Column(Integer, nullable=False, server_default="1")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Indexes for common queries
    __table_args__ = (
        Index("idx_event_log_tenant_timestamp", "tenant_id", "timestamp"),
        Index("idx_event_log_exception_timestamp", "exception_id", "timestamp"),
        Index("idx_event_log_tenant_type_timestamp", "tenant_id", "event_type", "timestamp"),
    )


class EventProcessingStatus(PyEnum):
    """Event processing status."""
    
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class EventProcessing(Base):
    """
    Event processing tracking for idempotency.
    
    Phase 9 P9-12: Tracks event processing status to ensure idempotency.
    """
    __tablename__ = "event_processing"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False, index=True)
    worker_type = Column(String, nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    exception_id = Column(String, ForeignKey("exception.exception_id", ondelete="SET NULL"), nullable=True, index=True)
    status = Column(Enum(EventProcessingStatus, name="event_processing_status", create_type=True), nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    error_message = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Unique constraint on (event_id, worker_type)
    __table_args__ = (
        UniqueConstraint("event_id", "worker_type", name="uq_event_processing_event_worker"),
        Index("idx_event_processing_tenant_worker", "tenant_id", "worker_type"),
        Index("idx_event_processing_exception_worker", "exception_id", "worker_type"),
        Index("idx_event_processing_status", "status", "processed_at"),
    )


class DLQStatus(PyEnum):
    """DLQ entry lifecycle status (Phase 10 P10-4)."""
    PENDING = "pending"
    RETRYING = "retrying"
    DISCARDED = "discarded"
    SUCCEEDED = "succeeded"


class DeadLetterEvent(Base):
    """
    Dead Letter Queue event entry.

    Phase 9 P9-15: Stores events that failed processing after max retries.
    Phase 10 P10-4: Enhanced with status tracking for DLQ management.
    """
    __tablename__ = "dead_letter_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, nullable=False, unique=True, index=True)
    event_type = Column(String, nullable=False, index=True)
    tenant_id = Column(String, ForeignKey("tenant.tenant_id", ondelete="CASCADE"), nullable=False, index=True)
    exception_id = Column(String, ForeignKey("exception.exception_id", ondelete="SET NULL"), nullable=True, index=True)
    original_topic = Column(String, nullable=False)
    failure_reason = Column(String, nullable=False)
    retry_count = Column(Integer, nullable=False, server_default="0")
    worker_type = Column(String, nullable=False, index=True)
    payload = Column(JSONB, nullable=False)
    event_metadata = Column("metadata", JSONB, nullable=True, server_default="{}")
    failed_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    # Phase 10 P10-4: DLQ management fields
    status = Column(String(20), nullable=False, server_default="pending", index=True)
    retried_at = Column(DateTime(timezone=True), nullable=True)
    discarded_at = Column(DateTime(timezone=True), nullable=True)
    discarded_by = Column(String(255), nullable=True)

    # Indexes for common queries
    __table_args__ = (
        Index("idx_dlq_tenant_failed_at", "tenant_id", "failed_at"),
        Index("idx_dlq_exception_failed_at", "exception_id", "failed_at"),
        Index("idx_dlq_tenant_type_failed_at", "tenant_id", "event_type", "failed_at"),
        Index("idx_dlq_worker_failed_at", "worker_type", "failed_at"),
        Index("idx_dlq_tenant_status", "tenant_id", "status"),
    )


class ToolEnablement(Base):
    """
    Per-tenant tool enablement policy for Phase 8.
    
    Controls which tools are enabled/disabled for each tenant.
    Tools are enabled by default if no record exists.
    """
    
    __tablename__ = "tool_enablement"
    
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Tenant identifier",
    )
    tool_id = Column(
        Integer,
        ForeignKey("tool_definition.tool_id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
        doc="Tool definition identifier",
    )
    enabled = Column(
        sa.Boolean,
        nullable=False,
        default=True,
        doc="Whether the tool is enabled for this tenant",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when enablement was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when enablement was last updated",
    )
    
    # Relationships
    tenant = relationship("Tenant")
    tool_definition = relationship("ToolDefinition")
    
    # Unique constraint on (tenant_id, tool_id) is enforced by composite primary key
    
    def __repr__(self) -> str:
        return (
            f"<ToolEnablement(tenant_id={self.tenant_id!r}, "
            f"tool_id={self.tool_id}, enabled={self.enabled})>"
        )


# ============================================================================
# Phase 10 Alerting System Models (P10-5 through P10-9)
# ============================================================================


class AlertType(PyEnum):
    """Alert type categories (Phase 10 P10-5)."""
    SLA_BREACH = "sla_breach"
    SLA_IMMINENT = "sla_imminent"
    DLQ_GROWTH = "dlq_growth"
    WORKER_UNHEALTHY = "worker_unhealthy"
    ERROR_RATE_HIGH = "error_rate_high"
    THROUGHPUT_LOW = "throughput_low"


class AlertSeverity(PyEnum):
    """Alert severity levels (Phase 10 P10-5)."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AlertStatus(PyEnum):
    """Alert lifecycle status (Phase 10 P10-5)."""
    TRIGGERED = "triggered"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


class AlertConfig(Base):
    """
    Per-tenant alert configuration (Phase 10 P10-5).

    Stores alert type settings, thresholds, and notification channels.
    """

    __tablename__ = "alert_config"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Unique configuration identifier",
    )
    tenant_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    alert_type = Column(
        String(50),
        nullable=False,
        doc="Alert type (sla_breach, dlq_growth, etc.)",
    )
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether this alert type is enabled",
    )
    threshold = Column(
        Numeric,
        nullable=True,
        doc="Threshold value for triggering alert",
    )
    threshold_unit = Column(
        String(50),
        nullable=True,
        doc="Unit for threshold (percent, count, minutes, etc.)",
    )
    channels = Column(
        JSONB,
        nullable=False,
        default=list,
        doc="Notification channels [{type: webhook/email, url/address: ...}]",
    )
    quiet_hours_start = Column(
        sa.Time,
        nullable=True,
        doc="Start of quiet hours (suppress non-critical)",
    )
    quiet_hours_end = Column(
        sa.Time,
        nullable=True,
        doc="End of quiet hours",
    )
    escalation_minutes = Column(
        Integer,
        nullable=True,
        doc="Minutes before escalation if not acknowledged",
    )
    config_metadata = Column(
        JSONB,
        nullable=True,
        doc="Additional configuration metadata",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when config was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when config was last updated",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "alert_type", name="uq_alert_config_tenant_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<AlertConfig(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"alert_type={self.alert_type!r}, enabled={self.enabled})>"
        )


class AlertHistory(Base):
    """
    Alert trigger history and acknowledgment (Phase 10 P10-5).

    Stores all triggered alerts with their lifecycle state.
    """

    __tablename__ = "alert_history"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Unique history entry identifier",
    )
    alert_id = Column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
        doc="Unique alert identifier (ALT-XXX)",
    )
    tenant_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    alert_type = Column(
        String(50),
        nullable=False,
        doc="Alert type that triggered",
    )
    severity = Column(
        String(20),
        nullable=False,
        default="warning",
        doc="Alert severity level",
    )
    title = Column(
        String(500),
        nullable=False,
        doc="Short alert title",
    )
    message = Column(
        sa.Text,
        nullable=True,
        doc="Detailed alert message",
    )
    details = Column(
        JSONB,
        nullable=True,
        doc="Additional alert context (exception_id, metrics, etc.)",
    )
    status = Column(
        String(20),
        nullable=False,
        default="triggered",
        doc="Alert status (triggered, acknowledged, resolved)",
    )
    triggered_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="When the alert was triggered",
    )
    acknowledged_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the alert was acknowledged",
    )
    acknowledged_by = Column(
        String(255),
        nullable=True,
        doc="Who acknowledged the alert",
    )
    resolved_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the alert was resolved",
    )
    resolved_by = Column(
        String(255),
        nullable=True,
        doc="Who resolved the alert",
    )
    notification_sent = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether notification was successfully sent",
    )
    notification_error = Column(
        sa.Text,
        nullable=True,
        doc="Error message if notification failed",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when entry was created",
    )

    __table_args__ = (
        Index("idx_alert_history_tenant_status", "tenant_id", "status"),
        Index("idx_alert_history_tenant_type", "tenant_id", "alert_type"),
        Index("idx_alert_history_triggered_at", "triggered_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AlertHistory(alert_id={self.alert_id!r}, tenant_id={self.tenant_id!r}, "
            f"alert_type={self.alert_type!r}, status={self.status!r})>"
        )


# ============================================================================
# Phase 10 Config Change Governance Models (P10-10)
# ============================================================================


class ConfigChangeType(PyEnum):
    """Config change types for governance workflow (Phase 10 P10-10)."""
    DOMAIN_PACK = "domain_pack"
    TENANT_POLICY = "tenant_policy"
    TOOL_DEFINITION = "tool"
    PLAYBOOK = "playbook"


class ConfigChangeStatus(PyEnum):
    """Config change request status (Phase 10 P10-10)."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"


class ConfigChangeRequest(Base):
    """
    Configuration change request for governance workflow (Phase 10 P10-10).

    Tracks proposed changes to Domain Packs, Tenant Policy Packs, Tools, and Playbooks
    through a review and approval process.
    """

    __tablename__ = "config_change_request"

    id = Column(
        String(36),
        primary_key=True,
        doc="Unique change request identifier (UUID)",
    )
    tenant_id = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    change_type = Column(
        String(50),
        nullable=False,
        doc="Type of config change (domain_pack, tenant_policy, tool, playbook)",
    )
    resource_id = Column(
        String(255),
        nullable=False,
        doc="ID of the resource being changed",
    )
    resource_name = Column(
        String(255),
        nullable=True,
        doc="Human-readable name of the resource",
    )
    current_config = Column(
        JSONB,
        nullable=True,
        doc="Snapshot of the current configuration",
    )
    proposed_config = Column(
        JSONB,
        nullable=False,
        doc="Proposed new configuration",
    )
    diff_summary = Column(
        sa.Text,
        nullable=True,
        doc="Human-readable summary of changes",
    )
    change_reason = Column(
        sa.Text,
        nullable=True,
        doc="Reason for the proposed change",
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        doc="Request status (pending, approved, rejected, applied)",
    )
    requested_by = Column(
        String(255),
        nullable=False,
        doc="User who requested the change",
    )
    requested_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="When the change was requested",
    )
    reviewed_by = Column(
        String(255),
        nullable=True,
        doc="User who reviewed the change",
    )
    reviewed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the change was reviewed",
    )
    review_comment = Column(
        sa.Text,
        nullable=True,
        doc="Reviewer's comment",
    )
    applied_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the change was applied",
    )
    applied_by = Column(
        String(255),
        nullable=True,
        doc="User who applied the change",
    )
    rollback_config = Column(
        JSONB,
        nullable=True,
        doc="Configuration to rollback to if needed",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when record was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when record was last updated",
    )

    __table_args__ = (
        Index("idx_config_change_tenant", "tenant_id"),
        Index("idx_config_change_status", "status"),
        Index("idx_config_change_tenant_status", "tenant_id", "status"),
        Index("idx_config_change_type", "change_type"),
        Index("idx_config_change_requested_at", "requested_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ConfigChangeRequest(id={self.id!r}, tenant_id={self.tenant_id!r}, "
            f"change_type={self.change_type!r}, status={self.status!r})>"
        )


# ============================================================================
# Phase 10 Audit Reports Models (P10-11 to P10-14)
# ============================================================================


class AuditReportType(PyEnum):
    """Audit report types (Phase 10 P10-11)."""
    EXCEPTION_ACTIVITY = "exception_activity"
    TOOL_EXECUTION = "tool_execution"
    POLICY_DECISIONS = "policy_decisions"
    CONFIG_CHANGES = "config_changes"
    SLA_COMPLIANCE = "sla_compliance"


class AuditReportStatus(PyEnum):
    """Audit report generation status (Phase 10 P10-11)."""
    PENDING = "pending"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"


class AuditReportFormat(PyEnum):
    """Audit report output format (Phase 10 P10-11)."""
    JSON = "json"
    CSV = "csv"
    PDF = "pdf"


class AuditReport(Base):
    """
    Audit report tracking (Phase 10 P10-11 to P10-14).

    Tracks generated audit reports with their status and download information.
    Reports are generated asynchronously and stored for download.
    """

    __tablename__ = "audit_report"

    id = Column(
        String(36),
        primary_key=True,
        doc="Unique report identifier (UUID)",
    )
    tenant_id = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    report_type = Column(
        String(50),
        nullable=False,
        doc="Report type (exception_activity, tool_execution, etc.)",
    )
    title = Column(
        String(255),
        nullable=False,
        doc="Human-readable report title",
    )
    status = Column(
        String(20),
        nullable=False,
        default="pending",
        doc="Report status (pending, generating, completed, failed)",
    )
    format = Column(
        "format",
        String(10),
        nullable=False,
        default="json",
        doc="Output format (json, csv, pdf)",
    )
    parameters = Column(
        JSONB,
        nullable=True,
        doc="Report generation parameters (date range, filters, etc.)",
    )
    file_path = Column(
        String(500),
        nullable=True,
        doc="Path to generated report file",
    )
    file_size_bytes = Column(
        sa.BigInteger,
        nullable=True,
        doc="Size of the generated file in bytes",
    )
    download_url = Column(
        String(1000),
        nullable=True,
        doc="Signed URL for download",
    )
    download_expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When the download URL expires",
    )
    row_count = Column(
        Integer,
        nullable=True,
        doc="Number of rows/records in the report",
    )
    error_message = Column(
        sa.Text,
        nullable=True,
        doc="Error message if generation failed",
    )
    requested_by = Column(
        String(255),
        nullable=False,
        doc="User who requested the report",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When report generation started",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="When report generation completed",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when record was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when record was last updated",
    )

    __table_args__ = (
        Index("idx_audit_report_tenant", "tenant_id"),
        Index("idx_audit_report_status", "status"),
        Index("idx_audit_report_tenant_status", "tenant_id", "status"),
        Index("idx_audit_report_type", "report_type"),
        Index("idx_audit_report_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditReport(id={self.id!r}, tenant_id={self.tenant_id!r}, "
            f"report_type={self.report_type!r}, status={self.status!r})>"
        )


# ============================================================================
# Phase 10 Rate Limiting Models (P10-15 to P10-17)
# ============================================================================


class RateLimitType(PyEnum):
    """Rate limit types (Phase 10 P10-15)."""
    API_REQUESTS = "api_requests"
    EVENTS_INGESTED = "events_ingested"
    TOOL_EXECUTIONS = "tool_executions"
    REPORT_GENERATIONS = "report_generations"


class RateLimitConfig(Base):
    """
    Per-tenant rate limit configuration (Phase 10 P10-15).

    Defines rate limits by type for each tenant.
    """

    __tablename__ = "rate_limit_config"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Unique configuration identifier",
    )
    tenant_id = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    limit_type = Column(
        String(50),
        nullable=False,
        doc="Type of rate limit (api_requests, events_ingested, etc.)",
    )
    limit_value = Column(
        Integer,
        nullable=False,
        doc="Maximum allowed per window",
    )
    window_seconds = Column(
        Integer,
        nullable=False,
        default=60,
        doc="Time window in seconds",
    )
    enabled = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether this rate limit is enabled",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when config was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when config was last updated",
    )

    __table_args__ = (
        UniqueConstraint("tenant_id", "limit_type", name="uq_rate_limit_config_tenant_type"),
        Index("idx_rate_limit_config_tenant", "tenant_id"),
        Index("idx_rate_limit_config_type", "limit_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<RateLimitConfig(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"limit_type={self.limit_type!r}, limit_value={self.limit_value})>"
        )


class RateLimitUsage(Base):
    """
    Rate limit usage tracking (Phase 10 P10-15).

    Tracks current usage within time windows for rate limiting.
    """

    __tablename__ = "rate_limit_usage"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Unique usage record identifier",
    )
    tenant_id = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    limit_type = Column(
        String(50),
        nullable=False,
        doc="Type of rate limit",
    )
    window_start = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="Start of the current time window",
    )
    current_count = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Current count within the window",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when record was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when record was last updated",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "limit_type", "window_start",
            name="uq_rate_limit_usage_tenant_type_window",
        ),
        Index("idx_rate_limit_usage_tenant", "tenant_id"),
        Index("idx_rate_limit_usage_type", "limit_type"),
        Index("idx_rate_limit_usage_window", "window_start"),
        Index("idx_rate_limit_usage_tenant_type", "tenant_id", "limit_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<RateLimitUsage(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"limit_type={self.limit_type!r}, current_count={self.current_count})>"
        )


# ============================================================================
# Phase 10 Usage Metering Models (P10-18 to P10-20)
# ============================================================================


class UsageMetricType(PyEnum):
    """Usage metric types (Phase 10 P10-18)."""
    API_CALLS = "api_calls"
    EXCEPTIONS = "exceptions"
    TOOL_EXECUTIONS = "tool_executions"
    EVENTS = "events"
    STORAGE = "storage"


class UsagePeriodType(PyEnum):
    """Usage aggregation period types (Phase 10 P10-18)."""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    MONTH = "month"


class UsageMetric(Base):
    """
    Usage metric tracking (Phase 10 P10-18 to P10-20).

    Tracks aggregated usage metrics per tenant for billing and monitoring.
    """

    __tablename__ = "usage_metric"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Unique metric record identifier",
    )
    tenant_id = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    metric_type = Column(
        String(50),
        nullable=False,
        doc="Type of metric (api_calls, exceptions, etc.)",
    )
    resource_id = Column(
        String(255),
        nullable=True,
        doc="Optional resource identifier (e.g., tool_id, endpoint)",
    )
    period_start = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="Start of the measurement period",
    )
    period_end = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="End of the measurement period",
    )
    period_type = Column(
        String(20),
        nullable=False,
        default="minute",
        doc="Period granularity (minute, hour, day, month)",
    )
    count = Column(
        sa.BigInteger,
        nullable=False,
        default=0,
        doc="Count for count-based metrics",
    )
    bytes_value = Column(
        sa.BigInteger,
        nullable=True,
        doc="Byte count for storage metrics",
    )
    usage_metadata = Column(
        "metadata",
        JSONB,
        nullable=True,
        doc="Additional metadata",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when record was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when record was last updated",
    )

    __table_args__ = (
        UniqueConstraint(
            "tenant_id", "metric_type", "resource_id", "period_start", "period_type",
            name="uq_usage_metric_tenant_type_resource_period",
        ),
        Index("idx_usage_metric_tenant", "tenant_id"),
        Index("idx_usage_metric_type", "metric_type"),
        Index("idx_usage_metric_period", "period_start", "period_end"),
        Index("idx_usage_metric_tenant_type_period", "tenant_id", "metric_type", "period_start"),
        Index("idx_usage_metric_tenant_period_type", "tenant_id", "period_type", "period_start"),
    )

    def __repr__(self) -> str:
        return (
            f"<UsageMetric(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"metric_type={self.metric_type!r}, count={self.count})>"
        )


# ============================================================================
# Tenant & Domain Pack Onboarding Models
# ============================================================================


class DomainPack(Base):
    """
    Domain Pack for onboarding and management.
    
    Matches docs/phase12-onboarding-packs-mvp.md Section 4.2.
    This is separate from DomainPackVersion which is for runtime.
    """

    __tablename__ = "domain_packs"

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    domain = Column(String, nullable=False, index=True, doc="Domain name (e.g., Finance, Healthcare)")
    version = Column(String, nullable=False, doc="Version string (e.g., 'v1.0', 'v2.3')")
    content_json = Column(JSONB, nullable=False, doc="Domain Pack JSON content")
    checksum = Column(String, nullable=False, doc="Checksum for integrity verification")
    status = Column(
        Enum(
            PackStatus,
            name="pack_status",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PackStatus.DRAFT,
        doc="Pack lifecycle status",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when pack was created",
    )
    created_by = Column(String, nullable=False, doc="User identifier who created the pack")

    # Unique constraint on domain + version
    __table_args__ = (
        UniqueConstraint("domain", "version", name="uq_domain_packs_domain_version"),
        Index("ix_domain_packs_domain", "domain"),
        Index("ix_domain_packs_version", "version"),
        Index("ix_domain_packs_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<DomainPack(id={self.id}, domain={self.domain!r}, version={self.version!r}, status={self.status.value})>"


class TenantPack(Base):
    """
    Tenant Pack for onboarding and management.
    
    Matches docs/phase12-onboarding-packs-mvp.md Section 4.3.
    This is separate from TenantPolicyPackVersion which is for runtime.
    """

    __tablename__ = "tenant_packs"

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Tenant identifier",
    )
    version = Column(String, nullable=False, doc="Version string (e.g., 'v1.0', 'v2.3')")
    content_json = Column(JSONB, nullable=False, doc="Tenant Pack JSON content")
    checksum = Column(String, nullable=False, doc="Checksum for integrity verification")
    status = Column(
        Enum(
            PackStatus,
            name="pack_status",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        default=PackStatus.DRAFT,
        doc="Pack lifecycle status",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when pack was created",
    )
    created_by = Column(String, nullable=False, doc="User identifier who created the pack")

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    # Unique constraint on tenant_id + version
    __table_args__ = (
        UniqueConstraint("tenant_id", "version", name="uq_tenant_packs_tenant_version"),
        Index("ix_tenant_packs_tenant_id", "tenant_id"),
        Index("ix_tenant_packs_version", "version"),
        Index("ix_tenant_packs_status", "status"),
    )

    def __repr__(self) -> str:
        return (
            f"<TenantPack(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"version={self.version!r}, status={self.status.value})>"
        )


class TenantActiveConfig(Base):
    """
    Active configuration mapping.
    
    Maps tenants to their active pack versions.
    Matches docs/phase12-onboarding-packs-mvp.md Section 4.4.
    """

    __tablename__ = "tenant_active_config"

    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        primary_key=True,
        doc="Tenant identifier (primary key)",
    )
    active_domain_pack_version = Column(
        String,
        nullable=True,
        doc="Active domain pack version string (e.g., 'v3.2')",
    )
    active_tenant_pack_version = Column(
        String,
        nullable=True,
        doc="Active tenant pack version string (e.g., 'v1.4')",
    )
    activated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when configuration was activated",
    )
    activated_by = Column(String, nullable=False, doc="User identifier who activated the configuration")

    # Relationships
    tenant = relationship("Tenant", foreign_keys=[tenant_id])

    def __repr__(self) -> str:
        return (
            f"<TenantActiveConfig(tenant_id={self.tenant_id!r}, "
            f"domain_pack={self.active_domain_pack_version!r}, "
            f"tenant_pack={self.active_tenant_pack_version!r})>"
        )


# ============================================================================
# Phase 12+ Governance Audit Models
# ============================================================================


class AuditEntityType(PyEnum):
    """Entity types for governance audit events."""
    TENANT = "tenant"
    DOMAIN_PACK = "domain_pack"
    TENANT_PACK = "tenant_pack"
    PLAYBOOK = "playbook"
    TOOL = "tool"
    RATE_LIMIT = "rate_limit"
    ALERT_CONFIG = "alert_config"
    CONFIG_CHANGE = "config_change"
    REPORT = "report"


class AuditAction(PyEnum):
    """Actions for governance audit events."""
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    IMPORT = "import"
    VALIDATE = "validate"
    ACTIVATE = "activate"
    DEPRECATE = "deprecate"
    ENABLE = "enable"
    DISABLE = "disable"
    APPROVE = "approve"
    REJECT = "reject"
    APPLY = "apply"
    STATUS_CHANGE = "status_change"
    LINK = "link"
    UNLINK = "unlink"


class GovernanceAuditEvent(Base):
    """
    Governance audit event log for Phase 12+ enterprise audit trail.

    Provides a standardized audit trail for all governance-related actions
    including tenant lifecycle, pack management, playbook/tool configuration,
    rate limits, alerts, and config change approvals.

    Matches Phase 12+ Governance & Audit Polish requirements.
    """

    __tablename__ = "governance_audit_event"

    id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique audit event identifier",
    )
    event_type = Column(
        String(100),
        nullable=False,
        index=True,
        doc="Event type (e.g., TENANT_CREATED, DOMAIN_PACK_ACTIVATED)",
    )
    actor_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Actor identifier (user ID or 'system')",
    )
    actor_role = Column(
        String(50),
        nullable=True,
        doc="Actor role (admin, supervisor, system)",
    )
    tenant_id = Column(
        String(255),
        nullable=True,  # Nullable for global events (e.g., domain pack import)
        index=True,
        doc="Tenant identifier (required for tenant-scoped events)",
    )
    domain = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Domain name (when relevant)",
    )
    entity_type = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Entity type (tenant, domain_pack, tenant_pack, playbook, tool, etc.)",
    )
    entity_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Entity identifier",
    )
    entity_version = Column(
        String(50),
        nullable=True,
        doc="Entity version (when applicable)",
    )
    action = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Action performed (create, update, activate, approve, reject, etc.)",
    )
    before_json = Column(
        JSONB,
        nullable=True,
        doc="State before change (redacted of sensitive data)",
    )
    after_json = Column(
        JSONB,
        nullable=True,
        doc="State after change (redacted of sensitive data)",
    )
    diff_summary = Column(
        sa.Text,
        nullable=True,
        doc="Human-readable summary of changes",
    )
    correlation_id = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Correlation ID for distributed tracing",
    )
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Request ID from HTTP request",
    )
    related_exception_id = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Related exception ID (when applicable)",
    )
    related_change_request_id = Column(
        String(36),
        nullable=True,
        index=True,
        doc="Related config change request ID (for approval flows)",
    )
    event_metadata = Column(
        "metadata",
        JSONB,
        nullable=True,
        doc="Additional event metadata (redacted)",
    )
    ip_address = Column(
        String(45),
        nullable=True,
        doc="Client IP address (for audit)",
    )
    user_agent = Column(
        String(500),
        nullable=True,
        doc="Client user agent (for audit)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        doc="Timestamp when event was created",
    )

    # Comprehensive indexes for common query patterns
    __table_args__ = (
        Index("idx_gov_audit_tenant_created", "tenant_id", "created_at"),
        Index("idx_gov_audit_entity_type_id", "entity_type", "entity_id"),
        Index("idx_gov_audit_tenant_entity", "tenant_id", "entity_type", "entity_id"),
        Index("idx_gov_audit_actor_created", "actor_id", "created_at"),
        Index("idx_gov_audit_action_created", "action", "created_at"),
        Index("idx_gov_audit_domain_created", "domain", "created_at"),
        Index("idx_gov_audit_correlation", "correlation_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<GovernanceAuditEvent(id={self.id}, event_type={self.event_type!r}, "
            f"entity_type={self.entity_type!r}, entity_id={self.entity_id!r}, "
            f"action={self.action!r}, tenant_id={self.tenant_id!r})>"
        )


# ============================================================================
# Phase 13 Copilot Intelligence Models
# ============================================================================


class CopilotDocumentSourceType(PyEnum):
    """Source types for copilot documents (Phase 13 P13-1)."""
    POLICY_DOC = "policy_doc"
    RESOLVED_EXCEPTION = "resolved_exception"
    AUDIT_EVENT = "audit_event"
    TOOL_REGISTRY = "tool_registry"
    PLAYBOOK = "playbook"


class CopilotIndexJobStatus(PyEnum):
    """Status for copilot index rebuild jobs (Phase 13 P13-8)."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class CopilotMessageRole(PyEnum):
    """Message roles for copilot conversation (Phase 13 P13-14)."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class CopilotDocument(Base):
    """
    Vector-indexed documents for Copilot RAG retrieval (Phase 13 P13-1).

    Stores document chunks with embeddings for semantic search.
    Uses pgvector for vector similarity search.

    Matches docs/phase13-copilot-intelligence-mvp.md Section 4.2.
    """

    __tablename__ = "copilot_documents"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Primary key",
    )
    tenant_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Tenant identifier for isolation (mandatory)",
    )
    source_type = Column(
        String(50),
        nullable=False,
        index=True,
        doc="Source type (policy_doc, resolved_exception, audit_event, tool_registry, playbook)",
    )
    source_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Source document identifier (e.g., SOP-FIN-001, EX-2024-1120)",
    )
    domain = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Domain name (Finance, Healthcare, etc.) - nullable for global docs",
    )
    chunk_id = Column(
        String(100),
        nullable=False,
        doc="Unique chunk identifier within document (e.g., source_id-chunk-0)",
    )
    chunk_index = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Position of chunk within source document (0-indexed)",
    )
    content = Column(
        sa.Text,
        nullable=False,
        doc="Document chunk text content",
    )
    # Note: The 'embedding' column will be added via migration using pgvector
    # We define it here as JSONB fallback for testing without pgvector
    embedding = Column(
        JSONB,
        nullable=True,
        doc="Vector embedding (stored as JSONB array, converted to vector in queries)",
    )
    embedding_model = Column(
        String(100),
        nullable=True,
        doc="Embedding model used (e.g., text-embedding-3-small)",
    )
    embedding_dimension = Column(
        Integer,
        nullable=True,
        doc="Dimension of the embedding vector",
    )
    metadata_json = Column(
        JSONB,
        nullable=True,
        doc="Additional metadata (title, snippet, url, tags, etc.)",
    )
    version = Column(
        String(50),
        nullable=True,
        doc="Document version for cache invalidation",
    )
    content_hash = Column(
        String(64),
        nullable=True,
        index=True,
        doc="SHA-256 hash of content for deduplication",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when document was indexed",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when document was last updated",
    )

    __table_args__ = (
        # Unique constraint on tenant + source + chunk
        UniqueConstraint(
            "tenant_id", "source_type", "source_id", "chunk_id",
            name="uq_copilot_doc_tenant_source_chunk",
        ),
        # Indexes for common query patterns
        Index("idx_copilot_doc_tenant_source_type", "tenant_id", "source_type"),
        Index("idx_copilot_doc_tenant_domain", "tenant_id", "domain"),
        Index("idx_copilot_doc_tenant_source_id", "tenant_id", "source_id"),
        Index("idx_copilot_doc_content_hash", "content_hash"),
    )

    def __repr__(self) -> str:
        return (
            f"<CopilotDocument(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"source_type={self.source_type!r}, source_id={self.source_id!r}, "
            f"chunk_id={self.chunk_id!r})>"
        )


class IndexingState(Base):
    """
    Track indexing watermarks for incremental processing (Phase 13 P13-5).
    
    Stores the last successfully indexed timestamp per tenant and source type
    to enable efficient incremental indexing operations.
    """

    __tablename__ = "indexing_state"

    id = Column(Integer, primary_key=True, autoincrement=True, doc="Primary key")
    tenant_id = Column(
        String,
        ForeignKey("tenant.tenant_id", ondelete="CASCADE"),
        nullable=False,
        doc="Tenant identifier",
    )
    source_type = Column(
        Enum(
            CopilotDocumentSourceType,
            name="indexing_source_type",
            create_constraint=True,
            native_enum=False,
            values_callable=lambda x: [e.value for e in x],
        ),
        nullable=False,
        doc="Source type being indexed",
    )
    last_indexed_at = Column(
        DateTime(timezone=True),
        nullable=False,
        doc="Timestamp of last successfully indexed record",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when state was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when state was last updated",
    )

    # Relationships
    tenant = relationship("Tenant")

    # Ensure one state per tenant/source_type combination
    __table_args__ = (
        UniqueConstraint("tenant_id", "source_type", name="uq_indexing_state_tenant_source"),
        Index("idx_indexing_state_tenant_source", "tenant_id", "source_type"),
    )

    def __repr__(self) -> str:
        return (
            f"<IndexingState(tenant_id={self.tenant_id!r}, source_type={self.source_type.value}, "
            f"last_indexed_at={self.last_indexed_at})>"
        )


class CopilotSession(Base):
    """
    Copilot conversation session (Phase 13 P13-14).

    Stores session metadata for conversation memory.
    Scoped to tenant + user for isolation.

    Matches docs/phase13-copilot-intelligence-mvp.md Section 3, 5.
    """

    __tablename__ = "copilot_sessions"

    id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Session identifier (UUID)",
    )
    tenant_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Tenant identifier for isolation (mandatory)",
    )
    user_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="User identifier within tenant",
    )
    title = Column(
        String(500),
        nullable=True,
        doc="Optional session title (auto-generated or user-provided)",
    )
    context_json = Column(
        JSONB,
        nullable=True,
        doc="Session context metadata (exception_id, filters, preferences)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        doc="Timestamp when session was created",
    )
    last_activity_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp of last activity (message sent/received)",
    )
    expires_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Optional TTL-based expiration timestamp",
    )
    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
        doc="Whether session is active (false = soft-deleted)",
    )

    # Relationships
    messages = relationship(
        "CopilotMessage",
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="CopilotMessage.created_at",
    )

    __table_args__ = (
        Index("idx_copilot_session_tenant_user", "tenant_id", "user_id"),
        Index("idx_copilot_session_tenant_active", "tenant_id", "is_active"),
        Index("idx_copilot_session_last_activity", "last_activity_at"),
        Index("idx_copilot_session_expires", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CopilotSession(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"user_id={self.user_id!r}, is_active={self.is_active})>"
        )


class CopilotMessage(Base):
    """
    Copilot conversation message (Phase 13 P13-14).

    Stores individual messages in a conversation session.
    Includes role, content, and response metadata (citations, playbooks).

    Matches docs/phase13-copilot-intelligence-mvp.md Section 3, 6.
    """

    __tablename__ = "copilot_messages"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
        doc="Message identifier",
    )
    session_id = Column(
        PostgresUUID(as_uuid=True),
        ForeignKey("copilot_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        doc="Session identifier (FK to copilot_sessions)",
    )
    tenant_id = Column(
        String(255),
        nullable=False,
        index=True,
        doc="Tenant identifier for isolation (denormalized for query efficiency)",
    )
    role = Column(
        String(20),
        nullable=False,
        doc="Message role (user, assistant, system)",
    )
    content = Column(
        sa.Text,
        nullable=False,
        doc="Message content text",
    )
    metadata_json = Column(
        JSONB,
        nullable=True,
        doc="Response metadata (citations, playbook recommendations, safety info)",
    )
    intent = Column(
        String(50),
        nullable=True,
        doc="Detected intent for user messages (summary, explain, find_similar, etc.)",
    )
    request_id = Column(
        String(100),
        nullable=True,
        index=True,
        doc="Request ID for tracing and evidence retrieval",
    )
    exception_id = Column(
        String(255),
        nullable=True,
        index=True,
        doc="Related exception ID if query is exception-scoped",
    )
    tokens_used = Column(
        Integer,
        nullable=True,
        doc="Number of tokens used for this message (for metering)",
    )
    latency_ms = Column(
        Integer,
        nullable=True,
        doc="Response latency in milliseconds",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        doc="Timestamp when message was created",
    )

    # Relationships
    session = relationship("CopilotSession", back_populates="messages")

    __table_args__ = (
        Index("idx_copilot_msg_session_created", "session_id", "created_at"),
        Index("idx_copilot_msg_tenant_created", "tenant_id", "created_at"),
        Index("idx_copilot_msg_request_id", "request_id"),
        Index("idx_copilot_msg_exception_id", "exception_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<CopilotMessage(id={self.id}, session_id={self.session_id}, "
            f"role={self.role!r}, tenant_id={self.tenant_id!r})>"
        )


class CopilotIndexJob(Base):
    """
    Copilot index rebuild jobs tracking (Phase 13 P13-8).

    Tracks progress and status of index rebuild operations for
    different source types and tenants.
    """

    __tablename__ = "copilot_index_jobs"

    id = Column(
        PostgresUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        doc="Unique job identifier",
    )
    tenant_id = Column(
        String(255),
        nullable=True,  # Null for global jobs
        index=True,
        doc="Tenant identifier (null for global index jobs)",
    )
    sources = Column(
        JSONB,
        nullable=False,
        doc="List of source types to rebuild (e.g., ['policy_doc', 'audit_event'])",
    )
    full_rebuild = Column(
        Boolean,
        nullable=False,
        default=False,
        doc="Whether this is a full rebuild (true) or incremental (false)",
    )
    status = Column(
        Enum(CopilotIndexJobStatus, name="copilot_index_job_status", create_type=True),
        nullable=False,
        index=True,
        default=CopilotIndexJobStatus.PENDING,
        doc="Current job status",
    )
    progress_current = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Current progress count (documents processed)",
    )
    progress_total = Column(
        Integer,
        nullable=True,
        doc="Total documents to process (null if unknown)",
    )
    documents_processed = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total documents successfully processed",
    )
    documents_failed = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total documents that failed processing",
    )
    chunks_indexed = Column(
        Integer,
        nullable=False,
        default=0,
        doc="Total chunks successfully indexed",
    )
    error_message = Column(
        String(1000),
        nullable=True,
        doc="Error message if job failed",
    )
    error_details = Column(
        JSONB,
        nullable=True,
        doc="Detailed error information as JSON",
    )
    started_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when job started running",
    )
    completed_at = Column(
        DateTime(timezone=True),
        nullable=True,
        doc="Timestamp when job completed (success or failure)",
    )
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
        doc="Timestamp when job was created",
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        doc="Timestamp when job was last updated",
    )

    __table_args__ = (
        Index("idx_copilot_index_job_tenant_status", "tenant_id", "status"),
        Index("idx_copilot_index_job_created", "created_at"),
        Index("idx_copilot_index_job_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<CopilotIndexJob(id={self.id}, tenant_id={self.tenant_id!r}, "
            f"status={self.status!r}, sources={self.sources})>"
        )

