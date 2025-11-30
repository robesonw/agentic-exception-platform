"""
Operations module for Phase 3.

Provides operational runbooks and incident playbooks.
"""

from src.operations.runbook_integration import (
    trigger_runbooks_for_observability_error,
    trigger_runbooks_for_slo_violation,
    trigger_runbooks_for_violation_incident,
)
from src.operations.runbooks import (
    Runbook,
    RunbookExecution,
    RunbookExecutor,
    RunbookLoader,
    RunbookStatus,
    RunbookStep,
    RunbookSuggester,
    get_runbook_executor,
    get_runbook_loader,
    get_runbook_suggester,
    suggest_runbooks_for_incident,
)

__all__ = [
    # Runbook Models
    "Runbook",
    "RunbookExecution",
    "RunbookStep",
    "RunbookStatus",
    # Runbook Services
    "RunbookLoader",
    "RunbookSuggester",
    "RunbookExecutor",
    # Convenience Functions
    "get_runbook_loader",
    "get_runbook_suggester",
    "get_runbook_executor",
    "suggest_runbooks_for_incident",
    # Integration Functions
    "trigger_runbooks_for_violation_incident",
    "trigger_runbooks_for_slo_violation",
    "trigger_runbooks_for_observability_error",
]

