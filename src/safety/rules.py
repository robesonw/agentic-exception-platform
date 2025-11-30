"""
Expanded Safety Rules for LLM Calls and Tool Usage (P3-20).

Central safety rules around:
- LLM usage (rate, tokens, cost)
- Tool usage (execution time, resources, retries)
- Per-tenant overrides

Matches specification from phase3-mvp-issues.md P3-20.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class SafetyViolation(Exception):
    """Raised when a safety rule is violated."""

    def __init__(self, message: str, rule_type: str, tenant_id: str, details: Optional[dict[str, Any]] = None):
        """
        Initialize safety violation.
        
        Args:
            message: Human-readable error message
            rule_type: Type of rule violated (e.g., "llm_tokens", "llm_rate", "tool_time", "tool_disallowed")
            tenant_id: Tenant identifier
            details: Optional additional details about the violation
        """
        super().__init__(message)
        self.message = message
        self.rule_type = rule_type
        self.tenant_id = tenant_id
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)


@dataclass
class LLMSafetyRules:
    """Safety rules for LLM usage."""

    max_tokens_per_call: int = 4000
    max_calls_per_minute: int = 60
    max_cost_per_hour: float = 10.0  # Approximate cost in USD


@dataclass
class ToolSafetyRules:
    """Safety rules for tool usage."""

    max_exec_time_ms: int = 30000  # 30 seconds
    max_retries: int = 3
    disallowed_tools: list[str] = field(default_factory=list)


@dataclass
class SafetyRuleConfig:
    """
    Safety rule configuration.
    
    Includes global defaults and per-tenant overrides.
    """

    llm: LLMSafetyRules = field(default_factory=LLMSafetyRules)
    tools: ToolSafetyRules = field(default_factory=ToolSafetyRules)
    tenant_overrides: dict[str, "SafetyRuleConfig"] = field(default_factory=dict)

    def get_llm_rules(self, tenant_id: Optional[str] = None) -> LLMSafetyRules:
        """
        Get LLM safety rules for a tenant.
        
        Args:
            tenant_id: Optional tenant identifier for overrides
            
        Returns:
            LLMSafetyRules (tenant-specific if override exists, otherwise global)
        """
        if tenant_id and tenant_id in self.tenant_overrides:
            return self.tenant_overrides[tenant_id].llm
        return self.llm

    def get_tool_rules(self, tenant_id: Optional[str] = None) -> ToolSafetyRules:
        """
        Get tool safety rules for a tenant.
        
        Args:
            tenant_id: Optional tenant identifier for overrides
            
        Returns:
            ToolSafetyRules (tenant-specific if override exists, otherwise global)
        """
        if tenant_id and tenant_id in self.tenant_overrides:
            return self.tenant_overrides[tenant_id].tools
        return self.tools


@dataclass
class LLMUsageMetrics:
    """Metrics for tracking LLM usage per tenant."""

    tenant_id: str
    call_count: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    calls_in_current_minute: int = 0
    cost_in_current_hour: float = 0.0
    minute_window_start: float = field(default_factory=time.time)
    hour_window_start: float = field(default_factory=time.time)
    last_call_time: Optional[float] = None

    def reset_minute_window(self) -> None:
        """Reset minute window if expired."""
        now = time.time()
        if now - self.minute_window_start >= 60.0:
            self.calls_in_current_minute = 0
            self.minute_window_start = now

    def reset_hour_window(self) -> None:
        """Reset hour window if expired."""
        now = time.time()
        if now - self.hour_window_start >= 3600.0:
            self.cost_in_current_hour = 0.0
            self.hour_window_start = now


@dataclass
class ToolUsageMetrics:
    """Metrics for tracking tool usage per tenant."""

    tenant_id: str
    call_count: int = 0
    total_exec_time_ms: int = 0
    max_exec_time_ms: int = 0
    retry_count: int = 0
    last_call_time: Optional[float] = None


class SafetyEnforcer:
    """
    Enforces safety rules for LLM calls and tool usage.
    
    Tracks usage metrics and blocks operations that violate safety rules.
    """

    def __init__(self, config: Optional[SafetyRuleConfig] = None, audit_logger: Optional[Any] = None):
        """
        Initialize safety enforcer.
        
        Args:
            config: Safety rule configuration (uses default if not provided)
            audit_logger: Optional audit logger for recording violations
        """
        self.config = config or SafetyRuleConfig()
        self.audit_logger = audit_logger
        
        # Per-tenant usage metrics
        self._llm_metrics: dict[str, LLMUsageMetrics] = {}
        self._tool_metrics: dict[str, ToolUsageMetrics] = {}

    def check_llm_call(
        self,
        tenant_id: str,
        tokens: int,
        estimated_cost: float = 0.0,
    ) -> None:
        """
        Check if an LLM call is allowed based on safety rules.
        
        Args:
            tenant_id: Tenant identifier
            tokens: Number of tokens for this call
            estimated_cost: Estimated cost for this call (in USD)
            
        Raises:
            SafetyViolation: If the call violates safety rules
        """
        rules = self.config.get_llm_rules(tenant_id)
        
        # Get or create metrics for tenant
        if tenant_id not in self._llm_metrics:
            self._llm_metrics[tenant_id] = LLMUsageMetrics(tenant_id=tenant_id)
        
        metrics = self._llm_metrics[tenant_id]
        
        # Reset windows if expired
        metrics.reset_minute_window()
        metrics.reset_hour_window()
        
        # Check max tokens per call
        if tokens > rules.max_tokens_per_call:
            violation = SafetyViolation(
                message=f"LLM call exceeds max tokens per call: {tokens} > {rules.max_tokens_per_call}",
                rule_type="llm_tokens",
                tenant_id=tenant_id,
                details={"tokens": tokens, "max_tokens": rules.max_tokens_per_call},
            )
            self._log_violation(violation)
            raise violation
        
        # Check max calls per minute
        if metrics.calls_in_current_minute >= rules.max_calls_per_minute:
            violation = SafetyViolation(
                message=f"LLM call rate limit exceeded: {metrics.calls_in_current_minute} >= {rules.max_calls_per_minute} calls/min",
                rule_type="llm_rate",
                tenant_id=tenant_id,
                details={
                    "calls_in_minute": metrics.calls_in_current_minute,
                    "max_calls_per_minute": rules.max_calls_per_minute,
                },
            )
            self._log_violation(violation)
            raise violation
        
        # Check max cost per hour
        projected_cost = metrics.cost_in_current_hour + estimated_cost
        if projected_cost > rules.max_cost_per_hour:
            violation = SafetyViolation(
                message=f"LLM call would exceed max cost per hour: ${projected_cost:.2f} > ${rules.max_cost_per_hour:.2f}",
                rule_type="llm_cost",
                tenant_id=tenant_id,
                details={
                    "projected_cost": projected_cost,
                    "max_cost_per_hour": rules.max_cost_per_hour,
                    "estimated_cost": estimated_cost,
                },
            )
            self._log_violation(violation)
            raise violation

    def record_llm_usage(
        self,
        tenant_id: str,
        tokens: int,
        actual_cost: float = 0.0,
    ) -> None:
        """
        Record LLM usage after a successful call.
        
        Args:
            tenant_id: Tenant identifier
            tokens: Number of tokens used
            actual_cost: Actual cost incurred (in USD)
        """
        if tenant_id not in self._llm_metrics:
            self._llm_metrics[tenant_id] = LLMUsageMetrics(tenant_id=tenant_id)
        
        metrics = self._llm_metrics[tenant_id]
        
        # Reset windows if expired
        metrics.reset_minute_window()
        metrics.reset_hour_window()
        
        # Update metrics
        metrics.call_count += 1
        metrics.total_tokens += tokens
        metrics.total_cost += actual_cost
        metrics.calls_in_current_minute += 1
        metrics.cost_in_current_hour += actual_cost
        metrics.last_call_time = time.time()
        
        logger.debug(
            f"Recorded LLM usage for tenant {tenant_id}: "
            f"tokens={tokens}, cost=${actual_cost:.4f}, "
            f"calls/min={metrics.calls_in_current_minute}, "
            f"cost/hour=${metrics.cost_in_current_hour:.2f}"
        )

    def check_tool_call(
        self,
        tenant_id: str,
        tool_name: str,
        estimated_time_ms: int = 0,
    ) -> None:
        """
        Check if a tool call is allowed based on safety rules.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool to call
            estimated_time_ms: Estimated execution time in milliseconds
            
        Raises:
            SafetyViolation: If the call violates safety rules
        """
        rules = self.config.get_tool_rules(tenant_id)
        
        # Check if tool is disallowed
        if tool_name in rules.disallowed_tools:
            violation = SafetyViolation(
                message=f"Tool '{tool_name}' is disallowed for tenant {tenant_id}",
                rule_type="tool_disallowed",
                tenant_id=tenant_id,
                details={"tool_name": tool_name, "disallowed_tools": rules.disallowed_tools},
            )
            self._log_violation(violation)
            raise violation
        
        # Check max execution time (if estimated)
        if estimated_time_ms > 0 and estimated_time_ms > rules.max_exec_time_ms:
            violation = SafetyViolation(
                message=f"Tool call estimated time exceeds limit: {estimated_time_ms}ms > {rules.max_exec_time_ms}ms",
                rule_type="tool_time",
                tenant_id=tenant_id,
                details={
                    "tool_name": tool_name,
                    "estimated_time_ms": estimated_time_ms,
                    "max_exec_time_ms": rules.max_exec_time_ms,
                },
            )
            self._log_violation(violation)
            raise violation

    def record_tool_usage(
        self,
        tenant_id: str,
        tool_name: str,
        exec_time_ms: int,
        retry_count: int = 0,
    ) -> None:
        """
        Record tool usage after execution.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            exec_time_ms: Actual execution time in milliseconds
            retry_count: Number of retries attempted
        """
        if tenant_id not in self._tool_metrics:
            self._tool_metrics[tenant_id] = ToolUsageMetrics(tenant_id=tenant_id)
        
        metrics = self._tool_metrics[tenant_id]
        
        # Update metrics
        metrics.call_count += 1
        metrics.total_exec_time_ms += exec_time_ms
        metrics.max_exec_time_ms = max(metrics.max_exec_time_ms, exec_time_ms)
        metrics.retry_count += retry_count
        metrics.last_call_time = time.time()
        
        # Check if execution time exceeded limit (post-execution check)
        rules = self.config.get_tool_rules(tenant_id)
        if exec_time_ms > rules.max_exec_time_ms:
            logger.warning(
                f"Tool '{tool_name}' execution time exceeded limit for tenant {tenant_id}: "
                f"{exec_time_ms}ms > {rules.max_exec_time_ms}ms"
            )
        
        logger.debug(
            f"Recorded tool usage for tenant {tenant_id}: "
            f"tool={tool_name}, exec_time={exec_time_ms}ms, retries={retry_count}"
        )

    def check_tool_retries(
        self,
        tenant_id: str,
        tool_name: str,
        current_retry_count: int,
    ) -> None:
        """
        Check if tool retries are allowed.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of the tool
            current_retry_count: Current number of retries attempted
            
        Raises:
            SafetyViolation: If retry count exceeds limit
        """
        rules = self.config.get_tool_rules(tenant_id)
        
        if current_retry_count > rules.max_retries:
            violation = SafetyViolation(
                message=f"Tool '{tool_name}' retry count exceeds limit: {current_retry_count} >= {rules.max_retries}",
                rule_type="tool_retries",
                tenant_id=tenant_id,
                details={
                    "tool_name": tool_name,
                    "retry_count": current_retry_count,
                    "max_retries": rules.max_retries,
                },
            )
            self._log_violation(violation)
            raise violation

    def get_llm_metrics(self, tenant_id: str) -> Optional[LLMUsageMetrics]:
        """
        Get LLM usage metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            LLMUsageMetrics or None if no usage recorded
        """
        return self._llm_metrics.get(tenant_id)

    def get_tool_metrics(self, tenant_id: str) -> Optional[ToolUsageMetrics]:
        """
        Get tool usage metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            ToolUsageMetrics or None if no usage recorded
        """
        return self._tool_metrics.get(tenant_id)

    def _log_violation(self, violation: SafetyViolation) -> None:
        """
        Log safety violation to audit trail.
        
        Args:
            violation: SafetyViolation instance
        """
        logger.warning(
            f"Safety violation for tenant {violation.tenant_id}: "
            f"{violation.rule_type} - {violation.message}"
        )
        
        # Log to audit trail if available
        if self.audit_logger:
            try:
                self.audit_logger.log_event(
                    event_type="safety_violation",
                    data={
                        "rule_type": violation.rule_type,
                        "tenant_id": violation.tenant_id,
                        "message": violation.message,
                        "details": violation.details,
                        "timestamp": violation.timestamp.isoformat(),
                    },
                    tenant_id=violation.tenant_id,
                )
            except Exception as e:
                logger.error(f"Failed to log safety violation to audit trail: {e}")


# Global safety enforcer instance
_safety_enforcer: Optional[SafetyEnforcer] = None


def get_safety_enforcer(
    config: Optional[SafetyRuleConfig] = None,
    audit_logger: Optional[Any] = None,
) -> SafetyEnforcer:
    """
    Get the global safety enforcer instance.
    
    Args:
        config: Optional safety rule configuration
        audit_logger: Optional audit logger
        
    Returns:
        SafetyEnforcer instance
    """
    global _safety_enforcer
    if _safety_enforcer is None:
        _safety_enforcer = SafetyEnforcer(config, audit_logger)
    return _safety_enforcer

