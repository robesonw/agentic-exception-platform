"""
PolicyAgent implementation for MVP and Phase 3.
Enforces tenant policies and guardrails.
Phase 3: Enhanced with LLM reasoning and policy explanation.

Matches specification from:
- docs/04-agent-templates.md
- phase3-mvp-issues.md P3-2
"""

import json
import logging
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.llm.fallbacks import llm_or_rules
from src.llm.provider import LLMClient
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Playbook
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.safety.violation_detector import ViolationDetector

logger = logging.getLogger(__name__)


class PolicyAgentError(Exception):
    """Raised when PolicyAgent operations fail."""

    pass


class PolicyAgent:
    """
    PolicyAgent enforces guardrails and approval rules.
    
    Responsibilities:
    - Apply tenant policies and guardrails
    - Decide if exception is actionable
    - Decide if playbook is allowed
    - Decide if human approval is required
    - Produce AgentDecision with actionability classification
    """

    def __init__(
        self,
        domain_pack: DomainPack,
        tenant_policy: TenantPolicyPack,
        audit_logger: Optional[AuditLogger] = None,
        llm_client: Optional[LLMClient] = None,
        violation_detector: Optional[ViolationDetector] = None,
        playbook_matching_service: Optional[Any] = None,
        exception_events_repository: Optional[Any] = None,
    ):
        """
        Initialize PolicyAgent.
        
        Args:
            domain_pack: Domain Pack containing playbooks
            tenant_policy: Tenant Policy Pack with guardrails and rules
            audit_logger: Optional AuditLogger for logging
            llm_client: Optional LLMClient for Phase 3 LLM-enhanced reasoning
            violation_detector: Optional ViolationDetector for Phase 3 violation detection
            playbook_matching_service: Optional PlaybookMatchingService for playbook validation (P7-12)
            exception_events_repository: Optional ExceptionEventRepository for logging PolicyEvaluated events (P7-12)
        """
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.audit_logger = audit_logger
        self.llm_client = llm_client
        self.violation_detector = violation_detector
        self.playbook_matching_service = playbook_matching_service
        self.exception_events_repository = exception_events_repository
        
        # Build approved playbook IDs set for fast lookup
        # Note: Sample files use approvedBusinessProcesses, but model uses approved_tools
        # For MVP, we'll check if playbooks match exception types and are "approved"
        # In a real implementation, approvedBusinessProcesses would be in the model
        self._approved_playbook_ids: set[str] = set()
        # We'll infer from playbooks that match exception types
        self._build_approved_playbooks()

    def _build_approved_playbooks(self) -> None:
        """
        Build set of approved playbook IDs from domain pack and tenant policy.
        
        Note: Sample files have approvedBusinessProcesses (list of playbook IDs),
        but the TenantPolicyPack model doesn't capture this yet. For MVP, we
        consider all playbooks in domain pack as approved if they match exception types.
        In production, this would check tenant_policy.approvedBusinessProcesses.
        """
        # For MVP, consider all playbooks in domain pack as potentially approved
        # In production, this would come from tenant_policy.approvedBusinessProcesses
        for playbook in self.domain_pack.playbooks:
            # Use exception_type as identifier (playbooks are keyed by exception type)
            self._approved_playbook_ids.add(playbook.exception_type)
        
        # Also check custom playbooks from tenant policy
        for playbook in self.tenant_policy.custom_playbooks:
            self._approved_playbook_ids.add(playbook.exception_type)

    async def process(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Evaluate exception against Tenant Policy Pack guardrails.
        
        Phase 3: Enhanced with LLM reasoning and policy explanation.
        Falls back to rule-based logic if LLM unavailable.
        
        Args:
            exception: Triaged exception with classification and severity
            context: Optional context from TriageAgent (includes confidence, triage decision)
            
        Returns:
            AgentDecision with approval/block decision and actionability classification
            (includes structured reasoning if LLM was used)
        """
        # Phase 3: Use LLM-enhanced reasoning if available, otherwise fallback to rule-based
        if self.llm_client:
            try:
                # Build prompt with exception, triage result, tenant policy, and domain pack
                prompt = self.build_policy_prompt(exception, context)
                
                # Get rule-based evaluation for fallback
                rule_based_result = self._evaluate_rule_based(exception, context)
                
                # Call LLM with fallback to rule-based logic
                llm_result = llm_or_rules(
                    llm_client=self.llm_client,
                    agent_name="PolicyAgent",
                    tenant_id=exception.tenant_id,
                    schema_name="policy",
                    prompt=prompt,
                    rule_based_fn=lambda: self._create_rule_based_policy_result(
                        exception, context, rule_based_result
                    ),
                    audit_logger=self.audit_logger,
                )
                
                # Merge LLM result with rule-based evaluation
                decision = self._merge_policy_results(
                    exception, context, llm_result, rule_based_result
                )
                
            except Exception as e:
                logger.warning(f"LLM-enhanced policy evaluation failed: {e}, falling back to rule-based")
                # Fall through to rule-based logic
                decision = await self._process_rule_based(exception, context)
        else:
            # No LLM client, use rule-based logic
            decision = await self._process_rule_based(exception, context)
        
        # Phase 3: Check for policy violations
        if self.violation_detector:
            try:
                # Extract triage result from context if available
                triage_result = None
                if context and "triage" in context:
                    triage_result = context.get("triage")
                    if isinstance(triage_result, dict):
                        # Convert dict to AgentDecision if needed
                        try:
                            triage_result = AgentDecision.model_validate(triage_result)
                        except Exception:
                            pass  # Keep as dict or None
                
                violations = self.violation_detector.check_policy_decision(
                    tenant_id=exception.tenant_id,
                    exception_record=exception,
                    triage_result=triage_result,
                    policy_decision=decision,
                    tenant_policy=self.tenant_policy,
                    domain_pack=self.domain_pack,
                )
                
                # If critical violation detected, override decision to BLOCK
                for violation in violations:
                    if violation.severity.value == "CRITICAL":
                        logger.error(
                            f"CRITICAL policy violation detected for exception {exception.exception_id}: "
                            f"{violation.description}"
                        )
                        # Override decision to BLOCK
                        decision = AgentDecision(
                            decision="BLOCK",
                            confidence=1.0,
                            evidence=decision.evidence + [f"CRITICAL VIOLATION: {violation.description}"],
                            next_step="EscalateToSupervisor",
                        )
                        break
            except Exception as e:
                logger.warning(f"Violation detection failed: {e}")
        
        # Phase 7: Playbook matching and assignment (P7-12)
        assigned_playbook_id = None
        playbook_reasoning = None
        if decision.next_step != "Escalate" and "Blocked" not in decision.decision:
            # Only assign playbook if not blocked/escalated
            try:
                # Get playbook suggestion from triage context or call matching service
                suggested_playbook_id = None
                if context and "suggested_playbook_id" in context:
                    suggested_playbook_id = context.get("suggested_playbook_id")
                    playbook_reasoning = context.get("playbook_reasoning", "Playbook suggested by TriageAgent")
                
                # If no suggestion from triage, call matching service
                if not suggested_playbook_id and self.playbook_matching_service:
                    try:
                        matching_result = await self.playbook_matching_service.match_playbook(
                            tenant_id=exception.tenant_id,
                            exception=exception,
                            tenant_policy=self.tenant_policy,
                        )
                        if matching_result.playbook:
                            suggested_playbook_id = matching_result.playbook.playbook_id
                            playbook_reasoning = matching_result.reasoning
                    except Exception as e:
                        logger.warning(f"Playbook matching failed during policy evaluation: {e}")
                
                # Validate playbook aligns with policy guardrails
                if suggested_playbook_id:
                    # Check if playbook is approved (aligns with policy)
                    # For MVP, we check if the playbook matches an approved exception type
                    # In production, this would check actual playbook IDs against approvedBusinessProcesses
                    is_approved = False
                    if exception.exception_type in self._approved_playbook_ids:
                        # Check if there's an approved playbook for this exception type
                        applicable_playbooks = self._find_applicable_playbooks(exception)
                        if applicable_playbooks:
                            # For MVP, if we have applicable playbooks and the exception type is approved,
                            # we consider the suggested playbook approved
                            is_approved = True
                            assigned_playbook_id = suggested_playbook_id
                            logger.info(
                                f"PolicyAgent: Approved playbook {assigned_playbook_id} "
                                f"for exception {exception.exception_id}: {playbook_reasoning}"
                            )
                    
                    if not is_approved:
                        logger.debug(
                            f"PolicyAgent: Playbook {suggested_playbook_id} not approved "
                            f"for exception {exception.exception_id}"
                        )
                        playbook_reasoning = f"Playbook {suggested_playbook_id} not in approved list"
                
                # Assign playbook to exception if approved
                if assigned_playbook_id:
                    exception.current_playbook_id = assigned_playbook_id
                    exception.current_step = 1
                    logger.info(
                        f"PolicyAgent: Assigned playbook {assigned_playbook_id} "
                        f"to exception {exception.exception_id}, current_step=1"
                    )
            except Exception as e:
                logger.warning(f"Playbook assignment failed during policy evaluation: {e}")
        
        # Phase 7: Emit PolicyEvaluated event (P7-12)
        if self.exception_events_repository:
            try:
                from src.domain.events.exception_events import (
                    ActorType,
                    EventType,
                    PolicyEvaluatedPayload,
                    validate_and_build_event,
                )
                from datetime import datetime, timezone
                
                # Build event payload
                event_payload = PolicyEvaluatedPayload(
                    decision=decision.decision,
                    violated_rules=[e for e in decision.evidence if "violated" in e.lower() or "blocked" in e.lower()],
                    approval_required="Human approval required" in " ".join(decision.evidence),
                    guardrail_checks={"applied_guardrails": [e for e in decision.evidence if "guardrail" in e.lower()]},
                    playbook_id=assigned_playbook_id,
                    reasoning=playbook_reasoning,
                )
                
                # Build event envelope
                event_envelope = validate_and_build_event(
                    event_type=EventType.POLICY_EVALUATED,
                    payload_dict=event_payload.model_dump(),
                    tenant_id=exception.tenant_id,
                    exception_id=exception.exception_id,
                    actor_type=ActorType.AGENT,
                    actor_id="PolicyAgent",
                )
                
                # Log event via repository
                from src.repository.dto import ExceptionEventDTO
                from src.infrastructure.db.models import ActorType as DBActorType
                event_dto = ExceptionEventDTO(
                    event_id=event_envelope.event_id,
                    tenant_id=event_envelope.tenant_id,
                    exception_id=event_envelope.exception_id,
                    event_type=event_envelope.event_type,
                    actor_type=DBActorType.AGENT,  # Use DB enum
                    actor_id=event_envelope.actor_id,
                    payload=event_envelope.payload,
                )
                
                await self.exception_events_repository.append_event_if_new(event_dto)
                logger.debug(
                    f"PolicyAgent: Emitted PolicyEvaluated event for exception {exception.exception_id}"
                )
            except Exception as e:
                logger.warning(f"Failed to emit PolicyEvaluated event: {e}")
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context or {},
            }
            self.audit_logger.log_agent_event("PolicyAgent", input_data, decision, exception.tenant_id)
        
        return decision

    def _apply_severity_overrides(self, exception: ExceptionRecord) -> Severity:
        """
        Apply tenant severity overrides.
        
        Args:
            exception: ExceptionRecord to evaluate
            
        Returns:
            Effective severity after overrides
        """
        # Check custom severity overrides
        for override in self.tenant_policy.custom_severity_overrides:
            if override.exception_type == exception.exception_type:
                return Severity(override.severity.upper())
        
        # Return original severity if no override
        return exception.severity or Severity.MEDIUM

    def _find_applicable_playbooks(self, exception: ExceptionRecord) -> list[Playbook]:
        """
        Find playbooks applicable to this exception type.
        
        Args:
            exception: ExceptionRecord to find playbooks for
            
        Returns:
            List of applicable playbooks
        """
        applicable = []
        
        if not exception.exception_type:
            return applicable
        
        # Find playbooks from domain pack
        for playbook in self.domain_pack.playbooks:
            if playbook.exception_type == exception.exception_type:
                applicable.append(playbook)
        
        # Find custom playbooks from tenant policy
        for playbook in self.tenant_policy.custom_playbooks:
            if playbook.exception_type == exception.exception_type:
                applicable.append(playbook)
        
        return applicable

    def _check_playbook_approval(
        self, exception: ExceptionRecord, playbooks: list[Playbook]
    ) -> Optional[Playbook]:
        """
        Check if any playbook is approved for this exception.
        
        Rules:
        - Never approve a playbook not in tenant.approvedBusinessProcesses
        - For MVP, we check if playbook exception_type matches approved set
        
        Args:
            exception: ExceptionRecord to check
            playbooks: List of applicable playbooks
            
        Returns:
            Approved Playbook or None
        """
        if not playbooks:
            return None
        
        # For MVP, check if exception type is in approved set
        # In production, this would check actual playbook IDs
        if exception.exception_type in self._approved_playbook_ids:
            # Return first matching playbook
            return playbooks[0]
        
        # Check if any playbook matches approved exception types
        for playbook in playbooks:
            if playbook.exception_type in self._approved_playbook_ids:
                return playbook
        
        return None

    def _determine_actionability(
        self,
        exception: ExceptionRecord,
        severity: Severity,
        approved_playbook: Optional[Playbook],
    ) -> str:
        """
        Determine actionability classification.
        
        Returns:
            ACTIONABLE_APPROVED_PROCESS: Has approved playbook
            ACTIONABLE_NON_APPROVED_PROCESS: Has playbook but not approved
            NON_ACTIONABLE_INFO_ONLY: No playbook or blocked by guardrails
        """
        # Check if blocked by guardrails (noAutoActionIfSeverityIn)
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        
        # Check if severity is in no-auto-action list
        # Note: Sample files have noAutoActionIfSeverityIn, but model doesn't capture it
        # For MVP, we'll check if CRITICAL severity requires approval
        if severity == Severity.CRITICAL:
            # Check if human approval is explicitly required
            requires_approval = any(
                rule.severity.upper() == "CRITICAL" and rule.require_approval
                for rule in self.tenant_policy.human_approval_rules
            )
            if requires_approval:
                # Still actionable, but requires approval
                if approved_playbook:
                    return "ACTIONABLE_APPROVED_PROCESS"
                else:
                    return "NON_ACTIONABLE_INFO_ONLY"
        
        # Check if there's an approved playbook
        if approved_playbook:
            return "ACTIONABLE_APPROVED_PROCESS"
        
        # Check if there's any playbook (but not approved)
        playbooks = self._find_applicable_playbooks(exception)
        if playbooks:
            return "ACTIONABLE_NON_APPROVED_PROCESS"
        
        # No playbook available
        return "NON_ACTIONABLE_INFO_ONLY"

    def _check_human_approval_required(
        self,
        exception: ExceptionRecord,
        severity: Severity,
        context: Optional[dict[str, Any]],
    ) -> bool:
        """
        Check if human approval is required.
        
        Rules:
        - Check humanApprovalRules from tenant policy
        - Check requireHumanApprovalFor from guardrails
        - Check confidence threshold
        
        Args:
            exception: ExceptionRecord to check
            severity: Effective severity
            context: Optional context with confidence
            
        Returns:
            True if human approval is required
        """
        # Check human approval rules
        for rule in self.tenant_policy.human_approval_rules:
            if rule.severity.upper() == severity.value.upper():
                if rule.require_approval:
                    return True
        
        # Check guardrails threshold
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        if context and "confidence" in context:
            confidence = context.get("confidence", 1.0)
            if confidence < guardrails.human_approval_threshold:
                return True
        
        # Check if CRITICAL severity (default rule: never auto-execute CRITICAL)
        if severity == Severity.CRITICAL:
            # Unless explicitly allowed by tenant policy
            # For MVP, default to requiring approval for CRITICAL
            return True
        
        return False

    def _check_confidence_threshold(self, context: Optional[dict[str, Any]]) -> bool:
        """
        Check if confidence is below escalation threshold.
        
        Args:
            context: Optional context with confidence
            
        Returns:
            True if should escalate due to low confidence
        """
        if not context or "confidence" not in context:
            return False
        
        confidence = context.get("confidence", 1.0)
        
        # Check guardrails escalateIfConfidenceBelow
        # Note: Sample files have this, but model doesn't capture it directly
        # For MVP, use human_approval_threshold as proxy
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        
        # Use a lower threshold for escalation (e.g., 0.1 below approval threshold)
        escalation_threshold = guardrails.human_approval_threshold - 0.1
        
        return confidence < escalation_threshold

    def _create_decision(
        self,
        exception: ExceptionRecord,
        severity: Severity,
        actionability: str,
        approved_playbook: Optional[Playbook],
        human_approval_required: bool,
        should_escalate: bool,
    ) -> AgentDecision:
        """
        Create agent decision from policy evaluation results.
        
        Args:
            exception: ExceptionRecord
            severity: Effective severity
            actionability: Actionability classification
            approved_playbook: Approved playbook if any
            human_approval_required: Whether human approval is required
            should_escalate: Whether to escalate
            
        Returns:
            AgentDecision
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Exception type: {exception.exception_type}")
        evidence.append(f"Severity: {severity.value}")
        evidence.append(f"Actionability: {actionability}")
        
        if approved_playbook:
            evidence.append(f"Approved playbook found for: {approved_playbook.exception_type}")
        else:
            evidence.append("No approved playbook found")
        
        if human_approval_required:
            evidence.append("Human approval required")
        
        if should_escalate:
            evidence.append("Escalation recommended (low confidence)")
        
        # Add severity override info if applied
        if exception.severity != severity:
            evidence.append(f"Severity overridden: {exception.severity.value} -> {severity.value}")
        
        # Determine decision text
        if should_escalate:
            decision_text = "Escalate"
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            decision_text = "Blocked - Non-actionable"
        elif human_approval_required:
            decision_text = "Approved - Human approval required"
        elif actionability == "ACTIONABLE_APPROVED_PROCESS":
            decision_text = "Approved"
        else:
            decision_text = "Blocked - Playbook not approved"
        
        # Calculate confidence
        if actionability == "ACTIONABLE_APPROVED_PROCESS" and not human_approval_required:
            confidence = 0.9
        elif actionability == "ACTIONABLE_APPROVED_PROCESS":
            confidence = 0.8
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            confidence = 0.6
        else:
            confidence = 0.5
        
        # Determine next step
        if should_escalate:
            next_step = "Escalate"
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            next_step = "Escalate"
        elif human_approval_required:
            next_step = "ProceedToResolution"  # Will wait for approval
        else:
            next_step = "ProceedToResolution"
        
        # Add metadata to evidence for downstream agents
        evidence.append(f"selectedPlaybookId: {approved_playbook.exception_type if approved_playbook else 'None'}")
        evidence.append(f"humanApprovalRequired: {human_approval_required}")
        
        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )

    def build_policy_prompt(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
    ) -> str:
        """
        Build prompt for LLM policy reasoning.
        
        Combines exception details, triage result, tenant policy, and domain pack into a structured prompt.
        
        Args:
            exception: ExceptionRecord to evaluate
            context: Optional context from TriageAgent (includes triage decision)
            
        Returns:
            Formatted prompt string for LLM
        """
        prompt_parts = []
        
        # Base prompt from agent template
        prompt_parts.append(
            "You are the PolicyAgent. Evaluate triage output against Tenant Policy Pack "
            "guardrails, allow-lists, and humanApprovalRules. Approve or block suggestedActions. "
            "Explain which guardrails triggered and why."
        )
        
        # Exception details
        prompt_parts.append("\n## Exception Details:")
        prompt_parts.append(f"- Exception ID: {exception.exception_id}")
        prompt_parts.append(f"- Tenant ID: {exception.tenant_id}")
        prompt_parts.append(f"- Exception Type: {exception.exception_type}")
        prompt_parts.append(f"- Severity: {exception.severity.value if exception.severity else 'UNKNOWN'}")
        prompt_parts.append(f"- Source System: {exception.source_system}")
        
        # Triage result from context
        if context:
            triage_decision = context.get("triage_decision")
            triage_confidence = context.get("confidence", 0.0)
            if triage_decision:
                prompt_parts.append(f"\n## Triage Result:")
                prompt_parts.append(f"- Decision: {triage_decision}")
                prompt_parts.append(f"- Confidence: {triage_confidence:.2f}")
                if "evidence" in context:
                    prompt_parts.append(f"- Evidence: {', '.join(str(e) for e in context['evidence'][:3])}")
        
        # Tenant policy context
        prompt_parts.append("\n## Tenant Policy Guardrails:")
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        if guardrails:
            prompt_parts.append(f"- Human Approval Threshold: {guardrails.human_approval_threshold}")
            prompt_parts.append(f"- Max Auto-Action Severity: {guardrails.max_auto_action_severity if hasattr(guardrails, 'max_auto_action_severity') else 'Not specified'}")
        
        # Human approval rules
        if self.tenant_policy.human_approval_rules:
            prompt_parts.append("\n## Human Approval Rules:")
            for rule in self.tenant_policy.human_approval_rules[:5]:  # Limit to first 5
                prompt_parts.append(f"- Severity: {rule.severity}, Require Approval: {rule.require_approval}")
        
        # Severity overrides
        if self.tenant_policy.custom_severity_overrides:
            prompt_parts.append("\n## Custom Severity Overrides:")
            for override in self.tenant_policy.custom_severity_overrides[:5]:
                prompt_parts.append(f"- {override.exception_type} -> {override.severity}")
        
        # Applicable playbooks
        applicable_playbooks = self._find_applicable_playbooks(exception)
        if applicable_playbooks:
            prompt_parts.append("\n## Applicable Playbooks:")
            for playbook in applicable_playbooks[:3]:  # Top 3
                prompt_parts.append(f"- {playbook.exception_type}: {playbook.description if hasattr(playbook, 'description') else 'N/A'}")
        else:
            prompt_parts.append("\n## Applicable Playbooks: None found")
        
        # Approved playbooks
        prompt_parts.append(f"\n## Approved Playbook IDs: {', '.join(list(self._approved_playbook_ids)[:5])}")
        
        # Instructions
        prompt_parts.append(
            "\n## Instructions:"
            "\nAnalyze the exception against the tenant policy and provide:"
            "\n1. Policy decision: ALLOW, BLOCK, or REQUIRE_APPROVAL"
            "\n2. List of applied guardrails (which rules were checked)"
            "\n3. List of violated rules (if any)"
            "\n4. Whether human approval is required and why"
            "\n5. Human-readable violation report (if blocked)"
            "\n6. Explanation of how tenant-specific policies influenced the decision"
            "\n7. Structured reasoning steps explaining your decision"
            "\n8. Evidence references (which policies, rules, and guardrails were used)"
        )
        
        return "\n".join(prompt_parts)

    def _evaluate_rule_based(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Evaluate policy using rule-based logic (Phase 1 baseline).
        
        Returns a dictionary with all rule-based evaluation results.
        
        Args:
            exception: ExceptionRecord to evaluate
            context: Optional context from TriageAgent
            
        Returns:
            Dictionary with rule-based evaluation results
        """
        # Apply severity overrides
        effective_severity = self._apply_severity_overrides(exception)
        
        # Find applicable playbooks
        applicable_playbooks = self._find_applicable_playbooks(exception)
        
        # Check if any playbook is approved
        approved_playbook = self._check_playbook_approval(exception, applicable_playbooks)
        
        # Check actionability
        actionability = self._determine_actionability(
            exception, effective_severity, approved_playbook
        )
        
        # Check human approval requirements
        human_approval_required = self._check_human_approval_required(
            exception, effective_severity, context
        )
        
        # Check confidence threshold
        should_escalate = self._check_confidence_threshold(context)
        
        # Collect applied guardrails
        applied_guardrails = []
        guardrails = self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
        if guardrails:
            applied_guardrails.append(f"Human approval threshold: {guardrails.human_approval_threshold}")
            
            # Phase 3: Record guardrail as evidence (P3-29)
            try:
                from src.explainability.evidence_integration import record_policy_evidence
                
                record_policy_evidence(
                    exception_id=exception.exception_id,
                    tenant_id=exception.tenant_id,
                    rule_id="guardrail_human_approval_threshold",
                    rule_description=f"Human approval threshold: {guardrails.human_approval_threshold}",
                    applied=True,
                    agent_name="PolicyAgent",
                    stage_name="policy",
                )
            except Exception as e:
                logger.warning(f"Failed to record guardrail evidence: {e}")
        
        # Collect violated rules
        violated_rules = []
        if actionability == "NON_ACTIONABLE_INFO_ONLY":
            violated_rules.append("No approved playbook available")
            # Phase 3: Record violated rule as evidence (P3-29)
            try:
                from src.explainability.evidence_integration import record_policy_evidence
                
                record_policy_evidence(
                    exception_id=exception.exception_id,
                    tenant_id=exception.tenant_id,
                    rule_id="rule_no_approved_playbook",
                    rule_description="No approved playbook available",
                    applied=False,
                    agent_name="PolicyAgent",
                    stage_name="policy",
                )
            except Exception as e:
                logger.warning(f"Failed to record policy evidence: {e}")
        
        if not approved_playbook and applicable_playbooks:
            violated_rules.append("Playbook not in approved list")
            # Phase 3: Record violated rule as evidence (P3-29)
            try:
                from src.explainability.evidence_integration import record_policy_evidence
                
                record_policy_evidence(
                    exception_id=exception.exception_id,
                    tenant_id=exception.tenant_id,
                    rule_id="rule_playbook_not_approved",
                    rule_description="Playbook not in approved list",
                    applied=False,
                    agent_name="PolicyAgent",
                    stage_name="policy",
                )
            except Exception as e:
                logger.warning(f"Failed to record policy evidence: {e}")
        
        # Determine policy decision
        if should_escalate:
            policy_decision = "BLOCK"
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            policy_decision = "BLOCK"
        elif human_approval_required:
            policy_decision = "REQUIRE_APPROVAL"
        elif actionability == "ACTIONABLE_APPROVED_PROCESS":
            policy_decision = "ALLOW"
        else:
            policy_decision = "BLOCK"
        
        return {
            "effective_severity": effective_severity,
            "applicable_playbooks": applicable_playbooks,
            "approved_playbook": approved_playbook,
            "actionability": actionability,
            "human_approval_required": human_approval_required,
            "should_escalate": should_escalate,
            "applied_guardrails": applied_guardrails,
            "violated_rules": violated_rules,
            "policy_decision": policy_decision,
        }

    def _create_rule_based_policy_result(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
        rule_based_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Create rule-based policy result in LLM output format.
        
        This is used as fallback when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord
            context: Optional context
            rule_based_result: Rule-based evaluation results
            
        Returns:
            Dictionary in PolicyLLMOutput format
        """
        approval_reason = None
        if rule_based_result["human_approval_required"]:
            if rule_based_result["effective_severity"] == Severity.CRITICAL:
                approval_reason = "CRITICAL severity requires human approval"
            else:
                approval_reason = "Guardrail threshold requires human approval"
        
        violation_report = None
        if rule_based_result["policy_decision"] == "BLOCK":
            if rule_based_result["violated_rules"]:
                violation_report = f"Blocked due to: {', '.join(rule_based_result['violated_rules'])}"
            else:
                violation_report = "Blocked: No approved playbook available"
        
        tenant_policy_influence = f"Tenant policy applied severity overrides and guardrails. "
        if rule_based_result["approved_playbook"]:
            tenant_policy_influence += "Playbook approved for this exception type."
        else:
            tenant_policy_influence += "No approved playbook found."
        
        return {
            "policy_decision": rule_based_result["policy_decision"],
            "applied_guardrails": rule_based_result["applied_guardrails"],
            "violated_rules": rule_based_result["violated_rules"],
            "approval_required": rule_based_result["human_approval_required"],
            "approval_reason": approval_reason,
            "policy_violation_report": violation_report,
            "tenant_policy_influence": tenant_policy_influence,
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Evaluated exception against tenant policy guardrails",
                    "outcome": f"Applied guardrails: {len(rule_based_result['applied_guardrails'])}",
                },
                {
                    "step_number": 2,
                    "description": "Checked playbook approval status",
                    "outcome": f"Approved playbook: {rule_based_result['approved_playbook'] is not None}",
                },
                {
                    "step_number": 3,
                    "description": "Determined policy decision",
                    "outcome": f"Decision: {rule_based_result['policy_decision']}",
                },
            ],
            "evidence_references": [
                {
                    "reference_id": "tenant_policy",
                    "description": "Tenant Policy Pack guardrails and rules",
                    "relevance_score": 1.0,
                },
            ],
            "confidence": 0.85 if rule_based_result["approved_playbook"] else 0.75,
            "natural_language_summary": f"Policy evaluation: {rule_based_result['policy_decision']}. "
            f"{'Human approval required' if rule_based_result['human_approval_required'] else 'No approval required'}.",
        }

    def _merge_policy_results(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
        llm_result: dict[str, Any],
        rule_based_result: dict[str, Any],
    ) -> AgentDecision:
        """
        Merge LLM result with rule-based evaluation.
        
        Ensures LLM reasoning augments but does not contradict guardrails.
        
        Args:
            exception: ExceptionRecord
            context: Optional context
            llm_result: LLM output dictionary (may have _metadata if fallback was used)
            rule_based_result: Rule-based evaluation results
            
        Returns:
            AgentDecision with merged results and reasoning
        """
        # Check if LLM was used or fallback was triggered
        used_llm = not llm_result.get("_metadata", {}).get("llm_fallback", False)
        
        if used_llm:
            # Use LLM decision, but validate against guardrails
            llm_decision = llm_result.get("policy_decision", rule_based_result["policy_decision"]).upper()
            
            # Validate decision is one of the allowed values
            if llm_decision not in ["ALLOW", "BLOCK", "REQUIRE_APPROVAL"]:
                logger.warning(
                    f"LLM returned invalid decision '{llm_decision}', "
                    f"using rule-based decision '{rule_based_result['policy_decision']}'"
                )
                final_decision = rule_based_result["policy_decision"]
            else:
                # Check if LLM decision contradicts critical guardrails
                # Never allow if rule-based says BLOCK due to no approved playbook
                if rule_based_result["policy_decision"] == "BLOCK" and llm_decision == "ALLOW":
                    if not rule_based_result["approved_playbook"]:
                        logger.warning(
                            "LLM decision ALLOW contradicts rule-based BLOCK (no approved playbook). "
                            "Using rule-based decision."
                        )
                        final_decision = rule_based_result["policy_decision"]
                    else:
                        # LLM might have additional reasoning, but we'll be cautious
                        final_decision = "REQUIRE_APPROVAL"  # Require approval as compromise
                else:
                    final_decision = llm_decision
            
            # Merge approval requirement (use more restrictive)
            llm_approval_required = llm_result.get("approval_required", False)
            final_approval_required = (
                rule_based_result["human_approval_required"] or llm_approval_required
            )
            
            # Extract reasoning from LLM result
            reasoning = {
                "reasoning_steps": llm_result.get("reasoning_steps", []),
                "evidence_references": llm_result.get("evidence_references", []),
                "natural_language_summary": llm_result.get("natural_language_summary", ""),
            }
            
            # Use LLM's applied_guardrails and violated_rules, but merge with rule-based
            applied_guardrails = list(set(
                llm_result.get("applied_guardrails", []) + rule_based_result["applied_guardrails"]
            ))
            violated_rules = list(set(
                llm_result.get("violated_rules", []) + rule_based_result["violated_rules"]
            ))
            
        else:
            # Fallback to rule-based
            final_decision = rule_based_result["policy_decision"]
            final_approval_required = rule_based_result["human_approval_required"]
            applied_guardrails = rule_based_result["applied_guardrails"]
            violated_rules = rule_based_result["violated_rules"]
            
            reasoning = {
                "reasoning_steps": llm_result.get("reasoning_steps", []),
                "evidence_references": llm_result.get("evidence_references", []),
                "natural_language_summary": llm_result.get("natural_language_summary", ""),
            }
        
        # Map policy decision to actionability and create decision
        if final_decision == "ALLOW":
            actionability = "ACTIONABLE_APPROVED_PROCESS"
        elif final_decision == "REQUIRE_APPROVAL":
            actionability = "ACTIONABLE_APPROVED_PROCESS" if rule_based_result["approved_playbook"] else "ACTIONABLE_NON_APPROVED_PROCESS"
        else:  # BLOCK
            actionability = "NON_ACTIONABLE_INFO_ONLY"
        
        # Create decision with reasoning
        return self._create_decision_with_reasoning(
            exception,
            rule_based_result["effective_severity"],
            actionability,
            rule_based_result["approved_playbook"],
            final_approval_required,
            rule_based_result["should_escalate"],
            applied_guardrails,
            violated_rules,
            llm_result.get("policy_violation_report"),
            llm_result.get("tenant_policy_influence"),
            reasoning,
        )

    def _create_decision_with_reasoning(
        self,
        exception: ExceptionRecord,
        severity: Severity,
        actionability: str,
        approved_playbook: Optional[Playbook],
        human_approval_required: bool,
        should_escalate: bool,
        applied_guardrails: list[str],
        violated_rules: list[str],
        violation_report: Optional[str],
        tenant_policy_influence: Optional[str],
        reasoning: dict[str, Any],
    ) -> AgentDecision:
        """
        Create agent decision with structured reasoning from LLM.
        
        Args:
            exception: ExceptionRecord
            severity: Effective severity
            actionability: Actionability classification
            approved_playbook: Approved playbook if any
            human_approval_required: Whether human approval is required
            should_escalate: Whether to escalate
            applied_guardrails: List of applied guardrails
            violated_rules: List of violated rules
            violation_report: Optional violation report
            tenant_policy_influence: Optional tenant policy influence explanation
            reasoning: Dictionary with reasoning_steps, evidence_references, natural_language_summary
            
        Returns:
            AgentDecision with enhanced evidence including reasoning
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Exception type: {exception.exception_type}")
        evidence.append(f"Severity: {severity.value}")
        evidence.append(f"Actionability: {actionability}")
        
        # Add natural language summary
        if reasoning.get("natural_language_summary"):
            evidence.append(f"Summary: {reasoning['natural_language_summary']}")
        
        # Add applied guardrails
        if applied_guardrails:
            evidence.append("Applied guardrails:")
            for guardrail in applied_guardrails:
                evidence.append(f"  - {guardrail}")
        
        # Add violated rules
        if violated_rules:
            evidence.append("Violated rules:")
            for rule in violated_rules:
                evidence.append(f"  - {rule}")
        
        # Add violation report if blocked
        if violation_report:
            evidence.append(f"Violation report: {violation_report}")
        
        # Add tenant policy influence
        if tenant_policy_influence:
            evidence.append(f"Tenant policy influence: {tenant_policy_influence}")
        
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
        
        if approved_playbook:
            evidence.append(f"Approved playbook found for: {approved_playbook.exception_type}")
        else:
            evidence.append("No approved playbook found")
        
        if human_approval_required:
            evidence.append("Human approval required")
        
        if should_escalate:
            evidence.append("Escalation recommended (low confidence)")
        
        # Determine decision text
        if should_escalate:
            decision_text = "Escalate"
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            decision_text = "Blocked - Non-actionable"
        elif human_approval_required:
            decision_text = "Approved - Human approval required"
        elif actionability == "ACTIONABLE_APPROVED_PROCESS":
            decision_text = "Approved"
        else:
            decision_text = "Blocked - Playbook not approved"
        
        # Calculate confidence
        if actionability == "ACTIONABLE_APPROVED_PROCESS" and not human_approval_required:
            confidence = 0.9
        elif actionability == "ACTIONABLE_APPROVED_PROCESS":
            confidence = 0.8
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            confidence = 0.6
        else:
            confidence = 0.5
        
        # Determine next step
        if should_escalate:
            next_step = "Escalate"
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            next_step = "Escalate"
        elif human_approval_required:
            next_step = "ProceedToResolution"  # Will wait for approval
        else:
            next_step = "ProceedToResolution"
        
        # Add metadata to evidence for downstream agents
        evidence.append(f"selectedPlaybookId: {approved_playbook.exception_type if approved_playbook else 'None'}")
        evidence.append(f"humanApprovalRequired: {human_approval_required}")
        
        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep=next_step,
        )

    async def _process_rule_based(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
    ) -> AgentDecision:
        """
        Process exception using rule-based logic (Phase 1 fallback).
        
        This preserves the original Phase 1 behavior when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord to process
            context: Optional context from previous agents
            
        Returns:
            AgentDecision with rule-based policy results
        """
        # Apply severity overrides
        effective_severity = self._apply_severity_overrides(exception)
        
        # Find applicable playbooks
        applicable_playbooks = self._find_applicable_playbooks(exception)
        
        # Check if any playbook is approved
        approved_playbook = self._check_playbook_approval(exception, applicable_playbooks)
        
        # Check actionability
        actionability = self._determine_actionability(
            exception, effective_severity, approved_playbook
        )
        
        # Check human approval requirements
        human_approval_required = self._check_human_approval_required(
            exception, effective_severity, context
        )
        
        # Check confidence threshold
        should_escalate = self._check_confidence_threshold(context)
        
        # Create agent decision
        decision = self._create_decision(
            exception,
            effective_severity,
            actionability,
            approved_playbook,
            human_approval_required,
            should_escalate,
        )
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context or {},
            }
            self.audit_logger.log_agent_event("PolicyAgent", input_data, decision, exception.tenant_id)
        
        return decision
