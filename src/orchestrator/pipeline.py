"""
Agent pipeline orchestrator for Phase 1.

Implements the basic Intake → Triage → Policy → Resolution → Feedback pipeline
as specified in docs/01-architecture.md and docs/06-mvp-plan.md Phase 1.
"""

import logging
from typing import Any, Dict, Optional

from src.agents.feedback import FeedbackAgent
from src.agents.intake import IntakeAgent
from src.agents.policy import PolicyAgent
from src.agents.resolution import ResolutionAgent
from src.agents.triage import TriageAgent
from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus
from src.models.tenant_policy import TenantPolicyPack
from src.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class AgentOrchestratorError(Exception):
    """Raised when orchestrator operations fail."""
    pass


class AgentOrchestrator:
    """
    Orchestrates the agent pipeline: Intake → Triage → Policy → Resolution → Feedback.

    Phase 1 MVP Implementation:
    - Sequential execution of agents
    - Context passing between agents
    - Basic error handling
    - Audit trail generation via AuditLogger
    - Tenant isolation enforcement

    Follows specification from:
    - docs/01-architecture.md (Agent Orchestration Workflow)
    - docs/06-mvp-plan.md (Phase 1: MVP Agent)
    - PHASE1_STABILIZATION_PLAN.md
    """

    def __init__(
        self,
        domain_pack: DomainPack,
        tenant_policy: TenantPolicyPack,
        audit_logger: Optional[AuditLogger] = None,
        tool_registry: Optional[ToolRegistry] = None,
    ):
        """
        Initialize orchestrator with agent instances and configuration.

        Args:
            domain_pack: Domain Pack for the tenant's domain
            tenant_policy: Tenant Policy Pack for the tenant
            audit_logger: Optional AuditLogger for audit trail
            tool_registry: Optional ToolRegistry (creates new instance if not provided)
        """
        self.domain_pack = domain_pack
        self.tenant_policy = tenant_policy
        self.audit_logger = audit_logger

        # Create or use provided tool registry
        self.tool_registry = tool_registry or ToolRegistry()

        # Register tools from domain pack into registry
        if domain_pack.tools:
            for tool_name, tool_def in domain_pack.tools.items():
                # Tool registry registration happens here if needed
                # For MVP, we just keep the registry for validation
                pass

        # Initialize agents with domain pack and tenant policy
        self.intake_agent = IntakeAgent(domain_pack=domain_pack, audit_logger=audit_logger)
        self.triage_agent = TriageAgent(domain_pack=domain_pack, audit_logger=audit_logger)
        self.policy_agent = PolicyAgent(
            domain_pack=domain_pack,
            tenant_policy=tenant_policy,
            audit_logger=audit_logger,
        )
        self.resolution_agent = ResolutionAgent(
            domain_pack=domain_pack,
            tool_registry=self.tool_registry,
            tenant_policy=tenant_policy,
            audit_logger=audit_logger,
        )
        self.feedback_agent = FeedbackAgent(audit_logger=audit_logger)

    async def process_exception(
        self, raw_exception: Dict[str, Any] | ExceptionRecord
    ) -> Dict[str, Any]:
        """
        Process an exception through the full agent pipeline.

        Pipeline: Intake → Triage → Policy → Resolution → Feedback

        Args:
            raw_exception: Raw exception dict or ExceptionRecord to process

        Returns:
            Dictionary containing:
            - exception: Final ExceptionRecord with updates
            - context: Full context with all agent decisions
            - decisions: List of all agent decisions in order
            - events: List of audit events generated

        Raises:
            AgentOrchestratorError: If pipeline execution fails
        """
        logger.info("Starting agent pipeline for exception processing")

        # Initialize context for passing between agents
        context: Dict[str, Any] = {
            "prior_outputs": {},
            "events": [],
        }
        decisions: list[AgentDecision] = []

        try:
            # Stage 1: Intake - Normalize exception
            logger.info("Stage 1: IntakeAgent - Normalizing exception")
            exception, intake_decision = await self.intake_agent.process(raw_exception)
            context["prior_outputs"]["intake"] = intake_decision
            decisions.append(intake_decision)
            context["events"].append({"stage": "intake", "decision": intake_decision.model_dump()})

            # Check if we should proceed (accept both "triage" and "ProceedToTriage")
            if intake_decision.next_step.lower() not in ["triage", "proceedtotriage"]:
                logger.warning(f"IntakeAgent did not proceed to triage: {intake_decision.next_step}")
                return self._build_response(exception, context, decisions)

            # Stage 2: Triage - Classify and assign severity
            logger.info("Stage 2: TriageAgent - Classifying and triaging exception")
            triage_decision = await self.triage_agent.process(exception, context)
            context["prior_outputs"]["triage"] = triage_decision
            decisions.append(triage_decision)
            context["events"].append({"stage": "triage", "decision": triage_decision.model_dump()})

            # Update exception with triage results (severity, classification)
            # Note: Agents don't modify the exception directly in MVP - orchestrator does

            # Check if we should proceed (accept variations of "policy")
            if "policy" not in triage_decision.next_step.lower():
                logger.warning(f"TriageAgent did not proceed to policy: {triage_decision.next_step}")
                return self._build_response(exception, context, decisions)

            # Stage 3: Policy - Evaluate policies and approve actions
            logger.info("Stage 3: PolicyAgent - Evaluating policies")
            policy_decision = await self.policy_agent.process(exception, context)
            context["prior_outputs"]["policy"] = policy_decision
            decisions.append(policy_decision)
            context["events"].append({"stage": "policy", "decision": policy_decision.model_dump()})

            # Check if we should proceed or escalate
            if policy_decision.next_step == "ESCALATE":
                logger.info("PolicyAgent escalated - human approval required")
                exception.resolution_status = ResolutionStatus.ESCALATED
                return self._build_response(exception, context, decisions)

            if "resolution" not in policy_decision.next_step.lower():
                logger.warning(f"PolicyAgent did not proceed to resolution: {policy_decision.next_step}")
                return self._build_response(exception, context, decisions)

            # Stage 4: Resolution - Create resolution plan
            logger.info("Stage 4: ResolutionAgent - Creating resolution plan")
            resolution_decision = await self.resolution_agent.process(exception, context)
            context["prior_outputs"]["resolution"] = resolution_decision
            decisions.append(resolution_decision)
            context["events"].append({"stage": "resolution", "decision": resolution_decision.model_dump()})

            # Check if we should proceed or escalate
            if resolution_decision.next_step == "ESCALATE":
                logger.info("ResolutionAgent escalated - resolution failed")
                exception.resolution_status = ResolutionStatus.ESCALATED
                return self._build_response(exception, context, decisions)

            # Stage 5: Feedback - Capture outcomes and metrics
            logger.info("Stage 5: FeedbackAgent - Capturing feedback")
            feedback_decision = await self.feedback_agent.process(exception, context)
            context["prior_outputs"]["feedback"] = feedback_decision
            decisions.append(feedback_decision)
            context["events"].append({"stage": "feedback", "decision": feedback_decision.model_dump()})

            # Mark exception as resolved (or in progress depending on resolution)
            if exception.resolution_status == ResolutionStatus.OPEN:
                exception.resolution_status = ResolutionStatus.IN_PROGRESS

            logger.info("Agent pipeline completed successfully")
            return self._build_response(exception, context, decisions)

        except Exception as e:
            logger.error(f"Agent pipeline failed: {e}", exc_info=True)
            if self.audit_logger:
                self.audit_logger.log_error(
                    f"Pipeline execution failed: {str(e)}",
                    exception.tenant_id if isinstance(raw_exception, ExceptionRecord) else None,
                )
            raise AgentOrchestratorError(f"Pipeline execution failed: {str(e)}") from e

    def _build_response(
        self,
        exception: ExceptionRecord,
        context: Dict[str, Any],
        decisions: list[AgentDecision],
    ) -> Dict[str, Any]:
        """
        Build the orchestrator response.

        Args:
            exception: Final exception state
            context: Full context
            decisions: List of agent decisions

        Returns:
            Dictionary with exception, context, decisions, and events
        """
        return {
            "exception": exception,
            "context": context,
            "decisions": decisions,
            "events": context.get("events", []),
        }

