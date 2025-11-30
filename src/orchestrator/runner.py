"""
Orchestrator pipeline runner with advanced multi-agent orchestration.

Phase 2 enhancements:
- Parallel execution across exceptions using asyncio.gather
- Timeout support per stage
- State snapshot persistence
- Orchestration hooks (before_stage, after_stage, on_failure)
- Branching logic (PENDING_APPROVAL stops pipeline, non-actionable skips ResolutionAgent)
- Maintain deterministic order within each exception

Matches specification from docs/01-architecture.md and phase2-mvp-issues.md Issue 33.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

from src.agents.feedback import FeedbackAgent
from src.agents.intake import IntakeAgent, IntakeAgentError
from src.agents.policy import PolicyAgent, PolicyAgentError
from src.agents.resolution import ResolutionAgent, ResolutionAgentError
from src.agents.supervisor import SupervisorAgent, SupervisorAgentError
from src.agents.triage import TriageAgent, TriageAgentError
from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus
from src.models.tenant_policy import TenantPolicyPack
from src.notify.service import NotificationService
from src.observability.metrics import MetricsCollector
from src.orchestrator.store import get_exception_store
from src.tools.registry import ToolRegistry


class PipelineRunnerError(Exception):
    """Raised when pipeline runner operations fail."""

    pass


# Default timeout per stage (in seconds)
DEFAULT_STAGE_TIMEOUT = 300.0  # 5 minutes


class OrchestrationHooks:
    """
    Orchestration hooks for pipeline lifecycle events.
    
    Phase 2: Allows external code to observe and react to pipeline events.
    """

    def __init__(self):
        """Initialize orchestration hooks."""
        self.before_stage: Optional[Callable[[str, dict[str, Any]], None]] = None
        self.after_stage: Optional[Callable[[str, AgentDecision], None]] = None
        self.on_failure: Optional[Callable[[str, Exception], None]] = None

    def set_before_stage(self, hook: Callable[[str, dict[str, Any]], None]) -> None:
        """Set hook called before each stage."""
        self.before_stage = hook

    def set_after_stage(self, hook: Callable[[str, AgentDecision], None]) -> None:
        """Set hook called after each stage."""
        self.after_stage = hook

    def set_on_failure(self, hook: Callable[[str, Exception], None]) -> None:
        """Set hook called on stage failure."""
        self.on_failure = hook


async def run_pipeline(
    domain_pack: DomainPack,
    tenant_policy: TenantPolicyPack,
    exceptions_batch: list[dict[str, Any]],
    metrics_collector: MetricsCollector | None = None,
    exception_store: Any = None,
    stage_timeouts: Optional[dict[str, float]] = None,
    hooks: Optional[OrchestrationHooks] = None,
    enable_parallel: bool = True,
    snapshot_dir: Optional[str] = None,
    notification_service: Optional[NotificationService] = None,
) -> dict[str, Any]:
    """
    Run the full agent pipeline for a batch of exceptions.
    
    Phase 2: Supports parallel execution, timeouts, hooks, and state snapshots.
    
    Executes agents in strict order per exception:
    IntakeAgent -> TriageAgent -> PolicyAgent -> ResolutionAgent -> FeedbackAgent
    
    Args:
        domain_pack: Domain Pack for the tenant
        tenant_policy: Tenant Policy Pack for the tenant
        exceptions_batch: List of raw exception dictionaries
        metrics_collector: Optional metrics collector
        exception_store: Optional exception store
        stage_timeouts: Optional dict mapping stage names to timeout seconds
        hooks: Optional orchestration hooks
        enable_parallel: If True, process exceptions in parallel (default: True)
        snapshot_dir: Optional directory for state snapshots
        notification_service: Optional notification service for alerts
        
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
    
    # Initialize hooks if not provided
    if hooks is None:
        hooks = OrchestrationHooks()
    
    # Set default timeouts if not provided
    if stage_timeouts is None:
        stage_timeouts = {}
    default_timeouts = {
        "intake": DEFAULT_STAGE_TIMEOUT,
        "triage": DEFAULT_STAGE_TIMEOUT,
        "policy": DEFAULT_STAGE_TIMEOUT,
        "supervisor_post_policy": DEFAULT_STAGE_TIMEOUT,
        "resolution": DEFAULT_STAGE_TIMEOUT,
        "supervisor_post_resolution": DEFAULT_STAGE_TIMEOUT,
        "feedback": DEFAULT_STAGE_TIMEOUT,
    }
    stage_timeouts = {**default_timeouts, **stage_timeouts}
    
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
    # Phase 2: Initialize PolicyLearning for FeedbackAgent
    from src.learning.policy_learning import PolicyLearning
    
    policy_learning = PolicyLearning()
    
    feedback_agent = FeedbackAgent(audit_logger=audit_logger, policy_learning=policy_learning)
    
    # Phase 2: Initialize SupervisorAgent (optional)
    supervisor_agent = SupervisorAgent(
        domain_pack=domain_pack,
        tenant_policy=tenant_policy,
        audit_logger=audit_logger,
    )
    
    # Setup snapshot directory
    if snapshot_dir is None:
        snapshot_dir = f"./runtime/snapshots/{tenant_id}/{run_id}"
    Path(snapshot_dir).mkdir(parents=True, exist_ok=True)
    
    # Process exceptions (parallel or sequential)
    if enable_parallel and len(exceptions_batch) > 1:
        # Process exceptions in parallel
        tasks = [
            _process_exception(
                raw_exception=raw_exception,
                tenant_id=tenant_id,
                intake_agent=intake_agent,
                triage_agent=triage_agent,
                policy_agent=policy_agent,
                resolution_agent=resolution_agent,
                feedback_agent=feedback_agent,
                supervisor_agent=supervisor_agent,
                audit_logger=audit_logger,
                stage_timeouts=stage_timeouts,
                hooks=hooks,
                snapshot_dir=snapshot_dir,
                exception_index=idx,
            )
            for idx, raw_exception in enumerate(exceptions_batch)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Handle exceptions from gather
        processed_results = []
        for idx, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception {idx} failed with error: {result}")
                processed_results.append({
                    "exceptionId": f"unknown_{idx}",
                    "status": "FAILED",
                    "stages": {},
                    "evidence": [f"Pipeline error: {str(result)}"],
                    "errors": [str(result)],
                })
            else:
                processed_results.append(result)
        results = processed_results
    else:
        # Process exceptions sequentially (maintains order)
        results = []
        for idx, raw_exception in enumerate(exceptions_batch):
            result = await _process_exception(
                raw_exception=raw_exception,
                tenant_id=tenant_id,
                intake_agent=intake_agent,
                triage_agent=triage_agent,
                policy_agent=policy_agent,
                resolution_agent=resolution_agent,
                feedback_agent=feedback_agent,
                supervisor_agent=supervisor_agent,
                audit_logger=audit_logger,
                stage_timeouts=stage_timeouts,
                hooks=hooks,
                snapshot_dir=snapshot_dir,
                exception_index=idx,
                tenant_policy=tenant_policy,
                notification_service=notification_service,
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
    supervisor_agent: SupervisorAgent,
    audit_logger: AuditLogger,
    stage_timeouts: dict[str, float],
    hooks: OrchestrationHooks,
    snapshot_dir: str,
    exception_index: int = 0,
    tenant_policy: Optional[TenantPolicyPack] = None,
    notification_service: Optional[NotificationService] = None,
) -> dict[str, Any]:
    """
    Process a single exception through the full agent pipeline.
    
    Phase 2: Supports timeouts, hooks, branching, and state snapshots.
    
    Args:
        raw_exception: Raw exception dictionary
        tenant_id: Tenant identifier
        intake_agent: IntakeAgent instance
        triage_agent: TriageAgent instance
        policy_agent: PolicyAgent instance
        resolution_agent: ResolutionAgent instance
        feedback_agent: FeedbackAgent instance
        audit_logger: AuditLogger instance
        stage_timeouts: Dict mapping stage names to timeout seconds
        hooks: OrchestrationHooks instance
        snapshot_dir: Directory for state snapshots
        exception_index: Index of exception in batch (for snapshots)
        tenant_policy: Tenant policy pack (for notification routing)
        notification_service: Notification service (for alerts)
        
    Returns:
        Dictionary with exception processing result
    """
    # Initialize per-exception context
    context: dict[str, Any] = {
        "stages": {},
        "evidence": [],
        "errors": [],
        "prior_outputs": {},
    }
    
    exception: ExceptionRecord | None = None
    stages: dict[str, Any] = {}
    
    # Helper function to save state snapshot
    def save_snapshot(stage_name: str) -> None:
        """Save state snapshot after stage."""
        try:
            snapshot_path = Path(snapshot_dir) / f"exception_{exception_index}_{stage_name}.json"
            snapshot_data = {
                "exception": exception.model_dump(by_alias=True) if exception else None,
                "context": {
                    "stages": {k: v.model_dump(by_alias=True) if hasattr(v, "model_dump") else v
                              for k, v in context["stages"].items()},
                    "evidence": context["evidence"],
                    "errors": context["errors"],
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            with open(snapshot_path, "w") as f:
                json.dump(snapshot_data, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Failed to save snapshot for {stage_name}: {e}")
    
    # Helper function to run stage with timeout
    async def run_stage_with_timeout(
        stage_name: str,
        stage_func: Callable,
        *args,
        **kwargs,
    ) -> Any:
        """Run a stage with timeout and hooks."""
        # Call before_stage hook
        if hooks.before_stage:
            try:
                hooks.before_stage(stage_name, context)
            except Exception as e:
                logger.warning(f"before_stage hook failed for {stage_name}: {e}")
        
        # Get timeout for this stage
        timeout = stage_timeouts.get(stage_name, DEFAULT_STAGE_TIMEOUT)
        
        try:
            # Run stage with timeout
            result = await asyncio.wait_for(
                stage_func(*args, **kwargs),
                timeout=timeout,
            )
            
            # Call after_stage hook
            # IntakeAgent returns tuple (ExceptionRecord, AgentDecision), extract decision
            decision = result
            if isinstance(result, tuple) and len(result) == 2:
                # Assume second element is AgentDecision
                if isinstance(result[1], AgentDecision):
                    decision = result[1]
            
            if hooks.after_stage and isinstance(decision, AgentDecision):
                try:
                    hooks.after_stage(stage_name, decision)
                except Exception as e:
                    logger.warning(f"after_stage hook failed for {stage_name}: {e}")
            
            return result
        except asyncio.TimeoutError:
            error = TimeoutError(f"Stage {stage_name} timed out after {timeout}s")
            if hooks.on_failure:
                try:
                    hooks.on_failure(stage_name, error)
                except Exception as e:
                    logger.warning(f"on_failure hook failed for {stage_name}: {e}")
            raise error
        except Exception as e:
            if hooks.on_failure:
                try:
                    hooks.on_failure(stage_name, e)
                except Exception as hook_error:
                    logger.warning(f"on_failure hook failed for {stage_name}: {hook_error}")
            raise
    
    # Stage 1: IntakeAgent
    try:
        intake_decision = await run_stage_with_timeout(
            "intake",
            intake_agent.process,
            raw_exception=raw_exception,
            tenant_id=tenant_id,
        )
        # IntakeAgent.process returns tuple[ExceptionRecord, AgentDecision]
        if isinstance(intake_decision, tuple):
            exception, intake_decision = intake_decision
        else:
            # Fallback if API changed
            exception = ExceptionRecord.model_validate(raw_exception)
        
        stages["intake"] = intake_decision.model_dump(by_alias=True)
        context["stages"]["intake"] = intake_decision
        context["prior_outputs"]["intake"] = intake_decision
        context["evidence"].extend(intake_decision.evidence)
        
        # Log audit entry
        audit_logger.log_decision("intake", intake_decision.model_dump(), tenant_id)
        save_snapshot("intake")
        
        # Phase 3: Emit stage completed event for streaming
        try:
            from src.streaming.decision_stream import emit_stage_completed
            emit_stage_completed(
                exception_id=exception.exception_id,
                tenant_id=tenant_id,
                stage_name="intake",
                decision=intake_decision,
            )
        except Exception as e:
            logger.warning(f"Failed to emit intake stage event: {e}")
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
            triage_decision = await run_stage_with_timeout(
                "triage",
                triage_agent.process,
                exception,
                context,
            )
            stages["triage"] = triage_decision.model_dump(by_alias=True)
            context["stages"]["triage"] = triage_decision
            context["prior_outputs"]["triage"] = triage_decision
            context["evidence"].extend(triage_decision.evidence)
            
            # Add confidence to context for policy agent
            context["confidence"] = triage_decision.confidence
            
            # Log audit entry
            audit_logger.log_decision("triage", triage_decision.model_dump(), tenant_id)
            save_snapshot("triage")
            
            # Phase 3: Emit stage completed event for streaming
            try:
                from src.streaming.decision_stream import emit_stage_completed
                emit_stage_completed(
                    exception_id=exception.exception_id,
                    tenant_id=tenant_id,
                    stage_name="triage",
                    decision=triage_decision,
                )
            except Exception as e:
                logger.warning(f"Failed to emit triage stage event: {e}")
        except (TriageAgentError, Exception) as e:
            error_msg = f"TriageAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["triage"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
    
    # Stage 3: PolicyAgent (only if previous stages succeeded)
    if exception and exception.resolution_status != ResolutionStatus.ESCALATED:
        try:
            policy_decision = await run_stage_with_timeout(
                "policy",
                policy_agent.process,
                exception,
                context,
            )
            stages["policy"] = policy_decision.model_dump(by_alias=True)
            context["stages"]["policy"] = policy_decision
            context["prior_outputs"]["policy"] = policy_decision
            context["evidence"].extend(policy_decision.evidence)
            
            # Extract actionability and selectedPlaybookId from evidence
            for evidence in policy_decision.evidence:
                if "Actionability:" in evidence:
                    context["actionability"] = evidence.split("Actionability:")[1].strip()
                if "selectedPlaybookId:" in evidence:
                    playbook_id = evidence.split("selectedPlaybookId:")[1].strip()
                    if playbook_id != "None":
                        context["selectedPlaybookId"] = playbook_id
            
            # Extract humanApprovalRequired from evidence
            for evidence in policy_decision.evidence:
                if "humanApprovalRequired:" in evidence:
                    value = evidence.split("humanApprovalRequired:")[1].strip().lower()
                    context["humanApprovalRequired"] = value == "true"
            
            # Log audit entry
            audit_logger.log_decision("policy", policy_decision.model_dump(), tenant_id)
            save_snapshot("policy")
            
            # Phase 3: Emit stage completed event for streaming
            try:
                from src.streaming.decision_stream import emit_stage_completed
                emit_stage_completed(
                    exception_id=exception.exception_id,
                    tenant_id=tenant_id,
                    stage_name="policy",
                    decision=policy_decision,
                )
            except Exception as e:
                logger.warning(f"Failed to emit policy stage event: {e}")
            
            # Phase 2: SupervisorAgent review (post-policy checkpoint)
            try:
                supervisor_decision = await run_stage_with_timeout(
                    "supervisor_post_policy",
                    supervisor_agent.review_post_policy,
                    exception,
                    policy_decision,
                    context,
                )
                # Append supervisor evidence to context
                context["evidence"].extend(supervisor_decision.evidence)
                context["stages"]["supervisor_post_policy"] = supervisor_decision
                context["prior_outputs"]["supervisor_post_policy"] = supervisor_decision
                
                # Phase 3: Emit supervisor stage completed event for streaming
                try:
                    from src.streaming.decision_stream import emit_stage_completed
                    emit_stage_completed(
                        exception_id=exception.exception_id,
                        tenant_id=tenant_id,
                        stage_name="supervisor_post_policy",
                        decision=supervisor_decision,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit supervisor_post_policy stage event: {e}")
                
                # Check if supervisor overrode nextStep to ESCALATE
                if supervisor_decision.next_step == "ESCALATE":
                    logger.warning(
                        f"SupervisorAgent escalated exception {exception.exception_id} "
                        f"after policy review"
                    )
                    exception.resolution_status = ResolutionStatus.ESCALATED
                    # Override policy decision nextStep
                    policy_decision.next_step = "ESCALATE"
            except (SupervisorAgentError, Exception) as e:
                logger.warning(f"SupervisorAgent review failed: {e}")
                # Continue with policy decision if supervisor fails
            
            # Phase 2: Branching - If PENDING_APPROVAL, stop pipeline
            if exception.resolution_status == ResolutionStatus.PENDING_APPROVAL:
                logger.info(f"Exception {exception.exception_id} requires approval, stopping pipeline")
                
                # Phase 2: Send notification for approval required
                if notification_service and tenant_policy:
                    _send_approval_notification(
                        notification_service=notification_service,
                        tenant_policy=tenant_policy,
                        exception=exception,
                        context=context,
                    )
                
                # Skip ResolutionAgent and FeedbackAgent, return early
                status = "PENDING_APPROVAL"
                result: dict[str, Any] = {
                    "exceptionId": exception.exception_id,
                    "status": status,
                    "stages": stages,
                    "evidence": context["evidence"],
                }
                result["exception"] = exception.model_dump(by_alias=True)
                if context["errors"]:
                    result["errors"] = context["errors"]
                return result
        except (PolicyAgentError, Exception) as e:
            error_msg = f"PolicyAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["policy"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
            
            # Phase 2: Send notification for escalation
            if notification_service and tenant_policy:
                _send_escalation_notification(
                    notification_service=notification_service,
                    tenant_policy=tenant_policy,
                    exception=exception,
                    context=context,
                    reason="PolicyAgent failed",
                )
    
    # Stage 4: ResolutionAgent (only if previous stages succeeded and actionable)
    # Phase 2: Branching - Skip ResolutionAgent if non-actionable
    actionability = context.get("actionability", "")
    if (
        exception
        and exception.resolution_status != ResolutionStatus.ESCALATED
        and exception.resolution_status != ResolutionStatus.PENDING_APPROVAL
        and actionability != "NON_ACTIONABLE_INFO_ONLY"
    ):
        try:
            # Add resolved plan to context if available
            if "resolvedPlan" not in context:
                context["resolvedPlan"] = None
            
            resolution_decision = await run_stage_with_timeout(
                "resolution",
                resolution_agent.process,
                exception,
                context,
            )
            stages["resolution"] = resolution_decision.model_dump(by_alias=True)
            context["stages"]["resolution"] = resolution_decision
            context["prior_outputs"]["resolution"] = resolution_decision
            context["evidence"].extend(resolution_decision.evidence)
            
            # Extract resolved plan from evidence if available
            for evidence in resolution_decision.evidence:
                if "resolvedPlan:" in evidence:
                    # Try to extract plan details (for MVP, we'll store in context)
                    context["resolvedPlan"] = "available"
            
            # Log audit entry
            audit_logger.log_decision("resolution", resolution_decision.model_dump(), tenant_id)
            save_snapshot("resolution")
            
            # Phase 3: Emit stage completed event for streaming
            try:
                from src.streaming.decision_stream import emit_stage_completed
                emit_stage_completed(
                    exception_id=exception.exception_id,
                    tenant_id=tenant_id,
                    stage_name="resolution",
                    decision=resolution_decision,
                )
            except Exception as e:
                logger.warning(f"Failed to emit resolution stage event: {e}")
            
            # Phase 2: SupervisorAgent review (post-resolution checkpoint)
            try:
                supervisor_decision = await run_stage_with_timeout(
                    "supervisor_post_resolution",
                    supervisor_agent.review_post_resolution,
                    exception,
                    resolution_decision,
                    context,
                )
                # Append supervisor evidence to context
                context["evidence"].extend(supervisor_decision.evidence)
                context["stages"]["supervisor_post_resolution"] = supervisor_decision
                context["prior_outputs"]["supervisor_post_resolution"] = supervisor_decision
                
                # Phase 3: Emit supervisor stage completed event for streaming
                try:
                    from src.streaming.decision_stream import emit_stage_completed
                    emit_stage_completed(
                        exception_id=exception.exception_id,
                        tenant_id=tenant_id,
                        stage_name="supervisor_post_resolution",
                        decision=supervisor_decision,
                    )
                except Exception as e:
                    logger.warning(f"Failed to emit supervisor_post_resolution stage event: {e}")
                
                # Check if supervisor overrode nextStep to ESCALATE
                if supervisor_decision.next_step == "ESCALATE":
                    logger.warning(
                        f"SupervisorAgent escalated exception {exception.exception_id} "
                        f"after resolution review"
                    )
                    exception.resolution_status = ResolutionStatus.ESCALATED
                    # Override resolution decision nextStep
                    resolution_decision.next_step = "ESCALATE"
                    
                    # Phase 2: Send notification for escalation
                    if notification_service and tenant_policy:
                        _send_escalation_notification(
                            notification_service=notification_service,
                            tenant_policy=tenant_policy,
                            exception=exception,
                            context=context,
                            reason="SupervisorAgent escalated after resolution review",
                        )
            except (SupervisorAgentError, Exception) as e:
                logger.warning(f"SupervisorAgent review failed: {e}")
                # Continue with resolution decision if supervisor fails
        except (ResolutionAgentError, Exception) as e:
            error_msg = f"ResolutionAgent failed: {str(e)}"
            context["errors"].append(error_msg)
            context["evidence"].append(error_msg)
            stages["resolution"] = {"error": error_msg}
            exception.resolution_status = ResolutionStatus.ESCALATED
            
            # Phase 2: Send notification for escalation
            if notification_service and tenant_policy:
                _send_escalation_notification(
                    notification_service=notification_service,
                    tenant_policy=tenant_policy,
                    exception=exception,
                    context=context,
                    reason="ResolutionAgent failed",
                )
    elif actionability == "NON_ACTIONABLE_INFO_ONLY":
        # Skip ResolutionAgent for non-actionable exceptions
        logger.info(f"Exception {exception.exception_id} is non-actionable, skipping ResolutionAgent")
        stages["resolution"] = {"skipped": "Non-actionable exception"}
    
    # Stage 5: FeedbackAgent (always runs, even if previous stages failed)
    if exception:
        try:
            feedback_decision = await run_stage_with_timeout(
                "feedback",
                feedback_agent.process,
                exception,
                context,
            )
            stages["feedback"] = feedback_decision.model_dump(by_alias=True)
            context["stages"]["feedback"] = feedback_decision
            context["prior_outputs"]["feedback"] = feedback_decision
            context["evidence"].extend(feedback_decision.evidence)
            
            # Log audit entry
            audit_logger.log_decision("feedback", feedback_decision.model_dump(), tenant_id)
            save_snapshot("feedback")
            
            # Phase 3: Emit stage completed event for streaming
            try:
                from src.streaming.decision_stream import emit_stage_completed
                emit_stage_completed(
                    exception_id=exception.exception_id,
                    tenant_id=tenant_id,
                    stage_name="feedback",
                    decision=feedback_decision,
                )
            except Exception as e:
                logger.warning(f"Failed to emit feedback stage event: {e}")
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
            # Phase 2: Send notification for escalation (if not already sent)
            if notification_service and tenant_policy:
                _send_escalation_notification(
                    notification_service=notification_service,
                    tenant_policy=tenant_policy,
                    exception=exception,
                    context=context,
                    reason="Exception escalated",
                )
        elif exception.resolution_status == ResolutionStatus.PENDING_APPROVAL:
            status = "PENDING_APPROVAL"  # Phase 2: Human approval required
        elif exception.resolution_status == ResolutionStatus.IN_PROGRESS:
            status = "IN_PROGRESS"
        elif exception.resolution_status == ResolutionStatus.RESOLVED:
            status = "RESOLVED"
            # Phase 2: Send notification for auto-resolution complete
            if notification_service and tenant_policy:
                # Check if this was auto-resolved (not requiring approval)
                was_auto_resolved = context.get("humanApprovalRequired", False) is False
                if was_auto_resolved:
                    _send_resolution_notification(
                        notification_service=notification_service,
                        tenant_policy=tenant_policy,
                        exception=exception,
                        context=context,
                    )
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


def _get_notification_group(
    exception: ExceptionRecord,
    tenant_policy: TenantPolicyPack,
    context: dict[str, Any],
) -> str:
    """
    Determine notification group for exception.
    
    For MVP, uses exception type or default group.
    In production, would use routingRules from tenant policy.
    
    Args:
        exception: Exception record
        tenant_policy: Tenant policy pack
        context: Processing context
        
    Returns:
        Group name for notification routing
    """
    # Try to extract group from context (if routing rules were applied)
    group = context.get("assignedGroup")
    if group:
        return group
    
    # Fallback: use exception type as group identifier
    if exception.exception_type:
        return exception.exception_type
    
    # Default group
    return "DefaultOps"


def _send_escalation_notification(
    notification_service: NotificationService,
    tenant_policy: TenantPolicyPack,
    exception: ExceptionRecord,
    context: dict[str, Any],
    reason: str,
) -> None:
    """
    Send notification for exception escalation.
    
    Args:
        notification_service: Notification service instance
        tenant_policy: Tenant policy pack
        exception: Exception record
        context: Processing context
        reason: Reason for escalation
    """
    if not tenant_policy.notification_policies:
        return
    
    try:
        group = _get_notification_group(exception, tenant_policy, context)
        subject = f"Exception Escalated: {exception.exception_id}"
        message = (
            f"Exception {exception.exception_id} has been escalated.\n\n"
            f"Type: {exception.exception_type or 'Unknown'}\n"
            f"Severity: {exception.severity.value if exception.severity else 'Unknown'}\n"
            f"Reason: {reason}\n"
            f"Timestamp: {exception.timestamp.isoformat() if exception.timestamp else 'Unknown'}"
        )
        
        # Build payload link (for UI)
        payload_link = f"/ui/exceptions/{exception.tenant_id}/{exception.exception_id}"
        
        # Convert notification policies to dict
        notif_policies_dict = tenant_policy.notification_policies.model_dump(by_alias=True)
        
        notification_service.send_notification(
            tenant_id=exception.tenant_id,
            group=group,
            subject=subject,
            message=message,
            payload_link=payload_link,
            notification_policies=notif_policies_dict,
        )
    except Exception as e:
        logger.warning(f"Failed to send escalation notification: {e}")


def _send_approval_notification(
    notification_service: NotificationService,
    tenant_policy: TenantPolicyPack,
    exception: ExceptionRecord,
    context: dict[str, Any],
) -> None:
    """
    Send notification for approval required.
    
    Args:
        notification_service: Notification service instance
        tenant_policy: Tenant policy pack
        exception: Exception record
        context: Processing context
    """
    if not tenant_policy.notification_policies:
        return
    
    try:
        group = _get_notification_group(exception, tenant_policy, context)
        subject = f"Approval Required: {exception.exception_id}"
        message = (
            f"Exception {exception.exception_id} requires human approval.\n\n"
            f"Type: {exception.exception_type or 'Unknown'}\n"
            f"Severity: {exception.severity.value if exception.severity else 'Unknown'}\n"
            f"Timestamp: {exception.timestamp.isoformat() if exception.timestamp else 'Unknown'}\n\n"
            f"Please review and approve or reject the resolution plan."
        )
        
        # Build payload link (for approval UI)
        payload_link = f"/ui/approvals/{exception.tenant_id}"
        
        # Convert notification policies to dict
        notif_policies_dict = tenant_policy.notification_policies.model_dump(by_alias=True)
        
        notification_service.send_notification(
            tenant_id=exception.tenant_id,
            group=group,
            subject=subject,
            message=message,
            payload_link=payload_link,
            notification_policies=notif_policies_dict,
        )
    except Exception as e:
        logger.warning(f"Failed to send approval notification: {e}")


def _send_resolution_notification(
    notification_service: NotificationService,
    tenant_policy: TenantPolicyPack,
    exception: ExceptionRecord,
    context: dict[str, Any],
) -> None:
    """
    Send notification for auto-resolution complete.
    
    Args:
        notification_service: Notification service instance
        tenant_policy: Tenant policy pack
        exception: Exception record
        context: Processing context
    """
    if not tenant_policy.notification_policies:
        return
    
    try:
        group = _get_notification_group(exception, tenant_policy, context)
        subject = f"Exception Auto-Resolved: {exception.exception_id}"
        message = (
            f"Exception {exception.exception_id} has been automatically resolved.\n\n"
            f"Type: {exception.exception_type or 'Unknown'}\n"
            f"Severity: {exception.severity.value if exception.severity else 'Unknown'}\n"
            f"Timestamp: {exception.timestamp.isoformat() if exception.timestamp else 'Unknown'}\n"
            f"Resolved: {datetime.now(timezone.utc).isoformat()}"
        )
        
        # Build payload link (for UI)
        payload_link = f"/ui/exceptions/{exception.tenant_id}/{exception.exception_id}"
        
        # Convert notification policies to dict
        notif_policies_dict = tenant_policy.notification_policies.model_dump(by_alias=True)
        
        notification_service.send_notification(
            tenant_id=exception.tenant_id,
            group=group,
            subject=subject,
            message=message,
            payload_link=payload_link,
            notification_policies=notif_policies_dict,
        )
    except Exception as e:
        logger.warning(f"Failed to send resolution notification: {e}")
