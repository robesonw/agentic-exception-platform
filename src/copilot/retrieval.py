"""
Copilot Retrieval Utilities for Phase 5 - AI Co-Pilot.

Provides functions to retrieve exceptions, domain packs, and policy packs
for use in Co-Pilot context. All functions enforce tenant isolation and
format data for LLM context consumption.

Phase 6 P6-21: Integrated with PostgreSQL repositories.

Reference: docs/phase5-copilot-mvp.md Section 3 (Retrieval utilities)
"""

import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domainpack.loader import DomainPackRegistry
from src.infrastructure.db.models import Exception as ExceptionModel, ExceptionEvent
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.repository.dto import ExceptionFilter, EventFilter
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository
from src.tenantpack.loader import TenantPolicyRegistry

logger = logging.getLogger(__name__)


def _db_exception_to_dict(
    db_exception: ExceptionModel,
    events: Optional[list[ExceptionEvent]] = None,
) -> dict:
    """
    Convert database Exception model to dictionary format for LLM context.
    
    Args:
        db_exception: Database Exception model instance
        events: Optional list of events for timeline/audit trail
        
    Returns:
        Dictionary with formatted exception data for LLM context
    """
    # Map severity enum to string
    severity_map = {
        "low": Severity.LOW,
        "medium": Severity.MEDIUM,
        "high": Severity.HIGH,
        "critical": Severity.CRITICAL,
    }
    severity_enum = severity_map.get(
        db_exception.severity.value if hasattr(db_exception.severity, 'value') else str(db_exception.severity).lower(),
        Severity.MEDIUM
    )
    
    # Map status enum to ResolutionStatus
    status_map = {
        "open": ResolutionStatus.OPEN,
        "analyzing": ResolutionStatus.IN_PROGRESS,
        "resolved": ResolutionStatus.RESOLVED,
        "escalated": ResolutionStatus.ESCALATED,
    }
    resolution_status = status_map.get(
        db_exception.status.value if hasattr(db_exception.status, 'value') else str(db_exception.status).lower(),
        ResolutionStatus.OPEN
    )
    
    # Build normalized context
    normalized_context = {"domain": db_exception.domain}
    if db_exception.entity:
        normalized_context["entity"] = db_exception.entity
    if db_exception.amount is not None:
        normalized_context["amount"] = float(db_exception.amount)
    if db_exception.sla_deadline:
        normalized_context["sla_deadline"] = db_exception.sla_deadline.isoformat()
    
    # Create ExceptionRecord
    exception = ExceptionRecord(
        exception_id=db_exception.exception_id,
        tenant_id=db_exception.tenant_id,
        source_system=db_exception.source_system,
        exception_type=db_exception.type,
        severity=severity_enum,
        timestamp=db_exception.created_at,
        raw_payload={},  # Not stored in DB
        normalized_context=normalized_context,
        resolution_status=resolution_status,
        audit_trail=[],  # Will be populated from events if provided
    )
    
    # Build audit trail from events if provided
    if events:
        from src.models.exception_record import AuditEntry
        for event in events:
            actor_type = event.actor_type.value if hasattr(event.actor_type, 'value') else str(event.actor_type)
            exception.audit_trail.append(
                AuditEntry(
                    action=event.event_type,
                    timestamp=event.created_at,
                    actor=f"{actor_type}:{event.actor_id or 'system'}",
                )
            )
    
    # Convert to dict using model_dump with by_alias=True (camelCase)
    exception_dict = exception.model_dump(by_alias=True)
    
    # Add pipeline status (inferred from status)
    exception_dict["pipelineStatus"] = "COMPLETED" if resolution_status == ResolutionStatus.RESOLVED else "IN_PROGRESS"
    
    return exception_dict


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


async def get_exception_by_id(
    session: AsyncSession,
    tenant_id: str,
    domain: Optional[str],
    exception_id: str,
) -> Optional[dict]:
    """
    Retrieve a single exception by ID using repository.
    
    Enforces tenant isolation and optionally filters by domain.
    Returns formatted exception data for LLM context.
    
    Args:
        session: Database session
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        exception_id: Exception identifier (e.g., "EX-12345")
        
    Returns:
        Dictionary with formatted exception data for LLM context, or None if not found
        
    Raises:
        ValueError: If tenant_id is empty or None
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if not exception_id:
        return None
    
    logger.debug(f"Retrieving exception {exception_id} for tenant {tenant_id} (domain: {domain})")
    
    try:
        repo = ExceptionRepository(session)
        db_exception = await repo.get_exception(tenant_id, exception_id)
        
        if db_exception is None:
            logger.debug(f"Exception {exception_id} not found for tenant {tenant_id}")
            return None
        
        # Filter by domain if specified
        if domain and db_exception.domain != domain:
            logger.debug(f"Exception {exception_id} does not match domain {domain} (exception domain: {db_exception.domain})")
            return None
        
        # Get events for timeline
        event_repo = ExceptionEventRepository(session)
        events = await event_repo.get_events_for_exception(tenant_id, exception_id)
        
        # Convert to dict format
        return _db_exception_to_dict(db_exception, events)
    except Exception as e:
        logger.warning(f"Error retrieving exception from repository: {e}", exc_info=True)
        return None


async def get_recent_exceptions(
    session: AsyncSession,
    tenant_id: str,
    domain: Optional[str],
    limit: int = 10,
) -> list[dict]:
    """
    Retrieve the most recent exceptions for a tenant/domain using repository.
    
    Returns the latest N exceptions sorted by created_at (newest first).
    Enforces tenant isolation and optionally filters by domain.
    
    Args:
        session: Database session
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        limit: Maximum number of exceptions to return (default: 10)
        
    Returns:
        List of dictionaries with formatted exception data for LLM context
        (sorted by timestamp, newest first)
        
    Raises:
        ValueError: If tenant_id is empty or None, or limit is invalid
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if limit < 0:
        raise ValueError("limit must be non-negative")
    
    if limit == 0:
        return []
    
    logger.debug(f"Retrieving recent exceptions for tenant {tenant_id} (domain: {domain}, limit: {limit})")
    
    try:
        repo = ExceptionRepository(session)
        
        # Build filter
        filters = ExceptionFilter()
        if domain:
            filters.domain = domain
        
        # List exceptions (ordered by created_at DESC, newest first)
        result = await repo.list_exceptions(
            tenant_id=tenant_id,
            filters=filters,
            page=1,
            page_size=limit,
        )
        
        # Convert to dict format
        exceptions = []
        for db_exception in result.items:
            exception_dict = _db_exception_to_dict(db_exception)
            exceptions.append(exception_dict)
        
        return exceptions
    except Exception as e:
        logger.warning(f"Error retrieving recent exceptions from repository: {e}", exc_info=True)
        return []


async def get_similar_exceptions(
    session: AsyncSession,
    tenant_id: str,
    domain: Optional[str] = None,
    exception_type: Optional[str] = None,
    limit: int = 10,
) -> list[dict]:
    """
    Find similar exceptions for Co-Pilot contextual retrieval.
    
    Uses ExceptionRepository.find_similar_exceptions() to retrieve exceptions
    matching the specified domain and/or exception type.
    
    Args:
        session: Database session
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter
        exception_type: Optional exception type filter
        limit: Maximum number of results (default: 10)
        
    Returns:
        List of dictionaries with formatted exception data for LLM context
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    logger.debug(
        f"Finding similar exceptions for tenant {tenant_id} "
        f"(domain: {domain}, type: {exception_type}, limit: {limit})"
    )
    
    try:
        repo = ExceptionRepository(session)
        similar = await repo.find_similar_exceptions(
            tenant_id=tenant_id,
            domain=domain,
            exception_type=exception_type,
            limit=limit,
        )
        
        # Convert to dict format
        exceptions = []
        for db_exception in similar:
            exception_dict = _db_exception_to_dict(db_exception)
            exceptions.append(exception_dict)
        
        return exceptions
    except Exception as e:
        logger.warning(f"Error finding similar exceptions from repository: {e}", exc_info=True)
        return []


async def get_exceptions_by_entity(
    session: AsyncSession,
    tenant_id: str,
    entity: str,
    limit: int = 50,
) -> list[dict]:
    """
    Get exceptions by entity identifier for Co-Pilot contextual retrieval.
    
    Uses ExceptionRepository.get_exceptions_by_entity() to retrieve exceptions
    for a specific entity (e.g., counterparty, patient, account).
    
    Args:
        session: Database session
        tenant_id: Tenant identifier (required for isolation)
        entity: Entity identifier
        limit: Maximum number of results (default: 50)
        
    Returns:
        List of dictionaries with formatted exception data for LLM context
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if not entity:
        return []
    
    logger.debug(f"Getting exceptions by entity for tenant {tenant_id} (entity: {entity}, limit: {limit})")
    
    try:
        repo = ExceptionRepository(session)
        exceptions = await repo.get_exceptions_by_entity(
            tenant_id=tenant_id,
            entity=entity,
            limit=limit,
        )
        
        # Convert to dict format
        result = []
        for db_exception in exceptions:
            exception_dict = _db_exception_to_dict(db_exception)
            result.append(exception_dict)
        
        return result
    except Exception as e:
        logger.warning(f"Error getting exceptions by entity from repository: {e}", exc_info=True)
        return []


async def get_imminent_sla_breaches(
    session: AsyncSession,
    tenant_id: str,
    within_minutes: int = 60,
    limit: int = 100,
) -> list[dict]:
    """
    Get exceptions with imminent SLA breaches for Co-Pilot contextual retrieval.
    
    Uses ExceptionRepository.get_imminent_sla_breaches() to retrieve exceptions
    at risk of SLA breach within the specified time window.
    
    Args:
        session: Database session
        tenant_id: Tenant identifier (required for isolation)
        within_minutes: Time window in minutes (default: 60)
        limit: Maximum number of results (default: 100)
        
    Returns:
        List of dictionaries with formatted exception data for LLM context
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    logger.debug(
        f"Getting imminent SLA breaches for tenant {tenant_id} "
        f"(within_minutes: {within_minutes}, limit: {limit})"
    )
    
    try:
        repo = ExceptionRepository(session)
        breaches = await repo.get_imminent_sla_breaches(
            tenant_id=tenant_id,
            within_minutes=within_minutes,
            limit=limit,
        )
        
        # Convert to dict format
        result = []
        for db_exception in breaches:
            exception_dict = _db_exception_to_dict(db_exception)
            result.append(exception_dict)
        
        return result
    except Exception as e:
        logger.warning(f"Error getting imminent SLA breaches from repository: {e}", exc_info=True)
        return []


def get_exceptions_by_severity(
    tenant_id: str, domain: Optional[str], severity: Severity
) -> list[dict]:
    """
    Retrieve exceptions filtered by severity for a tenant/domain.
    
    DEPRECATED: This function is kept for backward compatibility but should
    be replaced with repository calls. For new code, use get_recent_exceptions
    with ExceptionFilter.
    
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
    """
    logger.warning(
        "get_exceptions_by_severity is deprecated. Use repository calls with ExceptionFilter instead."
    )
    # This function is kept for backward compatibility but should not be used in new code
    # It would need session injection to work properly
    return []


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


async def get_exception_timeline(
    session: AsyncSession,
    tenant_id: str,
    domain: Optional[str],
    exception_id: str,
) -> Optional[dict]:
    """
    Retrieve exception timeline/events for a specific exception using repository.
    
    Returns key exception fields and event timeline in a format suitable for LLM context.
    Includes:
    - Exception ID, type, severity, status
    - Timestamp
    - Event timeline (chronologically ordered)
    - Key fields from normalized context
    
    Enforces tenant isolation and optionally filters by domain.
    
    Args:
        session: Database session
        tenant_id: Tenant identifier (required for isolation)
        domain: Optional domain filter (None means no domain filter)
        exception_id: Exception identifier (e.g., "EX-12345")
        
    Returns:
        Dictionary with formatted exception timeline for LLM context, or None if not found
        
    Raises:
        ValueError: If tenant_id is empty or None
    """
    if not tenant_id:
        raise ValueError("tenant_id is required and cannot be empty")
    
    if not exception_id:
        return None
    
    logger.debug(f"Retrieving exception timeline for {exception_id}, tenant {tenant_id} (domain: {domain})")
    
    try:
        # Get exception
        repo = ExceptionRepository(session)
        db_exception = await repo.get_exception(tenant_id, exception_id)
        
        if db_exception is None:
            logger.debug(f"Exception {exception_id} not found for tenant {tenant_id}")
            return None
        
        # Filter by domain if specified
        if domain and db_exception.domain != domain:
            logger.debug(
                f"Exception {exception_id} does not match domain {domain} "
                f"(exception domain: {db_exception.domain})"
            )
            return None
        
        # Get events for timeline
        event_repo = ExceptionEventRepository(session)
        events = await event_repo.get_events_for_exception(tenant_id, exception_id)
        
        # Format events for timeline
        event_entries = []
        for event in events:
            actor_type = event.actor_type.value if hasattr(event.actor_type, 'value') else str(event.actor_type)
            event_entries.append({
                "timestamp": event.created_at.isoformat() if event.created_at else None,
                "event_type": event.event_type,
                "actor_type": actor_type,
                "actor_id": event.actor_id,
                "payload": event.payload if isinstance(event.payload, dict) else {},
            })
        
        # Create timeline summary
        severity_map = {
            "low": "LOW",
            "medium": "MEDIUM",
            "high": "HIGH",
            "critical": "CRITICAL",
        }
        severity_str = severity_map.get(
            db_exception.severity.value if hasattr(db_exception.severity, 'value') else str(db_exception.severity).lower(),
            "MEDIUM"
        )
        
        status_map = {
            "open": "OPEN",
            "analyzing": "IN_PROGRESS",
            "resolved": "RESOLVED",
            "escalated": "ESCALATED",
        }
        status_str = status_map.get(
            db_exception.status.value if hasattr(db_exception.status, 'value') else str(db_exception.status).lower(),
            "OPEN"
        )
        
        timeline = {
            "exceptionId": db_exception.exception_id,
            "tenantId": db_exception.tenant_id,
            "exceptionType": db_exception.type,
            "severity": severity_str,
            "resolutionStatus": status_str,
            "sourceSystem": db_exception.source_system,
            "timestamp": db_exception.created_at.isoformat() if db_exception.created_at else None,
            "eventTimeline": event_entries,
            "keyFields": {
                "domain": db_exception.domain,
                "entity": db_exception.entity,
                "slaDeadline": db_exception.sla_deadline.isoformat() if db_exception.sla_deadline else None,
            },
        }
        
        return timeline
    except Exception as e:
        logger.warning(f"Error retrieving exception timeline from repository: {e}", exc_info=True)
        return None
