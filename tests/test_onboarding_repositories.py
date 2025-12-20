"""
Unit tests for Phase 12 repositories.

Tests:
- DomainPackRepository
- TenantPackRepository
- TenantActiveConfigRepository
- TenantRepository (create_tenant method)
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import DomainPack, PackStatus, Tenant, TenantActiveConfig, TenantPack
from src.infrastructure.repositories.onboarding_domain_pack_repository import DomainPackRepository
from src.infrastructure.repositories.onboarding_tenant_pack_repository import TenantPackRepository
from src.infrastructure.repositories.tenant_active_config_repository import (
    TenantActiveConfigRepository,
)
from src.infrastructure.repositories.tenant_repository import TenantRepository


@pytest.mark.asyncio
async def test_domain_pack_repository_create(session: AsyncSession):
    """Test creating a domain pack."""
    repo = DomainPackRepository(session)
    
    pack_data = {
        "domainName": "Finance",
        "exceptionTypes": {
            "DataQualityFailure": {
                "description": "Data quality issue",
                "detectionRules": ["rule1"],
            }
        },
        "severityRules": [],
        "tools": {},
        "playbooks": [],
        "guardrails": {},
    }
    
    pack = await repo.create_domain_pack(
        domain="Finance",
        version="v1.0",
        content_json=pack_data,
        created_by="admin@example.com",
    )
    
    assert pack.domain == "Finance"
    assert pack.version == "v1.0"
    assert pack.status == PackStatus.DRAFT
    assert pack.created_by == "admin@example.com"
    assert pack.checksum is not None


@pytest.mark.asyncio
async def test_domain_pack_repository_get(session: AsyncSession):
    """Test getting a domain pack."""
    repo = DomainPackRepository(session)
    
    pack_data = {
        "domainName": "Finance",
        "exceptionTypes": {"Test": {"description": "Test", "detectionRules": []}},
        "severityRules": [],
        "tools": {},
        "playbooks": [],
        "guardrails": {},
    }
    
    created = await repo.create_domain_pack(
        domain="Finance",
        version="v1.0",
        content_json=pack_data,
        created_by="admin@example.com",
    )
    
    retrieved = await repo.get_domain_pack("Finance", "v1.0")
    
    assert retrieved is not None
    assert retrieved.id == created.id
    assert retrieved.domain == "Finance"
    assert retrieved.version == "v1.0"


@pytest.mark.asyncio
async def test_tenant_pack_repository_create(session: AsyncSession):
    """Test creating a tenant pack."""
    # First create a tenant
    tenant_repo = TenantRepository(session)
    tenant = await tenant_repo.create_tenant(
        tenant_id="TENANT_001",
        name="Test Tenant",
        created_by="admin@example.com",
    )
    
    repo = TenantPackRepository(session)
    
    pack_data = {
        "tenantId": "TENANT_001",
        "domainName": "Finance",
        "approvedTools": [],
        "customPlaybooks": [],
        "customSeverityOverrides": [],
    }
    
    pack = await repo.create_tenant_pack(
        tenant_id="TENANT_001",
        version="v1.0",
        content_json=pack_data,
        created_by="admin@example.com",
    )
    
    assert pack.tenant_id == "TENANT_001"
    assert pack.version == "v1.0"
    assert pack.status == PackStatus.DRAFT
    assert pack.created_by == "admin@example.com"
    assert pack.checksum is not None


@pytest.mark.asyncio
async def test_tenant_active_config_repository_activate(session: AsyncSession):
    """Test activating configuration."""
    # Create tenant
    tenant_repo = TenantRepository(session)
    await tenant_repo.create_tenant(
        tenant_id="TENANT_001",
        name="Test Tenant",
        created_by="admin@example.com",
    )
    
    # Create domain pack
    domain_repo = DomainPackRepository(session)
    pack_data = {
        "domainName": "Finance",
        "exceptionTypes": {"Test": {"description": "Test", "detectionRules": []}},
        "severityRules": [],
        "tools": {},
        "playbooks": [],
        "guardrails": {},
    }
    await domain_repo.create_domain_pack(
        domain="Finance",
        version="v1.0",
        content_json=pack_data,
        created_by="admin@example.com",
    )
    
    # Create tenant pack
    tenant_pack_repo = TenantPackRepository(session)
    tenant_pack_data = {
        "tenantId": "TENANT_001",
        "domainName": "Finance",
        "approvedTools": [],
        "customPlaybooks": [],
        "customSeverityOverrides": [],
    }
    await tenant_pack_repo.create_tenant_pack(
        tenant_id="TENANT_001",
        version="v1.0",
        content_json=tenant_pack_data,
        created_by="admin@example.com",
    )
    
    # Activate config
    config_repo = TenantActiveConfigRepository(session)
    config = await config_repo.activate_config(
        tenant_id="TENANT_001",
        domain_pack_version="v1.0",
        tenant_pack_version="v1.0",
        activated_by="admin@example.com",
    )
    
    assert config.tenant_id == "TENANT_001"
    assert config.active_domain_pack_version == "v1.0"
    assert config.active_tenant_pack_version == "v1.0"
    assert config.activated_by == "admin@example.com"


@pytest.mark.asyncio
async def test_tenant_repository_create(session: AsyncSession):
    """Test creating a tenant."""
    repo = TenantRepository(session)
    
    tenant = await repo.create_tenant(
        tenant_id="TENANT_001",
        name="Test Tenant",
        created_by="admin@example.com",
    )
    
    assert tenant.tenant_id == "TENANT_001"
    assert tenant.name == "Test Tenant"
    assert tenant.created_by == "admin@example.com"
    assert tenant.status.value == "active"

