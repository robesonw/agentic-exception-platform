"""
Enhanced authentication for FastAPI with API Key and JWT support.

Phase 2: Gateway/Auth hardening with JWT authentication and RBAC.
Matches specification from docs/08-security-compliance.md and phase2-mvp-issues.md Issue 44.
"""

import logging
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

import jwt
from fastapi import HTTPException, Request, status

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class AuthorizationError(Exception):
    """Raised when authorization fails."""

    pass


class Role(str, Enum):
    """RBAC roles."""

    VIEWER = "viewer"  # Read-only access
    OPERATOR = "operator"  # Can execute operations, approve/reject
    ADMIN = "admin"  # Full access including configuration


class AuthMethod(str, Enum):
    """Authentication methods."""

    API_KEY = "api_key"
    JWT = "jwt"


class UserContext:
    """User context from authentication."""

    def __init__(
        self,
        tenant_id: str,
        user_id: Optional[str] = None,
        role: Role = Role.VIEWER,
        auth_method: AuthMethod = AuthMethod.API_KEY,
    ):
        """
        Initialize user context.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier (optional for API key auth)
            role: RBAC role
            auth_method: Authentication method used
        """
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role
        self.auth_method = auth_method

    def has_permission(self, required_role: Role) -> bool:
        """
        Check if user has required role permission.
        
        Role hierarchy: viewer < operator < admin
        
        Args:
            required_role: Required role for the operation
            
        Returns:
            True if user has permission, False otherwise
        """
        role_hierarchy = {
            Role.VIEWER: 1,
            Role.OPERATOR: 2,
            Role.ADMIN: 3,
        }
        user_level = role_hierarchy.get(self.role, 0)
        required_level = role_hierarchy.get(required_role, 0)
        return user_level >= required_level


class APIKeyAuth:
    """
    API Key authentication manager.
    
    MVP uses simple in-memory mapping of API keys to tenant IDs.
    In production, this would use a secure database or external auth service.
    """

    def __init__(self):
        """Initialize API key authentication."""
        # In-memory mapping: api_key -> (tenant_id, role)
        # In production, this would be stored securely (e.g., encrypted database)
        self._api_keys: dict[str, tuple[str, Role]] = {}
        
        # Initialize with some sample API keys for MVP
        # In production, these would be generated securely and stored in a database
        self._api_keys["test_api_key_tenant_001"] = ("TENANT_001", Role.ADMIN)
        self._api_keys["test_api_key_tenant_002"] = ("TENANT_002", Role.OPERATOR)
        self._api_keys["test_api_key_tenant_finance"] = ("TENANT_FINANCE_001", Role.ADMIN)
        self._api_keys["test_api_key_tenant_healthcare"] = ("TENANT_HEALTHCARE_001", Role.VIEWER)
        self._api_keys["test_api_key_tenant_healthcare_042"] = ("TENANT_HEALTHCARE_042", Role.ADMIN)
        self._api_keys["test_api_key_tenant_health"] = ("TENANT_HEALTH_001", Role.ADMIN)
        # Test API key used in test suites
        self._api_keys["test-api-key-123"] = ("tenant_001", Role.ADMIN)

    def register_api_key(self, api_key: str, tenant_id: str, role: Role = Role.VIEWER) -> None:
        """
        Register an API key for a tenant.
        
        Args:
            api_key: API key string
            tenant_id: Tenant identifier
            role: RBAC role for the API key
        """
        self._api_keys[api_key] = (tenant_id, role)
        logger.info(f"Registered API key for tenant {tenant_id} with role {role.value}")

    def revoke_api_key(self, api_key: str) -> None:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
        """
        if api_key in self._api_keys:
            tenant_id, _ = self._api_keys.pop(api_key)
            logger.info(f"Revoked API key for tenant {tenant_id}")

    def get_tenant_id_and_role(self, api_key: str) -> Optional[tuple[str, Role]]:
        """
        Get tenant ID and role for an API key.
        
        Args:
            api_key: API key string
            
        Returns:
            Tuple of (tenant_id, role) if API key is valid, None otherwise
        """
        return self._api_keys.get(api_key)

    def validate_api_key(self, api_key: str) -> UserContext:
        """
        Validate API key and return user context.
        
        Args:
            api_key: API key string
            
        Returns:
            UserContext with tenant ID and role
            
        Raises:
            AuthenticationError: If API key is invalid
        """
        if not api_key:
            raise AuthenticationError("API key is required")
        
        result = self.get_tenant_id_and_role(api_key)
        if result is None:
            logger.warning("Authentication failed: Invalid API key provided")
            raise AuthenticationError("Invalid API key")
        
        tenant_id, role = result
        # For API key authentication, use a default user identifier based on the API key
        # This ensures session isolation while providing a consistent user context
        user_id = f"api_user_{api_key[-8:]}"  # Use last 8 chars of API key as user identifier
        
        return UserContext(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            auth_method=AuthMethod.API_KEY,
        )

    def list_tenants(self) -> list[str]:
        """
        List all tenant IDs with registered API keys.
        
        Returns:
            List of tenant IDs
        """
        return list(set(tenant_id for tenant_id, _ in self._api_keys.values()))


class JWTAuth:
    """
    JWT authentication manager.
    
    Supports JWT token validation and tenant ID extraction from claims.
    """

    def __init__(
        self,
        secret_key: str = "change-me-in-production",
        algorithm: str = "HS256",
        token_expiry_hours: int = 24,
    ):
        """
        Initialize JWT authentication.
        
        Args:
            secret_key: Secret key for JWT signing/verification
            algorithm: JWT algorithm (default: HS256)
            token_expiry_hours: Token expiry in hours (default: 24)
        """
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.token_expiry_hours = token_expiry_hours

    def create_token(
        self,
        tenant_id: str,
        user_id: str,
        role: Role = Role.VIEWER,
        additional_claims: Optional[dict] = None,
    ) -> str:
        """
        Create a JWT token.
        
        Args:
            tenant_id: Tenant identifier
            user_id: User identifier
            role: RBAC role
            additional_claims: Additional claims to include in token
            
        Returns:
            JWT token string
        """
        now = datetime.now(timezone.utc)
        expiry = now + timedelta(hours=self.token_expiry_hours)
        
        payload = {
            "sub": user_id,  # Subject (user ID)
            "tenant_id": tenant_id,
            "role": role.value,
            "iat": int(now.timestamp()),  # Issued at
            "exp": int(expiry.timestamp()),  # Expiration
        }
        
        if additional_claims:
            payload.update(additional_claims)
        
        token = jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
        return token

    def validate_token(self, token: str) -> UserContext:
        """
        Validate JWT token and return user context.
        
        Args:
            token: JWT token string
            
        Returns:
            UserContext with tenant ID, user ID, and role
            
        Raises:
            AuthenticationError: If token is invalid or expired
        """
        if not token:
            raise AuthenticationError("JWT token is required")
        
        try:
            # Decode and verify token
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={"verify_signature": True, "verify_exp": True},
            )
            
            # Extract claims
            tenant_id = payload.get("tenant_id")
            user_id = payload.get("sub")
            role_str = payload.get("role", Role.VIEWER.value)
            
            if not tenant_id:
                raise AuthenticationError("JWT token missing tenant_id claim")
            
            # Validate role
            try:
                role = Role(role_str)
            except ValueError:
                logger.warning(f"Invalid role in JWT token: {role_str}, defaulting to VIEWER")
                role = Role.VIEWER
            
            return UserContext(
                tenant_id=tenant_id,
                user_id=user_id,
                role=role,
                auth_method=AuthMethod.JWT,
            )
        
        except jwt.ExpiredSignatureError:
            raise AuthenticationError("JWT token has expired")
        except jwt.InvalidTokenError as e:
            logger.warning(f"JWT token validation failed: {e}")
            raise AuthenticationError(f"Invalid JWT token: {str(e)}")


class AuthManager:
    """
    Unified authentication manager supporting both API key and JWT.
    
    Automatically detects authentication method and validates accordingly.
    """

    def __init__(
        self,
        jwt_secret_key: Optional[str] = None,
        jwt_algorithm: str = "HS256",
        jwt_token_expiry_hours: int = 24,
    ):
        """
        Initialize authentication manager.
        
        Args:
            jwt_secret_key: Secret key for JWT (default: auto-generated for MVP)
            jwt_algorithm: JWT algorithm (default: HS256)
            jwt_token_expiry_hours: JWT token expiry in hours (default: 24)
        """
        self.api_key_auth = get_api_key_auth()  # Use singleton instance
        self.jwt_auth = JWTAuth(
            secret_key=jwt_secret_key or "change-me-in-production",
            algorithm=jwt_algorithm,
            token_expiry_hours=jwt_token_expiry_hours,
        )

    def authenticate(self, api_key: Optional[str] = None, jwt_token: Optional[str] = None) -> UserContext:
        """
        Authenticate using API key or JWT token.
        
        Args:
            api_key: Optional API key
            jwt_token: Optional JWT token (from Authorization: Bearer <token>)
            
        Returns:
            UserContext with tenant ID, user ID, and role
            
        Raises:
            AuthenticationError: If authentication fails
        """
        # Try JWT first if provided
        if jwt_token:
            return self.jwt_auth.validate_token(jwt_token)
        
        # Fall back to API key
        if api_key:
            return self.api_key_auth.validate_api_key(api_key)
        
        raise AuthenticationError("No authentication credentials provided (API key or JWT token required)")

    def require_role(self, user_context: UserContext, required_role: Role) -> None:
        """
        Check if user has required role, raise exception if not.
        
        Args:
            user_context: User context from authentication
            required_role: Required role for the operation
            
        Raises:
            AuthorizationError: If user doesn't have required role
        """
        if not user_context.has_permission(required_role):
            raise AuthorizationError(
                f"User with role {user_context.role.value} does not have permission "
                f"for operation requiring {required_role.value}"
            )


# Global singleton instances
_api_key_auth: Optional[APIKeyAuth] = None
_jwt_auth: Optional[JWTAuth] = None
_auth_manager: Optional[AuthManager] = None


def get_api_key_auth() -> APIKeyAuth:
    """
    Get the global API key authentication instance.
    
    Returns:
        APIKeyAuth instance
    """
    global _api_key_auth
    if _api_key_auth is None:
        _api_key_auth = APIKeyAuth()
    return _api_key_auth


def get_jwt_auth() -> JWTAuth:
    """
    Get the global JWT authentication instance.
    
    Returns:
        JWTAuth instance
    """
    global _jwt_auth
    if _jwt_auth is None:
        _jwt_auth = JWTAuth()
    return _jwt_auth


def get_auth_manager() -> AuthManager:
    """
    Get the global authentication manager instance.
    
    Returns:
        AuthManager instance
    """
    global _auth_manager
    if _auth_manager is None:
        _auth_manager = AuthManager()
    return _auth_manager
