"""
Tests for Quota Enforcer (P3-26).

Tests quota enforcement, usage tracking, and per-tenant isolation.
"""

import pytest
import time

from src.safety.quotas import QuotaConfig, QuotaEnforcer, QuotaExceeded, QuotaUsage


class TestQuotaConfig:
    """Tests for QuotaConfig."""

    def test_quota_config_defaults(self):
        """Test quota config with defaults."""
        config = QuotaConfig(tenant_id="tenant_001")
        
        assert config.tenant_id == "tenant_001"
        assert config.llm_tokens_per_day == 1_000_000
        assert config.llm_requests_per_minute == 100
        assert config.llm_cost_per_day == 100.0
        assert config.vector_queries_per_minute == 200
        assert config.vector_writes_per_minute == 50
        assert config.vector_storage_mb == 10_000
        assert config.tool_calls_per_minute == 500
        assert config.tool_exec_time_ms_per_minute == 300_000

    def test_quota_config_custom(self):
        """Test quota config with custom values."""
        config = QuotaConfig(
            tenant_id="tenant_001",
            llm_tokens_per_day=500_000,
            llm_requests_per_minute=50,
            vector_queries_per_minute=100,
            tool_calls_per_minute=200,
        )
        
        assert config.llm_tokens_per_day == 500_000
        assert config.llm_requests_per_minute == 50
        assert config.vector_queries_per_minute == 100
        assert config.tool_calls_per_minute == 200

    def test_quota_config_to_dict(self):
        """Test quota config to dictionary conversion."""
        config = QuotaConfig(tenant_id="tenant_001")
        data = config.to_dict()
        
        assert data["tenant_id"] == "tenant_001"
        assert "llm_tokens_per_day" in data
        assert "vector_queries_per_minute" in data


class TestQuotaUsage:
    """Tests for QuotaUsage."""

    def test_quota_usage_reset_windows(self):
        """Test quota usage window reset logic."""
        usage = QuotaUsage(tenant_id="tenant_001")
        
        # Set usage
        usage.llm_requests_current_minute = 50
        usage.llm_tokens_today = 100_000
        
        # Reset minute window (simulate time passing)
        usage.llm_minute_window_start = time.time() - 70  # 70 seconds ago
        usage.reset_llm_minute_window()
        
        assert usage.llm_requests_current_minute == 0
        
        # Reset day window
        usage.llm_day_window_start = time.time() - 90000  # 25 hours ago
        usage.reset_llm_day_window()
        
        assert usage.llm_tokens_today == 0
        assert usage.llm_cost_today == 0.0


class TestQuotaEnforcer:
    """Tests for QuotaEnforcer."""

    def test_llm_quota_check_passes(self):
        """Test LLM quota check when under limits."""
        enforcer = QuotaEnforcer()
        
        # Should not raise
        enforcer.check_llm_quota("tenant_001", tokens=1000, estimated_cost=0.01)
        enforcer.record_llm_usage("tenant_001", tokens=1000, cost=0.01)

    def test_llm_quota_tokens_exceeded(self):
        """Test LLM quota check when tokens exceed limit."""
        config = QuotaConfig(tenant_id="tenant_001", llm_tokens_per_day=1000)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        enforcer.record_llm_usage("tenant_001", tokens=1000, cost=0.01)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_llm_quota("tenant_001", tokens=1, estimated_cost=0.0)
        
        assert exc_info.value.quota_type == "llm_tokens"
        assert exc_info.value.tenant_id == "tenant_001"

    def test_llm_quota_requests_exceeded(self):
        """Test LLM quota check when requests per minute exceed limit."""
        config = QuotaConfig(tenant_id="tenant_001", llm_requests_per_minute=5)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        for _ in range(5):
            enforcer.record_llm_usage("tenant_001", tokens=100, cost=0.001)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_llm_quota("tenant_001", tokens=100, estimated_cost=0.001)
        
        assert exc_info.value.quota_type == "llm_requests"

    def test_llm_quota_cost_exceeded(self):
        """Test LLM quota check when cost per day exceeds limit."""
        config = QuotaConfig(tenant_id="tenant_001", llm_cost_per_day=10.0)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        enforcer.record_llm_usage("tenant_001", tokens=1000, cost=10.0)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_llm_quota("tenant_001", tokens=100, estimated_cost=0.01)
        
        assert exc_info.value.quota_type == "llm_cost"

    def test_vector_quota_check_passes(self):
        """Test vector quota check when under limits."""
        enforcer = QuotaEnforcer()
        
        # Should not raise
        enforcer.check_vector_quota("tenant_001", query_count=1)
        enforcer.record_vector_usage("tenant_001", query_count=1)

    def test_vector_quota_queries_exceeded(self):
        """Test vector quota check when queries per minute exceed limit."""
        config = QuotaConfig(tenant_id="tenant_001", vector_queries_per_minute=5)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        for _ in range(5):
            enforcer.record_vector_usage("tenant_001", query_count=1)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_vector_quota("tenant_001", query_count=1)
        
        assert exc_info.value.quota_type == "vector_queries"

    def test_vector_quota_storage_exceeded(self):
        """Test vector quota check when storage exceeds limit."""
        config = QuotaConfig(tenant_id="tenant_001", vector_storage_mb=100)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        enforcer.record_vector_usage("tenant_001", storage_mb_delta=100.0)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_vector_quota("tenant_001", storage_mb_delta=1.0)
        
        assert exc_info.value.quota_type == "vector_storage"

    def test_tool_quota_check_passes(self):
        """Test tool quota check when under limits."""
        enforcer = QuotaEnforcer()
        
        # Should not raise
        enforcer.check_tool_quota("tenant_001", "test_tool", estimated_exec_time_ms=1000)
        enforcer.record_tool_usage("tenant_001", "test_tool", actual_exec_time_ms=1000)

    def test_tool_quota_calls_exceeded(self):
        """Test tool quota check when calls per minute exceed limit."""
        config = QuotaConfig(tenant_id="tenant_001", tool_calls_per_minute=5)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        for _ in range(5):
            enforcer.record_tool_usage("tenant_001", "test_tool", actual_exec_time_ms=100)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_tool_quota("tenant_001", "test_tool", estimated_exec_time_ms=100)
        
        assert exc_info.value.quota_type == "tool_calls"

    def test_tool_quota_exec_time_exceeded(self):
        """Test tool quota check when execution time per minute exceeds limit."""
        config = QuotaConfig(tenant_id="tenant_001", tool_exec_time_ms_per_minute=5000)
        enforcer = QuotaEnforcer(default_config=config)
        
        # Use up quota
        enforcer.record_tool_usage("tenant_001", "test_tool", actual_exec_time_ms=5000)
        
        # Should raise QuotaExceeded
        with pytest.raises(QuotaExceeded) as exc_info:
            enforcer.check_tool_quota("tenant_001", "test_tool", estimated_exec_time_ms=1)
        
        assert exc_info.value.quota_type == "tool_exec_time"

    def test_tenant_specific_config(self):
        """Test that tenant-specific configs override defaults."""
        default_config = QuotaConfig(tenant_id="default", llm_tokens_per_day=1000)
        tenant_config = QuotaConfig(tenant_id="tenant_001", llm_tokens_per_day=5000)
        
        enforcer = QuotaEnforcer(
            default_config=default_config,
            tenant_configs={"tenant_001": tenant_config},
        )
        
        # tenant_001 should use its own config
        enforcer.record_llm_usage("tenant_001", tokens=5000, cost=0.01)
        # Should not raise
        enforcer.check_llm_quota("tenant_001", tokens=1, estimated_cost=0.0)
        
        # Other tenant should use default
        enforcer.record_llm_usage("tenant_002", tokens=1000, cost=0.01)
        # Should raise
        with pytest.raises(QuotaExceeded):
            enforcer.check_llm_quota("tenant_002", tokens=1, estimated_cost=0.0)

    def test_per_tenant_isolation(self):
        """Test that quotas are isolated per tenant."""
        enforcer = QuotaEnforcer()
        
        # Use up quota for tenant_001
        config = QuotaConfig(tenant_id="tenant_001", llm_requests_per_minute=5)
        enforcer.tenant_configs["tenant_001"] = config
        
        for _ in range(5):
            enforcer.record_llm_usage("tenant_001", tokens=100, cost=0.001)
        
        # tenant_001 should be blocked
        with pytest.raises(QuotaExceeded):
            enforcer.check_llm_quota("tenant_001", tokens=100, estimated_cost=0.001)
        
        # tenant_002 should still work (different quota)
        enforcer.check_llm_quota("tenant_002", tokens=100, estimated_cost=0.001)

    def test_get_usage_summary(self):
        """Test getting usage summary."""
        enforcer = QuotaEnforcer()
        
        # Record some usage
        enforcer.record_llm_usage("tenant_001", tokens=1000, cost=1.0)
        enforcer.record_vector_usage("tenant_001", query_count=10)
        enforcer.record_tool_usage("tenant_001", "test_tool", actual_exec_time_ms=5000)
        
        summary = enforcer.get_usage_summary("tenant_001")
        
        assert summary["tenant_id"] == "tenant_001"
        assert summary["llm"]["tokens_today"] == 1000
        assert summary["llm"]["cost_today"] == 1.0
        assert summary["vector"]["queries_current_minute"] == 10
        assert summary["tool"]["exec_time_ms_current_minute"] == 5000

    def test_persist_usage_snapshot(self, tmp_path):
        """Test persisting usage snapshot."""
        enforcer = QuotaEnforcer(storage_dir=str(tmp_path))
        
        # Record usage
        enforcer.record_llm_usage("tenant_001", tokens=1000, cost=1.0)
        
        # Persist snapshot
        enforcer.persist_usage_snapshot("tenant_001")
        
        # Check file was created
        usage_file = tmp_path / "tenant_001_usage.jsonl"
        assert usage_file.exists()
        
        # Check content
        with open(usage_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            assert len(lines) == 1
            import json
            data = json.loads(lines[0])
            assert data["tenant_id"] == "tenant_001"
            assert data["llm_tokens_today"] == 1000

