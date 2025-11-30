"""
Simulation orchestrator for Phase 3.

Allows re-running exceptions with overrides in simulation mode
without persisting changes to real exception state.

Matches specification from phase3-mvp-issues.md P3-14.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.orchestrator.runner import _process_exception, run_pipeline

logger = logging.getLogger(__name__)


class SimulationError(Exception):
    """Raised when simulation operations fail."""

    pass


async def run_simulation(
    exception_record: ExceptionRecord,
    domain_pack: DomainPack,
    tenant_policy: TenantPolicyPack,
    overrides: Optional[dict[str, Any]] = None,
    tenant_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Run a simulation of exception processing with optional overrides.
    
    Simulation mode:
    - Reuses same agent pipeline
    - Respects guardrails
    - Does NOT persist changes to real exception state
    - Tags audit events as "SIMULATION"
    
    Args:
        exception_record: Original exception record to simulate
        domain_pack: Domain Pack for the tenant
        tenant_policy: Tenant Policy Pack for the tenant
        overrides: Optional overrides dictionary with:
            - severity: Optional Severity override
            - policies: Optional policy overrides (dict)
            - playbook: Optional playbook override
        tenant_id: Optional tenant ID (uses exception_record.tenant_id if not provided)
        
    Returns:
        Simulation result dictionary with:
        {
            "simulation_id": str,
            "original_exception_id": str,
            "simulated_exception": ExceptionRecord,
            "pipeline_result": dict,
            "overrides_applied": dict,
            "timestamp": datetime,
        }
    """
    if overrides is None:
        overrides = {}
    
    tenant_id = tenant_id or exception_record.tenant_id
    
    # Create simulation ID
    simulation_id = str(uuid.uuid4())
    
    # Create a copy of the exception record for simulation
    # Apply overrides if provided
    exception_dict = exception_record.model_dump()
    
    # Apply severity override
    if "severity" in overrides:
        exception_dict["severity"] = overrides["severity"]
    
    # Apply other overrides to normalized_context
    if "normalized_context" not in exception_dict:
        exception_dict["normalized_context"] = {}
    
    # Apply policy overrides to normalized_context
    if "policies" in overrides:
        exception_dict["normalized_context"]["policy_overrides"] = overrides["policies"]
    
    # Apply playbook override
    if "playbook" in overrides:
        exception_dict["normalized_context"]["playbook_override"] = overrides["playbook"]
    
    # Create simulated exception record
    simulated_exception = ExceptionRecord(**exception_dict)
    
    # Create simulation-specific audit logger
    # Use a special run_id to tag all events as SIMULATION
    simulation_run_id = f"SIMULATION_{simulation_id}"
    simulation_audit_logger = AuditLogger(run_id=simulation_run_id, tenant_id=tenant_id)
    
    # Create a modified tenant policy if policy overrides are provided
    simulated_tenant_policy = tenant_policy
    if "policies" in overrides:
        # Create a copy of tenant policy with overrides
        policy_dict = tenant_policy.model_dump()
        # Apply policy overrides (this is a simplified approach - in production,
        # you'd want more sophisticated policy merging)
        if "custom_guardrails" in overrides["policies"]:
            if "custom_guardrails" not in policy_dict:
                policy_dict["custom_guardrails"] = {}
            policy_dict["custom_guardrails"].update(overrides["policies"]["custom_guardrails"])
        
        simulated_tenant_policy = TenantPolicyPack(**policy_dict)
    
    # Run pipeline in simulation mode
    # Pass simulation flag to prevent persistence
    try:
        # Convert exception to raw format for pipeline
        raw_exception = {
            "exceptionId": simulated_exception.exception_id,
            "tenantId": simulated_exception.tenant_id,
            "sourceSystem": simulated_exception.source_system,
            "exceptionType": simulated_exception.exception_type,
            "severity": simulated_exception.severity.value if simulated_exception.severity else None,
            "timestamp": simulated_exception.timestamp.isoformat(),
            "rawPayload": simulated_exception.raw_payload,
            "normalizedContext": simulated_exception.normalized_context,
        }
        
        # Run pipeline with simulation mode
        # Note: We need to modify the pipeline runner to support simulation mode
        # For now, we'll use a custom processing function that doesn't persist
        
        # Initialize agents with simulation audit logger
        from src.agents.intake import IntakeAgent
        from src.agents.triage import TriageAgent
        from src.agents.policy import PolicyAgent
        from src.agents.resolution import ResolutionAgent
        from src.agents.feedback import FeedbackAgent
        from src.agents.supervisor import SupervisorAgent
        from src.tools.registry import ToolRegistry
        from src.tools.invoker import ToolInvoker
        from src.learning.policy_learning import PolicyLearning
        
        tool_registry = ToolRegistry()
        tool_registry.register_domain_pack(tenant_id, domain_pack)
        tool_registry.register_policy_pack(tenant_id, simulated_tenant_policy)
        
        intake_agent = IntakeAgent(audit_logger=simulation_audit_logger)
        triage_agent = TriageAgent(domain_pack=domain_pack, audit_logger=simulation_audit_logger)
        policy_agent = PolicyAgent(
            domain_pack=domain_pack,
            tenant_policy=simulated_tenant_policy,
            audit_logger=simulation_audit_logger,
        )
        # For simulation, create a no-op tool invoker that doesn't actually execute tools
        # This prevents side effects during simulation
        from unittest.mock import MagicMock
        mock_tool_invoker = MagicMock(spec=ToolInvoker)
        mock_tool_invoker.invoke_tool = MagicMock(return_value={"status": "simulated", "result": "No actual tool execution in simulation mode"})
        
        tool_invoker = mock_tool_invoker  # Use mock instead of real invoker for simulation
        
        # Create execution engine that doesn't execute (simulation mode)
        from src.tools.execution_engine import ToolExecutionEngine
        mock_execution_engine = MagicMock(spec=ToolExecutionEngine)
        mock_execution_engine.execute_playbook_steps = MagicMock(return_value=[])
        
        resolution_agent = ResolutionAgent(
            domain_pack=domain_pack,
            tool_registry=tool_registry,
            audit_logger=simulation_audit_logger,
            tool_invoker=tool_invoker,
            tenant_policy=simulated_tenant_policy,
            execution_engine=mock_execution_engine,  # Use mock execution engine
        )
        policy_learning = PolicyLearning()
        feedback_agent = FeedbackAgent(audit_logger=simulation_audit_logger, policy_learning=policy_learning)
        supervisor_agent = SupervisorAgent(
            domain_pack=domain_pack,
            tenant_policy=simulated_tenant_policy,
            audit_logger=simulation_audit_logger,
        )
        
        # Process exception through pipeline (simulation mode - no persistence)
        # Note: _process_exception doesn't persist to exception_store by default
        # We just need to ensure we don't pass exception_store to it
        pipeline_result = await _process_exception(
            raw_exception=raw_exception,
            tenant_id=tenant_id,
            intake_agent=intake_agent,
            triage_agent=triage_agent,
            policy_agent=policy_agent,
            resolution_agent=resolution_agent,
            feedback_agent=feedback_agent,
            supervisor_agent=supervisor_agent,
            audit_logger=simulation_audit_logger,
            stage_timeouts={},
            hooks=None,
            snapshot_dir=None,  # No snapshots for simulation
            exception_index=0,
            tenant_policy=simulated_tenant_policy,
            notification_service=None,  # No notifications for simulation
        )
        
        # Ensure we don't persist to exception store (simulation mode)
        # The _process_exception function doesn't persist by default, so we're safe
        
        # Extract final exception from pipeline result
        final_exception = pipeline_result.get("exception", simulated_exception)
        
        # Build simulation result
        simulation_result = {
            "simulation_id": simulation_id,
            "original_exception_id": exception_record.exception_id,
            "simulated_exception": final_exception.model_dump() if hasattr(final_exception, "model_dump") else final_exception,
            "pipeline_result": pipeline_result,
            "overrides_applied": overrides,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        # Persist simulation result to file
        _persist_simulation_result(tenant_id, simulation_id, simulation_result)
        
        return simulation_result
        
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
        raise SimulationError(f"Failed to run simulation: {e}") from e


def _persist_simulation_result(tenant_id: str, simulation_id: str, result: dict[str, Any]) -> None:
    """
    Persist simulation result to file.
    
    Args:
        tenant_id: Tenant identifier
        simulation_id: Simulation identifier
        result: Simulation result dictionary
    """
    simulation_dir = Path("./runtime/simulations") / tenant_id
    simulation_dir.mkdir(parents=True, exist_ok=True)
    
    simulation_file = simulation_dir / f"{simulation_id}.json"
    
    try:
        with open(simulation_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, default=str)
        logger.debug(f"Persisted simulation result to {simulation_file}")
    except Exception as e:
        logger.warning(f"Failed to persist simulation result: {e}")


def get_simulation_result(tenant_id: str, simulation_id: str) -> Optional[dict[str, Any]]:
    """
    Retrieve a simulation result from storage.
    
    Args:
        tenant_id: Tenant identifier
        simulation_id: Simulation identifier
        
    Returns:
        Simulation result dictionary or None if not found
    """
    simulation_file = Path("./runtime/simulations") / tenant_id / f"{simulation_id}.json"
    
    if not simulation_file.exists():
        return None
    
    try:
        with open(simulation_file, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load simulation result: {e}")
        return None

