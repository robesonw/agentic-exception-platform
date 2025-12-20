"""
Tests for Phase 12 Admin API routes.

Tests tenant management, pack import/validation, pack listing, and pack activation endpoints.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routes.onboarding import router
from src.api.auth import Role, UserContext, AuthMethod
from src.infrastructure.db.models import Tenant, TenantStatus, DomainPack, TenantPack, PackStatus


@pytest.fixture
def app():
    """Create a test FastAPI app with onboarding router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a sync test client."""
    return TestClient(app)


@pytest.fixture
def mock_admin_user_context():
    """Create a mock admin user context."""
    return UserContext(
        tenant_id="TENANT_TEST",
        user_id="admin_user",
        role=Role.ADMIN,
        auth_method=AuthMethod.API_KEY,
    )


@pytest.fixture
def mock_request_state(mock_admin_user_context):
    """Create a mock request state with admin user context."""
    state = MagicMock()
    state.user_context = mock_admin_user_context
    state.tenant_id = "TENANT_TEST"
    return state


class TestTenantManagementAPIs:
    """Test P12-10: Tenant Management APIs."""

    def test_create_tenant_success(self, client, mock_request_state):
        """Test successful tenant creation."""
        tenant_data = {
            "tenant_id": "TENANT_NEW_001",
            "name": "New Tenant",
        }
        
        mock_tenant = Tenant(
            tenant_id="TENANT_NEW_001",
            name="New Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin_user",
            updated_at=datetime.now(timezone.utc),
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.create_tenant = AsyncMock(return_value=mock_tenant)
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.post(
                        "/admin/tenants",
                        json=tenant_data,
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 201
                    data = response.json()
                    assert data["tenant_id"] == "TENANT_NEW_001"
                    assert data["name"] == "New Tenant"
                    assert data["status"] == "ACTIVE"

    def test_create_tenant_duplicate(self, client, mock_request_state):
        """Test tenant creation with duplicate tenant_id."""
        tenant_data = {
            "tenant_id": "TENANT_EXISTING",
            "name": "Existing Tenant",
        }
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.create_tenant = AsyncMock(side_effect=ValueError("Tenant already exists"))
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.post(
                        "/admin/tenants",
                        json=tenant_data,
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 400

    def test_list_tenants(self, client, mock_request_state):
        """Test listing tenants with pagination."""
        mock_tenants = [
            Tenant(
                tenant_id="TENANT_001",
                name="Tenant 1",
                status=TenantStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                created_by="admin",
                updated_at=datetime.now(timezone.utc),
            ),
            Tenant(
                tenant_id="TENANT_002",
                name="Tenant 2",
                status=TenantStatus.SUSPENDED,
                created_at=datetime.now(timezone.utc),
                created_by="admin",
                updated_at=datetime.now(timezone.utc),
            ),
        ]
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.select") as mock_select:
                from sqlalchemy import func
                mock_query = MagicMock()
                mock_select.return_value = mock_query
                mock_query.where = MagicMock(return_value=mock_query)
                mock_query.order_by = MagicMock(return_value=mock_query)
                mock_query.offset = MagicMock(return_value=mock_query)
                mock_query.limit = MagicMock(return_value=mock_query)
                
                mock_result = MagicMock()
                mock_result.scalars.return_value.all = MagicMock(return_value=mock_tenants)
                mock_session_instance.execute = AsyncMock(return_value=mock_result)
                
                # Mock count query
                mock_count_result = MagicMock()
                mock_count_result.scalar.return_value = 2
                mock_session_instance.execute = AsyncMock(
                    side_effect=[mock_count_result, mock_result]
                )
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.get(
                        "/admin/tenants?page=1&page_size=10",
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["total"] == 2
                    assert len(data["items"]) == 2

    def test_get_tenant_not_found(self, client, mock_request_state):
        """Test getting non-existent tenant."""
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.get_tenant = AsyncMock(return_value=None)
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.get(
                        "/admin/tenants/NONEXISTENT",
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 404

    def test_update_tenant_status(self, client, mock_request_state):
        """Test updating tenant status."""
        mock_tenant = Tenant(
            tenant_id="TENANT_001",
            name="Test Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.get_tenant = AsyncMock(return_value=mock_tenant)
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.patch(
                        "/admin/tenants/TENANT_001/status",
                        json={"status": "SUSPENDED"},
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 200
                    assert mock_tenant.status == TenantStatus.SUSPENDED


class TestPackImportValidationAPIs:
    """Test P12-11: Pack Import & Validation APIs."""

    def test_import_domain_pack_success(self, client, mock_request_state):
        """Test successful domain pack import."""
        pack_data = {
            "domain": "Finance",
            "version": "v1.0",
            "content": {
                "domainName": "Finance",
                "exceptionTypes": {
                    "TRADE_FAILED": {
                        "description": "Trade execution failed",
                        "detectionRules": [],
                    }
                },
                "tools": {},
                "playbooks": [],
            },
        }
        
        mock_pack = DomainPack(
            id=1,
            domain="Finance",
            version="v1.0",
            content_json=pack_data["content"],
            checksum="abc123",
            status=PackStatus.DRAFT,
            created_at=datetime.now(timezone.utc),
            created_by="admin_user",
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.DomainPackRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.create_domain_pack = AsyncMock(return_value=mock_pack)
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.post(
                        "/admin/packs/domain/import",
                        json=pack_data,
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 201
                    data = response.json()
                    assert data["domain"] == "Finance"
                    assert data["version"] == "v1.0"

    def test_import_domain_pack_validation_failure(self, client, mock_request_state):
        """Test domain pack import with validation failure."""
        pack_data = {
            "domain": "Finance",
            "version": "v1.0",
            "content": {
                # Missing required fields
            },
        }
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch.object(client.app, "state", mock_request_state):
                response = client.post(
                    "/admin/packs/domain/import",
                    json=pack_data,
                    headers={"X-API-KEY": "test_api_key_tenant_001"},
                )
                    
                assert response.status_code == 400

    def test_import_tenant_pack_success(self, client, mock_request_state):
        """Test successful tenant pack import."""
        pack_data = {
            "tenant_id": "TENANT_001",
            "version": "v1.0",
            "content": {
                "tenantId": "TENANT_001",
                "domainName": "Finance",
                "approvedTools": [],
                "customSeverityOverrides": [],
                "humanApprovalRules": [],
                "customPlaybooks": [],
            },
        }
        
        mock_tenant = Tenant(
            tenant_id="TENANT_001",
            name="Test Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
        )
        
        mock_pack = TenantPack(
            id=1,
            tenant_id="TENANT_001",
            version="v1.0",
            content_json=pack_data["content"],
            checksum="abc123",
            status=PackStatus.DRAFT,
            created_at=datetime.now(timezone.utc),
            created_by="admin_user",
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_tenant_repo_class:
                mock_tenant_repo = AsyncMock()
                mock_tenant_repo.get_tenant = AsyncMock(return_value=mock_tenant)
                mock_tenant_repo_class.return_value = mock_tenant_repo
                
                with patch("src.api.routes.onboarding.TenantPackRepository") as mock_pack_repo_class:
                    mock_pack_repo = AsyncMock()
                    mock_pack_repo.create_tenant_pack = AsyncMock(return_value=mock_pack)
                    mock_pack_repo_class.return_value = mock_pack_repo
                    
                    with patch.object(client.app, "state", mock_request_state):
                        response = client.post(
                            "/admin/packs/tenant/import",
                            json=pack_data,
                            headers={"X-API-KEY": "test_api_key_tenant_001"},
                        )
                        
                        assert response.status_code == 201
                        data = response.json()
                        assert data["tenant_id"] == "TENANT_001"
                        assert data["version"] == "v1.0"

    def test_validate_pack(self, client, mock_request_state):
        """Test pack validation endpoint."""
        pack_data = {
            "pack_type": "domain",
            "content": {
                "domainName": "Finance",
                "exceptionTypes": {
                    "TRADE_FAILED": {
                        "description": "Trade execution failed",
                        "detectionRules": [],
                    }
                },
                "tools": {},
                "playbooks": [],
            },
        }
        
        with patch.object(client.app, "state", mock_request_state):
            response = client.post(
                "/admin/packs/validate",
                json=pack_data,
                headers={"X-API-KEY": "test_api_key_tenant_001"},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "is_valid" in data
            assert "errors" in data
            assert "warnings" in data


class TestPackListingAPIs:
    """Test P12-12: Pack Listing & Version APIs."""

    def test_list_domain_packs(self, client, mock_request_state):
        """Test listing domain packs."""
        mock_packs = [
            DomainPack(
                id=1,
                domain="Finance",
                version="v1.0",
                content_json={},
                checksum="abc123",
                status=PackStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                created_by="admin",
            ),
        ]
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.DomainPackRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.list_domain_packs = AsyncMock(return_value=mock_packs)
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.get(
                        "/admin/packs/domain",
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["total"] == 1
                    assert len(data["items"]) == 1

    def test_get_domain_pack(self, client, mock_request_state):
        """Test getting domain pack by domain and version."""
        mock_pack = DomainPack(
            id=1,
            domain="Finance",
            version="v1.0",
            content_json={},
            checksum="abc123",
            status=PackStatus.DRAFT,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.DomainPackRepository") as mock_repo_class:
                mock_repo = AsyncMock()
                mock_repo.get_domain_pack = AsyncMock(return_value=mock_pack)
                mock_repo_class.return_value = mock_repo
                
                with patch.object(client.app, "state", mock_request_state):
                    response = client.get(
                        "/admin/packs/domain/Finance/v1.0",
                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["domain"] == "Finance"
                    assert data["version"] == "v1.0"

    def test_list_tenant_packs(self, client, mock_request_state):
        """Test listing tenant packs."""
        mock_tenant = Tenant(
            tenant_id="TENANT_001",
            name="Test Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
        )
        
        mock_packs = [
            TenantPack(
                id=1,
                tenant_id="TENANT_001",
                version="v1.0",
                content_json={},
                checksum="abc123",
                status=PackStatus.DRAFT,
                created_at=datetime.now(timezone.utc),
                created_by="admin",
            ),
        ]
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_tenant_repo_class:
                mock_tenant_repo = AsyncMock()
                mock_tenant_repo.get_tenant = AsyncMock(return_value=mock_tenant)
                mock_tenant_repo_class.return_value = mock_tenant_repo
                
                with patch("src.api.routes.onboarding.TenantPackRepository") as mock_pack_repo_class:
                    mock_pack_repo = AsyncMock()
                    mock_pack_repo.list_tenant_packs = AsyncMock(return_value=mock_packs)
                    mock_pack_repo_class.return_value = mock_pack_repo
                    
                    with patch.object(client.app, "state", mock_request_state):
                        response = client.get(
                            "/admin/packs/tenant/TENANT_001",
                            headers={"X-API-KEY": "test_api_key_tenant_001"},
                        )
                        
                        assert response.status_code == 200
                        data = response.json()
                        assert data["total"] == 1


class TestPackActivationAPI:
    """Test P12-13: Pack Activation API."""

    def test_activate_packs_direct(self, client, mock_request_state):
        """Test direct pack activation (no approval)."""
        activation_data = {
            "tenant_id": "TENANT_001",
            "domain_pack_version": "v1.0",
            "tenant_pack_version": "v1.0",
            "require_approval": False,
        }
        
        mock_tenant = Tenant(
            tenant_id="TENANT_001",
            name="Test Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
        )
        
        from src.infrastructure.db.models import TenantActiveConfig
        
        mock_active_config = TenantActiveConfig(
            tenant_id="TENANT_001",
            active_domain_pack_version="v1.0",
            active_tenant_pack_version="v1.0",
            activated_at=datetime.now(timezone.utc),
            activated_by="admin_user",
        )
        
        mock_domain_packs = [
            DomainPack(
                id=1,
                domain="Finance",
                version="v1.0",
                content_json={},
                checksum="abc123",
                status=PackStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                created_by="admin",
            ),
        ]
        
        mock_tenant_pack = TenantPack(
            id=1,
            tenant_id="TENANT_001",
            version="v1.0",
            content_json={},
            checksum="abc123",
            status=PackStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_tenant_repo_class:
                mock_tenant_repo = AsyncMock()
                mock_tenant_repo.get_tenant = AsyncMock(return_value=mock_tenant)
                mock_tenant_repo_class.return_value = mock_tenant_repo
                
                with patch("src.api.routes.onboarding.DomainPackRepository") as mock_domain_repo_class:
                    mock_domain_repo = AsyncMock()
                    mock_domain_repo.list_domain_packs = AsyncMock(return_value=mock_domain_packs)
                    mock_domain_repo_class.return_value = mock_domain_repo
                    
                    with patch("src.api.routes.onboarding.TenantPackRepository") as mock_tenant_pack_repo_class:
                        mock_tenant_pack_repo = AsyncMock()
                        mock_tenant_pack_repo.get_tenant_pack = AsyncMock(return_value=mock_tenant_pack)
                        mock_tenant_pack_repo_class.return_value = mock_tenant_pack_repo
                        
                        with patch("src.api.routes.onboarding.TenantActiveConfigRepository") as mock_config_repo_class:
                            mock_config_repo = AsyncMock()
                            mock_config_repo.get_active_config = AsyncMock(return_value=None)
                            mock_config_repo.activate_config = AsyncMock(return_value=mock_active_config)
                            mock_config_repo_class.return_value = mock_config_repo
                            
                            with patch.object(client.app, "state", mock_request_state):
                                response = client.post(
                                    "/admin/packs/activate",
                                    json=activation_data,
                                    headers={"X-API-KEY": "test_api_key_tenant_001"},
                                )
                                
                                assert response.status_code == 200
                                data = response.json()
                                assert data["tenant_id"] == "TENANT_001"
                                assert data["active_domain_pack_version"] == "v1.0"
                                assert data["change_request_id"] is None

    def test_activate_packs_with_approval(self, client, mock_request_state):
        """Test pack activation with approval workflow."""
        activation_data = {
            "tenant_id": "TENANT_001",
            "domain_pack_version": "v1.0",
            "tenant_pack_version": "v1.0",
            "require_approval": True,
        }
        
        mock_tenant = Tenant(
            tenant_id="TENANT_001",
            name="Test Tenant",
            status=TenantStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
            updated_at=datetime.now(timezone.utc),
        )
        
        mock_domain_packs = [
            DomainPack(
                id=1,
                domain="Finance",
                version="v1.0",
                content_json={},
                checksum="abc123",
                status=PackStatus.ACTIVE,
                created_at=datetime.now(timezone.utc),
                created_by="admin",
            ),
        ]
        
        mock_tenant_pack = TenantPack(
            id=1,
            tenant_id="TENANT_001",
            version="v1.0",
            content_json={},
            checksum="abc123",
            status=PackStatus.ACTIVE,
            created_at=datetime.now(timezone.utc),
            created_by="admin",
        )
        
        from src.infrastructure.db.models import ConfigChangeRequest
        from src.infrastructure.repositories.config_change_repository import ConfigChangeStatus, ConfigChangeType
        
        mock_change_request = ConfigChangeRequest(
            id="change-123",
            tenant_id="TENANT_001",
            change_type=ConfigChangeType.POLICY_PACK,
            resource_id="TENANT_001",
            status=ConfigChangeStatus.PENDING,
            requested_by="admin_user",
            requested_at=datetime.now(timezone.utc),
            proposed_config={"domain_pack_version": "v1.0", "tenant_pack_version": "v1.0"},
        )
        
        with patch("src.api.routes.onboarding.get_db_session_context") as mock_session:
            mock_session_instance = AsyncMock()
            mock_session.return_value.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session.return_value.__aexit__ = AsyncMock(return_value=None)
            
            with patch("src.api.routes.onboarding.TenantRepository") as mock_tenant_repo_class:
                mock_tenant_repo = AsyncMock()
                mock_tenant_repo.get_tenant = AsyncMock(return_value=mock_tenant)
                mock_tenant_repo_class.return_value = mock_tenant_repo
                
                with patch("src.api.routes.onboarding.DomainPackRepository") as mock_domain_repo_class:
                    mock_domain_repo = AsyncMock()
                    mock_domain_repo.list_domain_packs = AsyncMock(return_value=mock_domain_packs)
                    mock_domain_repo_class.return_value = mock_domain_repo
                    
                    with patch("src.api.routes.onboarding.TenantPackRepository") as mock_tenant_pack_repo_class:
                        mock_tenant_pack_repo = AsyncMock()
                        mock_tenant_pack_repo.get_tenant_pack = AsyncMock(return_value=mock_tenant_pack)
                        mock_tenant_pack_repo_class.return_value = mock_tenant_pack_repo
                        
                        with patch("src.api.routes.onboarding.TenantActiveConfigRepository") as mock_config_repo_class:
                            mock_config_repo = AsyncMock()
                            mock_config_repo.get_active_config = AsyncMock(return_value=None)
                            mock_config_repo_class.return_value = mock_config_repo
                            
                            with patch("src.api.routes.onboarding.ConfigChangeRepository") as mock_change_repo_class:
                                mock_change_repo = AsyncMock()
                                mock_change_repo.create_change_request = AsyncMock(return_value=mock_change_request)
                                mock_change_repo_class.return_value = mock_change_repo
                                
                                with patch.object(client.app, "state", mock_request_state):
                                    response = client.post(
                                        "/admin/packs/activate",
                                        json=activation_data,
                                        headers={"X-API-KEY": "test_api_key_tenant_001"},
                                    )
                                    
                                    assert response.status_code == 200
                                    data = response.json()
                                    assert data["tenant_id"] == "TENANT_001"
                                    assert data["change_request_id"] == "change-123"

