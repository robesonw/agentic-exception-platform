"""
PolicyAgent implementation for MVP.
Enforces tenant policies and guardrails.
Matches specification from docs/04-agent-templates.md
"""

from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Playbook
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack


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
    ):
        """
        Initialize PolicyAgent.
        
        Args:
            domain_pack: Domain Pack containing playbooks
            tenant_policy: Tenant Policy Pack with guardrails and rules
            audit_logger: Optional AuditLogger for logging
        """
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.audit_logger = audit_logger
        
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
        
        Args:
            exception: Triaged exception with classification and severity
            context: Optional context from TriageAgent (includes confidence)
            
        Returns:
            AgentDecision with approval/block decision and actionability classification
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
