"""
Tool invocation interface with HTTP support and sandboxing.
Matches specification from docs/02-modules-components.md and phase1-mvp-issues.md Issue 12.
"""

import logging
from typing import Any

import httpx

from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack
from src.tools.registry import AllowListEnforcer, ToolRegistry, ToolRegistryError

logger = logging.getLogger(__name__)


class ToolInvocationError(Exception):
    """Raised when tool invocation fails."""

    pass


class ToolInvoker:
    """
    Tool invoker that executes allow-listed tools via HTTP.
    
    MVP supports HTTP tools only (no gRPC yet).
    Enforces tenant allow-lists and provides sandbox behavior via dry_run.
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        audit_logger: AuditLogger | None = None,
    ):
        """
        Initialize the tool invoker.
        
        Args:
            tool_registry: ToolRegistry for validation and allow-list enforcement
            audit_logger: Optional AuditLogger for logging tool invocations
        """
        self.tool_registry = tool_registry
        self.audit_logger = audit_logger
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=30.0)
        return self._http_client

    async def close(self) -> None:
        """Close HTTP client."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

    async def invoke(
        self,
        tool_name: str,
        args: dict[str, Any],
        tenant_policy: TenantPolicyPack,
        domain_pack: DomainPack,
        tenant_id: str,
        dry_run: bool = True,
    ) -> dict[str, Any]:
        """
        Invoke a tool with given arguments.
        
        Args:
            tool_name: Name of the tool to invoke
            args: Arguments to pass to the tool
            tenant_policy: Tenant Policy Pack for allow-list enforcement
            domain_pack: Domain Pack containing tool definitions
            tenant_id: Tenant identifier
            dry_run: If True, skip real call and return mock response (default: True for MVP)
            
        Returns:
            Tool execution result dictionary
            
        Raises:
            ToolInvocationError: If tool invocation fails
            ToolRegistryError: If tool validation fails
        """
        # Validate tool exists in DomainPack.tools
        if tool_name not in domain_pack.tools:
            error_msg = (
                f"Tool '{tool_name}' not found in Domain Pack. "
                f"Available tools: {sorted(domain_pack.tools.keys())}"
            )
            logger.error(error_msg)
            self._audit_log_invocation(tool_name, args, None, error_msg, tenant_id)
            raise ToolInvocationError(error_msg)
        
        tool_def = domain_pack.tools[tool_name]
        
        # Enforce tenant allow-list via AllowListEnforcer
        enforcer = AllowListEnforcer(tenant_policy)
        if not enforcer.is_allowed(tool_name):
            error_msg = (
                f"Tool '{tool_name}' is not in allow-list for tenant {tenant_id}. "
                f"Approved tools: {sorted(enforcer.get_approved_tools())}"
            )
            logger.error(error_msg)
            self._audit_log_invocation(tool_name, args, None, error_msg, tenant_id)
            raise ToolInvocationError(error_msg)
        
        # Validate tool access via registry (double-check)
        try:
            self.tool_registry.validate_tool_access(tenant_id, tool_name)
        except ToolRegistryError as e:
            error_msg = f"Tool registry validation failed: {str(e)}"
            logger.error(error_msg)
            self._audit_log_invocation(tool_name, args, None, error_msg, tenant_id)
            raise ToolInvocationError(error_msg) from e
        
        # Perform HTTP call (or mock if dry_run)
        if dry_run:
            logger.info(f"DRY RUN: Would invoke tool '{tool_name}' with args: {args}")
            mock_response = {
                "status": "success",
                "dry_run": True,
                "tool": tool_name,
                "message": "Dry run mode - no actual tool invocation performed",
                "mock_result": {
                    "executed": True,
                    "parameters": args,
                    "endpoint": tool_def.endpoint,
                },
            }
            self._audit_log_invocation(tool_name, args, mock_response, None, tenant_id)
            return mock_response
        
        # Real HTTP invocation
        try:
            logger.info(f"Invoking tool '{tool_name}' at endpoint: {tool_def.endpoint}")
            
            client = await self._get_http_client()
            
            # Perform HTTP POST request (MVP assumes POST for all tools)
            response = await client.post(
                tool_def.endpoint,
                json=args,
                headers={"Content-Type": "application/json"},
            )
            
            # Raise for HTTP errors
            response.raise_for_status()
            
            # Parse response
            result = {
                "status": "success",
                "tool": tool_name,
                "http_status": response.status_code,
                "response": response.json() if response.content else {},
            }
            
            logger.info(f"Tool '{tool_name}' invocation successful: {result}")
            self._audit_log_invocation(tool_name, args, result, None, tenant_id)
            
            return result
            
        except httpx.HTTPStatusError as e:
            error_msg = f"HTTP error invoking tool '{tool_name}': {e.response.status_code} - {e.response.text}"
            logger.error(error_msg)
            self._audit_log_invocation(tool_name, args, None, error_msg, tenant_id)
            raise ToolInvocationError(error_msg) from e
        except httpx.RequestError as e:
            error_msg = f"Request error invoking tool '{tool_name}': {str(e)}"
            logger.error(error_msg)
            self._audit_log_invocation(tool_name, args, None, error_msg, tenant_id)
            raise ToolInvocationError(error_msg) from e
        except Exception as e:
            error_msg = f"Unexpected error invoking tool '{tool_name}': {str(e)}"
            logger.error(error_msg)
            self._audit_log_invocation(tool_name, args, None, error_msg, tenant_id)
            raise ToolInvocationError(error_msg) from e

    def _audit_log_invocation(
        self,
        tool_name: str,
        args: dict[str, Any],
        response: dict[str, Any] | None,
        error: str | None,
        tenant_id: str,
    ) -> None:
        """
        Log tool invocation to audit logger.
        
        Args:
            tool_name: Name of the tool
            args: Arguments passed to tool
            response: Tool response (if successful)
            error: Error message (if failed)
            tenant_id: Tenant identifier
        """
        if not self.audit_logger:
            return
        
        audit_data = {
            "tool_name": tool_name,
            "args": args,
            "tenant_id": tenant_id,
        }
        
        if response:
            audit_data["response"] = response
            audit_data["status"] = "success"
        else:
            audit_data["error"] = error
            audit_data["status"] = "error"
        
        try:
            self.audit_logger.log_decision("tool_invocation", audit_data, tenant_id)
        except Exception as e:
            logger.warning(f"Failed to audit log tool invocation: {e}")
