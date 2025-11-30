"""
SupervisorAgent implementation for Phase 2 and Phase 3.

Provides pipeline oversight and intervention capabilities.
Runs after PolicyAgent and ResolutionAgent to review decisions for safety/consistency.
Can override nextStep to "ESCALATE" if confidence too low or policy breach detected.

Phase 3: Enhanced with LLM oversight reasoning.

Matches specification from:
- docs/04-agent-templates.md
- phase2-mvp-issues.md Issue 34
- phase3-mvp-issues.md P3-4
"""

import json
import logging
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.llm.fallbacks import llm_or_rules
from src.llm.provider import LLMClient
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
        llm_client: Optional[LLMClient] = None,
    ):
        """
        Initialize SupervisorAgent.
        
        Args:
            domain_pack: Domain Pack for rules and guardrails
            tenant_policy: Tenant Policy Pack for guardrails
            audit_logger: Optional AuditLogger for logging
            min_confidence_threshold: Minimum confidence threshold for escalation (default: 0.6)
            llm_client: Optional LLMClient for Phase 3 LLM-enhanced oversight reasoning
        """
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.audit_logger = audit_logger
        self.min_confidence_threshold = min_confidence_threshold
        self.llm_client = llm_client

    async def review_post_policy(
        self,
        exception: ExceptionRecord,
        policy_decision: AgentDecision,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Review PolicyAgent decision and intervene if needed.
        
        Phase 3: Enhanced with LLM oversight reasoning.
        Falls back to rule-based logic if LLM unavailable.
        
        Called after PolicyAgent completes.
        
        Args:
            exception: ExceptionRecord being processed
            policy_decision: Decision from PolicyAgent
            context: Optional context with prior agent outputs (includes triage_decision)
            
        Returns:
            AgentDecision with review result and potential override
            (includes structured reasoning if LLM was used)
        """
        context = context or {}
        prior_outputs = context.get("prior_outputs", {})
        
        # Phase 3: Use LLM-enhanced oversight if available, otherwise fallback to rule-based
        if self.llm_client:
            try:
                # Build context snapshot for LLM
                context_snapshot = self._build_context_snapshot(
                    exception, prior_outputs, policy_decision, context
                )
                
                # Build prompt
                prompt = self.build_supervisor_prompt(context_snapshot)
                
                # Get rule-based evaluation for fallback
                rule_based_result = self._evaluate_rule_based_post_policy(
                    exception, prior_outputs, policy_decision, context
                )
                
                # Call LLM with fallback to rule-based logic
                llm_result = llm_or_rules(
                    llm_client=self.llm_client,
                    agent_name="SupervisorAgent",
                    tenant_id=exception.tenant_id,
                    schema_name="supervisor",
                    prompt=prompt,
                    rule_based_fn=lambda: self._create_rule_based_supervisor_result(
                        exception, rule_based_result, "post_policy"
                    ),
                    audit_logger=self.audit_logger,
                )
                
                # Merge LLM result with rule-based evaluation
                # CRITICAL: LLM cannot override guardrails - if rule-based says ESCALATE, enforce it
                decision = self._merge_supervisor_results(
                    exception, policy_decision, llm_result, rule_based_result, context
                )
                
            except Exception as e:
                logger.warning(f"LLM-enhanced supervisor review failed: {e}, falling back to rule-based")
                # Fall through to rule-based logic
                return await self._review_post_policy_rule_based(
                    exception, policy_decision, context
                )
        else:
            # No LLM client, use rule-based logic
            return await self._review_post_policy_rule_based(exception, policy_decision, context)
        
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
            f"{decision.next_step}"
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
        
        Phase 3: Enhanced with LLM oversight reasoning.
        Falls back to rule-based logic if LLM unavailable.
        
        Called after ResolutionAgent completes.
        
        Args:
            exception: ExceptionRecord being processed
            resolution_decision: Decision from ResolutionAgent
            context: Optional context with prior agent outputs (includes triage_decision, policy_decision)
            
        Returns:
            AgentDecision with review result and potential override
            (includes structured reasoning if LLM was used)
        """
        context = context or {}
        prior_outputs = context.get("prior_outputs", {})
        
        # Phase 3: Use LLM-enhanced oversight if available, otherwise fallback to rule-based
        if self.llm_client:
            try:
                # Build context snapshot for LLM
                context_snapshot = self._build_context_snapshot(
                    exception, prior_outputs, resolution_decision, context, checkpoint="post_resolution"
                )
                
                # Build prompt
                prompt = self.build_supervisor_prompt(context_snapshot)
                
                # Get rule-based evaluation for fallback
                rule_based_result = self._evaluate_rule_based_post_resolution(
                    exception, prior_outputs, resolution_decision, context
                )
                
                # Call LLM with fallback to rule-based logic
                llm_result = llm_or_rules(
                    llm_client=self.llm_client,
                    agent_name="SupervisorAgent",
                    tenant_id=exception.tenant_id,
                    schema_name="supervisor",
                    prompt=prompt,
                    rule_based_fn=lambda: self._create_rule_based_supervisor_result(
                        exception, rule_based_result, "post_resolution"
                    ),
                    audit_logger=self.audit_logger,
                )
                
                # Merge LLM result with rule-based evaluation
                # CRITICAL: LLM cannot override guardrails - if rule-based says ESCALATE, enforce it
                decision = self._merge_supervisor_results(
                    exception, resolution_decision, llm_result, rule_based_result, context
                )
                
            except Exception as e:
                logger.warning(f"LLM-enhanced supervisor review failed: {e}, falling back to rule-based")
                # Fall through to rule-based logic
                return await self._review_post_resolution_rule_based(
                    exception, resolution_decision, context
                )
        else:
            # No LLM client, use rule-based logic
            return await self._review_post_resolution_rule_based(exception, resolution_decision, context)
        
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
            f"{decision.next_step}"
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

    def _build_context_snapshot(
        self,
        exception: ExceptionRecord,
        prior_outputs: dict[str, Any],
        current_decision: AgentDecision,
        context: dict[str, Any],
        checkpoint: str = "post_policy",
    ) -> dict[str, Any]:
        """
        Build context snapshot for LLM oversight reasoning.
        
        Args:
            exception: ExceptionRecord being processed
            prior_outputs: Prior agent outputs (triage, policy, etc.)
            current_decision: Current agent decision being reviewed
            context: Full context dictionary
            checkpoint: Checkpoint name ("post_policy" or "post_resolution")
            
        Returns:
            Dictionary with context snapshot for LLM
        """
        snapshot = {
            "exception": {
                "exception_id": exception.exception_id,
                "tenant_id": exception.tenant_id,
                "exception_type": exception.exception_type,
                "severity": exception.severity.value if exception.severity else "UNKNOWN",
                "source_system": exception.source_system,
            },
            "checkpoint": checkpoint,
            "current_decision": {
                "decision": current_decision.decision,
                "confidence": current_decision.confidence,
                "next_step": current_decision.next_step,
                "evidence": current_decision.evidence[:5],  # Limit to first 5
            },
            "agent_chain": {},
        }
        
        # Add triage decision if available
        triage_output = prior_outputs.get("triage")
        if triage_output:
            snapshot["agent_chain"]["triage"] = {
                "decision": triage_output.decision if hasattr(triage_output, "decision") else str(triage_output),
                "confidence": triage_output.confidence if hasattr(triage_output, "confidence") else 0.0,
                "evidence": triage_output.evidence[:3] if hasattr(triage_output, "evidence") else [],
            }
        
        # Add policy decision if available
        policy_output = prior_outputs.get("policy")
        if policy_output:
            snapshot["agent_chain"]["policy"] = {
                "decision": policy_output.decision if hasattr(policy_output, "decision") else str(policy_output),
                "confidence": policy_output.confidence if hasattr(policy_output, "confidence") else 0.0,
                "next_step": policy_output.next_step if hasattr(policy_output, "next_step") else "",
                "evidence": policy_output.evidence[:3] if hasattr(policy_output, "evidence") else [],
            }
        
        # Add resolution decision if available (for post-resolution checkpoint)
        if checkpoint == "post_resolution":
            resolution_output = prior_outputs.get("resolution")
            if resolution_output:
                snapshot["agent_chain"]["resolution"] = {
                    "decision": resolution_output.decision if hasattr(resolution_output, "decision") else str(resolution_output),
                    "confidence": resolution_output.confidence if hasattr(resolution_output, "confidence") else 0.0,
                    "evidence": resolution_output.evidence[:3] if hasattr(resolution_output, "evidence") else [],
                }
        
        # Add guardrails context
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        snapshot["guardrails"] = {
            "human_approval_threshold": guardrails.human_approval_threshold if guardrails else 0.7,
            "min_confidence_threshold": self.min_confidence_threshold,
        }
        
        return snapshot

    def build_supervisor_prompt(self, context_snapshot: dict[str, Any]) -> str:
        """
        Build prompt for LLM supervisor oversight reasoning.
        
        Combines exception details, agent chain decisions, and guardrails into a structured prompt.
        
        Args:
            context_snapshot: Context snapshot dictionary from _build_context_snapshot
            
        Returns:
            Formatted prompt string for LLM
        """
        prompt_parts = []
        
        # Base prompt from agent template
        prompt_parts.append(
            "You are the SupervisorAgent. Oversee pipeline; intervene if anomalies "
            "(e.g., low confidence chain, inconsistencies between agents, high risk + low confidence combos, policy violation risks). "
            "Review the agent chain decisions and determine if escalation or approval is required."
        )
        
        # Exception details
        exception_info = context_snapshot["exception"]
        prompt_parts.append("\n## Exception Details:")
        prompt_parts.append(f"- Exception ID: {exception_info['exception_id']}")
        prompt_parts.append(f"- Tenant ID: {exception_info['tenant_id']}")
        prompt_parts.append(f"- Exception Type: {exception_info['exception_type']}")
        prompt_parts.append(f"- Severity: {exception_info['severity']}")
        prompt_parts.append(f"- Source System: {exception_info['source_system']}")
        
        # Agent chain decisions
        prompt_parts.append("\n## Agent Chain Decisions:")
        agent_chain = context_snapshot["agent_chain"]
        
        if "triage" in agent_chain:
            triage = agent_chain["triage"]
            prompt_parts.append(f"\n### TriageAgent:")
            prompt_parts.append(f"- Decision: {triage['decision']}")
            prompt_parts.append(f"- Confidence: {triage['confidence']:.2f}")
            if triage.get("evidence"):
                prompt_parts.append(f"- Key Evidence: {', '.join(str(e)[:50] for e in triage['evidence'][:2])}")
        
        if "policy" in agent_chain:
            policy = agent_chain["policy"]
            prompt_parts.append(f"\n### PolicyAgent:")
            prompt_parts.append(f"- Decision: {policy['decision']}")
            prompt_parts.append(f"- Confidence: {policy['confidence']:.2f}")
            prompt_parts.append(f"- Next Step: {policy['next_step']}")
            if policy.get("evidence"):
                prompt_parts.append(f"- Key Evidence: {', '.join(str(e)[:50] for e in policy['evidence'][:2])}")
        
        if "resolution" in agent_chain:
            resolution = agent_chain["resolution"]
            prompt_parts.append(f"\n### ResolutionAgent:")
            prompt_parts.append(f"- Decision: {resolution['decision']}")
            prompt_parts.append(f"- Confidence: {resolution['confidence']:.2f}")
            if resolution.get("evidence"):
                prompt_parts.append(f"- Key Evidence: {', '.join(str(e)[:50] for e in resolution['evidence'][:2])}")
        
        # Current decision being reviewed
        current = context_snapshot["current_decision"]
        prompt_parts.append(f"\n## Current Decision (Being Reviewed):")
        prompt_parts.append(f"- Decision: {current['decision']}")
        prompt_parts.append(f"- Confidence: {current['confidence']:.2f}")
        prompt_parts.append(f"- Next Step: {current['next_step']}")
        
        # Guardrails
        guardrails = context_snapshot["guardrails"]
        prompt_parts.append(f"\n## Guardrails:")
        prompt_parts.append(f"- Human Approval Threshold: {guardrails['human_approval_threshold']:.2f}")
        prompt_parts.append(f"- Min Confidence Threshold: {guardrails['min_confidence_threshold']:.2f}")
        
        # Instructions
        prompt_parts.append(
            "\n## Instructions:"
            "\nReview the agent chain and check for:"
            "\n1. Inconsistencies between agents (e.g., triage says HIGH severity but policy allows auto-action)"
            "\n2. High risk + low confidence combos (e.g., CRITICAL severity with confidence < 0.8)"
            "\n3. Policy violation risks (e.g., guardrails require approval but not flagged)"
            "\n4. Confidence degradation across the chain"
            "\n\nProvide:"
            "\n1. Oversight decision: APPROVED_FLOW, INTERVENED (require approval), or ESCALATED"
            "\n2. Intervention reason (if intervened)"
            "\n3. Escalation reason (if escalated)"
            "\n4. Anomaly detection and description (if any anomalies found)"
            "\n5. Agent chain review (summary of each agent's decision quality)"
            "\n6. Recommended action"
            "\n7. Structured reasoning steps"
            "\n8. Evidence references"
            "\n9. Suggested human message (if intervention or escalation - a clear message for operators)"
            "\n\nCRITICAL: If guardrails require escalation or approval, you MUST respect that. "
            "You cannot approve flows that guardrails have blocked."
        )
        
        return "\n".join(prompt_parts)

    def _evaluate_rule_based_post_policy(
        self,
        exception: ExceptionRecord,
        prior_outputs: dict[str, Any],
        policy_decision: AgentDecision,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate supervisor oversight using rule-based logic (post-policy checkpoint).
        
        Returns a dictionary with rule-based evaluation results.
        
        Args:
            exception: ExceptionRecord
            prior_outputs: Prior agent outputs
            policy_decision: PolicyAgent decision
            context: Full context
            
        Returns:
            Dictionary with rule-based evaluation results
        """
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
        
        # Check for inconsistencies
        inconsistencies = []
        triage_output = prior_outputs.get("triage")
        if triage_output and hasattr(triage_output, "confidence"):
            if exception.severity == Severity.CRITICAL and triage_output.confidence < 0.8:
                inconsistencies.append("CRITICAL severity but low triage confidence")
            if policy_decision.confidence < triage_output.confidence - 0.2:
                inconsistencies.append("Policy confidence degraded significantly from triage")
        
        return {
            "should_escalate": should_escalate,
            "confidence_issues": confidence_issues,
            "policy_breaches": policy_breaches,
            "severity_issues": severity_issues,
            "inconsistencies": inconsistencies,
        }

    def _evaluate_rule_based_post_resolution(
        self,
        exception: ExceptionRecord,
        prior_outputs: dict[str, Any],
        resolution_decision: AgentDecision,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Evaluate supervisor oversight using rule-based logic (post-resolution checkpoint).
        
        Returns a dictionary with rule-based evaluation results.
        
        Args:
            exception: ExceptionRecord
            prior_outputs: Prior agent outputs
            resolution_decision: ResolutionAgent decision
            context: Full context
            
        Returns:
            Dictionary with rule-based evaluation results
        """
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
        
        # Check for inconsistencies
        inconsistencies = []
        policy_output = prior_outputs.get("policy")
        if policy_output and hasattr(policy_output, "confidence"):
            if resolution_decision.confidence < policy_output.confidence - 0.2:
                inconsistencies.append("Resolution confidence degraded significantly from policy")
        
        return {
            "should_escalate": should_escalate,
            "confidence_issues": confidence_issues,
            "safety_issues": safety_issues,
            "critical_issues": critical_issues,
            "inconsistencies": inconsistencies,
        }

    def _create_rule_based_supervisor_result(
        self,
        exception: ExceptionRecord,
        rule_based_result: dict[str, Any],
        checkpoint: str,
    ) -> dict[str, Any]:
        """
        Create rule-based supervisor result in LLM output format.
        
        This is used as fallback when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord
            rule_based_result: Rule-based evaluation results
            checkpoint: Checkpoint name ("post_policy" or "post_resolution")
            
        Returns:
            Dictionary in SupervisorLLMOutput format
        """
        if rule_based_result["should_escalate"]:
            oversight_decision = "ESCALATED"
            escalation_reason = "; ".join(
                rule_based_result["confidence_issues"]
                + rule_based_result.get("policy_breaches", [])
                + rule_based_result.get("severity_issues", [])
                + rule_based_result.get("safety_issues", [])
                + rule_based_result.get("critical_issues", [])
            )
            anomaly_detected = True
            anomaly_description = escalation_reason
        else:
            oversight_decision = "APPROVED_FLOW"
            escalation_reason = None
            anomaly_detected = False
            anomaly_description = None
        
        # Build agent chain review
        agent_chain_review = {}
        if rule_based_result.get("inconsistencies"):
            agent_chain_review["inconsistencies"] = rule_based_result["inconsistencies"]
        if rule_based_result.get("confidence_issues"):
            agent_chain_review["confidence_issues"] = rule_based_result["confidence_issues"]
        
        return {
            "oversight_decision": oversight_decision,
            "intervention_reason": escalation_reason if oversight_decision == "ESCALATED" else None,
            "anomaly_detected": anomaly_detected,
            "anomaly_description": anomaly_description,
            "agent_chain_review": agent_chain_review,
            "recommended_action": "ESCALATE" if rule_based_result["should_escalate"] else "CONTINUE",
            "escalation_reason": escalation_reason,
            "suggested_human_message": escalation_reason if rule_based_result["should_escalate"] else None,
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": f"Reviewed {checkpoint} checkpoint",
                    "outcome": f"Found {len(rule_based_result.get('confidence_issues', []))} confidence issues, "
                              f"{len(rule_based_result.get('policy_breaches', []))} policy breaches",
                },
            ],
            "evidence_references": [
                {
                    "reference_id": "guardrails",
                    "description": "Tenant policy guardrails and domain pack rules",
                    "relevance_score": 1.0,
                },
            ],
            "confidence": 0.85 if rule_based_result["should_escalate"] else 0.75,
            "natural_language_summary": f"Supervisor review at {checkpoint}: "
            f"{'Escalating due to safety concerns' if rule_based_result['should_escalate'] else 'Approved flow'}.",
        }

    def _merge_supervisor_results(
        self,
        exception: ExceptionRecord,
        current_decision: AgentDecision,
        llm_result: dict[str, Any],
        rule_based_result: dict[str, Any],
        context: dict[str, Any],
    ) -> AgentDecision:
        """
        Merge LLM result with rule-based evaluation.
        
        CRITICAL: LLM cannot override guardrails. If rule-based says ESCALATE,
        the final decision must be ESCALATE (or at least REQUIRE_APPROVAL).
        
        Args:
            exception: ExceptionRecord
            current_decision: Current agent decision being reviewed
            llm_result: LLM output dictionary (may have _metadata if fallback was used)
            rule_based_result: Rule-based evaluation results
            context: Full context
            
        Returns:
            AgentDecision with merged results and reasoning
        """
        # Check if LLM was used or fallback was triggered
        used_llm = not llm_result.get("_metadata", {}).get("llm_fallback", False)
        
        if used_llm:
            # Use LLM decision, but validate against guardrails
            llm_decision = llm_result.get("oversight_decision", "APPROVED_FLOW").upper()
            
            # Validate decision is one of the allowed values
            if llm_decision not in ["APPROVED_FLOW", "INTERVENED", "ESCALATED"]:
                logger.warning(
                    f"LLM returned invalid decision '{llm_decision}', "
                    f"using rule-based decision"
                )
                final_decision = "ESCALATED" if rule_based_result["should_escalate"] else "APPROVED_FLOW"
            else:
                # CRITICAL: If rule-based says ESCALATE, LLM cannot override to APPROVED_FLOW
                if rule_based_result["should_escalate"] and llm_decision == "APPROVED_FLOW":
                    logger.warning(
                        "LLM decision APPROVED_FLOW contradicts rule-based ESCALATE. "
                        "Enforcing rule-based escalation (guardrails cannot be overridden)."
                    )
                    final_decision = "ESCALATED"
                # If rule-based says OK but LLM says ESCALATE, use LLM (more conservative)
                elif not rule_based_result["should_escalate"] and llm_decision == "ESCALATED":
                    final_decision = "ESCALATED"
                else:
                    final_decision = llm_decision
            
            # Extract reasoning from LLM result
            reasoning = {
                "reasoning_steps": llm_result.get("reasoning_steps", []),
                "evidence_references": llm_result.get("evidence_references", []),
                "natural_language_summary": llm_result.get("natural_language_summary", ""),
            }
            
            # Use LLM's escalation reason and anomaly description
            escalation_reason = llm_result.get("escalation_reason")
            anomaly_description = llm_result.get("anomaly_description")
            intervention_reason = llm_result.get("intervention_reason")
            suggested_human_message = llm_result.get("suggested_human_message")
            
        else:
            # Fallback to rule-based
            if rule_based_result["should_escalate"]:
                final_decision = "ESCALATED"
            else:
                final_decision = "APPROVED_FLOW"
            
            escalation_reason = "; ".join(
                rule_based_result["confidence_issues"]
                + rule_based_result.get("policy_breaches", [])
                + rule_based_result.get("severity_issues", [])
                + rule_based_result.get("safety_issues", [])
                + rule_based_result.get("critical_issues", [])
            ) if rule_based_result["should_escalate"] else None
            
            anomaly_description = escalation_reason if rule_based_result["should_escalate"] else None
            intervention_reason = escalation_reason if final_decision == "ESCALATED" else None
            suggested_human_message = escalation_reason if rule_based_result["should_escalate"] else None
            
            reasoning = {
                "reasoning_steps": llm_result.get("reasoning_steps", []),
                "evidence_references": llm_result.get("evidence_references", []),
                "natural_language_summary": llm_result.get("natural_language_summary", ""),
            }
        
        # Map oversight decision to next step
        if final_decision == "ESCALATED":
            next_step = "ESCALATE"
            decision_text = "SupervisorAgent intervened: escalating due to safety concerns"
            confidence = 0.9
        elif final_decision == "INTERVENED":
            next_step = "PENDING_APPROVAL"  # Require approval
            decision_text = "SupervisorAgent intervened: requiring human approval"
            confidence = 0.85
        else:  # APPROVED_FLOW
            next_step = current_decision.next_step  # Preserve original nextStep
            decision_text = "SupervisorAgent approved: flow continues as planned"
            confidence = 0.8
        
        # Create decision with reasoning
        return self._create_decision_with_reasoning(
            exception,
            current_decision,
            final_decision,
            escalation_reason,
            anomaly_description,
            intervention_reason,
            llm_result.get("agent_chain_review", {}),
            llm_result.get("recommended_action"),
            llm_result.get("suggested_human_message") if used_llm else suggested_human_message,
            reasoning,
            next_step,
            decision_text,
            confidence,
        )

    def _create_decision_with_reasoning(
        self,
        exception: ExceptionRecord,
        current_decision: AgentDecision,
        oversight_decision: str,
        escalation_reason: Optional[str],
        anomaly_description: Optional[str],
        intervention_reason: Optional[str],
        agent_chain_review: dict[str, Any],
        recommended_action: Optional[str],
        suggested_human_message: Optional[str],
        reasoning: dict[str, Any],
        next_step: str,
        decision_text: str,
        confidence: float,
    ) -> AgentDecision:
        """
        Create agent decision with structured reasoning from LLM.
        
        Args:
            exception: ExceptionRecord
            current_decision: Current agent decision being reviewed
            oversight_decision: Oversight decision (APPROVED_FLOW, INTERVENED, ESCALATED)
            escalation_reason: Reason for escalation if escalated
            anomaly_description: Description of detected anomaly
            intervention_reason: Reason for intervention if intervened
            agent_chain_review: Review of agent chain decisions
            recommended_action: Recommended action
            reasoning: Dictionary with reasoning_steps, evidence_references, natural_language_summary
            next_step: Next step for orchestrator
            decision_text: Decision text
            confidence: Confidence score
            
        Returns:
            AgentDecision with enhanced evidence including reasoning
        """
        # Build evidence list
        evidence = []
        evidence.append(f"SupervisorAgent review: {oversight_decision}")
        evidence.append(f"Current decision confidence: {current_decision.confidence:.2f}")
        
        # Add natural language summary
        if reasoning.get("natural_language_summary"):
            evidence.append(f"Summary: {reasoning['natural_language_summary']}")
        
        # Add escalation reason if escalated
        if escalation_reason:
            evidence.append(f"Escalation reason: {escalation_reason}")
        
        # Add intervention reason if intervened
        if intervention_reason:
            evidence.append(f"Intervention reason: {intervention_reason}")
        
        # Add anomaly description if detected
        if anomaly_description:
            evidence.append(f"Anomaly detected: {anomaly_description}")
        
        # Add agent chain review
        if agent_chain_review:
            evidence.append("Agent chain review:")
            if agent_chain_review.get("inconsistencies"):
                evidence.append("  Inconsistencies:")
                for inconsistency in agent_chain_review["inconsistencies"]:
                    evidence.append(f"    - {inconsistency}")
            if agent_chain_review.get("confidence_issues"):
                evidence.append("  Confidence issues:")
                for issue in agent_chain_review["confidence_issues"]:
                    evidence.append(f"    - {issue}")
        
        # Add recommended action
        if recommended_action:
            evidence.append(f"Recommended action: {recommended_action}")
        
        # Add suggested human message
        if suggested_human_message:
            evidence.append(f"Suggested human message: {suggested_human_message}")
        
        # Add reasoning steps
        if reasoning.get("reasoning_steps"):
            evidence.append("Reasoning steps:")
            for step in reasoning["reasoning_steps"]:
                step_desc = step.get("description", "")
                step_outcome = step.get("outcome", "")
                evidence.append(f"  - {step_desc}")
                if step_outcome:
                    evidence.append(f"    Outcome: {step_outcome}")
        
        # Add evidence references
        if reasoning.get("evidence_references"):
            evidence.append("Evidence sources:")
            for ref in reasoning["evidence_references"]:
                ref_id = ref.get("reference_id", "Unknown")
                ref_desc = ref.get("description", "")
                evidence.append(f"  - {ref_id}: {ref_desc}")
        
        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )

    async def _review_post_policy_rule_based(
        self,
        exception: ExceptionRecord,
        policy_decision: AgentDecision,
        context: dict[str, Any],
    ) -> AgentDecision:
        """
        Review PolicyAgent decision using rule-based logic (Phase 2 fallback).
        
        This preserves the original Phase 2 behavior when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord being processed
            policy_decision: Decision from PolicyAgent
            context: Optional context with prior agent outputs
            
        Returns:
            AgentDecision with review result and potential override
        """
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

    async def _review_post_resolution_rule_based(
        self,
        exception: ExceptionRecord,
        resolution_decision: AgentDecision,
        context: dict[str, Any],
    ) -> AgentDecision:
        """
        Review ResolutionAgent decision using rule-based logic (Phase 2 fallback).
        
        This preserves the original Phase 2 behavior when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord being processed
            resolution_decision: Decision from ResolutionAgent
            context: Optional context with prior agent outputs
            
        Returns:
            AgentDecision with review result and potential override
        """
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

