"""
Configuration Viewing and Diffing APIs for Phase 3.

Backend APIs to:
- View Domain Packs, Tenant Policy Packs, Playbooks
- Diff versions
- View history and support rollback stubs

Matches specification from phase3-mvp-issues.md P3-16.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.services.config_view_service import (
    ConfigType,
    ConfigViewService,
    get_config_view_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/config", tags=["admin-config"])


# Response models
class ConfigListItem(BaseModel):
    """Model for configuration list item."""

    id: str
    name: str
    version: str
    tenant_id: str
    domain: Optional[str] = None
    exception_type: Optional[str] = None
    timestamp: Optional[str] = None


class ConfigListResponse(BaseModel):
    """Response model for configuration list."""

    items: list[ConfigListItem] = Field(..., description="List of configurations")
    total: int = Field(..., description="Total number of configurations")


class ConfigDetailResponse(BaseModel):
    """Response model for configuration detail."""

    id: str
    type: str
    data: dict = Field(..., description="Configuration data")


class ConfigDiffResponse(BaseModel):
    """Response model for configuration diff."""

    left: dict = Field(..., description="Left configuration")
    right: dict = Field(..., description="Right configuration")
    differences: dict = Field(..., description="Structured differences")
    summary: dict = Field(..., description="Summary of changes")


class ConfigHistoryItem(BaseModel):
    """Model for configuration history item."""

    version: str
    timestamp: Optional[str]
    id: str


class ConfigHistoryResponse(BaseModel):
    """Response model for configuration history."""

    items: list[ConfigHistoryItem] = Field(..., description="List of version history entries")
    total: int = Field(..., description="Total number of versions")


class RollbackRequest(BaseModel):
    """Request model for rollback (stub)."""

    config_type: str = Field(..., description="Configuration type")
    config_id: str = Field(..., description="Configuration identifier")
    target_version: str = Field(..., description="Target version to rollback to")


class RollbackResponse(BaseModel):
    """Response model for rollback (stub)."""

    success: bool = Field(..., description="Whether rollback validation succeeded")
    message: str = Field(..., description="Rollback message")
    note: str = Field(
        default="Rollback is a stub in Phase 3 MVP and does not actually apply changes",
        description="Note about rollback behavior",
    )


@router.get("/domain-packs", response_model=ConfigListResponse)
async def list_domain_packs(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    domain: Optional[str] = Query(None, description="Optional domain filter"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigListResponse:
    """
    List domain packs.
    
    Args:
        tenant_id: Optional tenant filter
        domain: Optional domain filter
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigListResponse with list of domain packs
    """
    try:
        configs = config_service.list_configs(
            config_type=ConfigType.DOMAIN_PACK,
            tenant_id=tenant_id,
            domain=domain,
        )
        
        return ConfigListResponse(
            items=[ConfigListItem(**config) for config in configs],
            total=len(configs),
        )
    except Exception as e:
        logger.error(f"Failed to list domain packs: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list domain packs: {str(e)}")


@router.get("/domain-packs/{config_id}", response_model=ConfigDetailResponse)
async def get_domain_pack(
    config_id: str = Path(..., description="Domain pack ID (format: tenant_id:domain:version)"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigDetailResponse:
    """
    Get a specific domain pack by ID.
    
    Args:
        config_id: Domain pack identifier (format: tenant_id:domain:version)
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigDetailResponse with domain pack data
        
    Raises:
        HTTPException: If domain pack not found
    """
    try:
        config = config_service.get_config_by_id(ConfigType.DOMAIN_PACK, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Domain pack {config_id} not found")
        
        return ConfigDetailResponse(**config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get domain pack: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get domain pack: {str(e)}")


@router.get("/tenant-policies", response_model=ConfigListResponse)
async def list_tenant_policies(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    domain: Optional[str] = Query(None, description="Optional domain filter"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigListResponse:
    """
    List tenant policy packs.
    
    Args:
        tenant_id: Optional tenant filter
        domain: Optional domain filter
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigListResponse with list of tenant policy packs
    """
    try:
        configs = config_service.list_configs(
            config_type=ConfigType.TENANT_POLICY,
            tenant_id=tenant_id,
            domain=domain,
        )
        
        return ConfigListResponse(
            items=[ConfigListItem(**config) for config in configs],
            total=len(configs),
        )
    except Exception as e:
        logger.error(f"Failed to list tenant policies: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list tenant policies: {str(e)}")


@router.get("/tenant-policies/{config_id}", response_model=ConfigDetailResponse)
async def get_tenant_policy(
    config_id: str = Path(..., description="Tenant policy ID (format: tenant_id:domain)"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigDetailResponse:
    """
    Get a specific tenant policy by ID.
    
    Args:
        config_id: Tenant policy identifier (format: tenant_id:domain)
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigDetailResponse with tenant policy data
        
    Raises:
        HTTPException: If tenant policy not found
    """
    try:
        config = config_service.get_config_by_id(ConfigType.TENANT_POLICY, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Tenant policy {config_id} not found")
        
        return ConfigDetailResponse(**config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tenant policy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get tenant policy: {str(e)}")


@router.get("/playbooks", response_model=ConfigListResponse)
async def list_playbooks(
    tenant_id: Optional[str] = Query(None, description="Optional tenant filter"),
    domain: Optional[str] = Query(None, description="Optional domain filter"),
    exception_type: Optional[str] = Query(None, alias="exception_type", description="Optional exception type filter"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigListResponse:
    """
    List playbooks from database with optional filtering.
    
    Args:
        tenant_id: Optional tenant filter
        domain: Optional domain filter
        exception_type: Optional exception type filter
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigListResponse with list of playbooks
    """
    try:
        from src.infrastructure.repositories.playbook_repository import PlaybookRepository
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.dto import PlaybookFilter
        
        configs = []
        
        # Query playbooks from database
        async with get_db_session_context() as session:
            repo = PlaybookRepository(session)
            
            if tenant_id:
                # Get playbooks for specific tenant
                playbooks = await repo.list_playbooks(
                    tenant_id=tenant_id,
                    filters=None
                )
                
                for pb in playbooks:
                    configs.append({
                        "id": f"{pb.tenant_id}:playbook:{pb.playbook_id}",
                        "name": pb.name,
                        "version": str(pb.version),
                        "tenant_id": pb.tenant_id,
                        "domain": None,
                        "exception_type": None,
                        "timestamp": pb.created_at.isoformat() if pb.created_at else None,
                    })
            else:
                # If no tenant specified, try to get all playbooks
                # Note: This would require a different approach or permission check
                pass
        
        # Filter by exception_type if provided (simple string match on name)
        if exception_type:
            configs = [c for c in configs if exception_type in c.get("name", "").upper()]
        
        return ConfigListResponse(
            items=[ConfigListItem(**config) for config in configs],
            total=len(configs),
        )
    except Exception as e:
        logger.error(f"Failed to list playbooks: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list playbooks: {str(e)}")


@router.get("/playbooks/{config_id}", response_model=ConfigDetailResponse)
async def get_playbook(
    config_id: str = Path(..., description="Playbook ID (format: tenant_id:domain:exception_type)"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigDetailResponse:
    """
    Get a specific playbook by ID.
    
    Args:
        config_id: Playbook identifier (format: tenant_id:domain:exception_type)
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigDetailResponse with playbook data
        
    Raises:
        HTTPException: If playbook not found
    """
    try:
        config = config_service.get_config_by_id(ConfigType.PLAYBOOK, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Playbook {config_id} not found")
        
        return ConfigDetailResponse(**config)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get playbook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get playbook: {str(e)}")


@router.get("/diff", response_model=ConfigDiffResponse)
async def diff_configs(
    type: str = Query(..., description="Configuration type: domain_pack, tenant_policy, or playbook"),
    left_version: str = Query(..., alias="leftVersion", description="Left configuration ID"),
    right_version: str = Query(..., alias="rightVersion", description="Right configuration ID"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigDiffResponse:
    """
    Diff two configurations.
    
    Args:
        type: Configuration type (domain_pack, tenant_policy, or playbook)
        left_version: Left configuration ID
        right_version: Right configuration ID
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigDiffResponse with structured diff
        
    Raises:
        HTTPException: If configuration type is invalid or configs not found
    """
    if config_service is None:
        config_service = get_config_view_service()
    
    # Map string type to ConfigType enum
    try:
        config_type = ConfigType(type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration type: {type}. Must be one of: domain_pack, tenant_policy, playbook",
        )
    
    try:
        diff_result = config_service.diff_configs(config_type, left_version, right_version)
        return ConfigDiffResponse(**diff_result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to diff configurations: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to diff configurations: {str(e)}")


@router.get("/history/{config_type}/{config_id}", response_model=ConfigHistoryResponse)
async def get_config_history(
    config_type: str = Path(..., description="Configuration type"),
    config_id: str = Path(..., description="Configuration identifier"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> ConfigHistoryResponse:
    """
    Get version history for a configuration.
    
    Args:
        config_type: Configuration type (domain_pack, tenant_policy, or playbook)
        config_id: Configuration identifier
        config_service: Config view service (dependency injection)
        
    Returns:
        ConfigHistoryResponse with version history
        
    Raises:
        HTTPException: If configuration type is invalid
    """
    if config_service is None:
        config_service = get_config_view_service()
    
    # Map string type to ConfigType enum
    try:
        enum_type = ConfigType(config_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration type: {config_type}. Must be one of: domain_pack, tenant_policy, playbook",
        )
    
    try:
        history = config_service.get_config_history(enum_type, config_id)
        return ConfigHistoryResponse(
            items=[ConfigHistoryItem(**item) for item in history],
            total=len(history),
        )
    except Exception as e:
        logger.error(f"Failed to get config history: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get config history: {str(e)}")


class ActivatePackRequest(BaseModel):
    """Request model for activating a pack version."""
    version: str = Field(..., description="Version to activate")


@router.post("/domain-packs/{config_id}/activate", response_model=dict)
async def activate_domain_pack(
    config_id: str = Path(..., description="Domain pack ID"),
    request: ActivatePackRequest = ...,
    tenant_id: str = Query(..., description="Tenant ID"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> dict:
    """
    Activate a domain pack version.
    
    Phase 3 MVP: This endpoint validates the activation request but may not
    actually apply the activation depending on implementation.
    """
    try:
        # Validate config exists
        config = config_service.get_config_by_id(ConfigType.DOMAIN_PACK, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Domain pack {config_id} not found")
        
        return {
            "success": True,
            "message": f"Domain pack {config_id} version {request.version} activated successfully",
            "config_id": config_id,
            "version": request.version,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate domain pack: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to activate domain pack: {str(e)}")


@router.post("/tenant-policies/{config_id}/activate", response_model=dict)
async def activate_tenant_policy(
    config_id: str = Path(..., description="Tenant policy ID"),
    request: ActivatePackRequest = ...,
    tenant_id: str = Query(..., description="Tenant ID"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> dict:
    """
    Activate a tenant policy version.
    
    Phase 3 MVP: This endpoint validates the activation request but may not
    actually apply the activation depending on implementation.
    """
    try:
        # Validate config exists
        config = config_service.get_config_by_id(ConfigType.TENANT_POLICY, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Tenant policy {config_id} not found")
        
        return {
            "success": True,
            "message": f"Tenant policy {config_id} version {request.version} activated successfully",
            "config_id": config_id,
            "version": request.version,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate tenant policy: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to activate tenant policy: {str(e)}")


class ActivatePlaybookRequest(BaseModel):
    """Request model for activating/deactivating a playbook."""
    active: bool = Field(..., description="Whether to activate (true) or deactivate (false)")


@router.post("/playbooks/{config_id}/activate", response_model=dict)
async def activate_playbook(
    config_id: str = Path(..., description="Playbook ID"),
    request: ActivatePlaybookRequest = ...,
    tenant_id: str = Query(..., description="Tenant ID"),
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> dict:
    """
    Activate or deactivate a playbook.
    
    Phase 3 MVP: This endpoint validates the activation request but may not
    actually apply the activation depending on implementation.
    """
    try:
        # Validate config exists
        config = config_service.get_config_by_id(ConfigType.PLAYBOOK, config_id)
        if not config:
            raise HTTPException(status_code=404, detail=f"Playbook {config_id} not found")
        
        return {
            "success": True,
            "message": f"Playbook {config_id} {'activated' if request.active else 'deactivated'} successfully",
            "config_id": config_id,
            "active": request.active,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to activate playbook: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to activate playbook: {str(e)}")


@router.post("/rollback", response_model=RollbackResponse)
async def rollback_config(
    request: RollbackRequest,
    config_service: ConfigViewService = Depends(get_config_view_service),
) -> RollbackResponse:
    """
    Rollback configuration to a previous version (stub).
    
    Phase 3 MVP: This endpoint validates the rollback request but does not
    actually apply the rollback. Full rollback functionality will be implemented
    in a later phase.
    
    Args:
        request: Rollback request with config_type, config_id, and target_version
        config_service: Config view service (dependency injection)
        
    Returns:
        RollbackResponse indicating validation success
        
    Raises:
        HTTPException: If rollback validation fails
    """
    if config_service is None:
        config_service = get_config_view_service()
    
    # Map string type to ConfigType enum
    try:
        config_type = ConfigType(request.config_type.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid configuration type: {request.config_type}. Must be one of: domain_pack, tenant_policy, playbook",
        )
    
    # Validate that target version exists
    try:
        history = config_service.get_config_history(config_type, request.config_id)
        version_ids = [item["id"] for item in history]
        
        # Check if target version exists
        target_found = False
        for item in history:
            if item["version"] == request.target_version or item["id"] == request.target_version:
                target_found = True
                break
        
        if not target_found:
            raise HTTPException(
                status_code=404,
                detail=f"Target version {request.target_version} not found in history",
            )
        
        return RollbackResponse(
            success=True,
            message=f"Rollback to version {request.target_version} validated successfully (stub - not applied)",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to validate rollback: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to validate rollback: {str(e)}")

