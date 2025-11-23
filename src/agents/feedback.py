"""
FeedbackAgent implementation for MVP.
Captures resolution outcomes and prepares for learning (placeholder).
Matches specification from docs/04-agent-templates.md
"""

from datetime import datetime, timezone
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord, ResolutionStatus


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
    ):
        """
        Initialize FeedbackAgent.
        
        Args:
            audit_logger: Optional AuditLogger for logging
        """
        self.audit_logger = audit_logger

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
        
        # Create agent decision
        decision = self._create_decision(exception, context)
        
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

    def _create_decision(
        self, exception: ExceptionRecord, context: dict[str, Any]
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

        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )
