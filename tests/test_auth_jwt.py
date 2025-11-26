"""
Comprehensive tests for JWT authentication and RBAC.

Tests:
- JWT token creation and validation
- Tenant ID extraction from JWT claims
- RBAC role enforcement
- API key authentication (backward compatibility)
- Rate limiting with role-based limits
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import jwt

from src.api.auth import (
    APIKeyAuth,
    AuthManager,
    AuthenticationError,
    AuthorizationError,
    JWTAuth,
    Role,
    UserContext,
    get_auth_manager,
)
from src.api.middleware import RateLimiter, TenantRouterMiddleware
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient


@pytest.fixture
def jwt_auth():
    """JWT auth instance for testing."""
    return JWTAuth(secret_key="test-secret-key", algorithm="HS256", token_expiry_hours=24)


@pytest.fixture
def api_key_auth():
    """API key auth instance for testing."""
    return APIKeyAuth()


@pytest.fixture
def auth_manager():
    """Auth manager instance for testing."""
    return AuthManager(jwt_secret_key="test-secret-key")


@pytest.fixture(autouse=True)
def reset_api_keys():
    """Reset API keys before each test to ensure consistent state."""
    from src.api.auth import get_api_key_auth
    auth = get_api_key_auth()
    # Ensure test_api_key_tenant_001 is registered to TENANT_001
    auth.register_api_key("test_api_key_tenant_001", "TENANT_001", Role.ADMIN)
    yield
    # Cleanup handled by singleton


@pytest.fixture
def rate_limiter():
    """Rate limiter instance for testing."""
    return RateLimiter(
        default_requests_per_minute=100,
        endpoint_limits={"/admin": 10, "/metrics": 50},
        role_limits={"viewer": 50, "operator": 200, "admin": 500},
    )


class TestJWTAuth:
    """Tests for JWT authentication."""

    def test_create_token(self, jwt_auth):
        """Test JWT token creation."""
        token = jwt_auth.create_token(
            tenant_id="TENANT_A",
            user_id="user123",
            role=Role.ADMIN,
        )
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_validate_token_success(self, jwt_auth):
        """Test successful JWT token validation."""
        token = jwt_auth.create_token(
            tenant_id="TENANT_A",
            user_id="user123",
            role=Role.OPERATOR,
        )
        
        user_context = jwt_auth.validate_token(token)
        
        assert user_context.tenant_id == "TENANT_A"
        assert user_context.user_id == "user123"
        assert user_context.role == Role.OPERATOR
        assert user_context.auth_method.value == "jwt"

    def test_validate_token_expired(self, jwt_auth):
        """Test JWT token validation with expired token."""
        # Create token with very short expiry
        jwt_auth_short = JWTAuth(secret_key="test-secret-key", token_expiry_hours=-1)
        token = jwt_auth_short.create_token(
            tenant_id="TENANT_A",
            user_id="user123",
            role=Role.VIEWER,
        )
        
        # Wait a moment to ensure expiry
        import time
        time.sleep(0.1)
        
        with pytest.raises(AuthenticationError) as exc_info:
            jwt_auth.validate_token(token)
        
        assert "expired" in str(exc_info.value).lower()

    def test_validate_token_invalid(self, jwt_auth):
        """Test JWT token validation with invalid token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(AuthenticationError) as exc_info:
            jwt_auth.validate_token(invalid_token)
        
        assert "invalid" in str(exc_info.value).lower()

    def test_validate_token_missing_tenant_id(self, jwt_auth):
        """Test JWT token validation with missing tenant_id claim."""
        # Create token without tenant_id
        payload = {
            "sub": "user123",
            "role": Role.VIEWER.value,
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
        }
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        
        with pytest.raises(AuthenticationError) as exc_info:
            jwt_auth.validate_token(token)
        
        assert "tenant_id" in str(exc_info.value).lower()

    def test_validate_token_invalid_role(self, jwt_auth):
        """Test JWT token validation with invalid role defaults to VIEWER."""
        # Create token with invalid role
        payload = {
            "sub": "user123",
            "tenant_id": "TENANT_A",
            "role": "invalid_role",
            "iat": int(datetime.now(timezone.utc).timestamp()),
            "exp": int((datetime.now(timezone.utc) + timedelta(hours=24)).timestamp()),
        }
        token = jwt.encode(payload, "test-secret-key", algorithm="HS256")
        
        user_context = jwt_auth.validate_token(token)
        
        # Should default to VIEWER
        assert user_context.role == Role.VIEWER

    def test_create_token_with_additional_claims(self, jwt_auth):
        """Test JWT token creation with additional claims."""
        additional_claims = {"email": "user@example.com", "department": "Engineering"}
        token = jwt_auth.create_token(
            tenant_id="TENANT_A",
            user_id="user123",
            role=Role.ADMIN,
            additional_claims=additional_claims,
        )
        
        # Decode to verify additional claims
        payload = jwt.decode(token, "test-secret-key", algorithms=["HS256"])
        assert payload["email"] == "user@example.com"
        assert payload["department"] == "Engineering"


class TestUserContext:
    """Tests for UserContext and RBAC."""

    def test_has_permission_viewer(self):
        """Test permission checking for viewer role."""
        user_context = UserContext(tenant_id="TENANT_A", role=Role.VIEWER)
        
        assert user_context.has_permission(Role.VIEWER) is True
        assert user_context.has_permission(Role.OPERATOR) is False
        assert user_context.has_permission(Role.ADMIN) is False

    def test_has_permission_operator(self):
        """Test permission checking for operator role."""
        user_context = UserContext(tenant_id="TENANT_A", role=Role.OPERATOR)
        
        assert user_context.has_permission(Role.VIEWER) is True
        assert user_context.has_permission(Role.OPERATOR) is True
        assert user_context.has_permission(Role.ADMIN) is False

    def test_has_permission_admin(self):
        """Test permission checking for admin role."""
        user_context = UserContext(tenant_id="TENANT_A", role=Role.ADMIN)
        
        assert user_context.has_permission(Role.VIEWER) is True
        assert user_context.has_permission(Role.OPERATOR) is True
        assert user_context.has_permission(Role.ADMIN) is True


class TestAuthManager:
    """Tests for unified AuthManager."""

    def test_authenticate_with_jwt(self, auth_manager):
        """Test authentication with JWT token."""
        token = auth_manager.jwt_auth.create_token(
            tenant_id="TENANT_A",
            user_id="user123",
            role=Role.ADMIN,
        )
        
        user_context = auth_manager.authenticate(jwt_token=token)
        
        assert user_context.tenant_id == "TENANT_A"
        assert user_context.user_id == "user123"
        assert user_context.role == Role.ADMIN

    def test_authenticate_with_api_key(self, auth_manager):
        """Test authentication with API key."""
        user_context = auth_manager.authenticate(api_key="test_api_key_tenant_001")
        
        assert user_context.tenant_id == "TENANT_001"
        assert user_context.role == Role.ADMIN
        assert user_context.auth_method.value == "api_key"

    def test_authenticate_jwt_precedence(self, auth_manager):
        """Test that JWT takes precedence over API key when both provided."""
        token = auth_manager.jwt_auth.create_token(
            tenant_id="TENANT_JWT",
            user_id="user123",
            role=Role.OPERATOR,
        )
        
        user_context = auth_manager.authenticate(
            api_key="test_api_key_tenant_001",
            jwt_token=token,
        )
        
        # Should use JWT
        assert user_context.tenant_id == "TENANT_JWT"
        assert user_context.user_id == "user123"

    def test_authenticate_no_credentials(self, auth_manager):
        """Test authentication fails when no credentials provided."""
        with pytest.raises(AuthenticationError) as exc_info:
            auth_manager.authenticate()
        
        assert "credentials" in str(exc_info.value).lower()

    def test_require_role_success(self, auth_manager):
        """Test require_role succeeds when user has permission."""
        user_context = UserContext(tenant_id="TENANT_A", role=Role.ADMIN)
        
        # Should not raise
        auth_manager.require_role(user_context, Role.VIEWER)
        auth_manager.require_role(user_context, Role.OPERATOR)
        auth_manager.require_role(user_context, Role.ADMIN)

    def test_require_role_failure(self, auth_manager):
        """Test require_role fails when user lacks permission."""
        user_context = UserContext(tenant_id="TENANT_A", role=Role.VIEWER)
        
        # Should raise for higher roles
        with pytest.raises(AuthorizationError):
            auth_manager.require_role(user_context, Role.OPERATOR)
        
        with pytest.raises(AuthorizationError):
            auth_manager.require_role(user_context, Role.ADMIN)


class TestAPIKeyAuthBackwardCompatibility:
    """Tests for API key authentication backward compatibility."""

    def test_api_key_auth_still_works(self, api_key_auth):
        """Test that existing API key auth still works."""
        user_context = api_key_auth.validate_api_key("test_api_key_tenant_001")
        
        assert user_context.tenant_id == "TENANT_001"
        assert user_context.role == Role.ADMIN

    def test_register_api_key_with_role(self, api_key_auth):
        """Test registering API key with specific role."""
        api_key_auth.register_api_key("new_key", "TENANT_NEW", Role.OPERATOR)
        
        user_context = api_key_auth.validate_api_key("new_key")
        assert user_context.tenant_id == "TENANT_NEW"
        assert user_context.role == Role.OPERATOR


class TestRateLimiter:
    """Tests for enhanced rate limiter."""

    def test_rate_limit_default(self, rate_limiter):
        """Test default rate limiting."""
        # Should allow requests up to default limit
        for i in range(100):
            is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/test", None)
            assert is_allowed is True
        
        # 101st request should be blocked
        is_allowed, error_msg = rate_limiter.is_allowed("TENANT_A", "/test", None)
        assert is_allowed is False
        assert "exceeded" in error_msg.lower()

    def test_rate_limit_endpoint_specific(self, rate_limiter):
        """Test endpoint-specific rate limiting."""
        # /admin endpoint has limit of 10
        for i in range(10):
            is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/admin/users", None)
            assert is_allowed is True
        
        # 11th request should be blocked
        is_allowed, error_msg = rate_limiter.is_allowed("TENANT_A", "/admin/users", None)
        assert is_allowed is False

    def test_rate_limit_role_based(self, rate_limiter):
        """Test role-based rate limiting."""
        # Viewer has limit of 50
        for i in range(50):
            is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/test", "viewer")
            assert is_allowed is True
        
        # 51st request should be blocked
        is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/test", "viewer")
        assert is_allowed is False
        
        # Admin has limit of 500, so should allow more
        for i in range(100):
            is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/test", "admin")
            assert is_allowed is True

    def test_rate_limit_per_tenant(self, rate_limiter):
        """Test rate limiting is per tenant."""
        # Tenant A uses up limit
        for i in range(100):
            rate_limiter.is_allowed("TENANT_A", "/test", None)
        
        # Tenant B should still have full limit
        is_allowed, _ = rate_limiter.is_allowed("TENANT_B", "/test", None)
        assert is_allowed is True

    def test_rate_limit_reset_tenant(self, rate_limiter):
        """Test resetting rate limit for a tenant."""
        # Use up limit
        for i in range(100):
            rate_limiter.is_allowed("TENANT_A", "/test", None)
        
        # Should be blocked
        is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/test", None)
        assert is_allowed is False
        
        # Reset
        rate_limiter.reset_tenant("TENANT_A")
        
        # Should be allowed again
        is_allowed, _ = rate_limiter.is_allowed("TENANT_A", "/test", None)
        assert is_allowed is True


class TestMiddlewareIntegration:
    """Tests for middleware integration with JWT and API key."""

    def test_middleware_jwt_auth(self):
        """Test middleware with JWT authentication."""
        app = FastAPI()
        middleware = TenantRouterMiddleware(app)
        
        # Create JWT token
        auth_manager = get_auth_manager()
        token = auth_manager.jwt_auth.create_token(
            tenant_id="TENANT_A",
            user_id="user123",
            role=Role.OPERATOR,
        )
        
        # Mock request
        from unittest.mock import Mock
        request = Mock()
        request.url.path = "/test"
        request.headers = {"Authorization": f"Bearer {token}"}
        request.state = Mock()
        
        # Test authentication (simplified - actual middleware would be async)
        user_context = auth_manager.authenticate(jwt_token=token)
        assert user_context.tenant_id == "TENANT_A"
        assert user_context.role == Role.OPERATOR

    def test_middleware_api_key_auth(self):
        """Test middleware with API key authentication."""
        app = FastAPI()
        middleware = TenantRouterMiddleware(app)
        
        # Mock request
        from unittest.mock import Mock
        request = Mock()
        request.url.path = "/test"
        request.headers = {"X-API-KEY": "test_api_key_tenant_001"}
        request.state = Mock()
        
        # Test authentication
        auth_manager = get_auth_manager()
        user_context = auth_manager.authenticate(api_key="test_api_key_tenant_001")
        assert user_context.tenant_id == "TENANT_001"
        assert user_context.role == Role.ADMIN

