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

from src.api.auth import AuthenticationError, get_api_key_auth

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Simple per-tenant rate limiter (stub for MVP).
    
    Tracks requests per minute per tenant.
    In production, this would use Redis or similar distributed cache.
    """

    def __init__(self, requests_per_minute: int = 100):
        """
        Initialize rate limiter.
        
        Args:
            requests_per_minute: Maximum requests per minute per tenant
        """
        self.requests_per_minute = requests_per_minute
        # Structure: {tenant_id: [(timestamp, ...), ...]}
        self._request_timestamps: dict[str, list[float]] = defaultdict(list)

    def is_allowed(self, tenant_id: str) -> tuple[bool, Optional[str]]:
        """
        Check if request is allowed for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Tuple of (is_allowed, error_message)
        """
        current_time = time.time()
        one_minute_ago = current_time - 60.0
        
        # Clean old timestamps (older than 1 minute)
        timestamps = self._request_timestamps[tenant_id]
        timestamps[:] = [ts for ts in timestamps if ts > one_minute_ago]
        
        # Check if limit exceeded
        if len(timestamps) >= self.requests_per_minute:
            return False, f"Rate limit exceeded: {self.requests_per_minute} requests per minute"
        
        # Record this request
        timestamps.append(current_time)
        
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
        _rate_limiter = RateLimiter()
    return _rate_limiter


class TenantRouterMiddleware(BaseHTTPMiddleware):
    """
    Middleware for tenant routing and authentication.
    
    Responsibilities:
    - Extract API key from X-API-KEY header
    - Validate API key and get tenant ID
    - Attach tenant ID to request.state.tenant_id
    - Enforce rate limiting per tenant
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
        self.api_key_auth = get_api_key_auth()
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
        
        # Extract API key from header
        api_key = request.headers.get("X-API-KEY")
        
        if not api_key:
            logger.warning(f"Authentication failed: Missing X-API-KEY header for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Missing X-API-KEY header"},
            )
        
        # Validate API key and get tenant ID
        try:
            tenant_id = self.api_key_auth.validate_api_key(api_key)
        except AuthenticationError as e:
            logger.warning(f"Authentication failed: {str(e)} for {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": str(e)},
            )
        
        # Check rate limiting
        is_allowed, error_msg = self.rate_limiter.is_allowed(tenant_id)
        if not is_allowed:
            logger.warning(f"Rate limit exceeded for tenant {tenant_id} on {request.url.path}")
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": error_msg},
            )
        
        # Attach tenant ID to request state
        request.state.tenant_id = tenant_id
        
        # Process request
        response = await call_next(request)
        
        return response

