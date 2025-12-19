"""
Worker Health Aggregation Service for Phase 10.

Aggregates health status from all worker instances by polling their
/healthz and /readyz endpoints.

Reference: docs/phase10-ops-governance-mvp.md Section 5.1
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


class WorkerHealthStatus(str, Enum):
    """Worker health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class WorkerInstance:
    """Configuration for a single worker instance."""
    worker_type: str
    instance_id: str
    host: str
    port: int

    @property
    def healthz_url(self) -> str:
        return f"http://{self.host}:{self.port}/healthz"

    @property
    def readyz_url(self) -> str:
        return f"http://{self.host}:{self.port}/readyz"


@dataclass
class WorkerHealthResult:
    """Health check result for a worker instance."""
    worker_type: str
    instance_id: str
    status: WorkerHealthStatus
    healthz_ok: bool
    readyz_ok: bool
    last_check: datetime
    response_time_ms: Optional[float] = None
    error_message: Optional[str] = None


@dataclass
class WorkerHealthCache:
    """Cached health status for a worker."""
    result: WorkerHealthResult
    expires_at: datetime
    consecutive_failures: int = 0


class WorkerHealthService:
    """
    Service to aggregate health status from all worker instances.

    Polls worker /healthz and /readyz endpoints and caches results.
    Workers are marked unhealthy after consecutive failures.
    """

    # Default worker configuration (ports 9001-9007)
    DEFAULT_WORKERS = [
        WorkerInstance("intake", "intake-1", "localhost", 9001),
        WorkerInstance("triage", "triage-1", "localhost", 9002),
        WorkerInstance("policy", "policy-1", "localhost", 9003),
        WorkerInstance("playbook", "playbook-1", "localhost", 9004),
        WorkerInstance("tool", "tool-1", "localhost", 9005),
        WorkerInstance("feedback", "feedback-1", "localhost", 9006),
        WorkerInstance("sla_monitor", "sla_monitor-1", "localhost", 9007),
    ]

    def __init__(
        self,
        workers: Optional[list[WorkerInstance]] = None,
        cache_ttl_seconds: int = 30,
        timeout_seconds: float = 5.0,
        unhealthy_threshold: int = 3,
    ):
        """
        Initialize the worker health service.

        Args:
            workers: List of worker instances to monitor. Defaults to standard workers.
            cache_ttl_seconds: How long to cache health results.
            timeout_seconds: HTTP request timeout.
            unhealthy_threshold: Consecutive failures before marking unhealthy.
        """
        self.workers = workers or self.DEFAULT_WORKERS.copy()
        self.cache_ttl = timedelta(seconds=cache_ttl_seconds)
        self.timeout = timeout_seconds
        self.unhealthy_threshold = unhealthy_threshold
        self._cache: dict[str, WorkerHealthCache] = {}
        self._client: Optional[httpx.AsyncClient] = None

    def _get_cache_key(self, worker: WorkerInstance) -> str:
        """Generate cache key for a worker instance."""
        return f"{worker.worker_type}:{worker.instance_id}"

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    async def close(self):
        """Close HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _check_endpoint(self, url: str) -> tuple[bool, float, Optional[str]]:
        """
        Check a single health endpoint.

        Returns:
            Tuple of (is_ok, response_time_ms, error_message)
        """
        client = await self._get_client()
        start = datetime.utcnow()

        try:
            response = await client.get(url)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000

            if response.status_code == 200:
                return True, elapsed, None
            else:
                return False, elapsed, f"HTTP {response.status_code}"
        except httpx.TimeoutException:
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            return False, elapsed, "Timeout"
        except httpx.ConnectError:
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            return False, elapsed, "Connection refused"
        except Exception as e:
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000
            return False, elapsed, str(e)

    async def check_worker_health(
        self,
        worker: WorkerInstance,
        use_cache: bool = True,
    ) -> WorkerHealthResult:
        """
        Check health of a single worker instance.

        Args:
            worker: Worker instance to check.
            use_cache: Whether to use cached results if available.

        Returns:
            WorkerHealthResult with health status.
        """
        cache_key = self._get_cache_key(worker)
        now = datetime.utcnow()

        # Check cache
        if use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            if cached.expires_at > now:
                return cached.result

        # Perform health checks
        healthz_ok, healthz_time, healthz_error = await self._check_endpoint(
            worker.healthz_url
        )
        readyz_ok, readyz_time, readyz_error = await self._check_endpoint(
            worker.readyz_url
        )

        # Determine overall status
        if healthz_ok and readyz_ok:
            status = WorkerHealthStatus.HEALTHY
            consecutive_failures = 0
        elif healthz_ok and not readyz_ok:
            status = WorkerHealthStatus.DEGRADED
            consecutive_failures = 0
        else:
            # Check consecutive failures for unhealthy determination
            old_cache = self._cache.get(cache_key)
            if old_cache:
                consecutive_failures = old_cache.consecutive_failures + 1
            else:
                consecutive_failures = 1

            if consecutive_failures >= self.unhealthy_threshold:
                status = WorkerHealthStatus.UNHEALTHY
            else:
                status = WorkerHealthStatus.DEGRADED

        # Build result
        error_message = healthz_error or readyz_error
        response_time = max(healthz_time, readyz_time)

        result = WorkerHealthResult(
            worker_type=worker.worker_type,
            instance_id=worker.instance_id,
            status=status,
            healthz_ok=healthz_ok,
            readyz_ok=readyz_ok,
            last_check=now,
            response_time_ms=response_time,
            error_message=error_message,
        )

        # Update cache
        self._cache[cache_key] = WorkerHealthCache(
            result=result,
            expires_at=now + self.cache_ttl,
            consecutive_failures=consecutive_failures,
        )

        return result

    async def get_all_worker_health(
        self,
        use_cache: bool = True,
    ) -> list[WorkerHealthResult]:
        """
        Get health status of all configured workers.

        Args:
            use_cache: Whether to use cached results if available.

        Returns:
            List of WorkerHealthResult for all workers.
        """
        tasks = [
            self.check_worker_health(worker, use_cache=use_cache)
            for worker in self.workers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions
        health_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                worker = self.workers[i]
                logger.error(f"Failed to check health for {worker.worker_type}: {result}")
                health_results.append(WorkerHealthResult(
                    worker_type=worker.worker_type,
                    instance_id=worker.instance_id,
                    status=WorkerHealthStatus.UNKNOWN,
                    healthz_ok=False,
                    readyz_ok=False,
                    last_check=datetime.utcnow(),
                    error_message=str(result),
                ))
            else:
                health_results.append(result)

        return health_results

    async def get_health_summary(self) -> dict:
        """
        Get a summary of worker health across all instances.

        Returns:
            Dictionary with counts by status and worker type.
        """
        results = await self.get_all_worker_health()

        # Count by status
        status_counts = {status.value: 0 for status in WorkerHealthStatus}
        for result in results:
            status_counts[result.status.value] += 1

        # Group by worker type
        by_type: dict[str, list[dict]] = {}
        for result in results:
            if result.worker_type not in by_type:
                by_type[result.worker_type] = []
            by_type[result.worker_type].append({
                "instance_id": result.instance_id,
                "status": result.status.value,
                "response_time_ms": result.response_time_ms,
            })

        return {
            "total_workers": len(results),
            "status_counts": status_counts,
            "by_worker_type": by_type,
            "checked_at": datetime.utcnow().isoformat(),
        }

    def add_worker(self, worker: WorkerInstance):
        """Add a worker instance to monitor."""
        self.workers.append(worker)

    def remove_worker(self, worker_type: str, instance_id: str):
        """Remove a worker instance from monitoring."""
        self.workers = [
            w for w in self.workers
            if not (w.worker_type == worker_type and w.instance_id == instance_id)
        ]
        # Also remove from cache
        cache_key = f"{worker_type}:{instance_id}"
        self._cache.pop(cache_key, None)


# Singleton instance for dependency injection
_worker_health_service: Optional[WorkerHealthService] = None


def get_worker_health_service() -> WorkerHealthService:
    """Get or create the worker health service singleton."""
    global _worker_health_service
    if _worker_health_service is None:
        _worker_health_service = WorkerHealthService()
    return _worker_health_service
