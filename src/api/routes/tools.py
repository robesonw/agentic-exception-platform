"""
Tool definition and invocation API routes.

Phase 6 P6-25: Tool definition CRUD endpoints for Phase 8 preparation.
Phase 8 P8-1: Enhanced schema validation with required fields.
Phase 9 P9-18: POST /api/tools/{tool_id}/execute transformed to async command pattern.

Supports both tenant-scoped and global tools.
Maintains backward compatibility with existing tool definitions.
"""

import logging
from typing import Any, Literal, Optional, Union

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field, ValidationError
from uuid import uuid4

from src.events.types import ToolExecutionRequested
from src.infrastructure.db.models import ActorType, ToolExecutionStatus
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
from src.infrastructure.repositories.tool_execution_repository import ToolExecutionRepository
from src.messaging.event_publisher import EventPublisherService
from src.models.tool_definition_phase8 import (
    ToolDefinitionRequest,
    ToolDefinitionConfig,
    EndpointConfig,
    AuthType,
    TenantScope,
)
from src.repository.dto import ToolDefinitionCreateDTO, ToolDefinitionFilter, ToolExecutionCreateDTO, ToolExecutionFilter
from src.repository.exception_events_repository import ExceptionEventRepository
from src.tools.execution_service import ToolExecutionService, ToolExecutionServiceError
from src.tools.provider import DummyToolProvider, HttpToolProvider
from src.tools.validation import ToolValidationService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolDefinitionResponse(BaseModel):
    """Response model for a single tool definition."""

    toolId: int = Field(..., description="Tool identifier")
    tenantId: Optional[str] = Field(None, description="Tenant identifier (null for global tools)")
    name: str = Field(..., description="Tool name")
    type: str = Field(..., description="Tool type (e.g., 'webhook', 'rest', 'email', 'workflow')")
    config: dict[str, Any] = Field(..., description="Tool configuration (endpoint, auth, schema)")
    enabled: Optional[bool] = Field(None, description="Whether tool is enabled (if authenticated, null otherwise)")
    createdAt: str = Field(..., description="Timestamp when tool was created (ISO format)")

    class Config:
        populate_by_name = True


class ToolDefinitionListResponse(BaseModel):
    """Response model for listing tool definitions."""

    items: list[ToolDefinitionResponse] = Field(..., description="List of tool definition records")
    total: int = Field(..., description="Total number of tools matching filters")


class ToolDefinitionCreateRequest(BaseModel):
    """
    Request model for creating a tool definition.
    
    Phase 8: Supports both legacy format (name, type, config) and enhanced format
    (all fields flattened). The enhanced format is validated against Phase 8 schema.
    """

    # Legacy format fields (for backward compatibility)
    name: Optional[str] = Field(None, min_length=1, description="Tool name (legacy format)")
    type: Optional[str] = Field(None, min_length=1, description="Tool type (legacy format)")
    config: Optional[dict[str, Any]] = Field(None, description="Tool configuration (legacy format)")
    
    # Phase 8 enhanced format fields
    # If these are provided, they take precedence and config is ignored
    description: Optional[str] = Field(None, min_length=1, description="Tool description (Phase 8)")
    inputSchema: Optional[dict[str, Any]] = Field(None, alias="input_schema", description="Input JSON Schema (Phase 8)")
    outputSchema: Optional[dict[str, Any]] = Field(None, alias="output_schema", description="Output JSON Schema (Phase 8)")
    authType: Optional[str] = Field(None, alias="auth_type", description="Auth type: none|api_key|oauth_stub (Phase 8)")
    endpointConfig: Optional[dict[str, Any]] = Field(None, alias="endpoint_config", description="Endpoint config (Phase 8)")
    tenantScope: Optional[str] = Field(None, alias="tenant_scope", description="Tenant scope: global|tenant (Phase 8)")

    def validate_phase8_schema(self) -> ToolDefinitionRequest:
        """
        Validate and convert to Phase 8 ToolDefinitionRequest.
        
        Returns:
            Validated ToolDefinitionRequest
            
        Raises:
            ValueError: If validation fails
        """
        # Check if using Phase 8 format (has description, inputSchema, etc.)
        if self.description is not None or self.inputSchema is not None:
            # Phase 8 format: all fields should be provided
            if not self.name:
                raise ValueError("name is required")
            if not self.type:
                raise ValueError("type is required")
            if not self.description:
                raise ValueError("description is required")
            if not self.inputSchema:
                raise ValueError("inputSchema is required")
            if not self.outputSchema:
                raise ValueError("outputSchema is required")
            if not self.authType:
                raise ValueError("authType is required")
            
            # Validate auth_type enum
            try:
                auth_type = AuthType(self.authType.lower())
            except ValueError:
                raise ValueError(
                    f"Invalid authType '{self.authType}'. Must be one of: none, api_key, oauth_stub"
                )
            
            # Validate tenant_scope enum
            tenant_scope = TenantScope.TENANT
            if self.tenantScope:
                try:
                    tenant_scope = TenantScope(self.tenantScope.lower())
                except ValueError:
                    raise ValueError(
                        f"Invalid tenantScope '{self.tenantScope}'. Must be one of: global, tenant"
                    )
            
            # Convert endpointConfig dict to EndpointConfig object if provided
            endpoint_config_obj = None
            if self.endpointConfig:
                if isinstance(self.endpointConfig, dict):
                    endpoint_config_obj = EndpointConfig(**self.endpointConfig)
                else:
                    endpoint_config_obj = self.endpointConfig
            
            # Create Phase 8 request model (this will validate endpoint_config for http tools)
            return ToolDefinitionRequest(
                name=self.name,
                type=self.type,
                description=self.description,
                input_schema=self.inputSchema,
                output_schema=self.outputSchema,
                auth_type=auth_type,
                endpoint_config=endpoint_config_obj,
                tenant_scope=tenant_scope,
            )
        else:
            # Legacy format: validate that name, type, config are provided
            if not self.name:
                raise ValueError("name is required")
            if not self.type:
                raise ValueError("type is required")
            if not self.config:
                raise ValueError("config is required")
            
            # For backward compatibility, we allow legacy format without Phase 8 validation
            # But we can optionally validate the config structure if it looks like Phase 8 format
            if isinstance(self.config, dict):
                # Check if config has Phase 8 structure
                has_phase8_fields = any(
                    key in self.config
                    for key in ["description", "inputSchema", "input_schema", "outputSchema", "output_schema"]
                )
                if has_phase8_fields:
                    # Try to validate as Phase 8 config
                    try:
                        ToolDefinitionConfig.validate_for_tool_type(self.type, self.config)
                    except Exception as e:
                        logger.warning(
                            f"Config has Phase 8 fields but validation failed: {e}. "
                            "Allowing legacy format for backward compatibility."
                        )
            
            # Return a minimal ToolDefinitionRequest for legacy format
            # We'll store the config as-is in the database
            return None  # Signal to use legacy format


@router.get("", response_model=ToolDefinitionListResponse)
async def list_tools(
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (optional, for tenant-scoped tools)"),
    scope: Literal["tenant", "global", "all"] = Query("tenant", description="Scope filter: tenant, global, or all"),
    status: Optional[Literal["enabled", "disabled"]] = Query(None, description="Status filter: enabled or disabled"),
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
    - status: Optional status filter - "enabled" (enabled tools only), "disabled" (disabled tools only)
    - name: Optional tool name filter (partial match, case-insensitive)
    - type: Optional tool type filter (exact match)
    
    Returns:
    - List of tool definitions based on scope, status, and other filters
    
    Raises:
    - HTTPException 400 if scope is "tenant" but tenant_id is missing
    - HTTPException 401 if authentication required for status filter
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 500 if database error occurs
    """
    # Get authenticated tenant ID (required for status filter)
    authenticated_tenant_id = _get_tenant_id_from_request(request)
    
    # Verify tenant ID matches authenticated tenant if available
    if authenticated_tenant_id:
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
    elif status is not None:
        # Status filter requires authentication
        raise HTTPException(
            status_code=401,
            detail="Authentication required to filter by status",
        )
    
    # Validate scope requirements
    if scope == "tenant" and not tenant_id:
        raise HTTPException(
            status_code=400,
            detail="tenant_id is required when scope='tenant'",
        )
    
    logger.info(f"Listing tools: tenant_id={tenant_id}, scope={scope}, status={status}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
        
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
                # If tenant_id is None, only return global tools
                tools = await repo.list_tools(tenant_id=tenant_id, filters=filters if any([name, type]) else None)
            
            # Apply status filter if provided
            if status is not None and authenticated_tenant_id:
                enablement_repo = ToolEnablementRepository(session)
                filtered_tools = []
                for tool in tools:
                    # Check enablement status
                    is_enabled = await enablement_repo.is_enabled(authenticated_tenant_id, tool.tool_id)
                    if status == "enabled" and is_enabled:
                        filtered_tools.append(tool)
                    elif status == "disabled" and not is_enabled:
                        filtered_tools.append(tool)
                tools = filtered_tools
            
            # Get enablement status for each tool if authenticated
            enablement_repo = None
            if authenticated_tenant_id:
                enablement_repo = ToolEnablementRepository(session)
            
            # Convert to response format
            items = []
            for tool in tools:
                enabled = None
                if authenticated_tenant_id and enablement_repo:
                    enabled = await enablement_repo.is_enabled(authenticated_tenant_id, tool.tool_id)
                
                items.append(
                    ToolDefinitionResponse(
                        toolId=tool.tool_id,
                        tenantId=tool.tenant_id,
                        name=tool.name,
                        type=tool.type,
                        config=tool.config if isinstance(tool.config, dict) else {},
                        enabled=enabled,
                        createdAt=tool.created_at.isoformat() if tool.created_at else "",
                    )
                )
            
            logger.info(f"Listed {len(items)} tools: tenant_id={tenant_id}, scope={scope}, status={status}")
            
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


# ============================================================================
# Phase 8: Tool Execution API Models (must be defined before routes)
# ============================================================================

class ToolExecutionResponse(BaseModel):
    """Response model for a tool execution."""

    executionId: str = Field(..., alias="execution_id", description="Execution identifier (UUID)")
    tenantId: str = Field(..., alias="tenant_id", description="Tenant identifier")
    toolId: int = Field(..., alias="tool_id", description="Tool definition identifier")
    exceptionId: Optional[str] = Field(None, alias="exception_id", description="Exception identifier (if linked)")
    status: str = Field(..., description="Execution status: requested, running, succeeded, failed")
    requestedByActorType: str = Field(..., alias="requested_by_actor_type", description="Actor type who requested execution")
    requestedByActorId: str = Field(..., alias="requested_by_actor_id", description="Actor identifier who requested execution")
    inputPayload: dict[str, Any] = Field(..., alias="input_payload", description="Input payload provided to tool")
    outputPayload: Optional[dict[str, Any]] = Field(None, alias="output_payload", description="Output payload from tool (if succeeded)")
    errorMessage: Optional[str] = Field(None, alias="error_message", description="Error message (if failed)")
    createdAt: str = Field(..., alias="created_at", description="Timestamp when execution was created (ISO format)")
    updatedAt: str = Field(..., alias="updated_at", description="Timestamp when execution was last updated (ISO format)")

    class Config:
        populate_by_name = True


class ToolExecutionListResponse(BaseModel):
    """Response model for listing tool executions."""

    items: list[ToolExecutionResponse] = Field(..., description="List of execution records")
    total: int = Field(..., description="Total number of executions matching filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    pageSize: int = Field(..., alias="page_size", description="Number of items per page")
    totalPages: int = Field(..., alias="total_pages", description="Total number of pages")

    class Config:
        populate_by_name = True


# ============================================================================
# Phase 8: Tool Execution API Routes
# ============================================================================

# IMPORTANT: More specific routes (like /executions) must come BEFORE less specific ones (like /{tool_id})
# FastAPI matches routes in order, so /executions must come before /{tool_id}

@router.get("/executions", response_model=ToolExecutionListResponse)
async def list_executions(
    request: Request,
    tool_id: Optional[int] = Query(None, ge=1, description="Filter by tool ID"),
    exception_id: Optional[str] = Query(None, description="Filter by exception ID"),
    status: Optional[str] = Query(None, description="Filter by status: requested, running, succeeded, failed"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type: user, agent, system"),
    actor_id: Optional[str] = Query(None, description="Filter by actor ID"),
    tenant_id: Optional[str] = Query(None, description="Tenant identifier (required for isolation)"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
) -> ToolExecutionListResponse:
    """
    List tool executions with filtering and pagination.
    
    GET /api/tools/executions
    
    Query Parameters:
    - tool_id: Optional filter by tool ID
    - exception_id: Optional filter by exception ID
    - status: Optional filter by status (requested, running, succeeded, failed)
    - actor_type: Optional filter by actor type (user, agent, system)
    - actor_id: Optional filter by actor ID
    - tenant_id: Tenant identifier (required for isolation, can come from query or auth)
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 100)
    
    Returns:
    - Paginated list of tool execution records
    
    Raises:
    - HTTPException 401 if authentication required
    - HTTPException 400 if invalid filter parameters
    """
    # Get tenant ID from query parameter or authentication
    # If tenant_id is provided in query, use it (for UI compatibility)
    # Otherwise, try to get from authentication
    if tenant_id:
        # Use tenant_id from query parameter
        # Verify it matches authenticated tenant if available (for security)
        if request and hasattr(request.state, "tenant_id"):
            authenticated_tenant_id = request.state.tenant_id
            if authenticated_tenant_id != tenant_id:
                logger.warning(
                    f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                    f"query={tenant_id} for {request.url.path}"
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                    f"does not match query tenant '{tenant_id}'",
                )
    else:
        # Try to get from authentication
        tenant_id = _get_tenant_id_from_request(request)
        if not tenant_id:
            raise HTTPException(
                status_code=400,
                detail="tenant_id is required (provide as query parameter or via authentication)",
            )
    
    logger.info(f"Listing tool executions for tenant {tenant_id} (page={page}, page_size={page_size})")
    
    # Build filter
    filters = ToolExecutionFilter()
    if tool_id is not None:
        filters.tool_id = tool_id
    if exception_id is not None:
        filters.exception_id = exception_id
    if status is not None:
        try:
            filters.status = ToolExecutionStatus(status.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status: {status}. Must be one of: requested, running, succeeded, failed",
            )
    if actor_type is not None:
        try:
            filters.actor_type = ActorType(actor_type.lower())
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid actor_type: {actor_type}. Must be one of: user, agent, system",
            )
    if actor_id is not None:
        filters.actor_id = actor_id
    
    try:
        async with get_db_session_context() as session:
            repo = ToolExecutionRepository(session)
            
            # List executions with tenant isolation
            result = await repo.list_executions(
                tenant_id=tenant_id,
                filters=filters if any([tool_id, exception_id, status, actor_type, actor_id]) else None,
                page=page,
                page_size=page_size,
            )
            
            # Convert to response
            items = [
                ToolExecutionResponse(
                    executionId=str(execution.id),
                    tenantId=execution.tenant_id,
                    toolId=execution.tool_id,
                    exceptionId=execution.exception_id,
                    status=execution.status.value,
                    requestedByActorType=execution.requested_by_actor_type.value,
                    requestedByActorId=execution.requested_by_actor_id,
                    inputPayload=execution.input_payload,
                    outputPayload=execution.output_payload,
                    errorMessage=execution.error_message,
                    createdAt=execution.created_at.isoformat() if execution.created_at else "",
                    updatedAt=execution.updated_at.isoformat() if execution.updated_at else "",
                )
                for execution in result.items
            ]
            
            logger.info(f"Listed {len(items)} executions for tenant {tenant_id}")
            
            return ToolExecutionListResponse(
                items=items,
                total=result.total,
                page=result.page,
                pageSize=result.page_size,
                totalPages=result.total_pages,
            )
    
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    
    except HTTPException as e:
        logger.error(f"HTTPException in list_executions: {e.status_code} - {e.detail}", exc_info=True)
        raise
    
    except Exception as e:
        logger.error(f"Error listing executions: {e}", exc_info=True)
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to list executions: {str(e)}",
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
            
            # Get enablement status if authenticated
            enabled = None
            authenticated_tenant_id = _get_tenant_id_from_request(request)
            if authenticated_tenant_id:
                from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
                enablement_repo = ToolEnablementRepository(session)
                enabled = await enablement_repo.is_enabled(authenticated_tenant_id, tool.tool_id)
            
            # Convert to response format
            response = ToolDefinitionResponse(
                toolId=tool.tool_id,
                tenantId=tool.tenant_id,
                name=tool.name,
                type=tool.type,
                config=tool.config if isinstance(tool.config, dict) else {},
                enabled=enabled,
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
    
    Phase 8: Enhanced schema validation with required fields.
    
    Request Body (Phase 8 format):
    - name: Tool name (required)
    - type: Tool type (required, e.g., 'http', 'webhook', 'email', 'workflow', 'dummy')
    - description: Tool description (required)
    - inputSchema: Input JSON Schema (required)
    - outputSchema: Output JSON Schema (required)
    - authType: Authentication type - none|api_key|oauth_stub (required)
    - endpointConfig: Endpoint configuration (required for http/rest/webhook tools)
    - tenantScope: Tenant scope - global|tenant (default: tenant)
    
    Request Body (Legacy format - backward compatibility):
    - name: Tool name (required)
    - type: Tool type (required)
    - config: Tool configuration JSON (required)
    
    Query Parameters:
    - tenant_id: Optional tenant identifier. If provided, creates tenant-scoped tool.
                 If omitted, creates global tool.
                 Note: This overrides tenantScope in request body for Phase 8 format.
    
    Returns:
    - Created tool definition record
    
    Raises:
    - HTTPException 400 if request body is invalid or schema validation fails
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

    # Get authenticated tenant ID
    authenticated_tenant_id = _get_tenant_id_from_request(request)
    
    scope = "tenant-scoped" if tenant_id else "global"
    logger.info(f"Creating {scope} tool for tenant_id={tenant_id}")

    try:
        # Validate Phase 8 schema if using enhanced format
        validated_request = None
        try:
            validated_request = tool_data.validate_phase8_schema()
        except ValueError as e:
            logger.error(f"Phase 8 schema validation failed: {e}", exc_info=True)
            raise HTTPException(status_code=400, detail=f"Schema validation failed: {str(e)}")

        from src.infrastructure.db.session import get_db_session_context

        async with get_db_session_context() as session:
            repo = ToolDefinitionRepository(session)

            # Determine tenant_id from request or query parameter
            # Query parameter takes precedence for backward compatibility
            final_tenant_id = tenant_id
            
            if validated_request:
                # Phase 8 format: Enforce schema validation and tenant scope rules
                
                # 1. Validate schema using ToolDefinitionConfig
                try:
                    from src.models.tool_definition_phase8 import ToolDefinitionConfig
                    ToolDefinitionConfig.validate_for_tool_type(validated_request.type, validated_request.to_config_dict())
                except ValueError as e:
                    logger.error(f"Tool definition config validation failed: {e}", exc_info=True)
                    raise HTTPException(status_code=400, detail=f"Tool configuration validation failed: {str(e)}")
                
                # 2. Enforce tenant scope rules
                if validated_request.tenant_scope == TenantScope.GLOBAL:
                    # Global tools: tenant_id must be None
                    if final_tenant_id is not None:
                        logger.warning(
                            f"Tenant scope mismatch: tenantScope='global' but tenant_id={final_tenant_id} provided. "
                            "Ignoring tenant_id for global tool."
                        )
                    final_tenant_id = None  # Force global tool
                elif validated_request.tenant_scope == TenantScope.TENANT:
                    # Tenant-scoped tools: require authenticated tenant_id
                    if not authenticated_tenant_id:
                        raise HTTPException(
                            status_code=401,
                            detail="Authentication required to create tenant-scoped tools",
                        )
                    if final_tenant_id is None:
                        # Use authenticated tenant ID
                        final_tenant_id = authenticated_tenant_id
                    elif final_tenant_id != authenticated_tenant_id:
                        # Tenant ID mismatch
                        raise HTTPException(
                            status_code=403,
                            detail=f"Tenant ID mismatch: cannot create tool for tenant '{final_tenant_id}'. "
                            f"Authenticated tenant is '{authenticated_tenant_id}'",
                        )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid tenantScope: {validated_request.tenant_scope}. Must be 'global' or 'tenant'",
                    )
                
                # Convert to config dict for storage
                config_dict = validated_request.to_config_dict()
                tool_name = validated_request.name
                tool_type = validated_request.type
            else:
                # Legacy format: use provided fields
                if not tool_data.name or not tool_data.type or not tool_data.config:
                    raise HTTPException(
                        status_code=400,
                        detail="Legacy format requires: name, type, and config fields",
                    )
                
                # For legacy format, enforce tenant scope rules based on tenant_id
                if final_tenant_id is not None:
                    # Tenant-scoped: require authentication
                    if not authenticated_tenant_id:
                        raise HTTPException(
                            status_code=401,
                            detail="Authentication required to create tenant-scoped tools",
                        )
                    if final_tenant_id != authenticated_tenant_id:
                        raise HTTPException(
                            status_code=403,
                            detail=f"Tenant ID mismatch: cannot create tool for tenant '{final_tenant_id}'. "
                            f"Authenticated tenant is '{authenticated_tenant_id}'",
                        )
                
                config_dict = tool_data.config
                tool_name = tool_data.name
                tool_type = tool_data.type

            # Create tool DTO
            create_dto = ToolDefinitionCreateDTO(
                name=tool_name,
                type=tool_type,
                config=config_dict,
            )

            # Create tool (tenant_id=None for global, tenant_id=string for tenant-scoped)
            tool = await repo.create_tool(tenant_id=final_tenant_id, tool_data=create_dto)

            # Convert to response format
            response = ToolDefinitionResponse(
                toolId=tool.tool_id,
                tenantId=tool.tenant_id,
                name=tool.name,
                type=tool.type,
                config=tool.config if isinstance(tool.config, dict) else {},
                createdAt=tool.created_at.isoformat() if tool.created_at else "",
            )

            logger.info(f"Created {scope} tool {tool.tool_id} (tenant_id={final_tenant_id})")

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


def _get_tenant_id_from_request(request: Request) -> Optional[str]:
    """Extract tenant_id from request state (set by middleware)."""
    if request and hasattr(request.state, "tenant_id"):
        return request.state.tenant_id
    return None


def _get_authenticated_tenant_id(request: Request) -> str:
    """
    Get authenticated tenant ID from request.
    
    Raises:
        HTTPException: If tenant_id is not available
    """
    tenant_id = _get_tenant_id_from_request(request)
    if not tenant_id:
        raise HTTPException(
            status_code=401,
            detail="Authentication required: tenant_id not found in request",
        )
    return tenant_id


def _get_execution_service(session) -> ToolExecutionService:
    """Get ToolExecutionService instance with dependencies."""
    from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
    
    tool_def_repo = ToolDefinitionRepository(session)
    tool_exec_repo = ToolExecutionRepository(session)
    event_repo = ExceptionEventRepository(session)
    enablement_repo = ToolEnablementRepository(session)
    validation_service = ToolValidationService(tool_def_repo, enablement_repo)
    
    return ToolExecutionService(
        tool_definition_repository=tool_def_repo,
        tool_execution_repository=tool_exec_repo,
        exception_event_repository=event_repo,
        validation_service=validation_service,
        http_provider=HttpToolProvider(
            allowed_schemes=['https'],  # P8-14: Enforce HTTPS by default
            # allowed_domains can be configured via TOOL_ALLOWED_DOMAINS env var
        ),
        dummy_provider=DummyToolProvider(),
    )


# ============================================================================
# Phase 8: Tool Execution API Endpoints
# ============================================================================


class ToolExecuteRequest(BaseModel):
    """Request model for executing a tool."""

    payload: dict[str, Any] = Field(..., description="Input payload for the tool")
    exceptionId: Optional[str] = Field(None, alias="exception_id", description="Optional exception identifier to link execution")
    actorType: str = Field(default="user", alias="actor_type", description="Actor type: user, agent, or system")
    actorId: str = Field(..., alias="actor_id", description="Actor identifier (user ID or agent name)")

    class Config:
        populate_by_name = True


def get_event_publisher() -> EventPublisherService:
    """
    Get the global event publisher service instance.
    
    In production, this would be injected via dependency injection.
    
    Returns:
        EventPublisherService instance
    """
    # For MVP, create a singleton instance
    # In production, use dependency injection
    from src.messaging.broker import get_broker_settings
    from src.messaging.kafka_broker import KafkaBroker
    from src.messaging.event_store import DatabaseEventStore
    
    # Get broker settings and create broker
    broker_settings = get_broker_settings()
    broker = KafkaBroker(
        bootstrap_servers=broker_settings.bootstrap_servers,
        client_id=broker_settings.client_id,
    )
    
    # Create event store (database-backed)
    # Note: In production, this would be injected
    event_store = DatabaseEventStore()
    
    return EventPublisherService(broker=broker, event_store=event_store)


@router.post("/{tool_id}/execute", response_model=ToolExecutionResponse, status_code=status.HTTP_202_ACCEPTED)
async def execute_tool(
    request: Request,
    tool_id: int = Path(..., ge=1, description="Tool identifier"),
    request_body: ToolExecuteRequest = ...,
) -> ToolExecutionResponse:
    """
    Request tool execution with the given payload.
    
    Phase 9 P9-18: Transformed to async command pattern.
    - Validates request
    - Creates tool_execution record in "requested" state
    - Creates ToolExecutionRequested event
    - Stores event in EventStore
    - Publishes to message broker
    - Returns 202 Accepted with execution_id
    
    Body:
    - payload: Input payload for the tool (must match tool's input_schema)
    - exceptionId: Optional exception identifier to link execution
    - actorType: Actor type (user, agent, system) - defaults to "user"
    - actorId: Actor identifier (required)
    
    Returns:
    - 202 Accepted
    - execution_id (generated UUID)
    - status: "accepted"
    
    Raises:
    - HTTPException 400 if payload validation fails or actor_type is invalid
    - HTTPException 401 if authentication required
    - HTTPException 403 if tenant access denied
    - HTTPException 404 if tool not found
    - HTTPException 500 if event publishing fails
    """
    # Get authenticated tenant ID
    tenant_id = _get_authenticated_tenant_id(request)
    
    logger.info(
        f"Requesting tool execution: tool_id={tool_id}, tenant_id={tenant_id} "
        f"(actor: {request_body.actorType}/{request_body.actorId})"
    )
    
    # Validate actor type
    try:
        actor_type = ActorType(request_body.actorType.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid actor_type: {request_body.actorType}. Must be one of: user, agent, system",
        )
    
    # Validate tool exists and is accessible
    try:
        async with get_db_session_context() as session:
            tool_def_repo = ToolDefinitionRepository(session)
            tool = await tool_def_repo.get_tool(tool_id=tool_id, tenant_id=tenant_id)
            
            if tool is None:
                logger.warning(
                    f"Tool {tool_id} not found or not accessible to tenant {tenant_id}"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool {tool_id} not found or not accessible",
                )
            
            # Get tool name for event
            tool_name = tool.name
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating tool: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to validate tool: {str(e)}")
    
    # Create tool_execution record in "requested" state
    try:
        async with get_db_session_context() as session:
            tool_exec_repo = ToolExecutionRepository(session)
            
            execution_data = ToolExecutionCreateDTO(
                tenant_id=tenant_id,
                tool_id=tool_id,
                exception_id=request_body.exceptionId,
                status=ToolExecutionStatus.REQUESTED,
                requested_by_actor_type=actor_type,
                requested_by_actor_id=request_body.actorId,
                input_payload=request_body.payload,
                output_payload=None,
                error_message=None,
            )
            
            # Create execution record (ID is generated by database)
            execution = await tool_exec_repo.create_execution(execution_data)
            execution_id = str(execution.id)
            
            await session.commit()
            
            logger.info(
                f"Created tool execution record: execution_id={execution_id}, "
                f"tool_id={tool_id}, tenant_id={tenant_id}, status=requested"
            )
    except Exception as e:
        logger.error(f"Error creating tool execution record: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create execution record: {str(e)}",
        )
    
    # Get event publisher
    event_publisher = get_event_publisher()
    
    # Create ToolExecutionRequested event
    try:
        # ToolExecutionRequested requires exception_id as str, but it can be empty if not linked
        exception_id_for_event = request_body.exceptionId if request_body.exceptionId else ""
        
        tool_execution_event = ToolExecutionRequested.create(
            tenant_id=tenant_id,
            exception_id=exception_id_for_event,
            tool_id=str(tool_id),
            tool_name=tool_name,
            tool_params=request_body.payload,
            execution_context={
                "execution_id": execution_id,
                "actor_type": request_body.actorType,
                "actor_id": request_body.actorId,
            },
        )
    except Exception as e:
        logger.error(f"Failed to create ToolExecutionRequested event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create event: {str(e)}",
        )
    
    # Publish event (this will store in EventStore and publish to broker)
    try:
        await event_publisher.publish_event(
            topic="exceptions",
            event=tool_execution_event.model_dump(by_alias=True),
        )
        
        logger.info(
            f"Published ToolExecutionRequested event: execution_id={execution_id}, "
            f"tool_id={tool_id}, tenant_id={tenant_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to publish ToolExecutionRequested event: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish event: {str(e)}",
        )
    
    # Return 202 Accepted with minimal response
    # Note: Full execution details would be available via GET endpoint after async processing
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    return ToolExecutionResponse(
        executionId=execution_id,
        tenantId=tenant_id,
        toolId=tool_id,
        exceptionId=request_body.exceptionId,
        status="requested",  # Status is "requested" since it's queued
        requestedByActorType=request_body.actorType,
        requestedByActorId=request_body.actorId,
        inputPayload=request_body.payload,
        outputPayload=None,
        errorMessage=None,
        createdAt=now.isoformat(),
        updatedAt=now.isoformat(),
    )


@router.get("/executions/{execution_id}", response_model=ToolExecutionResponse)
async def get_execution(
    request: Request,
    execution_id: str = Path(..., description="Execution identifier (UUID)"),
) -> ToolExecutionResponse:
    """
    Get a single tool execution by ID.
    
    GET /api/tools/executions/{execution_id}
    
    Returns:
    - Tool execution record
    
    Raises:
    - HTTPException 401 if authentication required
    - HTTPException 403 if tenant access denied
    - HTTPException 404 if execution not found
    """
    # Get authenticated tenant ID
    tenant_id = _get_authenticated_tenant_id(request)
    
    logger.info(f"Getting execution {execution_id} for tenant {tenant_id}")
    
    # Validate UUID format
    from uuid import UUID
    try:
        execution_uuid = UUID(execution_id)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid execution_id format: {execution_id}. Must be a valid UUID",
        )
    
    try:
        async with get_db_session_context() as session:
            repo = ToolExecutionRepository(session)
            
            # Get execution with tenant isolation
            execution = await repo.get_execution(execution_id=execution_uuid, tenant_id=tenant_id)
            
            if execution is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool execution {execution_id} not found or access denied",
                )
            
            # Convert to response
            return ToolExecutionResponse(
                executionId=str(execution.id),
                tenantId=execution.tenant_id,
                toolId=execution.tool_id,
                exceptionId=execution.exception_id,
                status=execution.status.value,
                requestedByActorType=execution.requested_by_actor_type.value,
                requestedByActorId=execution.requested_by_actor_id,
                inputPayload=execution.input_payload,
                outputPayload=execution.output_payload,
                errorMessage=execution.error_message,
                createdAt=execution.created_at.isoformat() if execution.created_at else "",
                updatedAt=execution.updated_at.isoformat() if execution.updated_at else "",
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error getting execution: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to get execution: {str(e)}",
        )


# ============================================================================
# Phase 8: Tool Enablement Admin API Endpoints
# ============================================================================


class ToolEnablementRequest(BaseModel):
    """Request model for setting tool enablement."""

    enabled: bool = Field(..., description="Whether to enable (true) or disable (false) the tool")

    class Config:
        populate_by_name = True


class ToolEnablementResponse(BaseModel):
    """Response model for tool enablement status."""

    tenantId: str = Field(..., alias="tenant_id", description="Tenant identifier")
    toolId: int = Field(..., alias="tool_id", description="Tool identifier")
    enabled: bool = Field(..., description="Whether the tool is enabled")
    createdAt: str = Field(..., alias="created_at", description="Timestamp when enablement was created (ISO format)")
    updatedAt: str = Field(..., alias="updated_at", description="Timestamp when enablement was last updated (ISO format)")

    class Config:
        populate_by_name = True


@router.put("/{tool_id}/enablement", response_model=ToolEnablementResponse)
async def set_tool_enablement(
    request: Request,
    tool_id: int = Path(..., ge=1, description="Tool identifier"),
    request_body: ToolEnablementRequest = ...,
) -> ToolEnablementResponse:
    """
    Enable or disable a tool for the authenticated tenant.
    
    PUT /api/tools/{tool_id}/enablement
    
    Body:
    - enabled: true to enable, false to disable
    
    Returns:
    - Tool enablement record
    
    Raises:
    - HTTPException 401 if authentication required
    - HTTPException 403 if tenant access denied
    - HTTPException 404 if tool not found
    """
    # Get authenticated tenant ID
    tenant_id = _get_authenticated_tenant_id(request)
    
    logger.info(
        f"Setting tool enablement: tool_id={tool_id}, tenant_id={tenant_id}, "
        f"enabled={request_body.enabled}"
    )
    
    try:
        async with get_db_session_context() as session:
            from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
            from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
            
            # Verify tool exists and is accessible
            tool_def_repo = ToolDefinitionRepository(session)
            tool = await tool_def_repo.get_tool(tool_id=tool_id, tenant_id=tenant_id)
            if tool is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool {tool_id} not found or not accessible to tenant {tenant_id}",
                )
            
            # Set enablement
            enablement_repo = ToolEnablementRepository(session)
            enablement = await enablement_repo.set_enablement(
                tenant_id=tenant_id,
                tool_id=tool_id,
                enabled=request_body.enabled,
            )
            
            await session.commit()
            
            # Convert to response
            return ToolEnablementResponse(
                tenantId=enablement.tenant_id,
                toolId=enablement.tool_id,
                enabled=enablement.enabled,
                createdAt=enablement.created_at.isoformat() if enablement.created_at else "",
                updatedAt=enablement.updated_at.isoformat() if enablement.updated_at else "",
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error setting tool enablement: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to set tool enablement: {str(e)}",
        )


@router.get("/{tool_id}/enablement", response_model=ToolEnablementResponse)
async def get_tool_enablement(
    request: Request,
    tool_id: int = Path(..., ge=1, description="Tool identifier"),
) -> ToolEnablementResponse:
    """
    Get enablement status for a tool for the authenticated tenant.
    
    GET /api/tools/{tool_id}/enablement
    
    Returns:
    - Tool enablement record (defaults to enabled if no record exists)
    
    Raises:
    - HTTPException 401 if authentication required
    - HTTPException 404 if tool not found
    """
    # Get authenticated tenant ID
    tenant_id = _get_authenticated_tenant_id(request)
    
    logger.info(f"Getting tool enablement: tool_id={tool_id}, tenant_id={tenant_id}")
    
    try:
        async with get_db_session_context() as session:
            from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
            from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
            
            # Verify tool exists and is accessible
            tool_def_repo = ToolDefinitionRepository(session)
            tool = await tool_def_repo.get_tool(tool_id=tool_id, tenant_id=tenant_id)
            if tool is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool {tool_id} not found or not accessible to tenant {tenant_id}",
                )
            
            # Get enablement (defaults to enabled if not found)
            enablement_repo = ToolEnablementRepository(session)
            is_enabled = await enablement_repo.is_enabled(tenant_id, tool_id)
            enablement = await enablement_repo.get_enablement(tenant_id, tool_id)
            
            # If no record exists, return default (enabled)
            if enablement is None:
                from datetime import datetime, timezone
                now = datetime.now(timezone.utc)
                return ToolEnablementResponse(
                    tenantId=tenant_id,
                    toolId=tool_id,
                    enabled=True,  # Default
                    createdAt=now.isoformat(),
                    updatedAt=now.isoformat(),
                )
            
            # Convert to response
            return ToolEnablementResponse(
                tenantId=enablement.tenant_id,
                toolId=enablement.tool_id,
                enabled=enablement.enabled,
                createdAt=enablement.created_at.isoformat() if enablement.created_at else "",
                updatedAt=enablement.updated_at.isoformat() if enablement.updated_at else "",
            )
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error getting tool enablement: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to get tool enablement: {str(e)}",
        )


@router.delete("/{tool_id}/enablement")
async def delete_tool_enablement(
    request: Request,
    tool_id: int = Path(..., ge=1, description="Tool identifier"),
) -> dict[str, str]:
    """
    Delete enablement record, reverting to default (enabled).
    
    DELETE /api/tools/{tool_id}/enablement
    
    Returns:
    - Success message
    
    Raises:
    - HTTPException 401 if authentication required
    - HTTPException 404 if tool not found
    """
    # Get authenticated tenant ID
    tenant_id = _get_authenticated_tenant_id(request)
    
    logger.info(f"Deleting tool enablement: tool_id={tool_id}, tenant_id={tenant_id}")
    
    try:
        async with get_db_session_context() as session:
            from src.infrastructure.repositories.tool_enablement_repository import ToolEnablementRepository
            from src.infrastructure.repositories.tool_definition_repository import ToolDefinitionRepository
            
            # Verify tool exists and is accessible
            tool_def_repo = ToolDefinitionRepository(session)
            tool = await tool_def_repo.get_tool(tool_id=tool_id, tenant_id=tenant_id)
            if tool is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tool {tool_id} not found or not accessible to tenant {tenant_id}",
                )
            
            # Delete enablement
            enablement_repo = ToolEnablementRepository(session)
            deleted = await enablement_repo.delete_enablement(tenant_id, tool_id)
            
            await session.commit()
            
            if deleted:
                return {"message": f"Tool enablement deleted for tool {tool_id}. Tool is now enabled by default."}
            else:
                return {"message": f"No enablement record found for tool {tool_id}. Tool is already enabled by default."}
    
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Error deleting tool enablement: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to delete tool enablement: {str(e)}",
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

