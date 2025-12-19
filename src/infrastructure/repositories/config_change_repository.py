"""
Config Change Repository for Phase 10 (P10-10).

Provides CRUD operations for configuration change requests with tenant isolation.
Supports governance workflow: submit -> review -> approve/reject -> apply

Reference: docs/phase10-ops-governance-mvp.md Section 7
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    ConfigChangeRequest,
    ConfigChangeStatus,
    ConfigChangeType,
)
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


def generate_change_id() -> str:
    """Generate a unique change request ID."""
    return str(uuid.uuid4())


@dataclass
class ConfigChangeStats:
    """Statistics about config change requests for a tenant."""
    tenant_id: str
    total_requests: int
    pending_count: int
    approved_count: int
    rejected_count: int
    applied_count: int
    by_change_type: dict[str, int]


class ConfigChangeRepository(AbstractBaseRepository[ConfigChangeRequest]):
    """
    Repository for configuration change request management.

    Provides:
    - Create change requests (submit)
    - Get change request by ID
    - List change requests for a tenant
    - Approve/reject change requests (review)
    - Mark change requests as applied

    All operations enforce tenant isolation.
    """

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[ConfigChangeRequest]:
        """Get config change request by ID with tenant isolation."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(ConfigChangeRequest)
            .where(ConfigChangeRequest.id == id)
            .where(ConfigChangeRequest.tenant_id == tenant_id)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[ConfigChangeRequest]:
        """List config change requests for a tenant with pagination."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        # Build base query with filters
        query = select(ConfigChangeRequest).where(
            ConfigChangeRequest.tenant_id == tenant_id
        )

        # Apply filters
        if filters.get("status"):
            query = query.where(ConfigChangeRequest.status == filters["status"])
        if filters.get("change_type"):
            query = query.where(
                ConfigChangeRequest.change_type == filters["change_type"]
            )
        if filters.get("requested_by"):
            query = query.where(
                ConfigChangeRequest.requested_by == filters["requested_by"]
            )

        # Get total count (build separate count query without ordering/pagination)
        count_query = select(func.count(ConfigChangeRequest.id)).where(
            ConfigChangeRequest.tenant_id == tenant_id
        )
        if filters.get("status"):
            count_query = count_query.where(ConfigChangeRequest.status == filters["status"])
        if filters.get("change_type"):
            count_query = count_query.where(
                ConfigChangeRequest.change_type == filters["change_type"]
            )
        if filters.get("requested_by"):
            count_query = count_query.where(
                ConfigChangeRequest.requested_by == filters["requested_by"]
            )
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply ordering and pagination to main query
        query = query.order_by(desc(ConfigChangeRequest.requested_at))
        offset = (page - 1) * page_size
        query = query.offset(offset).limit(page_size)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_change_request(
        self,
        tenant_id: str,
        change_type: str,
        resource_id: str,
        proposed_config: dict,
        requested_by: str,
        resource_name: Optional[str] = None,
        current_config: Optional[dict] = None,
        diff_summary: Optional[str] = None,
        change_reason: Optional[str] = None,
    ) -> ConfigChangeRequest:
        """
        Create a new config change request.

        Args:
            tenant_id: Tenant identifier
            change_type: Type of change (domain_pack, tenant_policy, tool, playbook)
            resource_id: ID of the resource being changed
            proposed_config: Proposed new configuration
            requested_by: User requesting the change
            resource_name: Optional human-readable name
            current_config: Optional snapshot of current config
            diff_summary: Optional human-readable diff
            change_reason: Optional reason for the change

        Returns:
            Created ConfigChangeRequest
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        change_id = generate_change_id()

        change_request = ConfigChangeRequest(
            id=change_id,
            tenant_id=tenant_id,
            change_type=change_type,
            resource_id=resource_id,
            resource_name=resource_name,
            current_config=current_config,
            proposed_config=proposed_config,
            diff_summary=diff_summary,
            change_reason=change_reason,
            status="pending",
            requested_by=requested_by,
            requested_at=datetime.now(timezone.utc),
        )

        self.session.add(change_request)
        await self.session.flush()
        await self.session.refresh(change_request)

        logger.info(
            f"Created config change request: id={change_id}, tenant_id={tenant_id}, "
            f"change_type={change_type}, resource_id={resource_id}"
        )

        return change_request

    async def approve_change_request(
        self,
        change_id: str,
        tenant_id: str,
        reviewed_by: str,
        review_comment: Optional[str] = None,
    ) -> Optional[ConfigChangeRequest]:
        """
        Approve a pending config change request.

        Args:
            change_id: Change request ID
            tenant_id: Tenant identifier
            reviewed_by: User approving the change
            review_comment: Optional comment

        Returns:
            Updated ConfigChangeRequest or None if not found
        """
        change_request = await self.get_by_id(change_id, tenant_id)
        if not change_request:
            return None

        if change_request.status != "pending":
            logger.warning(
                f"Cannot approve change request {change_id}: status is {change_request.status}"
            )
            raise ValueError(
                f"Change request is not pending (status: {change_request.status})"
            )

        change_request.status = "approved"
        change_request.reviewed_by = reviewed_by
        change_request.reviewed_at = datetime.now(timezone.utc)
        change_request.review_comment = review_comment

        await self.session.flush()
        await self.session.refresh(change_request)

        logger.info(
            f"Approved config change request: id={change_id}, reviewed_by={reviewed_by}"
        )

        return change_request

    async def reject_change_request(
        self,
        change_id: str,
        tenant_id: str,
        reviewed_by: str,
        review_comment: Optional[str] = None,
    ) -> Optional[ConfigChangeRequest]:
        """
        Reject a pending config change request.

        Args:
            change_id: Change request ID
            tenant_id: Tenant identifier
            reviewed_by: User rejecting the change
            review_comment: Optional comment explaining rejection

        Returns:
            Updated ConfigChangeRequest or None if not found
        """
        change_request = await self.get_by_id(change_id, tenant_id)
        if not change_request:
            return None

        if change_request.status != "pending":
            logger.warning(
                f"Cannot reject change request {change_id}: status is {change_request.status}"
            )
            raise ValueError(
                f"Change request is not pending (status: {change_request.status})"
            )

        change_request.status = "rejected"
        change_request.reviewed_by = reviewed_by
        change_request.reviewed_at = datetime.now(timezone.utc)
        change_request.review_comment = review_comment

        await self.session.flush()
        await self.session.refresh(change_request)

        logger.info(
            f"Rejected config change request: id={change_id}, reviewed_by={reviewed_by}"
        )

        return change_request

    async def mark_as_applied(
        self,
        change_id: str,
        tenant_id: str,
        applied_by: str,
    ) -> Optional[ConfigChangeRequest]:
        """
        Mark an approved change request as applied.

        Args:
            change_id: Change request ID
            tenant_id: Tenant identifier
            applied_by: User who applied the change

        Returns:
            Updated ConfigChangeRequest or None if not found
        """
        change_request = await self.get_by_id(change_id, tenant_id)
        if not change_request:
            return None

        if change_request.status != "approved":
            logger.warning(
                f"Cannot apply change request {change_id}: status is {change_request.status}"
            )
            raise ValueError(
                f"Change request is not approved (status: {change_request.status})"
            )

        # Store current config for potential rollback
        change_request.rollback_config = change_request.current_config
        change_request.status = "applied"
        change_request.applied_at = datetime.now(timezone.utc)
        change_request.applied_by = applied_by

        await self.session.flush()
        await self.session.refresh(change_request)

        logger.info(
            f"Applied config change request: id={change_id}, applied_by={applied_by}"
        )

        return change_request

    async def get_pending_requests(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[ConfigChangeRequest]:
        """Get all pending change requests for a tenant."""
        return await self.list_by_tenant(
            tenant_id=tenant_id,
            page=page,
            page_size=page_size,
            status="pending",
        )

    async def get_stats(self, tenant_id: str) -> ConfigChangeStats:
        """
        Get statistics about config change requests for a tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            ConfigChangeStats with counts and breakdowns
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        # Get total count
        total_query = (
            select(func.count())
            .select_from(ConfigChangeRequest)
            .where(ConfigChangeRequest.tenant_id == tenant_id)
        )
        total_result = await self.session.execute(total_query)
        total = total_result.scalar() or 0

        # Get counts by status
        status_query = (
            select(
                ConfigChangeRequest.status,
                func.count().label("count"),
            )
            .where(ConfigChangeRequest.tenant_id == tenant_id)
            .group_by(ConfigChangeRequest.status)
        )
        status_result = await self.session.execute(status_query)
        status_counts = {row.status: row.count for row in status_result.fetchall()}

        # Get counts by change type
        type_query = (
            select(
                ConfigChangeRequest.change_type,
                func.count().label("count"),
            )
            .where(ConfigChangeRequest.tenant_id == tenant_id)
            .group_by(ConfigChangeRequest.change_type)
        )
        type_result = await self.session.execute(type_query)
        type_counts = {row.change_type: row.count for row in type_result.fetchall()}

        return ConfigChangeStats(
            tenant_id=tenant_id,
            total_requests=total,
            pending_count=status_counts.get("pending", 0),
            approved_count=status_counts.get("approved", 0),
            rejected_count=status_counts.get("rejected", 0),
            applied_count=status_counts.get("applied", 0),
            by_change_type=type_counts,
        )

    async def get_requests_by_resource(
        self,
        tenant_id: str,
        resource_id: str,
        change_type: Optional[str] = None,
    ) -> list[ConfigChangeRequest]:
        """
        Get all change requests for a specific resource.

        Args:
            tenant_id: Tenant identifier
            resource_id: Resource ID
            change_type: Optional filter by change type

        Returns:
            List of ConfigChangeRequest for the resource
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(ConfigChangeRequest)
            .where(ConfigChangeRequest.tenant_id == tenant_id)
            .where(ConfigChangeRequest.resource_id == resource_id)
        )

        if change_type:
            query = query.where(ConfigChangeRequest.change_type == change_type)

        query = query.order_by(desc(ConfigChangeRequest.requested_at))

        result = await self.session.execute(query)
        return list(result.scalars().all())
