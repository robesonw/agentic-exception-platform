"""
Governance Audit Repository for Phase 12+ Enterprise Audit Trail.

Provides data access for governance audit events including:
- Creating audit events with redaction
- Querying events with filtering and pagination
- Timeline queries for entity history

Reference: Phase 12+ Governance & Audit Polish requirements.
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import and_, desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import GovernanceAuditEvent
from src.services.governance_audit import (
    AuditEventFilter,
    GovernanceAuditEventCreate,
    GovernanceAuditEventResponse,
    PaginatedResult,
    generate_diff_summary,
    get_actor_context,
    get_correlation_id,
    get_request_id,
    redact_payload,
)

logger = logging.getLogger(__name__)


class GovernanceAuditRepository:
    """Repository for governance audit event operations."""

    def __init__(self, session: AsyncSession):
        """Initialize with database session."""
        self.session = session

    async def create_event(
        self,
        event_type: str,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: Optional[str] = None,
        actor_role: Optional[str] = None,
        tenant_id: Optional[str] = None,
        domain: Optional[str] = None,
        entity_version: Optional[str] = None,
        before_json: Optional[dict] = None,
        after_json: Optional[dict] = None,
        diff_summary: Optional[str] = None,
        correlation_id: Optional[str] = None,
        request_id: Optional[str] = None,
        related_exception_id: Optional[str] = None,
        related_change_request_id: Optional[str] = None,
        metadata: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        auto_redact: bool = True,
    ) -> GovernanceAuditEvent:
        """
        Create a new governance audit event.

        Automatically:
        - Redacts sensitive data from before_json, after_json, and metadata
        - Generates diff_summary if not provided
        - Uses context values for correlation_id, request_id, actor if not provided

        Args:
            event_type: Event type (e.g., TENANT_CREATED)
            entity_type: Entity type (e.g., tenant, domain_pack)
            entity_id: Entity identifier
            action: Action performed (e.g., create, update, activate)
            actor_id: Actor identifier (optional, uses context if not provided)
            actor_role: Actor role (optional, uses context if not provided)
            tenant_id: Tenant identifier (optional for global events)
            domain: Domain name (optional)
            entity_version: Entity version (optional)
            before_json: State before change (optional, will be redacted)
            after_json: State after change (optional, will be redacted)
            diff_summary: Human-readable diff (optional, auto-generated if not provided)
            correlation_id: Correlation ID (optional, uses context if not provided)
            request_id: Request ID (optional, uses context if not provided)
            related_exception_id: Related exception ID (optional)
            related_change_request_id: Related config change request ID (optional)
            metadata: Additional metadata (optional, will be redacted)
            ip_address: Client IP address (optional, uses context if not provided)
            user_agent: Client user agent (optional, uses context if not provided)
            auto_redact: Whether to auto-redact sensitive data (default True)

        Returns:
            Created GovernanceAuditEvent
        """
        # Get context values if not provided
        actor_ctx = get_actor_context()
        if actor_id is None and actor_ctx:
            actor_id = actor_ctx.get("actor_id", "system")
        if actor_id is None:
            actor_id = "system"

        if actor_role is None and actor_ctx:
            actor_role = actor_ctx.get("actor_role")

        if ip_address is None and actor_ctx:
            ip_address = actor_ctx.get("ip_address")

        if user_agent is None and actor_ctx:
            user_agent = actor_ctx.get("user_agent")

        if correlation_id is None:
            correlation_id = get_correlation_id()

        if request_id is None:
            request_id = get_request_id()

        # Redact sensitive data
        if auto_redact:
            before_json = redact_payload(before_json) if before_json else None
            after_json = redact_payload(after_json) if after_json else None
            metadata = redact_payload(metadata) if metadata else None

        # Generate diff summary if not provided
        if diff_summary is None and (before_json is not None or after_json is not None):
            diff_summary = generate_diff_summary(before_json, after_json)

        # Create event
        event = GovernanceAuditEvent(
            id=uuid4(),
            event_type=event_type,
            actor_id=actor_id,
            actor_role=actor_role,
            tenant_id=tenant_id,
            domain=domain,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_version=entity_version,
            action=action,
            before_json=before_json,
            after_json=after_json,
            diff_summary=diff_summary,
            correlation_id=correlation_id,
            request_id=request_id,
            related_exception_id=related_exception_id,
            related_change_request_id=related_change_request_id,
            event_metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        self.session.add(event)

        logger.info(
            f"Audit event created: {event_type} | entity={entity_type}:{entity_id} | "
            f"action={action} | actor={actor_id} | tenant={tenant_id}"
        )

        return event

    async def get_by_id(self, event_id: str) -> Optional[GovernanceAuditEvent]:
        """
        Get an audit event by ID.

        Args:
            event_id: Event ID (UUID)

        Returns:
            GovernanceAuditEvent or None if not found
        """
        query = select(GovernanceAuditEvent).where(
            GovernanceAuditEvent.id == event_id
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def query_events(
        self,
        filter_params: AuditEventFilter,
        page: int = 1,
        page_size: int = 50,
        order_by_desc: bool = True,
    ) -> PaginatedResult:
        """
        Query audit events with filtering and pagination.

        Args:
            filter_params: Filter parameters
            page: Page number (1-indexed)
            page_size: Items per page
            order_by_desc: Order by created_at descending (default True)

        Returns:
            PaginatedResult with events and pagination info
        """
        # Build base query
        query = select(GovernanceAuditEvent)
        conditions = []

        if filter_params.tenant_id:
            conditions.append(GovernanceAuditEvent.tenant_id == filter_params.tenant_id)

        if filter_params.domain:
            conditions.append(GovernanceAuditEvent.domain == filter_params.domain)

        if filter_params.entity_type:
            conditions.append(GovernanceAuditEvent.entity_type == filter_params.entity_type)

        if filter_params.entity_id:
            conditions.append(GovernanceAuditEvent.entity_id == filter_params.entity_id)

        if filter_params.event_type:
            conditions.append(GovernanceAuditEvent.event_type == filter_params.event_type)

        if filter_params.action:
            conditions.append(GovernanceAuditEvent.action == filter_params.action)

        if filter_params.actor_id:
            conditions.append(GovernanceAuditEvent.actor_id == filter_params.actor_id)

        if filter_params.correlation_id:
            conditions.append(GovernanceAuditEvent.correlation_id == filter_params.correlation_id)

        if filter_params.from_date:
            conditions.append(GovernanceAuditEvent.created_at >= filter_params.from_date)

        if filter_params.to_date:
            conditions.append(GovernanceAuditEvent.created_at <= filter_params.to_date)

        if conditions:
            query = query.where(and_(*conditions))

        # Get total count
        count_query = select(func.count(GovernanceAuditEvent.id))
        if conditions:
            count_query = count_query.where(and_(*conditions))
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply ordering
        if order_by_desc:
            query = query.order_by(desc(GovernanceAuditEvent.created_at))
        else:
            query = query.order_by(GovernanceAuditEvent.created_at)

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        # Execute query
        result = await self.session.execute(query)
        events = list(result.scalars().all())

        return PaginatedResult(
            items=events,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_entity_timeline(
        self,
        entity_type: str,
        entity_id: str,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[GovernanceAuditEvent]:
        """
        Get timeline of events for a specific entity.

        Args:
            entity_type: Entity type
            entity_id: Entity identifier
            tenant_id: Tenant identifier (optional for tenant-scoped entities)
            limit: Maximum number of events to return

        Returns:
            List of audit events ordered by created_at descending
        """
        conditions = [
            GovernanceAuditEvent.entity_type == entity_type,
            GovernanceAuditEvent.entity_id == entity_id,
        ]

        if tenant_id:
            conditions.append(GovernanceAuditEvent.tenant_id == tenant_id)

        query = (
            select(GovernanceAuditEvent)
            .where(and_(*conditions))
            .order_by(desc(GovernanceAuditEvent.created_at))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_recent_events_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        tenant_id: Optional[str] = None,
        limit: int = 5,
    ) -> list[GovernanceAuditEvent]:
        """
        Get the most recent events for an entity (for "Recent Changes" panels).

        Args:
            entity_type: Entity type
            entity_id: Entity identifier
            tenant_id: Tenant identifier (optional)
            limit: Maximum number of events (default 5)

        Returns:
            List of recent audit events
        """
        return await self.get_entity_timeline(entity_type, entity_id, tenant_id, limit)

    async def get_recent_events_by_tenant(
        self,
        tenant_id: str,
        limit: int = 20,
        entity_types: Optional[list[str]] = None,
    ) -> list[GovernanceAuditEvent]:
        """
        Get recent events for a tenant across all entity types.

        Args:
            tenant_id: Tenant identifier
            limit: Maximum number of events
            entity_types: Optional list of entity types to filter

        Returns:
            List of recent audit events
        """
        conditions = [GovernanceAuditEvent.tenant_id == tenant_id]

        if entity_types:
            conditions.append(GovernanceAuditEvent.entity_type.in_(entity_types))

        query = (
            select(GovernanceAuditEvent)
            .where(and_(*conditions))
            .order_by(desc(GovernanceAuditEvent.created_at))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_events_by_correlation_id(
        self,
        correlation_id: str,
    ) -> list[GovernanceAuditEvent]:
        """
        Get all events for a correlation ID (for distributed tracing).

        Args:
            correlation_id: Correlation identifier

        Returns:
            List of related audit events
        """
        query = (
            select(GovernanceAuditEvent)
            .where(GovernanceAuditEvent.correlation_id == correlation_id)
            .order_by(GovernanceAuditEvent.created_at)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_pending_approvals_audit(
        self,
        tenant_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[GovernanceAuditEvent]:
        """
        Get audit events related to pending config change approvals.

        Args:
            tenant_id: Optional tenant ID filter
            limit: Maximum number of events

        Returns:
            List of approval-related audit events
        """
        from src.services.governance_audit import AuditEventTypes

        conditions = [
            GovernanceAuditEvent.event_type.in_([
                AuditEventTypes.CONFIG_CHANGE_SUBMITTED,
                AuditEventTypes.CONFIG_ACTIVATION_REQUESTED,
            ])
        ]

        if tenant_id:
            conditions.append(GovernanceAuditEvent.tenant_id == tenant_id)

        query = (
            select(GovernanceAuditEvent)
            .where(and_(*conditions))
            .order_by(desc(GovernanceAuditEvent.created_at))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())


def event_to_response(event: GovernanceAuditEvent) -> GovernanceAuditEventResponse:
    """
    Convert a GovernanceAuditEvent model to response model.

    Args:
        event: Database model

    Returns:
        Response model
    """
    return GovernanceAuditEventResponse(
        id=str(event.id),
        event_type=event.event_type,
        actor_id=event.actor_id,
        actor_role=event.actor_role,
        tenant_id=event.tenant_id,
        domain=event.domain,
        entity_type=event.entity_type,
        entity_id=event.entity_id,
        entity_version=event.entity_version,
        action=event.action,
        before_json=event.before_json,
        after_json=event.after_json,
        diff_summary=event.diff_summary,
        correlation_id=event.correlation_id,
        request_id=event.request_id,
        related_exception_id=event.related_exception_id,
        related_change_request_id=event.related_change_request_id,
        metadata=event.event_metadata,
        ip_address=event.ip_address,
        user_agent=event.user_agent,
        created_at=event.created_at,
    )
