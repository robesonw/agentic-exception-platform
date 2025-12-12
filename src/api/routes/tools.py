"""
Tool definition and invocation API routes.

Phase 6 P6-25: Tool definition CRUD endpoints for Phase 8 preparation.
Supports both tenant-scoped and global tools.
"""

import logging
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.repository.dto import ToolDefinitionCreateDTO, ToolDefinitionFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolDefinitionResponse(BaseModel):
    """Response model for a single tool definition."""

    toolId: int = Field(..., description="Tool identifier")
    tenantId: Optional[str] = Field(None, description="Tenant identifier (null for global tools)")
    name: str = Field(..., description="Tool name")
    type: str = Field(..., description="Tool type (e.g., 'webhook', 'rest', 'email', 'workflow')")
    config: dict[str, Any] = Field(..., description="Tool configuration (endpoint, auth, schema)")
    createdAt: str = Field(..., description="Timestamp when tool was created (ISO format)")

    class Config:
        populate_by_name = True


class ToolDefinitionListResponse(BaseModel):
    """Response model for listing tool definitions."""

    items: list[ToolDefinitionResponse] = Field(..., description="List of tool definition records")
    total: int = Field(..., description="Total number of tools matching filters")


class ToolDefinitionCreateRequest(BaseModel):
    """Request model for creating a tool definition."""

    name: str = Field(..., min_length=1, description="Tool name")
    type: str = Field(..., min_length=1, description="Tool type (e.g., 'webhook', 'rest', 'email', 'workflow')")
    config: dict[str, Any] = Field(..., description="Tool configuration (endpoint, auth, schema) as JSON")


@router.get("", response_model=ToolDefinitionListResponse)
async def list_tools(
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (optional, for tenant-scoped tools)"),
    scope: Literal["tenant", "global", "all"] = Query("tenant", description="Scope filter: tenant, global, or all"),
    name: Optional[str] = Query(None, description="Filter by tool name (partial match)"),
    type: Optional[str] = Query(None, description="Filter by tool type"),
    request: Request = None,
) -> ToolDefinitionListResponse:
    """
    List tool definitions with optional filtering.
    
    GET /api/tools
    
    Query Parameters:
    - tenant_id: Optional tenant identifier
    - scope: Filter by scope - "tenant" (tenant-scoped only), "global" (global only), "all" (both)
    - name: Optional tool name filter (partial match, case-insensitive)
    - type: Optional tool type filter (exact match)
    
    Returns:
    - List of tool definitions based on scope and filters
    
    Raises:
    - HTTPException 400 if scope is "tenant" but tenant_id is missing
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if tenant_id and authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"query={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match query tenant '{tenant_id}'",
            )
        # Use authenticated tenant ID if tenant_id was provided
        if tenant_id:
            tenant_id = authenticated_tenant_id
    
    # Validate scope requirements
    if scope == "tenant" and not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="tenant_id is required when scope='tenant'",
        )
    
    logger.info(f"Listing tools: tenant_id={tenant_id}, scope={scope}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            repo = ToolDefinitionRepository(session)
            
            # Build filter from query parameters
            filters = ToolDefinitionFilter()
            if name:
                filters.name = name
            if type:
                filters.type = type
            
            # Determine which tools to list based on scope
            if scope == "global":
                # Only global tools (tenant_id=None)
                tools = await repo.list_tools(tenant_id=None, filters=filters if any([name, type]) else None)
            elif scope == "tenant":
                # Only tenant-scoped tools for the tenant
                all_tools = await repo.list_tools(tenant_id=tenant_id, filters=filters if any([name, type]) else None)
                # Filter to only tenant-scoped tools (exclude global)
                tools = [t for t in all_tools if t.tenant_id == tenant_id]
            else:  # scope == "all"
                # All tools (global + tenant-scoped for tenant)
                tools = await repo.list_tools(tenant_id=tenant_id, filters=filters if any([name, type]) else None)
            
            # Convert to response format
            items = [
                ToolDefinitionResponse(
                    toolId=tool.tool_id,
                    tenantId=tool.tenant_id,
                    name=tool.name,
                    type=tool.type,
                    config=tool.config if isinstance(tool.config, dict) else {},
                    createdAt=tool.created_at.isoformat() if tool.created_at else "",
                )
                for tool in tools
            ]
            
            logger.info(f"Listed {len(items)} tools: tenant_id={tenant_id}, scope={scope}")
            
            return ToolDefinitionListResponse(items=items, total=len(items))
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing tools from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to list tools: {str(e)}",
        )


@router.get("/{tool_id}", response_model=ToolDefinitionResponse)
async def get_tool(
    tool_id: int = Path(..., ge=1, description="Tool identifier"),
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (optional, required for tenant-scoped tools)"),
    request: Request = None,
) -> ToolDefinitionResponse:
    """
    Get a single tool definition by ID.
    
    GET /api/tools/{tool_id}
    
    Query Parameters:
    - tenant_id: Optional tenant identifier. Required if tool is tenant-scoped.
    
    Returns:
    - Tool definition record
    
    Raises:
    - HTTPException 400 if tool is tenant-scoped but tenant_id is missing
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if tool not found or access denied
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if tenant_id and authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"query={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match query tenant '{tenant_id}'",
            )
        # Use authenticated tenant ID if tenant_id was provided
        if tenant_id:
            tenant_id = authenticated_tenant_id
    
    logger.info(f"Retrieving tool {tool_id}, tenant_id={tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            repo = ToolDefinitionRepository(session)
            
            # Get tool (handles global vs tenant-scoped logic)
            tool = await repo.get_tool(tool_id=tool_id, tenant_id=tenant_id)
            
            if tool is None:
                logger.warning(
                    f"Tool {tool_id} not found or access denied (tenant_id={tenant_id})"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool {tool_id} not found or access denied",
                )
            
            # If tool is tenant-scoped, verify tenant_id was provided
            if tool.tenant_id is not None and tenant_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"tenant_id is required for tenant-scoped tool {tool_id}",
                )
            
            # Convert to response format
            response = ToolDefinitionResponse(
                toolId=tool.tool_id,
                tenantId=tool.tenant_id,
                name=tool.name,
                type=tool.type,
                config=tool.config if isinstance(tool.config, dict) else {},
                createdAt=tool.created_at.isoformat() if tool.created_at else "",
            )
            
            logger.info(f"Retrieved tool {tool_id} (tenant_id={tenant_id}, scope={'tenant' if tool.tenant_id else 'global'})")
            
            return response
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving tool from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to retrieve tool: {str(e)}",
        )


@router.post("", response_model=ToolDefinitionResponse, status_code=201)
async def create_tool(
    tool_data: ToolDefinitionCreateRequest,
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (optional, omit for global tools)"),
    request: Request = None,
) -> ToolDefinitionResponse:
    """
    Create a new tool definition.
    
    POST /api/tools
    
    Request Body:
    - name: Tool name (required)
    - type: Tool type (required, e.g., 'webhook', 'rest', 'email', 'workflow')
    - config: Tool configuration (required, JSON with endpoint, auth, schema)
    
    Query Parameters:
    - tenant_id: Optional tenant identifier. If provided, creates tenant-scoped tool.
                 If omitted, creates global tool.
    
    Returns:
    - Created tool definition record
    
    Raises:
    - HTTPException 400 if request body is invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if tenant_id and authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"query={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match query tenant '{tenant_id}'",
            )
        # Use authenticated tenant ID if tenant_id was provided
        if tenant_id:
            tenant_id = authenticated_tenant_id
    
    scope = "tenant-scoped" if tenant_id else "global"
    logger.info(f"Creating {scope} tool for tenant_id={tenant_id}: {tool_data.name}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            repo = ToolDefinitionRepository(session)
            
            # Create tool DTO
            create_dto = ToolDefinitionCreateDTO(
                name=tool_data.name,
                type=tool_data.type,
                config=tool_data.config,
            )
            
            # Create tool (tenant_id=None for global, tenant_id=string for tenant-scoped)
            tool = await repo.create_tool(tenant_id=tenant_id, tool_data=create_dto)
            
            # Convert to response format
            response = ToolDefinitionResponse(
                toolId=tool.tool_id,
                tenantId=tool.tenant_id,
                name=tool.name,
                type=tool.type,
                config=tool.config if isinstance(tool.config, dict) else {},
                createdAt=tool.created_at.isoformat() if tool.created_at else "",
            )
            
            logger.info(f"Created {scope} tool {tool.tool_id} (tenant_id={tenant_id})")
            
            return response
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating tool in database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to create tool: {str(e)}",
        )


# Keep the original tool invocation endpoint for backward compatibility
@router.post("/{tenant_id}/{tool_name}")
async def invoke_tool(tenant_id: str, tool_name: str):
    """
    Invoke a registered tool.
    POST /api/tools/{tenantId}/{toolName}
    
    Note: This endpoint is kept for backward compatibility.
    Tool invocation logic will be implemented in Phase 8.
    """
    # TODO: Implement tool invocation
    pass

