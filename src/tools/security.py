"""
Security utilities for tool execution.

Phase 8 P8-14: Security enhancements for tool execution:
- Secret redaction for logging and events
- URL validation and endpoint allow-list enforcement
- API key masking
"""

import logging
import re
from typing import Any, Optional
from urllib.parse import urlparse

from src.llm.utils import mask_secret

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Raised when security validation fails."""

    pass


class URLValidationError(SecurityError):
    """Raised when URL validation fails."""

    pass


def redact_secrets_from_dict(
    data: dict[str, Any],
    additional_patterns: Optional[list[str]] = None,
    redaction_placeholder: str = "[REDACTED]",
) -> dict[str, Any]:
    """
    Redact secrets from a dictionary recursively.
    
    Identifies common secret field names and redacts their values.
    This is a more comprehensive version than the one in validation.py.
    
    Args:
        data: Dictionary to redact
        additional_patterns: Optional additional regex patterns for secret field names
        redaction_placeholder: Placeholder to use for redacted values
        
    Returns:
        Dictionary with secrets redacted (new dictionary, original unchanged)
    """
    if not isinstance(data, dict):
        return data
    
    # Common secret field name patterns (case-insensitive)
    secret_patterns = [
        r"password",
        r"passwd",
        r"secret",
        r"api[_-]?key",
        r"apikey",
        r"token",
        r"auth[_-]?token",
        r"access[_-]?token",
        r"refresh[_-]?token",
        r"credential",
        r"private[_-]?key",
        r"privatekey",
        r"apisecret",
        r"client[_-]?secret",
        r"bearer",
        r"authorization",
        r"x-api-key",
        r"x-auth-token",
    ]
    
    if additional_patterns:
        secret_patterns.extend(additional_patterns)
    
    # Compile patterns for efficiency
    compiled_patterns = [re.compile(pattern, re.IGNORECASE) for pattern in secret_patterns]
    
    def should_redact(key: str) -> bool:
        """Check if a key should be redacted."""
        return any(pattern.search(key) for pattern in compiled_patterns)
    
    def redact_value(value: Any) -> Any:
        """Recursively redact values in nested structures."""
        if isinstance(value, dict):
            return {
                k: redaction_placeholder if should_redact(k) else redact_value(v)
                for k, v in value.items()
            }
        elif isinstance(value, list):
            return [redact_value(item) for item in value]
        elif isinstance(value, str) and should_redact(str(value)[:50]):  # Check first 50 chars for patterns
            # If the value itself looks like a secret, redact it
            return redaction_placeholder
        else:
            return value
    
    # Create redacted copy
    redacted = {}
    for key, value in data.items():
        if should_redact(key):
            # Key matches secret pattern - redact the value
            if isinstance(value, (dict, list)):
                redacted[key] = redact_value(value)
            else:
                redacted[key] = redaction_placeholder
        else:
            # Key doesn't match - recurse to check nested structures
            redacted[key] = redact_value(value)
    
    return redacted


def redact_secrets_from_string(text: str, redaction_placeholder: str = "[REDACTED]") -> str:
    """
    Redact secrets from a string by masking common patterns.
    
    Args:
        text: String that may contain secrets
        redaction_placeholder: Placeholder to use for redacted values
        
    Returns:
        String with secrets masked
    """
    if not isinstance(text, str):
        return text
    
    # Common secret patterns in strings
    patterns = [
        (r'["\']?api[_-]?key["\']?\s*[:=]\s*["\']([^"\']+)["\']', f'api_key: {redaction_placeholder}'),
        (r'["\']?password["\']?\s*[:=]\s*["\']([^"\']+)["\']', f'password: {redaction_placeholder}'),
        (r'["\']?token["\']?\s*[:=]\s*["\']([^"\']+)["\']', f'token: {redaction_placeholder}'),
        (r'Bearer\s+([A-Za-z0-9\-_\.]+)', 'Bearer ***'),
        (r'sk-[A-Za-z0-9\-_\.]+', 'sk-***'),
        (r'sk_live_[A-Za-z0-9\-_\.]+', 'sk_live_***'),
        (r'sk_test_[A-Za-z0-9\-_\.]+', 'sk_test_***'),
    ]
    
    redacted = text
    for pattern, replacement in patterns:
        redacted = re.sub(pattern, replacement, redacted, flags=re.IGNORECASE)
    
    return redacted


def validate_url(url: str, allowed_domains: Optional[list[str]] = None, allowed_schemes: Optional[list[str]] = None) -> None:
    """
    Validate URL against allow-list.
    
    Args:
        url: URL to validate
        allowed_domains: Optional list of allowed domains (e.g., ['api.example.com', '*.example.com'])
                        If None, allows any domain (not recommended for production)
        allowed_schemes: Optional list of allowed URL schemes (default: ['https'])
                        If None, defaults to ['https'] for security
        
    Raises:
        URLValidationError: If URL is invalid or not in allow-list
    """
    if not url or not isinstance(url, str):
        raise URLValidationError("URL must be a non-empty string")
    
    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise URLValidationError(f"Invalid URL format: {e}") from e
    
    # Validate scheme
    if allowed_schemes is None:
        allowed_schemes = ['https']  # Default to HTTPS only for security
    
    if parsed.scheme not in allowed_schemes:
        raise URLValidationError(
            f"URL scheme '{parsed.scheme}' not allowed. "
            f"Allowed schemes: {', '.join(allowed_schemes)}"
        )
    
    # Validate domain if allow-list provided
    if allowed_domains:
        domain = parsed.netloc.split(':')[0]  # Remove port if present
        
        # Check exact match or wildcard match
        allowed = False
        for allowed_domain in allowed_domains:
            if allowed_domain == domain:
                allowed = True
                break
            elif allowed_domain.startswith('*.'):
                # Wildcard domain: *.example.com matches api.example.com, sub.example.com, etc.
                base_domain = allowed_domain[2:]  # Remove '*.' prefix
                if domain.endswith('.' + base_domain) or domain == base_domain:
                    allowed = True
                    break
        
        if not allowed:
            raise URLValidationError(
                f"URL domain '{domain}' not in allow-list. "
                f"Allowed domains: {', '.join(allowed_domains)}"
            )
    
    # Additional security checks
    # Block localhost and private IPs unless explicitly allowed
    if not allowed_domains or not any('localhost' in d or '127.0.0.1' in d for d in allowed_domains):
        if parsed.hostname in ('localhost', '127.0.0.1', '::1') or (
            parsed.hostname and parsed.hostname.startswith('192.168.')
        ):
            raise URLValidationError(
                f"URL points to localhost or private IP: {parsed.hostname}. "
                "This is blocked for security. Add to allow-list if needed."
            )


def mask_api_key_in_headers(headers: dict[str, str]) -> dict[str, str]:
    """
    Create a safe copy of headers with API keys masked for logging.
    
    Args:
        headers: Original headers dictionary
        
    Returns:
        New dictionary with sensitive headers masked
    """
    masked = {}
    sensitive_headers = [
        'authorization',
        'x-api-key',
        'x-auth-token',
        'api-key',
        'apikey',
    ]
    
    for key, value in headers.items():
        key_lower = key.lower()
        if any(sensitive in key_lower for sensitive in sensitive_headers):
            masked[key] = mask_secret(value)
        else:
            masked[key] = value
    
    return masked


def safe_log_payload(payload: Any, logger_instance: Optional[logging.Logger] = None) -> str:
    """
    Create a safe string representation of payload for logging.
    
    Args:
        payload: Payload to log (dict, list, or other)
        logger_instance: Optional logger instance (uses module logger if None)
        
    Returns:
        Safe string representation with secrets redacted
    """
    log = logger_instance or logger
    
    if isinstance(payload, dict):
        redacted = redact_secrets_from_dict(payload)
        try:
            import json
            return json.dumps(redacted, indent=2, default=str)
        except Exception:
            return str(redacted)
    elif isinstance(payload, str):
        return redact_secrets_from_string(payload)
    else:
        # For other types, convert to string and try to redact
        return redact_secrets_from_string(str(payload))

