"""
Prompt Constraint System for Phase 5 - LLM Routing.

Provides prompt sanitization and restriction hooks for external LLM providers,
especially for PHI/PII-heavy domains like Healthcare.

Reference: docs/phase5-llm-routing.md Section 2 (Security first - Ability to constrain outbound prompts)
"""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Common PII/PHI patterns to detect and redact
PII_PATTERNS = [
    # Patient identifiers
    (r"\b(?:patient[_\s]?id|patient_id|MRN|medical[_\s]?record[_\s]?number)\s*[:=]\s*([A-Z0-9\-]+)", r"patient_id=[REDACTED]"),
    (r"\b(?:SSN|social[_\s]?security[_\s]?number)\s*[:=]\s*(\d{3}-\d{2}-\d{4})", r"SSN=[REDACTED]"),
    # Email addresses
    (r"\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b", r"[EMAIL_REDACTED]"),
    # Phone numbers (US format)
    (r"\b(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})\b", r"[PHONE_REDACTED]"),
    # Credit card numbers (basic pattern)
    (r"\b(\d{4}[-.\s]?\d{4}[-.\s]?\d{4}[-.\s]?\d{4})\b", r"[CARD_REDACTED]"),
]


def sanitize_prompt(domain: Optional[str], prompt: str, context: dict | None = None) -> str:
    """
    Sanitize or restrict prompts before sending to external LLM providers.
    
    This function provides a hook for domain-specific prompt sanitization,
    especially for PHI/PII-heavy domains like Healthcare. It can:
    - Redact obvious PII tokens (patient_id, MRN, SSN, etc.)
    - Remove sensitive context data
    - Apply domain-specific restrictions
    
    Phase 5 minimal implementation:
    - Healthcare domain: Basic PII redaction if context contains patient identifiers
    - Other domains: Return prompt unchanged
    - TODO: Advanced PHI/PII detection using NER models
    - TODO: Configurable redaction rules per domain
    - TODO: Prompt validation and blocking for high-risk domains
    
    Args:
        domain: Domain name (e.g., "Healthcare", "Finance", "Insurance")
        prompt: The prompt text to sanitize
        context: Optional context dictionary that may contain sensitive data
    
    Returns:
        Sanitized prompt string with PII/PHI redacted if applicable
    
    Example:
        # Healthcare domain with patient ID in context
        context = {"patient_id": "MRN-12345", "domain": "Healthcare"}
        prompt = "Explain exception for patient_id: MRN-12345"
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        # Returns: "Explain exception for patient_id=[REDACTED]"
        
        # Non-Healthcare domain
        sanitized = sanitize_prompt("Finance", prompt, context)
        # Returns: prompt unchanged
    """
    if not prompt:
        return prompt
    
    # Normalize domain name (case-insensitive)
    domain_normalized = domain.lower().strip() if domain else None
    
    # Healthcare domain: Apply PII/PHI redaction
    if domain_normalized == "healthcare":
        sanitized = _sanitize_healthcare_prompt(prompt, context)
        
        # Log sanitization if any redaction occurred
        if sanitized != prompt:
            logger.info(
                f"Prompt sanitized for Healthcare domain: "
                f"original_length={len(prompt)}, sanitized_length={len(sanitized)}"
            )
        
        return sanitized
    
    # TODO (Future phases): Add sanitization for other PHI/PII-heavy domains
    # - Finance: Credit card numbers, account numbers, SSN
    # - Insurance: Policy numbers, claim numbers, SSN
    # - Legal: Case numbers, client identifiers
    
    # For all other domains, return prompt unchanged
    return prompt


def _sanitize_healthcare_prompt(prompt: str, context: dict | None = None) -> str:
    """
    Sanitize prompt for Healthcare domain with basic PII/PHI redaction.
    
    This is a minimal implementation for Phase 5. Future phases will include:
    - Advanced NER-based PHI detection
    - Configurable redaction rules
    - Domain Pack-based redaction policies
    
    Args:
        prompt: The prompt text to sanitize
        context: Optional context dictionary that may contain patient identifiers
    
    Returns:
        Sanitized prompt with PII/PHI redacted
    """
    sanitized = prompt
    
    # Step 1: Redact PII patterns in prompt text
    for pattern, replacement in PII_PATTERNS:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    
    # Step 2: Redact patient identifiers from context if present
    if context:
        # Check for common patient identifier keys in context
        patient_id_keys = ["patient_id", "patientId", "mrn", "MRN", "medical_record_number"]
        for key in patient_id_keys:
            if key in context:
                patient_id_value = str(context[key])
                # Redact the value if it appears in the prompt
                if patient_id_value in sanitized:
                    sanitized = sanitized.replace(patient_id_value, "[REDACTED]")
                    logger.debug(f"Redacted patient identifier '{key}' from prompt")
        
        # TODO (Future phases): Advanced PHI detection
        # - Use NER models to detect PHI entities (names, dates, locations, etc.)
        # - Apply configurable redaction rules from Domain Pack
        # - Support partial redaction (e.g., "John D***" instead of full name)
        # - Track redaction events for audit purposes
    
    return sanitized


def validate_prompt_for_domain(domain: Optional[str], prompt: str) -> tuple[bool, Optional[str]]:
    """
    Validate prompt for domain-specific constraints.
    
    This function can block prompts that violate domain-specific policies,
    such as prompts that contain too much sensitive data or prompts that
    are not allowed for certain domains.
    
    Phase 5: Minimal implementation - always allows prompts.
    Future phases: Implement blocking rules based on Domain Pack policies.
    
    Args:
        domain: Domain name
        prompt: The prompt text to validate
    
    Returns:
        Tuple of (is_allowed, reason):
        - is_allowed: True if prompt is allowed, False if blocked
        - reason: Optional reason string if blocked
    
    Example:
        is_allowed, reason = validate_prompt_for_domain("Healthcare", prompt)
        if not is_allowed:
            # Block the request
    """
    # Phase 5: All prompts are allowed
    # TODO (Future phases): Implement blocking rules
    # - Check prompt length limits per domain
    # - Detect excessive PII/PHI content
    # - Apply Domain Pack-based blocking policies
    # - Support prompt approval workflows for high-risk domains
    
    return (True, None)

