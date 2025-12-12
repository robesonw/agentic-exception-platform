"""
Playbook API routes for Phase 7 preparation.

Phase 6 P6-24: Basic CRUD endpoints for playbook management.
All operations are tenant-scoped and enforce strict tenant isolation.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.repository.dto import PlaybookCreateDTO, PlaybookFilter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


class PlaybookResponse(BaseModel):
    """Response model for a single playbook."""

    playbookId: int = Field(..., description="Playbook identifier")
    tenantId: str = Field(..., description="Tenant identifier")
    name: str = Field(..., description="Playbook name")
    version: int = Field(..., description="Playbook version number")
    conditions: dict[str, Any] = Field(..., description="Matching rules (JSON)")
    createdAt: datetime = Field(..., description="Timestamp when playbook was created")

    class Config:
        populate_by_name = True


class PlaybookListResponse(BaseModel):
    """Response model for listing playbooks."""

    items: list[PlaybookResponse] = Field(..., description="List of playbook records")
    total: int = Field(..., description="Total number of playbooks matching filters")


class PlaybookCreateRequest(BaseModel):
    """Request model for creating a playbook."""

    name: str = Field(..., min_length=1, description="Playbook name")
    version: int = Field(..., ge=1, description="Playbook version number")
    conditions: dict[str, Any] = Field(..., description="Matching rules (JSON)")


@router.get("", response_model=PlaybookListResponse)
async def list_playbooks(
    tenant_id: str = Query(..., description="Tenant identifier (required for isolation)"),
    name: Optional[str] = Query(None, description="Filter by playbook name (partial match)"),
    version: Optional[int] = Query(None, ge=1, description="Filter by playbook version"),
    request: Request = None,
) -> PlaybookListResponse:
    """
    List playbooks for a tenant with optional filtering.
    
    GET /api/playbooks
    
    Query Parameters:
    - tenant_id: Tenant identifier (required)
    - name: Optional playbook name filter (partial match, case-insensitive)
    - version: Optional version filter
    
    Returns:
    - List of playbooks for the tenant
    
    Raises:
    - HTTPException 400 if tenant_id is missing
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
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
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Listing playbooks for tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            repo = PlaybookRepository(session)
            
            # Build filter from query parameters
            filters = PlaybookFilter()
            if name:
                filters.name = name
            if version is not None:
                filters.version = version
            
            # List playbooks
            playbooks = await repo.list_playbooks(tenant_id=tenant_id, filters=filters if any([name, version]) else None)
            
            # Convert to response format
            items = [
                PlaybookResponse(
                    playbookId=pb.playbook_id,
                    tenantId=pb.tenant_id,
                    name=pb.name,
                    version=pb.version,
                    conditions=pb.conditions if isinstance(pb.conditions, dict) else {},
                    createdAt=pb.created_at,
                )
                for pb in playbooks
            ]
            
            logger.info(f"Listed {len(items)} playbooks for tenant {tenant_id}")
            
            return PlaybookListResponse(items=items, total=len(items))
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing playbooks from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to list playbooks: {str(e)}",
        )


@router.get("/{playbook_id}", response_model=PlaybookResponse)
async def get_playbook(
    playbook_id: int = Path(..., ge=1, description="Playbook identifier"),
    tenant_id: str = Query(..., description="Tenant identifier (required for isolation)"),
    request: Request = None,
) -> PlaybookResponse:
    """
    Get a single playbook by ID.
    
    GET /api/playbooks/{playbook_id}
    
    Query Parameters:
    - tenant_id: Tenant identifier (required)
    
    Returns:
    - Playbook record
    
    Raises:
    - HTTPException 400 if tenant_id is missing
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if playbook not found or doesn't belong to tenant
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
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
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Retrieving playbook {playbook_id} for tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            repo = PlaybookRepository(session)
            
            # Get playbook (enforces tenant isolation)
            playbook = await repo.get_playbook(playbook_id=playbook_id, tenant_id=tenant_id)
            
            if playbook is None:
                logger.warning(
                    f"Playbook {playbook_id} not found for tenant {tenant_id} "
                    "or doesn't belong to tenant"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Playbook {playbook_id} not found for tenant {tenant_id}",
                )
            
            # Convert to response format
            response = PlaybookResponse(
                playbookId=playbook.playbook_id,
                tenantId=playbook.tenant_id,
                name=playbook.name,
                version=playbook.version,
                conditions=playbook.conditions if isinstance(playbook.conditions, dict) else {},
                createdAt=playbook.created_at,
            )
            
            logger.info(f"Retrieved playbook {playbook_id} for tenant {tenant_id}")
            
            return response
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error retrieving playbook from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to retrieve playbook: {str(e)}",
        )


@router.post("", response_model=PlaybookResponse, status_code=201)
async def create_playbook(
    playbook_data: PlaybookCreateRequest,
    tenant_id: str = Query(..., description="Tenant identifier (required for isolation)"),
    request: Request = None,
) -> PlaybookResponse:
    """
    Create a new playbook.
    
    POST /api/playbooks
    
    Request Body:
    - name: Playbook name (required)
    - version: Playbook version number (required, >= 1)
    - conditions: Matching rules (JSON, required)
    
    Query Parameters:
    - tenant_id: Tenant identifier (required)
    
    Returns:
    - Created playbook record
    
    Raises:
    - HTTPException 400 if tenant_id is missing or request body is invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
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
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Creating playbook for tenant {tenant_id}: {playbook_data.name} v{playbook_data.version}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        
        async with get_db_session_context() as session:
            repo = PlaybookRepository(session)
            
            # Create playbook DTO
            create_dto = PlaybookCreateDTO(
                name=playbook_data.name,
                version=playbook_data.version,
                conditions=playbook_data.conditions,
            )
            
            # Create playbook (enforces tenant isolation)
            playbook = await repo.create_playbook(tenant_id=tenant_id, playbook_data=create_dto)
            
            # Convert to response format
            response = PlaybookResponse(
                playbookId=playbook.playbook_id,
                tenantId=playbook.tenant_id,
                name=playbook.name,
                version=playbook.version,
                conditions=playbook.conditions if isinstance(playbook.conditions, dict) else {},
                createdAt=playbook.created_at,
            )
            
            logger.info(f"Created playbook {playbook.playbook_id} for tenant {tenant_id}")
            
            return response
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error creating playbook in database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to create playbook: {str(e)}",
        )

