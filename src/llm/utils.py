"""
LLM utility functions for security and logging.

Provides helper functions for secure logging and secret masking.
"""

from typing import Optional


def mask_secret(value: Optional[str]) -> str:
    """
    Mask a secret value for safe logging.
    
    This function ensures that sensitive values like API keys, tokens, and
    passwords never appear in logs in their raw form. It returns a safe
    representation that indicates a secret is present without exposing it.
    
    Args:
        value: Secret value to mask (e.g., API key, token, password).
               Can be None or empty string.
    
    Returns:
        Masked representation of the secret:
        - Empty string ("") if value is None or empty
        - "sk-***" if value starts with "sk-" (OpenAI/OpenRouter style)
        - "***masked***" for all other cases
    
    Example:
        >>> mask_secret("sk-or-v1-1234567890abcdef")
        'sk-***'
        
        >>> mask_secret("my-secret-token")
        '***masked***'
        
        >>> mask_secret(None)
        ''
        
        >>> mask_secret("")
        ''
    """
    if not value or not value.strip():
        return ""
    
    # Normalize value (strip whitespace)
    value = value.strip()
    
    # Check for common API key patterns
    if value.startswith("sk-"):
        # OpenAI/OpenRouter style API key: "sk-..." -> "sk-***"
        return "sk-***"
    elif value.startswith("sk_live_") or value.startswith("sk_test_"):
        # Stripe-style API key: "sk_live_..." -> "sk_live_***"
        return value.split("_")[0] + "_" + value.split("_")[1] + "_***"
    elif value.startswith("Bearer "):
        # Bearer token: "Bearer ..." -> "Bearer ***"
        return "Bearer ***"
    else:
        # Generic secret: return fixed mask
        return "***masked***"

