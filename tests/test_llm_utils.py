"""
Unit tests for LLM utility functions.

Tests secret masking functionality to ensure API keys and sensitive
secrets never appear in logs.
"""

import pytest

from src.llm.utils import mask_secret


class TestMaskSecret:
    """Test cases for mask_secret() function."""
    
    def test_mask_secret_none(self):
        """Test that None returns empty string."""
        assert mask_secret(None) == ""
    
    def test_mask_secret_empty_string(self):
        """Test that empty string returns empty string."""
        assert mask_secret("") == ""
        assert mask_secret("   ") == ""  # Whitespace only
    
    def test_mask_secret_openai_style_key(self):
        """Test that OpenAI-style API keys (sk-...) are masked correctly."""
        api_key = "sk-1234567890abcdef"
        masked = mask_secret(api_key)
        assert masked == "sk-***"
        assert "1234567890abcdef" not in masked
        assert "sk-" in masked
    
    def test_mask_secret_openrouter_style_key(self):
        """Test that OpenRouter-style API keys (sk-or-v1-...) are masked correctly."""
        api_key = "sk-or-v1-1234567890abcdef"
        masked = mask_secret(api_key)
        assert masked == "sk-***"
        assert "1234567890abcdef" not in masked
        assert "or-v1" not in masked
    
    def test_mask_secret_stripe_style_key(self):
        """Test that Stripe-style API keys are masked correctly."""
        live_key = "sk_live_1234567890abcdef"
        masked_live = mask_secret(live_key)
        assert masked_live == "sk_live_***"
        assert "1234567890abcdef" not in masked_live
        
        test_key = "sk_test_1234567890abcdef"
        masked_test = mask_secret(test_key)
        assert masked_test == "sk_test_***"
        assert "1234567890abcdef" not in masked_test
    
    def test_mask_secret_bearer_token(self):
        """Test that Bearer tokens are masked correctly."""
        bearer_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"
        masked = mask_secret(bearer_token)
        assert masked == "Bearer ***"
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in masked
    
    def test_mask_secret_generic_secret(self):
        """Test that generic secrets are masked with default format."""
        secret = "my-secret-token-12345"
        masked = mask_secret(secret)
        assert masked == "***masked***"
        assert "my-secret-token-12345" not in masked
        assert "12345" not in masked
    
    def test_mask_secret_password(self):
        """Test that passwords are masked correctly."""
        password = "SuperSecretPassword123!"
        masked = mask_secret(password)
        assert masked == "***masked***"
        assert "SuperSecretPassword123!" not in masked
        assert "123" not in masked
    
    def test_mask_secret_with_whitespace(self):
        """Test that secrets with whitespace are handled correctly."""
        api_key = "  sk-1234567890abcdef  "
        masked = mask_secret(api_key)
        assert masked == "sk-***"
        assert "1234567890abcdef" not in masked
    
    def test_mask_secret_long_key(self):
        """Test that long API keys are masked correctly."""
        long_key = "sk-" + "a" * 100
        masked = mask_secret(long_key)
        assert masked == "sk-***"
        assert "a" * 10 not in masked  # Ensure no part of the key leaks
    
    def test_mask_secret_no_raw_value_in_output(self):
        """Test that no raw secret value appears in masked output."""
        test_secrets = [
            "sk-1234567890abcdef",
            "sk-or-v1-1234567890abcdef",
            "sk_live_1234567890abcdef",
            "Bearer token123",
            "my-secret-value",
            "password123",
        ]
        
        for secret in test_secrets:
            masked = mask_secret(secret)
            # Extract the actual secret part (after prefix if any)
            if secret.startswith("sk-"):
                secret_part = secret[3:]  # Everything after "sk-"
            elif secret.startswith("sk_"):
                parts = secret.split("_")
                secret_part = "_".join(parts[2:])  # Everything after "sk_live_" or "sk_test_"
            elif secret.startswith("Bearer "):
                secret_part = secret[7:]  # Everything after "Bearer "
            else:
                secret_part = secret
            
            # Ensure no part of the actual secret appears in masked output
            if secret_part:
                assert secret_part not in masked, f"Secret part '{secret_part}' leaked in masked output: '{masked}'"
    
    def test_mask_secret_consistency(self):
        """Test that same secret always produces same masked output."""
        secret = "sk-1234567890abcdef"
        masked1 = mask_secret(secret)
        masked2 = mask_secret(secret)
        assert masked1 == masked2 == "sk-***"
    
    def test_mask_secret_different_secrets_different_outputs(self):
        """Test that different secrets produce appropriate masked outputs."""
        secret1 = "sk-1234567890abcdef"
        secret2 = "my-secret-token"
        
        masked1 = mask_secret(secret1)
        masked2 = mask_secret(secret2)
        
        # Both should be masked, but format may differ
        assert "1234567890abcdef" not in masked1
        assert "my-secret-token" not in masked2
        assert masked1 == "sk-***"
        assert masked2 == "***masked***"

