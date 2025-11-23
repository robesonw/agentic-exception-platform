"""
Orchestrator pipeline runner.
Executes the full agent pipeline for batch exception processing.
Matches specification from docs/01-architecture.md and docs/master_project_instruction_full.md
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

from src.agents.feedback import FeedbackAgent
from src.agents.intake import IntakeAgent, IntakeAgentError
from src.agents.policy import PolicyAgent, PolicyAgentError
from src.agents.resolution import ResolutionAgent, ResolutionAgentError
from src.agents.triage import TriageAgent, TriageAgentError
from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus
from src.models.tenant_policy import TenantPolicyPack
from src.observability.metrics import MetricsCollector
from src.orchestrator.store import get_exception_store
from src.tools.registry import ToolRegistry


class PipelineRunnerError(Exception):
    """Raised when pipeline runner operations fail."""

    pass


async def run_pipeline(
    domain_pack: DomainPack,
    tenant_policy: TenantPolicyPack,
    exceptions_batch: list[dict[str, Any]],
    metrics_collector: MetricsCollector | None = None,
    exception_store: Any = None,
) -> dict[str, Any]:
    """
    Run the full agent pipeline for a batch of exceptions.
    
    Executes agents in strict order per exception:
    IntakeAgent -> TriageAgent -> PolicyAgent -> ResolutionAgent -> FeedbackAgent
    
    Args:
        domain_pack: Domain Pack for the tenant
        tenant_policy: Tenant Policy Pack for the tenant
        exceptions_batch: List of raw exception dictionaries
        
    Returns:
        Dictionary with format:
        {
            "tenantId": str,
            "runId": str,
            "results": [
                {
                    "exceptionId": str,
                    "status": str,
                    "stages": {
                        "intake": AgentDecision,
                        "triage": AgentDecision,
                        "policy": AgentDecision,
                        "resolution": AgentDecision,
                        "feedback": AgentDecision,
                    },
                    "exception": ExceptionRecord,
                    "evidence": list[str],
                },
                ...
            ]
        }
    """
    # Generate run ID
    run_id = str(uuid.uuid4())
    tenant_id = tenant_policy.tenant_id
    
    # Initialize audit logger for this run
    audit_logger = AuditLogger(run_id=run_id, tenant_id=tenant_id)
    
    # Initialize tool registry
    tool_registry = ToolRegistry()
    tool_registry.register_domain_pack(tenant_id, domain_pack)
    tool_registry.register_policy_pack(tenant_id, tenant_policy)
    
    # Initialize agents
    intake_agent = IntakeAgent(domain_pack=domain_pack, audit_logger=audit_logger)
    triage_agent = TriageAgent(domain_pack=domain_pack, audit_logger=audit_logger)
    policy_agent = PolicyAgent(
        domain_pack=domain_pack, tenant_policy=tenant_policy, audit_logger=audit_logger
    )
    # Create tool invoker (optional, for tool execution)
    from src.tools.invoker import ToolInvoker
    
    tool_invoker = ToolInvoker(tool_registry=tool_registry, audit_logger=audit_logger)
    
    resolution_agent = ResolutionAgent(
        domain_pack=domain_pack,
        tool_registry=tool_registry,
        audit_logger=audit_logger,
        tool_invoker=tool_invoker,
        tenant_policy=tenant_policy,
    )
    feedback_agent = FeedbackAgent(audit_logger=audit_logger)
    
    # Process each exception through the pipeline
    results = []
    for raw_exception in exceptions_batch:
        result = await _process_exception(
            raw_exception=raw_exception,
            tenant_id=tenant_id,
            intake_agent=intake_agent,
            triage_agent=triage_agent,
            policy_agent=policy_agent,
            resolution_agent=resolution_agent,
            feedback_agent=feedback_agent,
            audit_logger=audit_logger,
        )
        results.append(result)
    
    # Close audit logger
    audit_logger.close()
    
    # Record metrics if collector provided
    if metrics_collector:
        metrics_collector.record_pipeline_run(tenant_id, results)
    
    # Store exceptions in exception store
    if exception_store is None:
        exception_store = get_exception_store()
    
    # Store each exception with its pipeline result
    for result in results:
        exception_id = result.get("exceptionId")
        if exception_id:
            # Extract ExceptionRecord from result if available
            exception_data = result.get("exception")
            if exception_data and isinstance(exception_data, dict):
                try:
                    exception = ExceptionRecord.model_validate(exception_data)
                    exception_store.store_exception(exception, result)
                except Exception as e:
                    logger.warning(f"Failed to store exception {exception_id}: {e}")
    
    # Return final output
    return {
        "tenantId": tenant_id,
        "runId": run_id,
        "results": results,
    }


async def _process_exception(
    raw_exception: dict[str, Any],
    tenant_id: str,
    intake_agent: IntakeAgent,
    triage_agent: TriageAgent,
    policy_agent: PolicyAgent,
    resolution_agent: ResolutionAgent,
    feedback_agent: FeedbackAgent,
    audit_logger: AuditLogger,
) -> dict[str, Any]:
    """
    Process a single exception through the full agent pipeline.
    
    Args:
        raw_exception: Raw exception dictionary
        tenant_id: Tenant identifier
        intake_agent: IntakeAgent instance
        triage_agent: TriageAgent instance
        policy_agent: PolicyAgent instance
        resolution_agent: ResolutionAgent instance
        feedback_agent: FeedbackAgent instance
        audit_logger: AuditLogger instance
        
    Returns:
        Dictionary with exception processing result
    """
    # Initialize per-exception context
    context: dict[str, Any] = {
        "stages": {},
        "evidence": [],
        "errors": [],
    }
    
    exception: ExceptionRecord | None = None
    stages: dict[str, Any] = {}
    
    # Stage 1: IntakeAgent
    try:
        # IntakeAgent.process returns tuple[ExceptionRecord, AgentDecision]
        normalized, intake_decision = await intake_agent.process(
            raw_exception=raw_exception,
            tenant_id=tenant_id,
        )
        exception = normalized
        stages["intake"] = intake_decision.model_dump(by_alias=True)
        context["stages"]["intake"] = intake_decision
        context["evidence"].extend(intake_decision.evidence)
        
        # Log audit entry
        audit_logger.log_decision("intake", intake_decision.model_dump(), tenant_id)
    except (IntakeAgentError, Exception) as e:
        error_msg = f"IntakeAgent failed: {str(e)}"
        context["errors"].append(error_msg)
        context["evidence"].append(error_msg)
        stages["intake"] = {"error": error_msg}
        
        # Create exception record with minimal data for error handling
        exception = ExceptionRecord(
            exceptionId=str(uuid.uuid4()),
            tenantId=tenant_id,
            sourceSystem=raw_exception.get("sourceSystem", "UNKNOWN"),
            timestamp=datetime.now(timezone.utc),
            rawPayload=raw_exception,
            resolutionStatus=ResolutionStatus.ESCALATED,
        )
    
    # Stage 2: TriageAgent (only if intake succeeded)
    if exception and exception.resolution_status != ResolutionStatus.ESCALATED:
        try:
            triage_decision = await triage_agent.process(exception, context)
            stages["triage"] = triage_decision.model_dump(by_alias=True)
            context["stages"]["triage"] = triage_decision
            context["evidence"].extend(triage_decision.evidence)
            
            # Add confidence to context for policy agent
            context["confidence"] = triage_decision.confidence
            
            # Log audit entry
            audit_logger.log_decision("triage", triage_decision.model_dump(), tenant_id)
        except (TriageAgentError, Exception) as e:
            error_msg = f"TriageAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["triage"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
    
    # Stage 3: PolicyAgent (only if previous stages succeeded)
    if exception and exception.resolution_status != ResolutionStatus.ESCALATED:
        try:
            policy_decision = await policy_agent.process(exception, context)
            stages["policy"] = policy_decision.model_dump(by_alias=True)
            context["stages"]["policy"] = policy_decision
            context["evidence"].extend(policy_decision.evidence)
            
            # Extract actionability and selectedPlaybookId from evidence
            for evidence in policy_decision.evidence:
                if "Actionability:" in evidence:
                    context["actionability"] = evidence.split("Actionability:")[1].strip()
                if "selectedPlaybookId:" in evidence:
                    playbook_id = evidence.split("selectedPlaybookId:")[1].strip()
                    if playbook_id != "None":
                        context["selectedPlaybookId"] = playbook_id
            
            # Log audit entry
            audit_logger.log_decision("policy", policy_decision.model_dump(), tenant_id)
        except (PolicyAgentError, Exception) as e:
            error_msg = f"PolicyAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["policy"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
    
    # Stage 4: ResolutionAgent (only if previous stages succeeded)
    if exception and exception.resolution_status != ResolutionStatus.ESCALATED:
        try:
            # Add resolved plan to context if available
            if "resolvedPlan" not in context:
                context["resolvedPlan"] = None
            
            resolution_decision = await resolution_agent.process(exception, context)
            stages["resolution"] = resolution_decision.model_dump(by_alias=True)
            context["stages"]["resolution"] = resolution_decision
            context["evidence"].extend(resolution_decision.evidence)
            
            # Extract resolved plan from evidence if available
            for evidence in resolution_decision.evidence:
                if "resolvedPlan:" in evidence:
                    # Try to extract plan details (for MVP, we'll store in context)
                    context["resolvedPlan"] = "available"
            
            # Log audit entry
            audit_logger.log_decision("resolution", resolution_decision.model_dump(), tenant_id)
        except (ResolutionAgentError, Exception) as e:
            error_msg = f"ResolutionAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["resolution"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
    
    # Stage 5: FeedbackAgent (always runs, even if previous stages failed)
    if exception:
        try:
            feedback_decision = await feedback_agent.process(exception, context)
            stages["feedback"] = feedback_decision.model_dump(by_alias=True)
            context["stages"]["feedback"] = feedback_decision
            context["evidence"].extend(feedback_decision.evidence)
            
            # Log audit entry
            audit_logger.log_decision("feedback", feedback_decision.model_dump(), tenant_id)
        except Exception as e:
            error_msg = f"FeedbackAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["feedback"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
    
    # Determine final status
    if exception:
        if exception.resolution_status == ResolutionStatus.ESCALATED:
            status = "ESCALATED"
        elif exception.resolution_status == ResolutionStatus.IN_PROGRESS:
            status = "IN_PROGRESS"
        elif exception.resolution_status == ResolutionStatus.RESOLVED:
            status = "RESOLVED"
        else:
            status = "OPEN"
    else:
        status = "FAILED"
    
    # Build result
    result: dict[str, Any] = {
        "exceptionId": exception.exception_id if exception else "unknown",
        "status": status,
        "stages": stages,
        "evidence": context["evidence"],
    }
    
    if exception:
        result["exception"] = exception.model_dump(by_alias=True)
    
    if context["errors"]:
        result["errors"] = context["errors"]
    
    return result

