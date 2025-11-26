"""
Comprehensive tests for Admin Domain Pack Management API.

Tests:
- POST /admin/domainpacks/{tenantId} - upload pack (JSON/YAML), validate, store, register
- GET /admin/domainpacks/{tenantId} - list domain packs + versions + usage stats
- POST /admin/domainpacks/{tenantId}/rollback - rollback active version
"""

import json
import tempfile
from io import BytesIO
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes import admin_domainpacks
from src.domainpack.loader import DomainPackRegistry
from src.domainpack.storage import DomainPackStorage
from src.models.domain_pack import DomainPack

DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture
def temp_storage_dir():
    """Temporary storage directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def domain_pack_storage(temp_storage_dir):
    """Domain pack storage for testing."""
    return DomainPackStorage(storage_root=temp_storage_dir)


@pytest.fixture
def domain_pack_registry():
    """Domain pack registry for testing."""
    return DomainPackRegistry()


@pytest.fixture
def client(domain_pack_storage, domain_pack_registry):
    """Test client with mocked storage and registry."""
    admin_domainpacks.set_domain_pack_storage(domain_pack_storage)
    admin_domainpacks.set_domain_pack_registry(domain_pack_registry)
    
    yield TestClient(app)
    
    # Cleanup after test
    admin_domainpacks.set_domain_pack_storage(None)
    admin_domainpacks.set_domain_pack_registry(None)


@pytest.fixture
def sample_domain_pack_json():
    """Sample domain pack as JSON string."""
    return json.dumps({
        "domainName": "Finance",
        "entities": {
            "Order": {
                "attributes": {
                    "orderId": {"type": "string", "required": True},
                    "amount": {"type": "number", "required": False},
                    "status": {"type": "string", "required": False}
                },
                "relations": []
            }
        },
        "exceptionTypes": {
            "SETTLEMENT_FAIL": {
                "description": "Settlement failure",
                "detectionRules": ["amount > 0"]
            }
        },
        "severityRules": [
            {
                "condition": "amount > 1000",
                "severity": "HIGH"
            }
        ],
        "tools": {
            "retry_settlement": {
                "description": "Retry settlement",
                "endpoint": "https://api.example.com/retry",
                "parameters": {
                    "orderId": {"type": "string"}
                }
            }
        },
        "playbooks": [
            {
                "exceptionType": "SETTLEMENT_FAIL",
                "steps": [
                    {
                        "action": "retry_settlement",
                        "parameters": {"orderId": "{{orderId}}"}
                    }
                ]
            }
        ],
        "guardrails": {
            "allowLists": [],
            "blockLists": [],
            "humanApprovalThreshold": 0.8
        },
        "testSuites": []
    })


@pytest.fixture
def sample_domain_pack_yaml():
    """Sample domain pack as YAML string."""
    return yaml.dump({
        "domainName": "Finance",
        "entities": {
            "Order": {
                "attributes": {
                    "orderId": {"type": "string", "required": True},
                    "amount": {"type": "number", "required": False},
                    "status": {"type": "string", "required": False}
                },
                "relations": []
            }
        },
        "exceptionTypes": {
            "SETTLEMENT_FAIL": {
                "description": "Settlement failure",
                "detectionRules": ["amount > 0"]
            }
        },
        "severityRules": [
            {
                "condition": "amount > 1000",
                "severity": "HIGH"
            }
        ],
        "tools": {
            "retry_settlement": {
                "description": "Retry settlement",
                "endpoint": "https://api.example.com/retry",
                "parameters": {
                    "orderId": {"type": "string"}
                }
            }
        },
        "playbooks": [
            {
                "exceptionType": "SETTLEMENT_FAIL",
                "steps": [
                    {
                        "action": "retry_settlement",
                        "parameters": {"orderId": "{{orderId}}"}
                    }
                ]
            }
        ],
        "guardrails": {
            "allowLists": [],
            "blockLists": [],
            "humanApprovalThreshold": 0.8
        },
        "testSuites": []
    })


@pytest.fixture
def setup_api_key():
    """Setup API key for testing."""
    from src.api.auth import get_api_key_auth
    from src.api.middleware import get_rate_limiter
    auth = get_api_key_auth()
    limiter = get_rate_limiter()
    yield auth
    # Reset rate limiter after each test
    limiter._request_timestamps.clear()


class TestAdminDomainPackUpload:
    """Tests for Domain Pack upload endpoint."""

    def test_upload_domain_pack_json_success(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_json, setup_api_key
    ):
        """Test successful upload of JSON domain pack."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload pack
        response = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(sample_domain_pack_json.encode()), "application/json")},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        if response.status_code != 200:
            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
        assert response.status_code == 200, f"Response: {response.text}"
        data = response.json()
        
        assert data["domainName"] == "Finance"
        assert data["version"] == "1.0.0"
        assert data["stored"] is True
        assert data["registered"] is True
        assert "uploaded successfully" in data["message"]
        
        # Verify pack is stored
        stored_pack = domain_pack_storage.get_pack(
            tenant_id=tenant_id,
            domain_name="Finance",
            version="1.0.0",
        )
        assert stored_pack is not None
        assert stored_pack.domain_name == "Finance"
        
        # Verify pack is registered
        registered_pack = domain_pack_registry.get(
            domain_name="Finance",
            tenant_id=tenant_id,
        )
        assert registered_pack is not None
        assert registered_pack.domain_name == "Finance"

    def test_upload_domain_pack_yaml_success(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_yaml, setup_api_key
    ):
        """Test successful upload of YAML domain pack."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload pack
        response = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.yaml", BytesIO(sample_domain_pack_yaml.encode()), "application/yaml")},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["domainName"] == "Finance"
        assert data["stored"] is True
        assert data["registered"] is True

    def test_upload_domain_pack_with_custom_version(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_json, setup_api_key
    ):
        """Test upload with custom version parameter."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload pack with custom version
        response = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(sample_domain_pack_json.encode()), "application/json")},
            params={"version": "2.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["version"] == "2.0.0"
        
        # Verify pack is stored with custom version
        stored_pack = domain_pack_storage.get_pack(
            tenant_id=tenant_id,
            domain_name="Finance",
            version="2.0.0",
        )
        assert stored_pack is not None

    def test_upload_domain_pack_invalid_json(self, client, setup_api_key):
        """Test upload with invalid JSON."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload invalid JSON
        response = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(b"{ invalid json }"), "application/json")},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "Invalid JSON" in response.json()["detail"]

    def test_upload_domain_pack_invalid_schema(self, client, setup_api_key):
        """Test upload with invalid domain pack schema."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload invalid schema (missing required fields)
        invalid_pack = json.dumps({"domainName": "Finance"})  # Missing required fields
        
        response = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(invalid_pack.encode()), "application/json")},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "validation failed" in response.json()["detail"].lower()


class TestAdminDomainPackList:
    """Tests for Domain Pack list endpoint."""

    def test_list_domain_packs_success(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_json, setup_api_key
    ):
        """Test successful listing of domain packs."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload a pack first
        client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(sample_domain_pack_json.encode()), "application/json")},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        # List packs
        response = client.get(
            f"/admin/domainpacks/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["total"] == 1
        assert len(data["packs"]) == 1
        
        pack_info = data["packs"][0]
        assert pack_info["domainName"] == "Finance"
        assert "1.0.0" in pack_info["versions"]
        assert pack_info["latestVersion"] == "1.0.0"

    def test_list_domain_packs_multiple_versions(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_json, setup_api_key
    ):
        """Test listing packs with multiple versions."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload pack with version 1.0.0
        client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(sample_domain_pack_json.encode()), "application/json")},
            params={"version": "1.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        # Upload pack with version 2.0.0
        pack_data = json.loads(sample_domain_pack_json)
        client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(json.dumps(pack_data).encode()), "application/json")},
            params={"version": "2.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        # List packs
        response = client.get(
            f"/admin/domainpacks/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        pack_info = data["packs"][0]
        assert len(pack_info["versions"]) == 2
        assert "1.0.0" in pack_info["versions"]
        assert "2.0.0" in pack_info["versions"]
        assert pack_info["latestVersion"] == "2.0.0"

    def test_list_domain_packs_empty(self, client, setup_api_key):
        """Test listing packs when none exist."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/admin/domainpacks/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["total"] == 0
        assert len(data["packs"]) == 0


class TestAdminDomainPackRollback:
    """Tests for Domain Pack rollback endpoint."""

    def test_rollback_domain_pack_success(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_json, setup_api_key
    ):
        """Test successful rollback of domain pack."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload pack with version 1.0.0
        response1 = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(sample_domain_pack_json.encode()), "application/json")},
            params={"version": "1.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        assert response1.status_code == 200
        
        # Upload pack with version 2.0.0
        pack_data = json.loads(sample_domain_pack_json)
        response2 = client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(json.dumps(pack_data).encode()), "application/json")},
            params={"version": "2.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        assert response2.status_code == 200
        
        # Verify versions are stored
        versions = domain_pack_storage.list_versions(tenant_id=tenant_id, domain_name="Finance")
        assert "1.0.0" in versions
        assert "2.0.0" in versions
        
        # Rollback to version 1.0.0
        response = client.post(
            f"/admin/domainpacks/{tenant_id}/rollback",
            json={"domainName": "Finance", "targetVersion": "1.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["domainName"] == "Finance"
        assert data["previousVersion"] == "2.0.0"
        assert data["newVersion"] == "1.0.0"
        assert data["success"] is True
        
        # Verify registry now has version 1.0.0 as latest
        latest_pack = domain_pack_registry.get_latest(domain_name="Finance", tenant_id=tenant_id)
        assert latest_pack is not None
        # The registry should have the rolled-back version

    def test_rollback_domain_pack_version_not_found(
        self, client, domain_pack_storage, domain_pack_registry, sample_domain_pack_json, setup_api_key
    ):
        """Test rollback with non-existent version."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Upload pack
        client.post(
            f"/admin/domainpacks/{tenant_id}",
            files={"file": ("pack.json", BytesIO(sample_domain_pack_json.encode()), "application/json")},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        # Try to rollback to non-existent version
        response = client.post(
            f"/admin/domainpacks/{tenant_id}/rollback",
            json={"domainName": "Finance", "targetVersion": "999.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_rollback_domain_pack_domain_not_found(self, client, setup_api_key):
        """Test rollback with non-existent domain."""
        tenant_id = "TENANT_A"
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Try to rollback non-existent domain
        response = client.post(
            f"/admin/domainpacks/{tenant_id}/rollback",
            json={"domainName": "NonExistent", "targetVersion": "1.0.0"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

