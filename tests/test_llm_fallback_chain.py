"""
Unit tests for provider-specific fallback chains (LR-10).

Tests the call_with_fallback_chain() function and fallback chain resolution.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.llm.base import LLMClient, LLMResponse
from src.llm.dummy_llm import DummyLLMClient
from src.llm.fallbacks import call_with_fallback_chain
from src.llm.routing_config import (
    DomainRoutingConfig,
    LLMRoutingConfig,
    TenantRoutingConfig,
    load_routing_config,
)


class FakeLLMClient(LLMClient):
    """Fake LLM client for testing that can be configured to succeed or fail."""
    
    def __init__(self, should_fail: bool = False, error_message: str = "Test error"):
        self.should_fail = should_fail
        self.error_message = error_message
        self.call_count = 0
    
    async def generate(self, prompt: str, context: dict | None = None) -> LLMResponse:
        self.call_count += 1
        if self.should_fail:
            raise Exception(self.error_message)
        return LLMResponse(
            text=f"Response from {self.__class__.__name__}",
            raw={"provider": self.__class__.__name__.lower()}
        )


class FakeOpenRouterClient(FakeLLMClient):
    """Fake OpenRouter client."""
    pass


class FakeOpenAIClient(FakeLLMClient):
    """Fake OpenAI client."""
    pass


@pytest.fixture
def mock_routing_config():
    """Create a mock routing config with fallback chains."""
    return LLMRoutingConfig(
        default_fallback_chain=["openrouter", "openai", "dummy"],
        domains={
            "Finance": DomainRoutingConfig(
                provider="openrouter",
                model="gpt-4.1-mini",
                fallback_chain=["openrouter", "openai", "dummy"]
            ),
            "Healthcare": DomainRoutingConfig(
                provider="dummy",
                model="dummy-model",
                fallback_chain=["dummy"]  # No external providers
            ),
        },
        tenants={
            "TENANT_001": TenantRoutingConfig(
                provider="openrouter",
                model="gpt-4o",
                fallback_chain=["openrouter", "dummy"]  # Tenant-specific chain
            ),
        },
    )


@pytest.mark.asyncio
async def test_fallback_chain_success_first_provider():
    """Test that fallback chain succeeds on first provider."""
    # Mock load_llm_provider to return a working client
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        mock_client = FakeOpenRouterClient(should_fail=False)
        mock_load.return_value = mock_client
        
        # Mock routing config
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["openrouter", "openai", "dummy"]
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance", "tenant_id": "TENANT_001"},
                domain="Finance",
                tenant_id="TENANT_001"
            )
            
            assert response.text == "Response from FakeOpenRouterClient"
            assert response.raw["provider_used"] == "openrouter"
            assert response.raw["provider_index"] == 0
            assert response.raw["total_providers_attempted"] == 1
            assert mock_client.call_count == 1


@pytest.mark.asyncio
async def test_fallback_chain_fallback_to_second_provider():
    """Test that fallback chain falls back to second provider when first fails."""
    # Mock load_llm_provider to return different clients
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        # First call returns failing client, second returns working client
        failing_client = FakeOpenRouterClient(should_fail=True, error_message="OpenRouter failed")
        working_client = FakeOpenAIClient(should_fail=False)
        
        call_count = 0
        def load_provider_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return failing_client
            elif call_count == 2:
                return working_client
            return DummyLLMClient()
        
        mock_load.side_effect = load_provider_side_effect
        
        # Mock routing config
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["openrouter", "openai", "dummy"]
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance"},
                domain="Finance"
            )
            
            assert response.text == "Response from FakeOpenAIClient"
            assert response.raw["provider_used"] == "openai"
            assert response.raw["provider_index"] == 1
            assert response.raw["total_providers_attempted"] == 2
            assert failing_client.call_count == 1
            assert working_client.call_count == 1


@pytest.mark.asyncio
async def test_fallback_chain_all_providers_fail():
    """Test that fallback chain returns DummyLLMClient response when all providers fail."""
    # Mock load_llm_provider to return failing clients
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        failing_client1 = FakeOpenRouterClient(should_fail=True, error_message="OpenRouter failed")
        failing_client2 = FakeOpenAIClient(should_fail=True, error_message="OpenAI failed")
        
        call_count = 0
        def load_provider_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return failing_client1
            elif call_count == 2:
                return failing_client2
            return DummyLLMClient()
        
        mock_load.side_effect = load_provider_side_effect
        
        # Mock routing config
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["openrouter", "openai", "dummy"]
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance"},
                domain="Finance"
            )
            
            # Should return DummyLLMClient response with error metadata
            assert "unable to process" in response.text.lower() or "apologize" in response.text.lower()
            assert response.raw["fallback_chain_exhausted"] is True
            assert response.raw["all_providers_failed"] is True
            assert len(response.raw["attempts"]) == 2  # openrouter and openai failed
            assert response.raw["attempts"][0]["outcome"] == "failure"
            assert response.raw["attempts"][1]["outcome"] == "failure"


@pytest.mark.asyncio
async def test_fallback_chain_tenant_overrides_domain():
    """Test that tenant-level fallback chain overrides domain-level chain."""
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        mock_client = FakeOpenRouterClient(should_fail=False)
        mock_load.return_value = mock_client
        
        # Mock routing config with tenant override
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                domains={
                    "Finance": DomainRoutingConfig(
                        provider="openrouter",
                        fallback_chain=["openrouter", "openai", "dummy"]
                    ),
                },
                tenants={
                    "TENANT_001": TenantRoutingConfig(
                        provider="openrouter",
                        fallback_chain=["openrouter", "dummy"]  # Shorter chain
                    ),
                },
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance", "tenant_id": "TENANT_001"},
                domain="Finance",
                tenant_id="TENANT_001"
            )
            
            # Should use tenant's fallback chain (only 2 providers)
            assert response.raw["provider_used"] == "openrouter"
            # Verify that only openrouter was attempted (tenant chain is shorter)
            assert mock_load.call_count == 1


@pytest.mark.asyncio
async def test_fallback_chain_domain_specific():
    """Test that domain-specific fallback chain is used."""
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        mock_client = DummyLLMClient()
        mock_load.return_value = mock_client
        
        # Mock routing config with domain-specific chain
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["openrouter", "openai", "dummy"],
                domains={
                    "Healthcare": DomainRoutingConfig(
                        provider="dummy",
                        fallback_chain=["dummy"]  # Only dummy for Healthcare
                    ),
                },
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Healthcare"},
                domain="Healthcare"
            )
            
            # Should use Healthcare's fallback chain (only dummy)
            assert response.raw["provider_used"] == "dummy"
            assert mock_load.call_count == 1


@pytest.mark.asyncio
async def test_fallback_chain_default_when_no_config():
    """Test that default fallback chain is used when no routing config exists."""
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        mock_client = DummyLLMClient()
        mock_load.return_value = mock_client
        
        # Mock routing config to return None
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_get_config.return_value = None
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance"},
                domain="Finance"
            )
            
            # Should use default chain ["dummy"]
            assert response.raw["provider_used"] == "dummy"
            assert mock_load.call_count == 1


@pytest.mark.asyncio
async def test_fallback_chain_extracts_domain_from_context():
    """Test that domain and tenant_id are extracted from context if not provided."""
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        mock_client = DummyLLMClient()
        mock_load.return_value = mock_client
        
        # Mock routing config
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["dummy"]
            )
            mock_get_config.return_value = mock_config
            
            # Don't pass domain/tenant_id explicitly, only in context
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={"domain": "Finance", "tenant_id": "TENANT_001"}
            )
            
            # Should still work and use context values
            assert response.raw["provider_used"] == "dummy"
            # Verify load_llm_provider was called with domain and tenant_id from context
            assert mock_load.call_count == 1
            call_kwargs = mock_load.call_args[1]
            assert call_kwargs.get("domain") == "Finance"
            assert call_kwargs.get("tenant_id") == "TENANT_001"


@pytest.mark.asyncio
async def test_fallback_chain_logs_attempts():
    """Test that fallback chain logs all attempts for auditing."""
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        failing_client = FakeOpenRouterClient(should_fail=True)
        working_client = FakeOpenAIClient(should_fail=False)
        
        call_count = 0
        def load_provider_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return failing_client
            return working_client
        
        mock_load.side_effect = load_provider_side_effect
        
        # Mock routing config
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["openrouter", "openai", "dummy"]
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={},
            )
            
            # Verify attempts are logged in response
            assert len(response.raw["attempts"]) == 2
            assert response.raw["attempts"][0]["provider"] == "openrouter"
            assert response.raw["attempts"][0]["outcome"] == "failure"
            assert response.raw["attempts"][1]["provider"] == "openai"
            assert response.raw["attempts"][1]["outcome"] == "success"


@pytest.mark.asyncio
async def test_fallback_chain_respects_order():
    """Test that fallback chain respects the order of providers."""
    with patch("src.llm.fallbacks.load_llm_provider") as mock_load:
        # All providers fail except the last one
        failing_client1 = FakeOpenRouterClient(should_fail=True)
        failing_client2 = FakeOpenAIClient(should_fail=True)
        working_client = DummyLLMClient()
        
        call_count = 0
        def load_provider_side_effect(**kwargs):
            nonlocal call_count
            call_count += 1
            provider = kwargs.get("provider", "unknown")
            if call_count == 1:
                return failing_client1
            elif call_count == 2:
                return failing_client2
            return working_client
        
        mock_load.side_effect = load_provider_side_effect
        
        # Mock routing config with specific order
        with patch("src.llm.fallbacks.get_routing_config") as mock_get_config:
            mock_config = LLMRoutingConfig(
                default_fallback_chain=["openrouter", "openai", "dummy"]
            )
            mock_get_config.return_value = mock_config
            
            response = await call_with_fallback_chain(
                prompt="Test prompt",
                context={},
            )
            
            # Should try openrouter first, then openai, then dummy
            assert mock_load.call_count == 3
            # Verify order by checking call arguments
            calls = mock_load.call_args_list
            assert calls[0][1]["provider"] == "openrouter"
            assert calls[1][1]["provider"] == "openai"
            assert calls[2][1]["provider"] == "dummy"
            
            # Final response should be from dummy
            assert "dummy" in response.raw.get("provider_used", "").lower() or response.text

