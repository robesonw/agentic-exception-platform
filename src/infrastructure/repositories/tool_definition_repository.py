"""
Tool definition repository for tool management.

Phase 6 P6-15: ToolDefinitionRepository with support for global and tenant-scoped tools.

Note: Tools can be either:
- Global (tenant_id=None): Available to all tenants
- Tenant-scoped (tenant_id set): Available only to the specific tenant
"""

import logging
from typing import Optional

from sqlalchemy import and_, desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import ToolDefinition
from src.repository.base import AbstractBaseRepository
from src.repository.dto import ToolDefinitionCreateDTO, ToolDefinitionFilter

logger = logging.getLogger(__name__)


class ToolDefinitionRepository(AbstractBaseRepository[ToolDefinition]):
    """
    Repository for tool definition management.
    
    Provides:
    - Get tool by ID (supports global and tenant-scoped)
    - List tools with filtering (supports global and tenant-scoped)
    - Create tool (supports global and tenant-scoped)
    
    Tools can be:
    - Global (tenant_id=None): Available to all tenants
    - Tenant-scoped (tenant_id set): Available only to the specific tenant
    """

    async def get_tool(
        self,
        tool_id: int,
        tenant_id: Optional[str] = None,
    ) -> Optional[ToolDefinition]:
        """
        Get a tool by ID.
        
        For tenant-scoped tools, the tool must belong to the tenant.
        For global tools (tenant_id=None in DB), any tenant can access them.
        
        Args:
            tool_id: Tool identifier (primary key)
            tenant_id: Optional tenant identifier. If None, only global tools are returned.
                      If provided, returns global tools OR tenant-scoped tools for that tenant.
            
        Returns:
            ToolDefinition instance or None if not found or access denied
            
        Raises:
            ValueError: If tool_id < 1
        """
        if tool_id < 1:
            raise ValueError("tool_id must be >= 1")
        
        query = select(ToolDefinition).where(ToolDefinition.tool_id == tool_id)
        
        # Apply tenant filtering
        if tenant_id is not None:
            # Return tool if it's global (tenant_id is None) OR belongs to the tenant
            query = query.where(
                or_(
                    ToolDefinition.tenant_id.is_(None),  # Global tool
                    ToolDefinition.tenant_id == tenant_id,  # Tenant-scoped tool
                )
            )
        else:
            # If tenant_id is None, only return global tools
            query = query.where(ToolDefinition.tenant_id.is_(None))
        
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_tools(
        self,
        tenant_id: Optional[str] = None,
        filters: Optional[ToolDefinitionFilter] = None,
    ) -> list[ToolDefinition]:
        """
        List tools with optional filtering.
        
        Returns:
        - If tenant_id is None: Only global tools
        - If tenant_id is provided: Global tools + tenant-scoped tools for that tenant
        
        Results are ordered by created_at (descending, newest first).
        
        Args:
            tenant_id: Optional tenant identifier. If None, only global tools are returned.
                      If provided, returns global tools OR tenant-scoped tools for that tenant.
            filters: Optional ToolDefinitionFilter for filtering tools
            
        Returns:
            List of ToolDefinition instances
        """
        query = select(ToolDefinition)
        
        # Apply tenant filtering
        if tenant_id is not None:
            # Return tools that are global (tenant_id is None) OR belong to the tenant
            query = query.where(
                or_(
                    ToolDefinition.tenant_id.is_(None),  # Global tools
                    ToolDefinition.tenant_id == tenant_id,  # Tenant-scoped tools
                )
            )
        else:
            # If tenant_id is None, only return global tools
            query = query.where(ToolDefinition.tenant_id.is_(None))
        
        # Apply filters if provided
        if filters:
            conditions = []
            
            # Filter by name (partial match, case-insensitive)
            if filters.name:
                conditions.append(ToolDefinition.name.ilike(f"%{filters.name}%"))
            
            # Filter by type (exact match)
            if filters.type:
                conditions.append(ToolDefinition.type == filters.type)
            
            # Apply all conditions
            if conditions:
                query = query.where(and_(*conditions))
        
        # Order by created_at descending (newest first)
        query = query.order_by(desc(ToolDefinition.created_at))
        
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def create_tool(
        self,
        tenant_id: Optional[str],
        tool_data: ToolDefinitionCreateDTO,
    ) -> ToolDefinition:
        """
        Create a new tool definition.
        
        Args:
            tenant_id: Optional tenant identifier. If None, creates a global tool.
                      If provided, creates a tenant-scoped tool.
            tool_data: ToolDefinitionCreateDTO with tool details
            
        Returns:
            Created ToolDefinition instance
            
        Raises:
            ValueError: If tool_data is invalid
        """
        # Create new tool
        tool = ToolDefinition(
            tenant_id=tenant_id,  # None for global, string for tenant-scoped
            name=tool_data.name,
            type=tool_data.type,
            config=tool_data.config,
        )
        
        self.session.add(tool)
        await self.session.flush()
        await self.session.refresh(tool)
        
        scope = "global" if tenant_id is None else f"tenant={tenant_id}"
        logger.info(
            f"Created tool definition: tool_id={tool.tool_id}, name={tool.name}, "
            f"type={tool.type}, scope={scope}"
        )
        return tool

    # AbstractBaseRepository implementations
    # Note: These methods support both global and tenant-scoped tools

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[ToolDefinition]:
        """
        Get tool by ID with tenant context.
        
        Args:
            id: Tool database ID (as string)
            tenant_id: Tenant identifier (required by interface, but can access global tools)
            
        Returns:
            ToolDefinition instance or None if not found or access denied
        """
        try:
            tool_id = int(id)
        except (ValueError, TypeError):
            return None
        
        # Use get_tool which handles global vs tenant-scoped logic
        return await self.get_tool(tool_id, tenant_id)

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ):
        """
        List tools for a tenant with pagination and filtering.
        
        Returns global tools + tenant-scoped tools for the tenant.
        
        Args:
            tenant_id: Tenant identifier (required)
            page: Page number (1-indexed, default: 1)
            page_size: Number of items per page (default: 50)
            **filters: Additional filter criteria (converted to ToolDefinitionFilter)
            
        Returns:
            PaginatedResult with tools
            
        Raises:
            ValueError: If tenant_id is None or empty
        """
        from src.repository.base import PaginatedResult
        
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")
        
        # Convert filters to ToolDefinitionFilter if provided
        tool_filter = None
        if filters:
            tool_filter = ToolDefinitionFilter(**filters)
        
        # Get all tools (global + tenant-scoped, with optional filters)
        all_tools = await self.list_tools(tenant_id=tenant_id, filters=tool_filter)
        
        # Apply pagination manually
        total = len(all_tools)
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        paginated_tools = all_tools[start_idx:end_idx]
        
        return PaginatedResult(
            items=paginated_tools,
            total=total,
            page=page,
            page_size=page_size,
        )


