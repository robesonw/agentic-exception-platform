"""
FeedbackAgent implementation for MVP and Phase 2.
Captures resolution outcomes and prepares for learning.
Phase 2: Integrates with PolicyLearning for policy suggestions.

Matches specification from docs/04-agent-templates.md and phase2-mvp-issues.md Issue 35.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.domain.events.exception_events import (
    ActorType,
    EventType,
    FeedbackCapturedPayload,
    validate_and_build_event,
)
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.learning.policy_learning import PolicyLearning
from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord, ResolutionStatus
from src.repository.dto import ExceptionEventCreateDTO
from src.repository.exception_events_repository import ExceptionEventRepository

logger = logging.getLogger(__name__)


class FeedbackAgentError(Exception):
    """Raised when FeedbackAgent operations fail."""

    pass


class FeedbackAgent:
    """
    FeedbackAgent captures resolution outcomes and prepares for learning.
    
    MVP Responsibilities:
    - Accept ResolutionAgent output
    - Append outcome placeholder fields:
        * resolutionStatus
        * feedbackCapturedAt
        * learningArtifacts (empty list for MVP)
    - Produce AgentDecision with feedback format
    - Log input/output via AuditLogger
    
    Constraints:
    - No learning automation in Phase 1
    - Must remain domain-agnostic
    """

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        policy_learning: Optional[PolicyLearning] = None,
        playbook_repository: Optional[PlaybookRepository] = None,
        exception_events_repository: Optional[ExceptionEventRepository] = None,
    ):
        """
        Initialize FeedbackAgent.
        
        Args:
            audit_logger: Optional AuditLogger for logging
            policy_learning: Optional PolicyLearning instance for Phase 2
            playbook_repository: Optional PlaybookRepository for playbook metrics (P7-14)
            exception_events_repository: Optional ExceptionEventRepository for event emission (P7-14)
        """
        self.audit_logger = audit_logger
        self.policy_learning = policy_learning
        self.playbook_repository = playbook_repository
        self.exception_events_repository = exception_events_repository

    async def process(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Capture resolution outcome and prepare for learning.
        
        Args:
            exception: ExceptionRecord from ResolutionAgent
            context: Optional context from ResolutionAgent (includes resolvedPlan)
            
        Returns:
            AgentDecision with feedback capture confirmation
            
        Raises:
            FeedbackAgentError: If feedback capture fails
        """
        context = context or {}
        
        # Append outcome placeholder fields
        self._append_outcome_fields(exception, context)
        
        # Phase 2: Ingest feedback for learning if policy_learning is available
        if self.policy_learning:
            try:
                # Extract outcome from exception status
                outcome = self._determine_outcome(exception, context)
                
                # Extract human override from context if available
                human_override = context.get("humanOverride")
                
                # Phase 3: Determine if resolution was successful
                resolution_successful = self._determine_resolution_success(exception, context)
                
                # Phase 3: Extract policy rules that were applied (from context or prior outputs)
                policy_rules_applied = self._extract_policy_rules_applied(context)
                
                # Ingest feedback
                self.policy_learning.ingest_feedback(
                    tenant_id=exception.tenant_id,
                    exception_id=exception.exception_id,
                    outcome=outcome,
                    human_override=human_override,
                    exception_type=exception.exception_type,
                    severity=exception.severity.value if exception.severity else None,
                    context=context,
                    resolution_successful=resolution_successful,
                    policy_rules_applied=policy_rules_applied,
                )
            except Exception as e:
                logger.warning(f"Failed to ingest feedback for learning: {e}")
        
        # Phase 7: Compute playbook metrics when exception is resolved/completed (P7-14)
        playbook_metrics = None
        if exception.resolution_status == ResolutionStatus.RESOLVED:
            try:
                playbook_metrics = await self._compute_playbook_metrics(exception)
            except Exception as e:
                logger.warning(f"Failed to compute playbook metrics for exception {exception.exception_id}: {e}")

        # Create agent decision
        decision = self._create_decision(exception, context, playbook_metrics)
        
        # Phase 7: Emit FeedbackCaptured event including metrics (P7-14)
        if self.exception_events_repository:
            try:
                feedback_type = "positive" if exception.resolution_status == ResolutionStatus.RESOLVED else "negative"
                feedback_captured_payload = FeedbackCapturedPayload(
                    feedback_type=feedback_type,
                    feedback_text=None,  # MVP: no user feedback text
                    rating=None,  # MVP: no rating
                    resolution_effective=exception.resolution_status == ResolutionStatus.RESOLVED,
                    playbook_id=playbook_metrics.get("playbook_id") if playbook_metrics else None,
                    total_steps=playbook_metrics.get("total_steps") if playbook_metrics else None,
                    completed_steps=playbook_metrics.get("completed_steps") if playbook_metrics else None,
                    duration=playbook_metrics.get("duration") if playbook_metrics else None,
                    last_actor=playbook_metrics.get("last_actor") if playbook_metrics else None,
                )
                event_envelope = validate_and_build_event(
                    event_type=EventType.FEEDBACK_CAPTURED,
                    payload_dict=feedback_captured_payload.model_dump(),
                    tenant_id=exception.tenant_id,
                    exception_id=exception.exception_id,
                    actor_type=ActorType.AGENT,
                    actor_id="FeedbackAgent",
                )
                await self.exception_events_repository.append_event_if_new(
                    ExceptionEventCreateDTO(**event_envelope.model_dump())
                )
                logger.debug(f"Emitted FeedbackCaptured event for exception {exception.exception_id}")
            except Exception as e:
                logger.error(f"Failed to emit FeedbackCaptured event for exception {exception.exception_id}: {e}")
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context,
            }
            self.audit_logger.log_agent_event("FeedbackAgent", input_data, decision, exception.tenant_id)
        
        return decision

    def _append_outcome_fields(
        self, exception: ExceptionRecord, context: dict[str, Any]
    ) -> None:
        """
        Append outcome placeholder fields to exception.
        
        Args:
            exception: ExceptionRecord to update
            context: Context from ResolutionAgent
        """
        # Update resolution status if not already set
        # For MVP, if we have a resolved plan, mark as IN_PROGRESS or RESOLVED
        # Otherwise, keep existing status
        if exception.resolution_status == ResolutionStatus.OPEN:
            # Check if we have a resolved plan from ResolutionAgent
            if context.get("resolvedPlan") or self._has_resolved_plan_in_context(context):
                exception.resolution_status = ResolutionStatus.IN_PROGRESS
            # If no plan, keep as OPEN (non-actionable)
        
        # Add feedback captured timestamp to normalized context
        if exception.normalized_context is None:
            exception.normalized_context = {}
        
        exception.normalized_context["feedbackCapturedAt"] = datetime.now(timezone.utc).isoformat()
        
        # Add learning artifacts placeholder (empty list for MVP)
        if "learningArtifacts" not in exception.normalized_context:
            exception.normalized_context["learningArtifacts"] = []

    def _has_resolved_plan_in_context(self, context: dict[str, Any]) -> bool:
        """
        Check if context contains a resolved plan.
        
        Args:
            context: Context from ResolutionAgent
            
        Returns:
            True if resolved plan exists
        """
        # Check if resolvedPlan is directly in context
        if "resolvedPlan" in context:
            resolved_plan = context["resolvedPlan"]
            if isinstance(resolved_plan, list) and len(resolved_plan) > 0:
                return True
        
        # Check if it's in prior outputs (from ResolutionAgent decision evidence)
        if "prior_outputs" in context:
            resolution_output = context["prior_outputs"].get("resolution")
            if resolution_output and hasattr(resolution_output, "evidence"):
                for evidence in resolution_output.evidence:
                    if "resolvedPlan:" in evidence or "Resolved plan" in evidence:
                        return True
        
        return False

    def _determine_resolution_success(
        self, exception: ExceptionRecord, context: dict[str, Any]
    ) -> Optional[bool]:
        """
        Determine if resolution was successful.
        
        Phase 3: Analyzes exception status and context to determine success.
        
        Args:
            exception: ExceptionRecord
            context: Context from ResolutionAgent
            
        Returns:
            True if successful, False if failed, None if unknown
        """
        # Check resolution status
        if exception.resolution_status == ResolutionStatus.RESOLVED:
            return True
        elif exception.resolution_status == ResolutionStatus.FAILED:
            return False
        
        # Check outcome from context
        outcome = self._determine_outcome(exception, context)
        if outcome in ("SUCCESS", "RESOLVED"):
            return True
        elif outcome in ("FAILED", "ESCALATED"):
            return False
        
        return None

    def _extract_policy_rules_applied(self, context: dict[str, Any]) -> list[str]:
        """
        Extract policy rule IDs that were applied during processing.
        
        Phase 3: Extracts rule IDs from context for outcome tracking.
        
        Args:
            context: Context from previous agents
            
        Returns:
            List of policy rule IDs
        """
        rule_ids = []
        
        # Check if policy rules are explicitly in context
        if "policyRulesApplied" in context:
            rules = context["policyRulesApplied"]
            if isinstance(rules, list):
                rule_ids.extend(rules)
        
        # Check if policy decision has evidence with rule information
        if "prior_outputs" in context:
            policy_output = context["prior_outputs"].get("policy")
            if policy_output and hasattr(policy_output, "evidence"):
                for evidence_item in policy_output.evidence:
                    # Look for rule references in evidence
                    if isinstance(evidence_item, str):
                        # Try to extract rule IDs from evidence strings
                        # Format: "Applied rule: rule_id" or "Rule: rule_id"
                        if "rule:" in evidence_item.lower() or "applied rule" in evidence_item.lower():
                            # Simple extraction - in production, would use more robust parsing
                            parts = evidence_item.split(":")
                            if len(parts) > 1:
                                rule_id = parts[-1].strip()
                                if rule_id:
                                    rule_ids.append(rule_id)
        
        # If no explicit rules found, use exception type as a rule identifier (fallback)
        if not rule_ids and "exception_type" in context:
            rule_ids.append(f"exception_type:{context['exception_type']}")
        
        return rule_ids

    async def _compute_playbook_metrics(
        self, exception: ExceptionRecord
    ) -> Optional[dict[str, Any]]:
        """
        Compute playbook metrics when exception is resolved/completed.
        
        Phase 7 P7-14: Computes metrics including:
        - playbook_id: The playbook ID if one was assigned
        - total_steps: Total number of steps in the playbook
        - completed_steps: Number of steps completed (based on current_step)
        - duration: Time from exception creation to resolution (in seconds)
        - last_actor: Last actor that performed an action (from events or audit trail)
        
        Args:
            exception: ExceptionRecord with resolution status
            
        Returns:
            Dictionary with metrics or None if no playbook was assigned
        """
        if not exception.current_playbook_id:
            return None
        
        if not self.playbook_repository or not self.exception_events_repository:
            logger.debug(
                f"PlaybookRepository or ExceptionEventRepository not available "
                f"for metrics computation for exception {exception.exception_id}"
            )
            return None
        
        try:
            # Get playbook and steps
            playbook, steps = await self.playbook_repository.get_playbook_with_steps(
                exception.current_playbook_id, exception.tenant_id
            )
            
            total_steps = len(steps)
            completed_steps = exception.current_step if exception.current_step else 0
            
            # Compute duration: from exception timestamp to now
            now = datetime.now(timezone.utc)
            duration = (now - exception.timestamp).total_seconds()
            
            # Get last actor from events (most recent event's actor_id)
            last_actor = None
            try:
                events = await self.exception_events_repository.get_events_for_exception(
                    exception.tenant_id, exception.exception_id
                )
                if events:
                    # Events are ordered by created_at ASC, so last one is most recent
                    last_event = events[-1]
                    last_actor = last_event.actor_id
            except Exception as e:
                logger.warning(f"Failed to get events for last actor: {e}")
                # Fallback to audit trail if available
                if exception.audit_trail:
                    last_audit_entry = exception.audit_trail[-1]
                    last_actor = last_audit_entry.actor
            
            return {
                "playbook_id": exception.current_playbook_id,
                "total_steps": total_steps,
                "completed_steps": completed_steps,
                "duration": duration,
                "last_actor": last_actor,
            }
        except Exception as e:
            logger.error(f"Error computing playbook metrics for exception {exception.exception_id}: {e}")
            return None

    def _create_decision(
        self, exception: ExceptionRecord, context: dict[str, Any], playbook_metrics: Optional[dict[str, Any]] = None
    ) -> AgentDecision:
        """
        Create agent decision from feedback capture results.
        
        Args:
            exception: ExceptionRecord with outcome fields appended
            context: Context from ResolutionAgent
            
        Returns:
            AgentDecision
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Exception ID: {exception.exception_id}")
        evidence.append(f"Resolution status: {exception.resolution_status.value}")
        
        # Add feedback timestamp
        if exception.normalized_context and "feedbackCapturedAt" in exception.normalized_context:
            evidence.append(f"Feedback captured at: {exception.normalized_context['feedbackCapturedAt']}")
        
        # Add resolution summary
        if self._has_resolved_plan_in_context(context):
            evidence.append("Resolution plan executed")
            # Try to extract plan details from context
            if "resolvedPlan" in context:
                resolved_plan = context["resolvedPlan"]
                if isinstance(resolved_plan, list):
                    evidence.append(f"Actions executed: {len(resolved_plan)}")
        else:
            evidence.append("No resolution plan (non-actionable or escalated)")
        
        # Add learning artifacts placeholder info
        if exception.normalized_context and "learningArtifacts" in exception.normalized_context:
            artifacts = exception.normalized_context["learningArtifacts"]
            evidence.append(f"Learning artifacts: {len(artifacts)} (MVP placeholder)")
        
        # Phase 2: Get policy suggestions if policy_learning is available
        policy_suggestions = []
        if self.policy_learning:
            try:
                suggestions = self.policy_learning.get_policy_suggestions(
                    tenant_id=exception.tenant_id,
                    min_confidence=0.7,
                )
                policy_suggestions = [s.model_dump() for s in suggestions]
                
                if policy_suggestions:
                    evidence.append(f"Policy suggestions available: {len(policy_suggestions)}")
                    # Add summary of suggestions
                    for suggestion in policy_suggestions[:3]:  # Show top 3
                        evidence.append(
                            f"Suggestion: {suggestion['description']} "
                            f"(confidence: {suggestion['confidence']:.2f})"
                        )
            except Exception as e:
                logger.warning(f"Failed to get policy suggestions: {e}")
        
        # Phase 7: Add playbook metrics to evidence if available (P7-14)
        if playbook_metrics:
            evidence.append(f"Playbook ID: {playbook_metrics.get('playbook_id')}")
            evidence.append(f"Total steps: {playbook_metrics.get('total_steps')}")
            evidence.append(f"Completed steps: {playbook_metrics.get('completed_steps')}")
            if playbook_metrics.get('duration') is not None:
                evidence.append(f"Duration: {playbook_metrics.get('duration'):.2f} seconds")
            if playbook_metrics.get('last_actor'):
                evidence.append(f"Last actor: {playbook_metrics.get('last_actor')}")

        # Add final resolution summary
        evidence.append(f"Final status: {exception.resolution_status.value}")
        if exception.exception_type:
            evidence.append(f"Exception type: {exception.exception_type}")
        if exception.severity:
            evidence.append(f"Severity: {exception.severity.value}")

        # Decision is always "FEEDBACK_CAPTURED" for MVP
        decision_text = "FEEDBACK_CAPTURED"
        
        # Confidence is always 1.0 for MVP (we're just capturing, not learning)
        confidence = 1.0
        
        # Next step is always "complete"
        next_step = "complete"

        decision = AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )
        
        # Phase 2: Attach policy suggestions to decision metadata
        # (In production, this would be in a separate metadata field)
        if policy_suggestions:
            # Add to evidence as structured data indicator
            decision.evidence.append(f"policySuggestions: {len(policy_suggestions)} available")
        
        return decision

    def _determine_outcome(
        self, exception: ExceptionRecord, context: dict[str, Any]
    ) -> str:
        """
        Determine outcome from exception status and context.
        
        Args:
            exception: ExceptionRecord
            context: Context from processing
            
        Returns:
            Outcome string
        """
        status = exception.resolution_status
        
        if status == ResolutionStatus.RESOLVED:
            return "RESOLVED"
        elif status == ResolutionStatus.ESCALATED:
            return "ESCALATED"
        elif status == ResolutionStatus.PENDING_APPROVAL:
            return "PENDING_APPROVAL"
        elif status == ResolutionStatus.IN_PROGRESS:
            return "IN_PROGRESS"
        else:
            return "OPEN"
