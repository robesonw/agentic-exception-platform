"""
ResolutionAgent implementation for MVP.
Plans resolution actions from playbooks (no execution in MVP).
Matches specification from docs/04-agent-templates.md
"""

import re
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Playbook, PlaybookStep
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.tools.invoker import ToolInvoker, ToolInvocationError
from src.tools.registry import ToolRegistry


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
    ):
        """
        Initialize ResolutionAgent.
        
        Args:
            domain_pack: Domain Pack containing playbooks and tools
            tool_registry: Tool Registry for validation
            audit_logger: Optional AuditLogger for logging
            tool_invoker: Optional ToolInvoker for executing tools (default: None, uses dry_run)
            tenant_policy: Optional TenantPolicyPack for human approval checks
        """
        self.domain_pack = domain_pack
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger
        self.tool_invoker = tool_invoker
        self.tenant_policy = tenant_policy

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
        
        # Extract actionability from context (from PolicyAgent decision evidence)
        actionability = self._extract_actionability(exception, context)
        
        # Extract selected playbook ID if available
        selected_playbook_id = self._extract_selected_playbook_id(context)
        
        resolved_plan = []
        suggested_draft_playbook = None
        
        # If actionable and approved, load and resolve playbook
        if actionability == "ACTIONABLE_APPROVED_PROCESS":
            if selected_playbook_id:
                resolved_plan = await self._resolve_approved_playbook(
                    exception, selected_playbook_id
                )
            else:
                # Find playbook for exception type
                playbook = self._find_playbook_for_exception(exception)
                if playbook:
                    resolved_plan = await self._resolve_playbook_steps(exception, playbook)
        
        # If non-approved but actionable, generate draft playbook
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            suggested_draft_playbook = self._generate_draft_playbook(exception)
        
        # Create agent decision
        decision = self._create_decision(
            exception, actionability, resolved_plan, suggested_draft_playbook
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
        self, exception: ExceptionRecord, playbook_id: str
    ) -> list[dict[str, Any]]:
        """
        Resolve an approved playbook into structured action plan.
        
        Args:
            exception: ExceptionRecord
            playbook_id: Playbook identifier (exception type for MVP)
            
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
        
        return await self._resolve_playbook_steps(exception, playbook)

    async def _resolve_playbook_steps(
        self, exception: ExceptionRecord, playbook: Playbook
    ) -> list[dict[str, Any]]:
        """
        Resolve playbook steps into structured action plan.
        
        Optionally executes tools if conditions are met:
        - policy approved (actionability == "ACTIONABLE_APPROVED_PROCESS")
        - not CRITICAL severity
        - humanApprovalRequired == false
        
        Args:
            exception: ExceptionRecord
            playbook: Playbook to resolve
            
        Returns:
            List of structured actions with validated tool references and execution results
        """
        resolved_plan = []
        
        # Determine if tools should be executed (not just planned)
        should_execute = self._should_execute_tools(exception)
        
        for step_idx, step in enumerate(playbook.steps):
            # Extract tool name from step action
            tool_name = self._extract_tool_name_from_step(step)
            
            # Validate tool exists in domain pack
            if tool_name:
                if tool_name not in self.domain_pack.tools:
                    raise ResolutionAgentError(
                        f"Tool '{tool_name}' referenced in playbook step {step_idx + 1} "
                        f"not found in domain pack. Valid tools: {sorted(self.domain_pack.tools.keys())}"
                    )
                
                # Validate tool is allow-listed for tenant
                if not self.tool_registry.is_allowed(exception.tenant_id, tool_name):
                    raise ResolutionAgentError(
                        f"Tool '{tool_name}' referenced in playbook step {step_idx + 1} "
                        f"is not allow-listed for tenant {exception.tenant_id}"
                    )
                
                # Get tool definition
                tool_def = self.domain_pack.tools[tool_name]
                
                # Build structured action
                action = {
                    "stepNumber": step_idx + 1,
                    "action": step.action,
                    "toolName": tool_name,
                    "toolDescription": tool_def.description,
                    "parameters": step.parameters or {},
                    "endpoint": tool_def.endpoint,
                    "validated": True,
                    "executed": False,
                }
                
                # Optionally execute tool if conditions are met
                if should_execute and self.tool_invoker and self.tenant_policy:
                    try:
                        # Execute tool (default to dry_run=True for MVP)
                        dry_run = True  # MVP default: always dry run
                        result = await self.tool_invoker.invoke(
                            tool_name=tool_name,
                            args=step.parameters or {},
                            tenant_policy=self.tenant_policy,
                            domain_pack=self.domain_pack,
                            tenant_id=exception.tenant_id,
                            dry_run=dry_run,
                        )
                        action["executed"] = True
                        action["executionResult"] = result
                        action["dryRun"] = dry_run
                    except ToolInvocationError as e:
                        action["executionError"] = str(e)
                        if self.audit_logger:
                            self.audit_logger.log_decision(
                                f"ResolutionAgent - Tool execution failed: {tool_name}",
                                {"error": str(e), "step": step_idx + 1},
                                tenant_id=exception.tenant_id,
                            )
            else:
                # Step doesn't reference a tool (e.g., conditional logic, notification)
                action = {
                    "stepNumber": step_idx + 1,
                    "action": step.action,
                    "toolName": None,
                    "parameters": step.parameters or {},
                    "validated": True,
                }
            
            resolved_plan.append(action)
        
        return resolved_plan
    
    def _should_execute_tools(self, exception: ExceptionRecord) -> bool:
        """
        Determine if tools should be executed (not just planned).
        
        Conditions:
        - policy approved (checked in process method via actionability)
        - not CRITICAL severity
        - humanApprovalRequired == false
        
        Args:
            exception: ExceptionRecord
            
        Returns:
            True if tools should be executed, False otherwise
        """
        # Check severity: do not execute for CRITICAL
        if exception.severity == Severity.CRITICAL:
            return False
        
        # Check human approval requirement
        if self.tenant_policy:
            for rule in self.tenant_policy.human_approval_rules:
                if rule.severity == (exception.severity.value if exception.severity else "UNKNOWN"):
                    if rule.require_approval:
                        return False
        
        # All conditions met
        return True

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
