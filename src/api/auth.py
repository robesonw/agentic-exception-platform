"""
API Key authentication for FastAPI.
Matches specification from docs/08-security-compliance.md and phase1-mvp-issues.md Issues 1 & 2.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class AuthenticationError(Exception):
    """Raised when authentication fails."""

    pass


class APIKeyAuth:
    """
    API Key authentication manager.
    
    MVP uses simple in-memory mapping of API keys to tenant IDs.
    In production, this would use a secure database or external auth service.
    """

    def __init__(self):
        """Initialize API key authentication."""
        # In-memory mapping: api_key -> tenant_id
        # In production, this would be stored securely (e.g., encrypted database)
        self._api_keys: dict[str, str] = {}
        
        # Initialize with some sample API keys for MVP
        # In production, these would be generated securely and stored in a database
        self._api_keys["test_api_key_tenant_001"] = "TENANT_001"
        self._api_keys["test_api_key_tenant_002"] = "TENANT_002"
        self._api_keys["test_api_key_tenant_finance"] = "TENANT_FINANCE_001"
        self._api_keys["test_api_key_tenant_healthcare"] = "TENANT_HEALTHCARE_001"

    def register_api_key(self, api_key: str, tenant_id: str) -> None:
        """
        Register an API key for a tenant.
        
        Args:
            api_key: API key string
            tenant_id: Tenant identifier
        """
        self._api_keys[api_key] = tenant_id
        logger.info(f"Registered API key for tenant {tenant_id}")

    def revoke_api_key(self, api_key: str) -> None:
        """
        Revoke an API key.
        
        Args:
            api_key: API key to revoke
        """
        if api_key in self._api_keys:
            tenant_id = self._api_keys.pop(api_key)
            logger.info(f"Revoked API key for tenant {tenant_id}")

    def get_tenant_id(self, api_key: str) -> Optional[str]:
        """
        Get tenant ID for an API key.
        
        Args:
            api_key: API key string
            
        Returns:
            Tenant ID if API key is valid, None otherwise
        """
        return self._api_keys.get(api_key)

    def validate_api_key(self, api_key: str) -> str:
        """
        Validate API key and return tenant ID.
        
        Args:
            api_key: API key string
            
        Returns:
            Tenant ID if valid
            
        Raises:
            AuthenticationError: If API key is invalid
        """
        if not api_key:
            raise AuthenticationError("API key is required")
        
        tenant_id = self.get_tenant_id(api_key)
        if tenant_id is None:
            # Securely log auth failure (don't log the actual key)
            logger.warning("Authentication failed: Invalid API key provided")
            raise AuthenticationError("Invalid API key")
        
        return tenant_id

    def list_tenants(self) -> list[str]:
        """
        List all tenant IDs with registered API keys.
        
        Returns:
            List of tenant IDs
        """
        return list(set(self._api_keys.values()))


# Global singleton instance
_api_key_auth: Optional[APIKeyAuth] = None


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

