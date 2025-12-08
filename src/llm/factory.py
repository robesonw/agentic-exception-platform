"""
LLM Provider Factory for Phase 5 - AI Co-Pilot.

Provides factory function to create LLM client instances based on environment
configuration. Supports multiple providers with environment-driven selection.

Reference: docs/phase5-copilot-mvp.md Section 5.1 (Factory - env: LLM_PROVIDER, LLM_MODEL, LLM_API_KEY)
Reference: docs/phase5-llm-routing.md Section 2 (Config-driven routing)
"""

import logging
import os
from typing import Optional

from src.llm.base import LLMClient
from src.llm.dummy_llm import DummyLLMClient
from src.llm.metrics import record_provider_selection, routing_latency_timer
from src.llm.registry import ProviderConfigEntry, ProviderKey, registry
from src.llm.routing_config import (
    clear_routing_config_cache,
    get_routing_config,
    load_routing_config,
)
from src.llm.utils import mask_secret

logger = logging.getLogger(__name__)

# Global cache for routing config (loaded once on first use)
_routing_config_loaded = False

# Supported provider names
SUPPORTED_PROVIDERS = {"dummy", "openrouter", "openai"}


class LLMProviderError(Exception):
    """Raised when LLM provider operations fail."""

    pass


class OpenAILLMClient:
    """
    OpenAI LLM client placeholder for Phase 5 Co-Pilot.
    
    This is a placeholder implementation that does NOT make real API calls yet.
    It implements the LLMClient Protocol and returns mock responses.
    
    TODO: Implement actual OpenAI API integration in future phase.
    
    Reference: docs/phase5-copilot-mvp.md Section 5.1 (Factory)
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4"):
        """
        Initialize OpenAI LLM client placeholder.
        
        Args:
            api_key: OpenAI API key (not used yet, placeholder)
            model: Model name (default: gpt-4)
        """
        self.api_key = api_key
        self.model = model
        logger.warning(
            "OpenAILLMClient is a placeholder - no real API calls made yet. "
            "Using mock responses."
        )

    async def generate(
        self, prompt: str, context: dict | None = None
    ) -> "LLMResponse":  # type: ignore
        """
        Generate a mock response (placeholder - no real API calls).
        
        Args:
            prompt: The prompt text
            context: Optional context dictionary
            
        Returns:
            LLMResponse with mock text (no real API call made)
        """
        from src.llm.base import LLMResponse

        # Placeholder: Return mock response
        # TODO: Implement actual OpenAI API call
        text = f"[OpenAI Placeholder] Mock response for model {self.model}: {prompt[:100]}"
        
        if context:
            tenant_id = context.get("tenant_id", "unknown")
            text += f" (tenant: {tenant_id})"
        
        raw_response = {
            "provider": "openai",
            "model": self.model,
            "api_key_set": self.api_key is not None,
            "prompt_length": len(prompt),
            "has_context": context is not None,
            "note": "This is a placeholder - no real API call was made",
        }
        
        return LLMResponse(text=text, raw=raw_response)


def load_llm_provider(
    domain: Optional[str] = None,
    tenant_id: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> LLMClient:
    """
    Load and return an LLM client instance based on configuration.
    
    Reads environment variables if parameters are not provided:
    - LLM_PROVIDER: Provider name ("dummy", "openrouter", "openai", etc.)
    - LLM_MODEL: Model name (e.g., "gpt-4", "gpt-3.5-turbo", "gpt-4.1-mini")
    - LLM_API_KEY: API key for the provider (if required)
    - OPENROUTER_API_KEY: OpenRouter-specific API key override (optional)
    - LLM_ROUTING_CONFIG_PATH: Path to YAML/JSON routing config file (optional)
    
    Tenant-aware routing (LR-2) with domain fallback (LR-1):
    - Precedence order: tenant > domain > explicit params > env vars > defaults
    - If tenant_id is provided, checks tenant-level mapping from routing config first.
    - If domain is provided, checks domain-level mapping as fallback.
    - Tenant-specific config overrides domain-specific config.
    - Falls back to explicit parameters, then env vars, then defaults.
    
    Domain Pack integration (LR-1): TODO - check Domain Pack for LLM preferences
    Tenant Policy Pack integration (LR-2): TODO - check Tenant Policy Pack for LLM preferences
    (will override routing config if present, e.g., for premium tiers)
    
    Args:
        domain: Optional domain name for domain-aware routing (LR-1).
                If provided, routing config will be checked for domain-specific settings.
        tenant_id: Optional tenant ID for tenant-aware routing (LR-2).
                   If provided, routing config will be checked for tenant-specific settings.
                   Tenant config takes precedence over domain config.
        provider: Optional provider name override. If None, resolved from routing config/env.
        model: Optional model name override. If None, resolved from routing config/env.
        api_key: Optional API key. If None, reads from LLM_API_KEY env var.
                 For OpenRouter, OPENROUTER_API_KEY takes precedence if set.
    
    Returns:
        LLMClient instance (implements LLMClient Protocol)
        Falls back to DummyLLMClient if configuration is invalid or missing.
    
    Example:
        # Use environment variables
        client = load_llm_provider()
        
        # Domain-aware routing
        client = load_llm_provider(domain="Finance")
        
        # Tenant-aware routing (overrides domain)
        client = load_llm_provider(domain="Finance", tenant_id="TENANT_FINANCE_001")
        
        # Explicit configuration
        client = load_llm_provider(
            provider="openrouter",
            model="gpt-4.1-mini",
            api_key="sk-or-v1-...",
            domain="Finance",
            tenant_id="TENANT_FINANCE_001"
        )
    """
    # Load routing config once (cached for subsequent calls)
    global _routing_config_loaded
    if not _routing_config_loaded:
        routing_config_path = os.getenv("LLM_ROUTING_CONFIG_PATH")
        if routing_config_path:
            routing_config = load_routing_config(routing_config_path)
            if routing_config:
                logger.info(
                    f"Loaded LLM routing config from: {routing_config_path}. "
                    f"Routing logic will be applied in LR-1/LR-2/LR-6."
                )
            else:
                logger.debug(
                    f"LLM routing config not loaded from: {routing_config_path} "
                    f"(file missing or invalid)"
                )
        _routing_config_loaded = True
    
    # Build ProviderKey for registry lookup (LR-7)
    provider_key = ProviderKey(tenant_id=tenant_id, domain=domain)
    
    # Check registry for cached client (LR-7)
    cached_client = registry.get_client(provider_key)
    if cached_client is not None:
        cached_config = registry.get_config(provider_key)
        logger.debug(
            f"Using cached LLM client from registry: key={provider_key}, "
            f"provider={cached_config.provider if cached_config else 'unknown'}, "
            f"model={cached_config.model if cached_config else 'unknown'}"
        )
        # Record metrics for cached client (LR-11)
        if cached_config:
            record_provider_selection(
                tenant_id=tenant_id,
                domain=domain,
                provider=cached_config.provider,
                model=cached_config.model,
            )
        return cached_client
    
    # Measure routing decision latency (LR-11)
    with routing_latency_timer(tenant_id=tenant_id, domain=domain):
        # Get routing config if available
        routing_config = get_routing_config()
        
        # Tenant-aware routing (LR-2) - highest precedence
    # Attempt to resolve tenant-specific provider/model from routing config
    tenant_provider = None
    tenant_model = None
    if routing_config and tenant_id:
        tenant_provider, tenant_model = routing_config.get_tenant_provider_and_model(tenant_id)
        
        if tenant_provider or tenant_model:
            logger.debug(
                f"Tenant-aware routing for tenant '{tenant_id}': "
                f"provider={tenant_provider}, model={tenant_model}"
            )
        
        # TODO (LR-2): Tenant Policy Pack integration
        # Check Tenant Policy Pack for LLM preferences (llm_provider, llm_model fields)
        # If Tenant Policy Pack has LLM preferences, they override routing config
        # This is useful for premium tiers or tenant-specific overrides
        # Example:
        #   tenant_policy = get_tenant_policy_pack(tenant_id)
        #   if tenant_policy and hasattr(tenant_policy, 'llm_preferences'):
        #       if tenant_policy.llm_preferences.provider:
        #           tenant_provider = tenant_policy.llm_preferences.provider
        #       if tenant_policy.llm_preferences.model:
        #           tenant_model = tenant_policy.llm_preferences.model
    
    # Domain-aware routing (LR-1) - fallback if no tenant config
    # Attempt to resolve domain-specific provider/model from routing config
    domain_provider = None
    domain_model = None
    if routing_config and domain:
        domain_provider = routing_config.get_domain_provider(domain)
        domain_model = routing_config.get_domain_model(domain)
        
        if domain_provider or domain_model:
            logger.debug(
                f"Domain-aware routing for domain '{domain}': "
                f"provider={domain_provider}, model={domain_model}"
            )
        
        # TODO (LR-1): Domain Pack integration
        # Check Domain Pack for LLM preferences (llm_provider, llm_model fields)
        # If Domain Pack has LLM preferences, they override routing config
        # Example:
        #   domain_pack = get_domain_pack(domain)
        #   if domain_pack and hasattr(domain_pack, 'llm_preferences'):
        #       if domain_pack.llm_preferences.provider:
        #           domain_provider = domain_pack.llm_preferences.provider
        #       if domain_pack.llm_preferences.model:
        #           domain_model = domain_pack.llm_preferences.model
    
    # Resolve effective provider and model with precedence: tenant > domain > explicit > env > defaults
    # Tenant config overrides domain config, which overrides explicit params, etc.
    effective_provider = tenant_provider or domain_provider or provider or os.getenv("LLM_PROVIDER")
    effective_model = tenant_model or domain_model or model or os.getenv("LLM_MODEL")
    
    # Initialize effective_model to None if not set (will be set per-provider later)
    if effective_model is None:
        effective_model = None  # Will be set based on provider defaults
    
    # For API key, check provider-specific env var first, then generic one
    if not api_key:
        # Check for provider-specific API key (e.g., OPENROUTER_API_KEY)
        openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
        if openrouter_api_key:
            api_key = openrouter_api_key
        else:
            # Fall back to generic LLM_API_KEY
            api_key = os.getenv("LLM_API_KEY")
    
    # Default to "dummy" if no provider specified
    if not effective_provider:
        effective_provider = "dummy"
        logger.info("No LLM_PROVIDER specified, defaulting to 'dummy'")
    
    # Normalize provider name (lowercase, strip whitespace)
    effective_provider = effective_provider.lower().strip()
    
    # Log resolved configuration with structured logging (LR-11)
    logger.info(
        "llm_routing_decision",
        extra={
            "tenant_id": tenant_id or "unknown",
            "domain": domain or "unknown",
            "provider": effective_provider,
            "model": effective_model or "unknown",
            "source": "routing_factory",
        }
    )
    
    logger.debug(
        f"Resolved LLM configuration: provider={effective_provider}, "
        f"model={effective_model}, domain={domain}, tenant_id={tenant_id}"
    )
    
    # Validate provider name - if invalid, log warning and fall back to dummy
    if effective_provider not in SUPPORTED_PROVIDERS:
        logger.warning(
            f"Unsupported provider: {effective_provider}. "
            f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}. "
            f"Falling back to DummyLLMClient."
        )
        return DummyLLMClient()
    
    # Create appropriate client based on effective provider
    try:
        client: Optional[LLMClient] = None
        final_model: Optional[str] = effective_model  # Track final model used
        
        if effective_provider == "dummy":
            logger.debug("Creating DummyLLMClient")
            final_model = final_model or "dummy-model"
            client = DummyLLMClient()
        
        elif effective_provider == "openrouter":
            # Validate that api_key is set
            if not api_key:
                logger.warning(
                    "OpenRouter provider requires API key but none was provided. "
                    "Set LLM_API_KEY or OPENROUTER_API_KEY environment variable. "
                    "Falling back to DummyLLMClient."
                )
                final_model = "dummy-model"
                client = DummyLLMClient()
            else:
                # Use effective model or default
                final_model = effective_model or "gpt-4.1-mini"
                
                # Import OpenRouter client and config
                from src.llm.openrouter_llm import OpenRouterConfig, OpenRouterLLMClient
                
                # Construct OpenRouterConfig
                config = OpenRouterConfig(
                    api_key=api_key,
                    model=final_model,
                )
                
                # Log configuration without exposing API key
                logger.debug(
                    f"Creating OpenRouterLLMClient with model: {final_model}, "
                    f"api_key={mask_secret(api_key)}"
                )
                client = OpenRouterLLMClient(config)
        
        elif effective_provider == "openai":
            # Use effective model or default
            final_model = effective_model or "gpt-4"
            # Log configuration without exposing API key
            logger.debug(
                f"Creating OpenAILLMClient (placeholder) with model: {final_model}, "
                f"api_key={mask_secret(api_key)}"
            )
            client = OpenAILLMClient(api_key=api_key, model=final_model)
        
        else:
            # This should never happen due to validation above, but included for safety
            logger.warning(
                f"Provider implementation not found: {effective_provider}. "
                f"Falling back to DummyLLMClient."
            )
            final_model = "dummy-model"
            client = DummyLLMClient()
        
        # Cache the client in registry (LR-7)
        if client is not None:
            config_entry = ProviderConfigEntry(
                provider=effective_provider,
                model=final_model or "unknown",
                version=registry.get_global_version(),
            )
            try:
                registry.set_client(provider_key, config_entry, client)
            except Exception as e:
                # Log but don't fail if caching fails
                logger.warning(
                    f"Failed to cache LLM client in registry: {e}. "
                    f"Continuing without cache."
                )
            
            # Record provider selection metric (LR-11)
            record_provider_selection(
                tenant_id=tenant_id,
                domain=domain,
                provider=effective_provider,
                model=final_model or "unknown",
            )
        
        return client
    
    except Exception as e:
        # Catch any unexpected errors during client creation
        logger.warning(
            f"Error creating LLM client for provider '{effective_provider}': {e}. "
            f"Falling back to DummyLLMClient.",
            exc_info=True
        )
        return DummyLLMClient()


def reload_llm_routing_config() -> None:
    """
    Hot-reload LLM routing configuration and invalidate cached clients.
    
    This function:
    1. Reloads the routing configuration from the file specified in LLM_ROUTING_CONFIG_PATH
    2. Invalidates all cached clients in the registry
    3. Bumps the global version to track the configuration change
    
    After calling this function, subsequent calls to load_llm_provider() will:
    - Use the newly loaded routing configuration
    - Create new client instances (not from cache)
    - Cache the new clients with the updated version
    
    This is useful for:
    - Updating routing configuration without restarting the application
    - Testing configuration changes
    - Responding to configuration file updates
    
    Note: This is a Phase 5 in-memory implementation. Future phases may support
    distributed cache invalidation across multiple instances.
    
    Example:
        # Reload configuration after updating llm-routing.yaml
        reload_llm_routing_config()
        
        # Next call to load_llm_provider() will use new config
        client = load_llm_provider(domain="Finance", tenant_id="TENANT_001")
    
    TODO (Future phases): Wire this to admin API or CLI trigger
    TODO (Future phases): Support distributed cache invalidation
    """
    global _routing_config_loaded
    
    routing_config_path = os.getenv("LLM_ROUTING_CONFIG_PATH")
    if routing_config_path:
        logger.info(f"Reloading LLM routing config from: {routing_config_path}")
        routing_config = load_routing_config(routing_config_path)
        if routing_config:
            logger.info(
                f"Successfully reloaded LLM routing config. "
                f"Invalidating cached clients."
            )
        else:
            logger.warning(
                f"Failed to reload LLM routing config from: {routing_config_path}"
            )
    else:
        logger.debug("No LLM_ROUTING_CONFIG_PATH set, skipping config reload")
    
    # Clear routing config cache
    clear_routing_config_cache()
    
    # Invalidate all cached clients
    registry.invalidate(None)
    
    # Bump global version to track configuration change
    new_version = registry.bump_global_version()
    logger.info(f"LLM routing config reloaded. Global version: {new_version}")
    
    # Reset routing config loaded flag so it can be reloaded on next use
    _routing_config_loaded = False

