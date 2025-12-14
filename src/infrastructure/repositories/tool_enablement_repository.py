"""
Tool enablement repository for Phase 8.

Provides CRUD operations for tool enablement records with tenant isolation.
Reference: docs/phase8-tools-mvp.md Section 4.1 (Tool enable/disable per tenant)
"""

import logging
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import ToolEnablement
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


class ToolEnablementRepository(AbstractBaseRepository[ToolEnablement]):
    """
    Repository for tool enablement management.
    
    Provides:
    - Get enablement status for a tenant and tool
    - Set enablement status (create or update)
    - List enabled/disabled tools for a tenant
    - Delete enablement record (reverts to default: enabled)
    
    All operations enforce tenant isolation.
    """
    
    async def get_by_id(self, entity_id: str, tenant_id: str) -> Optional[ToolEnablement]:
        """
        Get enablement by composite key (not applicable for this model).
        
        This method is required by AbstractBaseRepository but doesn't apply
        to ToolEnablement which has a composite primary key.
        Use get_enablement() instead.
        """
        # ToolEnablement uses composite key (tenant_id, tool_id)
        # This method is not applicable
        raise NotImplementedError(
            "ToolEnablement uses composite key. Use get_enablement(tenant_id, tool_id) instead."
        )
    
    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[ToolEnablement]:
        """
        List enablements for a tenant with pagination.
        
        Args:
            tenant_id: Tenant identifier
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (enabled_only)
            
        Returns:
            PaginatedResult with enablements and pagination metadata
        """
        enabled_only = filters.get("enabled_only")
        enablements = await self.list_enablements(tenant_id, enabled_only)
        
        # Calculate pagination
        total = len(enablements)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_items = enablements[start_idx:end_idx]
        total_pages = (total + page_size - 1) // page_size if total > 0 else 1
        
        return PaginatedResult(
            items=paginated_items,
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )

    async def get_enablement(
        self, tenant_id: str, tool_id: int
    ) -> Optional[ToolEnablement]:
        """
        Get enablement status for a tenant and tool.
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            
        Returns:
            ToolEnablement instance or None if not found (defaults to enabled)
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = (
            select(ToolEnablement)
            .where(ToolEnablement.tenant_id == tenant_id)
            .where(ToolEnablement.tool_id == tool_id)
        )
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def is_enabled(self, tenant_id: str, tool_id: int) -> bool:
        """
        Check if tool is enabled for tenant.
        
        Default behavior: If no enablement record exists, tool is enabled by default.
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            
        Returns:
            True if enabled, False if disabled
        """
        enablement = await self.get_enablement(tenant_id, tool_id)
        if enablement is None:
            # Default: enabled if no record exists
            return True
        return enablement.enabled

    async def set_enablement(
        self, tenant_id: str, tool_id: int, enabled: bool
    ) -> ToolEnablement:
        """
        Set enablement status for a tenant and tool.
        
        Creates a new record if it doesn't exist, or updates existing record.
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            enabled: Whether tool should be enabled
            
        Returns:
            ToolEnablement instance (created or updated)
            
        Raises:
            ValueError: If tenant_id is empty or tool_id is invalid
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        if tool_id < 1:
            raise ValueError(f"Invalid tool_id: {tool_id}")
        
        # Check if record exists
        existing = await self.get_enablement(tenant_id, tool_id)
        
        if existing is None:
            # Create new record
            enablement = ToolEnablement(
                tenant_id=tenant_id,
                tool_id=tool_id,
                enabled=enabled,
            )
            self.session.add(enablement)
        else:
            # Update existing record
            existing.enabled = enabled
        
        await self.session.flush()
        
        # Refresh to get updated timestamps
        if existing is None:
            await self.session.refresh(enablement)
            logger.info(
                f"Created tool enablement: tenant_id={tenant_id}, "
                f"tool_id={tool_id}, enabled={enabled}"
            )
            return enablement
        else:
            # Refresh existing to get updated timestamp
            await self.session.refresh(existing)
            logger.info(
                f"Updated tool enablement: tenant_id={tenant_id}, "
                f"tool_id={tool_id}, enabled={enabled}"
            )
            return existing

    async def delete_enablement(self, tenant_id: str, tool_id: int) -> bool:
        """
        Delete enablement record, reverting to default (enabled).
        
        Args:
            tenant_id: Tenant identifier
            tool_id: Tool identifier
            
        Returns:
            True if record was deleted, False if it didn't exist
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        enablement = await self.get_enablement(tenant_id, tool_id)
        if enablement is None:
            return False
        
        await self.session.delete(enablement)
        await self.session.flush()
        
        logger.info(
            f"Deleted tool enablement: tenant_id={tenant_id}, tool_id={tool_id}"
        )
        return True

    async def list_enablements(
        self, tenant_id: str, enabled_only: Optional[bool] = None
    ) -> list[ToolEnablement]:
        """
        List enablement records for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            enabled_only: Optional filter:
                - None: Return all enablement records
                - True: Return only enabled tools
                - False: Return only disabled tools
                
        Returns:
            List of ToolEnablement instances
            
        Raises:
            ValueError: If tenant_id is empty
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")
        
        query = select(ToolEnablement).where(ToolEnablement.tenant_id == tenant_id)
        
        if enabled_only is not None:
            query = query.where(ToolEnablement.enabled == enabled_only)
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

