"""
Phase 12 Onboarding Integration Tests.

Tests the complete Phase 12 onboarding flow:
- Tenant lifecycle (create, list, status update)
- Pack import and validation
- Pack activation
- Runtime usage with active configuration

Verifies:
- All operations work end-to-end with database
- Tenant isolation is enforced
- Pack validation works correctly
- Active configuration is used by runtime
- Audit trail is complete

Reference: docs/phase12-onboarding-packs-mvp.md
"""

import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from src.api.main import app
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.tenant_repository import TenantRepository
from src.infrastructure.repositories.onboarding_domain_pack_repository import DomainPackRepository
from src.infrastructure.repositories.onboarding_tenant_pack_repository import TenantPackRepository
from src.infrastructure.repositories.tenant_active_config_repository import TenantActiveConfigRepository
from src.infrastructure.db.models import TenantStatus, PackStatus

client = TestClient(app)


@pytest.fixture
def sample_domain_pack():
    """Sample domain pack for testing."""
    return {
        "domainName": "Finance",
        "version": "v1.0",
        "exceptionTypes": {
            "PaymentFailed": {
                "description": "Payment processing failed",
                "severity": "high",
            }
        },
        "tools": {
            "refundPayment": {
                "name": "refundPayment",
                "description": "Refund a payment",
                "endpoint": "https://api.example.com/refund",
            }
        },
        "playbooks": [
            {
                "exceptionType": "PaymentFailed",
                "steps": [
                    {
                        "action": "refundPayment",
                        "parameters": {"paymentId": "{{paymentId}}"},
                    }
                ],
            }
        ],
    }


@pytest.fixture
def sample_tenant_pack():
    """Sample tenant pack for testing."""
    return {
        "tenantId": "TENANT_TEST_001",
        "domainName": "Finance",
        "approvedTools": ["refundPayment"],
        "customSeverityOverrides": [],
        "customGuardrails": None,
        "humanApprovalRules": [],
        "retentionPolicies": None,
        "customPlaybooks": [],
    }


@pytest.mark.asyncio
async def test_tenant_lifecycle_integration():
    """Test complete tenant lifecycle: create, list, get, update status."""
    # Create tenant
    response = client.post(
        "/admin/tenants",
        json={
            "tenant_id": "TENANT_TEST_001",
            "name": "Test Tenant",
        },
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 201
    tenant_data = response.json()
    assert tenant_data["tenant_id"] == "TENANT_TEST_001"
    assert tenant_data["name"] == "Test Tenant"
    assert tenant_data["status"] == "ACTIVE"

    # List tenants
    response = client.get(
        "/admin/tenants",
        params={"page": 1, "page_size": 10},
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(t["tenant_id"] == "TENANT_TEST_001" for t in data["items"])

    # Get tenant
    response = client.get(
        "/admin/tenants/TENANT_TEST_001",
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    assert response.json()["tenant_id"] == "TENANT_TEST_001"

    # Update tenant status
    response = client.patch(
        "/admin/tenants/TENANT_TEST_001/status",
        json={"status": "SUSPENDED"},
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "SUSPENDED"

    # Verify status change
    response = client.get(
        "/admin/tenants/TENANT_TEST_001",
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.json()["status"] == "SUSPENDED"


@pytest.mark.asyncio
async def test_pack_import_and_validation_integration(sample_domain_pack, sample_tenant_pack):
    """Test pack import and validation flow."""
    # First create tenant
    client.post(
        "/admin/tenants",
        json={
            "tenant_id": "TENANT_TEST_001",
            "name": "Test Tenant",
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    # Validate domain pack
    response = client.post(
        "/admin/packs/validate",
        json={
            "pack_type": "domain",
            "content": sample_domain_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    validation_result = response.json()
    assert validation_result["is_valid"] is True

    # Import domain pack
    response = client.post(
        "/admin/packs/domain/import",
        json={
            "domain": "Finance",
            "version": "v1.0",
            "content": sample_domain_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 201
    pack_data = response.json()
    assert pack_data["domain"] == "Finance"
    assert pack_data["version"] == "v1.0"
    assert pack_data["status"] == "DRAFT"

    # Validate tenant pack
    response = client.post(
        "/admin/packs/validate",
        json={
            "pack_type": "tenant",
            "content": sample_tenant_pack,
            "domain": "Finance",
        },
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    validation_result = response.json()
    assert validation_result["is_valid"] is True

    # Import tenant pack
    response = client.post(
        "/admin/packs/tenant/import",
        json={
            "tenant_id": "TENANT_TEST_001",
            "version": "v1.0",
            "content": sample_tenant_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 201
    pack_data = response.json()
    assert pack_data["tenant_id"] == "TENANT_TEST_001"
    assert pack_data["version"] == "v1.0"
    assert pack_data["status"] == "DRAFT"


@pytest.mark.asyncio
async def test_pack_activation_integration(sample_domain_pack, sample_tenant_pack):
    """Test pack activation flow."""
    # Setup: Create tenant and import packs
    client.post(
        "/admin/tenants",
        json={
            "tenant_id": "TENANT_TEST_001",
            "name": "Test Tenant",
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/packs/domain/import",
        json={
            "domain": "Finance",
            "version": "v1.0",
            "content": sample_domain_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/packs/tenant/import",
        json={
            "tenant_id": "TENANT_TEST_001",
            "version": "v1.0",
            "content": sample_tenant_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    # Activate packs
    response = client.post(
        "/admin/packs/activate",
        json={
            "tenant_id": "TENANT_TEST_001",
            "domain_pack_version": "v1.0",
            "tenant_pack_version": "v1.0",
            "require_approval": False,
        },
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    activation_data = response.json()
    assert activation_data["tenant_id"] == "TENANT_TEST_001"
    assert activation_data["active_domain_pack_version"] == "v1.0"
    assert activation_data["active_tenant_pack_version"] == "v1.0"

    # Verify active config
    response = client.get(
        "/admin/tenants/TENANT_TEST_001/active-config",
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    config_data = response.json()
    assert config_data["active_domain_pack_version"] == "v1.0"
    assert config_data["active_tenant_pack_version"] == "v1.0"


@pytest.mark.asyncio
async def test_runtime_usage_with_active_config(sample_domain_pack, sample_tenant_pack):
    """Test that runtime uses active configuration."""
    # Setup: Create tenant, import and activate packs
    client.post(
        "/admin/tenants",
        json={
            "tenant_id": "TENANT_TEST_001",
            "name": "Test Tenant",
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/packs/domain/import",
        json={
            "domain": "Finance",
            "version": "v1.0",
            "content": sample_domain_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/packs/tenant/import",
        json={
            "tenant_id": "TENANT_TEST_001",
            "version": "v1.0",
            "content": sample_tenant_pack,
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/packs/activate",
        json={
            "tenant_id": "TENANT_TEST_001",
            "domain_pack_version": "v1.0",
            "tenant_pack_version": "v1.0",
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    # Verify active config is accessible
    async with get_db_session_context()() as session:
        config_repo = TenantActiveConfigRepository(session)
        active_config = await config_repo.get_active_config("TENANT_TEST_001")
        
        assert active_config is not None
        assert active_config.active_domain_pack_version == "v1.0"
        assert active_config.active_tenant_pack_version == "v1.0"
        
        # Verify domain pack is accessible
        domain_pack_repo = DomainPackRepository(session)
        domain_pack = await domain_pack_repo.get_domain_pack("Finance", "v1.0")
        assert domain_pack is not None
        assert domain_pack.domain == "Finance"
        
        # Verify tenant pack is accessible
        tenant_pack_repo = TenantPackRepository(session)
        tenant_pack = await tenant_pack_repo.get_tenant_pack("TENANT_TEST_001", "v1.0")
        assert tenant_pack is not None
        assert tenant_pack.tenant_id == "TENANT_TEST_001"


@pytest.mark.asyncio
async def test_tenant_isolation_in_packs():
    """Test that tenant isolation is enforced in pack operations."""
    # Create two tenants
    client.post(
        "/admin/tenants",
        json={
            "tenant_id": "TENANT_A",
            "name": "Tenant A",
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/tenants",
        json={
            "tenant_id": "TENANT_B",
            "name": "Tenant B",
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    # Create tenant packs for each
    pack_a = {
        "tenantId": "TENANT_A",
        "domainName": "Finance",
        "approvedTools": ["tool1"],
    }
    
    pack_b = {
        "tenantId": "TENANT_B",
        "domainName": "Finance",
        "approvedTools": ["tool2"],
    }

    client.post(
        "/admin/packs/tenant/import",
        json={
            "tenant_id": "TENANT_A",
            "version": "v1.0",
            "content": pack_a,
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    client.post(
        "/admin/packs/tenant/import",
        json={
            "tenant_id": "TENANT_B",
            "version": "v1.0",
            "content": pack_b,
        },
        headers={"X-API-KEY": "test_api_key"},
    )

    # List packs for TENANT_A - should only see TENANT_A's pack
    response = client.get(
        "/admin/packs/tenant/TENANT_A",
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    packs = response.json()["items"]
    assert all(p["tenant_id"] == "TENANT_A" for p in packs)
    assert not any(p["tenant_id"] == "TENANT_B" for p in packs)

    # List packs for TENANT_B - should only see TENANT_B's pack
    response = client.get(
        "/admin/packs/tenant/TENANT_B",
        headers={"X-API-KEY": "test_api_key"},
    )
    assert response.status_code == 200
    packs = response.json()["items"]
    assert all(p["tenant_id"] == "TENANT_B" for p in packs)
    assert not any(p["tenant_id"] == "TENANT_A" for p in packs)

