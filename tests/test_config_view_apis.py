"""
Tests for Configuration Viewing and Diffing APIs (P3-16).

Tests cover:
- Listing configurations (domain packs, tenant policies, playbooks)
- Getting configuration details by ID
- Diffing configurations
- Viewing configuration history
- Rollback stub validation
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, Playbook, PlaybookStep, SeverityRule
from src.models.tenant_policy import TenantPolicyPack
from src.services.config_view_service import ConfigType

# Test client
client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test-api-key-123"


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack for testing."""
    return DomainPack(
        domain_name="TestDomain",
        version="1.0.0",
        exception_types={
            "DataQualityFailure": ExceptionTypeDefinition(
                name="DataQualityFailure",
                description="Data quality failure",
                severity_rules=[
                    SeverityRule(
                        condition="payload.error_code == 'DQ001'",
                        severity="HIGH",
                    )
                ],
            )
        },
        playbooks=[
            Playbook(
                exception_type="DataQualityFailure",
                steps=[
                    PlaybookStep(
                        step_id="step1",
                        action="invokeTool('validateData')",
                        description="Validate data",
                    )
                ],
            )
        ],
        tools={},
    )


@pytest.fixture
def sample_tenant_policy():
    """Create a sample tenant policy for testing."""
    return TenantPolicyPack(
        tenant_id="tenant_001",
        domain_name="TestDomain",
        custom_guardrails={},
        custom_playbooks=[],
    )


@pytest.fixture
def temp_storage_dir(sample_domain_pack):
    """Create temporary storage directory with sample domain pack."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage_root = Path(tmpdir) / "domainpacks"
        tenant_dir = storage_root / "tenant_001" / "TestDomain"
        tenant_dir.mkdir(parents=True, exist_ok=True)
        
        # Write domain pack to file
        pack_file = tenant_dir / "1.0.0.json"
        with open(pack_file, "w") as f:
            json.dump(sample_domain_pack.model_dump(), f, default=str)
        
        yield storage_root


class TestConfigViewAPI:
    """Test suite for config view API endpoints."""

    def test_list_domain_packs_basic(self, temp_storage_dir):
        """Test basic domain pack listing."""
        with patch("src.services.config_view_service.Path") as mock_path:
            mock_path.return_value = temp_storage_dir
            mock_path.return_value.exists.return_value = True
            
            # Mock the storage root path
            with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
                mock_storage = MagicMock()
                mock_storage.list_versions.return_value = ["1.0.0"]
                mock_storage.get_pack.return_value = DomainPack(
                    domain_name="TestDomain",
                    version="1.0.0",
                    exception_types=[],
                    playbooks=[],
                    tools={},
                )
                mock_storage_class.return_value = mock_storage
                
                response = client.get(
                    "/admin/config/domain-packs",
                    headers={"X-API-KEY": DEFAULT_API_KEY},
                )
                
                # API should work even if no packs are found
                assert response.status_code == 200
                data = response.json()
                assert "items" in data
                assert "total" in data

    def test_list_domain_packs_with_filters(self):
        """Test domain pack listing with tenant and domain filters."""
        response = client.get(
            "/admin/config/domain-packs?tenant_id=tenant_001&domain=TestDomain",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert "total" in data

    def test_get_domain_pack_by_id(self, temp_storage_dir, sample_domain_pack):
        """Test getting domain pack by ID."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_pack.return_value = sample_domain_pack
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/domain-packs/tenant_001:TestDomain:1.0.0",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "type" in data
            assert "data" in data
            assert data["type"] == "domain_pack"

    def test_get_domain_pack_not_found(self):
        """Test getting non-existent domain pack."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_pack.return_value = None
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/domain-packs/tenant_001:TestDomain:2.0.0",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_get_tenant_policy_by_id(self, sample_tenant_policy):
        """Test getting tenant policy by ID."""
        with patch("src.services.config_view_service.TenantPolicyRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.get.return_value = sample_tenant_policy
            mock_registry_class.return_value = mock_registry
            
            response = client.get(
                "/admin/config/tenant-policies/tenant_001:TestDomain",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "type" in data
            assert "data" in data
            assert data["type"] == "tenant_policy"

    def test_get_tenant_policy_not_found(self):
        """Test getting non-existent tenant policy."""
        with patch("src.services.config_view_service.TenantPolicyRegistry") as mock_registry_class:
            mock_registry = MagicMock()
            mock_registry.get.return_value = None
            mock_registry_class.return_value = mock_registry
            
            response = client.get(
                "/admin/config/tenant-policies/tenant_999:TestDomain",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404

    def test_get_playbook_by_id(self, sample_domain_pack):
        """Test getting playbook by ID."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_pack.return_value = sample_domain_pack
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/playbooks/tenant_001:TestDomain:DataQualityFailure",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "id" in data
            assert "type" in data
            assert "data" in data
            assert data["type"] == "playbook"

    def test_get_playbook_not_found(self):
        """Test getting non-existent playbook."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_pack.return_value = DomainPack(
                domain_name="TestDomain",
                version="1.0.0",
                exception_types=[],
                playbooks=[],  # No playbooks
                tools={},
            )
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/playbooks/tenant_001:TestDomain:NonExistent",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404

    def test_diff_configs_domain_pack(self, sample_domain_pack):
        """Test diffing two domain pack versions."""
        # Create two versions of domain pack
        pack_v1 = sample_domain_pack
        pack_v2 = DomainPack(
            domain_name="TestDomain",
            version="2.0.0",
            exception_types=[
                ExceptionTypeDefinition(
                    name="DataQualityFailure",
                    description="Data quality failure (updated)",
                    severity_rules=[],
                )
            ],
            playbooks=[],
            tools={},
        )
        
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_pack.side_effect = [pack_v1, pack_v2]
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/diff?type=domain_pack&leftVersion=tenant_001:TestDomain:1.0.0&rightVersion=tenant_001:TestDomain:2.0.0",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "left" in data
            assert "right" in data
            assert "differences" in data
            assert "summary" in data
            assert "added" in data["differences"]
            assert "removed" in data["differences"]
            assert "modified" in data["differences"]

    def test_diff_configs_invalid_type(self):
        """Test diffing with invalid configuration type."""
        response = client.get(
            "/admin/config/diff?type=invalid_type&leftVersion=id1&rightVersion=id2",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "Invalid configuration type" in response.json()["detail"]

    def test_diff_configs_not_found(self):
        """Test diffing when one or both configs not found."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.get_pack.return_value = None
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/diff?type=domain_pack&leftVersion=tenant_001:TestDomain:1.0.0&rightVersion=tenant_001:TestDomain:2.0.0",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404

    def test_get_config_history(self, sample_domain_pack):
        """Test getting configuration history."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_versions.return_value = ["1.0.0", "2.0.0"]
            mock_storage_class.return_value = mock_storage
            
            response = client.get(
                "/admin/config/history/domain_pack/tenant_001:TestDomain:1.0.0",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert len(data["items"]) > 0

    def test_get_config_history_invalid_type(self):
        """Test getting history with invalid configuration type."""
        response = client.get(
            "/admin/config/history/invalid_type/config_id",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "Invalid configuration type" in response.json()["detail"]

    def test_rollback_config_stub(self, sample_domain_pack):
        """Test rollback stub validation."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_versions.return_value = ["1.0.0", "2.0.0"]
            mock_storage_class.return_value = mock_storage
            
            response = client.post(
                "/admin/config/rollback",
                json={
                    "config_type": "domain_pack",
                    "config_id": "tenant_001:TestDomain:1.0.0",
                    "target_version": "1.0.0",
                },
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert "stub" in data["note"].lower()
            assert "not applied" in data["note"].lower()

    def test_rollback_config_invalid_type(self):
        """Test rollback with invalid configuration type."""
        response = client.post(
            "/admin/config/rollback",
            json={
                "config_type": "invalid_type",
                "config_id": "config_id",
                "target_version": "1.0.0",
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "Invalid configuration type" in response.json()["detail"]

    def test_rollback_config_version_not_found(self):
        """Test rollback with non-existent target version."""
        with patch("src.services.config_view_service.DomainPackStorage") as mock_storage_class:
            mock_storage = MagicMock()
            mock_storage.list_versions.return_value = ["1.0.0"]
            mock_storage_class.return_value = mock_storage
            
            response = client.post(
                "/admin/config/rollback",
                json={
                    "config_type": "domain_pack",
                    "config_id": "tenant_001:TestDomain:1.0.0",
                    "target_version": "999.0.0",
                },
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

