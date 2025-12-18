"""
PII Redaction Service for Phase 9.

Redacts PII (Personally Identifiable Information) from event payloads at ingestion.
Supports configurable PII fields per tenant and stores redaction metadata.

Phase 9 P9-24: Encryption in transit and PII redaction.
Reference: docs/phase9-async-scale-mvp.md Section 11
"""

import logging
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)


class PIIRedactionError(Exception):
    """Raised when PII redaction operations fail."""

    pass


class PIIRedactionService:
    """
    Service for redacting PII from event payloads.
    
    Features:
    - Configurable PII fields per tenant
    - Recursive redaction in nested structures
    - Redaction metadata tracking
    - Ensures secrets never logged
    """
    
    # Default PII field patterns (common PII identifiers)
    DEFAULT_PII_PATTERNS = [
        r"ssn",
        r"social[_\s-]?security[_\s-]?number",
        r"credit[_\s-]?card",
        r"card[_\s-]?number",
        r"cvv",
        r"cvc",
        r"pin",
        r"password",
        r"passwd",
        r"secret",
        r"api[_\s-]?key",
        r"token",
        r"auth[_\s-]?token",
        r"access[_\s-]?token",
        r"email",
        r"phone",
        r"telephone",
        r"mobile",
        r"address",
        r"street",
        r"city",
        r"zip[_\s-]?code",
        r"postal[_\s-]?code",
        r"date[_\s-]?of[_\s-]?birth",
        r"dob",
        r"birthdate",
        r"drivers[_\s-]?license",
        r"license[_\s-]?number",
        r"passport",
        r"account[_\s-]?number",
        r"routing[_\s-]?number",
        r"iban",
        r"swift",
        r"tax[_\s-]?id",
        r"ein",
        r"national[_\s-]?id",
        r"patient[_\s-]?id",
        r"medical[_\s-]?record",
        r"health[_\s-]?insurance",
    ]
    
    def __init__(
        self,
        default_pii_fields: Optional[list[str]] = None,
        tenant_pii_fields: Optional[dict[str, list[str]]] = None,
        redaction_placeholder: str = "[REDACTED]",
    ):
        """
        Initialize PII redaction service.
        
        Args:
            default_pii_fields: Default list of PII field patterns (uses DEFAULT_PII_PATTERNS if None)
            tenant_pii_fields: Optional dict mapping tenant_id to list of PII field patterns
            redaction_placeholder: Placeholder string to use for redacted values
        """
        self.default_pii_fields = default_pii_fields or self.DEFAULT_PII_PATTERNS
        self.tenant_pii_fields = tenant_pii_fields or {}
        self.redaction_placeholder = redaction_placeholder
        
        # Compile regex patterns for efficiency
        self._default_patterns = [
            re.compile(pattern, re.IGNORECASE) for pattern in self.default_pii_fields
        ]
        self._tenant_patterns: dict[str, list[re.Pattern]] = {}
        for tenant_id, patterns in self.tenant_pii_fields.items():
            self._tenant_patterns[tenant_id] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
        
        logger.info(
            f"Initialized PIIRedactionService: default_patterns={len(self.default_pii_fields)}, "
            f"tenant_configs={len(self.tenant_pii_fields)}"
        )
    
    def get_pii_fields_for_tenant(self, tenant_id: str) -> list[re.Pattern]:
        """
        Get compiled PII field patterns for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of compiled regex patterns for PII fields
        """
        # Combine tenant-specific patterns with defaults
        patterns = self._default_patterns.copy()
        if tenant_id in self._tenant_patterns:
            patterns.extend(self._tenant_patterns[tenant_id])
        return patterns
    
    def redact_pii(
        self,
        data: dict[str, Any],
        tenant_id: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Redact PII from a data dictionary.
        
        Phase 9 P9-24: Redacts PII fields at ingestion based on tenant configuration.
        
        Args:
            data: Dictionary to redact (will not be modified)
            tenant_id: Tenant identifier (for tenant-specific PII field configuration)
            
        Returns:
            Tuple of (redacted_data, redaction_metadata)
            - redacted_data: Dictionary with PII redacted
            - redaction_metadata: Dictionary with information about what was redacted:
                {
                    "redacted_fields": ["field1", "field2", ...],
                    "redaction_count": 5,
                    "tenant_id": "TENANT_001",
                }
        """
        if not isinstance(data, dict):
            return data, {}
        
        # Get PII patterns for tenant
        patterns = self.get_pii_fields_for_tenant(tenant_id)
        
        redacted = {}
        redacted_fields: list[str] = []
        redaction_count = 0
        
        def should_redact(key: str) -> bool:
            """Check if a key should be redacted based on PII patterns."""
            return any(pattern.search(key) for pattern in patterns)
        
        def redact_value(value: Any, path: str = "") -> Any:
            """Recursively redact values in nested structures."""
            nonlocal redaction_count  # Allow modification of outer scope variable
            if isinstance(value, dict):
                redacted_dict = {}
                for k, v in value.items():
                    current_path = f"{path}.{k}" if path else k
                    if should_redact(k):
                        redacted_dict[k] = self.redaction_placeholder
                        redacted_fields.append(current_path)
                        redaction_count += 1
                    else:
                        redacted_dict[k] = redact_value(v, current_path)
                return redacted_dict
            elif isinstance(value, list):
                return [redact_value(item, f"{path}[{i}]") for i, item in enumerate(value)]
            else:
                return value
        
        # Redact top-level and nested fields
        for key, value in data.items():
            if should_redact(key):
                redacted[key] = self.redaction_placeholder
                redacted_fields.append(key)
                redaction_count += 1
            else:
                redacted[key] = redact_value(value, key)
        
        # Build redaction metadata
        redaction_metadata = {
            "redacted_fields": redacted_fields,
            "redaction_count": redaction_count,
            "tenant_id": tenant_id,
            "redaction_placeholder": self.redaction_placeholder,
        }
        
        if redaction_count > 0:
            logger.info(
                f"Redacted {redaction_count} PII field(s) for tenant {tenant_id}: "
                f"{', '.join(redacted_fields[:10])}"  # Log first 10 fields
                + (f" and {len(redacted_fields) - 10} more" if len(redacted_fields) > 10 else "")
            )
        
        return redacted, redaction_metadata
    
    def ensure_secrets_never_logged(
        self,
        data: Any,
        tenant_id: Optional[str] = None,
    ) -> Any:
        """
        Ensure secrets are never logged by redacting them from data.
        
        Phase 9 P9-24: Defensive redaction to prevent secrets in logs.
        This is a more aggressive redaction that catches common secret patterns.
        
        Args:
            data: Data to redact (dict, list, or other)
            tenant_id: Optional tenant identifier
            
        Returns:
            Redacted data safe for logging
        """
        if isinstance(data, dict):
            # Use secret redaction patterns (more aggressive than PII)
            from src.tools.security import redact_secrets_from_dict
            
            return redact_secrets_from_dict(data)
        elif isinstance(data, list):
            return [
                self.ensure_secrets_never_logged(item, tenant_id) for item in data
            ]
        elif isinstance(data, str):
            from src.tools.security import redact_secrets_from_string
            
            return redact_secrets_from_string(data)
        else:
            return data


def get_pii_redaction_service() -> PIIRedactionService:
    """
    Get the global PII redaction service instance.
    
    For MVP, uses default configuration.
    In production, this would load tenant-specific configurations from database.
    
    Returns:
        PIIRedactionService instance
    """
    # For MVP, create with defaults
    # In production, load tenant configurations from database
    return PIIRedactionService()



