"""
Tool execution repository for Phase 8.

Provides CRUD operations for tool execution records with tenant isolation.
Reference: docs/phase8-tools-mvp.md Section 3.1
"""

import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import and_, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import ToolExecution
from src.repository.base import AbstractBaseRepository, PaginatedResult
from src.repository.dto import (
    ToolExecutionCreateDTO,
    ToolExecutionFilter,
    ToolExecutionUpdateDTO,
)

logger = logging.getLogger(__name__)


class ToolExecutionRepository(AbstractBaseRepository[ToolExecution]):
    """
    Repository for tool execution management.
    
    Provides:
    - Create execution record
    - Get execution by ID (with tenant isolation)
    - List executions with filtering (with tenant isolation)
    - Update execution status and results
    
    All operations enforce tenant isolation.
    """

    async def create_execution(
        self, execution_data: ToolExecutionCreateDTO
    ) -> ToolExecution:
        """
        Create a new tool execution record.
        
        Args:
            execution_data: ToolExecutionCreateDTO with execution details
            
        Returns:
            Created ToolExecution instance
            
        Raises:
            ValueError: If execution_data is invalid
        """
        # Create new execution
        execution = ToolExecution(
            tenant_id=execution_data.tenant_id,
            tool_id=execution_data.tool_id,
            exception_id=execution_data.exception_id,
            status=execution_data.status,
            requested_by_actor_type=execution_data.requested_by_actor_type,
            requested_by_actor_id=execution_data.requested_by_actor_id,
            input_payload=execution_data.input_payload,
            output_payload=execution_data.output_payload,
            error_message=execution_data.error_message,
        )
        
        self.session.add(execution)
        await self.session.flush()
        await self.session.refresh(execution)
        
        logger.info(
            f"Created tool execution: id={execution.id}, tenant_id={execution.tenant_id}, "
            f"tool_id={execution.tool_id}, status={execution.status.value}"
        )
        return execution

    async def get_execution(
        self, execution_id: UUID, tenant_id: str
    ) -> Optional[ToolExecution]:
        """
        Get a tool execution by ID with tenant isolation.
        
        Args:
            execution_id: Execution identifier (UUID)
            tenant_id: Tenant identifier (required for isolation)
            
        Returns:
            ToolExecution instance or None if not found or access denied
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(ToolExecution)
            .where(ToolExecution.id == execution_id)
            .where(ToolExecution.tenant_id == tenant_id)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_executions(
        self,
        tenant_id: str,
        filters: Optional[ToolExecutionFilter] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> PaginatedResult[ToolExecution]:
        """
        List tool executions for a tenant with filtering and pagination.
        
        Args:
            tenant_id: Tenant identifier (required)
            filters: Optional ToolExecutionFilter for filtering executions
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            
        Returns:
            PaginatedResult with executions and pagination metadata
            
        Raises:
            ValueError: If tenant_id is empty or pagination parameters invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        if page < 1:
            raise ValueError("page must be >= 1")
        if page_size < 1:
            raise ValueError("page_size must be >= 1")
        
        # Start with base query - always filter by tenant
        query = select(ToolExecution).where(ToolExecution.tenant_id == tenant_id)
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            if filters.tool_id is not None:
                conditions.append(ToolExecution.tool_id == filters.tool_id)
            
            if filters.exception_id is not None:
                conditions.append(ToolExecution.exception_id == filters.exception_id)
            
            if filters.status is not None:
                conditions.append(ToolExecution.status == filters.status)
            
            if filters.actor_type is not None:
                conditions.append(ToolExecution.requested_by_actor_type == filters.actor_type)
            
            if filters.actor_id is not None:
                conditions.append(ToolExecution.requested_by_actor_id == filters.actor_id)
            
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by created_at descending (newest first)
        query = query.order_by(desc(ToolExecution.created_at))
        
        # Execute paginated query
        return await self._execute_paginated(query, page=page, page_size=page_size)

    async def update_execution(
        self,
        execution_id: UUID,
        tenant_id: str,
        update_data: ToolExecutionUpdateDTO,
    ) -> Optional[ToolExecution]:
        """
        Update a tool execution record.
        
        Args:
            execution_id: Execution identifier (UUID)
            tenant_id: Tenant identifier (required for isolation)
            update_data: ToolExecutionUpdateDTO with fields to update
            
        Returns:
            Updated ToolExecution instance or None if not found or access denied
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        # Get execution with tenant isolation
        execution = await self.get_execution(execution_id, tenant_id)
        if execution is None:
            logger.warning(
                f"Tool execution {execution_id} not found or access denied for tenant {tenant_id}"
            )
            return None
        
        # Update fields if provided
        if update_data.status is not None:
            execution.status = update_data.status
        
        if update_data.output_payload is not None:
            execution.output_payload = update_data.output_payload
        
        if update_data.error_message is not None:
            execution.error_message = update_data.error_message
        
        await self.session.flush()
        await self.session.refresh(execution)
        
        logger.info(
            f"Updated tool execution: id={execution.id}, tenant_id={tenant_id}, "
            f"status={execution.status.value}"
        )
        return execution

    # AbstractBaseRepository implementations

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[ToolExecution]:
        """
        Get tool execution by ID with tenant context.
        
        Args:
            id: Execution database ID (UUID as string)
            tenant_id: Tenant identifier (required by interface)
            
        Returns:
            ToolExecution instance or None if not found or access denied
        """
        try:
            execution_id = UUID(id)
        except (ValueError, TypeError):
            return None
        
        return await self.get_execution(execution_id, tenant_id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[ToolExecution]:
        """
        List tool executions for a tenant with pagination and filtering.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (converted to ToolExecutionFilter)
            
        Returns:
            PaginatedResult with executions
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        # Convert filters to ToolExecutionFilter if provided
        tool_filter = None
        if filters:
            tool_filter = ToolExecutionFilter(**filters)
        
        return await self.list_executions(
            tenant_id=tenant_id, filters=tool_filter, page=page, page_size=page_size
        )


