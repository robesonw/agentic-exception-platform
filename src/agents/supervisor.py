"""
SupervisorAgent implementation for Phase 2.

Provides pipeline oversight and intervention capabilities.
Runs after PolicyAgent and ResolutionAgent to review decisions for safety/consistency.
Can override nextStep to "ESCALATE" if confidence too low or policy breach detected.

Matches specification from docs/04-agent-templates.md and phase2-mvp-issues.md Issue 34.
"""

import logging
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


class SupervisorAgentError(Exception):
    """Raised when SupervisorAgent operations fail."""

    pass


class SupervisorAgent:
    """
    SupervisorAgent provides pipeline oversight and intervention.
    
    Responsibilities:
    - Review agent decisions for safety and consistency
    - Check confidence thresholds across agent chain
    - Verify policy compliance
    - Override nextStep to "ESCALATE" if needed
    - Never executes tools, only governs flow
    
    Rules:
    - Uses tenant guardrails + domain pack rules
    - Never executes tools
    - Only reviews and intervenes in flow
    """

    def __init__(
        self,
        domain_pack: DomainPack,
        tenant_policy: TenantPolicyPack,
        audit_logger: Optional[AuditLogger] = None,
        min_confidence_threshold: float = 0.6,
    ):
        """
        Initialize SupervisorAgent.
        
        Args:
            domain_pack: Domain Pack for rules and guardrails
            tenant_policy: Tenant Policy Pack for guardrails
            audit_logger: Optional AuditLogger for logging
            min_confidence_threshold: Minimum confidence threshold for escalation (default: 0.6)
        """
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.audit_logger = audit_logger
        self.min_confidence_threshold = min_confidence_threshold

    async def review_post_policy(
        self,
        exception: ExceptionRecord,
        policy_decision: AgentDecision,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Review PolicyAgent decision and intervene if needed.
        
        Called after PolicyAgent completes.
        
        Args:
            exception: ExceptionRecord being processed
            policy_decision: Decision from PolicyAgent
            context: Optional context with prior agent outputs
            
        Returns:
            AgentDecision with review result and potential override
        """
        context = context or {}
        prior_outputs = context.get("prior_outputs", {})
        
        # Check confidence chain
        confidence_issues = self._check_confidence_chain(prior_outputs, policy_decision)
        
        # Check policy compliance
        policy_breaches = self._check_policy_compliance(exception, policy_decision, context)
        
        # Check severity vs confidence mismatch
        severity_issues = self._check_severity_confidence_mismatch(
            exception, prior_outputs, policy_decision
        )
        
        # Determine if escalation is needed
        should_escalate = (
            len(confidence_issues) > 0
            or len(policy_breaches) > 0
            or len(severity_issues) > 0
        )
        
        # Build evidence
        evidence = [
            "SupervisorAgent review: post-policy checkpoint",
            f"PolicyAgent confidence: {policy_decision.confidence:.2f}",
        ]
        
        if confidence_issues:
            evidence.extend([f"Confidence issue: {issue}" for issue in confidence_issues])
        
        if policy_breaches:
            evidence.extend([f"Policy breach: {breach}" for breach in policy_breaches])
        
        if severity_issues:
            evidence.extend([f"Severity issue: {issue}" for issue in severity_issues])
        
        # Create decision
        if should_escalate:
            decision_text = "SupervisorAgent intervened: escalating due to safety concerns"
            next_step = "ESCALATE"
            confidence = 0.9  # High confidence in escalation decision
        else:
            decision_text = "SupervisorAgent approved: flow continues as planned"
            next_step = policy_decision.next_step  # Preserve original nextStep
            confidence = 0.8  # High confidence in approval
        
        decision = AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "policy_decision": policy_decision.model_dump(),
                "context": context,
            }
            self.audit_logger.log_agent_event(
                "SupervisorAgent", input_data, decision, exception.tenant_id
            )
        
        logger.info(
            f"SupervisorAgent review (post-policy) for exception {exception.exception_id}: "
            f"{'ESCALATE' if should_escalate else 'APPROVED'}"
        )
        
        return decision

    async def review_post_resolution(
        self,
        exception: ExceptionRecord,
        resolution_decision: AgentDecision,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Review ResolutionAgent decision and intervene if needed.
        
        Called after ResolutionAgent completes.
        
        Args:
            exception: ExceptionRecord being processed
            resolution_decision: Decision from ResolutionAgent
            context: Optional context with prior agent outputs
            
        Returns:
            AgentDecision with review result and potential override
        """
        context = context or {}
        prior_outputs = context.get("prior_outputs", {})
        
        # Check confidence chain
        confidence_issues = self._check_confidence_chain(prior_outputs, resolution_decision)
        
        # Check if resolution plan is safe
        safety_issues = self._check_resolution_safety(exception, resolution_decision, context)
        
        # Check for critical severity with low confidence
        critical_issues = self._check_critical_severity_handling(
            exception, prior_outputs, resolution_decision
        )
        
        # Determine if escalation is needed
        should_escalate = (
            len(confidence_issues) > 0
            or len(safety_issues) > 0
            or len(critical_issues) > 0
        )
        
        # Build evidence
        evidence = [
            "SupervisorAgent review: post-resolution checkpoint",
            f"ResolutionAgent confidence: {resolution_decision.confidence:.2f}",
        ]
        
        if confidence_issues:
            evidence.extend([f"Confidence issue: {issue}" for issue in confidence_issues])
        
        if safety_issues:
            evidence.extend([f"Safety issue: {issue}" for issue in safety_issues])
        
        if critical_issues:
            evidence.extend([f"Critical issue: {issue}" for issue in critical_issues])
        
        # Create decision
        if should_escalate:
            decision_text = "SupervisorAgent intervened: escalating due to safety concerns"
            next_step = "ESCALATE"
            confidence = 0.9  # High confidence in escalation decision
        else:
            decision_text = "SupervisorAgent approved: resolution plan is safe"
            next_step = resolution_decision.next_step  # Preserve original nextStep
            confidence = 0.8  # High confidence in approval
        
        decision = AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "resolution_decision": resolution_decision.model_dump(),
                "context": context,
            }
            self.audit_logger.log_agent_event(
                "SupervisorAgent", input_data, decision, exception.tenant_id
            )
        
        logger.info(
            f"SupervisorAgent review (post-resolution) for exception {exception.exception_id}: "
            f"{'ESCALATE' if should_escalate else 'APPROVED'}"
        )
        
        return decision

    def _check_confidence_chain(
        self, prior_outputs: dict[str, Any], current_decision: AgentDecision
    ) -> list[str]:
        """
        Check confidence chain across agents.
        
        Args:
            prior_outputs: Dictionary of prior agent outputs
            current_decision: Current agent decision
            
        Returns:
            List of confidence issues found
        """
        issues = []
        
        # Check current decision confidence
        if current_decision.confidence < self.min_confidence_threshold:
            issues.append(
                f"Current decision confidence ({current_decision.confidence:.2f}) "
                f"below threshold ({self.min_confidence_threshold:.2f})"
            )
        
        # Check prior agent confidences
        for agent_name, output in prior_outputs.items():
            if hasattr(output, "confidence"):
                if output.confidence < self.min_confidence_threshold:
                    issues.append(
                        f"{agent_name} confidence ({output.confidence:.2f}) "
                        f"below threshold ({self.min_confidence_threshold:.2f})"
                    )
        
        # Check for confidence degradation
        confidences = [
            output.confidence
            for output in prior_outputs.values()
            if hasattr(output, "confidence")
        ]
        if confidences:
            if current_decision.confidence < min(confidences) - 0.2:
                issues.append(
                    f"Confidence degraded significantly: "
                    f"{min(confidences):.2f} -> {current_decision.confidence:.2f}"
                )
        
        return issues

    def _check_policy_compliance(
        self,
        exception: ExceptionRecord,
        policy_decision: AgentDecision,
        context: dict[str, Any],
    ) -> list[str]:
        """
        Check policy compliance.
        
        Args:
            exception: ExceptionRecord
            policy_decision: PolicyAgent decision
            context: Context with prior outputs
            
        Returns:
            List of policy breaches found
        """
        issues = []
        
        # Get guardrails
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        
        # Check if CRITICAL severity requires approval but wasn't flagged
        if exception.severity == Severity.CRITICAL:
            # Check if human approval was required
            human_approval_required = context.get("humanApprovalRequired", False)
            if not human_approval_required:
                # Check if tenant policy requires approval for CRITICAL
                requires_approval = any(
                    rule.severity.upper() == "CRITICAL" and rule.require_approval
                    for rule in self.tenant_policy.human_approval_rules
                )
                if requires_approval:
                    issues.append(
                        "CRITICAL severity requires human approval but not flagged"
                    )
        
        # Check guardrails threshold
        if hasattr(guardrails, "human_approval_threshold"):
            threshold = guardrails.human_approval_threshold
            # If confidence is below threshold, should require approval
            if policy_decision.confidence < threshold:
                human_approval_required = context.get("humanApprovalRequired", False)
                if not human_approval_required:
                    issues.append(
                        f"Confidence ({policy_decision.confidence:.2f}) below "
                        f"approval threshold ({threshold:.2f}) but approval not required"
                    )
        
        return issues

    def _check_severity_confidence_mismatch(
        self,
        exception: ExceptionRecord,
        prior_outputs: dict[str, Any],
        policy_decision: AgentDecision,
    ) -> list[str]:
        """
        Check for severity vs confidence mismatches.
        
        Args:
            exception: ExceptionRecord
            prior_outputs: Prior agent outputs
            policy_decision: PolicyAgent decision
            
        Returns:
            List of severity issues found
        """
        issues = []
        
        # High severity should have high confidence
        if exception.severity in (Severity.HIGH, Severity.CRITICAL):
            if policy_decision.confidence < 0.7:
                issues.append(
                    f"High severity ({exception.severity.value}) but low confidence "
                    f"({policy_decision.confidence:.2f})"
                )
        
        # Check triage confidence if available
        triage_output = prior_outputs.get("triage")
        if triage_output and hasattr(triage_output, "confidence"):
            if exception.severity == Severity.CRITICAL and triage_output.confidence < 0.8:
                issues.append(
                    f"CRITICAL severity but triage confidence only {triage_output.confidence:.2f}"
                )
        
        return issues

    def _check_resolution_safety(
        self,
        exception: ExceptionRecord,
        resolution_decision: AgentDecision,
        context: dict[str, Any],
    ) -> list[str]:
        """
        Check resolution plan safety.
        
        Args:
            exception: ExceptionRecord
            resolution_decision: ResolutionAgent decision
            context: Context with prior outputs
            
        Returns:
            List of safety issues found
        """
        issues = []
        
        # Check if CRITICAL exception has low confidence resolution
        if exception.severity == Severity.CRITICAL:
            if resolution_decision.confidence < 0.8:
                issues.append(
                    f"CRITICAL exception resolved with low confidence "
                    f"({resolution_decision.confidence:.2f})"
                )
        
        # Check if resolution plan exists for actionable exception
        actionability = context.get("actionability", "")
        if actionability == "ACTIONABLE_APPROVED_PROCESS":
            # Should have a resolved plan
            resolved_plan = context.get("resolvedPlan")
            if not resolved_plan:
                issues.append("Actionable exception but no resolved plan found")
        
        return issues

    def _check_critical_severity_handling(
        self,
        exception: ExceptionRecord,
        prior_outputs: dict[str, Any],
        resolution_decision: AgentDecision,
    ) -> list[str]:
        """
        Check critical severity handling.
        
        Args:
            exception: ExceptionRecord
            prior_outputs: Prior agent outputs
            resolution_decision: ResolutionAgent decision
            
        Returns:
            List of critical issues found
        """
        issues = []
        
        if exception.severity == Severity.CRITICAL:
            # CRITICAL should have high confidence throughout
            for agent_name, output in prior_outputs.items():
                if hasattr(output, "confidence") and output.confidence < 0.8:
                    issues.append(
                        f"{agent_name} confidence ({output.confidence:.2f}) too low "
                        f"for CRITICAL severity"
                    )
            
            # CRITICAL resolution should have high confidence
            if resolution_decision.confidence < 0.8:
                issues.append(
                    f"Resolution confidence ({resolution_decision.confidence:.2f}) too low "
                    f"for CRITICAL severity"
                )
        
        return issues

