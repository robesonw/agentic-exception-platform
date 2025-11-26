"""
Advanced Tool Execution Engine with retry, timeout, circuit breaker, and validation.

Phase 2 implementation:
- Retry logic with exponential backoff
- Timeout management per tool
- Circuit breaker pattern (open/half-open/closed)
- Result schema validation
- Async and sync execution modes
- Comprehensive audit logging

Matches specification from docs/08-security-compliance.md and phase2-mvp-issues.md Issue 25.
"""

import asyncio
import logging
import time
from enum import Enum
from threading import Lock
from typing import Any, Callable, Optional

import httpx

from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ToolDefinition
from src.models.tenant_policy import TenantPolicyPack

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation, requests pass through
    OPEN = "open"  # Failing, requests fail immediately
    HALF_OPEN = "half_open"  # Testing if service recovered


class ToolExecutionError(Exception):
    """Raised when tool execution fails."""

    pass


class CircuitBreakerOpenError(ToolExecutionError):
    """Raised when circuit breaker is open."""

    pass


class ToolTimeoutError(ToolExecutionError):
    """Raised when tool execution times out."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation for tool execution.
    
    Prevents cascading failures by stopping requests to failing tools.
    States:
    - CLOSED: Normal operation
    - OPEN: Failing, reject requests immediately
    - HALF_OPEN: Testing recovery
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 2,
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery (half-open)
            success_threshold: Number of successes in half-open to close circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self._lock = Lock()

    def record_success(self) -> None:
        """Record a successful execution."""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    logger.info("Circuit breaker closed after successful recovery")
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed execution."""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Any failure in half-open immediately opens circuit
                self.state = CircuitState.OPEN
                self.success_count = 0
                logger.warning("Circuit breaker opened after failure in half-open state")
            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(
                        f"Circuit breaker opened after {self.failure_count} failures"
                    )

    def can_execute(self) -> bool:
        """
        Check if execution is allowed.
        
        Returns:
            True if execution is allowed, False otherwise
        """
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                # Check if recovery timeout has passed
                if (
                    self.last_failure_time
                    and time.time() - self.last_failure_time >= self.recovery_timeout
                ):
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    logger.info("Circuit breaker entering half-open state for recovery test")
                    return True
                return False
            
            # HALF_OPEN state - allow execution to test recovery
            return True

    def get_state(self) -> CircuitState:
        """Get current circuit breaker state."""
        with self._lock:
            return self.state


class ToolExecutionEngine:
    """
    Advanced tool execution engine with retry, timeout, circuit breaker, and validation.
    
    Supports both sync and async execution modes.
    """

    def __init__(
        self,
        audit_logger: Optional[AuditLogger] = None,
        default_timeout: float = 30.0,
        default_max_retries: int = 3,
        circuit_breaker_failure_threshold: int = 5,
        circuit_breaker_recovery_timeout: float = 60.0,
    ):
        """
        Initialize the execution engine.
        
        Args:
            audit_logger: Optional audit logger for execution tracking
            default_timeout: Default timeout in seconds
            default_max_retries: Default maximum retry attempts
            circuit_breaker_failure_threshold: Failures before opening circuit
            circuit_breaker_recovery_timeout: Seconds before attempting recovery
        """
        self.audit_logger = audit_logger
        self.default_timeout = default_timeout
        self.default_max_retries = default_max_retries
        self.circuit_breaker_failure_threshold = circuit_breaker_failure_threshold
        self.circuit_breaker_recovery_timeout = circuit_breaker_recovery_timeout
        
        # Per-tool circuit breakers: tool_name -> CircuitBreaker
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._circuit_breaker_lock = Lock()
        
        # HTTP client for async execution
        self._async_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None

    def _get_circuit_breaker(self, tool_name: str) -> CircuitBreaker:
        """
        Get or create circuit breaker for a tool.
        
        Args:
            tool_name: Tool name identifier
            
        Returns:
            CircuitBreaker instance for the tool
        """
        with self._circuit_breaker_lock:
            if tool_name not in self._circuit_breakers:
                self._circuit_breakers[tool_name] = CircuitBreaker(
                    failure_threshold=self.circuit_breaker_failure_threshold,
                    recovery_timeout=self.circuit_breaker_recovery_timeout,
                )
            return self._circuit_breakers[tool_name]

    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(timeout=self.default_timeout)
        return self._async_client

    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(timeout=self.default_timeout)
        return self._sync_client

    async def close(self) -> None:
        """Close HTTP clients."""
        if self._async_client:
            await self._async_client.aclose()
            self._async_client = None
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None

    def _calculate_backoff(self, attempt: int, base_delay: float = 1.0) -> float:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Retry attempt number (0-indexed)
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds
        """
        return base_delay * (2 ** attempt)

    def _validate_result_schema(
        self, result: dict[str, Any], tool_def: ToolDefinition
    ) -> None:
        """
        Validate tool result against expected schema if defined.
        
        Args:
            result: Tool execution result
            tool_def: Tool definition with schema information
            
        Raises:
            ToolExecutionError: If validation fails
        """
        # For MVP, basic validation - check if result is a dict
        # In production, could use JSON Schema validation
        if not isinstance(result, dict):
            raise ToolExecutionError(
                f"Tool result must be a dictionary, got {type(result).__name__}"
            )
        
        # If tool definition has return schema info, validate
        # (This is a placeholder - full schema validation would go here)
        logger.debug(f"Result validation passed for tool (basic check)")

    async def _execute_async(
        self,
        tool_def: ToolDefinition,
        args: dict[str, Any],
        timeout: Optional[float],
    ) -> dict[str, Any]:
        """
        Execute tool asynchronously via HTTP.
        
        Args:
            tool_def: Tool definition
            args: Tool arguments
            timeout: Request timeout in seconds
            
        Returns:
            Tool execution result
            
        Raises:
            ToolTimeoutError: If execution times out
            ToolExecutionError: If execution fails
        """
        client = await self._get_async_client()
        request_timeout = timeout or tool_def.timeout_seconds or self.default_timeout
        
        try:
            # Use asyncio.wait_for for timeout control
            response = await asyncio.wait_for(
                client.post(
                    tool_def.endpoint,
                    json=args,
                    headers={"Content-Type": "application/json"},
                    timeout=request_timeout,
                ),
                timeout=request_timeout,
            )
            
            response.raise_for_status()
            
            result = {
                "status": "success",
                "tool": tool_def.endpoint,
                "http_status": response.status_code,
                "response": response.json() if response.content else {},
            }
            
            return result
            
        except asyncio.TimeoutError:
            raise ToolTimeoutError(
                f"Tool execution timed out after {request_timeout} seconds"
            )
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(
                f"HTTP error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ToolExecutionError(f"Request error: {str(e)}")

    def _execute_sync(
        self,
        tool_def: ToolDefinition,
        args: dict[str, Any],
        timeout: Optional[float],
    ) -> dict[str, Any]:
        """
        Execute tool synchronously via HTTP.
        
        Args:
            tool_def: Tool definition
            args: Tool arguments
            timeout: Request timeout in seconds
            
        Returns:
            Tool execution result
            
        Raises:
            ToolTimeoutError: If execution times out
            ToolExecutionError: If execution fails
        """
        client = self._get_sync_client()
        request_timeout = timeout or tool_def.timeout_seconds or self.default_timeout
        
        try:
            response = client.post(
                tool_def.endpoint,
                json=args,
                headers={"Content-Type": "application/json"},
                timeout=request_timeout,
            )
            
            response.raise_for_status()
            
            result = {
                "status": "success",
                "tool": tool_def.endpoint,
                "http_status": response.status_code,
                "response": response.json() if response.content else {},
            }
            
            return result
            
        except httpx.TimeoutException:
            raise ToolTimeoutError(
                f"Tool execution timed out after {request_timeout} seconds"
            )
        except httpx.HTTPStatusError as e:
            raise ToolExecutionError(
                f"HTTP error: {e.response.status_code} - {e.response.text}"
            )
        except httpx.RequestError as e:
            raise ToolExecutionError(f"Request error: {str(e)}")

    def _audit_log_attempt(
        self,
        tool_name: str,
        args: dict[str, Any],
        attempt: int,
        result: Optional[dict[str, Any]],
        error: Optional[str],
        tenant_id: str,
    ) -> None:
        """
        Log tool execution attempt to audit logger.
        
        Args:
            tool_name: Tool name
            args: Tool arguments
            attempt: Attempt number (0-indexed)
            result: Execution result (if successful)
            error: Error message (if failed)
            tenant_id: Tenant identifier
        """
        if not self.audit_logger:
            return
        
        audit_data = {
            "tool_name": tool_name,
            "args": args,
            "attempt": attempt + 1,
            "tenant_id": tenant_id,
        }
        
        if result:
            audit_data["result"] = result
            audit_data["status"] = "success"
        else:
            audit_data["error"] = error
            audit_data["status"] = "error"
        
        try:
            self.audit_logger.log_decision("tool_execution_attempt", audit_data, tenant_id)
        except Exception as e:
            logger.warning(f"Failed to audit log tool execution attempt: {e}")

    async def execute(
        self,
        tool_name: str,
        args: dict[str, Any],
        tenant_policy: TenantPolicyPack,
        domain_pack: DomainPack,
        tenant_id: str,
        mode: str = "sync",
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Execute a tool with retry, timeout, circuit breaker, and validation.
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            tenant_policy: Tenant Policy Pack for validation
            domain_pack: Domain Pack containing tool definition
            tenant_id: Tenant identifier
            mode: Execution mode ("sync" or "async")
            timeout: Override timeout in seconds (uses tool definition if None)
            
        Returns:
            Tool execution result dictionary
            
        Raises:
            ToolExecutionError: If execution fails after all retries
            CircuitBreakerOpenError: If circuit breaker is open
            ToolTimeoutError: If execution times out
        """
        # Validate tool exists
        if tool_name not in domain_pack.tools:
            error_msg = (
                f"Tool '{tool_name}' not found in Domain Pack. "
                f"Available tools: {sorted(domain_pack.tools.keys())}"
            )
            self._audit_log_attempt(tool_name, args, 0, None, error_msg, tenant_id)
            raise ToolExecutionError(error_msg)
        
        tool_def = domain_pack.tools[tool_name]
        
        # Get tool overrides from tenant policy if available
        max_retries = tool_def.max_retries
        tool_timeout = timeout or tool_def.timeout_seconds
        
        # Check for tool overrides in tenant policy
        if hasattr(tenant_policy, "tool_overrides"):
            for override in tenant_policy.tool_overrides:
                if override.tool_name == tool_name:
                    if override.max_retries is not None:
                        max_retries = override.max_retries
                    if override.timeout_seconds is not None:
                        tool_timeout = override.timeout_seconds
                    break
        
        # Check circuit breaker
        circuit_breaker = self._get_circuit_breaker(tool_name)
        if not circuit_breaker.can_execute():
            error_msg = f"Circuit breaker is OPEN for tool '{tool_name}'"
            self._audit_log_attempt(tool_name, args, 0, None, error_msg, tenant_id)
            raise CircuitBreakerOpenError(error_msg)
        
        # Execute with retries
        last_error: Optional[Exception] = None
        
        for attempt in range(max_retries + 1):  # +1 for initial attempt
            try:
                # Execute based on mode
                if mode == "async":
                    result = await self._execute_async(tool_def, args, tool_timeout)
                else:
                    # Run sync execution in thread pool for async compatibility
                    result = await asyncio.to_thread(
                        self._execute_sync, tool_def, args, tool_timeout
                    )
                
                # Validate result schema
                self._validate_result_schema(result, tool_def)
                
                # Record success in circuit breaker
                circuit_breaker.record_success()
                
                # Audit log success
                self._audit_log_attempt(
                    tool_name, args, attempt, result, None, tenant_id
                )
                
                logger.info(
                    f"Tool '{tool_name}' executed successfully on attempt {attempt + 1}"
                )
                return result
                
            except (ToolTimeoutError, ToolExecutionError) as e:
                last_error = e
                
                # Audit log failure
                self._audit_log_attempt(
                    tool_name, args, attempt, None, str(e), tenant_id
                )
                
                # Record failure in circuit breaker
                circuit_breaker.record_failure()
                
                # If not last attempt, wait with exponential backoff
                if attempt < max_retries:
                    backoff_delay = self._calculate_backoff(attempt)
                    logger.warning(
                        f"Tool '{tool_name}' failed on attempt {attempt + 1}, "
                        f"retrying in {backoff_delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(backoff_delay)
                else:
                    logger.error(
                        f"Tool '{tool_name}' failed after {max_retries + 1} attempts: {e}"
                    )
        
        # All retries exhausted
        error_msg = (
            f"Tool '{tool_name}' execution failed after {max_retries + 1} attempts: {last_error}"
        )
        raise ToolExecutionError(error_msg) from last_error

    def execute_sync(
        self,
        tool_name: str,
        args: dict[str, Any],
        tenant_policy: TenantPolicyPack,
        domain_pack: DomainPack,
        tenant_id: str,
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Execute a tool synchronously (blocking).
        
        This is a convenience wrapper that runs async execute in event loop.
        Note: This method should not be called from within an async context.
        Use execute() with mode="sync" instead when in async context.
        
        Args:
            tool_name: Name of the tool to execute
            args: Tool arguments
            tenant_policy: Tenant Policy Pack for validation
            domain_pack: Domain Pack containing tool definition
            tenant_id: Tenant identifier
            timeout: Override timeout in seconds
            
        Returns:
            Tool execution result dictionary
        """
        # Check if we're in an async context
        try:
            asyncio.get_running_loop()
            # If we're in an async context, raise an error
            # User should use execute() with mode="sync" instead
            raise RuntimeError(
                "execute_sync() cannot be called from within an async context. "
                "Use execute() with mode='sync' instead."
            )
        except RuntimeError as e:
            # Check if this is our error or the "no running loop" error
            if "cannot be called from within an async context" in str(e):
                raise
            # No running loop, safe to create new one
            pass
        
        # Create new event loop for sync execution
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.execute(
                    tool_name, args, tenant_policy, domain_pack, tenant_id, mode="sync", timeout=timeout
                )
            )
        finally:
            loop.close()

