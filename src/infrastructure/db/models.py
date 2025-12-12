"""
SQLAlchemy database models for Phase 6 Persistence MVP.

This module defines all database tables and models as specified in
docs/phase6-persistence-mvp.md Section 4 (Schema Overview).

All models use async-friendly SQLAlchemy with PostgreSQL-specific types.
"""

from enum import Enum as PyEnum
from uuid import uuid4

from sqlalchemy import (
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

