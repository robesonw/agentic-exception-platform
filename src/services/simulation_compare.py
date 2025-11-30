"""
Simulation comparison service for Phase 3.

Compares original exception processing runs with simulated runs
to highlight differences in decisions, severity, actions, and approvals.

Matches specification from phase3-mvp-issues.md P3-14.
"""

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SimulationComparisonError(Exception):
    """Raised when simulation comparison operations fail."""

    pass


def compare_runs(
    original_run: dict[str, Any], simulated_run: dict[str, Any]
) -> dict[str, Any]:
    """
    Compare original run with simulated run and highlight differences.
    
    Args:
        original_run: Original pipeline result dictionary
        simulated_run: Simulated pipeline result dictionary
        
    Returns:
        Dictionary with comparison results:
        {
            "differences": {
                "severity": {"original": ..., "simulated": ..., "changed": bool},
                "decisions": {
                    "intake": {"original": ..., "simulated": ..., "changed": bool},
                    "triage": {...},
                    "policy": {...},
                    "resolution": {...},
                },
                "actions": {
                    "playbook_selected": {"original": ..., "simulated": ..., "changed": bool},
                    "tools_executed": {"original": [...], "simulated": [...], "added": [...], "removed": [...]},
                },
                "approvals_required": {"original": bool, "simulated": bool, "changed": bool},
            },
            "summary": {
                "total_differences": int,
                "critical_changes": list[str],  # e.g., ["severity", "approvals_required"]
            }
        }
    """
    differences: dict[str, Any] = {
        "severity": {},
        "decisions": {},
        "actions": {},
        "approvals_required": {},
    }
    
    # Extract exception records
    original_exception = original_run.get("exception")
    simulated_exception = simulated_run.get("exception")
    
    original_stages = original_run.get("stages", {})
    simulated_stages = simulated_run.get("stages", {})
    
    # Compare severity
    original_severity = None
    simulated_severity = None
    if original_exception:
        original_severity = getattr(original_exception, "severity", None) or original_exception.get("severity") if isinstance(original_exception, dict) else None
    if simulated_exception:
        simulated_severity = getattr(simulated_exception, "severity", None) or simulated_exception.get("severity") if isinstance(simulated_exception, dict) else None
    
    differences["severity"] = {
        "original": str(original_severity) if original_severity else None,
        "simulated": str(simulated_severity) if simulated_severity else None,
        "changed": original_severity != simulated_severity,
    }
    
    # Compare decisions for each stage
    stage_names = ["intake", "triage", "policy", "resolution", "feedback", "supervisor"]
    for stage_name in stage_names:
        original_decision = original_stages.get(stage_name)
        simulated_decision = simulated_stages.get(stage_name)
        
        # Extract decision text and confidence
        original_decision_text = None
        original_confidence = None
        if original_decision:
            if hasattr(original_decision, "decision"):
                original_decision_text = original_decision.decision
                original_confidence = original_decision.confidence
            elif isinstance(original_decision, dict):
                original_decision_text = original_decision.get("decision")
                original_confidence = original_decision.get("confidence")
        
        simulated_decision_text = None
        simulated_confidence = None
        if simulated_decision:
            if hasattr(simulated_decision, "decision"):
                simulated_decision_text = simulated_decision.decision
                simulated_confidence = simulated_decision.confidence
            elif isinstance(simulated_decision, dict):
                simulated_decision_text = simulated_decision.get("decision")
                simulated_confidence = simulated_decision.get("confidence")
        
        differences["decisions"][stage_name] = {
            "original": {
                "decision": original_decision_text,
                "confidence": original_confidence,
            },
            "simulated": {
                "decision": simulated_decision_text,
                "confidence": simulated_confidence,
            },
            "changed": original_decision_text != simulated_decision_text or original_confidence != simulated_confidence,
        }
    
    # Compare actions (playbook and tools)
    original_playbook = None
    simulated_playbook = None
    original_tools = []
    simulated_tools = []
    
    # Extract playbook from resolution stage or pipeline result
    if "resolution" in original_stages:
        original_resolution = original_stages["resolution"]
        if isinstance(original_resolution, dict):
            original_playbook = original_resolution.get("playbook_id") or original_resolution.get("selected_playbook")
            original_tools = original_resolution.get("tools_executed", [])
        elif hasattr(original_resolution, "evidence"):
            # Try to extract from evidence
            evidence = original_resolution.evidence if hasattr(original_resolution, "evidence") else []
            for ev in evidence:
                if "playbook" in str(ev).lower():
                    original_playbook = str(ev)
    
    if "resolution" in simulated_stages:
        simulated_resolution = simulated_stages["resolution"]
        if isinstance(simulated_resolution, dict):
            simulated_playbook = simulated_resolution.get("playbook_id") or simulated_resolution.get("selected_playbook")
            simulated_tools = simulated_resolution.get("tools_executed", [])
        elif hasattr(simulated_resolution, "evidence"):
            evidence = simulated_resolution.evidence if hasattr(simulated_resolution, "evidence") else []
            for ev in evidence:
                if "playbook" in str(ev).lower():
                    simulated_playbook = str(ev)
    
    # Compare tools
    original_tools_set = set(str(t) for t in original_tools)
    simulated_tools_set = set(str(t) for t in simulated_tools)
    added_tools = list(simulated_tools_set - original_tools_set)
    removed_tools = list(original_tools_set - simulated_tools_set)
    
    differences["actions"] = {
        "playbook_selected": {
            "original": original_playbook,
            "simulated": simulated_playbook,
            "changed": original_playbook != simulated_playbook,
        },
        "tools_executed": {
            "original": list(original_tools_set),
            "simulated": list(simulated_tools_set),
            "added": added_tools,
            "removed": removed_tools,
            "changed": len(added_tools) > 0 or len(removed_tools) > 0,
        },
    }
    
    # Compare approvals required
    original_approval_required = False
    simulated_approval_required = False
    
    # Check policy stage for approval requirements
    if "policy" in original_stages:
        original_policy = original_stages["policy"]
        if isinstance(original_policy, dict):
            original_approval_required = original_policy.get("human_approval_required", False) or original_policy.get("next_step") == "PENDING_APPROVAL"
        elif hasattr(original_policy, "next_step"):
            original_approval_required = original_policy.next_step == "PENDING_APPROVAL"
    
    if "policy" in simulated_stages:
        simulated_policy = simulated_stages["policy"]
        if isinstance(simulated_policy, dict):
            simulated_approval_required = simulated_policy.get("human_approval_required", False) or simulated_policy.get("next_step") == "PENDING_APPROVAL"
        elif hasattr(simulated_policy, "next_step"):
            simulated_approval_required = simulated_policy.next_step == "PENDING_APPROVAL"
    
    differences["approvals_required"] = {
        "original": original_approval_required,
        "simulated": simulated_approval_required,
        "changed": original_approval_required != simulated_approval_required,
    }
    
    # Generate summary
    total_differences = 0
    critical_changes = []
    
    if differences["severity"]["changed"]:
        total_differences += 1
        critical_changes.append("severity")
    
    for stage_name, stage_diff in differences["decisions"].items():
        if stage_diff["changed"]:
            total_differences += 1
            if stage_name in ["policy", "resolution"]:
                critical_changes.append(f"decision_{stage_name}")
    
    if differences["actions"]["playbook_selected"]["changed"]:
        total_differences += 1
        critical_changes.append("playbook")
    
    if differences["actions"]["tools_executed"]["changed"]:
        total_differences += 1
        critical_changes.append("tools")
    
    if differences["approvals_required"]["changed"]:
        total_differences += 1
        critical_changes.append("approvals_required")
    
    return {
        "differences": differences,
        "summary": {
            "total_differences": total_differences,
            "critical_changes": critical_changes,
        },
    }

