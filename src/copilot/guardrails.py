"""
Copilot Guardrails for Phase 5 - AI Co-Pilot.

Provides guardrail checks to ensure Co-Pilot responses are read-only and safe.

Reference: docs/phase5-copilot-mvp.md Section 3 (Guardrails)
"""

import logging
import re
from typing import List

logger = logging.getLogger(__name__)

# Action verbs that must be blocked or rewritten
ACTION_VERBS: List[str] = [
    "approve",
    "resolve",
    "escalate",
    "delete",
    "force",
    "settle",
    "update",
    "modify",
]

# Safe refusal message when action request detected
SAFE_REFUSAL_MESSAGE = "I cannot perform or recommend actions. I can only summarize or explain."

# Pattern to match action verbs (case-insensitive, word boundaries)
ACTION_PATTERN = re.compile(
    r"\b(" + "|".join(re.escape(verb) for verb in ACTION_VERBS) + r")\b",
    re.IGNORECASE,
)


def check_guardrails(text: str) -> str:
    """
    Check text for action verbs and replace with safe refusal message if detected.
    
    This function ensures Co-Pilot responses are read-only and do not suggest
    or perform state-changing actions.
    
    Rules:
    - Detects action verbs: approve, resolve, escalate, delete, force, settle, update, modify
    - If action verbs detected, replaces entire response with safe refusal message
    - Logs guardrail violations for monitoring
    
    Args:
        text: Text to check for action verbs
        
    Returns:
        Safe text (original if no action verbs, or refusal message if detected)
        
    Example:
        >>> check_guardrails("I can help you understand the exception.")
        'I can help you understand the exception.'
        
        >>> check_guardrails("I will approve this exception.")
        'I cannot perform or recommend actions. I can only summarize or explain.'
    """
    if not text or not isinstance(text, str):
        return text
    
    # Check for action verbs in the text
    matches = ACTION_PATTERN.findall(text)
    
    if matches:
        # Action verbs detected - log violation and return safe refusal
        logger.warning(
            f"Guardrail violation detected: action verbs found in response: {matches}. "
            f"Replacing with safe refusal message."
        )
        return SAFE_REFUSAL_MESSAGE
    
    # No action verbs detected - return original text
    return text

