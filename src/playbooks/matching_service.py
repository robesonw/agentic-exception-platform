"""
Playbook Matching Service for Phase 7 MVP.

Implements playbook selection based on exception attributes and conditions.
Reference: docs/phase7-playbooks-mvp.md Sections 3.3 & 5.1
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from src.infrastructure.db.models import Playbook
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.models.exception_record import ExceptionRecord
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


@dataclass
class MatchingResult:
    """
    Result of playbook matching operation.
    
    Attributes:
        playbook: Selected Playbook instance, or None if no match found
        reasoning: Human-readable explanation of why this playbook was selected
    """
    playbook: Optional[Playbook]
    reasoning: str


class PlaybookMatchingService:
    """
    Service for matching exceptions to appropriate playbooks.
    
    Evaluates playbook conditions against exception attributes:
    - Domain
    - Exception type
    - Severity
    - SLA window (minutes remaining)
    - Policy tags from Tenant Policy Pack
    
    Ranks playbooks by priority and selects the best match.
    
    Reference: docs/phase7-playbooks-mvp.md Sections 3.3 & 5.1
    """
    
    def __init__(
        self,
        playbook_repository: PlaybookRepository,
    ):
        """
        Initialize the playbook matching service.
        
        Args:
            playbook_repository: Repository for loading playbooks
        """
        self.playbook_repository = playbook_repository
    
    async def match_playbook(
        self,
        tenant_id: str,
        exception: ExceptionRecord,
        tenant_policy: Optional[TenantPolicyPack] = None,
    ) -> MatchingResult:
        """
        Match an exception to an appropriate playbook.
        
        This method is idempotent - re-running does not create events or modify state.
        It only evaluates conditions and returns a recommendation.
        
        Args:
            tenant_id: Tenant identifier (must match exception.tenant_id)
            exception: ExceptionRecord to match
            tenant_policy: Optional TenantPolicyPack for policy tag evaluation
            
        Returns:
            MatchingResult with selected playbook (or None) and reasoning
            
        Raises:
            ValueError: If tenant_id doesn't match exception.tenant_id
        """
        # Validate tenant isolation
        if exception.tenant_id != tenant_id:
            raise ValueError(
                f"Tenant ID mismatch: exception.tenant_id={exception.tenant_id}, "
                f"provided tenant_id={tenant_id}"
            )
        
        # Load candidate playbooks for tenant
        candidate_playbooks = await self.playbook_repository.get_candidate_playbooks(tenant_id)
        
        if not candidate_playbooks:
            return MatchingResult(
                playbook=None,
                reasoning="No playbooks found for tenant"
            )
        
        # Extract exception attributes for condition evaluation
        domain = exception.normalized_context.get("domain")
        exception_type = exception.exception_type
        severity = exception.severity.value.lower() if exception.severity else None
        
        # Compute SLA minutes remaining (if SLA deadline exists in normalized_context)
        sla_minutes_remaining = None
        sla_deadline = exception.normalized_context.get("sla_deadline")
        if sla_deadline:
            if isinstance(sla_deadline, str):
                # Parse ISO datetime string
                try:
                    sla_deadline_dt = datetime.fromisoformat(sla_deadline.replace('Z', '+00:00'))
                except (ValueError, AttributeError):
                    logger.warning(f"Invalid SLA deadline format: {sla_deadline}")
                    sla_deadline_dt = None
            elif isinstance(sla_deadline, datetime):
                sla_deadline_dt = sla_deadline
            else:
                sla_deadline_dt = None
            
            if sla_deadline_dt:
                now = datetime.now(timezone.utc) if sla_deadline_dt.tzinfo else datetime.utcnow()
                if sla_deadline_dt.tzinfo:
                    now = now.replace(tzinfo=timezone.utc)
                delta = sla_deadline_dt - now
                sla_minutes_remaining = int(delta.total_seconds() / 60)
        
        # Extract policy tags from tenant policy pack or exception normalized_context
        policy_tags: list[str] = []
        # First, try to get from normalized_context (most common case)
        policy_tags = exception.normalized_context.get("policy_tags", [])
        # If not found and tenant_policy is provided, try to get from tenant_policy
        if not policy_tags and tenant_policy:
            if hasattr(tenant_policy, "tags"):
                policy_tags = getattr(tenant_policy, "tags", [])
        
        # Evaluate conditions for each playbook
        matching_playbooks: list[tuple[Playbook, int, str]] = []  # (playbook, priority, reason)
        
        for playbook in candidate_playbooks:
            match_result = self._evaluate_conditions(
                playbook=playbook,
                domain=domain,
                exception_type=exception_type,
                severity=severity,
                sla_minutes_remaining=sla_minutes_remaining,
                policy_tags=policy_tags,
            )
            
            if match_result["matches"]:
                priority = match_result.get("priority", 0)
                reason = match_result.get("reason", "Matched conditions")
                matching_playbooks.append((playbook, priority, reason))
        
        if not matching_playbooks:
            return MatchingResult(
                playbook=None,
                reasoning="No playbooks matched the exception conditions"
            )
        
        # Rank by priority (higher priority = better match)
        # If priority is equal, prefer newer playbooks (higher playbook_id)
        matching_playbooks.sort(key=lambda x: (-x[1], -x[0].playbook_id))
        
        # Select best match
        best_playbook, best_priority, best_reason = matching_playbooks[0]
        
        reasoning = (
            f"Selected playbook '{best_playbook.name}' (priority={best_priority}, "
            f"playbook_id={best_playbook.playbook_id}): {best_reason}"
        )
        
        if len(matching_playbooks) > 1:
            reasoning += f" (evaluated {len(matching_playbooks)} matching playbooks)"
        
        logger.info(
            f"Matched playbook for exception {exception.exception_id}: "
            f"playbook_id={best_playbook.playbook_id}, {reasoning}"
        )
        
        return MatchingResult(playbook=best_playbook, reasoning=reasoning)
    
    def _evaluate_conditions(
        self,
        playbook: Playbook,
        domain: Optional[str],
        exception_type: Optional[str],
        severity: Optional[str],
        sla_minutes_remaining: Optional[int],
        policy_tags: list[str],
    ) -> dict[str, Any]:
        """
        Evaluate playbook conditions against exception attributes.
        
        Supports condition types:
        - domain: exact match
        - exception_type: exact match
        - severity_in: array of allowed severities
        - sla_minutes_remaining_lt: SLA window comparison
        - policy_tags: array of required policy tags
        
        Args:
            playbook: Playbook to evaluate
            domain: Exception domain
            exception_type: Exception type
            severity: Exception severity (lowercase)
            sla_minutes_remaining: Minutes remaining until SLA deadline
            policy_tags: Policy tags from tenant policy pack
            
        Returns:
            Dictionary with:
            - matches: bool (whether conditions match)
            - priority: int (priority value if present, default 0)
            - reason: str (explanation of match)
        """
        conditions = playbook.conditions or {}
        
        # Extract match conditions (can be nested under "match" key or at root)
        match_conditions = conditions.get("match", conditions)
        priority = conditions.get("priority", 0)
        
        # Track which conditions were checked
        checked_conditions: list[str] = []
        failed_conditions: list[str] = []
        
        # Check domain match
        if "domain" in match_conditions:
            checked_conditions.append("domain")
            required_domain = match_conditions["domain"]
            if domain != required_domain:
                failed_conditions.append(f"domain: expected '{required_domain}', got '{domain}'")
                return {
                    "matches": False,
                    "priority": priority,
                    "reason": f"Domain mismatch: {failed_conditions[0]}"
                }
        
        # Check exception_type match
        if "exception_type" in match_conditions:
            checked_conditions.append("exception_type")
            required_type = match_conditions["exception_type"]
            if exception_type != required_type:
                failed_conditions.append(
                    f"exception_type: expected '{required_type}', got '{exception_type}'"
                )
                return {
                    "matches": False,
                    "priority": priority,
                    "reason": f"Exception type mismatch: {failed_conditions[0]}"
                }
        
        # Check severity match (supports severity_in array)
        if "severity" in match_conditions or "severity_in" in match_conditions:
            checked_conditions.append("severity")
            if "severity_in" in match_conditions:
                allowed_severities = match_conditions["severity_in"]
                if not isinstance(allowed_severities, list):
                    logger.warning(
                        f"Invalid severity_in format in playbook {playbook.playbook_id}: "
                        f"expected list, got {type(allowed_severities)}"
                    )
                    allowed_severities = []
                # Normalize severity values to lowercase for comparison
                allowed_severities_lower = [s.lower() if isinstance(s, str) else str(s).lower() 
                                          for s in allowed_severities]
                if severity not in allowed_severities_lower:
                    failed_conditions.append(
                        f"severity_in: expected one of {allowed_severities}, got '{severity}'"
                    )
                    return {
                        "matches": False,
                        "priority": priority,
                        "reason": f"Severity mismatch: {failed_conditions[0]}"
                    }
            elif "severity" in match_conditions:
                required_severity = match_conditions["severity"]
                if isinstance(required_severity, str):
                    required_severity = required_severity.lower()
                if severity != required_severity:
                    failed_conditions.append(
                        f"severity: expected '{required_severity}', got '{severity}'"
                    )
                    return {
                        "matches": False,
                        "priority": priority,
                        "reason": f"Severity mismatch: {failed_conditions[0]}"
                    }
        
        # Check SLA window condition
        if "sla_minutes_remaining_lt" in match_conditions:
            checked_conditions.append("sla_minutes_remaining_lt")
            max_minutes = match_conditions["sla_minutes_remaining_lt"]
            if sla_minutes_remaining is None:
                failed_conditions.append(
                    "sla_minutes_remaining_lt: SLA deadline not available"
                )
                return {
                    "matches": False,
                    "priority": priority,
                    "reason": f"SLA condition not met: {failed_conditions[0]}"
                }
            if sla_minutes_remaining >= max_minutes:
                failed_conditions.append(
                    f"sla_minutes_remaining_lt: expected < {max_minutes} minutes, "
                    f"got {sla_minutes_remaining} minutes"
                )
                return {
                    "matches": False,
                    "priority": priority,
                    "reason": f"SLA condition not met: {failed_conditions[0]}"
                }
        
        # Check policy tags
        if "policy_tags" in match_conditions:
            checked_conditions.append("policy_tags")
            required_tags = match_conditions["policy_tags"]
            if not isinstance(required_tags, list):
                logger.warning(
                    f"Invalid policy_tags format in playbook {playbook.playbook_id}: "
                    f"expected list, got {type(required_tags)}"
                )
                required_tags = []
            # Check if all required tags are present in exception policy_tags
            if not policy_tags:
                failed_conditions.append(
                    "policy_tags: no policy tags available in exception"
                )
                return {
                    "matches": False,
                    "priority": priority,
                    "reason": f"Policy tags condition not met: {failed_conditions[0]}"
                }
            missing_tags = set(required_tags) - set(policy_tags)
            if missing_tags:
                failed_conditions.append(
                    f"policy_tags: missing required tags {list(missing_tags)}"
                )
                return {
                    "matches": False,
                    "priority": priority,
                    "reason": f"Policy tags condition not met: {failed_conditions[0]}"
                }
        
        # All conditions matched
        reason_parts = [f"matched {cond}" for cond in checked_conditions]
        reason = f"Playbook matches: {', '.join(reason_parts)}"
        
        return {
            "matches": True,
            "priority": priority,
            "reason": reason
        }

