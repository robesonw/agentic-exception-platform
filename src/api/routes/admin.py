"""
Admin API routes for tenant and pack management.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/tenants", tags=["admin"])


@router.post("/{tenant_id}/packs/domain")
async def upload_domain_pack(tenant_id: str):
    """
    Upload Domain Pack for tenant.
    POST /tenants/{tenantId}/packs/domain
    """
    # TODO: Implement domain pack upload
    pass


@router.post("/{tenant_id}/packs/policy")
async def upload_policy_pack(tenant_id: str):
    """
    Upload Tenant Policy Pack.
    POST /tenants/{tenantId}/packs/policy
    """
    # TODO: Implement policy pack upload
    pass

