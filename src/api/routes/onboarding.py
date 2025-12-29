"""
Admin API Routes for Tenant & Pack Onboarding.

Provides tenant and pack management APIs:
- Tenant Management (create, list, status updates)
- Domain Pack Import & Validation
- Tenant Pack Import & Validation
- Pack Listing & Version Management
- Pack Activation
- Audit Logging for pack operations

Reference: docs/phase12-onboarding-packs-mvp.md
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status as http_status
from pydantic import BaseModel, ConfigDict, Field

from src.api.auth import Role, get_auth_manager
from src.api.middleware import TenantRouterMiddleware
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.config_change_repository import (
    ConfigChangeRepository,
    ConfigChangeType,
    ConfigChangeStatus,
)
from src.infrastructure.repositories.onboarding_domain_pack_repository import DomainPackRepository
from src.infrastructure.repositories.onboarding_tenant_pack_repository import TenantPackRepository
from src.infrastructure.repositories.pack_validation_service import (
    PackValidationService,
    ValidationResult,
)
from src.infrastructure.repositories.tenant_active_config_repository import (
    TenantActiveConfigRepository,
)
from src.infrastructure.repositories.tenant_repository import TenantRepository
from src.infrastructure.repositories.governance_audit_repository import GovernanceAuditRepository
from src.infrastructure.db.models import TenantStatus, PackStatus
from src.services.governance_audit import (
    AuditEventTypes,
    EntityTypes,
    Actions,
    get_or_create_correlation_id,
    set_correlation_id,
    set_request_id,
    generate_request_id,
    ActorContext,
    set_actor_context,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["onboarding"])


# =============================================================================
# Request/Response Models
# =============================================================================


class TenantCreateRequest(BaseModel):
    """Request to create a tenant."""

    tenant_id: str = Field(..., min_length=1, description="Tenant identifier")
    name: str = Field(..., min_length=1, description="Tenant name")


class TenantStatusUpdateRequest(BaseModel):
    """Request to update tenant status."""

    status: str = Field(..., description="New status: ACTIVE or SUSPENDED")


class TenantResponse(BaseModel):
    """Response for tenant operations."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    name: str
    status: str
    created_at: datetime
    created_by: Optional[str]
    updated_at: datetime


class PaginatedTenantResponse(BaseModel):
    """Paginated list of tenants."""

    items: list[TenantResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PackImportRequest(BaseModel):
    """Request to import a pack."""

    domain: Optional[str] = Field(None, description="Domain name (for domain packs)")
    tenant_id: Optional[str] = Field(None, description="Tenant ID (for tenant packs)")
    version: str = Field(..., min_length=1, description="Version string (e.g., 'v1.0')")
    content: dict = Field(..., description="Pack JSON content")
    overwrite: bool = Field(False, description="If True, update existing pack instead of raising error")


class PackValidateRequest(BaseModel):
    """Request to validate a pack."""

    pack_type: str = Field(..., description="Type: 'domain' or 'tenant'")
    content: dict = Field(..., description="Pack JSON content")
    domain: Optional[str] = Field(None, description="Domain name (for tenant pack validation)")


class PackValidationResponse(BaseModel):
    """Response for pack validation."""

    is_valid: bool
    errors: list[str]
    warnings: list[str]


class PackResponse(BaseModel):
    """Response for pack operations."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    domain: Optional[str]
    tenant_id: Optional[str]
    version: str
    status: str
    checksum: str
    created_at: datetime
    created_by: str
    content_json: Optional[dict] = None


class PaginatedPackResponse(BaseModel):
    """Paginated list of packs."""

    items: list[PackResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class PackActivateRequest(BaseModel):
    """Request to activate pack configuration."""

    tenant_id: str = Field(..., min_length=1, description="Tenant identifier")
    domain: Optional[str] = Field(None, description="Domain name (required when activating domain pack)")
    domain_pack_version: Optional[str] = Field(None, description="Domain pack version to activate")
    tenant_pack_version: Optional[str] = Field(None, description="Tenant pack version to activate")
    require_approval: bool = Field(
        False, description="Whether to require approval before activation"
    )


class PackActivateResponse(BaseModel):
    """Response for pack activation."""

    tenant_id: str
    active_domain_pack_version: Optional[str]
    active_tenant_pack_version: Optional[str]
    activated_at: datetime
    activated_by: str
    change_request_id: Optional[str] = Field(
        None, description="Config change request ID if approval required"
    )


class ActiveConfigResponse(BaseModel):
    """Response for active configuration."""

    model_config = ConfigDict(from_attributes=True)

    tenant_id: str
    active_domain_pack_version: Optional[str]
    active_tenant_pack_version: Optional[str]
    activated_at: datetime
    activated_by: str


class PlaybookRegistryEntry(BaseModel):
    """Playbook entry in the registry."""
    
    playbook_id: str = Field(..., description="Playbook identifier")
    name: str = Field(..., description="Playbook name")
    description: Optional[str] = Field(None, description="Playbook description")
    exception_type: Optional[str] = Field(None, description="Exception type or applies_to field")
    domain: str = Field(..., description="Domain name")
    version: str = Field(..., description="Pack version")
    status: str = Field(..., description="Status (active)")
    source_pack_type: str = Field(..., description="Source pack type: domain or tenant")
    source_pack_id: int = Field(..., description="Source pack database ID")
    source_pack_version: str = Field(..., description="Source pack version")
    steps_count: int = Field(..., description="Number of steps in playbook")
    tool_refs_count: int = Field(..., description="Number of tool references")
    overridden: bool = Field(False, description="Whether this playbook is overridden by tenant pack")
    overridden_from: Optional[str] = Field(None, description="Source of override if applicable")


class PlaybookRegistryResponse(BaseModel):
    """Response for playbook registry listing."""
    
    items: list[PlaybookRegistryEntry]
    total: int
    page: int
    page_size: int
    total_pages: int


# =============================================================================
# Helper Functions
# =============================================================================


def require_admin_role(request: Request) -> None:
    """
    Require ADMIN role for the request.
    
    Raises:
        HTTPException: If user is not authenticated or doesn't have ADMIN role
    """
    if not hasattr(request.state, "user_context"):
        raise HTTPException(
            status_code=http_status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )
    
    user_context = request.state.user_context
    auth_manager = get_auth_manager()
    
    try:
        auth_manager.require_role(user_context, Role.ADMIN)
    except Exception as e:
        raise HTTPException(
            status_code=http_status.HTTP_403_FORBIDDEN,
            detail=f"Admin role required: {str(e)}",
        )


def get_user_id(request: Request) -> str:
    """Get user ID from request state."""
    if hasattr(request.state, "user_context") and request.state.user_context.user_id:
        return request.state.user_context.user_id
    # Fallback to tenant_id if user_id not available
    if hasattr(request.state, "tenant_id"):
        return request.state.tenant_id
    return "system"


async def _log_governance_audit_event(
    session,
    event_type: str,
    entity_type: str,
    entity_id: str,
    action: str,
    actor_id: str,
    actor_role: Optional[str] = None,
    tenant_id: Optional[str] = None,
    domain: Optional[str] = None,
    entity_version: Optional[str] = None,
    before_json: Optional[dict] = None,
    after_json: Optional[dict] = None,
    diff_summary: Optional[str] = None,
    related_change_request_id: Optional[str] = None,
    metadata: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> Optional[str]:
    """
    Log governance audit event for Phase 12+ enterprise audit trail.

    Uses the new GovernanceAuditEvent table for standardized audit logging.

    Returns:
        Event ID if created, None otherwise
    """
    try:
        audit_repo = GovernanceAuditRepository(session)
        event = await audit_repo.create_event(
            event_type=event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            actor_role=actor_role,
            tenant_id=tenant_id,
            domain=domain,
            entity_version=entity_version,
            before_json=before_json,
            after_json=after_json,
            diff_summary=diff_summary,
            related_change_request_id=related_change_request_id,
            metadata=metadata,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        return str(event.id)
    except Exception as e:
        logger.warning(f"Failed to create governance audit event: {e}", exc_info=True)
        return None


async def _log_audit_event(
    event_type: str,
    tenant_id: str,
    user_id: str,
    details: dict,
    session,
) -> Optional[str]:
    """
    Legacy audit event logging - now routes to governance audit.

    For pack operations, creates a config change request for audit trail.
    For tenant operations, logs to application logs.

    Returns:
        Config change request ID if created, None otherwise
    """
    logger.info(
        f"Audit: {event_type} | tenant_id={tenant_id} | user_id={user_id} | details={details}"
    )

    # Map old event types to new governance audit events
    event_mapping = {
        "domain_pack_imported": (AuditEventTypes.DOMAIN_PACK_IMPORTED, EntityTypes.DOMAIN_PACK, Actions.IMPORT),
        "domain_pack_updated": (AuditEventTypes.DOMAIN_PACK_UPDATED, EntityTypes.DOMAIN_PACK, Actions.UPDATE),
        "tenant_pack_imported": (AuditEventTypes.TENANT_PACK_IMPORTED, EntityTypes.TENANT_PACK, Actions.IMPORT),
        "tenant_pack_updated": (AuditEventTypes.TENANT_PACK_UPDATED, EntityTypes.TENANT_PACK, Actions.UPDATE),
        "pack_activated": (AuditEventTypes.CONFIG_ACTIVATED, EntityTypes.ACTIVE_CONFIG, Actions.ACTIVATE),
        "pack_activation_requested": (AuditEventTypes.CONFIG_ACTIVATION_REQUESTED, EntityTypes.ACTIVE_CONFIG, Actions.ACTIVATE),
    }

    if event_type in event_mapping:
        audit_event_type, entity_type, action = event_mapping[event_type]

        # Determine entity_id based on event type
        if event_type.startswith("domain_pack"):
            entity_id = details.get("domain", "unknown")
            domain = details.get("domain")
            entity_version = details.get("version")
        elif event_type.startswith("tenant_pack"):
            entity_id = details.get("tenant_id", tenant_id)
            domain = details.get("domain")
            entity_version = details.get("version")
        else:
            entity_id = tenant_id
            domain = None
            entity_version = None

        # Create governance audit event
        await _log_governance_audit_event(
            session=session,
            event_type=audit_event_type,
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=user_id,
            actor_role="admin",
            tenant_id=tenant_id if tenant_id != "system" else details.get("tenant_id"),
            domain=domain,
            entity_version=entity_version,
            after_json=details,
            diff_summary=f"{event_type}: {entity_id}",
            metadata=details,
        )

    # Also create config change request for backward compatibility
    if event_type in ("domain_pack_imported", "domain_pack_updated", "tenant_pack_imported", "tenant_pack_updated", "pack_activated", "pack_activation_requested"):
        try:
            config_change_repo = ConfigChangeRepository(session)

            # Determine change type (convert enum to string value)
            if event_type == "domain_pack_imported":
                change_type = ConfigChangeType.DOMAIN_PACK.value
                resource_id = details.get("domain", "unknown")
                resource_name = f"Domain pack {details.get('domain')} v{details.get('version')}"
            elif event_type == "domain_pack_updated":
                change_type = ConfigChangeType.DOMAIN_PACK.value
                resource_id = details.get("domain", "unknown")
                resource_name = f"Domain pack {details.get('domain')} v{details.get('version')} (updated)"
            elif event_type == "tenant_pack_imported":
                change_type = ConfigChangeType.TENANT_POLICY.value
                resource_id = details.get("tenant_id", tenant_id)
                resource_name = f"Tenant pack for {resource_id} v{details.get('version')}"
            elif event_type == "tenant_pack_updated":
                change_type = ConfigChangeType.TENANT_POLICY.value
                resource_id = details.get("tenant_id", tenant_id)
                resource_name = f"Tenant pack for {resource_id} v{details.get('version')} (updated)"
            elif event_type in ("pack_activated", "pack_activation_requested"):
                change_type = ConfigChangeType.TENANT_POLICY.value
                resource_id = tenant_id
                resource_name = f"Active config for {tenant_id}"
            else:
                return None

            # Create audit change request (auto-approved for audit trail)
            change_request = await config_change_repo.create_change_request(
                tenant_id=tenant_id if tenant_id != "system" else details.get("tenant_id", "system"),
                change_type=change_type,
                resource_id=resource_id,
                proposed_config=details,
                requested_by=user_id,
                resource_name=resource_name,
                current_config=None,
                diff_summary=f"{event_type}: {details}",
                change_reason=f"Audit log for {event_type}",
            )

            # Auto-approve and mark as applied for audit trail entries
            if event_type in ("domain_pack_imported", "domain_pack_updated", "tenant_pack_imported", "tenant_pack_updated", "pack_activated"):
                await config_change_repo.approve_change_request(
                    change_id=change_request.id,
                    tenant_id=tenant_id if tenant_id != "system" else details.get("tenant_id", "system"),
                    reviewed_by="system",
                    review_comment="Auto-approved for audit trail",
                )
                await config_change_repo.mark_as_applied(
                    change_id=change_request.id,
                    tenant_id=tenant_id if tenant_id != "system" else details.get("tenant_id", "system"),
                    applied_by=user_id,
                )

            return change_request.id
        except Exception as e:
            logger.warning(f"Failed to create audit change request: {e}", exc_info=True)
            return None

    return None


# =============================================================================
# P12-10: Tenant Management APIs
# =============================================================================


@router.post("/tenants", response_model=TenantResponse, status_code=http_status.HTTP_201_CREATED)
async def create_tenant(
    request_data: TenantCreateRequest,
    request: Request,
):
    """
    Create a new tenant (P12-10).
    
    POST /admin/tenants
    """
    require_admin_role(request)
    user_id = get_user_id(request)
    
    async with get_db_session_context() as session:
        tenant_repo = TenantRepository(session)
        
        try:
            tenant = await tenant_repo.create_tenant(
                tenant_id=request_data.tenant_id,
                name=request_data.name,
                created_by=user_id,
            )

            # Log governance audit event
            await _log_governance_audit_event(
                session=session,
                event_type=AuditEventTypes.TENANT_CREATED,
                entity_type=EntityTypes.TENANT,
                entity_id=request_data.tenant_id,
                action=Actions.CREATE,
                actor_id=user_id,
                actor_role="admin",
                tenant_id=request_data.tenant_id,
                after_json={
                    "tenant_id": request_data.tenant_id,
                    "name": request_data.name,
                    "status": "active",
                },
                diff_summary=f"Created tenant {request_data.tenant_id}: {request_data.name}",
            )

            await session.commit()

            logger.info(
                f"Audit: tenant_created | tenant_id={request_data.tenant_id} | user_id={user_id} | name={request_data.name}"
            )

            return TenantResponse.model_validate(tenant)
        except ValueError as e:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error(f"Error creating tenant: {e}", exc_info=True)
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create tenant",
            )


@router.get("/tenants", response_model=PaginatedTenantResponse)
async def list_tenants(
    request: Request,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    status: Optional[str] = Query(None, description="Filter by status"),
):
    """
    List tenants with pagination (P12-10).
    
    GET /admin/tenants
    """
    require_admin_role(request)
    
    async with get_db_session_context() as session:
        tenant_repo = TenantRepository(session)
        
        # Build filters
        filters = {}
        status_enum = None
        if status:
            try:
                # Handle both uppercase (from UI) and lowercase (enum value) status
                status_enum = TenantStatus(status.lower())
                filters["status"] = status_enum
            except ValueError:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {status}. Must be ACTIVE or SUSPENDED",
                )

        # For admin, we can list all tenants (no tenant_id filter)
        # Note: TenantRepository.list_by_tenant requires tenant_id, so we'll use a different approach
        # We'll need to add a method to list all tenants for admin
        # For now, we'll use a workaround by querying directly

        from sqlalchemy import select
        from src.infrastructure.db.models import Tenant

        query = select(Tenant)
        if status_enum:
            query = query.where(Tenant.status == status_enum)

        # Get total count
        from sqlalchemy import func
        count_query = select(func.count(Tenant.tenant_id))
        if status_enum:
            count_query = count_query.where(Tenant.status == status_enum)
        
        count_result = await session.execute(count_query)
        total = count_result.scalar() or 0
        
        # Apply pagination
        offset = (page - 1) * page_size
        query = query.order_by(Tenant.created_at.desc()).offset(offset).limit(page_size)
        
        result = await session.execute(query)
        tenants = list(result.scalars().all())
        
        total_pages = (total + page_size - 1) // page_size if total > 0 else 0
        
        return PaginatedTenantResponse(
            items=[TenantResponse.model_validate(t) for t in tenants],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=total_pages,
        )


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: str,
    request: Request,
):
    """
    Get tenant by ID (P12-10).
    
    GET /admin/tenants/{tenant_id}
    """
    require_admin_role(request)
    
    async with get_db_session_context() as session:
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_id}",
            )
        
        return TenantResponse.model_validate(tenant)


@router.patch("/tenants/{tenant_id}/status", response_model=TenantResponse)
async def update_tenant_status(
    tenant_id: str,
    request_data: TenantStatusUpdateRequest,
    request: Request,
):
    """
    Update tenant status (P12-10).
    
    PATCH /admin/tenants/{tenant_id}/status
    """
    require_admin_role(request)
    user_id = get_user_id(request)
    
    async with get_db_session_context() as session:
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_tenant(tenant_id)
        
        if not tenant:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {tenant_id}",
            )
        
        try:
            # Handle both uppercase (from UI) and lowercase (enum value) status
            status_value = request_data.status.lower()
            new_status = TenantStatus(status_value)
        except ValueError:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {request_data.status}. Must be ACTIVE or SUSPENDED",
            )
        
        old_status = tenant.status
        tenant.status = new_status

        # Log governance audit event
        await _log_governance_audit_event(
            session=session,
            event_type=AuditEventTypes.TENANT_STATUS_CHANGED,
            entity_type=EntityTypes.TENANT,
            entity_id=tenant_id,
            action=Actions.STATUS_CHANGE,
            actor_id=user_id,
            actor_role="admin",
            tenant_id=tenant_id,
            before_json={"status": old_status.value},
            after_json={"status": new_status.value},
            diff_summary=f"Status changed from {old_status.value} to {new_status.value}",
        )

        await session.commit()
        await session.refresh(tenant)

        logger.info(
            f"Audit: tenant_status_updated | tenant_id={tenant_id} | user_id={user_id} | "
            f"old_status={old_status.value} | new_status={new_status.value}"
        )

        return TenantResponse.model_validate(tenant)


# =============================================================================
# P12-11: Pack Import & Validation APIs
# =============================================================================


@router.post("/packs/domain/import", response_model=PackResponse, status_code=http_status.HTTP_201_CREATED)
async def import_domain_pack(
    request_data: PackImportRequest,
    request: Request,
):
    """
    Import a domain pack (P12-11).
    
    POST /admin/packs/domain/import
    """
    require_admin_role(request)
    user_id = get_user_id(request)
    
    # Extract domain from request or content
    # Normalize by stripping whitespace
    domain_from_field = request_data.domain.strip() if request_data.domain else None
    content_domain = None
    if request_data.content:
        # Try to extract from content.domainName
        content_domain_raw = request_data.content.get("domainName") or request_data.content.get("domain")
        content_domain = content_domain_raw.strip() if content_domain_raw else None
    
    # Determine which domain to use
    domain = domain_from_field or content_domain
    
    # Log domain extraction for debugging
    logger.info(
        f"Domain extraction - request_data.domain: '{request_data.domain}', "
        f"domain_from_field: '{domain_from_field}', "
        f"content_domain: '{content_domain}', "
        f"final domain: '{domain}'"
    )
    
    if not domain:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="domain is required for domain pack import (provide in 'domain' field or in content.domainName)",
        )
    
    # If both are provided, ensure they match (case-insensitive comparison for user-friendliness)
    if domain_from_field and content_domain and domain_from_field.upper() != content_domain.upper():
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Domain mismatch: domain field ('{domain_from_field}') does not match content.domainName ('{content_domain}')",
        )
    
    # Normalize version by stripping whitespace
    if not request_data.version:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="version is required for domain pack import",
        )
    version = request_data.version.strip()
    
    logger.info(f"Import request - domain: '{domain}', version: '{version}', overwrite: {request_data.overwrite}")
    
    async with get_db_session_context() as session:
        # Validate pack first
        validation_service = PackValidationService()
        validation_result = validation_service.validate_domain_pack(request_data.content)
        
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Pack validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                },
            )
        
        # Import pack
        domain_pack_repo = DomainPackRepository(session)
        
        try:
            # Check if pack already exists
            logger.info(f"Checking if domain pack exists: domain='{domain}', version='{version}'")
            
            # Debug: List all packs for this domain to help diagnose issues
            all_packs_for_domain = await domain_pack_repo.list_domain_packs(domain=domain)
            logger.info(
                f"Found {len(all_packs_for_domain)} existing pack(s) for domain '{domain}': "
                f"{[(p.id, repr(p.domain), repr(p.version)) for p in all_packs_for_domain]}"
            )
            
            # Also check if any packs exist with similar domain names (case variations)
            all_packs = await domain_pack_repo.list_domain_packs()
            similar_domains = [p for p in all_packs if p.domain.upper() == domain.upper()]
            if similar_domains:
                logger.warning(
                    f"Found {len(similar_domains)} pack(s) with similar domain name (case-insensitive match): "
                    f"{[(p.id, repr(p.domain), repr(p.version)) for p in similar_domains]}"
                )
            
            existing = await domain_pack_repo.get_domain_pack(
                domain,
                version
            )
            
            if existing:
                logger.warning(
                    f"Domain pack already exists: domain='{domain}', version='{version}', "
                    f"existing_id={existing.id}, existing_domain='{existing.domain}', existing_version='{existing.version}'"
                )
                if request_data.overwrite:
                    # Update existing pack
                    logger.info(f"Overwriting existing pack with overwrite=true")
                    pack = await domain_pack_repo.update_domain_pack(
                        domain=domain,
                        version=version,
                        content_json=request_data.content,
                        updated_by=user_id,
                    )
                    
                    # Log audit event (P12-20) - do this BEFORE commit
                    try:
                        await _log_audit_event(
                            "domain_pack_updated",
                            "system",  # Domain packs are global
                            user_id,
                            {
                                "domain": domain,
                                "version": version,
                                "pack_id": pack.id,
                            },
                            session,
                        )
                    except Exception as audit_error:
                        logger.error(f"Failed to create audit log for domain pack update: {audit_error}", exc_info=True)
                        await session.rollback()
                        raise HTTPException(
                            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update domain pack: audit logging failed: {str(audit_error)}",
                        )
                    
                    # Commit only after both pack update and audit logging succeed
                    await session.commit()
                else:
                    await session.rollback()
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Domain pack version already exists: domain={domain}, version={version}. "
                               f"Please use a different version number (e.g., v1.1, v2.0), set overwrite=true to update, or delete the existing pack first.",
                    )
            else:
                # Create new pack (skip existence check since we already verified it doesn't exist)
                logger.info(f"Creating new domain pack: domain='{domain}', version='{version}'")
                pack = await domain_pack_repo.create_domain_pack(
                    domain=domain,
                    version=version,
                    content_json=request_data.content,
                    created_by=user_id,
                    skip_existence_check=True,  # We already checked above
                )
                logger.info(f"Successfully created domain pack: id={pack.id}, domain='{domain}', version='{version}'")
                
                # Log audit event (P12-20) - do this BEFORE commit so if it fails, we rollback
                # This ensures atomicity: either both pack creation and audit log succeed, or both fail
                try:
                    await _log_audit_event(
                        "domain_pack_imported",
                        "system",  # Domain packs are global
                        user_id,
                        {
                            "domain": domain,
                            "version": version,
                            "pack_id": pack.id,
                        },
                        session,
                    )
                except Exception as audit_error:
                    logger.error(f"Failed to create audit log for domain pack import: {audit_error}", exc_info=True)
                    await session.rollback()
                    raise HTTPException(
                        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to import domain pack: audit logging failed: {str(audit_error)}",
                    )
                
                # Commit only after both pack creation and audit logging succeed
                await session.commit()
            
            # Convert database model to response model with enum handling
            status_value = pack.status.value if isinstance(pack.status, PackStatus) else str(pack.status)
            return PackResponse(
                id=pack.id,
                domain=pack.domain,
                tenant_id=None,  # Domain packs don't have tenant_id
                version=pack.version,
                status=status_value,
                checksum=pack.checksum,
                created_at=pack.created_at,
                created_by=pack.created_by,
            )
        except HTTPException:
            # Re-raise HTTP exceptions (like the overwrite error)
            raise
        except ValueError as e:
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error(f"Error importing domain pack: {e}", exc_info=True)
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to import domain pack",
            )


@router.post("/packs/tenant/import", response_model=PackResponse, status_code=http_status.HTTP_201_CREATED)
async def import_tenant_pack(
    request_data: PackImportRequest,
    request: Request,
):
    """
    Import a tenant pack (P12-11).
    
    POST /admin/packs/tenant/import
    """
    require_admin_role(request)
    user_id = get_user_id(request)
    
    if not request_data.tenant_id:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail="tenant_id is required for tenant pack import",
        )
    
    async with get_db_session_context() as session:
        # Validate tenant exists
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_tenant(request_data.tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {request_data.tenant_id}",
            )
        
        # Validate pack
        validation_service = PackValidationService()
        
        # Try to get domain pack for cross-reference validation
        domain_pack = None
        if "domainName" in request_data.content:
            domain_name = request_data.content["domainName"]
            domain_pack_repo = DomainPackRepository(session)
            # Get latest domain pack for the domain
            domain_pack_latest = await domain_pack_repo.get_latest_version(domain_name)
            if domain_pack_latest:
                from src.models.domain_pack import DomainPack
                domain_pack = DomainPack.model_validate(domain_pack_latest.content_json)
        
        validation_result = validation_service.validate_tenant_pack(
            request_data.content, domain_pack
        )
        
        if not validation_result.is_valid:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "Pack validation failed",
                    "errors": validation_result.errors,
                    "warnings": validation_result.warnings,
                },
            )
        
        # Normalize version by stripping whitespace
        if not request_data.version:
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail="version is required for tenant pack import",
            )
        version = request_data.version.strip()
        tenant_id = request_data.tenant_id.strip() if request_data.tenant_id else request_data.tenant_id
        
        logger.info(f"Import request - tenant_id: '{tenant_id}', version: '{version}', overwrite: {request_data.overwrite}")
        
        # Import pack
        tenant_pack_repo = TenantPackRepository(session)
        
        try:
            # Check if pack already exists
            logger.info(f"Checking if tenant pack exists: tenant_id='{tenant_id}', version='{version}'")
            existing = await tenant_pack_repo.get_tenant_pack(tenant_id, version)
            
            if existing:
                logger.warning(
                    f"Tenant pack already exists: tenant_id='{tenant_id}', version='{version}', "
                    f"existing_id={existing.id}, existing_tenant_id='{existing.tenant_id}', existing_version='{existing.version}'"
                )
                if request_data.overwrite:
                    # Update existing pack
                    logger.info(f"Overwriting existing tenant pack with overwrite=true")
                    pack = await tenant_pack_repo.update_tenant_pack(
                        tenant_id=tenant_id,
                        version=version,
                        content_json=request_data.content,
                        updated_by=user_id,
                    )
                    
                    # Log audit event (P12-20) - do this BEFORE commit
                    try:
                        await _log_audit_event(
                            "tenant_pack_updated",
                            tenant_id,
                            user_id,
                            {
                                "tenant_id": tenant_id,
                                "version": version,
                                "pack_id": pack.id,
                            },
                            session,
                        )
                    except Exception as audit_error:
                        logger.error(f"Failed to create audit log for tenant pack update: {audit_error}", exc_info=True)
                        await session.rollback()
                        raise HTTPException(
                            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to update tenant pack: audit logging failed: {str(audit_error)}",
                        )
                    
                    # Commit only after both pack update and audit logging succeed
                    await session.commit()
                else:
                    await session.rollback()
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Tenant pack version already exists: tenant_id={tenant_id}, version={version}. "
                               f"Please use a different version number (e.g., v1.1, v2.0), set overwrite=true to update, or delete the existing pack first.",
                    )
            else:
                # Create new pack (skip existence check since we already verified it doesn't exist)
                logger.info(f"Creating new tenant pack: tenant_id='{tenant_id}', version='{version}'")
                pack = await tenant_pack_repo.create_tenant_pack(
                    tenant_id=tenant_id,
                    version=version,
                    content_json=request_data.content,
                    created_by=user_id,
                    skip_existence_check=True,  # We already checked above
                )
                logger.info(f"Successfully created tenant pack: id={pack.id}, tenant_id='{tenant_id}', version='{version}'")
                
                # Log audit event (P12-20) - do this BEFORE commit so if it fails, we rollback
                # This ensures atomicity: either both pack creation and audit log succeed, or both fail
                try:
                    await _log_audit_event(
                        "tenant_pack_imported",
                        tenant_id,
                        user_id,
                        {
                            "tenant_id": tenant_id,
                            "version": version,
                            "pack_id": pack.id,
                        },
                        session,
                    )
                except Exception as audit_error:
                    logger.error(f"Failed to create audit log for tenant pack import: {audit_error}", exc_info=True)
                    await session.rollback()
                    raise HTTPException(
                        status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Failed to import tenant pack: audit logging failed: {str(audit_error)}",
                    )
                
                # Commit only after both pack creation and audit logging succeed
                await session.commit()
            
            # Convert database model to response model with enum handling
            status_value = pack.status.value if isinstance(pack.status, PackStatus) else str(pack.status)
            # Extract domain from content_json for tenant packs (domain is stored in content, not as separate field)
            domain = None
            if pack.content_json and isinstance(pack.content_json, dict):
                domain = pack.content_json.get("domainName") or pack.content_json.get("domain")
            
            return PackResponse(
                id=pack.id,
                domain=domain,  # Extracted from content_json
                tenant_id=pack.tenant_id,  # Tenant packs have tenant_id
                version=pack.version,
                status=status_value,
                checksum=pack.checksum,
                created_at=pack.created_at,
                created_by=pack.created_by,
            )
        except HTTPException:
            # Re-raise HTTP exceptions (like the overwrite error)
            raise
        except ValueError as e:
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error(f"Error importing tenant pack: {e}", exc_info=True)
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to import tenant pack",
            )


@router.post("/packs/validate", response_model=PackValidationResponse)
async def validate_pack(
    request_data: PackValidateRequest,
    request: Request,
):
    """
    Validate a pack without importing (P12-11).
    
    POST /admin/packs/validate
    """
    require_admin_role(request)
    
    validation_service = PackValidationService()
    
    if request_data.pack_type == "domain":
        result = validation_service.validate_domain_pack(request_data.content)
    elif request_data.pack_type == "tenant":
        domain_pack = None
        if request_data.domain:
            async with get_db_session_context() as session:
                domain_pack_repo = DomainPackRepository(session)
                domain_pack_latest = await domain_pack_repo.get_latest_version(request_data.domain)
                if domain_pack_latest:
                    from src.models.domain_pack import DomainPack
                    domain_pack = DomainPack.model_validate(domain_pack_latest.content_json)
        
        result = validation_service.validate_tenant_pack(request_data.content, domain_pack)
    else:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid pack_type: {request_data.pack_type}. Must be 'domain' or 'tenant'",
        )
    
    return PackValidationResponse(
        is_valid=result.is_valid,
        errors=result.errors,
        warnings=result.warnings,
    )


# =============================================================================
# P12-12: Pack Listing & Version APIs
# =============================================================================


@router.get("/packs/domain", response_model=PaginatedPackResponse)
async def list_domain_packs(
    request: Request,
    domain: Optional[str] = Query(None, description="Filter by domain"),
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
    tenant_id: Optional[str] = Query(None, description="Tenant ID (ignored - domain packs are global)"),
):
    """
    List domain packs with pagination (P12-12).
    
    GET /admin/packs/domain
    
    Note: Domain packs are global and not tenant-specific. The tenant_id parameter
    is accepted for API compatibility but is ignored.
    """
    require_admin_role(request)
    
    try:
        async with get_db_session_context() as session:
            domain_pack_repo = DomainPackRepository(session)
            
            # Convert status string to enum
            status_filter = None
            if status:
                try:
                    status_filter = PackStatus(status)
                except ValueError:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid status: {status}. Valid values: {', '.join([s.value for s in PackStatus])}",
                    )
            
            packs = await domain_pack_repo.list_domain_packs(domain=domain, status=status_filter)
            
            # Apply pagination manually
            total = len(packs)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_packs = packs[start_idx:end_idx]
            
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            
            # Convert database models to response models
            # Pydantic's from_attributes should handle enum conversion, but we'll be explicit
            items = []
            for p in paginated_packs:
                # Convert PackStatus enum to string value
                status_value = p.status.value if isinstance(p.status, PackStatus) else str(p.status)
                pack_dict = {
                    "id": p.id,
                    "domain": p.domain,
                    "tenant_id": None,  # Domain packs don't have tenant_id
                    "version": p.version,
                    "status": status_value,
                    "checksum": p.checksum,
                    "created_at": p.created_at,
                    "created_by": p.created_by,
                }
                items.append(PackResponse(**pack_dict))
            
            return PaginatedPackResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
    except HTTPException:
        # Re-raise HTTP exceptions (like 400 Bad Request) as-is
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(
            f"Error listing domain packs: {error_type}: {error_msg}",
            exc_info=True
        )
        # Check if it's a database table missing error
        error_str = error_msg.lower()
        if "does not exist" in error_str or "relation" in error_str or "table" in error_str or "no such table" in error_str:
            logger.error(
                "Database table 'domain_packs' not found. "
                "This usually means migrations haven't been run. "
                "Please run: alembic upgrade head"
            )
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database tables not found. Please run migrations: alembic upgrade head",
            )
        # For other errors, return 500 with error details
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list domain packs: {error_type}: {error_msg}",
        )


@router.get("/packs/domain/{domain}/{version}", response_model=PackResponse)
async def get_domain_pack(
    domain: str,
    version: str,
    request: Request,
):
    """
    Get domain pack by domain and version (P12-12).
    
    GET /admin/packs/domain/{domain}/{version}
    """
    require_admin_role(request)
    
    async with get_db_session_context() as session:
        domain_pack_repo = DomainPackRepository(session)
        pack = await domain_pack_repo.get_domain_pack(domain, version)
        
        if not pack:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Domain pack not found: domain={domain}, version={version}",
            )
        
        # Convert database model to response model with enum handling
        status_value = pack.status.value if isinstance(pack.status, PackStatus) else str(pack.status)
        return PackResponse(
            id=pack.id,
            domain=pack.domain,
            tenant_id=None,  # Domain packs don't have tenant_id
            version=pack.version,
            status=status_value,
            checksum=pack.checksum,
            created_at=pack.created_at,
            created_by=pack.created_by,
            content_json=pack.content_json,
        )


@router.get("/packs/tenant/{tenant_id}", response_model=PaginatedPackResponse)
async def list_tenant_packs(
    tenant_id: str,
    request: Request,
    status: Optional[str] = Query(None, description="Filter by status"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Page size"),
):
    """
    List tenant packs for a tenant (P12-12).
    
    GET /admin/packs/tenant/{tenant_id}
    """
    require_admin_role(request)
    
    try:
        async with get_db_session_context() as session:
            # Validate tenant exists
            tenant_repo = TenantRepository(session)
            tenant = await tenant_repo.get_tenant(tenant_id)
            if not tenant:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Tenant not found: {tenant_id}",
                )
            
            tenant_pack_repo = TenantPackRepository(session)
            
            # Convert status string to enum
            status_filter = None
            if status:
                try:
                    status_filter = PackStatus(status)
                except ValueError:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid status: {status}",
                    )
            
            packs = await tenant_pack_repo.list_tenant_packs(tenant_id=tenant_id, status=status_filter)
            
            # Apply pagination manually
            total = len(packs)
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_packs = packs[start_idx:end_idx]
            
            total_pages = (total + page_size - 1) // page_size if total > 0 else 0
            
            # Convert database models to response models with enum handling
            items = []
            for p in paginated_packs:
                status_value = p.status.value if isinstance(p.status, PackStatus) else str(p.status)
                # Extract domain from content_json for tenant packs (domain is stored in content, not as separate field)
                domain = None
                if p.content_json and isinstance(p.content_json, dict):
                    domain = p.content_json.get("domainName") or p.content_json.get("domain")
                
                items.append(PackResponse(
                    id=p.id,
                    domain=domain,  # Extracted from content_json
                    tenant_id=p.tenant_id,  # Tenant packs have tenant_id
                    version=p.version,
                    status=status_value,
                    checksum=p.checksum,
                    created_at=p.created_at,
                    created_by=p.created_by,
                ))
            
            return PaginatedPackResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
    except HTTPException:
        # Re-raise HTTP exceptions (like 400 Bad Request) as-is
        raise
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logger.error(
            f"Error listing tenant packs: {error_type}: {error_msg}",
            exc_info=True
        )
        # Check if it's a database table missing error
        error_str = error_msg.lower()
        if "does not exist" in error_str or "relation" in error_str or "table" in error_str or "no such table" in error_str:
            logger.error(
                "Database table 'tenant_packs' not found. "
                "This usually means migrations haven't been run. "
                "Please run: alembic upgrade head"
            )
            raise HTTPException(
                status_code=http_status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database tables not found. Please run migrations: alembic upgrade head",
            )
        # For other errors, return 500 with error details
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list tenant packs: {error_type}: {error_msg}",
        )


@router.get("/packs/tenant/{tenant_id}/{version}", response_model=PackResponse)
async def get_tenant_pack(
    tenant_id: str,
    version: str,
    request: Request,
):
    """
    Get tenant pack by tenant and version (P12-12).
    
    GET /admin/packs/tenant/{tenant_id}/{version}
    """
    require_admin_role(request)
    
    async with get_db_session_context() as session:
        tenant_pack_repo = TenantPackRepository(session)
        pack = await tenant_pack_repo.get_tenant_pack(tenant_id, version)
        
        if not pack:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Tenant pack not found: tenant_id={tenant_id}, version={version}",
            )
        
        # Convert database model to response model with enum handling
        status_value = pack.status.value if isinstance(pack.status, PackStatus) else str(pack.status)
        # Extract domain from content_json for tenant packs (domain is stored in content, not as separate field)
        domain = None
        if pack.content_json and isinstance(pack.content_json, dict):
            domain = pack.content_json.get("domainName") or pack.content_json.get("domain")
        
        return PackResponse(
            id=pack.id,
            domain=domain,  # Extracted from content_json
            tenant_id=pack.tenant_id,  # Tenant packs have tenant_id
            version=pack.version,
            status=status_value,
            checksum=pack.checksum,
            created_at=pack.created_at,
            created_by=pack.created_by,
            content_json=pack.content_json,
        )


# =============================================================================
# P12-13: Pack Activation API
# =============================================================================


@router.post("/packs/activate", response_model=PackActivateResponse)
async def activate_packs(
    request_data: PackActivateRequest,
    request: Request,
):
    """
    Activate pack configuration for a tenant (P12-13).
    
    Validates pack versions exist and optionally creates config change request
    if approval workflow is enabled (P12-21).
    
    POST /admin/packs/activate
    """
    require_admin_role(request)
    user_id = get_user_id(request)
    
    async with get_db_session_context() as session:
        # Validate tenant exists
        tenant_repo = TenantRepository(session)
        tenant = await tenant_repo.get_tenant(request_data.tenant_id)
        if not tenant:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Tenant not found: {request_data.tenant_id}",
            )
        
        # Validate pack versions exist
        domain_pack_repo = DomainPackRepository(session)
        tenant_pack_repo = TenantPackRepository(session)
        
        # Validate domain pack version exists if provided
        domain_pack_validated = None
        domain_name = None
        if request_data.domain_pack_version:
            # Require domain name for domain pack activation
            if not request_data.domain:
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail="domain is required when activating a domain pack",
                )
            
            # Normalize domain name
            domain_name = request_data.domain.strip() if request_data.domain else None
            
            # Find domain pack by domain + version
            domain_pack_validated = await domain_pack_repo.get_domain_pack(
                domain=domain_name,
                version=request_data.domain_pack_version,
            )
            if not domain_pack_validated:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Domain pack not found: domain={domain_name}, version={request_data.domain_pack_version}",
                )
            
            # Validate pack status is ACTIVE or DRAFT
            if domain_pack_validated.status not in (PackStatus.ACTIVE, PackStatus.DRAFT):
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Domain pack version {request_data.domain_pack_version} has status {domain_pack_validated.status.value}, cannot activate",
                )
        
        tenant_pack_validated = None
        if request_data.tenant_pack_version:
            tenant_pack_validated = await tenant_pack_repo.get_tenant_pack(
                request_data.tenant_id, request_data.tenant_pack_version
            )
            if not tenant_pack_validated:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Tenant pack version not found: tenant_id={request_data.tenant_id}, version={request_data.tenant_pack_version}",
                )
            
            # Validate pack status is ACTIVE or DRAFT
            if tenant_pack_validated.status not in (PackStatus.ACTIVE, PackStatus.DRAFT):
                raise HTTPException(
                    status_code=http_status.HTTP_400_BAD_REQUEST,
                    detail=f"Tenant pack version {request_data.tenant_pack_version} has status {tenant_pack_validated.status.value}, cannot activate",
                )
            
            # Validate compatibility: tenant pack domain must match domain pack domain
            if domain_pack_validated and domain_name:
                tenant_pack_domain = tenant_pack_validated.content_json.get("domainName")
                if tenant_pack_domain and tenant_pack_domain != domain_name:
                    raise HTTPException(
                        status_code=http_status.HTTP_400_BAD_REQUEST,
                        detail=f"Tenant pack domain '{tenant_pack_domain}' does not match domain pack domain '{domain_name}'",
                    )
        
        # Get current active config
        active_config_repo = TenantActiveConfigRepository(session)
        current_config = await active_config_repo.get_active_config(request_data.tenant_id)
        
        # P12-21: Optional approval workflow
        change_request_id = None
        if request_data.require_approval:
            config_change_repo = ConfigChangeRepository(session)
            
            # Build proposed config
            proposed_config = {
                "domain_pack_version": request_data.domain_pack_version,
                "tenant_pack_version": request_data.tenant_pack_version,
            }
            
            # Build current config
            current_config_dict = None
            if current_config:
                current_config_dict = {
                    "domain_pack_version": current_config.active_domain_pack_version,
                    "tenant_pack_version": current_config.active_tenant_pack_version,
                }
            
            # Create config change request
            change_request = await config_change_repo.create_change_request(
                tenant_id=request_data.tenant_id,
                change_type=ConfigChangeType.TENANT_POLICY.value,
                resource_id=request_data.tenant_id,
                proposed_config=proposed_config,
                requested_by=user_id,
                resource_name=f"Active config for {request_data.tenant_id}",
                current_config=current_config_dict,
                diff_summary=f"Activate domain_pack={request_data.domain_pack_version}, tenant_pack={request_data.tenant_pack_version}",
                change_reason="Pack activation requested",
            )
            await session.commit()
            
            change_request_id = change_request.id
            
            # Log audit event (P12-20)
            await _log_audit_event(
                "pack_activation_requested",
                request_data.tenant_id,
                user_id,
                {
                    "domain_pack_version": request_data.domain_pack_version,
                    "tenant_pack_version": request_data.tenant_pack_version,
                    "change_request_id": change_request_id,
                },
                session,
            )
            
            return PackActivateResponse(
                tenant_id=request_data.tenant_id,
                active_domain_pack_version=current_config.active_domain_pack_version if current_config else None,
                active_tenant_pack_version=current_config.active_tenant_pack_version if current_config else None,
                activated_at=datetime.now(timezone.utc),
                activated_by=user_id,
                change_request_id=change_request_id,
            )
        
        # Direct activation (no approval required)
        try:
            # Update pack statuses to ACTIVE if they are currently DRAFT
            if domain_pack_validated:
                # Handle both enum and string status values
                current_status = domain_pack_validated.status
                status_value = current_status.value if hasattr(current_status, 'value') else str(current_status)
                logger.info(f"Domain pack status before update: id={domain_pack_validated.id}, domain={domain_pack_validated.domain}, version={domain_pack_validated.version}, status={status_value}")
                
                # Compare status (handle both enum and string)
                is_draft = (
                    current_status == PackStatus.DRAFT or 
                    status_value == PackStatus.DRAFT.value or
                    status_value == "draft"
                )
                
                if is_draft:
                    updated_pack = await domain_pack_repo.update_pack_status(
                        pack_id=domain_pack_validated.id,
                        status=PackStatus.ACTIVE,
                    )
                    updated_status_value = updated_pack.status.value if hasattr(updated_pack.status, 'value') else str(updated_pack.status)
                    logger.info(f"Updated domain pack status to ACTIVE: id={updated_pack.id}, domain={updated_pack.domain}, version={updated_pack.version}, status={updated_status_value}")
                    # Refresh the validated pack with updated status
                    domain_pack_validated = updated_pack
                else:
                    logger.info(f"Domain pack status is already {status_value}, skipping status update")
            
            if tenant_pack_validated:
                # Handle both enum and string status values
                current_status = tenant_pack_validated.status
                status_value = current_status.value if hasattr(current_status, 'value') else str(current_status)
                logger.info(f"Tenant pack status before update: id={tenant_pack_validated.id}, tenant_id={tenant_pack_validated.tenant_id}, version={tenant_pack_validated.version}, status={status_value}")
                
                # Compare status (handle both enum and string)
                is_draft = (
                    current_status == PackStatus.DRAFT or 
                    status_value == PackStatus.DRAFT.value or
                    status_value == "draft"
                )
                
                if is_draft:
                    updated_pack = await tenant_pack_repo.update_pack_status(
                        pack_id=tenant_pack_validated.id,
                        status=PackStatus.ACTIVE,
                    )
                    updated_status_value = updated_pack.status.value if hasattr(updated_pack.status, 'value') else str(updated_pack.status)
                    logger.info(f"Updated tenant pack status to ACTIVE: id={updated_pack.id}, tenant_id={updated_pack.tenant_id}, version={updated_pack.version}, status={updated_status_value}")
                    # Refresh the validated pack with updated status
                    tenant_pack_validated = updated_pack
                else:
                    logger.info(f"Tenant pack status is already {status_value}, skipping status update")
            
            active_config = await active_config_repo.activate_config(
                tenant_id=request_data.tenant_id,
                domain_pack_version=request_data.domain_pack_version,
                tenant_pack_version=request_data.tenant_pack_version,
                activated_by=user_id,
            )
            
            # Log audit event (P12-20) before commit for atomicity
            await _log_audit_event(
                "pack_activated",
                request_data.tenant_id,
                user_id,
                {
                    "domain_pack_version": request_data.domain_pack_version,
                    "tenant_pack_version": request_data.tenant_pack_version,
                },
                session,
            )
            
            await session.commit()
            
            return PackActivateResponse(
                tenant_id=active_config.tenant_id,
                active_domain_pack_version=active_config.active_domain_pack_version,
                active_tenant_pack_version=active_config.active_tenant_pack_version,
                activated_at=active_config.activated_at,
                activated_by=active_config.activated_by,
                change_request_id=None,
            )
        except ValueError as e:
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )
        except Exception as e:
            logger.error(f"Error activating packs: {e}", exc_info=True)
            await session.rollback()
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to activate packs",
            )


@router.get("/tenants/{tenant_id}/active-config", response_model=Optional[ActiveConfigResponse])
async def get_active_config(
    tenant_id: str,
    request: Request,
):
    """
    Get active configuration for a tenant.
    
    Returns None if no active configuration is set (200 OK with null response).
    
    GET /admin/tenants/{tenant_id}/active-config
    """
    require_admin_role(request)
    
    async with get_db_session_context() as session:
        active_config_repo = TenantActiveConfigRepository(session)
        config = await active_config_repo.get_active_config(tenant_id)
        
        if not config:
            return None
        
        return ActiveConfigResponse.model_validate(config)


@router.get("/playbooks/registry", response_model=PlaybookRegistryResponse)
async def get_playbooks_registry(
    request: Request,
    tenant_id: Optional[str] = Query(None, description="Filter by tenant ID"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
    exception_type: Optional[str] = Query(None, description="Filter by exception type"),
    source: Optional[str] = Query(None, description="Filter by source: domain or tenant"),
    search: Optional[str] = Query(None, description="Search by name or playbook ID"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(25, ge=1, le=100, description="Page size"),
):
    """
    Get playbooks registry from active domain and tenant packs.
    
    This endpoint aggregates playbooks from ACTIVE domain and tenant packs,
    applying override logic where tenant playbooks take precedence over domain playbooks.
    
    GET /admin/playbooks/registry
    """
    require_admin_role(request)
    
    try:
        async with get_db_session_context() as session:
            domain_pack_repo = DomainPackRepository(session)
            tenant_pack_repo = TenantPackRepository(session)
            
            # Get active domain packs
            domain_packs = await domain_pack_repo.list_domain_packs(
                domain=domain if domain else None,
                status=PackStatus.ACTIVE
            )
            
            # Get active tenant packs (only if tenant_id is specified)
            tenant_packs = []
            if tenant_id:
                tenant_packs = await tenant_pack_repo.list_tenant_packs(
                    tenant_id=tenant_id,
                    status=PackStatus.ACTIVE
                )
            
            registry_entries = []
            playbook_overrides = {}  # track tenant overrides: playbook_id -> tenant_entry
            
            # Process tenant packs first (they take precedence)
            for tenant_pack in tenant_packs:
                if tenant_pack.content_json:
                    try:
                        import json
                        content = json.loads(tenant_pack.content_json) if isinstance(tenant_pack.content_json, str) else tenant_pack.content_json
                        playbooks = content.get('playbooks', [])
                        
                        for idx, playbook in enumerate(playbooks):
                            # Skip if playbook is not a dict (malformed data)
                            if not isinstance(playbook, dict):
                                logger.warning(f"Skipping malformed playbook entry (not a dict) in tenant pack {tenant_pack.id}")
                                continue
                            
                            # Handle various playbook ID fields
                            exception_type_val = playbook.get('exceptionType') or playbook.get('exception_type') or playbook.get('applies_to') or f'UNKNOWN_{idx}'
                            playbook_id = playbook.get('playbook_id') or playbook.get('id') or f'{content.get("domainName", "unknown")}.{exception_type_val.lower()}'
                            name = playbook.get('name') or playbook.get('title') or f'Playbook for {exception_type_val}'
                                
                            # Check filters
                            if exception_type and exception_type_val != exception_type:
                                continue
                            if source and source != 'tenant':
                                continue
                            if search and search.lower() not in name.lower() and search.lower() not in playbook_id.lower():
                                continue
                                
                            # Count steps and tool refs - ensure steps is a list of dicts
                            steps = playbook.get('steps', [])
                            if not isinstance(steps, list):
                                steps = []
                            steps_count = len(steps)
                            tool_refs_count = len([step for step in steps if isinstance(step, dict) and (step.get('tool') or step.get('tool_id') or step.get('tool_ref'))])
                            
                            entry = PlaybookRegistryEntry(
                                playbook_id=playbook_id,
                                name=name,
                                description=playbook.get('description') or f'Automated playbook for {exception_type_val}',
                                exception_type=exception_type_val,
                                domain=tenant_pack.tenant_id,  # Use tenant_id as domain for tenant packs
                                version=tenant_pack.version,
                                status='active',
                                source_pack_type='tenant',
                                source_pack_id=tenant_pack.id,
                                source_pack_version=tenant_pack.version,
                                steps_count=steps_count,
                                tool_refs_count=tool_refs_count,
                                overridden=False,
                                overridden_from=None
                            )
                            
                            registry_entries.append(entry)
                            playbook_overrides[playbook_id] = entry
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse tenant pack {tenant_pack.id}: {e}")
                        continue
            
            # Process domain packs (add non-overridden playbooks)
            for domain_pack in domain_packs:
                if domain_pack.content_json:
                    try:
                        import json
                        content = json.loads(domain_pack.content_json) if isinstance(domain_pack.content_json, str) else domain_pack.content_json
                        playbooks = content.get('playbooks', [])
                        
                        for idx, playbook in enumerate(playbooks):
                            # Skip if playbook is not a dict (malformed data)
                            if not isinstance(playbook, dict):
                                logger.warning(f"Skipping malformed playbook entry (not a dict) in domain pack {domain_pack.id}")
                                continue
                            
                            # Handle various playbook ID fields
                            exception_type_val = playbook.get('exceptionType') or playbook.get('exception_type') or playbook.get('applies_to') or f'UNKNOWN_{idx}'
                            playbook_id = playbook.get('playbook_id') or playbook.get('id') or f'{domain_pack.domain}.{exception_type_val.lower()}'
                            name = playbook.get('name') or playbook.get('title') or f'Playbook for {exception_type_val}'
                                
                            # Check if overridden by tenant pack
                            if playbook_id in playbook_overrides:
                                # Mark the tenant entry as overriding
                                playbook_overrides[playbook_id].overridden_from = f"domain:{domain_pack.domain}:{domain_pack.version}"
                                continue
                                
                            # Check filters
                            if exception_type and exception_type_val != exception_type:
                                continue
                            if source and source != 'domain':
                                continue
                            if search and search.lower() not in name.lower() and search.lower() not in playbook_id.lower():
                                continue
                                
                            # Count steps and tool refs - ensure steps is a list of dicts
                            steps = playbook.get('steps', [])
                            if not isinstance(steps, list):
                                steps = []
                            steps_count = len(steps)
                            tool_refs_count = len([step for step in steps if isinstance(step, dict) and (step.get('tool') or step.get('tool_id') or step.get('tool_ref'))])
                            
                            entry = PlaybookRegistryEntry(
                                playbook_id=playbook_id,
                                name=name,
                                description=playbook.get('description') or f'Automated playbook for {exception_type_val}',
                                exception_type=exception_type_val,
                                domain=domain_pack.domain,
                                version=domain_pack.version,
                                status='active',
                                source_pack_type='domain',
                                source_pack_id=domain_pack.id,
                                source_pack_version=domain_pack.version,
                                steps_count=steps_count,
                                tool_refs_count=tool_refs_count,
                                overridden=False,
                                overridden_from=None
                            )
                            
                            registry_entries.append(entry)
                    except (json.JSONDecodeError, KeyError) as e:
                        logger.warning(f"Failed to parse domain pack {domain_pack.id}: {e}")
                        continue
            
            # Apply pagination
            total = len(registry_entries)
            offset = (page - 1) * page_size
            paginated_entries = registry_entries[offset:offset + page_size]
            total_pages = (total + page_size - 1) // page_size
            
            return PlaybookRegistryResponse(
                items=paginated_entries,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages
            )
            
    except Exception as e:
        logger.error(f"Error fetching playbooks registry: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch playbooks registry: {str(e)}",
        )

