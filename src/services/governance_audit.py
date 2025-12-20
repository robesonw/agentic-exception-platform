"""
Governance Audit Service for Phase 12+ Enterprise Audit Trail.

Provides utilities for:
- Generating and propagating correlation IDs
- Redacting sensitive data from audit payloads
- Emitting standardized governance audit events
- Querying audit events with filtering and pagination

Reference: Phase 12+ Governance & Audit Polish requirements.
"""

import hashlib
import logging
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TypeVar

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Context variable for correlation ID propagation across async calls
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
_request_id_ctx: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_actor_ctx: ContextVar[Optional[dict]] = ContextVar("actor_context", default=None)


# =============================================================================
# Correlation ID Management
# =============================================================================


def generate_correlation_id() -> str:
    """Generate a new correlation ID for distributed tracing."""
    return f"cor_{uuid.uuid4().hex[:16]}"


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID from context."""
    return _correlation_id_ctx.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set the correlation ID in context."""
    _correlation_id_ctx.set(correlation_id)


def get_or_create_correlation_id() -> str:
    """Get existing correlation ID or create a new one."""
    correlation_id = get_correlation_id()
    if not correlation_id:
        correlation_id = generate_correlation_id()
        set_correlation_id(correlation_id)
    return correlation_id


def generate_request_id() -> str:
    """Generate a new request ID."""
    return f"req_{uuid.uuid4().hex[:12]}"


def get_request_id() -> Optional[str]:
    """Get the current request ID from context."""
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> None:
    """Set the request ID in context."""
    _request_id_ctx.set(request_id)


# =============================================================================
# Actor Context Management
# =============================================================================


@dataclass
class ActorContext:
    """Actor context for audit events."""
    actor_id: str
    actor_role: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None


def set_actor_context(actor: ActorContext) -> None:
    """Set the actor context for the current request."""
    _actor_ctx.set({
        "actor_id": actor.actor_id,
        "actor_role": actor.actor_role,
        "ip_address": actor.ip_address,
        "user_agent": actor.user_agent,
    })


def get_actor_context() -> Optional[dict]:
    """Get the current actor context."""
    return _actor_ctx.get()


def clear_context() -> None:
    """Clear all context variables (call at end of request)."""
    _correlation_id_ctx.set(None)
    _request_id_ctx.set(None)
    _actor_ctx.set(None)


# =============================================================================
# Sensitive Data Redaction
# =============================================================================


# Patterns for sensitive data detection
SENSITIVE_PATTERNS = [
    # API keys and tokens
    (r'(api[_-]?key|apikey)["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?', r'\1: [REDACTED]'),
    (r'(token|bearer|auth[_-]?token)["\s:=]+["\']?([a-zA-Z0-9_\-\.]{16,})["\']?', r'\1: [REDACTED]'),
    (r'(secret|password|passwd|pwd)["\s:=]+["\']?([^"\'\s]{8,})["\']?', r'\1: [REDACTED]'),
    (r'(authorization)["\s:=]+["\']?(Bearer\s+[a-zA-Z0-9_\-\.]+)["\']?', r'\1: [REDACTED]'),

    # Credentials
    (r'(client[_-]?secret|client[_-]?id)["\s:=]+["\']?([a-zA-Z0-9_\-]{16,})["\']?', r'\1: [REDACTED]'),
    (r'(private[_-]?key|signing[_-]?key)["\s:=]+["\']?([a-zA-Z0-9_\-/+=]{32,})["\']?', r'\1: [REDACTED]'),

    # Connection strings
    (r'(postgres://|mysql://|mongodb://|redis://)[^\s"\']+', '[DATABASE_URL_REDACTED]'),
    (r'(connection[_-]?string)["\s:=]+["\']?([^"\'\s]+)["\']?', r'\1: [REDACTED]'),

    # PII patterns
    (r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b', '[EMAIL_REDACTED]'),
    (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]'),
    (r'\b\d{3}[-]?\d{2}[-]?\d{4}\b', '[SSN_REDACTED]'),
    (r'\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b', '[CARD_REDACTED]'),
]

# Keys that should always be redacted in JSON payloads
SENSITIVE_KEYS = {
    'password', 'passwd', 'pwd', 'secret', 'token', 'api_key', 'apikey',
    'api-key', 'auth_token', 'authorization', 'bearer', 'private_key',
    'signing_key', 'client_secret', 'access_token', 'refresh_token',
    'session_token', 'credentials', 'connection_string', 'database_url',
    'ssn', 'social_security', 'credit_card', 'card_number', 'cvv', 'cvc',
    'pin', 'bank_account', 'routing_number', 'tax_id', 'ein',
}


def redact_string(value: str) -> str:
    """
    Redact sensitive patterns from a string.

    Args:
        value: String to redact

    Returns:
        Redacted string
    """
    result = value
    for pattern, replacement in SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def redact_dict(data: dict, depth: int = 0, max_depth: int = 10) -> dict:
    """
    Recursively redact sensitive data from a dictionary.

    Args:
        data: Dictionary to redact
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        Redacted dictionary
    """
    if depth > max_depth:
        return {"_truncated": "max_depth_exceeded"}

    result = {}
    for key, value in data.items():
        key_lower = key.lower().replace("-", "_")

        # Check if key itself is sensitive
        if key_lower in SENSITIVE_KEYS:
            result[key] = "[REDACTED]"
        elif isinstance(value, dict):
            result[key] = redact_dict(value, depth + 1, max_depth)
        elif isinstance(value, list):
            result[key] = redact_list(value, depth + 1, max_depth)
        elif isinstance(value, str):
            result[key] = redact_string(value)
        else:
            result[key] = value

    return result


def redact_list(data: list, depth: int = 0, max_depth: int = 10) -> list:
    """
    Recursively redact sensitive data from a list.

    Args:
        data: List to redact
        depth: Current recursion depth
        max_depth: Maximum recursion depth

    Returns:
        Redacted list
    """
    if depth > max_depth:
        return ["_truncated: max_depth_exceeded"]

    result = []
    for item in data:
        if isinstance(item, dict):
            result.append(redact_dict(item, depth + 1, max_depth))
        elif isinstance(item, list):
            result.append(redact_list(item, depth + 1, max_depth))
        elif isinstance(item, str):
            result.append(redact_string(item))
        else:
            result.append(item)

    return result


def redact_payload(payload: Any) -> Any:
    """
    Redact sensitive data from any payload type.

    Args:
        payload: Payload to redact (dict, list, or string)

    Returns:
        Redacted payload
    """
    if payload is None:
        return None
    if isinstance(payload, dict):
        return redact_dict(payload)
    if isinstance(payload, list):
        return redact_list(payload)
    if isinstance(payload, str):
        return redact_string(payload)
    return payload


# =============================================================================
# Audit Event Models
# =============================================================================


class GovernanceAuditEventCreate(BaseModel):
    """Model for creating a governance audit event."""

    event_type: str = Field(..., description="Event type (e.g., TENANT_CREATED)")
    actor_id: str = Field(..., description="Actor identifier")
    actor_role: Optional[str] = Field(None, description="Actor role")
    tenant_id: Optional[str] = Field(None, description="Tenant identifier")
    domain: Optional[str] = Field(None, description="Domain name")
    entity_type: str = Field(..., description="Entity type")
    entity_id: str = Field(..., description="Entity identifier")
    entity_version: Optional[str] = Field(None, description="Entity version")
    action: str = Field(..., description="Action performed")
    before_json: Optional[dict] = Field(None, description="State before change")
    after_json: Optional[dict] = Field(None, description="State after change")
    diff_summary: Optional[str] = Field(None, description="Human-readable diff")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    request_id: Optional[str] = Field(None, description="Request ID")
    related_exception_id: Optional[str] = Field(None, description="Related exception ID")
    related_change_request_id: Optional[str] = Field(None, description="Related config change request ID")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")


class GovernanceAuditEventResponse(BaseModel):
    """Model for governance audit event response."""

    id: str = Field(..., description="Event ID")
    event_type: str = Field(..., description="Event type")
    actor_id: str = Field(..., description="Actor identifier")
    actor_role: Optional[str] = Field(None, description="Actor role")
    tenant_id: Optional[str] = Field(None, description="Tenant identifier")
    domain: Optional[str] = Field(None, description="Domain name")
    entity_type: str = Field(..., description="Entity type")
    entity_id: str = Field(..., description="Entity identifier")
    entity_version: Optional[str] = Field(None, description="Entity version")
    action: str = Field(..., description="Action performed")
    before_json: Optional[dict] = Field(None, description="State before change")
    after_json: Optional[dict] = Field(None, description="State after change")
    diff_summary: Optional[str] = Field(None, description="Human-readable diff")
    correlation_id: Optional[str] = Field(None, description="Correlation ID")
    request_id: Optional[str] = Field(None, description="Request ID")
    related_exception_id: Optional[str] = Field(None, description="Related exception ID")
    related_change_request_id: Optional[str] = Field(None, description="Related config change request ID")
    metadata: Optional[dict] = Field(None, description="Additional metadata")
    ip_address: Optional[str] = Field(None, description="Client IP address")
    user_agent: Optional[str] = Field(None, description="Client user agent")
    created_at: datetime = Field(..., description="Event timestamp")

    model_config = {"from_attributes": True}


class AuditEventFilter(BaseModel):
    """Filter parameters for querying audit events."""

    tenant_id: Optional[str] = Field(None, description="Filter by tenant ID")
    domain: Optional[str] = Field(None, description="Filter by domain")
    entity_type: Optional[str] = Field(None, description="Filter by entity type")
    entity_id: Optional[str] = Field(None, description="Filter by entity ID")
    event_type: Optional[str] = Field(None, description="Filter by event type")
    action: Optional[str] = Field(None, description="Filter by action")
    actor_id: Optional[str] = Field(None, description="Filter by actor ID")
    correlation_id: Optional[str] = Field(None, description="Filter by correlation ID")
    from_date: Optional[datetime] = Field(None, description="Filter events after this time")
    to_date: Optional[datetime] = Field(None, description="Filter events before this time")


@dataclass
class PaginatedResult:
    """Paginated query result."""
    items: list
    total: int
    page: int
    page_size: int

    @property
    def total_pages(self) -> int:
        return (self.total + self.page_size - 1) // self.page_size if self.total > 0 else 0


# =============================================================================
# Diff Generation
# =============================================================================


def generate_diff_summary(before: Optional[dict], after: Optional[dict]) -> str:
    """
    Generate a human-readable diff summary between two states.

    Args:
        before: State before change
        after: State after change

    Returns:
        Human-readable diff summary
    """
    if before is None and after is None:
        return "No changes"

    if before is None:
        return f"Created with {len(after or {})} fields"

    if after is None:
        return f"Deleted {len(before)} fields"

    added = []
    removed = []
    changed = []

    all_keys = set(before.keys()) | set(after.keys())

    for key in all_keys:
        if key not in before:
            added.append(key)
        elif key not in after:
            removed.append(key)
        elif before[key] != after[key]:
            changed.append(key)

    parts = []
    if added:
        parts.append(f"Added: {', '.join(added[:5])}" + ("..." if len(added) > 5 else ""))
    if removed:
        parts.append(f"Removed: {', '.join(removed[:5])}" + ("..." if len(removed) > 5 else ""))
    if changed:
        parts.append(f"Changed: {', '.join(changed[:5])}" + ("..." if len(changed) > 5 else ""))

    return "; ".join(parts) if parts else "No significant changes"


# =============================================================================
# Event Type Constants
# =============================================================================


class AuditEventTypes:
    """Standard audit event type constants."""

    # Tenant events
    TENANT_CREATED = "TENANT_CREATED"
    TENANT_UPDATED = "TENANT_UPDATED"
    TENANT_STATUS_CHANGED = "TENANT_STATUS_CHANGED"
    TENANT_DELETED = "TENANT_DELETED"

    # Domain pack events
    DOMAIN_PACK_IMPORTED = "DOMAIN_PACK_IMPORTED"
    DOMAIN_PACK_UPDATED = "DOMAIN_PACK_UPDATED"
    DOMAIN_PACK_VALIDATED = "DOMAIN_PACK_VALIDATED"
    DOMAIN_PACK_ACTIVATED = "DOMAIN_PACK_ACTIVATED"
    DOMAIN_PACK_DEPRECATED = "DOMAIN_PACK_DEPRECATED"

    # Tenant pack events
    TENANT_PACK_IMPORTED = "TENANT_PACK_IMPORTED"
    TENANT_PACK_UPDATED = "TENANT_PACK_UPDATED"
    TENANT_PACK_VALIDATED = "TENANT_PACK_VALIDATED"
    TENANT_PACK_ACTIVATED = "TENANT_PACK_ACTIVATED"
    TENANT_PACK_DEPRECATED = "TENANT_PACK_DEPRECATED"

    # Config activation events
    CONFIG_ACTIVATED = "CONFIG_ACTIVATED"
    CONFIG_ACTIVATION_REQUESTED = "CONFIG_ACTIVATION_REQUESTED"

    # Playbook events
    PLAYBOOK_CREATED = "PLAYBOOK_CREATED"
    PLAYBOOK_UPDATED = "PLAYBOOK_UPDATED"
    PLAYBOOK_ACTIVATED = "PLAYBOOK_ACTIVATED"
    PLAYBOOK_LINKED = "PLAYBOOK_LINKED"
    PLAYBOOK_UNLINKED = "PLAYBOOK_UNLINKED"

    # Tool events
    TOOL_CREATED = "TOOL_CREATED"
    TOOL_UPDATED = "TOOL_UPDATED"
    TOOL_ENABLED = "TOOL_ENABLED"
    TOOL_DISABLED = "TOOL_DISABLED"

    # Rate limit events
    RATE_LIMIT_CREATED = "RATE_LIMIT_CREATED"
    RATE_LIMIT_UPDATED = "RATE_LIMIT_UPDATED"
    RATE_LIMIT_DELETED = "RATE_LIMIT_DELETED"

    # Alert config events
    ALERT_CONFIG_CREATED = "ALERT_CONFIG_CREATED"
    ALERT_CONFIG_UPDATED = "ALERT_CONFIG_UPDATED"
    ALERT_CONFIG_ENABLED = "ALERT_CONFIG_ENABLED"
    ALERT_CONFIG_DISABLED = "ALERT_CONFIG_DISABLED"

    # Config change governance events
    CONFIG_CHANGE_SUBMITTED = "CONFIG_CHANGE_SUBMITTED"
    CONFIG_CHANGE_APPROVED = "CONFIG_CHANGE_APPROVED"
    CONFIG_CHANGE_REJECTED = "CONFIG_CHANGE_REJECTED"
    CONFIG_CHANGE_APPLIED = "CONFIG_CHANGE_APPLIED"


class EntityTypes:
    """Standard entity type constants."""

    TENANT = "tenant"
    DOMAIN_PACK = "domain_pack"
    TENANT_PACK = "tenant_pack"
    PLAYBOOK = "playbook"
    TOOL = "tool"
    RATE_LIMIT = "rate_limit"
    ALERT_CONFIG = "alert_config"
    CONFIG_CHANGE = "config_change"
    ACTIVE_CONFIG = "active_config"


class Actions:
    """Standard action constants."""

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
