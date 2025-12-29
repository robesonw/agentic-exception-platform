"""
Admin API routes for Tenant Policy Pack Management.

Phase 2: Tenant Policy Pack upload, validation against domain pack, storage, versioning, and activation.

Matches specification from phase2-mvp-issues.md Issue 38.
"""

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter, File, HTTPException, Path as PathParam, Query, UploadFile
from pydantic import BaseModel, Field

from src.domainpack.loader import DomainPackRegistry
from src.domainpack.storage import DomainPackStorage
from src.models.tenant_policy import TenantPolicyPack
from src.tenantpack.loader import (
    TenantPolicyRegistry,
    TenantPolicyValidationError,
    load_tenant_policy,
    validate_tenant_policy,
)
from src.services.copilot.indexing.rebuild_service import IndexRebuildService, IndexRebuildError
from src.services.copilot.chunking_service import DocumentChunkingService
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.infrastructure.db.session import get_db_session_context
from src.audit.logger import AuditLogger

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/tenantpolicies", tags=["admin-tenantpolicies"])

# Global instances (would be injected via dependency in production)
_tenant_policy_registry: TenantPolicyRegistry | None = None
_domain_pack_storage: DomainPackStorage | None = None
_domain_pack_registry: DomainPackRegistry | None = None

# Simple in-memory storage for tenant policy packs (MVP)
# Structure: {tenant_id: {version: (TenantPolicyPack, timestamp)}}
_tenant_policy_storage: dict[str, dict[str, tuple[TenantPolicyPack, datetime]]] = {}
_active_policy_versions: dict[str, str] = {}  # {tenant_id: active_version}


def set_tenant_policy_registry(registry: TenantPolicyRegistry) -> None:
    """Set the tenant policy registry (for dependency injection)."""
    global _tenant_policy_registry
    _tenant_policy_registry = registry


def set_domain_pack_storage(storage: DomainPackStorage) -> None:
    """Set the domain pack storage (for dependency injection)."""
    global _domain_pack_storage
    _domain_pack_storage = storage


def set_domain_pack_registry(registry: DomainPackRegistry) -> None:
    """Set the domain pack registry (for dependency injection)."""
    global _domain_pack_registry
    _domain_pack_registry = registry


def get_tenant_policy_registry() -> TenantPolicyRegistry:
    """Get the tenant policy registry instance."""
    global _tenant_policy_registry
    if _tenant_policy_registry is None:
        _tenant_policy_registry = TenantPolicyRegistry()
    return _tenant_policy_registry


def get_domain_pack_storage() -> DomainPackStorage:
    """Get the domain pack storage instance."""
    global _domain_pack_storage
    if _domain_pack_storage is None:
        _domain_pack_storage = DomainPackStorage()
    return _domain_pack_storage


def get_domain_pack_registry() -> DomainPackRegistry:
    """Get the domain pack registry instance."""
    global _domain_pack_registry
    if _domain_pack_registry is None:
        _domain_pack_registry = DomainPackRegistry()
    return _domain_pack_registry


def _get_active_domain_pack(tenant_id: str, domain_name: str) -> Any:
    """
    Get the active domain pack for a tenant.
    
    Args:
        tenant_id: Tenant identifier
        domain_name: Domain name
        
    Returns:
        DomainPack instance
        
    Raises:
        HTTPException: If domain pack not found
    """
    # Try registry first
    registry = get_domain_pack_registry()
    domain_pack = registry.get_latest(domain_name=domain_name, tenant_id=tenant_id)
    
    if domain_pack:
        return domain_pack
    
    # Try storage
    storage = get_domain_pack_storage()
    domain_pack = storage.get_pack(tenant_id=tenant_id, domain_name=domain_name)
    
    if domain_pack:
        return domain_pack
    
    raise HTTPException(
        status_code=404,
        detail=f"Active Domain Pack '{domain_name}' not found for tenant '{tenant_id}'. "
               f"Please upload a Domain Pack first."
    )


class TenantPolicyUploadResponse(BaseModel):
    """Response for tenant policy pack upload."""

    tenant_id: str = Field(..., alias="tenantId")
    domain_name: str = Field(..., alias="domainName")
    version: str
    message: str
    stored: bool = Field(..., description="Whether policy was stored successfully")
    registered: bool = Field(..., description="Whether policy was registered successfully")
    activated: bool = Field(..., description="Whether policy was activated automatically")


class TenantPolicyInfo(BaseModel):
    """Information about a tenant policy pack version."""

    version: str
    domain_name: str = Field(..., alias="domainName")
    uploaded_at: str = Field(..., alias="uploadedAt")
    is_active: bool = Field(..., alias="isActive")


class TenantPolicyListResponse(BaseModel):
    """Response for listing tenant policy packs."""

    tenant_id: str = Field(..., alias="tenantId")
    active_version: str | None = Field(None, alias="activeVersion")
    policies: list[TenantPolicyInfo]
    total: int


class ActivateRequest(BaseModel):
    """Request for activating a tenant policy pack version."""

    version: str


class ActivateResponse(BaseModel):
    """Response for activation operation."""

    tenant_id: str = Field(..., alias="tenantId")
    previous_version: str | None = Field(None, alias="previousVersion")
    new_version: str = Field(..., alias="newVersion")
    success: bool
    message: str


@router.post("/{tenant_id}", response_model=TenantPolicyUploadResponse)
async def upload_tenant_policy(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
    file: UploadFile = File(..., description="Tenant Policy Pack file (JSON or YAML)"),
    version: str | None = None,
    activate: bool = Query(False, description="Automatically activate this version"),
) -> TenantPolicyUploadResponse:
    """
    Upload and register a Tenant Policy Pack for a tenant.
    
    Supports JSON and YAML formats. The policy is validated against the active Domain Pack,
    stored, and optionally activated.
    
    Args:
        tenant_id: Tenant identifier
        file: Uploaded Tenant Policy Pack file (JSON or YAML)
        version: Optional version string. If not provided, auto-generates based on timestamp
        activate: Whether to automatically activate this version (default: False)
        
    Returns:
        TenantPolicyUploadResponse with upload status
        
    Raises:
        HTTPException: If upload, validation, or storage fails
    """
    registry = get_tenant_policy_registry()
    
    # Read file content
    try:
        content = await file.read()
        file_content = content.decode("utf-8")
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read uploaded file: {str(e)}"
        )
    
    # Parse based on file extension or content
    file_extension = file.filename.split(".")[-1].lower() if file.filename else ""
    
    try:
        if file_extension in ("json",):
            data = json.loads(file_content)
        elif file_extension in ("yaml", "yml"):
            data = yaml.safe_load(file_content)
            if data is None:
                raise HTTPException(status_code=400, detail="YAML file is empty or contains no data")
        else:
            # Try to auto-detect format
            try:
                data = json.loads(file_content)
            except json.JSONDecodeError:
                try:
                    data = yaml.safe_load(file_content)
                    if data is None:
                        raise HTTPException(status_code=400, detail="File content is empty or invalid")
                except yaml.YAMLError:
                    raise HTTPException(
                        status_code=400,
                        detail="File format not recognized. Expected JSON or YAML."
                    )
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {str(e)}")
    except yaml.YAMLError as e:
        raise HTTPException(status_code=400, detail=f"Invalid YAML: {str(e)}")
    
    # Validate and create TenantPolicyPack
    try:
        policy = TenantPolicyPack.model_validate(data)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant Policy Pack schema validation failed: {str(e)}"
        )
    
    # Verify tenant_id matches
    if policy.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant ID in policy ('{policy.tenant_id}') does not match URL tenant ID ('{tenant_id}')"
        )
    
    # Get active domain pack for validation
    try:
        domain_pack = _get_active_domain_pack(tenant_id=tenant_id, domain_name=policy.domain_name)
    except HTTPException:
        raise
    
    # Validate policy against domain pack
    try:
        validate_tenant_policy(policy, domain_pack)
    except TenantPolicyValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Tenant Policy Pack validation failed: {str(e)}"
        )
    
    # Determine version
    if version is None:
        # Auto-generate version based on timestamp with microsecond precision
        now = datetime.now(timezone.utc)
        version = now.strftime("%Y%m%d%H%M%S") + f".{now.microsecond:06d}"
    
    # Store policy (in-memory for MVP)
    stored = False
    try:
        if tenant_id not in _tenant_policy_storage:
            _tenant_policy_storage[tenant_id] = {}
        
        _tenant_policy_storage[tenant_id][version] = (policy, datetime.now(timezone.utc))
        stored = True
        logger.info(
            f"Stored Tenant Policy Pack version {version} for tenant '{tenant_id}'"
        )
    except Exception as e:
        logger.error(f"Failed to store Tenant Policy Pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store Tenant Policy Pack: {str(e)}"
        )
    
    # Register policy
    registered = False
    try:
        registry.register(policy=policy, domain_pack=domain_pack)
        registered = True
        logger.info(
            f"Registered Tenant Policy Pack version {version} for tenant '{tenant_id}'"
        )
    except TenantPolicyValidationError as e:
        logger.error(f"Failed to register Tenant Policy Pack: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Tenant Policy Pack validation failed: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to register Tenant Policy Pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register Tenant Policy Pack: {str(e)}"
        )
    
    # Activate if requested
    activated = False
    if activate:
        try:
            previous_version = _active_policy_versions.get(tenant_id)
            _active_policy_versions[tenant_id] = version
            activated = True
            logger.info(
                f"Activated Tenant Policy Pack version {version} for tenant '{tenant_id}'"
            )
        except Exception as e:
            logger.error(f"Failed to activate Tenant Policy Pack: {e}")
            # Don't fail the upload if activation fails
    
    # Trigger async policy docs indexing if uploaded successfully (and optionally activated)
    if stored:
        asyncio.create_task(
            _trigger_policy_docs_indexing(
                tenant_id=tenant_id,
                domain=policy.domain_name,
                pack_version=version,
                operation="tenant_policy_upload" + ("_and_activate" if activated else "")
            )
        )
    
    return TenantPolicyUploadResponse(
        tenantId=tenant_id,
        domainName=policy.domain_name,
        version=version,
        message=f"Tenant Policy Pack version {version} uploaded successfully",
        stored=stored,
        registered=registered,
        activated=activated,
    )


@router.get("/{tenant_id}", response_model=TenantPolicyListResponse)
async def list_tenant_policies(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
) -> TenantPolicyListResponse:
    """
    List all Tenant Policy Pack versions for a tenant with active policy.
    
    Args:
        tenant_id: Tenant identifier
        
    Returns:
        TenantPolicyListResponse with list of policy versions and active version
    """
    # Get all versions for tenant
    tenant_policies = _tenant_policy_storage.get(tenant_id, {})
    active_version = _active_policy_versions.get(tenant_id)
    
    # Build policy info list
    policy_infos = []
    for version, (policy, timestamp) in tenant_policies.items():
        policy_info = TenantPolicyInfo(
            version=version,
            domainName=policy.domain_name,
            uploadedAt=timestamp.isoformat(),
            isActive=(version == active_version),
        )
        policy_infos.append(policy_info)
    
    # Sort by upload time (most recent first)
    policy_infos.sort(key=lambda x: x.uploaded_at, reverse=True)
    
    return TenantPolicyListResponse(
        tenantId=tenant_id,
        activeVersion=active_version,
        policies=policy_infos,
        total=len(policy_infos),
    )


@router.post("/{tenant_id}/activate", response_model=ActivateResponse)
async def activate_tenant_policy(
    tenant_id: str = PathParam(..., description="Tenant identifier"),
    request: ActivateRequest = ...,
) -> ActivateResponse:
    """
    Activate a specific version of Tenant Policy Pack.
    
    Args:
        tenant_id: Tenant identifier
        request: Activation request with version
        
    Returns:
        ActivateResponse with activation status
        
    Raises:
        HTTPException: If activation fails
    """
    target_version = request.version
    
    # Verify version exists
    tenant_policies = _tenant_policy_storage.get(tenant_id, {})
    if target_version not in tenant_policies:
        raise HTTPException(
            status_code=404,
            detail=f"Tenant Policy Pack version '{target_version}' not found for tenant '{tenant_id}'. "
                   f"Available versions: {', '.join(sorted(tenant_policies.keys()))}"
        )
    
    # Get the policy and domain pack
    policy, _ = tenant_policies[target_version]
    
    # Get active domain pack for validation
    try:
        domain_pack = _get_active_domain_pack(tenant_id=tenant_id, domain_name=policy.domain_name)
    except HTTPException:
        raise
    
    # Re-validate policy against domain pack
    try:
        validate_tenant_policy(policy, domain_pack)
    except TenantPolicyValidationError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot activate Tenant Policy Pack: validation failed: {str(e)}"
        )
    
    # Get previous active version
    previous_version = _active_policy_versions.get(tenant_id)
    
    # Activate version
    try:
        _active_policy_versions[tenant_id] = target_version
        
        # Re-register in registry (this becomes the active policy)
        registry = get_tenant_policy_registry()
        registry.register(policy=policy, domain_pack=domain_pack)
        
        logger.info(
            f"Activated Tenant Policy Pack version {target_version} for tenant '{tenant_id}'"
        )
        
        # Trigger async policy docs indexing after successful activation
        asyncio.create_task(
            _trigger_policy_docs_indexing(
                tenant_id=tenant_id,
                domain=policy.domain_name,
                pack_version=target_version,
                operation="tenant_policy_activation"
            )
        )
        
        return ActivateResponse(
            tenantId=tenant_id,
            previousVersion=previous_version,
            newVersion=target_version,
            success=True,
            message=f"Successfully activated version {target_version}",
        )
    except Exception as e:
        logger.error(f"Failed to activate Tenant Policy Pack: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to activate Tenant Policy Pack: {str(e)}"
        )


async def _trigger_policy_docs_indexing(
    tenant_id: str,
    domain: str,
    pack_version: str,
    operation: str,
) -> None:
    """
    Trigger async policy docs indexing for a tenant/domain/version.
    
    This function runs in the background and does not block the HTTP response.
    
    Args:
        tenant_id: Tenant identifier
        domain: Domain name  
        pack_version: Pack version
        operation: Operation type (tenant_policy_upload, tenant_policy_activation, etc.)
    """
    try:
        # Create indexing service
        async with get_db_session_context() as db_session:
            # Initialize required services
            chunking_service = DocumentChunkingService()
            embedding_service = EmbeddingService()
            document_repository = CopilotDocumentRepository()
            
            rebuild_service = IndexRebuildService(
                db_session=db_session,
                embedding_service=embedding_service,
                chunking_service=chunking_service,
                document_repository=document_repository,
            )
            
            # Start indexing job for policy_doc source only
            job_id = await rebuild_service.start_rebuild(
                tenant_id=tenant_id,
                sources=["policy_doc"],
                full_rebuild=False,  # Incremental by default
            )
            
            logger.info(
                f"Started policy docs indexing job {job_id} for tenant {tenant_id}, "
                f"domain {domain}, version {pack_version}, operation {operation}"
            )
            
            # Record audit event
            try:
                audit_logger = AuditLogger()
                await audit_logger.log_event(
                    event_type="POLICY_INDEX_TRIGGERED",
                    tenant_id=tenant_id,
                    details={
                        "job_id": job_id,
                        "domain": domain,
                        "pack_version": pack_version,
                        "operation": operation,
                        "source_types": ["policy_doc"],
                    },
                    result="success",
                )
            except Exception as audit_error:
                # Don't fail the indexing if audit logging fails
                logger.warning(f"Failed to record audit event: {audit_error}")
                
    except IndexRebuildError as e:
        logger.error(
            f"Failed to start policy docs indexing for tenant {tenant_id}, "
            f"domain {domain}, version {pack_version}: {e}"
        )
        # Record audit failure
        try:
            audit_logger = AuditLogger()
            await audit_logger.log_event(
                event_type="POLICY_INDEX_TRIGGERED",
                tenant_id=tenant_id,
                details={
                    "domain": domain,
                    "pack_version": pack_version,
                    "operation": operation,
                    "error": str(e),
                },
                result="failure",
            )
        except Exception:
            pass  # Ignore audit logging failures
            
    except Exception as e:
        logger.error(
            f"Unexpected error triggering policy docs indexing for tenant {tenant_id}: {e}",
            exc_info=True
        )

