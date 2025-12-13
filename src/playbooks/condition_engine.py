"""
Playbook Condition Evaluation Engine for Phase 7 MVP.

Evaluates playbook conditions against exception attributes.
Reference: docs/phase7-playbooks-mvp.md Section 3.1
"""

import logging
import re
from typing import Any, Optional

from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


def evaluate_conditions(
    conditions: dict[str, Any],
    exception: ExceptionRecord,
    policy_pack: Optional[TenantPolicyPack] = None,
    sla_minutes_remaining: Optional[int] = None,
) -> dict[str, Any]:
    """
    Evaluate playbook conditions against exception attributes.
    
    Supports condition types:
    - domain: exact match
    - exception_type: exact or pattern match (supports wildcards: *, ?)
    - severity_in: array of allowed severities
    - severity: single severity value (exact match)
    - sla_minutes_remaining_lt: SLA window comparison
    - policy_tags: array of required policy tags (subset match - all required tags must be present)
    
    Args:
        conditions: Playbook conditions dict (can have "match" nested or at root, and "priority")
        exception: ExceptionRecord to evaluate
        policy_pack: Optional TenantPolicyPack for policy tag extraction
        sla_minutes_remaining: Optional minutes remaining until SLA deadline
        
    Returns:
        Dictionary with:
        - matches: bool (whether all conditions match)
        - priority: int (priority value from conditions, default 0)
        - reason: str (explanation of match result, for debugging/logging)
        - checked_conditions: list[str] (list of condition types that were checked)
        
    Examples:
        >>> conditions = {
        ...     "match": {
        ...         "domain": "Finance",
        ...         "exception_type": "Trade Settlement Failure",
        ...         "severity_in": ["high", "critical"],
        ...         "sla_minutes_remaining_lt": 60
        ...     },
        ...     "priority": 100
        ... }
        >>> result = evaluate_conditions(conditions, exception, policy_pack, 30)
        >>> result["matches"]  # True if all conditions match
    """
    if not conditions:
        return {
            "matches": False,
            "priority": 0,
            "reason": "No conditions provided",
            "checked_conditions": [],
        }
    
    # Extract match conditions (can be nested under "match" key or at root)
    match_conditions = conditions.get("match", conditions)
    priority = conditions.get("priority", 0)
    
    # Track which conditions were checked
    checked_conditions: list[str] = []
    failed_conditions: list[str] = []
    
    # Extract exception attributes
    domain = exception.normalized_context.get("domain")
    exception_type = exception.exception_type
    severity = exception.severity.value.lower() if exception.severity else None
    
    # Extract policy tags from exception or policy pack
    policy_tags: list[str] = []
    if policy_pack:
        # Policy tags would be in tenant_policy, but we need to check the structure
        # For MVP, we'll look for tags in normalized_context or tenant_policy metadata
        policy_tags = exception.normalized_context.get("policy_tags", [])
        if not policy_tags and hasattr(policy_pack, "tags"):
            policy_tags = getattr(policy_pack, "tags", [])
    else:
        policy_tags = exception.normalized_context.get("policy_tags", [])
    
    # Check domain match (exact)
    if "domain" in match_conditions:
        checked_conditions.append("domain")
        required_domain = match_conditions["domain"]
        if not isinstance(required_domain, str):
            logger.warning(f"Invalid domain condition: expected string, got {type(required_domain)}")
            failed_conditions.append(f"domain: invalid type {type(required_domain)}")
        elif domain != required_domain:
            failed_conditions.append(f"domain: expected '{required_domain}', got '{domain}'")
        # If domain is None and required_domain is set, it's a mismatch
        elif domain is None:
            failed_conditions.append(f"domain: required '{required_domain}', but exception has no domain")
    
    # Check exception_type match (exact or pattern)
    if "exception_type" in match_conditions:
        checked_conditions.append("exception_type")
        required_type = match_conditions["exception_type"]
        if not isinstance(required_type, str):
            logger.warning(f"Invalid exception_type condition: expected string, got {type(required_type)}")
            failed_conditions.append(f"exception_type: invalid type {type(required_type)}")
        elif exception_type is None:
            failed_conditions.append(f"exception_type: required '{required_type}', but exception has no type")
        else:
            # Support pattern matching (wildcards: * for any chars, ? for single char)
            if "*" in required_type or "?" in required_type:
                # Convert wildcard pattern to regex
                pattern = required_type.replace("*", ".*").replace("?", ".")
                if not re.match(f"^{pattern}$", exception_type, re.IGNORECASE):
                    failed_conditions.append(
                        f"exception_type: pattern '{required_type}' does not match '{exception_type}'"
                    )
            else:
                # Exact match (case-insensitive)
                if exception_type.lower() != required_type.lower():
                    failed_conditions.append(
                        f"exception_type: expected '{required_type}', got '{exception_type}'"
                    )
    
    # Check severity match (supports severity_in array or single severity)
    if "severity" in match_conditions or "severity_in" in match_conditions:
        checked_conditions.append("severity")
        if "severity_in" in match_conditions:
            allowed_severities = match_conditions["severity_in"]
            if not isinstance(allowed_severities, list):
                logger.warning(
                    f"Invalid severity_in format: expected list, got {type(allowed_severities)}"
                )
                failed_conditions.append(f"severity_in: invalid type {type(allowed_severities)}")
            else:
                # Normalize severity values to lowercase for comparison
                allowed_severities_lower = [
                    s.lower() if isinstance(s, str) else str(s).lower() for s in allowed_severities
                ]
                if severity is None:
                    failed_conditions.append(
                        f"severity_in: required one of {allowed_severities}, but exception has no severity"
                    )
                elif severity not in allowed_severities_lower:
                    failed_conditions.append(
                        f"severity_in: expected one of {allowed_severities}, got '{severity}'"
                    )
        elif "severity" in match_conditions:
            required_severity = match_conditions["severity"]
            if isinstance(required_severity, str):
                required_severity = required_severity.lower()
            else:
                required_severity = str(required_severity).lower()
            
            if severity is None:
                failed_conditions.append(
                    f"severity: required '{required_severity}', but exception has no severity"
                )
            elif severity != required_severity:
                failed_conditions.append(f"severity: expected '{required_severity}', got '{severity}'")
    
    # Check SLA window condition
    if "sla_minutes_remaining_lt" in match_conditions:
        checked_conditions.append("sla_minutes_remaining_lt")
        max_minutes = match_conditions["sla_minutes_remaining_lt"]
        if not isinstance(max_minutes, (int, float)):
            logger.warning(f"Invalid sla_minutes_remaining_lt: expected number, got {type(max_minutes)}")
            failed_conditions.append(f"sla_minutes_remaining_lt: invalid type {type(max_minutes)}")
        elif sla_minutes_remaining is None:
            failed_conditions.append("sla_minutes_remaining_lt: SLA deadline not available")
        elif sla_minutes_remaining >= max_minutes:
            failed_conditions.append(
                f"sla_minutes_remaining_lt: expected < {max_minutes} minutes, "
                f"got {sla_minutes_remaining} minutes"
            )
    
    # Check policy tags (subset match - all required tags must be present)
    if "policy_tags" in match_conditions:
        checked_conditions.append("policy_tags")
        required_tags = match_conditions["policy_tags"]
        if not isinstance(required_tags, list):
            logger.warning(f"Invalid policy_tags format: expected list, got {type(required_tags)}")
            failed_conditions.append(f"policy_tags: invalid type {type(required_tags)}")
        elif not required_tags:
            # Empty list means no policy tag requirements
            pass
        else:
            # Check if all required tags are present in exception policy_tags
            if not policy_tags:
                failed_conditions.append("policy_tags: no policy tags available in exception")
            else:
                missing_tags = set(required_tags) - set(policy_tags)
                if missing_tags:
                    failed_conditions.append(f"policy_tags: missing required tags {list(missing_tags)}")
    
    # Determine result
    if failed_conditions:
        reason = f"Conditions not met: {failed_conditions[0]}"
        if len(failed_conditions) > 1:
            reason += f" (and {len(failed_conditions) - 1} more)"
        return {
            "matches": False,
            "priority": priority,
            "reason": reason,
            "checked_conditions": checked_conditions,
        }
    
    # All conditions matched
    if checked_conditions:
        reason_parts = [f"matched {cond}" for cond in checked_conditions]
        reason = f"All conditions matched: {', '.join(reason_parts)}"
    else:
        reason = "No conditions to check (empty match conditions)"
    
    return {
        "matches": True,
        "priority": priority,
        "reason": reason,
        "checked_conditions": checked_conditions,
    }

