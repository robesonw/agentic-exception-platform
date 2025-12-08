"""
Copilot Retrieval Utilities for Phase 5 - AI Co-Pilot.

Provides functions to retrieve exceptions, domain packs, and policy packs
for use in Co-Pilot context. All functions enforce tenant isolation and
format data for LLM context consumption.

Reference: docs/phase5-copilot-mvp.md Section 3 (Retrieval utilities)
"""

import logging
from typing import Optional

from src.domainpack.loader import DomainPackRegistry
from src.models.exception_record import ExceptionRecord, Severity
from src.orchestrator.store import get_exception_store
from src.tenantpack.loader import TenantPolicyRegistry

logger = logging.getLogger(__name__)


def _format_exception_for_llm(
    exception: ExceptionRecord, pipeline_result: Optional[dict] = None
) -> dict:
    """
    Format exception record for LLM context.
    
    Converts ExceptionRecord to a dictionary suitable for LLM prompt context.
    Includes key fields and omits sensitive or unnecessary details.
    
    Args:
        exception: ExceptionRecord to format
        pipeline_result: Optional pipeline result dictionary
        
    Returns:
        Dictionary with formatted exception data for LLM context
    """
    # Convert exception to dict using model_dump with by_alias=True
    # This ensures field names match the API schema (camelCase)
    exception_dict = exception.model_dump(by_alias=True)
    
    # Add pipeline status if available
    if pipeline_result:
        exception_dict["pipelineStatus"] = pipeline_result.get("status", "UNKNOWN")
        # Optionally include key pipeline info (but keep it concise for LLM)
        if "stages" in pipeline_result:
            exception_dict["pipelineStages"] = list(pipeline_result["stages"].keys())
    
    return exception_dict


def _matches_domain(exception: ExceptionRecord, domain: Optional[str]) -> bool:
    """
    Check if exception matches the specified domain.
    
    Args:
        exception: ExceptionRecord to check
        domain: Optional domain filter (None means no domain filter)
        
    Returns:
        True if domain matches or domain is None, False otherwise
    """
    if domain is None:
        return True
    
    # Domain is stored in normalized_context
    exception_domain = exception.normalized_context.get("domain") if exception.normalized_context else None
    
    return exception_domain == domain


def get_exception_by_id(
    tenant_id: str, domain: Optional[str], exception_id: str
) -> Optional[dict]:
    """
    Retrieve a single exception by ID.
    
    Enforces tenant isolation and optionally filters by domain.
    Returns formatted exception data for LLM context.
    
    Args:
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        exception_id: Exception identifier (e.g., "EX-12345")
        
    Returns:
        Dictionary with formatted exception data for LLM context, or None if not found
        
    Raises:
        ValueError: If tenant_id is empty or None
        
    Example:
        >>> exception = get_exception_by_id("TENANT_001", "Capital Markets", "EX-12345")
        >>> if exception:
        ...     print(exception["exceptionId"])
        'EX-12345'
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if not exception_id:
        return None
    
    logger.debug(f"Retrieving exception {exception_id} for tenant {tenant_id} (domain: {domain})")
    
    # Get exception store
    exception_store = get_exception_store()
    
    # Retrieve exception (enforces tenant isolation at store level)
    stored = exception_store.get_exception(tenant_id, exception_id)
    
    if stored is None:
        logger.debug(f"Exception {exception_id} not found for tenant {tenant_id}")
        return None
    
    exception, pipeline_result = stored
    
    # Double-check tenant isolation (defense in depth)
    if exception.tenant_id != tenant_id:
        logger.error(
            f"Tenant isolation violation: Exception {exception_id} belongs to "
            f"tenant {exception.tenant_id}, not {tenant_id}"
        )
        return None
    
    # Filter by domain if specified
    if not _matches_domain(exception, domain):
        logger.debug(
            f"Exception {exception_id} does not match domain {domain} "
            f"(exception domain: {exception.normalized_context.get('domain') if exception.normalized_context else None})"
        )
        return None
    
    # Format for LLM context
    return _format_exception_for_llm(exception, pipeline_result)


def get_recent_exceptions(
    tenant_id: str, domain: Optional[str], limit: int = 10
) -> list[dict]:
    """
    Retrieve the most recent exceptions for a tenant/domain.
    
    Returns the latest N exceptions sorted by timestamp (newest first).
    Enforces tenant isolation and optionally filters by domain.
    
    Args:
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        limit: Maximum number of exceptions to return (default: 10)
        
    Returns:
        List of dictionaries with formatted exception data for LLM context
        (sorted by timestamp, newest first)
        
    Raises:
        ValueError: If tenant_id is empty or None, or limit is invalid
        
    Example:
        >>> exceptions = get_recent_exceptions("TENANT_001", "Capital Markets", limit=5)
        >>> len(exceptions) <= 5
        True
        >>> # Exceptions are sorted by timestamp (newest first)
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if limit < 0:
        raise ValueError("limit must be non-negative")
    
    if limit == 0:
        return []
    
    logger.debug(f"Retrieving recent exceptions for tenant {tenant_id} (domain: {domain}, limit: {limit})")
    
    # Get exception store
    exception_store = get_exception_store()
    
    # Get all exceptions for tenant (enforces tenant isolation at store level)
    all_exceptions = exception_store.get_tenant_exceptions(tenant_id)
    
    if not all_exceptions:
        logger.debug(f"No exceptions found for tenant {tenant_id}")
        return []
    
    # Filter by domain and verify tenant isolation
    filtered = []
    for exception, pipeline_result in all_exceptions:
        # Double-check tenant isolation (defense in depth)
        if exception.tenant_id != tenant_id:
            logger.warning(
                f"Tenant isolation violation: Exception {exception.exception_id} belongs to "
                f"tenant {exception.tenant_id}, not {tenant_id}"
            )
            continue
        
        # Filter by domain if specified
        if not _matches_domain(exception, domain):
            continue
        
        filtered.append((exception, pipeline_result))
    
    # Sort by timestamp (newest first)
    filtered.sort(key=lambda x: x[0].timestamp, reverse=True)
    
    # Limit results
    limited = filtered[:limit]
    
    # Format for LLM context
    return [_format_exception_for_llm(exception, pipeline_result) for exception, pipeline_result in limited]


def get_exceptions_by_severity(
    tenant_id: str, domain: Optional[str], severity: Severity
) -> list[dict]:
    """
    Retrieve exceptions filtered by severity for a tenant/domain.
    
    Returns all exceptions matching the specified severity level.
    Enforces tenant isolation and optionally filters by domain.
    
    Args:
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        severity: Severity level to filter by (LOW, MEDIUM, HIGH, CRITICAL)
        
    Returns:
        List of dictionaries with formatted exception data for LLM context
        (sorted by timestamp, newest first)
        
    Raises:
        ValueError: If tenant_id is empty or None
        
    Example:
        >>> critical = get_exceptions_by_severity("TENANT_001", "Capital Markets", Severity.CRITICAL)
        >>> all(e.get("severity") == "CRITICAL" for e in critical)
        True
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    logger.debug(
        f"Retrieving exceptions by severity {severity.value} for tenant {tenant_id} (domain: {domain})"
    )
    
    # Get exception store
    exception_store = get_exception_store()
    
    # Get all exceptions for tenant (enforces tenant isolation at store level)
    all_exceptions = exception_store.get_tenant_exceptions(tenant_id)
    
    if not all_exceptions:
        logger.debug(f"No exceptions found for tenant {tenant_id}")
        return []
    
    # Filter by severity, domain, and verify tenant isolation
    filtered = []
    for exception, pipeline_result in all_exceptions:
        # Double-check tenant isolation (defense in depth)
        if exception.tenant_id != tenant_id:
            logger.warning(
                f"Tenant isolation violation: Exception {exception.exception_id} belongs to "
                f"tenant {exception.tenant_id}, not {tenant_id}"
            )
            continue
        
        # Filter by severity
        if exception.severity != severity:
            continue
        
        # Filter by domain if specified
        if not _matches_domain(exception, domain):
            continue
        
        filtered.append((exception, pipeline_result))
    
    # Sort by timestamp (newest first)
    filtered.sort(key=lambda x: x[0].timestamp, reverse=True)
    
    # Format for LLM context
    return [_format_exception_for_llm(exception, pipeline_result) for exception, pipeline_result in filtered]


def get_domain_pack_summary(tenant_id: str, domain: str) -> Optional[dict]:
    """
    Retrieve a summary of the domain pack for a tenant/domain.
    
    Returns a small, LLM-friendly summary of the domain pack including:
    - Domain name
    - Exception types (names and descriptions)
    - Key tools (names and descriptions)
    - Guardrails summary
    - Playbooks summary
    
    Enforces tenant isolation by using tenant_id in registry lookup.
    
    Args:
        tenant_id: Tenant identifier (required for isolation)
        domain: Domain name identifier
        
    Returns:
        Dictionary with formatted domain pack summary for LLM context, or None if not found
        
    Raises:
        ValueError: If tenant_id or domain is empty or None
        
    Example:
        >>> summary = get_domain_pack_summary("TENANT_001", "Capital Markets")
        >>> if summary:
        ...     print(summary["domainName"])
        'Capital Markets'
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if not domain:
        raise ValueError("domain is required and cannot be empty")
    
    logger.debug(f"Retrieving domain pack summary for tenant {tenant_id}, domain {domain}")
    
    # Get domain pack registry
    registry = DomainPackRegistry()
    
    # Retrieve domain pack (enforces tenant isolation at registry level)
    domain_pack = registry.get_latest(domain_name=domain, tenant_id=tenant_id)
    
    if domain_pack is None:
        logger.debug(f"Domain pack not found for tenant {tenant_id}, domain {domain}")
        return None
    
    # Create small, LLM-friendly summary
    summary = {
        "domainName": domain_pack.domain_name,
        "exceptionTypes": [
            {
                "name": name,
                "description": exc_type.description,
                "detectionRulesCount": len(exc_type.detection_rules),
                "severityRulesCount": len(exc_type.severity_rules),
            }
            for name, exc_type in domain_pack.exception_types.items()
        ],
        "tools": [
            {
                "name": name,
                "description": tool.description,
                "type": tool.tool_type,
            }
            for name, tool in domain_pack.tools.items()
        ],
        "guardrails": {
            "allowListsCount": len(domain_pack.guardrails.allow_lists),
            "blockListsCount": len(domain_pack.guardrails.block_lists),
            "humanApprovalThreshold": domain_pack.guardrails.human_approval_threshold,
        },
        "playbooksCount": len(domain_pack.playbooks),
        "entitiesCount": len(domain_pack.entities),
    }
    
    return summary


def get_policy_pack_summary(tenant_id: str) -> Optional[dict]:
    """
    Retrieve a summary of the tenant policy pack for a tenant.
    
    Returns a small, LLM-friendly summary of the tenant policy pack including:
    - Tenant ID and domain name
    - Approved tools count
    - Custom playbooks summary
    - Custom severity overrides summary
    - Guardrails summary
    
    Enforces tenant isolation by using tenant_id in registry lookup.
    
    Args:
        tenant_id: Tenant identifier (required for isolation)
        
    Returns:
        Dictionary with formatted policy pack summary for LLM context, or None if not found
        
    Raises:
        ValueError: If tenant_id is empty or None
        
    Example:
        >>> summary = get_policy_pack_summary("TENANT_001")
        >>> if summary:
        ...     print(summary["tenantId"])
        'TENANT_001'
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    logger.debug(f"Retrieving policy pack summary for tenant {tenant_id}")
    
    # Get tenant policy registry
    registry = TenantPolicyRegistry()
    
    # Retrieve tenant policy pack (enforces tenant isolation at registry level)
    policy_pack = registry.get(tenant_id)
    
    if policy_pack is None:
        logger.debug(f"Policy pack not found for tenant {tenant_id}")
        return None
    
    # Create small, LLM-friendly summary
    summary = {
        "tenantId": policy_pack.tenant_id,
        "domainName": policy_pack.domain_name,
        "approvedToolsCount": len(policy_pack.approved_tools),
        "approvedTools": policy_pack.approved_tools[:10],  # Limit to first 10 for LLM context
        "customPlaybooks": [
            {
                "exceptionType": playbook.exception_type,
                "stepsCount": len(playbook.steps),
            }
            for playbook in policy_pack.custom_playbooks
        ],
        "customSeverityOverrides": [
            {
                "exceptionType": override.exception_type,
                "severity": override.severity,
            }
            for override in policy_pack.custom_severity_overrides
        ],
        "customGuardrails": {
            "allowListsCount": len(policy_pack.custom_guardrails.allow_lists) if policy_pack.custom_guardrails else 0,
            "blockListsCount": len(policy_pack.custom_guardrails.block_lists) if policy_pack.custom_guardrails else 0,
        } if policy_pack.custom_guardrails else None,
        "humanApprovalRules": [
            {
                "severity": rule.severity,
                "requireApproval": rule.require_approval,
            }
            for rule in policy_pack.human_approval_rules
        ],
    }
    
    return summary


def get_exception_timeline(
    tenant_id: str, domain: Optional[str], exception_id: str
) -> Optional[dict]:
    """
    Retrieve exception timeline/fields for a specific exception.
    
    Returns key exception fields and audit trail in a timeline format
    suitable for LLM context. Includes:
    - Exception ID, type, severity, status
    - Timestamp
    - Audit trail entries (chronologically ordered)
    - Key fields from normalized context
    
    Enforces tenant isolation and optionally filters by domain.
    
    Args:
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        exception_id: Exception identifier (e.g., "EX-12345")
        
    Returns:
        Dictionary with formatted exception timeline for LLM context, or None if not found
        
    Raises:
        ValueError: If tenant_id is empty or None
        
    Example:
        >>> timeline = get_exception_timeline("TENANT_001", "Capital Markets", "EX-12345")
        >>> if timeline:
        ...     print(timeline["exceptionId"])
        'EX-12345'
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if not exception_id:
        return None
    
    logger.debug(f"Retrieving exception timeline for {exception_id}, tenant {tenant_id} (domain: {domain})")
    
    # Get exception store
    exception_store = get_exception_store()
    
    # Retrieve exception (enforces tenant isolation at store level)
    stored = exception_store.get_exception(tenant_id, exception_id)
    
    if stored is None:
        logger.debug(f"Exception {exception_id} not found for tenant {tenant_id}")
        return None
    
    exception, pipeline_result = stored
    
    # Double-check tenant isolation (defense in depth)
    if exception.tenant_id != tenant_id:
        logger.error(
            f"Tenant isolation violation: Exception {exception_id} belongs to "
            f"tenant {exception.tenant_id}, not {tenant_id}"
        )
        return None
    
    # Filter by domain if specified
    if not _matches_domain(exception, domain):
        logger.debug(
            f"Exception {exception_id} does not match domain {domain} "
            f"(exception domain: {exception.normalized_context.get('domain') if exception.normalized_context else None})"
        )
        return None
    
    # Format audit trail entries for timeline
    audit_entries = []
    for entry in exception.audit_trail:
        audit_entries.append({
            "timestamp": entry.timestamp.isoformat() if hasattr(entry.timestamp, "isoformat") else str(entry.timestamp),
            "actor": entry.actor,
            "action": entry.action,
        })
    
    # Create timeline summary
    timeline = {
        "exceptionId": exception.exception_id,
        "tenantId": exception.tenant_id,
        "exceptionType": exception.exception_type,
        "severity": exception.severity.value if exception.severity else None,
        "resolutionStatus": exception.resolution_status.value,
        "sourceSystem": exception.source_system,
        "timestamp": exception.timestamp.isoformat() if hasattr(exception.timestamp, "isoformat") else str(exception.timestamp),
        "auditTrail": audit_entries,
        "keyFields": {
            "detectedRules": exception.detected_rules,
            "suggestedActions": exception.suggested_actions,
            "normalizedContextKeys": list(exception.normalized_context.keys()) if exception.normalized_context else [],
        },
    }
    
    # Add pipeline status if available
    if pipeline_result:
        timeline["pipelineStatus"] = pipeline_result.get("status", "UNKNOWN")
        if "stages" in pipeline_result:
            timeline["pipelineStages"] = list(pipeline_result["stages"].keys())
    
    return timeline

