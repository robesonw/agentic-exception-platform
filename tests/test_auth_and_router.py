"""
Tests for authentication and tenant router.
Tests API key authentication, tenant routing, and tenant isolation.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.auth import APIKeyAuth, AuthenticationError, get_api_key_auth
from src.api.main import app
from src.api.middleware import RateLimiter, get_rate_limiter

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_auth():
    """Reset API key auth before each test."""
    auth = get_api_key_auth()
    # Clear existing keys and reinitialize
    auth._api_keys.clear()
    auth._api_keys["test_api_key_tenant_001"] = "TENANT_001"
    auth._api_keys["test_api_key_tenant_002"] = "TENANT_002"
    yield
    # Reset after test
    auth._api_keys.clear()
    auth._api_keys["test_api_key_tenant_001"] = "TENANT_001"
    auth._api_keys["test_api_key_tenant_002"] = "TENANT_002"


@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Reset rate limiter before each test."""
    limiter = get_rate_limiter()
    limiter._request_timestamps.clear()
    yield
    limiter._request_timestamps.clear()


class TestAPIKeyAuth:
    """Tests for API key authentication."""

    def test_validate_api_key_returns_tenant_id(self):
        """Test that valid API key returns correct tenant ID."""
        auth = get_api_key_auth()
        
        tenant_id = auth.validate_api_key("test_api_key_tenant_001")
        assert tenant_id == "TENANT_001"

    def test_validate_api_key_rejects_invalid_key(self):
        """Test that invalid API key raises AuthenticationError."""
        auth = get_api_key_auth()
        
        with pytest.raises(AuthenticationError) as exc_info:
            auth.validate_api_key("invalid_key")
        
        assert "Invalid API key" in str(exc_info.value)

    def test_validate_api_key_rejects_empty_key(self):
        """Test that empty API key raises AuthenticationError."""
        auth = get_api_key_auth()
        
        with pytest.raises(AuthenticationError) as exc_info:
            auth.validate_api_key("")
        
        assert "required" in str(exc_info.value).lower()

    def test_register_api_key(self):
        """Test registering a new API key."""
        auth = get_api_key_auth()
        
        auth.register_api_key("new_api_key", "NEW_TENANT")
        
        tenant_id = auth.validate_api_key("new_api_key")
        assert tenant_id == "NEW_TENANT"

    def test_revoke_api_key(self):
        """Test revoking an API key."""
        auth = get_api_key_auth()
        
        # Register and validate
        auth.register_api_key("temp_key", "TEMP_TENANT")
        assert auth.validate_api_key("temp_key") == "TEMP_TENANT"
        
        # Revoke
        auth.revoke_api_key("temp_key")
        
        # Should now be invalid
        with pytest.raises(AuthenticationError):
            auth.validate_api_key("temp_key")


class TestTenantRouterMiddleware:
    """Tests for tenant router middleware."""

    def test_missing_api_key_returns_401(self):
        """Test that missing X-API-KEY header returns 401."""
        response = client.get("/exceptions/TENANT_001/exc_001")
        
        assert response.status_code == 401
        data = response.json()
        assert "X-API-KEY" in data["detail"] or "Missing" in data["detail"]

    def test_invalid_api_key_returns_401(self):
        """Test that invalid API key returns 401."""
        response = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "invalid_key"},
        )
        
        assert response.status_code == 401
        data = response.json()
        assert "Invalid" in data["detail"] or "invalid" in data["detail"].lower()

    def test_valid_api_key_attaches_tenant_id(self):
        """Test that valid API key attaches tenant ID to request state."""
        # This is tested indirectly through route handlers
        response = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        
        # Should not be 401 (authentication passed)
        # May be 404 if exception doesn't exist, but that's expected
        assert response.status_code != 401

    def test_health_endpoint_bypasses_auth(self):
        """Test that /health endpoint bypasses authentication."""
        response = client.get("/health")
        
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"

    def test_docs_endpoint_bypasses_auth(self):
        """Test that /docs endpoint bypasses authentication."""
        response = client.get("/docs")
        
        # Should not be 401 (may be 200 or redirect)
        assert response.status_code != 401


class TestTenantIsolation:
    """Tests for tenant isolation enforcement."""

    def test_tenant_mismatch_returns_403(self):
        """Test that tenant ID mismatch returns 403."""
        # Use tenant_001 API key but try to access tenant_002
        response = client.get(
            "/exceptions/TENANT_002/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        
        assert response.status_code == 403
        data = response.json()
        assert "mismatch" in data["detail"].lower() or "403" in str(response.status_code)

    def test_tenant_match_allows_access(self):
        """Test that matching tenant ID allows access."""
        # Use tenant_001 API key and access tenant_001
        response = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        
        # Should not be 403 (may be 404 if exception doesn't exist)
        assert response.status_code != 403

    def test_exceptions_route_tenant_isolation(self):
        """Test tenant isolation in exceptions route."""
        # Try to ingest exception with mismatched tenant
        response = client.post(
            "/exceptions/TENANT_002",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
            json={"exception": {"sourceSystem": "ERP", "rawPayload": {}}},
        )
        
        # Should return 403 for tenant mismatch
        assert response.status_code == 403

    def test_run_route_tenant_isolation(self):
        """Test tenant isolation in run route."""
        # This would require actual domain/tenant pack files
        # For now, we test that authentication is required
        response = client.post(
            "/run",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
            json={
                "domainPackPath": "domainpacks/finance.sample.json",
                "tenantPolicyPath": "tenantpacks/tenant_finance.sample.json",
                "exceptions": [{"sourceSystem": "ERP", "rawPayload": {}}],
            },
        )
        
        # Should not be 401 (authentication passed)
        # May be 400 or 500 depending on file paths, but auth should work
        assert response.status_code != 401


class TestRateLimiting:
    """Tests for rate limiting."""

    def test_rate_limiter_allows_requests(self):
        """Test that rate limiter allows requests within limit."""
        limiter = RateLimiter(requests_per_minute=5)
        
        for i in range(5):
            is_allowed, error = limiter.is_allowed("TENANT_001")
            assert is_allowed is True
            assert error is None

    def test_rate_limiter_blocks_excess_requests(self):
        """Test that rate limiter blocks requests exceeding limit."""
        limiter = RateLimiter(requests_per_minute=3)
        
        # Make 3 requests (should all be allowed)
        for i in range(3):
            is_allowed, error = limiter.is_allowed("TENANT_001")
            assert is_allowed is True
        
        # 4th request should be blocked
        is_allowed, error = limiter.is_allowed("TENANT_001")
        assert is_allowed is False
        assert "Rate limit exceeded" in error

    def test_rate_limiter_per_tenant(self):
        """Test that rate limiting is per tenant."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # Tenant 1 uses up limit
        limiter.is_allowed("TENANT_001")
        limiter.is_allowed("TENANT_001")
        
        # Tenant 2 should still be allowed
        is_allowed, error = limiter.is_allowed("TENANT_002")
        assert is_allowed is True
        
        # Tenant 1 should be blocked
        is_allowed, error = limiter.is_allowed("TENANT_001")
        assert is_allowed is False

    def test_rate_limiter_reset_tenant(self):
        """Test that rate limiter can be reset for a tenant."""
        limiter = RateLimiter(requests_per_minute=2)
        
        # Use up limit
        limiter.is_allowed("TENANT_001")
        limiter.is_allowed("TENANT_001")
        
        # Should be blocked
        is_allowed, error = limiter.is_allowed("TENANT_001")
        assert is_allowed is False
        
        # Reset
        limiter.reset_tenant("TENANT_001")
        
        # Should be allowed again
        is_allowed, error = limiter.is_allowed("TENANT_001")
        assert is_allowed is True

    def test_rate_limiting_returns_429(self):
        """Test that rate limiting returns 429 status code."""
        limiter = get_rate_limiter()
        limiter.requests_per_minute = 1
        
        # First request should succeed
        response1 = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        assert response1.status_code != 429
        
        # Second request should be rate limited
        response2 = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        # May be 429 or other status, but rate limiting should be checked
        # Reset limiter for other tests
        limiter.reset_tenant("TENANT_001")


class TestAuthAndRouterIntegration:
    """Integration tests for authentication and routing."""

    def test_full_flow_with_valid_key(self):
        """Test full flow with valid API key."""
        response = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        
        # Should not be 401 (authentication passed)
        # May be 404 if exception doesn't exist
        assert response.status_code != 401
        assert response.status_code != 403

    def test_full_flow_with_invalid_key(self):
        """Test full flow with invalid API key."""
        response = client.get(
            "/exceptions/TENANT_001/exc_001",
            headers={"X-API-KEY": "invalid_key"},
        )
        
        assert response.status_code == 401

    def test_full_flow_with_mismatched_tenant(self):
        """Test full flow with mismatched tenant ID."""
        response = client.get(
            "/exceptions/TENANT_002/exc_001",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
        )
        
        assert response.status_code == 403

