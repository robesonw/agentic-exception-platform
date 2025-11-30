"""
Tenancy-Aware Quotas and Limits (P3-26).

Implements hard quotas per tenant for:
- LLM API (tokens, requests, cost)
- Vector DB operations
- Tool executions

Connects to monitoring and enforcement.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Optional

logger = logging.getLogger(__name__)


class QuotaExceeded(Exception):
    """Raised when a quota is exceeded."""

    def __init__(
        self,
        message: str,
        quota_type: str,
        tenant_id: str,
        current_usage: float,
        quota_limit: float,
        details: Optional[dict[str, Any]] = None,
    ):
        """
        Initialize quota exceeded exception.
        
        Args:
            message: Human-readable error message
            quota_type: Type of quota (e.g., "llm_tokens", "vector_queries", "tool_calls")
            tenant_id: Tenant identifier
            current_usage: Current usage value
            quota_limit: Quota limit value
            details: Optional additional details
        """
        super().__init__(message)
        self.message = message
        self.quota_type = quota_type
        self.tenant_id = tenant_id
        self.current_usage = current_usage
        self.quota_limit = quota_limit
        self.details = details or {}
        self.timestamp = datetime.now(timezone.utc)


@dataclass
class QuotaConfig:
    """
    Quota configuration for a tenant.
    
    Defines hard limits for:
    - LLM usage (tokens per day, requests per minute, cost per day)
    - Vector DB operations (queries per minute, storage MB)
    - Tool executions (calls per minute, execution time per minute)
    """

    tenant_id: str
    # LLM quotas
    llm_tokens_per_day: int = 1_000_000  # Default: 1M tokens per day
    llm_requests_per_minute: int = 100  # Default: 100 requests per minute
    llm_cost_per_day: float = 100.0  # Default: $100 per day
    # Vector DB quotas
    vector_queries_per_minute: int = 200  # Default: 200 queries per minute
    vector_writes_per_minute: int = 50  # Default: 50 writes per minute
    vector_storage_mb: int = 10_000  # Default: 10GB storage
    # Tool execution quotas
    tool_calls_per_minute: int = 500  # Default: 500 calls per minute
    tool_exec_time_ms_per_minute: int = 300_000  # Default: 5 minutes total exec time per minute

    def to_dict(self) -> dict:
        """Convert quota config to dictionary."""
        return {
            "tenant_id": self.tenant_id,
            "llm_tokens_per_day": self.llm_tokens_per_day,
            "llm_requests_per_minute": self.llm_requests_per_minute,
            "llm_cost_per_day": self.llm_cost_per_day,
            "vector_queries_per_minute": self.vector_queries_per_minute,
            "vector_writes_per_minute": self.vector_writes_per_minute,
            "vector_storage_mb": self.vector_storage_mb,
            "tool_calls_per_minute": self.tool_calls_per_minute,
            "tool_exec_time_ms_per_minute": self.tool_exec_time_ms_per_minute,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuotaConfig":
        """Create quota config from dictionary."""
        return cls(
            tenant_id=data["tenant_id"],
            llm_tokens_per_day=data.get("llm_tokens_per_day", 1_000_000),
            llm_requests_per_minute=data.get("llm_requests_per_minute", 100),
            llm_cost_per_day=data.get("llm_cost_per_day", 100.0),
            vector_queries_per_minute=data.get("vector_queries_per_minute", 200),
            vector_writes_per_minute=data.get("vector_writes_per_minute", 50),
            vector_storage_mb=data.get("vector_storage_mb", 10_000),
            tool_calls_per_minute=data.get("tool_calls_per_minute", 500),
            tool_exec_time_ms_per_minute=data.get("tool_exec_time_ms_per_minute", 300_000),
        )


@dataclass
class QuotaUsage:
    """
    Current quota usage for a tenant.
    
    Tracks usage counters per window (day, minute).
    """

    tenant_id: str
    # LLM usage
    llm_tokens_today: int = 0
    llm_requests_current_minute: int = 0
    llm_cost_today: float = 0.0
    llm_minute_window_start: float = field(default_factory=time.time)
    llm_day_window_start: float = field(default_factory=time.time)
    # Vector DB usage
    vector_queries_current_minute: int = 0
    vector_writes_current_minute: int = 0
    vector_storage_mb: float = 0.0
    vector_minute_window_start: float = field(default_factory=time.time)
    # Tool usage
    tool_calls_current_minute: int = 0
    tool_exec_time_ms_current_minute: int = 0
    tool_minute_window_start: float = field(default_factory=time.time)

    def reset_llm_minute_window(self) -> None:
        """Reset LLM minute window if expired."""
        now = time.time()
        if now - self.llm_minute_window_start >= 60.0:
            self.llm_requests_current_minute = 0
            self.llm_minute_window_start = now

    def reset_llm_day_window(self) -> None:
        """Reset LLM day window if expired."""
        now = time.time()
        if now - self.llm_day_window_start >= 86400.0:  # 24 hours
            self.llm_tokens_today = 0
            self.llm_cost_today = 0.0
            self.llm_day_window_start = now

    def reset_vector_minute_window(self) -> None:
        """Reset vector DB minute window if expired."""
        now = time.time()
        if now - self.vector_minute_window_start >= 60.0:
            self.vector_queries_current_minute = 0
            self.vector_writes_current_minute = 0
            self.vector_minute_window_start = now

    def reset_tool_minute_window(self) -> None:
        """Reset tool minute window if expired."""
        now = time.time()
        if now - self.tool_minute_window_start >= 60.0:
            self.tool_calls_current_minute = 0
            self.tool_exec_time_ms_current_minute = 0
            self.tool_minute_window_start = now

    def to_dict(self) -> dict:
        """Convert usage to dictionary for persistence."""
        return {
            "tenant_id": self.tenant_id,
            "llm_tokens_today": self.llm_tokens_today,
            "llm_requests_current_minute": self.llm_requests_current_minute,
            "llm_cost_today": self.llm_cost_today,
            "vector_queries_current_minute": self.vector_queries_current_minute,
            "vector_writes_current_minute": self.vector_writes_current_minute,
            "vector_storage_mb": self.vector_storage_mb,
            "tool_calls_current_minute": self.tool_calls_current_minute,
            "tool_exec_time_ms_current_minute": self.tool_exec_time_ms_current_minute,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class QuotaEnforcer:
    """
    Enforces quota limits per tenant.
    
    Checks quotas before operations and records usage after operations.
    """

    def __init__(
        self,
        default_config: Optional[QuotaConfig] = None,
        tenant_configs: Optional[dict[str, QuotaConfig]] = None,
        storage_dir: str = "./runtime/quotas",
    ):
        """
        Initialize quota enforcer.
        
        Args:
            default_config: Default quota config (used if tenant-specific not found)
            tenant_configs: Dictionary of tenant_id -> QuotaConfig for overrides
            storage_dir: Directory for persisting usage snapshots
        """
        self.default_config = default_config or QuotaConfig(tenant_id="default")
        self.tenant_configs = tenant_configs or {}
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Per-tenant usage tracking
        self._usage: dict[str, QuotaUsage] = {}
        self._lock = Lock()

    def _get_config(self, tenant_id: str) -> QuotaConfig:
        """Get quota config for tenant (tenant-specific or default)."""
        return self.tenant_configs.get(tenant_id, self.default_config)

    def _get_usage(self, tenant_id: str) -> QuotaUsage:
        """Get or create usage tracker for tenant."""
        with self._lock:
            if tenant_id not in self._usage:
                self._usage[tenant_id] = QuotaUsage(tenant_id=tenant_id)
            return self._usage[tenant_id]

    def check_llm_quota(
        self, tenant_id: str, tokens: int, estimated_cost: float = 0.0
    ) -> None:
        """
        Check LLM quota before making a call.
        
        Args:
            tenant_id: Tenant identifier
            tokens: Number of tokens for this call
            estimated_cost: Estimated cost for this call (in USD)
            
        Raises:
            QuotaExceeded: If quota would be exceeded
        """
        config = self._get_config(tenant_id)
        usage = self._get_usage(tenant_id)
        
        # Reset windows if expired
        usage.reset_llm_minute_window()
        usage.reset_llm_day_window()
        
        # Check tokens per day
        if usage.llm_tokens_today + tokens > config.llm_tokens_per_day:
            raise QuotaExceeded(
                message=(
                    f"LLM tokens quota exceeded: {usage.llm_tokens_today + tokens} > "
                    f"{config.llm_tokens_per_day} tokens per day"
                ),
                quota_type="llm_tokens",
                tenant_id=tenant_id,
                current_usage=usage.llm_tokens_today + tokens,
                quota_limit=config.llm_tokens_per_day,
                details={"tokens": tokens, "current_tokens": usage.llm_tokens_today},
            )
        
        # Check requests per minute
        if usage.llm_requests_current_minute + 1 > config.llm_requests_per_minute:
            raise QuotaExceeded(
                message=(
                    f"LLM requests quota exceeded: {usage.llm_requests_current_minute + 1} > "
                    f"{config.llm_requests_per_minute} requests per minute"
                ),
                quota_type="llm_requests",
                tenant_id=tenant_id,
                current_usage=usage.llm_requests_current_minute + 1,
                quota_limit=config.llm_requests_per_minute,
            )
        
        # Check cost per day
        if usage.llm_cost_today + estimated_cost > config.llm_cost_per_day:
            raise QuotaExceeded(
                message=(
                    f"LLM cost quota exceeded: ${usage.llm_cost_today + estimated_cost:.2f} > "
                    f"${config.llm_cost_per_day:.2f} per day"
                ),
                quota_type="llm_cost",
                tenant_id=tenant_id,
                current_usage=usage.llm_cost_today + estimated_cost,
                quota_limit=config.llm_cost_per_day,
                details={"cost": estimated_cost, "current_cost": usage.llm_cost_today},
            )

    def record_llm_usage(
        self, tenant_id: str, tokens: int, cost: float = 0.0
    ) -> None:
        """
        Record LLM usage after a call.
        
        Args:
            tenant_id: Tenant identifier
            tokens: Number of tokens used
            cost: Actual cost (in USD)
        """
        usage = self._get_usage(tenant_id)
        
        usage.reset_llm_minute_window()
        usage.reset_llm_day_window()
        
        usage.llm_tokens_today += tokens
        usage.llm_requests_current_minute += 1
        usage.llm_cost_today += cost

    def check_vector_quota(
        self,
        tenant_id: str,
        query_count: int = 0,
        write_count: int = 0,
        storage_mb_delta: float = 0.0,
    ) -> None:
        """
        Check vector DB quota before operations.
        
        Args:
            tenant_id: Tenant identifier
            query_count: Number of queries to perform
            write_count: Number of writes to perform
            storage_mb_delta: Change in storage size (MB, positive for increase)
            
        Raises:
            QuotaExceeded: If quota would be exceeded
        """
        config = self._get_config(tenant_id)
        usage = self._get_usage(tenant_id)
        
        # Reset minute window if expired
        usage.reset_vector_minute_window()
        
        # Check queries per minute
        if query_count > 0:
            if usage.vector_queries_current_minute + query_count > config.vector_queries_per_minute:
                raise QuotaExceeded(
                    message=(
                        f"Vector queries quota exceeded: "
                        f"{usage.vector_queries_current_minute + query_count} > "
                        f"{config.vector_queries_per_minute} queries per minute"
                    ),
                    quota_type="vector_queries",
                    tenant_id=tenant_id,
                    current_usage=usage.vector_queries_current_minute + query_count,
                    quota_limit=config.vector_queries_per_minute,
                    details={"query_count": query_count},
                )
        
        # Check writes per minute
        if write_count > 0:
            if usage.vector_writes_current_minute + write_count > config.vector_writes_per_minute:
                raise QuotaExceeded(
                    message=(
                        f"Vector writes quota exceeded: "
                        f"{usage.vector_writes_current_minute + write_count} > "
                        f"{config.vector_writes_per_minute} writes per minute"
                    ),
                    quota_type="vector_writes",
                    tenant_id=tenant_id,
                    current_usage=usage.vector_writes_current_minute + write_count,
                    quota_limit=config.vector_writes_per_minute,
                    details={"write_count": write_count},
                )
        
        # Check storage limit
        if storage_mb_delta > 0:
            new_storage = usage.vector_storage_mb + storage_mb_delta
            if new_storage > config.vector_storage_mb:
                raise QuotaExceeded(
                    message=(
                        f"Vector storage quota exceeded: {new_storage:.2f}MB > "
                        f"{config.vector_storage_mb}MB"
                    ),
                    quota_type="vector_storage",
                    tenant_id=tenant_id,
                    current_usage=new_storage,
                    quota_limit=config.vector_storage_mb,
                    details={"storage_delta": storage_mb_delta},
                )

    def record_vector_usage(
        self,
        tenant_id: str,
        query_count: int = 0,
        write_count: int = 0,
        storage_mb_delta: float = 0.0,
    ) -> None:
        """
        Record vector DB usage after operations.
        
        Args:
            tenant_id: Tenant identifier
            query_count: Number of queries performed
            write_count: Number of writes performed
            storage_mb_delta: Change in storage size (MB)
        """
        usage = self._get_usage(tenant_id)
        
        usage.reset_vector_minute_window()
        
        usage.vector_queries_current_minute += query_count
        usage.vector_writes_current_minute += write_count
        usage.vector_storage_mb += storage_mb_delta

    def check_tool_quota(
        self, tenant_id: str, tool_name: str, estimated_exec_time_ms: int
    ) -> None:
        """
        Check tool execution quota before execution.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of tool being executed
            estimated_exec_time_ms: Estimated execution time in milliseconds
            
        Raises:
            QuotaExceeded: If quota would be exceeded
        """
        config = self._get_config(tenant_id)
        usage = self._get_usage(tenant_id)
        
        # Reset minute window if expired
        usage.reset_tool_minute_window()
        
        # Check calls per minute
        if usage.tool_calls_current_minute + 1 > config.tool_calls_per_minute:
            raise QuotaExceeded(
                message=(
                    f"Tool calls quota exceeded: {usage.tool_calls_current_minute + 1} > "
                    f"{config.tool_calls_per_minute} calls per minute"
                ),
                quota_type="tool_calls",
                tenant_id=tenant_id,
                current_usage=usage.tool_calls_current_minute + 1,
                quota_limit=config.tool_calls_per_minute,
                details={"tool_name": tool_name},
            )
        
        # Check execution time per minute
        new_exec_time = usage.tool_exec_time_ms_current_minute + estimated_exec_time_ms
        if new_exec_time > config.tool_exec_time_ms_per_minute:
            raise QuotaExceeded(
                message=(
                    f"Tool execution time quota exceeded: {new_exec_time}ms > "
                    f"{config.tool_exec_time_ms_per_minute}ms per minute"
                ),
                quota_type="tool_exec_time",
                tenant_id=tenant_id,
                current_usage=new_exec_time,
                quota_limit=config.tool_exec_time_ms_per_minute,
                details={
                    "tool_name": tool_name,
                    "estimated_exec_time_ms": estimated_exec_time_ms,
                },
            )

    def record_tool_usage(
        self, tenant_id: str, tool_name: str, actual_exec_time_ms: int
    ) -> None:
        """
        Record tool execution usage after execution.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Name of tool executed
            actual_exec_time_ms: Actual execution time in milliseconds
        """
        usage = self._get_usage(tenant_id)
        
        usage.reset_tool_minute_window()
        
        usage.tool_calls_current_minute += 1
        usage.tool_exec_time_ms_current_minute += actual_exec_time_ms

    def get_usage_summary(self, tenant_id: str) -> dict[str, Any]:
        """
        Get usage summary for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with usage summary
        """
        config = self._get_config(tenant_id)
        usage = self._get_usage(tenant_id)
        
        # Reset windows to get current state
        usage.reset_llm_minute_window()
        usage.reset_llm_day_window()
        usage.reset_vector_minute_window()
        usage.reset_tool_minute_window()
        
        return {
            "tenant_id": tenant_id,
            "llm": {
                "tokens_today": usage.llm_tokens_today,
                "tokens_limit": config.llm_tokens_per_day,
                "tokens_remaining": max(0, config.llm_tokens_per_day - usage.llm_tokens_today),
                "requests_current_minute": usage.llm_requests_current_minute,
                "requests_limit": config.llm_requests_per_minute,
                "cost_today": usage.llm_cost_today,
                "cost_limit": config.llm_cost_per_day,
            },
            "vector": {
                "queries_current_minute": usage.vector_queries_current_minute,
                "queries_limit": config.vector_queries_per_minute,
                "writes_current_minute": usage.vector_writes_current_minute,
                "writes_limit": config.vector_writes_per_minute,
                "storage_mb": usage.vector_storage_mb,
                "storage_limit_mb": config.vector_storage_mb,
            },
            "tool": {
                "calls_current_minute": usage.tool_calls_current_minute,
                "calls_limit": config.tool_calls_per_minute,
                "exec_time_ms_current_minute": usage.tool_exec_time_ms_current_minute,
                "exec_time_ms_limit": config.tool_exec_time_ms_per_minute,
            },
        }

    def persist_usage_snapshot(self, tenant_id: str) -> None:
        """
        Persist usage snapshot to file.
        
        Args:
            tenant_id: Tenant identifier
        """
        usage = self._get_usage(tenant_id)
        usage_dict = usage.to_dict()
        
        usage_file = self.storage_dir / f"{tenant_id}_usage.jsonl"
        
        try:
            with open(usage_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(usage_dict, default=str) + "\n")
            logger.debug(f"Persisted quota usage snapshot for tenant {tenant_id}")
        except Exception as e:
            logger.error(f"Failed to persist quota usage snapshot: {e}", exc_info=True)

    def persist_all_usage_snapshots(self) -> None:
        """Persist usage snapshots for all tenants."""
        with self._lock:
            for tenant_id in self._usage.keys():
                self.persist_usage_snapshot(tenant_id)


# Global enforcer instance
_quota_enforcer: Optional[QuotaEnforcer] = None


def get_quota_enforcer() -> QuotaEnforcer:
    """
    Get global quota enforcer instance.
    
    Returns:
        QuotaEnforcer instance
    """
    global _quota_enforcer
    if _quota_enforcer is None:
        _quota_enforcer = QuotaEnforcer()
    return _quota_enforcer

