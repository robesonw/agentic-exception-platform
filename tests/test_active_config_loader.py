"""
Unit tests for Phase 12 active config loader.

Tests:
- ActiveConfigLoader.load_domain_pack
- ActiveConfigLoader.load_tenant_pack
- Cache functionality
- Backward compatibility with file-based packs
"""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.repositories.active_config_loader import ActiveConfigLoader
from src.infrastructure.repositories.onboarding_domain_pack_repository import DomainPackRepository
from src.infrastructure.repositories.onboarding_tenant_pack_repository import TenantPackRepository
from src.infrastructure.repositories.tenant_active_config_repository import (
    TenantActiveConfigRepository,
)
from src.infrastructure.repositories.tenant_repository import TenantRepository


@pytest.mark.asyncio
async def test_load_domain_pack_from_database(session: AsyncSession):
    """Test loading domain pack from database."""
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
        "exceptionTypes": {
            "Test": {
                "description": "Test exception",
                "detectionRules": [],
            }
        },
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
    
    # Activate config
    config_repo = TenantActiveConfigRepository(session)
    await config_repo.activate_config(
        tenant_id="TENANT_001",
        domain_pack_version="v1.0",
        tenant_pack_version=None,
        activated_by="admin@example.com",
    )
    
    # Load domain pack
    loader = ActiveConfigLoader(session)
    domain_pack = await loader.load_domain_pack("TENANT_001")
    
    assert domain_pack is not None
    assert domain_pack.domain_name == "Finance"


@pytest.mark.asyncio
async def test_load_tenant_pack_from_database(session: AsyncSession):
    """Test loading tenant pack from database."""
    # Create tenant
    tenant_repo = TenantRepository(session)
    await tenant_repo.create_tenant(
        tenant_id="TENANT_001",
        name="Test Tenant",
        created_by="admin@example.com",
    )
    
    # Create tenant pack
    tenant_pack_repo = TenantPackRepository(session)
    pack_data = {
        "tenantId": "TENANT_001",
        "domainName": "Finance",
        "approvedTools": [],
        "customPlaybooks": [],
        "customSeverityOverrides": [],
    }
    await tenant_pack_repo.create_tenant_pack(
        tenant_id="TENANT_001",
        version="v1.0",
        content_json=pack_data,
        created_by="admin@example.com",
    )
    
    # Activate config
    config_repo = TenantActiveConfigRepository(session)
    await config_repo.activate_config(
        tenant_id="TENANT_001",
        domain_pack_version=None,
        tenant_pack_version="v1.0",
        activated_by="admin@example.com",
    )
    
    # Load tenant pack
    loader = ActiveConfigLoader(session)
    tenant_pack = await loader.load_tenant_pack("TENANT_001")
    
    assert tenant_pack is not None
    assert tenant_pack.tenant_id == "TENANT_001"
    assert tenant_pack.domain_name == "Finance"


@pytest.mark.asyncio
async def test_cache_functionality(session: AsyncSession):
    """Test that cache works correctly."""
    # Create tenant and pack
    tenant_repo = TenantRepository(session)
    await tenant_repo.create_tenant(
        tenant_id="TENANT_001",
        name="Test Tenant",
        created_by="admin@example.com",
    )
    
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
    
    config_repo = TenantActiveConfigRepository(session)
    await config_repo.activate_config(
        tenant_id="TENANT_001",
        domain_pack_version="v1.0",
        tenant_pack_version=None,
        activated_by="admin@example.com",
    )
    
    # Load twice - second should use cache
    loader = ActiveConfigLoader(session)
    pack1 = await loader.load_domain_pack("TENANT_001")
    pack2 = await loader.load_domain_pack("TENANT_001")
    
    assert pack1 is not None
    assert pack2 is not None
    assert pack1.domain_name == pack2.domain_name
    
    # Clear cache and verify it reloads
    loader.clear_cache("TENANT_001")
    pack3 = await loader.load_domain_pack("TENANT_001")
    
    assert pack3 is not None
    assert pack3.domain_name == "Finance"

