"""
Tests for Expanded Safety Rules (P3-20).

Tests cover:
- SafetyRuleConfig configuration
- SafetyEnforcer rule enforcement
- LLM call safety checks
- Tool call safety checks
- Per-tenant overrides
- Usage metrics tracking
- Safety violation logging
"""

import time
from unittest.mock import MagicMock

import pytest

from src.safety.rules import (
    LLMSafetyRules,
    SafetyEnforcer,
    SafetyRuleConfig,
    SafetyViolation,
    ToolSafetyRules,
    get_safety_enforcer,
)


class TestSafetyRuleConfig:
    """Test suite for SafetyRuleConfig."""

    def test_default_config(self):
        """Test default safety rule configuration."""
        config = SafetyRuleConfig()
        
        assert config.llm.max_tokens_per_call == 4000
        assert config.llm.max_calls_per_minute == 60
        assert config.llm.max_cost_per_hour == 10.0
        assert config.tools.max_exec_time_ms == 30000
        assert config.tools.max_retries == 3
        assert config.tools.disallowed_tools == []

    def test_custom_config(self):
        """Test custom safety rule configuration."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(
                max_tokens_per_call=2000,
                max_calls_per_minute=30,
                max_cost_per_hour=5.0,
            ),
            tools=ToolSafetyRules(
                max_exec_time_ms=15000,
                max_retries=2,
                disallowed_tools=["dangerous_tool"],
            ),
        )
        
        assert config.llm.max_tokens_per_call == 2000
        assert config.llm.max_calls_per_minute == 30
        assert config.tools.max_exec_time_ms == 15000
        assert config.tools.disallowed_tools == ["dangerous_tool"]

    def test_tenant_overrides(self):
        """Test per-tenant overrides."""
        config = SafetyRuleConfig()
        
        # Add tenant override
        tenant_config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_tokens_per_call=1000),
        )
        config.tenant_overrides["tenant_001"] = tenant_config
        
        # Get rules for tenant
        llm_rules = config.get_llm_rules("tenant_001")
        assert llm_rules.max_tokens_per_call == 1000
        
        # Get rules for other tenant (should use global)
        llm_rules_other = config.get_llm_rules("tenant_002")
        assert llm_rules_other.max_tokens_per_call == 4000


class TestSafetyEnforcer:
    """Test suite for SafetyEnforcer."""

    def test_initialization(self):
        """Test safety enforcer initialization."""
        enforcer = SafetyEnforcer()
        
        assert enforcer.config is not None
        assert enforcer.audit_logger is None

    def test_llm_call_check_tokens(self):
        """Test LLM call token limit check."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_tokens_per_call=1000),
        )
        enforcer = SafetyEnforcer(config)
        
        # Should allow call within limit
        enforcer.check_llm_call("tenant_001", tokens=500, estimated_cost=0.01)
        
        # Should reject call exceeding limit
        with pytest.raises(SafetyViolation) as exc_info:
            enforcer.check_llm_call("tenant_001", tokens=1500, estimated_cost=0.01)
        
        assert exc_info.value.rule_type == "llm_tokens"
        assert "exceeds max tokens" in exc_info.value.message.lower()

    def test_llm_call_check_rate(self):
        """Test LLM call rate limit check."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_calls_per_minute=2),
        )
        enforcer = SafetyEnforcer(config)
        
        tenant_id = "tenant_001"
        
        # Should allow first 2 calls
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.01)
        
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.01)
        
        # Should reject third call
        with pytest.raises(SafetyViolation) as exc_info:
            enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)
        
        assert exc_info.value.rule_type == "llm_rate"
        assert "rate limit exceeded" in exc_info.value.message.lower()

    def test_llm_call_check_cost(self):
        """Test LLM call cost limit check."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_cost_per_hour=1.0),
        )
        enforcer = SafetyEnforcer(config)
        
        tenant_id = "tenant_001"
        
        # Should allow call within cost limit
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.5)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.5)
        
        # Should reject call that would exceed cost limit
        with pytest.raises(SafetyViolation) as exc_info:
            enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.6)
        
        assert exc_info.value.rule_type == "llm_cost"
        assert "exceed max cost" in exc_info.value.message.lower()

    def test_tool_call_check_disallowed(self):
        """Test tool call disallowed check."""
        config = SafetyRuleConfig(
            tools=ToolSafetyRules(disallowed_tools=["dangerous_tool"]),
        )
        enforcer = SafetyEnforcer(config)
        
        # Should reject disallowed tool
        with pytest.raises(SafetyViolation) as exc_info:
            enforcer.check_tool_call("tenant_001", "dangerous_tool", estimated_time_ms=100)
        
        assert exc_info.value.rule_type == "tool_disallowed"
        assert "disallowed" in exc_info.value.message.lower()

    def test_tool_call_check_time(self):
        """Test tool call execution time check."""
        config = SafetyRuleConfig(
            tools=ToolSafetyRules(max_exec_time_ms=1000),
        )
        enforcer = SafetyEnforcer(config)
        
        # Should allow call within time limit
        enforcer.check_tool_call("tenant_001", "safe_tool", estimated_time_ms=500)
        
        # Should reject call exceeding time limit
        with pytest.raises(SafetyViolation) as exc_info:
            enforcer.check_tool_call("tenant_001", "slow_tool", estimated_time_ms=2000)
        
        assert exc_info.value.rule_type == "tool_time"
        assert "exceeds limit" in exc_info.value.message.lower()

    def test_tool_retries_check(self):
        """Test tool retry limit check."""
        config = SafetyRuleConfig(
            tools=ToolSafetyRules(max_retries=2),
        )
        enforcer = SafetyEnforcer(config)
        
        # Should allow retries within limit
        enforcer.check_tool_retries("tenant_001", "tool_001", current_retry_count=0)
        enforcer.check_tool_retries("tenant_001", "tool_001", current_retry_count=1)
        
        # Should reject retry exceeding limit (max_retries=2 means 0,1,2 are allowed, 3+ are not)
        with pytest.raises(SafetyViolation) as exc_info:
            enforcer.check_tool_retries("tenant_001", "tool_001", current_retry_count=3)
        
        assert exc_info.value.rule_type == "tool_retries"
        assert "retry count exceeds" in exc_info.value.message.lower()

    def test_record_llm_usage(self):
        """Test recording LLM usage metrics."""
        enforcer = SafetyEnforcer()
        tenant_id = "tenant_001"
        
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.01)
        
        metrics = enforcer.get_llm_metrics(tenant_id)
        assert metrics is not None
        assert metrics.call_count == 1
        assert metrics.total_tokens == 100
        assert metrics.total_cost == 0.01

    def test_record_tool_usage(self):
        """Test recording tool usage metrics."""
        enforcer = SafetyEnforcer()
        tenant_id = "tenant_001"
        
        enforcer.record_tool_usage(tenant_id, "tool_001", exec_time_ms=500, retry_count=0)
        
        metrics = enforcer.get_tool_metrics(tenant_id)
        assert metrics is not None
        assert metrics.call_count == 1
        assert metrics.total_exec_time_ms == 500
        assert metrics.max_exec_time_ms == 500

    def test_tenant_override_enforcement(self):
        """Test that tenant-specific overrides are enforced."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_tokens_per_call=2000),
        )
        
        # Add tenant override with stricter limit
        tenant_config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_tokens_per_call=500),
        )
        config.tenant_overrides["tenant_001"] = tenant_config
        
        enforcer = SafetyEnforcer(config)
        
        # Tenant 001 should have stricter limit
        with pytest.raises(SafetyViolation):
            enforcer.check_llm_call("tenant_001", tokens=600, estimated_cost=0.01)
        
        # Tenant 002 should use global limit
        enforcer.check_llm_call("tenant_002", tokens=1500, estimated_cost=0.01)

    def test_violation_logging(self):
        """Test that violations are logged to audit trail."""
        audit_logger = MagicMock()
        enforcer = SafetyEnforcer(audit_logger=audit_logger)
        
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_tokens_per_call=1000),
        )
        enforcer.config = config
        
        # Trigger violation
        with pytest.raises(SafetyViolation):
            enforcer.check_llm_call("tenant_001", tokens=1500, estimated_cost=0.01)
        
        # Verify audit log was called
        assert audit_logger.log_event.called
        call_args = audit_logger.log_event.call_args
        assert call_args[1]["event_type"] == "safety_violation"
        assert call_args[1]["tenant_id"] == "tenant_001"


class TestGetSafetyEnforcer:
    """Test suite for global safety enforcer."""

    def test_get_global_enforcer(self):
        """Test getting global enforcer instance."""
        enforcer1 = get_safety_enforcer()
        enforcer2 = get_safety_enforcer()
        
        # Should return same instance
        assert enforcer1 is enforcer2

    def test_custom_config(self):
        """Test creating enforcer with custom config."""
        # Reset global enforcer to allow new config
        from src.safety.rules import _safety_enforcer
        import src.safety.rules as safety_module
        safety_module._safety_enforcer = None
        
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_tokens_per_call=500),
        )
        enforcer = get_safety_enforcer(config=config)
        
        assert enforcer.config.llm.max_tokens_per_call == 500


class TestSafetyIntegration:
    """Test suite for safety integration scenarios."""

    def test_rate_limit_window_reset(self):
        """Test that rate limit windows reset correctly."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_calls_per_minute=2),
        )
        enforcer = SafetyEnforcer(config)
        
        tenant_id = "tenant_001"
        
        # Make 2 calls
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.01)
        
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.01)
        
        # Third call should be rejected
        with pytest.raises(SafetyViolation):
            enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)
        
        # Manually reset window (simulating time passage)
        metrics = enforcer.get_llm_metrics(tenant_id)
        metrics.minute_window_start = time.time() - 61  # 61 seconds ago
        metrics.calls_in_current_minute = 0
        
        # Should now allow call
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.01)

    def test_cost_limit_window_reset(self):
        """Test that cost limit windows reset correctly."""
        config = SafetyRuleConfig(
            llm=LLMSafetyRules(max_cost_per_hour=1.0),
        )
        enforcer = SafetyEnforcer(config)
        
        tenant_id = "tenant_001"
        
        # Use up cost limit
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.5)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.5)
        
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.5)
        enforcer.record_llm_usage(tenant_id, tokens=100, actual_cost=0.5)
        
        # Next call should be rejected
        with pytest.raises(SafetyViolation):
            enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.1)
        
        # Manually reset window (simulating time passage)
        metrics = enforcer.get_llm_metrics(tenant_id)
        metrics.hour_window_start = time.time() - 3601  # Over 1 hour ago
        metrics.cost_in_current_hour = 0.0
        
        # Should now allow call
        enforcer.check_llm_call(tenant_id, tokens=100, estimated_cost=0.1)

