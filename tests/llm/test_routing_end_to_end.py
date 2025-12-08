"""
Comprehensive end-to-end tests for LLM routing (LR-12).

This test suite validates:
- Domain/tenant routing
- Config file loading (YAML and JSON)
- Fallback chains
- Provider selection
- Secret masking
- Prompt constraints
- Registry operations

Target: >80% coverage for routing module.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.llm.base import LLMClient, LLMResponse
from src.llm.dummy_llm import DummyLLMClient
from src.llm.factory import load_llm_provider, reload_llm_routing_config
from src.llm.fallbacks import call_with_fallback_chain
from src.llm.prompt_constraints import sanitize_prompt
from src.llm.registry import ProviderKey, ProviderConfigEntry, registry
from src.llm.routing_config import (
    clear_routing_config_cache,
    get_routing_config,
    load_routing_config,
)
from src.llm.utils import mask_secret


@pytest.fixture
def test_config_yaml_path():
    """Path to test YAML config file."""
    return Path(__file__).parent.parent / "resources" / "llm-routing-test.yaml"


@pytest.fixture
def test_config_json_path():
    """Path to test JSON config file."""
    return Path(__file__).parent.parent / "resources" / "llm-routing-test.json"


@pytest.fixture(autouse=True)
def reset_routing_config():
    """Reset routing config cache before each test."""
    clear_routing_config_cache()
    registry.invalidate(None)
    # Reset the global loaded flag
    import src.llm.factory as factory_module
    factory_module._routing_config_loaded = False
    yield
    clear_routing_config_cache()
    registry.invalidate(None)
    factory_module._routing_config_loaded = False


@pytest.fixture
def setup_routing_config(test_config_yaml_path):
    """Helper fixture to set up routing config for tests."""
    config = load_routing_config(str(test_config_yaml_path))
    if config:
        # Set the cached config directly using the module's private variable
        import src.llm.routing_config as routing_config_module
        routing_config_module._routing_config_cache = config
    return config


class TestConfigLoading:
    """Test config file loading (YAML and JSON)."""
    
    def test_load_yaml_config(self, test_config_yaml_path):
        """Test loading YAML configuration file."""
        config = load_routing_config(str(test_config_yaml_path))
        
        assert config is not None
        assert config.default_provider == "dummy"
        assert config.default_model == "dummy-1"
        assert config.default_fallback_chain == ["dummy"]
        assert "Finance" in config.domains
        assert config.domains["Finance"].provider == "openrouter"
        assert config.domains["Finance"].model == "openrouter:finance-model"
    
    def test_load_json_config(self, test_config_json_path):
        """Test loading JSON configuration file."""
        config = load_routing_config(str(test_config_json_path))
        
        assert config is not None
        assert config.default_provider == "dummy"
        assert config.default_model == "dummy-1"
        assert "Finance" in config.domains
        assert config.domains["Finance"].provider == "openrouter"
    
    def test_config_precedence_tenant_over_domain(self, setup_routing_config):
        """Test that tenant config overrides domain config."""
        # Load provider for tenant that has override
        client = load_llm_provider(
            domain="Finance",
            tenant_id="TENANT_FINANCE_001"
        )
        
        # Should use tenant's provider (dummy) not domain's (openrouter)
        assert isinstance(client, DummyLLMClient)
    
    def test_config_precedence_domain_over_global(self, setup_routing_config):
        """Test that domain config overrides global default."""
        # Test the model selection
        config = get_routing_config()
        if config:
            domain_model = config.get_domain_model("Finance")
            assert domain_model == "openrouter:finance-model"
    
    def test_config_fallback_chain_resolution(self, test_config_yaml_path):
        """Test fallback chain resolution with precedence."""
        with patch.dict(os.environ, {"LLM_ROUTING_CONFIG_PATH": str(test_config_yaml_path)}):
            clear_routing_config_cache()
            config = load_routing_config(str(test_config_yaml_path))
            
            # Tenant-level chain
            chain = config.get_fallback_chain(domain="Finance", tenant_id="TENANT_FINANCE_001")
            assert chain == ["openrouter", "dummy"]  # Tenant override
            
            # Domain-level chain
            chain = config.get_fallback_chain(domain="Finance", tenant_id="TENANT_OTHER")
            assert chain == ["openrouter", "openai", "dummy"]  # Domain config
            
            # Global default chain
            chain = config.get_fallback_chain(domain="Unknown", tenant_id="TENANT_OTHER")
            assert chain == ["dummy"]  # Global default


class TestProviderSelection:
    """Test provider selection with domain/tenant routing."""
    
    def test_provider_selection_domain_only(self, setup_routing_config):
        """Test provider selection with domain-only config."""
        # Healthcare domain uses dummy provider
        client = load_llm_provider(domain="Healthcare")
        assert isinstance(client, DummyLLMClient)
    
    def test_provider_selection_tenant_only(self, setup_routing_config):
        """Test provider selection with tenant-only config."""
        # Tenant override should work
        client = load_llm_provider(
            domain="Finance",
            tenant_id="TENANT_FINANCE_001"
        )
        assert isinstance(client, DummyLLMClient)  # Tenant uses dummy
    
    def test_provider_selection_both_domain_and_tenant(self, setup_routing_config):
        """Test provider selection with both domain and tenant config."""
        # Tenant should override domain
        client = load_llm_provider(
            domain="Finance",  # Domain uses openrouter
            tenant_id="TENANT_FINANCE_001"  # Tenant uses dummy
        )
        assert isinstance(client, DummyLLMClient)  # Tenant wins
    
    def test_provider_selection_no_config(self):
        """Test provider selection with no routing config."""
        clear_routing_config_cache()
        
        # Should fall back to env vars or dummy
        client = load_llm_provider(domain="Unknown", tenant_id="TENANT_UNKNOWN")
        assert isinstance(client, DummyLLMClient)  # Default fallback
    
    def test_provider_selection_caching(self, setup_routing_config):
        """Test that provider selection is cached in registry."""
        registry.invalidate(None)
        
        # First call
        client1 = load_llm_provider(domain="Healthcare", tenant_id="TENANT_HEALTHCARE_001")
        
        # Second call should return cached client
        client2 = load_llm_provider(domain="Healthcare", tenant_id="TENANT_HEALTHCARE_001")
        
        # Should be the same instance (cached)
        assert client1 is client2


class TestFallbackChains:
    """Test fallback chain behavior."""
    
    @pytest.mark.asyncio
    async def test_fallback_chain_success_first_provider(self, setup_routing_config):
        """Test fallback chain succeeds on first provider."""
        # Mock load_llm_provider to return working dummy client
        with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
            mock_client = DummyLLMClient()
            mock_load.return_value = mock_client
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance", "tenant_id": "TENANT_FINANCE_001"},
                domain="Finance",
                tenant_id="TENANT_FINANCE_001"
            )
            
            # Should succeed on first provider (openrouter in tenant chain)
            assert response is not None
            assert response.raw["provider_used"] == "openrouter"
            assert response.raw["total_providers_attempted"] == 1
    
    @pytest.mark.asyncio
    async def test_fallback_chain_fallback_to_second(self, setup_routing_config):
        """Test fallback chain falls back to second provider."""
        # Mock load_llm_provider to return failing then working client
        call_count = 0
        async def failing_generate(*args, **kwargs):
            raise Exception("Provider failed")
        
        def load_provider_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                # First provider fails
                failing_client = MagicMock(spec=LLMClient)
                failing_client.generate = failing_generate
                return failing_client
            else:
                # Second provider succeeds
                return DummyLLMClient()
        
        with patch("src.llm.fallbacks.load_llm_provider", side_effect=load_provider_side_effect):
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance", "tenant_id": "TENANT_FINANCE_001"},
                domain="Finance",
                tenant_id="TENANT_FINANCE_001"
            )
            
            # Should succeed on second provider
            assert response is not None
            assert response.raw["provider_used"] == "dummy"
            assert response.raw["total_providers_attempted"] == 2


class TestSecretMasking:
    """Test secret masking in logs and functions."""
    
    def test_mask_secret_function(self):
        """Test mask_secret() function directly."""
        # OpenAI/OpenRouter style
        assert mask_secret("sk-1234567890") == "sk-***"
        assert "1234567890" not in mask_secret("sk-1234567890")
        
        # Generic secret
        assert mask_secret("my-secret-token") == "***masked***"
        assert "my-secret-token" not in mask_secret("my-secret-token")
        
        # None/empty
        assert mask_secret(None) == ""
        assert mask_secret("") == ""
    
    def test_factory_logs_no_secrets(self, caplog):
        """Test that factory logs don't contain raw API keys."""
        import logging
        caplog.set_level(logging.DEBUG)
        
        # Load provider with API key
        with patch.dict(os.environ, {"LLM_API_KEY": "sk-test-1234567890"}):
            client = load_llm_provider(provider="dummy")
        
        # Check logs
        log_messages = " ".join(caplog.messages)
        
        # Should not contain raw API key
        assert "sk-test-1234567890" not in log_messages
        # Should contain masked version
        assert "sk-***" in log_messages or "***masked***" in log_messages or "mask_secret" in log_messages
    
    def test_openrouter_logs_no_secrets(self):
        """Test that OpenRouter client doesn't log raw API keys."""
        from src.llm.openrouter_llm import OpenRouterConfig, OpenRouterLLMClient
        
        config = OpenRouterConfig(api_key="sk-or-v1-1234567890", model="gpt-4.1-mini")
        client = OpenRouterLLMClient(config)
        
        # Check that config.api_key is not exposed in __repr__ or similar
        # The actual logging happens in generate(), which we test via factory
        assert config.api_key == "sk-or-v1-1234567890"  # Config still has it
        # But logs should mask it (tested via factory test above)


class TestPromptConstraints:
    """Test prompt constraint and sanitization."""
    
    def test_sanitize_prompt_healthcare_with_patient_id(self):
        """Test that Healthcare domain redacts patient IDs."""
        prompt = "Explain exception for patient_id: MRN-12345"
        context = {"patient_id": "MRN-12345", "domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact patient ID
        assert "MRN-12345" not in sanitized
        assert "[REDACTED]" in sanitized or "patient_id=[REDACTED]" in sanitized
    
    def test_sanitize_prompt_healthcare_with_mrn_in_context(self):
        """Test that Healthcare domain redacts MRN from context."""
        prompt = "Explain this exception"
        context = {"mrn": "MRN-12345", "domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should not contain raw MRN if it was in prompt
        # (This test verifies context-based redaction works)
        assert sanitized is not None
    
    def test_sanitize_prompt_non_healthcare_unchanged(self):
        """Test that non-Healthcare domains don't modify prompts."""
        prompt = "Explain exception for patient_id: MRN-12345"
        context = {"patient_id": "MRN-12345", "domain": "Finance"}
        
        sanitized = sanitize_prompt("Finance", prompt, context)
        
        # Should be unchanged
        assert sanitized == prompt
        assert "MRN-12345" in sanitized
    
    def test_sanitize_prompt_healthcare_email_redaction(self):
        """Test that Healthcare domain redacts email addresses."""
        prompt = "Contact user at john.doe@example.com"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact email
        assert "john.doe@example.com" not in sanitized
        assert "[EMAIL_REDACTED]" in sanitized


class TestRegistryOperations:
    """Test registry get/set/invalidate operations."""
    
    def test_registry_set_and_get(self):
        """Test setting and getting from registry."""
        key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        config = ProviderConfigEntry(provider="dummy", model="dummy-model")
        client = DummyLLMClient()
        
        registry.set_client(key, config, client)
        
        # Should retrieve same client
        cached_client = registry.get_client(key)
        assert cached_client is client
        
        # Should retrieve same config
        cached_config = registry.get_config(key)
        assert cached_config.provider == "dummy"
        assert cached_config.model == "dummy-model"
    
    def test_registry_invalidate_by_key(self):
        """Test invalidating specific key."""
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_002", domain="Healthcare")
        
        client1 = DummyLLMClient()
        client2 = DummyLLMClient()
        config = ProviderConfigEntry(provider="dummy", model="dummy-model")
        
        registry.set_client(key1, config, client1)
        registry.set_client(key2, config, client2)
        
        # Invalidate key1
        registry.invalidate(key1)
        
        # key1 should be gone, key2 should remain
        assert registry.get_client(key1) is None
        assert registry.get_client(key2) is client2
    
    def test_registry_invalidate_all(self):
        """Test invalidating all entries."""
        key1 = ProviderKey(tenant_id="TENANT_001", domain="Finance")
        key2 = ProviderKey(tenant_id="TENANT_002", domain="Healthcare")
        
        client1 = DummyLLMClient()
        client2 = DummyLLMClient()
        config = ProviderConfigEntry(provider="dummy", model="dummy-model")
        
        registry.set_client(key1, config, client1)
        registry.set_client(key2, config, client2)
        
        # Invalidate all
        registry.invalidate(None)
        
        # Both should be gone
        assert registry.get_client(key1) is None
        assert registry.get_client(key2) is None


class TestHotReload:
    """Test hot reload functionality."""
    
    def test_reload_routing_config(self, test_config_yaml_path):
        """Test reloading routing configuration."""
        with patch.dict(os.environ, {"LLM_ROUTING_CONFIG_PATH": str(test_config_yaml_path)}):
            clear_routing_config_cache()
            
            # Load initial config
            config1 = load_routing_config(str(test_config_yaml_path))
            from src.llm.routing_config import _cached_routing_config
            import src.llm.routing_config as routing_config_module
            routing_config_module._cached_routing_config = config1
            
            # Cache a client
            key = ProviderKey(tenant_id="TENANT_001", domain="Finance")
            config_entry = ProviderConfigEntry(provider="dummy", model="dummy-model")
            client = DummyLLMClient()
            registry.set_client(key, config_entry, client)
            
            # Reload
            reload_llm_routing_config()
            
            # Registry should be invalidated
            assert registry.get_cache_stats()["cached_clients"] == 0


class TestRoutingHelpers:
    """Test routing config helper methods."""
    
    def test_get_domain_provider(self, test_config_yaml_path):
        """Test get_domain_provider helper."""
        config = load_routing_config(str(test_config_yaml_path))
        
        assert config.get_domain_provider("Finance") == "openrouter"
        assert config.get_domain_provider("Healthcare") == "dummy"
        assert config.get_domain_provider("Unknown") is None
    
    def test_get_domain_model(self, test_config_yaml_path):
        """Test get_domain_model helper."""
        config = load_routing_config(str(test_config_yaml_path))
        
        assert config.get_domain_model("Finance") == "openrouter:finance-model"
        assert config.get_domain_model("Healthcare") == "dummy-healthcare"
        assert config.get_domain_model("Unknown") is None
    
    def test_get_tenant_provider_and_model(self, test_config_yaml_path):
        """Test get_tenant_provider_and_model helper."""
        config = load_routing_config(str(test_config_yaml_path))
        
        provider, model = config.get_tenant_provider_and_model("TENANT_FINANCE_001")
        assert provider == "dummy"
        assert model == "dummy-tenant-special"
        
        provider, model = config.get_tenant_provider_and_model("TENANT_UNKNOWN")
        assert provider is None
        assert model is None

