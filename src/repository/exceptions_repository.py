"""
Exception repository with full CRUD operations and Co-Pilot query helpers.

Phase 6 P6-6: Complete CRUD operations for exceptions with filtering and pagination.
Phase 6 P6-7: Co-Pilot query helpers for contextual retrieval.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import Exception, ExceptionSeverity, ExceptionStatus
from src.repository.base import AbstractBaseRepository, PaginatedResult
from src.repository.dto import (
    ExceptionCreateDTO,
    ExceptionCreateOrUpdateDTO,
    ExceptionFilter,
    ExceptionUpdateDTO,
)

logger = logging.getLogger(__name__)


class ExceptionRepository(AbstractBaseRepository[Exception]):
    """
    Repository for exception operations with full CRUD support.
    
    Provides:
    - Idempotent upsert operations (P6-5)
    - Full CRUD operations (P6-6)
    - Filtering and pagination
    - Tenant isolation enforcement
    """

    async def upsert_exception(
        self,
        tenant_id: str,
        exception_data: ExceptionCreateOrUpdateDTO,
    ) -> Exception:
        """
        Upsert an exception (idempotent create or update).
        
        If exception_id exists for this tenant, update the existing row.
        If not, create a new exception.
        
        This method is idempotent: multiple calls with the same exception_id
        and tenant_id will not create duplicates. Uses primary key
        (exception_id) + tenant_id as uniqueness guard.
        
        Args:
            tenant_id: Tenant identifier (must match exception_data.tenant_id)
            exception_data: Exception data for create/update
            
        Returns:
            Exception model instance (created or updated)
            
        Raises:
            ValueError: If tenant_id doesn't match exception_data.tenant_id
        """
        if tenant_id != exception_data.tenant_id:
            raise ValueError(
                f"tenant_id parameter ({tenant_id}) must match "
                f"exception_data.tenant_id ({exception_data.tenant_id})"
            )
        
        # Check if exception already exists
        existing = await self.get_by_id(exception_data.exception_id, tenant_id)
        
        if existing:
            # Update existing exception
            logger.debug(
                f"Updating existing exception {exception_data.exception_id} "
                f"for tenant {tenant_id}"
            )
            
            existing.domain = exception_data.domain
            existing.type = exception_data.type
            existing.severity = exception_data.severity
            existing.status = exception_data.status
            existing.source_system = exception_data.source_system
            existing.entity = exception_data.entity
            existing.amount = exception_data.amount
            existing.sla_deadline = exception_data.sla_deadline
            existing.owner = exception_data.owner
            existing.current_playbook_id = exception_data.current_playbook_id
            existing.current_step = exception_data.current_step
            
            await self.session.flush()
            await self.session.refresh(existing)
            
            return existing
        else:
            # Create new exception
            logger.debug(
                f"Creating new exception {exception_data.exception_id} "
                f"for tenant {tenant_id}"
            )
            
            new_exception = Exception(
                exception_id=exception_data.exception_id,
                tenant_id=exception_data.tenant_id,
                domain=exception_data.domain,
                type=exception_data.type,
                severity=exception_data.severity,
                status=exception_data.status,
                source_system=exception_data.source_system,
                entity=exception_data.entity,
                amount=exception_data.amount,
                sla_deadline=exception_data.sla_deadline,
                owner=exception_data.owner,
                current_playbook_id=exception_data.current_playbook_id,
                current_step=exception_data.current_step,
            )
            
            self.session.add(new_exception)
            await self.session.flush()
            await self.session.refresh(new_exception)
            
            return new_exception

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[Exception]:
        """
        Get exception by ID with tenant isolation.
        
        Args:
            id: Exception identifier
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            Exception instance or None if not found
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(Exception).where(Exception.exception_id == id)
        query = self._tenant_filter(query, tenant_id, Exception.tenant_id)
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_exception(
        self,
        tenant_id: str,
        data: ExceptionCreateDTO,
    ) -> Exception:
        """
        Create a new exception.
        
        Args:
            tenant_id: Tenant identifier (must match data.tenant_id)
            data: Exception creation data
            
        Returns:
            Created Exception model instance
            
        Raises:
            ValueError: If tenant_id doesn't match data.tenant_id
            ValueError: If exception with same exception_id already exists for tenant
        """
        if tenant_id != data.tenant_id:
            raise ValueError(
                f"tenant_id parameter ({tenant_id}) must match "
                f"data.tenant_id ({data.tenant_id})"
            )
        
        # Check if exception already exists
        existing = await self.get_by_id(data.exception_id, tenant_id)
        if existing:
            raise ValueError(
                f"Exception {data.exception_id} already exists for tenant {tenant_id}. "
                "Use update_exception or upsert_exception instead."
            )
        
        logger.debug(
            f"Creating new exception {data.exception_id} for tenant {tenant_id}"
        )
        
        new_exception = Exception(
            exception_id=data.exception_id,
            tenant_id=data.tenant_id,
            domain=data.domain,
            type=data.type,
            severity=data.severity,
            status=data.status,
            source_system=data.source_system,
            entity=data.entity,
            amount=data.amount,
            sla_deadline=data.sla_deadline,
            owner=data.owner,
            current_playbook_id=data.current_playbook_id,
            current_step=data.current_step,
        )
        
        self.session.add(new_exception)
        await self.session.flush()
        await self.session.refresh(new_exception)
        
        return new_exception

    async def get_exception(self, tenant_id: str, exception_id: str) -> Optional[Exception]:
        """
        Get exception by ID with tenant isolation.
        
        Alias for get_by_id for consistency with other CRUD methods.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            exception_id: Exception identifier
            
        Returns:
            Exception instance or None if not found
        """
        return await self.get_by_id(exception_id, tenant_id)

    async def update_exception(
        self,
        tenant_id: str,
        exception_id: str,
        updates: ExceptionUpdateDTO,
    ) -> Optional[Exception]:
        """
        Update an existing exception.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            exception_id: Exception identifier
            updates: Update data (only provided fields will be updated)
            
        Returns:
            Updated Exception instance or None if not found
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Get existing exception
        existing = await self.get_by_id(exception_id, tenant_id)
        if not existing:
            logger.debug(
                f"Exception {exception_id} not found for tenant {tenant_id}, "
                "cannot update"
            )
            return None
        
        logger.debug(
            f"Updating exception {exception_id} for tenant {tenant_id}"
        )
        
        # Update only provided fields
        if updates.domain is not None:
            existing.domain = updates.domain
        if updates.type is not None:
            existing.type = updates.type
        if updates.severity is not None:
            existing.severity = updates.severity
        if updates.status is not None:
            existing.status = updates.status
        if updates.source_system is not None:
            existing.source_system = updates.source_system
        if updates.entity is not None:
            existing.entity = updates.entity
        if updates.amount is not None:
            existing.amount = updates.amount
        if updates.sla_deadline is not None:
            existing.sla_deadline = updates.sla_deadline
        if updates.owner is not None:
            existing.owner = updates.owner
        if updates.current_playbook_id is not None:
            existing.current_playbook_id = updates.current_playbook_id
        if updates.current_step is not None:
            existing.current_step = updates.current_step
        
        await self.session.flush()
        await self.session.refresh(existing)
        
        return existing

    async def list_exceptions(
        self,
        tenant_id: str,
        filters: ExceptionFilter,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[Exception]:
        """
        List exceptions for a tenant with filtering and pagination.
        
        Args:
            tenant_id: Tenant identifier (required)
            filters: Filter criteria (domain, status, severity, date range)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with exceptions and pagination metadata
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Build base query with tenant filter
        query = select(Exception)
        query = self._tenant_filter(query, tenant_id, Exception.tenant_id)
        
        # Apply filters
        if filters.domain is not None:
            query = query.where(Exception.domain == filters.domain)
        if filters.status is not None:
            query = query.where(Exception.status == filters.status)
        if filters.severity is not None:
            query = query.where(Exception.severity == filters.severity)
        if filters.created_from is not None:
            query = query.where(Exception.created_at >= filters.created_from)
        if filters.created_to is not None:
            query = query.where(Exception.created_at <= filters.created_to)
        
        # Order by created_at DESC (newest first)
        query = query.order_by(Exception.created_at.desc())
        
        return await self._execute_paginated(query, page, page_size)

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[Exception]:
        """
        List exceptions for a tenant with pagination.
        
        This method is kept for backward compatibility and calls list_exceptions.
        For new code, use list_exceptions with ExceptionFilter.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (legacy format)
            
        Returns:
            PaginatedResult with exceptions and pagination metadata
        """
        # Convert legacy filters to ExceptionFilter
        exception_filter = ExceptionFilter(
            domain=filters.get("domain"),
            status=filters.get("status"),
            severity=filters.get("severity"),
            created_from=filters.get("created_from"),
            created_to=filters.get("created_to"),
        )
        
        return await self.list_exceptions(tenant_id, exception_filter, page, page_size)

    # ============================================================================
    # Co-Pilot Query Helpers (P6-7)
    # ============================================================================

    async def find_similar_exceptions(
        self,
        tenant_id: str,
        domain: str | None = None,
        exception_type: str | None = None,
        limit: int = 10,
    ) -> list[Exception]:
        """
        Find similar exceptions for Co-Pilot contextual retrieval.
        
        This method primarily serves Co-Pilot retrieval needs and must respect tenant isolation.
        Currently uses basic filtering by domain and type. In future phases, this can be
        enhanced with vector search / RAG for semantic similarity without changing the
        calling contract.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            domain: Optional domain filter
            exception_type: Optional exception type filter
            limit: Maximum number of results (default: 10)
            
        Returns:
            List of similar Exception instances, ordered by created_at DESC (newest first)
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(Exception)
        query = self._tenant_filter(query, tenant_id, Exception.tenant_id)
        
        # Apply optional filters
        if domain is not None:
            query = query.where(Exception.domain == domain)
        if exception_type is not None:
            query = query.where(Exception.type == exception_type)
        
        # Order by created_at DESC (newest first)
        query = query.order_by(Exception.created_at.desc())
        
        # Apply limit
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_exceptions_by_entity(
        self,
        tenant_id: str,
        entity: str,
        limit: int = 50,
    ) -> list[Exception]:
        """
        Get exceptions by entity identifier for Co-Pilot contextual retrieval.
        
        This method primarily serves Co-Pilot retrieval needs and must respect tenant isolation.
        Useful for retrieving exception history for a specific entity (e.g., counterparty,
        patient, account).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            entity: Entity identifier (e.g., counterparty, patient, account)
            limit: Maximum number of results (default: 50)
            
        Returns:
            List of Exception instances for the entity, ordered by created_at DESC
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(Exception)
        query = self._tenant_filter(query, tenant_id, Exception.tenant_id)
        query = query.where(Exception.entity == entity)
        
        # Order by created_at DESC (newest first)
        query = query.order_by(Exception.created_at.desc())
        
        # Apply limit
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_exceptions_by_source_system(
        self,
        tenant_id: str,
        source_system: str,
        limit: int = 50,
    ) -> list[Exception]:
        """
        Get exceptions by source system for Co-Pilot contextual retrieval.
        
        This method primarily serves Co-Pilot retrieval needs and must respect tenant isolation.
        Useful for retrieving exceptions from a specific source system (e.g., Murex, ClaimsApp).
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            source_system: Source system name (e.g., Murex, ClaimsApp)
            limit: Maximum number of results (default: 50)
            
        Returns:
            List of Exception instances from the source system, ordered by created_at DESC
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(Exception)
        query = self._tenant_filter(query, tenant_id, Exception.tenant_id)
        query = query.where(Exception.source_system == source_system)
        
        # Order by created_at DESC (newest first)
        query = query.order_by(Exception.created_at.desc())
        
        # Apply limit
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_imminent_sla_breaches(
        self,
        tenant_id: str,
        within_minutes: int = 60,
        limit: int = 100,
    ) -> list[Exception]:
        """
        Get exceptions with imminent SLA breaches for Co-Pilot contextual retrieval.
        
        This method primarily serves Co-Pilot retrieval needs and must respect tenant isolation.
        Returns exceptions that are at risk of SLA breach within the specified time window.
        Only includes exceptions with status 'open' or 'analyzing' that have an SLA deadline.
        
        Args:
            tenant_id: Tenant identifier (required for isolation)
            within_minutes: Time window in minutes (default: 60)
            limit: Maximum number of results (default: 100)
            
        Returns:
            List of Exception instances with imminent SLA breaches, ordered by sla_deadline ASC
            (most urgent first)
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id:
            raise ValueError("tenant_id is required for tenant isolation")
        
        now = datetime.now(timezone.utc)
        deadline_threshold = now + timedelta(minutes=within_minutes)
        
        query = select(Exception)
        query = self._tenant_filter(query, tenant_id, Exception.tenant_id)
        
        # Filter by status (open or analyzing)
        query = query.where(
            Exception.status.in_([ExceptionStatus.OPEN, ExceptionStatus.ANALYZING])
        )
        
        # Filter by SLA deadline within the time window
        query = query.where(
            and_(
                Exception.sla_deadline.isnot(None),
                Exception.sla_deadline >= now,
                Exception.sla_deadline <= deadline_threshold,
            )
        )
        
        # Order by sla_deadline ASC (most urgent first)
        query = query.order_by(Exception.sla_deadline.asc())
        
        # Apply limit
        query = query.limit(limit)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

