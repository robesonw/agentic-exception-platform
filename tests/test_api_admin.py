"""
Tests for Admin API routes.
Tests domain pack and tenant policy pack upload endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestAdminAPI:
    """Tests for Admin API endpoints."""

    def test_upload_domain_pack_endpoint_exists(self):
        """Test that upload domain pack endpoint exists."""
        # Endpoint is a TODO in MVP, but should return appropriate response
        response = client.post(
            "/tenants/TENANT_001/packs/domain",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
            json={},
        )
        
        # Should not be 404 (endpoint exists)
        # May be 501 (not implemented) or 400 (validation error)
        assert response.status_code != 404

    def test_upload_policy_pack_endpoint_exists(self):
        """Test that upload policy pack endpoint exists."""
        # Endpoint is a TODO in MVP, but should return appropriate response
        response = client.post(
            "/tenants/TENANT_001/packs/policy",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
            json={},
        )
        
        # Should not be 404 (endpoint exists)
        # May be 501 (not implemented) or 400 (validation error)
        assert response.status_code != 404

    def test_admin_endpoints_require_auth(self):
        """Test that admin endpoints require authentication."""
        response = client.post("/tenants/TENANT_001/packs/domain", json={})
        
        # Should require authentication
        assert response.status_code == 401

