"""
Safety module for Phase 3.

Provides expanded safety rules, violation detection, incident management,
and quota enforcement for LLM calls, tool usage, and vector DB operations.
"""

from src.safety.incidents import (
    Incident,
    IncidentManager,
    IncidentStatus,
    get_incident_manager,
)
from src.safety.quota_integration import (
    QuotaAwareVectorStore,
    wrap_vector_store_with_quota,
)
from src.safety.quotas import (
    QuotaConfig,
    QuotaEnforcer,
    QuotaExceeded,
    QuotaUsage,
    get_quota_enforcer,
)
from src.safety.rules import (
    LLMSafetyRules,
    LLMUsageMetrics,
    SafetyEnforcer,
    SafetyRuleConfig,
    SafetyViolation,
    ToolSafetyRules,
    ToolUsageMetrics,
    get_safety_enforcer,
)
from src.safety.violation_detector import (
    PolicyViolation,
    ToolViolation,
    ViolationDetector,
    ViolationSeverity,
    get_violation_detector,
)

__all__ = [
    # Safety Rules
    "LLMSafetyRules",
    "LLMUsageMetrics",
    "SafetyEnforcer",
    "SafetyRuleConfig",
    "SafetyViolation",
    "ToolSafetyRules",
    "ToolUsageMetrics",
    "get_safety_enforcer",
    # Violation Detection
    "PolicyViolation",
    "ToolViolation",
    "ViolationDetector",
    "ViolationSeverity",
    "get_violation_detector",
    # Incident Management
    "Incident",
    "IncidentManager",
    "IncidentStatus",
    "get_incident_manager",
    # Quota Enforcement (P3-26)
    "QuotaConfig",
    "QuotaEnforcer",
    "QuotaExceeded",
    "QuotaUsage",
    "get_quota_enforcer",
    "QuotaAwareVectorStore",
    "wrap_vector_store_with_quota",
]

