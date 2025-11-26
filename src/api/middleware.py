"""
Tenant router middleware for FastAPI.
Extracts tenant ID from authentication and enforces tenant isolation.
Matches specification from docs/08-security-compliance.md and phase1-mvp-issues.md Issues 1 & 2.
"""

import logging
import time
from collections import defaultdict
from typing import Callable, Optional

from fastapi import Request, Response, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.api.auth import (
    AuthManager,
    AuthenticationError,
    AuthorizationError,
    get_api_key_auth,
    get_auth_manager,
    Role,
    UserContext,
)

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Enhanced rate limiter with per-endpoint and per-role limits.
    
    Phase 2: Real implementation with configurable limits per endpoint and role.
    In production, this would use Redis or similar distributed cache.
    """

    def __init__(
        self,
        default_requests_per_minute: int = 100,
        endpoint_limits: Optional[dict[str, int]] = None,
        role_limits: Optional[dict[str, int]] = None,
    ):
        """
        Initialize rate limiter.
        
        Args:
            default_requests_per_minute: Default requests per minute per tenant
            endpoint_limits: Optional dict mapping endpoint patterns to limits
            role_limits: Optional dict mapping roles to limits
        """
        self.default_requests_per_minute = default_requests_per_minute
        self.endpoint_limits = endpoint_limits or {}
        self.role_limits = role_limits or {
            "viewer": 50,  # Viewers have lower limits
            "operator": 200,  # Operators have higher limits
            "admin": 500,  # Admins have highest limits
        }
        # Structure: {tenant_id: {endpoint: [(timestamp, ...), ...]}}
        self._request_timestamps: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))

    def get_limit_for_request(self, endpoint: str, role: Optional[str] = None) -> int:
        """
        Get rate limit for a specific request.
        
        Args:
            endpoint: Request endpoint path
            role: Optional user role
            
        Returns:
            Rate limit (requests per minute)
        """
        # Check endpoint-specific limit first
        for pattern, limit in self.endpoint_limits.items():
            if endpoint.startswith(pattern):
                return limit
        
        # Check role-specific limit
        if role and role in self.role_limits:
            return self.role_limits[role]
        
        # Default limit
        return self.default_requests_per_minute

    def is_allowed(
        self, tenant_id: str, endpoint: str, role: Optional[str] = None
    ) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed for tenant and endpoint.
        
        Args:
            tenant_id: Tenant identifier
            endpoint: Request endpoint path
            role: Optional user role
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        limit = self.get_limit_for_request(endpoint, role)
        current_time = time.time()
        one_minute_ago = current_time - 60.0
        
        # Get timestamps for this tenant and endpoint
        endpoint_timestamps = self._request_timestamps[tenant_id][endpoint]
        
        # Clean old timestamps (older than 1 minute)
        endpoint_timestamps[:] = [ts for ts in endpoint_timestamps if ts > one_minute_ago]
        
        # Check if limit exceeded
        if len(endpoint_timestamps) >= limit:
            return (
                False,
                f"Rate limit exceeded: {limit} requests per minute for {endpoint}",
            )
        
        # Record this request
        endpoint_timestamps.append(current_time)
        
        return True, None

    def reset_tenant(self, tenant_id: str) -> None:
        """
        Reset rate limit for a tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        self._request_timestamps.pop(tenant_id, None)


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """
    Get the global rate limiter instance.
    
    Returns:
        RateLimiter instance
    """
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            default_requests_per_minute=100,
            endpoint_limits={"/admin": 10, "/metrics": 50},
            role_limits={"viewer": 50, "operator": 200, "admin": 500},
        )
    return _rate_limiter


class TenantRouterMiddleware(BaseHTTPMiddleware):
    """
    Enhanced middleware for tenant routing and authentication.
    
    Phase 2: Supports both API key and JWT authentication with RBAC.
    
    Responsibilities:
    - Extract API key from X-API-KEY header OR JWT from Authorization header
    - Validate credentials and get tenant ID and role
    - Attach tenant ID and user context to request.state
    - Enforce rate limiting per tenant/endpoint/role
    - Log authentication failures securely
    """

    def __init__(self, app, exclude_paths: list[str] | None = None):
        """
        Initialize middleware.
        
        Args:
            app: FastAPI application
            exclude_paths: List of paths to exclude from authentication (e.g., /health, /docs)
        """
        super().__init__(app)
        self.exclude_paths = exclude_paths or ["/health", "/docs", "/openapi.json", "/redoc"]
        self.auth_manager = get_auth_manager()
        self.rate_limiter = get_rate_limiter()

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request through middleware.
        
        Args:
            request: FastAPI request
            call_next: Next middleware/handler
            
        Returns:
            Response
        """
        # Skip authentication for excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Extract authentication credentials
        api_key = request.headers.get("X-API-KEY")
        jwt_token = None
        
        # Extract JWT from Authorization header (Bearer token)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            jwt_token = auth_header[7:]  # Remove "Bearer " prefix
        
        # Authenticate
        try:
            user_context = self.auth_manager.authenticate(api_key=api_key, jwt_token=jwt_token)
        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {str(e)} for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": str(e)},
            )
        
        # Check rate limiting (with role-based limits)
        is_allowed, error_msg = self.rate_limiter.is_allowed(
            tenant_id=user_context.tenant_id,
            endpoint=request.url.path,
            role=user_context.role.value,
        )
        if not is_allowed:
            logger.warning(
                f"Rate limit exceeded for tenant {user_context.tenant_id} "
                f"(role: {user_context.role.value}) on {request.url.path}"
            )
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": error_msg},
            )
        
        # Attach tenant ID and user context to request state
        request.state.tenant_id = user_context.tenant_id
        request.state.user_context = user_context
        
        # Process request
        response = await call_next(request)
        
        return response

