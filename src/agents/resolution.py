"""
ResolutionAgent implementation for MVP, Phase 2, and Phase 3.
Plans resolution actions from playbooks.
Phase 2: Supports partial automation with ToolExecutionEngine.
Phase 3: Enhanced with LLM-based action explanation.

Matches specification from:
- docs/04-agent-templates.md
- phase2-mvp-issues.md Issue 36
- phase3-mvp-issues.md P3-3
"""

import json
import logging
import re
from enum import Enum
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.llm.fallbacks import llm_or_rules
from src.llm.provider import LLMClient, LLMProvider
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.playbooks.generator import PlaybookGenerator, PlaybookGeneratorError
from src.playbooks.manager import PlaybookManager, PlaybookManagerError
from src.tools.execution_engine import ToolExecutionEngine, ToolExecutionError
from src.tools.invoker import ToolInvoker, ToolInvocationError
from src.tools.registry import ToolRegistry
from src.workflow.approval import ApprovalQueue, ApprovalQueueRegistry

logger = logging.getLogger(__name__)


class StepExecutionStatus(str, Enum):
    """Execution status for a playbook step."""

    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"
    NEEDS_APPROVAL = "NEEDS_APPROVAL"


class ResolutionAgentError(Exception):
    """Raised when ResolutionAgent operations fail."""

    pass


class ResolutionAgent:
    """
    ResolutionAgent plans resolution actions from playbooks.
    
    MVP Responsibilities:
    - If PolicyAgent marked actionable + approved:
        * Load the selected playbook
        * Resolve each step into a structured action plan
        * DO NOT execute tools yet in MVP
        * Validate each referenced tool exists in domainPack.tools
        * Validate tool is allow-listed for this tenant
    
    - If non-approved but actionable:
        * Generate a suggestedDraftPlaybook structure
    
    - Output AgentDecision with resolvedPlan and suggestedDraftPlaybook
    """

    def __init__(
        self,
        domain_pack: DomainPack,
        tool_registry: ToolRegistry,
        audit_logger: Optional[AuditLogger] = None,
        tool_invoker: Optional[ToolInvoker] = None,
        tenant_policy: Optional[TenantPolicyPack] = None,
        playbook_manager: Optional[PlaybookManager] = None,
        execution_engine: Optional[ToolExecutionEngine] = None,
        approval_queue_registry: Optional[ApprovalQueueRegistry] = None,
        llm_client: Optional[LLMClient] = None,
        playbook_repository: Optional[Any] = None,
        exception_events_repository: Optional[Any] = None,
    ):
        """
        Initialize ResolutionAgent.
        
        Args:
            domain_pack: Domain Pack containing playbooks and tools
            tool_registry: Tool Registry for validation
            audit_logger: Optional AuditLogger for logging
            tool_invoker: Optional ToolInvoker for executing tools (legacy, Phase 1)
            tenant_policy: Optional TenantPolicyPack for human approval checks
            playbook_manager: Optional PlaybookManager for playbook selection (Phase 2)
            execution_engine: Optional ToolExecutionEngine for automated execution (Phase 2)
            approval_queue_registry: Optional ApprovalQueueRegistry for approval workflow
            llm_client: Optional LLMClient for Phase 3 LLM-enhanced explanation
            playbook_repository: Optional PlaybookRepository for loading playbooks from database (P7-13)
            exception_events_repository: Optional ExceptionEventRepository for logging ResolutionSuggested events (P7-13)
        """
        self.domain_pack = domain_pack
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger
        self.tool_invoker = tool_invoker  # Legacy support
        self.tenant_policy = tenant_policy
        self.playbook_manager = playbook_manager or PlaybookManager()
        self.execution_engine = execution_engine or (
            ToolExecutionEngine(audit_logger=audit_logger) if audit_logger else None
        )
        self.approval_queue_registry = approval_queue_registry
        self.playbook_generator: Optional[PlaybookGenerator] = None  # Phase 2: LLM-based generation
        self.llm_client = llm_client  # Phase 3: LLM-enhanced explanation
        self.playbook_repository = playbook_repository  # Phase 7: Database playbook loading (P7-13)
        self.exception_events_repository = exception_events_repository  # Phase 7: Event logging (P7-13)
        
        # Load playbooks into manager if domain pack and tenant policy are available
        if tenant_policy:
            self.playbook_manager.load_playbooks(domain_pack, tenant_policy.tenant_id)

    def set_playbook_generator(self, generator: PlaybookGenerator) -> None:
        """
        Set playbook generator for LLM-based generation.
        
        Phase 2: Allows injecting PlaybookGenerator for ACTIONABLE_NON_APPROVED_PROCESS cases.
        
        Args:
            generator: PlaybookGenerator instance
        """
        self.playbook_generator = generator

    async def process(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Plan resolution actions from playbooks.
        
        Args:
            exception: ExceptionRecord with classification and severity
            context: Context from PolicyAgent (includes actionability, selectedPlaybookId)
            
        Returns:
            AgentDecision with resolvedPlan and suggestedDraftPlaybook
            
        Raises:
            ResolutionAgentError: If planning fails
        """
        context = context or {}
        
        # Phase 7: Check if exception has current_playbook_id (P7-13)
        next_action = None
        if exception.current_playbook_id and self.playbook_repository:
            try:
                # Load playbook from database
                playbook = await self.playbook_repository.get_playbook(
                    playbook_id=exception.current_playbook_id,
                    tenant_id=exception.tenant_id,
                )
                
                if playbook and playbook.steps:
                    # Identify next step based on current_step
                    # current_step is 1-indexed, so if current_step=1, next step is step_order=2
                    current_step_order = exception.current_step or 1
                    next_step_order = current_step_order + 1
                    
                    # Find the next step
                    next_step = None
                    for step in sorted(playbook.steps, key=lambda s: s.step_order):
                        if step.step_order == next_step_order:
                            next_step = step
                            break
                    
                    if next_step:
                        # Produce next_action suggestion
                        # Extract brief params summary (limit to key fields)
                        params_summary = {}
                        if next_step.params:
                            # Include only top-level keys, limit values to short strings
                            for key, value in list(next_step.params.items())[:5]:  # Limit to 5 params
                                if isinstance(value, (str, int, float, bool)):
                                    str_value = str(value)
                                    if len(str_value) > 50:
                                        str_value = str_value[:47] + "..."
                                    params_summary[key] = str_value
                                elif isinstance(value, (list, dict)):
                                    params_summary[key] = f"{type(value).__name__}({len(value)} items)"
                                else:
                                    params_summary[key] = str(type(value).__name__)
                        
                        next_action = {
                            "name": next_step.name,
                            "action_type": next_step.action_type,
                            "step_order": next_step.step_order,
                            "params_summary": params_summary,
                        }
                        
                        logger.info(
                            f"ResolutionAgent: Identified next action for exception {exception.exception_id}: "
                            f"step_order={next_step.step_order}, action_type={next_step.action_type}"
                        )
                        
                        # Emit ResolutionSuggested event (P7-13)
                        if self.exception_events_repository:
                            try:
                                from src.domain.events.exception_events import (
                                    ActorType,
                                    EventType,
                                    ResolutionSuggestedPayload,
                                    validate_and_build_event,
                                )
                                from src.repository.dto import ExceptionEventDTO
                                from src.infrastructure.db.models import ActorType as DBActorType
                                
                                # Build event payload
                                event_payload = ResolutionSuggestedPayload(
                                    suggested_action=next_step.name,
                                    playbook_id=exception.current_playbook_id,
                                    step_order=next_step.step_order,  # P7-13: Include step_order reference
                                    confidence=0.9,  # High confidence since it's the next step in assigned playbook
                                    reasoning=f"Next step in assigned playbook (step_order={next_step.step_order})",
                                    tool_calls=[{
                                        "action_type": next_step.action_type,
                                        "params": params_summary,
                                    }] if params_summary else None,
                                )
                                
                                # Build event envelope
                                event_envelope = validate_and_build_event(
                                    event_type=EventType.RESOLUTION_SUGGESTED,
                                    payload_dict=event_payload.model_dump(),
                                    tenant_id=exception.tenant_id,
                                    exception_id=exception.exception_id,
                                    actor_type=ActorType.AGENT,
                                    actor_id="ResolutionAgent",
                                )
                                
                                # Log event via repository
                                event_dto = ExceptionEventDTO(
                                    event_id=event_envelope.event_id,
                                    tenant_id=event_envelope.tenant_id,
                                    exception_id=event_envelope.exception_id,
                                    event_type=event_envelope.event_type,
                                    actor_type=DBActorType.AGENT,
                                    actor_id=event_envelope.actor_id,
                                    payload=event_envelope.payload,
                                )
                                
                                await self.exception_events_repository.append_event_if_new(event_dto)
                                logger.debug(
                                    f"ResolutionAgent: Emitted ResolutionSuggested event for exception {exception.exception_id}, "
                                    f"playbook_id={exception.current_playbook_id}, step_order={next_step.step_order}"
                                )
                            except Exception as e:
                                logger.warning(f"Failed to emit ResolutionSuggested event: {e}")
                    else:
                        logger.debug(
                            f"ResolutionAgent: No next step found for exception {exception.exception_id}, "
                            f"current_step={current_step_order}, playbook has {len(playbook.steps)} steps"
                        )
                else:
                    logger.debug(
                        f"ResolutionAgent: Playbook {exception.current_playbook_id} not found or has no steps "
                        f"for exception {exception.exception_id}"
                    )
            except Exception as e:
                logger.warning(f"Failed to load playbook or identify next step: {e}")
        
        # Extract actionability from context (from PolicyAgent decision evidence)
        actionability = self._extract_actionability(exception, context)
        
        # Extract selected playbook ID if available
        selected_playbook_id = self._extract_selected_playbook_id(context)
        
        resolved_plan = []
        suggested_draft_playbook = None
        
        # If actionable and approved, load and resolve playbook
        selected_playbook: Optional[Playbook] = None
        if actionability == "ACTIONABLE_APPROVED_PROCESS":
            if selected_playbook_id:
                resolved_plan = await self._resolve_approved_playbook(
                    exception, selected_playbook_id, actionability=actionability, context=context
                )
                # Find the selected playbook for LLM explanation
                selected_playbook = self._find_playbook_for_exception(exception)
            else:
                # Use PlaybookManager to select playbook (Phase 2)
                if self.tenant_policy:
                    playbook = self.playbook_manager.select_playbook(
                        exception, self.tenant_policy, self.domain_pack
                    )
                else:
                    # Fallback to manual lookup if no tenant policy
                    playbook = self._find_playbook_for_exception(exception)
                
                if playbook:
                    selected_playbook = playbook
                    # Get confidence from context if available
                    confidence = 1.0
                    if context and "prior_outputs" in context:
                        triage_output = context["prior_outputs"].get("triage")
                        if triage_output and hasattr(triage_output, "confidence"):
                            confidence = triage_output.confidence
                    
                    resolved_plan = await self._resolve_playbook_steps(
                        exception, playbook, actionability=actionability, confidence=confidence
                    )
        
        # Phase 2: If non-approved but actionable, generate draft playbook using LLM
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            if self.playbook_generator:
                # Use LLM-based generation
                try:
                    # Build evidence from context
                    evidence = []
                    if context and "prior_outputs" in context:
                        for agent_name, output in context["prior_outputs"].items():
                            if hasattr(output, "evidence"):
                                evidence.extend(output.evidence)
                    
                    # Generate playbook using LLM
                    generated_playbook = self.playbook_generator.generate_playbook(
                        exception_record=exception,
                        evidence=evidence,
                        domain_pack=self.domain_pack,
                    )
                    
                    # Convert to draft playbook format
                    suggested_draft_playbook = {
                        "exceptionType": generated_playbook.exception_type,
                        "steps": [
                            {
                                "stepNumber": i + 1,
                                "action": step.action,
                                "parameters": step.parameters or {},
                            }
                            for i, step in enumerate(generated_playbook.steps)
                        ],
                        "note": "LLM-generated playbook (not approved - requires human review)",
                        "approved": False,  # Never auto-approve LLM-generated playbooks
                    }
                    
                    logger.info(
                        f"Generated LLM playbook for exception {exception.exception_id} "
                        f"with {len(generated_playbook.steps)} steps"
                    )
                except PlaybookGeneratorError as e:
                    logger.warning(f"LLM playbook generation failed: {e}, falling back to simple draft")
                    suggested_draft_playbook = self._generate_draft_playbook(exception)
            else:
                # Fallback to simple draft generation
                suggested_draft_playbook = self._generate_draft_playbook(exception)
        
        # Phase 3: Add LLM-based explanation if available (advisory only - does not change tools)
        llm_reasoning: Optional[dict[str, Any]] = None
        if self.llm_client and resolved_plan and selected_playbook:
            try:
                # Build prompt with exception, triage result, policy decision, selected playbook, and evidence
                prompt = self.build_resolution_prompt(
                    exception, context, selected_playbook, resolved_plan
                )
                
                # Get rule-based result for fallback
                rule_based_result = self._create_rule_based_resolution_result(
                    exception, selected_playbook, resolved_plan, actionability
                )
                
                # Call LLM with fallback to rule-based logic
                llm_result = llm_or_rules(
                    llm_client=self.llm_client,
                    agent_name="ResolutionAgent",
                    tenant_id=exception.tenant_id,
                    schema_name="resolution",
                    prompt=prompt,
                    rule_based_fn=lambda: rule_based_result,
                    audit_logger=self.audit_logger,
                )
                
                # Extract reasoning from LLM result (advisory only - don't change tools)
                llm_reasoning = {
                    "playbook_selection_rationale": llm_result.get("playbook_selection_rationale", ""),
                    "rejected_playbooks": llm_result.get("rejected_playbooks", []),
                    "action_rationale": llm_result.get("action_rationale", ""),
                    "tool_execution_plan": llm_result.get("tool_execution_plan", []),
                    "expected_outcome": llm_result.get("expected_outcome"),
                    "reasoning_steps": llm_result.get("reasoning_steps", []),
                    "evidence_references": llm_result.get("evidence_references", []),
                    "natural_language_summary": llm_result.get("natural_language_summary", ""),
                }
                
            except Exception as e:
                logger.warning(f"LLM-enhanced resolution explanation failed: {e}, continuing without LLM reasoning")
        
        # Create agent decision with LLM reasoning (if available)
        decision = self._create_decision_with_reasoning(
            exception,
            actionability,
            resolved_plan,
            suggested_draft_playbook,
            llm_reasoning,
            next_action=next_action,  # Phase 7: Include next_action if available (P7-13)
        )
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context,
            }
            self.audit_logger.log_agent_event("ResolutionAgent", input_data, decision, exception.tenant_id)
        
        return decision

    def _extract_actionability(self, exception: ExceptionRecord, context: dict[str, Any]) -> str:
        """
        Extract actionability classification from context.
        
        Args:
            exception: ExceptionRecord
            context: Context from PolicyAgent
            
        Returns:
            Actionability classification string
        """
        # Check if actionability is directly in context
        if "actionability" in context:
            return context["actionability"]
        
        # Check if it's in prior outputs (from PolicyAgent decision evidence)
        if "prior_outputs" in context:
            policy_output = context["prior_outputs"].get("policy")
            if policy_output and hasattr(policy_output, "evidence"):
                for evidence in policy_output.evidence:
                    if "ACTIONABLE" in evidence or "NON_ACTIONABLE" in evidence:
                        if "ACTIONABLE_APPROVED_PROCESS" in evidence:
                            return "ACTIONABLE_APPROVED_PROCESS"
                        elif "ACTIONABLE_NON_APPROVED_PROCESS" in evidence:
                            return "ACTIONABLE_NON_APPROVED_PROCESS"
                        elif "NON_ACTIONABLE_INFO_ONLY" in evidence:
                            return "NON_ACTIONABLE_INFO_ONLY"
        
        # Default: assume actionable if we have an exception type
        # Note: This is a fallback - in production, actionability should come from PolicyAgent
        return "NON_ACTIONABLE_INFO_ONLY"

    def _extract_selected_playbook_id(self, context: dict[str, Any]) -> Optional[str]:
        """
        Extract selected playbook ID from context.
        
        Args:
            context: Context from PolicyAgent
            
        Returns:
            Playbook ID or None
        """
        # Check if playbook ID is directly in context
        if "selectedPlaybookId" in context:
            return context["selectedPlaybookId"]
        
        # Check if it's in prior outputs (from PolicyAgent decision evidence)
        if "prior_outputs" in context:
            policy_output = context["prior_outputs"].get("policy")
            if policy_output and hasattr(policy_output, "evidence"):
                for evidence in policy_output.evidence:
                    if "selectedPlaybookId:" in evidence:
                        # Extract playbook ID from evidence string
                        match = re.search(r"selectedPlaybookId:\s*(\S+)", evidence)
                        if match:
                            playbook_id = match.group(1)
                            if playbook_id != "None":
                                return playbook_id
        
        return None

    def _find_playbook_for_exception(self, exception: ExceptionRecord) -> Optional[Playbook]:
        """
        Find playbook for exception type.
        
        Args:
            exception: ExceptionRecord to find playbook for
            
        Returns:
            Playbook or None if not found
        """
        if not exception.exception_type:
            return None
        
        # Search domain pack playbooks
        for playbook in self.domain_pack.playbooks:
            if playbook.exception_type == exception.exception_type:
                return playbook
        
        return None

    async def _resolve_approved_playbook(
        self,
        exception: ExceptionRecord,
        playbook_id: str,
        actionability: str = "ACTIONABLE_APPROVED_PROCESS",
        context: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        Resolve an approved playbook into structured action plan.
        
        Args:
            exception: ExceptionRecord
            playbook_id: Playbook identifier (exception type for MVP)
            actionability: Actionability classification
            context: Optional context with prior outputs
            
        Returns:
            List of structured actions
            
        Raises:
            ResolutionAgentError: If playbook not found or validation fails
        """
        # Find playbook by exception type (MVP uses exception_type as ID)
        playbook = None
        for p in self.domain_pack.playbooks:
            if p.exception_type == playbook_id:
                playbook = p
                break
        
        if not playbook:
            raise ResolutionAgentError(f"Playbook not found for ID: {playbook_id}")
        
        # Get confidence from context if available
        confidence = 1.0
        if context and "prior_outputs" in context:
            triage_output = context["prior_outputs"].get("triage")
            if triage_output and hasattr(triage_output, "confidence"):
                confidence = triage_output.confidence
        
        return await self._resolve_playbook_steps(
            exception, playbook, actionability=actionability, confidence=confidence
        )

    async def _resolve_playbook_steps(
        self,
        exception: ExceptionRecord,
        playbook: Playbook,
        actionability: str = "ACTIONABLE_APPROVED_PROCESS",
        confidence: float = 1.0,
    ) -> list[dict[str, Any]]:
        """
        Resolve playbook steps into structured action plan with partial automation.
        
        Phase 2: Executes tools using ToolExecutionEngine if conditions are met:
        - PolicyAgent allows auto-action (actionability == "ACTIONABLE_APPROVED_PROCESS")
        - Severity not CRITICAL
        - Confidence meets threshold
        - Human approval not required
        
        Args:
            exception: ExceptionRecord
            playbook: Playbook to resolve
            actionability: Actionability classification from PolicyAgent
            confidence: Confidence score from previous agents
            
        Returns:
            List of structured actions with execution status and results
        """
        resolved_plan = []
        executed_steps: list[dict[str, Any]] = []  # Track executed steps for rollback
        
        # Determine if tools should be executed (not just planned)
        should_execute = self._should_execute_tools(exception, actionability, confidence)
        
        for step_idx, step in enumerate(playbook.steps):
            # Extract tool name from step action
            tool_name = self._extract_tool_name_from_step(step)
            
            # Initialize action structure
            action: dict[str, Any] = {
                "stepNumber": step_idx + 1,
                "action": step.action,
                "toolName": tool_name,
                "parameters": step.parameters or {},
                "validated": False,
                "status": StepExecutionStatus.SKIPPED.value,
            }
            
            # Validate tool exists in domain pack
            if tool_name:
                if tool_name not in self.domain_pack.tools:
                    # Validation failure - raise exception (backward compatibility)
                    error_msg = (
                        f"Tool '{tool_name}' referenced in playbook step {step_idx + 1} "
                        f"not found in domain pack. Valid tools: {sorted(self.domain_pack.tools.keys())}"
                    )
                    self._audit_step_execution(exception, step_idx + 1, {
                        "stepNumber": step_idx + 1,
                        "action": step.action,
                        "toolName": tool_name,
                        "status": StepExecutionStatus.FAILED.value,
                        "error": error_msg,
                    })
                    raise ResolutionAgentError(error_msg)
                
                # Validate tool is allow-listed for tenant
                if not self.tool_registry.is_allowed(exception.tenant_id, tool_name):
                    # Validation failure - raise exception (backward compatibility)
                    error_msg = (
                        f"Tool '{tool_name}' referenced in playbook step {step_idx + 1} "
                        f"is not allow-listed for tenant {exception.tenant_id}"
                    )
                    self._audit_step_execution(exception, step_idx + 1, {
                        "stepNumber": step_idx + 1,
                        "action": step.action,
                        "toolName": tool_name,
                        "status": StepExecutionStatus.FAILED.value,
                        "error": error_msg,
                    })
                    raise ResolutionAgentError(error_msg)
                
                # Get tool definition
                tool_def = self.domain_pack.tools[tool_name]
                action["toolDescription"] = tool_def.description
                action["endpoint"] = tool_def.endpoint
                action["validated"] = True
                
                # Execute tool if conditions are met (Phase 2)
                if should_execute and self.execution_engine and self.tenant_policy:
                    try:
                        # Execute using ToolExecutionEngine
                        result = await self.execution_engine.execute(
                            tool_name=tool_name,
                            args=step.parameters or {},
                            tenant_policy=self.tenant_policy,
                            domain_pack=self.domain_pack,
                            tenant_id=exception.tenant_id,
                            mode="async",
                            exception_id=exception.exception_id,  # Phase 3: Pass exception_id for evidence tracking (P3-29)
                        )
                        
                        action["status"] = StepExecutionStatus.SUCCESS.value
                        action["executionResult"] = result
                        action["executed"] = True
                        executed_steps.append(action)  # Track for potential rollback
                        
                        logger.info(
                            f"Step {step_idx + 1} executed successfully: {tool_name} "
                            f"for exception {exception.exception_id}"
                        )
                        
                    except ToolExecutionError as e:
                        action["status"] = StepExecutionStatus.FAILED.value
                        action["error"] = str(e)
                        action["executed"] = False
                        
                        logger.error(
                            f"Step {step_idx + 1} execution failed: {tool_name} - {e}"
                        )
                        
                        # Attempt rollback if rollback tool is defined
                        rollback_success = await self._attempt_rollback(
                            exception, executed_steps, step_idx + 1
                        )
                        
                        if not rollback_success:
                            # Escalate if rollback fails or not available
                            await self._escalate_failure(exception, step_idx + 1, str(e))
                        
                elif not should_execute:
                    # Conditions not met for execution
                    if exception.severity == Severity.CRITICAL:
                        action["status"] = StepExecutionStatus.NEEDS_APPROVAL.value
                        action["reason"] = "CRITICAL severity requires human approval"
                    elif confidence < self._get_confidence_threshold():
                        action["status"] = StepExecutionStatus.NEEDS_APPROVAL.value
                        action["reason"] = f"Confidence {confidence:.2f} below threshold"
                    else:
                        action["status"] = StepExecutionStatus.SKIPPED.value
                        action["reason"] = "Execution conditions not met"
                else:
                    # No execution engine available
                    action["status"] = StepExecutionStatus.SKIPPED.value
                    action["reason"] = "Execution engine not available"
            else:
                # Step doesn't reference a tool (e.g., conditional logic, notification)
                action["validated"] = True
                action["status"] = StepExecutionStatus.SKIPPED.value
                action["reason"] = "Non-tool step (notification/conditional)"
            
            # Always audit step execution
            self._audit_step_execution(exception, step_idx + 1, action)
            resolved_plan.append(action)
        
        return resolved_plan
    
    def _should_execute_tools(
        self,
        exception: ExceptionRecord,
        actionability: str,
        confidence: float,
    ) -> bool:
        """
        Determine if tools should be executed (not just planned).
        
        Phase 2 conditions:
        - PolicyAgent allows auto-action (actionability == "ACTIONABLE_APPROVED_PROCESS")
        - Severity not CRITICAL (never auto-execute CRITICAL)
        - Confidence meets threshold from tenant policy
        - Human approval not required
        
        Args:
            exception: ExceptionRecord
            actionability: Actionability classification
            confidence: Confidence score from previous agents
            
        Returns:
            True if tools should be executed, False otherwise
        """
        # Must be actionable and approved
        if actionability != "ACTIONABLE_APPROVED_PROCESS":
            return False
        
        # Never execute for CRITICAL severity
        if exception.severity == Severity.CRITICAL:
            return False
        
        # Check confidence threshold
        confidence_threshold = self._get_confidence_threshold()
        if confidence < confidence_threshold:
            return False
        
        # Check human approval requirement
        if self.tenant_policy:
            for rule in self.tenant_policy.human_approval_rules:
                if rule.severity == (exception.severity.value if exception.severity else "UNKNOWN"):
                    if rule.require_approval:
                        return False
        
        # All conditions met
        return True
    
    def _get_confidence_threshold(self) -> float:
        """
        Get confidence threshold from tenant policy or domain pack guardrails.
        
        Returns:
            Confidence threshold (0.0-1.0)
        """
        if self.tenant_policy:
            guardrails = (
                self.tenant_policy.custom_guardrails or self.domain_pack.guardrails
            )
            return guardrails.human_approval_threshold
        
        # Default threshold if no policy
        return 0.8
    
    async def _attempt_rollback(
        self,
        exception: ExceptionRecord,
        executed_steps: list[dict[str, Any]],
        failed_step: int,
    ) -> bool:
        """
        Attempt to rollback executed steps when a step fails.
        
        Looks for a rollback tool in the domain pack and executes it.
        
        Args:
            exception: ExceptionRecord
            executed_steps: List of successfully executed steps
            failed_step: Step number that failed
            
        Returns:
            True if rollback was attempted and succeeded, False otherwise
        """
        if not executed_steps or not self.execution_engine or not self.tenant_policy:
            return False
        
        # Look for rollback tool (common names: rollback, undo, revert)
        rollback_tool_names = ["rollback", "undo", "revert", "rollbackStep"]
        rollback_tool = None
        
        for tool_name in rollback_tool_names:
            if tool_name in self.domain_pack.tools:
                rollback_tool = tool_name
                break
        
        if not rollback_tool:
            logger.warning(
                f"No rollback tool found for exception {exception.exception_id} "
                f"after step {failed_step} failure"
            )
            return False
        
        # Check if rollback tool is approved
        if not self.tool_registry.is_allowed(exception.tenant_id, rollback_tool):
            logger.warning(
                f"Rollback tool '{rollback_tool}' not approved for tenant {exception.tenant_id}"
            )
            return False
        
        try:
            # Execute rollback with executed steps as context
            rollback_params = {
                "executedSteps": executed_steps,
                "failedStep": failed_step,
                "exceptionId": exception.exception_id,
            }
            
            await self.execution_engine.execute(
                tool_name=rollback_tool,
                args=rollback_params,
                tenant_policy=self.tenant_policy,
                domain_pack=self.domain_pack,
                tenant_id=exception.tenant_id,
                mode="async",
            )
            
            logger.info(
                f"Rollback executed successfully for exception {exception.exception_id} "
                f"after step {failed_step} failure"
            )
            
            # Audit rollback
            if self.audit_logger:
                self.audit_logger.log_decision(
                    "ResolutionAgent - Rollback executed",
                    {
                        "exceptionId": exception.exception_id,
                        "failedStep": failed_step,
                        "rollbackTool": rollback_tool,
                        "executedSteps": len(executed_steps),
                    },
                    tenant_id=exception.tenant_id,
                )
            
            return True
            
        except ToolExecutionError as e:
            logger.error(
                f"Rollback execution failed for exception {exception.exception_id}: {e}"
            )
            
            # Audit rollback failure
            if self.audit_logger:
                self.audit_logger.log_decision(
                    "ResolutionAgent - Rollback failed",
                    {
                        "exceptionId": exception.exception_id,
                        "failedStep": failed_step,
                        "rollbackTool": rollback_tool,
                        "error": str(e),
                    },
                    tenant_id=exception.tenant_id,
                )
            
            return False
    
    async def _escalate_failure(
        self, exception: ExceptionRecord, failed_step: int, error: str
    ) -> None:
        """
        Escalate a failed step to human review.
        
        Args:
            exception: ExceptionRecord
            failed_step: Step number that failed
            error: Error message
        """
        logger.warning(
            f"Escalating failure for exception {exception.exception_id} "
            f"at step {failed_step}: {error}"
        )
        
        # Look for escalation tool
        escalation_tool_names = ["escalate", "escalateCase", "openCase", "notifyEscalation"]
        escalation_tool = None
        
        for tool_name in escalation_tool_names:
            if tool_name in self.domain_pack.tools:
                if self.tool_registry.is_allowed(exception.tenant_id, tool_name):
                    escalation_tool = tool_name
                    break
        
        if escalation_tool and self.execution_engine and self.tenant_policy:
            try:
                escalation_params = {
                    "exceptionId": exception.exception_id,
                    "failedStep": failed_step,
                    "error": error,
                    "severity": exception.severity.value if exception.severity else "UNKNOWN",
                }
                
                await self.execution_engine.execute(
                    tool_name=escalation_tool,
                    args=escalation_params,
                    tenant_policy=self.tenant_policy,
                    domain_pack=self.domain_pack,
                    tenant_id=exception.tenant_id,
                    mode="async",
                )
                
                logger.info(
                    f"Escalation executed for exception {exception.exception_id}"
                )
            except ToolExecutionError as e:
                logger.error(
                    f"Escalation execution failed for exception {exception.exception_id}: {e}"
                )
        
        # Always audit escalation
        if self.audit_logger:
            self.audit_logger.log_decision(
                "ResolutionAgent - Escalation",
                {
                    "exceptionId": exception.exception_id,
                    "failedStep": failed_step,
                    "error": error,
                    "escalationTool": escalation_tool or "none",
                },
                tenant_id=exception.tenant_id,
            )
    
    def _audit_step_execution(
        self, exception: ExceptionRecord, step_number: int, action: dict[str, Any]
    ) -> None:
        """
        Audit log each step execution.
        
        Args:
            exception: ExceptionRecord
            step_number: Step number
            action: Action dictionary with execution details
        """
        if not self.audit_logger:
            return
        
        audit_data = {
            "stepNumber": step_number,
            "action": action.get("action"),
            "toolName": action.get("toolName"),
            "status": action.get("status"),
            "exceptionId": exception.exception_id,
        }
        
        if action.get("executionResult"):
            audit_data["executionResult"] = action["executionResult"]
        if action.get("error"):
            audit_data["error"] = action["error"]
        if action.get("reason"):
            audit_data["reason"] = action["reason"]
        
        self.audit_logger.log_decision(
            "ResolutionAgent - Step Execution",
            audit_data,
            tenant_id=exception.tenant_id,
        )

    def _extract_tool_name_from_step(self, step: PlaybookStep) -> Optional[str]:
        """
        Extract tool name from playbook step.
        
        Handles various formats:
        - "invokeTool('toolName')"
        - "toolName"
        - Parameters dict with tool references
        
        Args:
            step: PlaybookStep to analyze
            
        Returns:
            Tool name if found, None otherwise
        """
        action = step.action
        
        # Check if action directly references a tool
        # Common patterns: "invokeTool", "callTool", "useTool"
        if "tool" in action.lower() or "invoke" in action.lower() or "call" in action.lower():
            # Try to extract from action string
            # Look for patterns like invokeTool('name') or toolName('name')
            match = re.search(r"['\"]([^'\"]+)['\"]", action)
            if match:
                return match.group(1)
        
        # Check parameters for tool references
        if step.parameters:
            # Look for common tool parameter keys
            tool_keys = ["tool", "toolName", "tool_name", "action", "method"]
            for key in tool_keys:
                if key in step.parameters and isinstance(step.parameters[key], str):
                    return step.parameters[key]
        
        # If action looks like a direct tool name (simple identifier, possibly with parentheses)
        # Extract tool name before parentheses
        if "(" in action:
            tool_name = action.split("(")[0].strip()
            if tool_name and " " not in tool_name:
                return tool_name
        elif " " not in action and action:
            # Simple identifier without spaces
            return action
        
        return None

    def _generate_draft_playbook(self, exception: ExceptionRecord) -> dict[str, Any]:
        """
        Generate a suggested draft playbook for non-approved but actionable exceptions.
        
        Args:
            exception: ExceptionRecord to generate playbook for
            
        Returns:
            Dictionary with draft playbook structure
        """
        # Find applicable playbook from domain pack (even if not approved)
        playbook = self._find_playbook_for_exception(exception)
        
        if not playbook:
            return {
                "exceptionType": exception.exception_type,
                "steps": [],
                "note": "No playbook available for this exception type",
            }
        
        # Generate draft structure
        draft_steps = []
        for step_idx, step in enumerate(playbook.steps):
            tool_name = self._extract_tool_name_from_step(step)
            
            draft_step = {
                "stepNumber": step_idx + 1,
                "action": step.action,
                "toolName": tool_name,
                "parameters": step.parameters or {},
            }
            
            # Add validation status
            if tool_name:
                if tool_name in self.domain_pack.tools:
                    draft_step["toolExists"] = True
                    draft_step["toolAllowListed"] = self.tool_registry.is_allowed(
                        exception.tenant_id, tool_name
                    )
                else:
                    draft_step["toolExists"] = False
                    draft_step["toolAllowListed"] = False
            
            draft_steps.append(draft_step)
        
        return {
            "exceptionType": exception.exception_type,
            "steps": draft_steps,
            "note": "This playbook is not approved but could be used if approved",
        }

    def _check_human_approval_required(self, context: Optional[dict[str, Any]]) -> bool:
        """
        Check if human approval is required from context.
        
        Args:
            context: Context from PolicyAgent
            
        Returns:
            True if human approval is required
        """
        if not context:
            return False
        
        # Check if humanApprovalRequired is in context
        if "humanApprovalRequired" in context:
            return context["humanApprovalRequired"]
        
        # Check if it's in prior outputs (from PolicyAgent decision evidence)
        if "prior_outputs" in context:
            policy_output = context["prior_outputs"].get("policy")
            if policy_output and hasattr(policy_output, "evidence"):
                for evidence in policy_output.evidence:
                    if "humanApprovalRequired:" in evidence:
                        # Extract value from evidence string
                        match = re.search(r"humanApprovalRequired:\s*(\S+)", evidence)
                        if match:
                            value = match.group(1).lower()
                            return value == "true"
        
        return False

    def _submit_for_approval(
        self,
        exception: ExceptionRecord,
        resolved_plan: list[dict[str, Any]],
        context: Optional[dict[str, Any]],
    ) -> str:
        """
        Submit resolution plan for human approval.
        
        Args:
            exception: ExceptionRecord
            resolved_plan: Resolved plan from playbook
            context: Context from agents
            
        Returns:
            Approval ID
        """
        if not self.approval_queue_registry:
            raise ResolutionAgentError("Approval queue registry not available")
        
        # Get or create approval queue for tenant
        approval_queue = self.approval_queue_registry.get_or_create_queue(exception.tenant_id)
        
        # Build evidence from context
        evidence = []
        if context and "prior_outputs" in context:
            for agent_name, output in context["prior_outputs"].items():
                if hasattr(output, "evidence"):
                    evidence.extend(output.evidence)
        
        # Submit for approval
        approval_id = approval_queue.submit_for_approval(
            exception_id=exception.exception_id,
            plan={"resolvedPlan": resolved_plan, "exception": exception.model_dump()},
            evidence=evidence,
        )
        
        return approval_id

    def _create_approval_pending_decision(
        self,
        exception: ExceptionRecord,
        resolved_plan: list[dict[str, Any]],
        approval_id: str,
    ) -> AgentDecision:
        """
        Create decision indicating approval is pending.
        
        Args:
            exception: ExceptionRecord
            resolved_plan: Resolved plan
            approval_id: Approval ID
            
        Returns:
            AgentDecision
        """
        evidence = [
            f"Resolution plan submitted for approval: {approval_id}",
            f"Plan contains {len(resolved_plan)} steps",
            "Status: PENDING_APPROVAL",
        ]
        
        return AgentDecision(
            decision=f"Plan submitted for approval ({approval_id})",
            confidence=0.8,  # Lower confidence since pending approval
            evidence=evidence,
            nextStep="WaitForApproval",
        )

    def _create_decision(
        self,
        exception: ExceptionRecord,
        actionability: str,
        resolved_plan: list[dict[str, Any]],
        suggested_draft_playbook: Optional[dict[str, Any]],
    ) -> AgentDecision:
        """
        Create agent decision from resolution planning results.
        
        Args:
            exception: ExceptionRecord
            actionability: Actionability classification
            resolved_plan: Resolved action plan
            suggested_draft_playbook: Suggested draft playbook if applicable
            
        Returns:
            AgentDecision
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Exception type: {exception.exception_type}")
        evidence.append(f"Actionability: {actionability}")
        
        if resolved_plan:
            evidence.append(f"Resolved plan: {len(resolved_plan)} actions")
            for action in resolved_plan:
                if action.get("toolName"):
                    evidence.append(
                        f"Step {action['stepNumber']}: {action['toolName']} - {action.get('toolDescription', '')}"
                    )
                else:
                    evidence.append(f"Step {action['stepNumber']}: {action['action']}")
        else:
            evidence.append("No resolved plan (non-actionable or no playbook)")
        
        if suggested_draft_playbook:
            evidence.append("Suggested draft playbook generated")
            evidence.append(f"Draft steps: {len(suggested_draft_playbook.get('steps', []))}")
        
        # Calculate confidence
        if actionability == "ACTIONABLE_APPROVED_PROCESS" and resolved_plan:
            # All tools validated
            all_validated = all(action.get("validated", False) for action in resolved_plan)
            confidence = 0.9 if all_validated else 0.7
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            confidence = 0.6
        else:
            confidence = 0.5
        
        # Determine decision text
        if resolved_plan:
            decision_text = f"Resolved plan created with {len(resolved_plan)} actions"
        elif suggested_draft_playbook:
            decision_text = "Draft playbook suggested (not approved)"
        else:
            decision_text = "No resolution plan available"
        
        # Add resolved plan and draft playbook to evidence as structured data
        # (In production, these would be in a separate metadata field)
        evidence.append(f"resolvedPlan: {len(resolved_plan)} actions")
        if suggested_draft_playbook:
            evidence.append("suggestedDraftPlaybook: available")
        
        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep="ProceedToFeedback",
        )

    def build_resolution_prompt(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]],
        selected_playbook: Playbook,
        resolved_plan: list[dict[str, Any]],
    ) -> str:
        """
        Build prompt for LLM resolution explanation.
        
        Combines exception details, triage result, policy decision, selected playbook,
        and resolved plan into a structured prompt.
        
        Args:
            exception: ExceptionRecord to explain
            context: Optional context from previous agents (includes triage_result, policy_decision)
            selected_playbook: Selected playbook that was executed
            resolved_plan: Resolved action plan with tool execution results
            
        Returns:
            Formatted prompt string for LLM
        """
        prompt_parts = []
        
        # Base prompt from agent template
        prompt_parts.append(
            "You are the ResolutionAgent. Select playbook from Domain/Tenant Packs matching exceptionType. "
            "Explain why this playbook is appropriate, why alternative playbooks were rejected, "
            "and explain the tool execution order and dependencies. Provide a natural language summary for operators."
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
        
        # Policy decision from context
        if context:
            policy_decision = context.get("policy_decision")
            if policy_decision:
                prompt_parts.append(f"\n## Policy Decision:")
                prompt_parts.append(f"- Decision: {policy_decision}")
                actionability = self._extract_actionability(exception, context)
                prompt_parts.append(f"- Actionability: {actionability}")
        
        # Selected playbook
        prompt_parts.append(f"\n## Selected Playbook:")
        prompt_parts.append(f"- Exception Type: {selected_playbook.exception_type}")
        if hasattr(selected_playbook, "description") and selected_playbook.description:
            prompt_parts.append(f"- Description: {selected_playbook.description}")
        prompt_parts.append(f"- Number of Steps: {len(selected_playbook.steps)}")
        
        # Playbook steps
        prompt_parts.append("\n## Playbook Steps:")
        for i, step in enumerate(selected_playbook.steps, 1):
            prompt_parts.append(f"{i}. {step.action}")
            if step.parameters:
                prompt_parts.append(f"   Parameters: {json.dumps(step.parameters, indent=2)}")
        
        # Alternative playbooks (other playbooks for same exception type)
        alternative_playbooks = []
        for playbook in self.domain_pack.playbooks:
            if playbook.exception_type == exception.exception_type and playbook != selected_playbook:
                alternative_playbooks.append(playbook)
        
        if alternative_playbooks:
            prompt_parts.append("\n## Alternative Playbooks (Rejected):")
            for alt_playbook in alternative_playbooks[:3]:  # Limit to first 3
                prompt_parts.append(f"- {alt_playbook.exception_type}")
                if hasattr(alt_playbook, "description") and alt_playbook.description:
                    prompt_parts.append(f"  Description: {alt_playbook.description}")
        else:
            prompt_parts.append("\n## Alternative Playbooks: None found")
        
        # Resolved plan (tool execution results)
        prompt_parts.append("\n## Resolved Action Plan:")
        for action in resolved_plan:
            step_num = action.get("stepNumber", "?")
            tool_name = action.get("toolName", "N/A")
            status = action.get("status", "UNKNOWN")
            prompt_parts.append(f"Step {step_num}: {tool_name} - Status: {status}")
            if action.get("executionResult"):
                prompt_parts.append(f"  Result: {str(action['executionResult'])[:100]}")
        
        # Available tools in domain pack
        prompt_parts.append("\n## Available Tools in Domain Pack:")
        for tool_name, tool_def in list(self.domain_pack.tools.items())[:10]:  # Limit to first 10
            prompt_parts.append(f"- {tool_name}: {tool_def.description}")
        if len(self.domain_pack.tools) > 10:
            prompt_parts.append(f"... and {len(self.domain_pack.tools) - 10} more tools")
        
        # Instructions
        prompt_parts.append(
            "\n## Instructions:"
            "\nAnalyze the resolution plan and provide:"
            "\n1. Explanation why this playbook is appropriate for this exception"
            "\n2. Reasons for rejecting alternative playbooks (if any)"
            "\n3. Explanation of tool execution order and dependencies"
            "\n4. Expected outcome of the resolution"
            "\n5. Natural language action summary for operators"
            "\n6. Structured reasoning steps explaining your analysis"
            "\n7. Evidence references (which tools, playbooks, and policies were considered)"
            "\n\nIMPORTANT: Do NOT suggest adding new tools or changing the execution plan. "
            "You are providing explanation only, not modifying the approved playbook."
        )
        
        return "\n".join(prompt_parts)

    def _create_rule_based_resolution_result(
        self,
        exception: ExceptionRecord,
        selected_playbook: Playbook,
        resolved_plan: list[dict[str, Any]],
        actionability: str,
    ) -> dict[str, Any]:
        """
        Create rule-based resolution result in LLM output format.
        
        This is used as fallback when LLM is unavailable.
        
        Args:
            exception: ExceptionRecord
            selected_playbook: Selected playbook
            resolved_plan: Resolved action plan
            actionability: Actionability classification
            
        Returns:
            Dictionary in ResolutionLLMOutput format
        """
        # Build tool execution plan from resolved plan
        tool_execution_plan = []
        for action in resolved_plan:
            if action.get("toolName"):
                tool_execution_plan.append({
                    "step_number": action.get("stepNumber", 0),
                    "tool_name": action.get("toolName"),
                    "action": action.get("action", ""),
                    "status": action.get("status", "UNKNOWN"),
                    "dependencies": [],  # Would need to analyze step dependencies
                })
        
        # Determine resolution status
        if not resolved_plan:
            resolution_status = "PENDING"
        elif all(action.get("status") == "SUCCESS" for action in resolved_plan if action.get("toolName")):
            resolution_status = "RESOLVED"
        elif any(action.get("status") == "SUCCESS" for action in resolved_plan if action.get("toolName")):
            resolution_status = "PARTIAL"
        elif any(action.get("status") == "FAILED" for action in resolved_plan if action.get("toolName")):
            resolution_status = "FAILED"
        else:
            resolution_status = "PENDING"
        
        return {
            "selected_playbook_id": selected_playbook.exception_type,
            "playbook_selection_rationale": f"Playbook selected based on exception type {exception.exception_type} matching playbook exception type.",
            "rejected_playbooks": [],
            "action_rationale": f"Executed {len(resolved_plan)} steps from approved playbook. Actionability: {actionability}.",
            "tool_execution_plan": tool_execution_plan,
            "expected_outcome": f"Resolution of {exception.exception_type} exception using approved playbook.",
            "resolution_status": resolution_status,
            "reasoning_steps": [
                {
                    "step_number": 1,
                    "description": "Selected playbook based on exception type",
                    "outcome": f"Playbook {selected_playbook.exception_type} selected",
                },
                {
                    "step_number": 2,
                    "description": "Resolved playbook steps into action plan",
                    "outcome": f"{len(resolved_plan)} actions planned",
                },
            ],
            "evidence_references": [
                {
                    "reference_id": "selected_playbook",
                    "description": f"Playbook: {selected_playbook.exception_type}",
                    "relevance_score": 1.0,
                },
            ],
            "confidence": 0.85 if resolved_plan else 0.65,
            "natural_language_summary": f"Resolved {exception.exception_type} exception using playbook {selected_playbook.exception_type} with {len(resolved_plan)} actions.",
        }

    def _create_decision_with_reasoning(
        self,
        exception: ExceptionRecord,
        actionability: str,
        resolved_plan: list[dict[str, Any]],
        suggested_draft_playbook: Optional[dict[str, Any]],
        llm_reasoning: Optional[dict[str, Any]],
        next_action: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Create agent decision with structured reasoning from LLM.
        
        Args:
            exception: ExceptionRecord
            actionability: Actionability classification
            resolved_plan: Resolved action plan
            suggested_draft_playbook: Suggested draft playbook if applicable
            llm_reasoning: Optional LLM reasoning dictionary
            next_action: Optional next action suggestion from assigned playbook (P7-13)
            
        Returns:
            AgentDecision with enhanced evidence including reasoning
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Exception type: {exception.exception_type}")
        evidence.append(f"Actionability: {actionability}")
        
        # Phase 7: Add next_action to evidence if available (P7-13)
        if next_action:
            evidence.append(f"Next action: {next_action.get('name', 'N/A')}")
            evidence.append(f"Action type: {next_action.get('action_type', 'N/A')}")
            evidence.append(f"Step order: {next_action.get('step_order', 'N/A')}")
            if next_action.get('params_summary'):
                params_str = ", ".join(f"{k}={v}" for k, v in list(next_action['params_summary'].items())[:3])
                if len(next_action['params_summary']) > 3:
                    params_str += "..."
                evidence.append(f"Params: {params_str}")
        
        # Add LLM reasoning if available
        if llm_reasoning:
            # Add natural language summary
            if llm_reasoning.get("natural_language_summary"):
                evidence.append(f"Summary: {llm_reasoning['natural_language_summary']}")
            
            # Add playbook selection rationale
            if llm_reasoning.get("playbook_selection_rationale"):
                evidence.append(f"Playbook selection rationale: {llm_reasoning['playbook_selection_rationale']}")
            
            # Add rejected playbooks
            if llm_reasoning.get("rejected_playbooks"):
                evidence.append("Rejected playbooks:")
                for rejected in llm_reasoning["rejected_playbooks"]:
                    playbook_id = rejected.get("playbook_id", "Unknown")
                    reason = rejected.get("reason", "Not specified")
                    evidence.append(f"  - {playbook_id}: {reason}")
            
            # Add action rationale
            if llm_reasoning.get("action_rationale"):
                evidence.append(f"Action rationale: {llm_reasoning['action_rationale']}")
            
            # Add tool execution plan explanation
            if llm_reasoning.get("tool_execution_plan"):
                evidence.append("Tool execution plan:")
                for plan_item in llm_reasoning["tool_execution_plan"]:
                    step_num = plan_item.get("step_number", "?")
                    tool_name = plan_item.get("tool_name", "N/A")
                    explanation = plan_item.get("explanation", "")
                    evidence.append(f"  Step {step_num}: {tool_name}")
                    if explanation:
                        evidence.append(f"    Explanation: {explanation}")
            
            # Add expected outcome
            if llm_reasoning.get("expected_outcome"):
                evidence.append(f"Expected outcome: {llm_reasoning['expected_outcome']}")
            
            # Add reasoning steps
            if llm_reasoning.get("reasoning_steps"):
                evidence.append("Reasoning steps:")
                for step in llm_reasoning["reasoning_steps"]:
                    step_desc = step.get("description", "")
                    step_outcome = step.get("outcome", "")
                    evidence.append(f"  - {step_desc}")
                    if step_outcome:
                        evidence.append(f"    Outcome: {step_outcome}")
            
            # Add evidence references
            if llm_reasoning.get("evidence_references"):
                evidence.append("Evidence sources:")
                for ref in llm_reasoning["evidence_references"]:
                    ref_id = ref.get("reference_id", "Unknown")
                    ref_desc = ref.get("description", "")
                    evidence.append(f"  - {ref_id}: {ref_desc}")
        
        # Add resolved plan details
        if resolved_plan:
            evidence.append(f"Resolved plan: {len(resolved_plan)} actions")
            for action in resolved_plan:
                if action.get("toolName"):
                    evidence.append(
                        f"Step {action['stepNumber']}: {action['toolName']} - {action.get('toolDescription', '')} - Status: {action.get('status', 'UNKNOWN')}"
                    )
                else:
                    evidence.append(f"Step {action['stepNumber']}: {action['action']}")
        else:
            evidence.append("No resolved plan (non-actionable or no playbook)")
        
        if suggested_draft_playbook:
            evidence.append("Suggested draft playbook generated")
            evidence.append(f"Draft steps: {len(suggested_draft_playbook.get('steps', []))}")
        
        # Calculate confidence
        if actionability == "ACTIONABLE_APPROVED_PROCESS" and resolved_plan:
            # All tools validated
            all_validated = all(action.get("validated", False) for action in resolved_plan)
            confidence = 0.9 if all_validated else 0.7
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            confidence = 0.6
        else:
            confidence = 0.5
        
        # Adjust confidence if LLM reasoning is available
        if llm_reasoning:
            confidence = min(1.0, confidence + 0.05)  # Slight boost for LLM explanation
        
        # Determine decision text
        if resolved_plan:
            decision_text = f"Resolved plan created with {len(resolved_plan)} actions"
            if llm_reasoning:
                decision_text += " (with LLM explanation)"
        elif suggested_draft_playbook:
            decision_text = "Draft playbook suggested (not approved)"
        else:
            decision_text = "No resolution plan available"
        
        # Add resolved plan and draft playbook to evidence as structured data
        evidence.append(f"resolvedPlan: {len(resolved_plan)} actions")
        if suggested_draft_playbook:
            evidence.append("suggestedDraftPlaybook: available")
        
        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep="ProceedToFeedback",
        )
