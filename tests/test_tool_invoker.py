"""
Tests for ToolInvoker.
Tests tool invocation, allow-list enforcement, dry_run, and audit logging.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.models.domain_pack import DomainPack, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack
from src.tools.invoker import ToolInvocationError, ToolInvoker
from src.tools.registry import AllowListEnforcer, ToolRegistry, ToolRegistryError


@pytest.fixture
def sample_domain_pack():
    """Sample domain pack with tools."""
    return DomainPack(
        domainName="test_domain",
        tools={
            "tool1": ToolDefinition(
                description="Test tool 1",
                parameters={"param1": "string"},
                endpoint="https://api.example.com/tool1",
            ),
            "tool2": ToolDefinition(
                description="Test tool 2",
                parameters={"param2": "number"},
                endpoint="https://api.example.com/tool2",
            ),
        },
    )


@pytest.fixture
def sample_tenant_policy():
    """Sample tenant policy with approved tools."""
    return TenantPolicyPack(
        tenantId="TENANT_001",
        domainName="test_domain",
        approvedTools=["tool1"],  # Only tool1 is approved
    )


@pytest.fixture
def tool_registry(sample_domain_pack, sample_tenant_policy):
    """Tool registry with domain pack and policy pack registered."""
    registry = ToolRegistry()
    registry.register_domain_pack("TENANT_001", sample_domain_pack)
    registry.register_policy_pack("TENANT_001", sample_tenant_policy)
    return registry


@pytest.fixture
def audit_logger():
    """Mock audit logger."""
    logger = MagicMock()
    logger.log_decision = MagicMock()
    return logger


@pytest.fixture
def tool_invoker(tool_registry, audit_logger):
    """Tool invoker instance."""
    return ToolInvoker(tool_registry=tool_registry, audit_logger=audit_logger)


class TestToolInvokerValidation:
    """Tests for tool validation."""

    @pytest.mark.asyncio
    async def test_invoke_validates_tool_exists(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that tool must exist in domain pack."""
        with pytest.raises(ToolInvocationError) as exc_info:
            await tool_invoker.invoke(
                tool_name="nonexistent_tool",
                args={},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="TENANT_001",
            )
        
        assert "not found in Domain Pack" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invoke_enforces_allow_list(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that tool must be in allow-list."""
        # tool2 is not in approved tools
        with pytest.raises(ToolInvocationError) as exc_info:
            await tool_invoker.invoke(
                tool_name="tool2",
                args={},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="TENANT_001",
            )
        
        assert "not in allow-list" in str(exc_info.value)
        assert "tool2" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_invoke_validates_via_registry(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that tool registry validation is checked."""
        # Mock registry to raise error
        tool_invoker.tool_registry.validate_tool_access = MagicMock(
            side_effect=ToolRegistryError("Registry validation failed")
        )
        
        with pytest.raises(ToolInvocationError) as exc_info:
            await tool_invoker.invoke(
                tool_name="tool1",
                args={},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="TENANT_001",
            )
        
        assert "Registry validation failed" in str(exc_info.value)


class TestToolInvokerDryRun:
    """Tests for dry_run mode."""

    @pytest.mark.asyncio
    async def test_dry_run_returns_mock_response(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that dry_run returns mock response without HTTP call."""
        result = await tool_invoker.invoke(
            tool_name="tool1",
            args={"param1": "value1"},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
            tenant_id="TENANT_001",
            dry_run=True,
        )
        
        assert result["status"] == "success"
        assert result["dry_run"] is True
        assert result["tool"] == "tool1"
        assert "mock_result" in result
        assert result["mock_result"]["parameters"] == {"param1": "value1"}

    @pytest.mark.asyncio
    async def test_dry_run_defaults_to_true(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that dry_run defaults to True (MVP behavior)."""
        result = await tool_invoker.invoke(
            tool_name="tool1",
            args={},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
            tenant_id="TENANT_001",
            # dry_run not specified, should default to True
        )
        
        assert result["dry_run"] is True


class TestToolInvokerHTTP:
    """Tests for HTTP tool invocation."""

    @pytest.mark.asyncio
    async def test_invoke_performs_http_post(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that real invocation performs HTTP POST."""
        # Configure tool to have no retries for this test
        sample_domain_pack.tools["tool1"].max_retries = 0
        
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.content = b'{"result": "success"}'
        mock_response.raise_for_status = MagicMock()
        
        # Mock both async and sync clients (execution engine may use either)
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_async_post, \
             patch("httpx.Client.post") as mock_sync_post:
            mock_async_post.return_value = mock_response
            mock_sync_post.return_value = mock_response
            
            result = await tool_invoker.invoke(
                tool_name="tool1",
                args={"param1": "value1"},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="TENANT_001",
                dry_run=False,
                mode="async",  # Use async mode
            )
            
            # Verify HTTP call was made (either async or sync)
            total_calls = mock_async_post.call_count + mock_sync_post.call_count
            assert total_calls >= 1
            
            # Verify result
            assert result["status"] == "success"
            assert result["http_status"] == 200
            assert "response" in result

    @pytest.mark.asyncio
    async def test_invoke_handles_http_errors(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that HTTP errors are handled."""
        import httpx
        
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status = MagicMock(side_effect=httpx.HTTPStatusError("Server Error", request=MagicMock(), response=mock_response))
        
        # Configure tool to have no retries for this test
        sample_domain_pack.tools["tool1"].max_retries = 0
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_response
            
            with pytest.raises(ToolInvocationError) as exc_info:
                await tool_invoker.invoke(
                    tool_name="tool1",
                    args={},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=sample_domain_pack,
                    tenant_id="TENANT_001",
                    dry_run=False,
                )
            
            # Error message may contain "HTTP error" or "execution failed" depending on execution engine
            error_str = str(exc_info.value)
            assert "error" in error_str.lower() or "failed" in error_str.lower()

    @pytest.mark.asyncio
    async def test_invoke_handles_request_errors(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that request errors are handled."""
        import httpx
        
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.RequestError("Connection failed")
            
            with pytest.raises(ToolInvocationError) as exc_info:
                await tool_invoker.invoke(
                    tool_name="tool1",
                    args={},
                    tenant_policy=sample_tenant_policy,
                    domain_pack=sample_domain_pack,
                    tenant_id="TENANT_001",
                    dry_run=False,
                )
            
            assert "Request error" in str(exc_info.value)


class TestToolInvokerAuditLogging:
    """Tests for audit logging."""

    @pytest.mark.asyncio
    async def test_audit_logs_successful_invocation(self, tool_invoker, sample_tenant_policy, sample_domain_pack, audit_logger):
        """Test that successful invocation is audit logged."""
        await tool_invoker.invoke(
            tool_name="tool1",
            args={"param1": "value1"},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
            tenant_id="TENANT_001",
            dry_run=True,
        )
        
        # Verify audit log was called
        audit_logger.log_decision.assert_called_once()
        call_args = audit_logger.log_decision.call_args
        
        assert call_args[0][0] == "tool_invocation"
        assert call_args[0][1]["tool_name"] == "tool1"
        assert call_args[0][1]["args"] == {"param1": "value1"}
        assert call_args[0][1]["tenant_id"] == "TENANT_001"
        assert call_args[0][1]["status"] == "success"
        assert "response" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_audit_logs_failed_invocation(self, tool_invoker, sample_tenant_policy, sample_domain_pack, audit_logger):
        """Test that failed invocation is audit logged."""
        with pytest.raises(ToolInvocationError):
            await tool_invoker.invoke(
                tool_name="nonexistent_tool",
                args={},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="TENANT_001",
            )
        
        # Verify audit log was called with error
        audit_logger.log_decision.assert_called_once()
        call_args = audit_logger.log_decision.call_args
        
        assert call_args[0][0] == "tool_invocation"
        assert call_args[0][1]["status"] == "error"
        assert "error" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_audit_logs_without_logger(self, tool_registry, sample_tenant_policy, sample_domain_pack):
        """Test that invocation works without audit logger."""
        invoker = ToolInvoker(tool_registry=tool_registry, audit_logger=None)
        
        result = await invoker.invoke(
            tool_name="tool1",
            args={},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
            tenant_id="TENANT_001",
            dry_run=True,
        )
        
        assert result["status"] == "success"


class TestToolInvokerAllowList:
    """Tests for allow-list enforcement."""

    @pytest.mark.asyncio
    async def test_allow_list_blocks_forbidden_tools(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that allow-list blocks forbidden tools."""
        # tool2 is not in approved tools
        with pytest.raises(ToolInvocationError) as exc_info:
            await tool_invoker.invoke(
                tool_name="tool2",
                args={},
                tenant_policy=sample_tenant_policy,
                domain_pack=sample_domain_pack,
                tenant_id="TENANT_001",
            )
        
        assert "not in allow-list" in str(exc_info.value)
        assert "Approved tools" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_allow_list_allows_approved_tools(self, tool_invoker, sample_tenant_policy, sample_domain_pack):
        """Test that allow-list allows approved tools."""
        result = await tool_invoker.invoke(
            tool_name="tool1",
            args={},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
            tenant_id="TENANT_001",
            dry_run=True,
        )
        
        assert result["status"] == "success"


class TestToolInvokerIntegration:
    """Integration tests for tool invoker."""

    @pytest.mark.asyncio
    async def test_full_invocation_flow(self, tool_invoker, sample_tenant_policy, sample_domain_pack, audit_logger):
        """Test full invocation flow with validation and execution."""
        result = await tool_invoker.invoke(
            tool_name="tool1",
            args={"param1": "test_value"},
            tenant_policy=sample_tenant_policy,
            domain_pack=sample_domain_pack,
            tenant_id="TENANT_001",
            dry_run=True,
        )
        
        # Verify result structure
        assert result["status"] == "success"
        assert result["tool"] == "tool1"
        assert result["dry_run"] is True
        
        # Verify audit logging
        audit_logger.log_decision.assert_called_once()
        
        # Verify parameters were passed
        assert result["mock_result"]["parameters"] == {"param1": "test_value"}

    @pytest.mark.asyncio
    async def test_invoker_close(self, tool_invoker):
        """Test that invoker can be closed."""
        await tool_invoker.close()
        
        # Verify execution engine is closed (if using execution engine)
        if tool_invoker.use_execution_engine and tool_invoker.execution_engine:
            assert tool_invoker.execution_engine._async_client is None
        # Or verify HTTP client is closed (if using legacy mode)
        elif hasattr(tool_invoker, "_http_client"):
            assert tool_invoker._http_client is None

