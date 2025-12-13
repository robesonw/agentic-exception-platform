"""
Playbook management system.

Phase 2: Includes LLM-based playbook generation.
Phase 7: Includes playbook matching, condition evaluation, and execution.
"""

from src.playbooks.action_executors import (
    ActionExecutorError,
    exec_add_comment,
    exec_assign_owner,
    exec_call_tool,
    exec_notify,
    exec_set_status,
    resolve_placeholders,
)
from src.playbooks.condition_engine import evaluate_conditions
from src.playbooks.execution_service import PlaybookExecutionError, PlaybookExecutionService
from src.playbooks.generator import PlaybookGenerator, PlaybookGeneratorError
from src.playbooks.manager import PlaybookManager, PlaybookManagerError
from src.playbooks.matching_service import MatchingResult, PlaybookMatchingService

__all__ = [
    "PlaybookManager",
    "PlaybookManagerError",
    "PlaybookGenerator",
    "PlaybookGeneratorError",
    "evaluate_conditions",
    "PlaybookMatchingService",
    "MatchingResult",
    "PlaybookExecutionService",
    "PlaybookExecutionError",
    "ActionExecutorError",
    "resolve_placeholders",
    "exec_notify",
    "exec_assign_owner",
    "exec_set_status",
    "exec_add_comment",
    "exec_call_tool",
]

