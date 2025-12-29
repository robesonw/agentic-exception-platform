"""
Database infrastructure module for Phase 6 Persistence MVP.

This module provides SQLAlchemy models, database session management, and database-related utilities.
"""

from src.infrastructure.db.models import (
    ActorType,
    Base,
    DomainPackVersion,
    Exception,
    ExceptionEvent,
    ExceptionSeverity,
    ExceptionStatus,
    Playbook,
    PlaybookStep,
    Tenant,
    TenantPolicyPackVersion,
    TenantStatus,
    ToolDefinition,
    # Phase 13 Copilot models
    CopilotDocument,
    CopilotDocumentSourceType,
    CopilotMessage,
    CopilotMessageRole,
    CopilotSession,
)
from src.infrastructure.db.session import (
    check_database_connection,
    close_engine,
    get_db_session,
    get_db_session_context,
    get_engine,
    get_session_factory,
    initialize_database,
)

__all__ = [
    # Models
    "Base",
    "Tenant",
    "TenantStatus",
    "DomainPackVersion",
    "TenantPolicyPackVersion",
    "Exception",
    "ExceptionSeverity",
    "ExceptionStatus",
    "ExceptionEvent",
    "ActorType",
    "Playbook",
    "PlaybookStep",
    "ToolDefinition",
    # Phase 13 Copilot models
    "CopilotDocument",
    "CopilotDocumentSourceType",
    "CopilotMessage",
    "CopilotMessageRole",
    "CopilotSession",
    # Session management
    "get_engine",
    "get_session_factory",
    "get_db_session",
    "get_db_session_context",
    "close_engine",
    "initialize_database",
    "check_database_connection",
]

