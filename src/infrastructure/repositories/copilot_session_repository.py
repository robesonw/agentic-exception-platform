"""
Copilot Session Repository for Phase 13 Conversation Memory.

Provides CRUD operations for copilot sessions and messages with tenant isolation.

References:
- docs/phase13-copilot-intelligence-mvp.md Section 3, 5
- .github/ISSUE_TEMPLATE/phase13-copilot-intelligence-issues.md P13-14
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.infrastructure.db.models import CopilotMessage, CopilotSession
from src.repository.base import AbstractBaseRepository, PaginatedResult, RepositoryError

logger = logging.getLogger(__name__)


class CopilotSessionRepository(AbstractBaseRepository[CopilotSession]):
    """
    Repository for Copilot conversation sessions.

    Provides:
    - Session CRUD with tenant + user isolation
    - Message management within sessions
    - Session expiration and cleanup
    - Conversation history retrieval
    """

    def __init__(self, session: AsyncSession):
        """Initialize repository with session."""
        super().__init__(session)

    async def get_by_id(
        self,
        id: str,
        tenant_id: str,
    ) -> Optional[CopilotSession]:
        """
        Get session by ID with tenant isolation.

        Args:
            id: Session UUID as string
            tenant_id: Tenant identifier

        Returns:
            CopilotSession or None
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        try:
            session_uuid = UUID(id) if isinstance(id, str) else id
        except ValueError:
            return None

        query = select(CopilotSession).where(
            CopilotSession.id == session_uuid,
            CopilotSession.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalars().first()

    async def get_by_id_with_messages(
        self,
        id: str,
        tenant_id: str,
        message_limit: int = 50,
    ) -> Optional[CopilotSession]:
        """
        Get session by ID with messages eagerly loaded.

        Args:
            id: Session UUID as string
            tenant_id: Tenant identifier
            message_limit: Maximum messages to load

        Returns:
            CopilotSession with messages loaded
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        try:
            session_uuid = UUID(id) if isinstance(id, str) else id
        except ValueError:
            return None

        query = (
            select(CopilotSession)
            .options(selectinload(CopilotSession.messages))
            .where(
                CopilotSession.id == session_uuid,
                CopilotSession.tenant_id == tenant_id,
            )
        )
        result = await self.session.execute(query)
        session = result.scalars().first()

        # Limit messages if needed (they're already ordered by created_at)
        if session and len(session.messages) > message_limit:
            session.messages = session.messages[-message_limit:]

        return session

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        user_id: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> PaginatedResult[CopilotSession]:
        """
        List sessions for a tenant with pagination.

        Args:
            tenant_id: Tenant identifier
            page: Page number (1-indexed)
            page_size: Items per page
            user_id: Optional filter by user
            is_active: Optional filter by active status

        Returns:
            PaginatedResult with sessions
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(CopilotSession).where(CopilotSession.tenant_id == tenant_id)

        if user_id:
            query = query.where(CopilotSession.user_id == user_id)
        if is_active is not None:
            query = query.where(CopilotSession.is_active == is_active)

        query = query.order_by(CopilotSession.last_activity_at.desc())

        return await self._execute_paginated(query, page, page_size)

    async def list_by_user(
        self,
        tenant_id: str,
        user_id: str,
        page: int = 1,
        page_size: int = 20,
        active_only: bool = True,
    ) -> PaginatedResult[CopilotSession]:
        """
        List sessions for a specific user within a tenant.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            page: Page number
            page_size: Items per page
            active_only: Only return active sessions

        Returns:
            PaginatedResult with sessions
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        if not user_id:
            raise ValueError(f"user_id is required (Repository.get_sessions received: {repr(user_id)})")

        query = select(CopilotSession).where(
            CopilotSession.tenant_id == tenant_id,
            CopilotSession.user_id == user_id,
        )

        if active_only:
            query = query.where(CopilotSession.is_active == True)

        query = query.order_by(CopilotSession.last_activity_at.desc())

        return await self._execute_paginated(query, page, page_size)

    async def create_session(
        self,
        tenant_id: str,
        user_id: str,
        title: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
        ttl_hours: Optional[int] = None,
    ) -> CopilotSession:
        """
        Create a new conversation session.

        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            title: Optional session title
            context: Optional session context (exception_id, filters, etc.)
            ttl_hours: Optional TTL in hours

        Returns:
            Created CopilotSession
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        if not user_id:
            raise ValueError(f"user_id is required (Repository.create_session received: {repr(user_id)})")

        expires_at = None
        if ttl_hours:
            expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl_hours)

        copilot_session = CopilotSession(
            id=uuid4(),
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            context_json=context,
            expires_at=expires_at,
            is_active=True,
        )

        self.session.add(copilot_session)
        await self.session.flush()
        await self.session.refresh(copilot_session)

        logger.info(f"Created copilot session {copilot_session.id} for user {user_id}")
        return copilot_session

    async def update_session(
        self,
        session_id: str,
        tenant_id: str,
        title: Optional[str] = None,
        context: Optional[dict[str, Any]] = None,
    ) -> Optional[CopilotSession]:
        """
        Update session metadata.

        Args:
            session_id: Session UUID
            tenant_id: Tenant identifier
            title: New title (if provided)
            context: New context (if provided)

        Returns:
            Updated CopilotSession or None if not found
        """
        copilot_session = await self.get_by_id(session_id, tenant_id)
        if not copilot_session:
            return None

        if title is not None:
            copilot_session.title = title
        if context is not None:
            copilot_session.context_json = context

        await self.session.flush()
        await self.session.refresh(copilot_session)

        return copilot_session

    async def deactivate_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> bool:
        """
        Soft-delete a session by marking it inactive.

        Args:
            session_id: Session UUID
            tenant_id: Tenant identifier

        Returns:
            True if session was deactivated, False if not found
        """
        copilot_session = await self.get_by_id(session_id, tenant_id)
        if not copilot_session:
            return False

        copilot_session.is_active = False
        await self.session.flush()

        logger.info(f"Deactivated copilot session {session_id}")
        return True

    async def delete_session(
        self,
        session_id: str,
        tenant_id: str,
    ) -> bool:
        """
        Hard-delete a session and all its messages.

        Args:
            session_id: Session UUID
            tenant_id: Tenant identifier

        Returns:
            True if session was deleted, False if not found
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        try:
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
        except ValueError:
            return False

        stmt = delete(CopilotSession).where(
            CopilotSession.id == session_uuid,
            CopilotSession.tenant_id == tenant_id,
        )
        result = await self.session.execute(stmt)
        await self.session.flush()

        deleted = result.rowcount > 0
        if deleted:
            logger.info(f"Deleted copilot session {session_id}")

        return deleted

    async def add_message(
        self,
        session_id: str,
        tenant_id: str,
        role: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
        intent: Optional[str] = None,
        request_id: Optional[str] = None,
        exception_id: Optional[str] = None,
        tokens_used: Optional[int] = None,
        latency_ms: Optional[int] = None,
    ) -> CopilotMessage:
        """
        Add a message to a session.

        Args:
            session_id: Session UUID
            tenant_id: Tenant identifier
            role: Message role (user, assistant, system)
            content: Message content
            metadata: Optional metadata (citations, playbooks, etc.)
            intent: Detected intent for user messages
            request_id: Request ID for tracing
            exception_id: Related exception ID
            tokens_used: Token count for metering
            latency_ms: Response latency

        Returns:
            Created CopilotMessage

        Raises:
            RepositoryError: If session not found
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        # Verify session exists and belongs to tenant
        copilot_session = await self.get_by_id(session_id, tenant_id)
        if not copilot_session:
            raise RepositoryError(
                f"Session {session_id} not found",
                entity_type="CopilotSession",
                entity_id=session_id,
            )

        try:
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
        except ValueError:
            raise RepositoryError(f"Invalid session ID: {session_id}")

        message = CopilotMessage(
            session_id=session_uuid,
            tenant_id=tenant_id,
            role=role,
            content=content,
            metadata_json=metadata,
            intent=intent,
            request_id=request_id,
            exception_id=exception_id,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
        )

        self.session.add(message)
        await self.session.flush()
        await self.session.refresh(message)

        # Update session last_activity_at
        copilot_session.last_activity_at = datetime.now(timezone.utc)
        await self.session.flush()

        logger.debug(f"Added {role} message to session {session_id}")
        return message

    async def get_messages(
        self,
        session_id: str,
        tenant_id: str,
        limit: int = 50,
        before_id: Optional[int] = None,
    ) -> list[CopilotMessage]:
        """
        Get messages for a session.

        Args:
            session_id: Session UUID
            tenant_id: Tenant identifier
            limit: Maximum messages to return
            before_id: Get messages before this ID (for pagination)

        Returns:
            List of messages ordered by created_at ascending
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        try:
            session_uuid = UUID(session_id) if isinstance(session_id, str) else session_id
        except ValueError:
            return []

        query = select(CopilotMessage).where(
            CopilotMessage.session_id == session_uuid,
            CopilotMessage.tenant_id == tenant_id,
        )

        if before_id:
            query = query.where(CopilotMessage.id < before_id)

        query = query.order_by(CopilotMessage.created_at.desc()).limit(limit)

        result = await self.session.execute(query)
        messages = list(result.scalars().all())

        # Reverse to get ascending order
        return messages[::-1]

    async def get_recent_messages(
        self,
        session_id: str,
        tenant_id: str,
        count: int = 10,
    ) -> list[CopilotMessage]:
        """
        Get the most recent messages for a session.

        Args:
            session_id: Session UUID
            tenant_id: Tenant identifier
            count: Number of recent messages

        Returns:
            List of recent messages ordered by created_at ascending
        """
        return await self.get_messages(session_id, tenant_id, limit=count)

    async def cleanup_expired_sessions(
        self,
        tenant_id: Optional[str] = None,
    ) -> int:
        """
        Delete expired sessions (based on expires_at).

        Args:
            tenant_id: Optional tenant filter (if None, cleans all tenants)

        Returns:
            Number of sessions deleted
        """
        now = datetime.now(timezone.utc)

        stmt = delete(CopilotSession).where(
            CopilotSession.expires_at.isnot(None),
            CopilotSession.expires_at < now,
        )

        if tenant_id:
            stmt = stmt.where(CopilotSession.tenant_id == tenant_id)

        result = await self.session.execute(stmt)
        await self.session.flush()

        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} expired sessions")

        return count

    async def cleanup_inactive_sessions(
        self,
        inactive_hours: int = 24,
        tenant_id: Optional[str] = None,
    ) -> int:
        """
        Delete sessions with no activity for specified hours.

        Args:
            inactive_hours: Hours of inactivity before cleanup
            tenant_id: Optional tenant filter

        Returns:
            Number of sessions deleted
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=inactive_hours)

        stmt = delete(CopilotSession).where(
            CopilotSession.last_activity_at < cutoff,
            CopilotSession.is_active == False,
        )

        if tenant_id:
            stmt = stmt.where(CopilotSession.tenant_id == tenant_id)

        result = await self.session.execute(stmt)
        await self.session.flush()

        count = result.rowcount
        if count > 0:
            logger.info(f"Cleaned up {count} inactive sessions")

        return count

    async def count_sessions_by_user(
        self,
        tenant_id: str,
        user_id: str,
        active_only: bool = True,
    ) -> int:
        """Count sessions for a user."""
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        from sqlalchemy import func
        query = select(func.count()).select_from(CopilotSession).where(
            CopilotSession.tenant_id == tenant_id,
            CopilotSession.user_id == user_id,
        )

        if active_only:
            query = query.where(CopilotSession.is_active == True)

        result = await self.session.execute(query)
        return result.scalar_one() or 0

    async def get_message_by_request_id(
        self,
        request_id: str,
        tenant_id: str,
    ) -> Optional[CopilotMessage]:
        """
        Get a message by its request ID.

        Args:
            request_id: Request ID for tracing
            tenant_id: Tenant identifier

        Returns:
            CopilotMessage or None
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(CopilotMessage).where(
            CopilotMessage.request_id == request_id,
            CopilotMessage.tenant_id == tenant_id,
        )
        result = await self.session.execute(query)
        return result.scalars().first()
