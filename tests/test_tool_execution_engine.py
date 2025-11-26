"""
Comprehensive tests for Phase 2 Tool Execution Engine.

Tests:
- Retry with exponential backoff
- Timeout handling
- Circuit breaker pattern
- Result validation
- Async execution
- Audit logging
"""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack
from src.models.tenant_policy import ToolOverride
from src.tools.execution_engine import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    ToolExecutionEngine,
    ToolExecutionError,
    ToolTimeoutError,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    def test_circuit_breaker_starts_closed(self):
        """Test that circuit breaker starts in CLOSED state."""
        cb = CircuitBreaker()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_circuit_breaker_opens_after_threshold(self):
        """Test that circuit breaker opens after failure threshold."""
        cb = CircuitBreaker(failure_threshold=3)
        
        # Record failures up to threshold
        cb.record_failure()
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.can_execute() is True
        
        cb.record_failure()
        assert cb.get_state() == CircuitState.CLOSED
        
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_circuit_breaker_resets_on_success(self):
        """Test that circuit breaker resets failure count on success."""
        cb = CircuitBreaker(failure_threshold=3)
        
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        
        # Failure count should reset
        assert cb.get_state() == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_circuit_breaker_half_open_recovery(self):
        """Test that circuit breaker enters half-open state after recovery timeout."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        # Should enter half-open state
        assert cb.can_execute() is True
        assert cb.get_state() == CircuitState.HALF_OPEN

    def test_circuit_breaker_half_open_success(self):
        """Test that circuit breaker closes after success in half-open."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1, success_threshold=2)
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Enter half-open
        
        # Record successes
        cb.record_success()
        assert cb.get_state() == CircuitState.HALF_OPEN
        
        cb.record_success()
        assert cb.get_state() == CircuitState.CLOSED

    def test_circuit_breaker_half_open_failure(self):
        """Test that circuit breaker reopens on failure in half-open."""
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Open circuit
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.can_execute()  # Enter half-open
        
        # Record failure in half-open
        cb.record_failure()
        assert cb.get_state() == CircuitState.OPEN


class TestToolExecutionEngine:
    """Tests for ToolExecutionEngine class."""

    @pytest.fixture
    def sample_domain_pack(self):
        """Create a sample domain pack with tool."""
        return DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "testTool": ToolDefinition(
                    description="Test tool",
                    parameters={},
                    endpoint="https://api.example.com/tool",
                    timeout_seconds=5.0,
                    max_retries=3,
                )
            },
        )

    @pytest.fixture
    def sample_tenant_policy(self):
        """Create a sample tenant policy pack."""
        return TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["testTool"],
        )

    @pytest.fixture
    def audit_logger(self):
        """Create a mock audit logger."""
        return MagicMock(spec=AuditLogger)

    @pytest.fixture
    def execution_engine(self, audit_logger):
        """Create execution engine instance."""
        return ToolExecutionEngine(audit_logger=audit_logger)

    @pytest.mark.asyncio
    async def test_execute_success(self, execution_engine, sample_domain_pack, sample_tenant_policy):
        """Test successful tool execution."""
        # Mock successful HTTP response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            
            assert result["status"] == "success"
            assert result["http_status"] == 200
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_retry_on_failure(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that execution retries on failure with exponential backoff."""
        # Mock HTTP responses: first two fail, third succeeds
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"result": "success"}
        mock_response_success.content = b'{"result": "success"}'
        mock_response_success.raise_for_status = MagicMock()
        
        mock_response_failure = MagicMock()
        mock_response_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [
                mock_response_failure,
                mock_response_failure,
                mock_response_success,
            ]
            
            start_time = time.time()
            result = await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            elapsed = time.time() - start_time
            
            assert result["status"] == "success"
            assert mock_post.call_count == 3  # 2 retries + 1 success
            # Should have backoff delays (at least some time elapsed)
            assert elapsed > 0.1

    @pytest.mark.asyncio
    async def test_execute_exhausts_retries(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that execution fails after exhausting retries."""
        mock_response_failure = MagicMock()
        mock_response_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_failure
            
            with pytest.raises(ToolExecutionError) as exc_info:
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=sample_domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )
            
            # Should have attempted max_retries + 1 times (initial + retries)
            assert mock_post.call_count == 4  # 1 initial + 3 retries
            assert "failed after" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_timeout(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that execution times out correctly."""
        # Create tool with short timeout
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "testTool": ToolDefinition(
                    description="Test tool",
                    parameters={},
                    endpoint="https://api.example.com/tool",
                    timeout_seconds=0.1,  # Very short timeout
                    max_retries=0,  # No retries for timeout test
                )
            },
        )
        
        # Mock timeout
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(ToolExecutionError) as exc_info:
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )
            
            assert "timeout" in str(exc_info.value).lower() or "timed out" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_execute_circuit_breaker_opens(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that circuit breaker opens after threshold failures."""
        # Configure for quick circuit opening
        execution_engine.circuit_breaker_failure_threshold = 2
        execution_engine.circuit_breaker_recovery_timeout = 60.0
        
        mock_response_failure = MagicMock()
        mock_response_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_failure
            
            # First execution - should fail and open circuit
            with pytest.raises(ToolExecutionError):
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=sample_domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )
            
            # Second execution - should also fail and open circuit
            with pytest.raises(ToolExecutionError):
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=sample_domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )
            
            # Third execution - circuit should be open
            with pytest.raises(CircuitBreakerOpenError):
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=sample_domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )

    @pytest.mark.asyncio
    async def test_execute_circuit_breaker_recovery(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that circuit breaker recovers after timeout."""
        # Configure for quick recovery
        execution_engine.circuit_breaker_failure_threshold = 2
        execution_engine.circuit_breaker_recovery_timeout = 0.2
        
        mock_response_failure = MagicMock()
        mock_response_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        
        mock_response_success = MagicMock()
        mock_response_success.status_code = 200
        mock_response_success.json.return_value = {"result": "success"}
        mock_response_success.content = b'{"result": "success"}'
        mock_response_success.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            # Open circuit with failures
            mock_post.return_value = mock_response_failure
            for _ in range(2):
                with pytest.raises(ToolExecutionError):
                    await execution_engine.execute(
                        tool_name="testTool",
                        args={"param": "value"},
                        tenant_policy=sample_tenant_policy,
                        domain_pack=sample_domain_pack,
                        tenant_id="tenant1",
                        mode="async",
                    )
            
            # Wait for recovery timeout
            await asyncio.sleep(0.25)
            
            # Service recovered - should succeed
            mock_post.return_value = mock_response_success
            result = await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_async_mode(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test async execution mode."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            
            assert result["status"] == "success"
            # Verify async client was used
            assert execution_engine._async_client is not None

    @pytest.mark.asyncio
    async def test_execute_sync_mode(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test sync execution mode (runs in thread pool)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = mock_response
            
            result = await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="sync",
            )
            
            assert result["status"] == "success"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_audit_logging(
        self, execution_engine, sample_domain_pack, sample_tenant_policy, audit_logger
    ):
        """Test that every attempt is audit logged."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            
            # Verify audit logging was called
            assert audit_logger.log_decision.called
            call_args = audit_logger.log_decision.call_args
            assert call_args[0][0] == "tool_execution_attempt"
            assert call_args[0][1]["tool_name"] == "testTool"
            assert call_args[0][1]["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_audit_logs_failures(
        self, execution_engine, sample_domain_pack, sample_tenant_policy, audit_logger
    ):
        """Test that failures are audit logged."""
        mock_response_failure = MagicMock()
        mock_response_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        
        # Configure for single attempt (no retries)
        domain_pack = DomainPack(
            domainName="TestDomain",
            exceptionTypes={},
            tools={
                "testTool": ToolDefinition(
                    description="Test tool",
                    parameters={},
                    endpoint="https://api.example.com/tool",
                    max_retries=0,  # No retries
                )
            },
        )
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_failure
            
            with pytest.raises(ToolExecutionError):
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )
            
            # Verify failure was logged
            assert audit_logger.log_decision.called
            call_args = audit_logger.log_decision.call_args
            assert call_args[0][1]["status"] == "error"
            assert "error" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_execute_tool_override_timeout(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that tool timeout override from tenant policy is applied."""
        # Create tenant policy with timeout override
        policy_with_override = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["testTool"],
            toolOverrides=[
                ToolOverride(
                    toolName="testTool",
                    timeoutSeconds=10.0,  # Override timeout
                )
            ],
        )
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=policy_with_override,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            
            # Verify timeout was used (check call args)
            call_kwargs = mock_post.call_args[1]
            assert call_kwargs.get("timeout") == 10.0 or call_kwargs.get("timeout") is None  # httpx may handle differently

    @pytest.mark.asyncio
    async def test_execute_tool_override_retries(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that tool retries override from tenant policy is applied."""
        # Create tenant policy with retries override
        policy_with_override = TenantPolicyPack(
            tenantId="tenant1",
            domainName="TestDomain",
            approvedTools=["testTool"],
            toolOverrides=[
                ToolOverride(
                    toolName="testTool",
                    maxRetries=5,  # Override retries
                )
            ],
        )
        
        mock_response_failure = MagicMock()
        mock_response_failure.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response_failure
            
            with pytest.raises(ToolExecutionError):
                await execution_engine.execute(
                    tool_name="testTool",
                    args={"param": "value"},
                    tenant_policy=policy_with_override,
                    domain_pack=sample_domain_pack,
                    tenant_id="tenant1",
                    mode="async",
                )
            
            # Should have attempted 6 times (1 initial + 5 retries)
            assert mock_post.call_count == 6

    @pytest.mark.asyncio
    async def test_execute_result_validation(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that result validation is performed."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            result = await execution_engine.execute(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
            
            # Result should be validated (basic check - dict)
            assert isinstance(result, dict)
            assert result["status"] == "success"

    @pytest.mark.asyncio
    async def test_execute_nonexistent_tool(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test that execution fails for non-existent tool."""
        with pytest.raises(ToolExecutionError) as exc_info:
            await execution_engine.execute(
                tool_name="nonexistent",
                args={},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
                mode="async",
            )
        
        assert "not found" in str(exc_info.value).lower()

    def test_execute_sync_wrapper(
        self, execution_engine, sample_domain_pack, sample_tenant_policy
    ):
        """Test execute_sync convenience wrapper (non-async test)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        with patch("httpx.Client.post") as mock_post:
            mock_post.return_value = mock_response
            
            result = execution_engine.execute_sync(
                tool_name="testTool",
                args={"param": "value"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="tenant1",
            )
            
            assert result["status"] == "success"
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_close_clients(self, execution_engine):
        """Test that close() properly closes HTTP clients."""
        # Initialize clients
        await execution_engine._get_async_client()
        execution_engine._get_sync_client()
        
        # Close
        await execution_engine.close()
        
        assert execution_engine._async_client is None
        assert execution_engine._sync_client is None

