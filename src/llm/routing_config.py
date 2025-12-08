"""
LLM Routing Configuration Loader for Phase 5 - LLM Routing.

Provides configuration loading from YAML/JSON files for domain/tenant-aware
LLM provider and model routing.

Reference: docs/phase5-llm-routing.md Section 2 (Config-driven routing)
"""

import json
import logging
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)

# Global cache for loaded routing config
_routing_config_cache: Optional["LLMRoutingConfig"] = None
_routing_config_path: Optional[str] = None


class DomainRoutingConfig(BaseModel):
    """
    Routing configuration for a specific domain.
    
    Attributes:
        provider: LLM provider name (e.g., "openrouter", "openai", "dummy")
        model: Model identifier (e.g., "gpt-4.1-mini", "openrouter:gpt-4.1-mini")
        fallback_chain: Optional list of provider names for fallback chain (e.g., ["openrouter", "openai", "dummy"])
    """
    
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider name (optional, inherits from global default if not specified)",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier (optional, uses default if not specified)",
    )
    fallback_chain: Optional[list[str]] = Field(
        default=None,
        description="Optional fallback chain of provider names (e.g., ['openrouter', 'openai', 'dummy'])",
    )


class TenantRoutingConfig(BaseModel):
    """
    Routing configuration for a specific tenant.
    
    Attributes:
        provider: LLM provider name (e.g., "openrouter", "openai", "dummy")
        model: Model identifier (e.g., "gpt-4.1-mini", "openrouter:gpt-4.1-mini")
        fallback_chain: Optional list of provider names for fallback chain (e.g., ["openrouter", "openai", "dummy"])
    """
    
    provider: Optional[str] = Field(
        default=None,
        description="LLM provider name (optional, inherits from domain/global if not specified)",
    )
    model: Optional[str] = Field(
        default=None,
        description="Model identifier (optional, uses default if not specified)",
    )
    fallback_chain: Optional[list[str]] = Field(
        default=None,
        description="Optional fallback chain of provider names (e.g., ['openrouter', 'openai', 'dummy'])",
    )


class LLMRoutingConfig(BaseModel):
    """
    LLM routing configuration model.
    
    Supports configuration at multiple levels:
    - Global defaults (default_provider, default_model)
    - Domain-specific overrides (domains)
    - Tenant-specific overrides (tenants)
    
    Precedence: tenant > domain > global defaults
    
    Attributes:
        default_provider: Default LLM provider name (optional)
        default_model: Default model identifier (optional)
        domains: Domain-specific routing configs (optional)
        tenants: Tenant-specific routing configs (optional)
    """
    
    default_provider: Optional[str] = Field(
        default=None,
        description="Default LLM provider name (e.g., 'openrouter', 'openai', 'dummy')",
    )
    default_model: Optional[str] = Field(
        default=None,
        description="Default model identifier (e.g., 'gpt-4.1-mini', 'openrouter:gpt-4.1-mini')",
    )
    default_fallback_chain: Optional[list[str]] = Field(
        default=None,
        description="Default fallback chain of provider names (e.g., ['openrouter', 'openai', 'dummy'])",
    )
    domains: Optional[dict[str, DomainRoutingConfig]] = Field(
        default=None,
        description="Domain-specific routing configurations (key: domain name, value: routing config)",
    )
    tenants: Optional[dict[str, TenantRoutingConfig]] = Field(
        default=None,
        description="Tenant-specific routing configurations (key: tenant ID, value: routing config)",
    )
    
    @field_validator("default_provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        """Validate provider name."""
        if v is not None:
            v = v.lower().strip()
            # Basic validation - can be extended later
            if not v:
                raise ValueError("Provider name cannot be empty")
        return v
    
    @field_validator("domains")
    @classmethod
    def validate_domains(cls, v: Optional[dict[str, DomainRoutingConfig]]) -> Optional[dict[str, DomainRoutingConfig]]:
        """Validate domains dictionary."""
        if v is not None:
            # Ensure all values are DomainRoutingConfig instances
            for domain_name, config in v.items():
                if not isinstance(config, DomainRoutingConfig):
                    # Try to convert dict to DomainRoutingConfig
                    if isinstance(config, dict):
                        v[domain_name] = DomainRoutingConfig(**config)
                    else:
                        raise ValueError(f"Invalid domain config for '{domain_name}': expected dict or DomainRoutingConfig")
        return v
    
    @field_validator("tenants")
    @classmethod
    def validate_tenants(cls, v: Optional[dict[str, TenantRoutingConfig]]) -> Optional[dict[str, TenantRoutingConfig]]:
        """Validate tenants dictionary."""
        if v is not None:
            # Ensure all values are TenantRoutingConfig instances
            for tenant_id, config in v.items():
                if not isinstance(config, TenantRoutingConfig):
                    # Try to convert dict to TenantRoutingConfig
                    if isinstance(config, dict):
                        v[tenant_id] = TenantRoutingConfig(**config)
                    else:
                        raise ValueError(f"Invalid tenant config for '{tenant_id}': expected dict or TenantRoutingConfig")
        return v
    
    def get_domain_provider(self, domain: str) -> Optional[str]:
        """
        Get provider for a specific domain.
        
        Args:
            domain: Domain name to look up
        
        Returns:
            Provider name if domain-specific config exists, None otherwise
        """
        if not self.domains or not domain:
            return None
        
        domain_config = self.domains.get(domain)
        if domain_config:
            return domain_config.provider
        
        return None
    
    def get_domain_model(self, domain: str) -> Optional[str]:
        """
        Get model for a specific domain.
        
        Args:
            domain: Domain name to look up
        
        Returns:
            Model identifier if domain-specific config exists, None otherwise
        """
        if not self.domains or not domain:
            return None
        
        domain_config = self.domains.get(domain)
        if domain_config:
            return domain_config.model
        
        return None
    
    def get_tenant_provider(self, tenant_id: str) -> Optional[str]:
        """
        Get provider for a specific tenant.
        
        Args:
            tenant_id: Tenant ID to look up
        
        Returns:
            Provider name if tenant-specific config exists, None otherwise
        """
        if not self.tenants or not tenant_id:
            return None
        
        tenant_config = self.tenants.get(tenant_id)
        if tenant_config:
            return tenant_config.provider
        
        return None
    
    def get_tenant_model(self, tenant_id: str) -> Optional[str]:
        """
        Get model for a specific tenant.
        
        Args:
            tenant_id: Tenant ID to look up
        
        Returns:
            Model identifier if tenant-specific config exists, None otherwise
        """
        if not self.tenants or not tenant_id:
            return None
        
        tenant_config = self.tenants.get(tenant_id)
        if tenant_config:
            return tenant_config.model
        
        return None
    
    def get_tenant_provider_and_model(self, tenant_id: str) -> tuple[Optional[str], Optional[str]]:
        """
        Get both provider and model for a specific tenant in a single call.
        
        This is a convenience method that returns both values together,
        which is useful for tenant-aware routing where both values are
        typically needed together.
        
        Args:
            tenant_id: Tenant ID to look up
        
        Returns:
            Tuple of (provider, model) where both can be None if tenant
            config doesn't exist or doesn't specify these values.
            Returns (None, None) if tenant_id is empty or tenants dict is empty.
        
        Example:
            provider, model = config.get_tenant_provider_and_model("TENANT_001")
            if provider:
                # Use tenant-specific provider
        """
        if not self.tenants or not tenant_id:
            return (None, None)
        
        tenant_config = self.tenants.get(tenant_id)
        if tenant_config:
            return (tenant_config.provider, tenant_config.model)
        
        return (None, None)
    
    def get_fallback_chain(self, domain: Optional[str] = None, tenant_id: Optional[str] = None) -> list[str]:
        """
        Get fallback chain for a given domain and tenant.
        
        Precedence: tenant-level chain > domain-level chain > global default chain > ["dummy"]
        
        Args:
            domain: Optional domain name
            tenant_id: Optional tenant ID
        
        Returns:
            List of provider names in fallback order (e.g., ["openrouter", "openai", "dummy"])
        
        Example:
            # Tenant-level chain overrides domain-level
            config.get_fallback_chain(domain="Finance", tenant_id="TENANT_001")
            # Returns tenant's fallback_chain if defined, else domain's, else default, else ["dummy"]
        """
        # Check tenant-level fallback chain first (highest precedence)
        if tenant_id and self.tenants:
            tenant_config = self.tenants.get(tenant_id)
            if tenant_config and tenant_config.fallback_chain:
                return tenant_config.fallback_chain
        
        # Check domain-level fallback chain
        if domain and self.domains:
            domain_config = self.domains.get(domain)
            if domain_config and domain_config.fallback_chain:
                return domain_config.fallback_chain
        
        # Check global default fallback chain
        if self.default_fallback_chain:
            return self.default_fallback_chain
        
        # Default: return ["dummy"] if no chain is defined
        return ["dummy"]


def load_routing_config(path: Optional[str] = None) -> Optional[LLMRoutingConfig]:
    """
    Load LLM routing configuration from YAML or JSON file.
    
    Supports:
    - YAML files (.yaml, .yml) via PyYAML
    - JSON files (.json) via standard json module
    - Automatic format detection based on file extension
    
    Args:
        path: Path to configuration file. If None, returns None.
              If file doesn't exist, returns None with warning logged.
    
    Returns:
        LLMRoutingConfig instance if file exists and is valid, None otherwise.
        Returns None if:
        - path is None
        - file doesn't exist
        - file format is invalid (not .yaml/.yml/.json)
        - YAML/JSON parsing fails
        - Pydantic validation fails
    
    Example:
        # Load from file
        config = load_routing_config("/path/to/llm-routing.yaml")
        
        # Returns None if file doesn't exist (logs warning)
        config = load_routing_config("/path/to/missing.yaml")  # Returns None
    """
    global _routing_config_cache, _routing_config_path
    
    # If path is None, return None
    if path is None:
        return None
    
    # Check if we've already loaded this config (cache hit)
    if _routing_config_cache is not None and _routing_config_path == path:
        logger.debug(f"Using cached routing config from: {path}")
        return _routing_config_cache
    
    # Resolve file path
    file_path = Path(path)
    
    # Check if file exists
    if not file_path.exists():
        logger.warning(f"LLM routing config file not found: {path}")
        return None
    
    # Check if it's a file (not a directory)
    if not file_path.is_file():
        logger.warning(f"LLM routing config path is not a file: {path}")
        return None
    
    # Infer parser from extension
    extension = file_path.suffix.lower()
    
    # Load file content
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            if extension == ".json":
                try:
                    data = json.load(f)
                except json.JSONDecodeError as e:
                    logger.error(
                        f"Invalid JSON in LLM routing config file '{path}': {e}",
                        exc_info=True,
                    )
                    return None
            elif extension in (".yaml", ".yml"):
                try:
                    data = yaml.safe_load(f)
                    if data is None:
                        logger.warning(f"LLM routing config file '{path}' is empty or contains only null")
                        return None
                except yaml.YAMLError as e:
                    logger.error(
                        f"Invalid YAML in LLM routing config file '{path}': {e}",
                        exc_info=True,
                    )
                    return None
            else:
                logger.warning(
                    f"Unsupported file extension '{extension}' for LLM routing config. "
                    f"Supported: .json, .yaml, .yml"
                )
                return None
    except IOError as e:
        logger.error(
            f"Error reading LLM routing config file '{path}': {e}",
            exc_info=True,
        )
        return None
    
    # Validate and parse with Pydantic
    try:
        config = LLMRoutingConfig.model_validate(data)
        logger.info(f"Successfully loaded LLM routing config from: {path}")
        
        # Cache the config
        _routing_config_cache = config
        _routing_config_path = path
        
        return config
    except Exception as e:
        logger.error(
            f"Validation error in LLM routing config file '{path}': {e}",
            exc_info=True,
        )
        return None


def clear_routing_config_cache() -> None:
    """
    Clear the cached routing configuration.
    
    Useful for testing or when config file is updated and needs to be reloaded.
    """
    global _routing_config_cache, _routing_config_path
    _routing_config_cache = None
    _routing_config_path = None
    logger.debug("Cleared LLM routing config cache")


def get_routing_config() -> Optional[LLMRoutingConfig]:
    """
    Get the currently cached routing configuration.
    
    Returns:
        Cached LLMRoutingConfig if available, None otherwise.
    """
    return _routing_config_cache

