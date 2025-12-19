"""
Tests for Worker Health Aggregation Service (P10-1).

Tests health checking, caching, and aggregation across worker instances.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from src.services.worker_health_service import (
    WorkerHealthService,
    WorkerHealthStatus,
    WorkerHealthResult,
    WorkerInstance,
    get_worker_health_service,
)


class TestWorkerInstance:
    """Test WorkerInstance dataclass."""

    def test_healthz_url(self):
        """Test healthz URL generation."""
        worker = WorkerInstance(
            worker_type="intake",
            instance_id="intake-1",
            host="localhost",
            port=9001,
        )
        assert worker.healthz_url == "http://localhost:9001/healthz"

    def test_readyz_url(self):
        """Test readyz URL generation."""
        worker = WorkerInstance(
            worker_type="triage",
            instance_id="triage-1",
            host="worker.local",
            port=9002,
        )
        assert worker.readyz_url == "http://worker.local:9002/readyz"


class TestWorkerHealthService:
    """Test WorkerHealthService functionality."""

    @pytest.fixture
    def service(self):
        """Create a test service with no workers."""
        return WorkerHealthService(workers=[], cache_ttl_seconds=10)

    @pytest.fixture
    def service_with_workers(self):
        """Create a service with test workers."""
        workers = [
            WorkerInstance("intake", "intake-1", "localhost", 9001),
            WorkerInstance("triage", "triage-1", "localhost", 9002),
        ]
        return WorkerHealthService(workers=workers, cache_ttl_seconds=10)

    def test_init_default_workers(self):
        """Test service initializes with default workers."""
        service = WorkerHealthService()
        assert len(service.workers) == 7
        worker_types = [w.worker_type for w in service.workers]
        assert "intake" in worker_types
        assert "triage" in worker_types
        assert "playbook" in worker_types

    def test_init_custom_workers(self, service_with_workers):
        """Test service initializes with custom workers."""
        assert len(service_with_workers.workers) == 2

    def test_get_cache_key(self, service_with_workers):
        """Test cache key generation."""
        worker = service_with_workers.workers[0]
        key = service_with_workers._get_cache_key(worker)
        assert key == "intake:intake-1"

    @pytest.mark.asyncio
    async def test_check_endpoint_success(self, service):
        """Test successful endpoint check."""
        mock_response = MagicMock()
        mock_response.status_code = 200

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            ok, time_ms, error = await service._check_endpoint("http://test/healthz")

            assert ok is True
            assert time_ms >= 0
            assert error is None

    @pytest.mark.asyncio
    async def test_check_endpoint_failure(self, service):
        """Test failed endpoint check."""
        mock_response = MagicMock()
        mock_response.status_code = 503

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.return_value = mock_response
            mock_get_client.return_value = mock_client

            ok, time_ms, error = await service._check_endpoint("http://test/healthz")

            assert ok is False
            assert "503" in error

    @pytest.mark.asyncio
    async def test_check_endpoint_timeout(self, service):
        """Test endpoint timeout handling."""
        import httpx

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.TimeoutException("timeout")
            mock_get_client.return_value = mock_client

            ok, time_ms, error = await service._check_endpoint("http://test/healthz")

            assert ok is False
            assert error == "Timeout"

    @pytest.mark.asyncio
    async def test_check_endpoint_connection_error(self, service):
        """Test endpoint connection error handling."""
        import httpx

        with patch.object(service, "_get_client") as mock_get_client:
            mock_client = AsyncMock()
            mock_client.get.side_effect = httpx.ConnectError("connection refused")
            mock_get_client.return_value = mock_client

            ok, time_ms, error = await service._check_endpoint("http://test/healthz")

            assert ok is False
            assert error == "Connection refused"

    @pytest.mark.asyncio
    async def test_check_worker_health_healthy(self, service_with_workers):
        """Test checking health of healthy worker."""
        with patch.object(
            service_with_workers, "_check_endpoint"
        ) as mock_check:
            mock_check.return_value = (True, 10.0, None)

            worker = service_with_workers.workers[0]
            result = await service_with_workers.check_worker_health(
                worker, use_cache=False
            )

            assert result.status == WorkerHealthStatus.HEALTHY
            assert result.healthz_ok is True
            assert result.readyz_ok is True

    @pytest.mark.asyncio
    async def test_check_worker_health_degraded(self, service_with_workers):
        """Test checking health of degraded worker (healthz ok, readyz not)."""
        with patch.object(
            service_with_workers, "_check_endpoint"
        ) as mock_check:
            # healthz ok, readyz fail
            mock_check.side_effect = [
                (True, 10.0, None),
                (False, 10.0, "Not ready"),
            ]

            worker = service_with_workers.workers[0]
            result = await service_with_workers.check_worker_health(
                worker, use_cache=False
            )

            assert result.status == WorkerHealthStatus.DEGRADED
            assert result.healthz_ok is True
            assert result.readyz_ok is False

    @pytest.mark.asyncio
    async def test_check_worker_health_uses_cache(self, service_with_workers):
        """Test that health checks use cache when available."""
        worker = service_with_workers.workers[0]
        cache_key = service_with_workers._get_cache_key(worker)

        # Populate cache
        from src.services.worker_health_service import WorkerHealthCache

        cached_result = WorkerHealthResult(
            worker_type=worker.worker_type,
            instance_id=worker.instance_id,
            status=WorkerHealthStatus.HEALTHY,
            healthz_ok=True,
            readyz_ok=True,
            last_check=datetime.utcnow(),
            response_time_ms=5.0,
        )
        service_with_workers._cache[cache_key] = WorkerHealthCache(
            result=cached_result,
            expires_at=datetime.utcnow() + timedelta(minutes=5),
        )

        # Should return cached result without checking endpoints
        with patch.object(
            service_with_workers, "_check_endpoint"
        ) as mock_check:
            result = await service_with_workers.check_worker_health(
                worker, use_cache=True
            )

            mock_check.assert_not_called()
            assert result == cached_result

    @pytest.mark.asyncio
    async def test_check_worker_health_bypasses_expired_cache(
        self, service_with_workers
    ):
        """Test that expired cache is bypassed."""
        worker = service_with_workers.workers[0]
        cache_key = service_with_workers._get_cache_key(worker)

        # Populate cache with expired entry
        from src.services.worker_health_service import WorkerHealthCache

        cached_result = WorkerHealthResult(
            worker_type=worker.worker_type,
            instance_id=worker.instance_id,
            status=WorkerHealthStatus.HEALTHY,
            healthz_ok=True,
            readyz_ok=True,
            last_check=datetime.utcnow() - timedelta(minutes=10),
            response_time_ms=5.0,
        )
        service_with_workers._cache[cache_key] = WorkerHealthCache(
            result=cached_result,
            expires_at=datetime.utcnow() - timedelta(minutes=5),  # Expired
        )

        with patch.object(
            service_with_workers, "_check_endpoint"
        ) as mock_check:
            mock_check.return_value = (True, 10.0, None)

            result = await service_with_workers.check_worker_health(
                worker, use_cache=True
            )

            # Should have called endpoints because cache expired
            assert mock_check.call_count == 2

    @pytest.mark.asyncio
    async def test_get_all_worker_health(self, service_with_workers):
        """Test getting health of all workers."""
        with patch.object(
            service_with_workers, "check_worker_health"
        ) as mock_check:
            mock_check.return_value = WorkerHealthResult(
                worker_type="test",
                instance_id="test-1",
                status=WorkerHealthStatus.HEALTHY,
                healthz_ok=True,
                readyz_ok=True,
                last_check=datetime.utcnow(),
            )

            results = await service_with_workers.get_all_worker_health()

            assert len(results) == 2
            assert mock_check.call_count == 2

    @pytest.mark.asyncio
    async def test_get_health_summary(self, service_with_workers):
        """Test getting health summary."""
        with patch.object(
            service_with_workers, "get_all_worker_health"
        ) as mock_get:
            mock_get.return_value = [
                WorkerHealthResult(
                    worker_type="intake",
                    instance_id="intake-1",
                    status=WorkerHealthStatus.HEALTHY,
                    healthz_ok=True,
                    readyz_ok=True,
                    last_check=datetime.utcnow(),
                    response_time_ms=10.0,
                ),
                WorkerHealthResult(
                    worker_type="triage",
                    instance_id="triage-1",
                    status=WorkerHealthStatus.DEGRADED,
                    healthz_ok=True,
                    readyz_ok=False,
                    last_check=datetime.utcnow(),
                    response_time_ms=20.0,
                ),
            ]

            summary = await service_with_workers.get_health_summary()

            assert summary["total_workers"] == 2
            assert summary["status_counts"]["healthy"] == 1
            assert summary["status_counts"]["degraded"] == 1
            assert "intake" in summary["by_worker_type"]
            assert "triage" in summary["by_worker_type"]

    def test_add_worker(self, service):
        """Test adding a worker."""
        worker = WorkerInstance("test", "test-1", "localhost", 9000)
        service.add_worker(worker)
        assert worker in service.workers

    def test_remove_worker(self, service_with_workers):
        """Test removing a worker."""
        initial_count = len(service_with_workers.workers)
        service_with_workers.remove_worker("intake", "intake-1")
        assert len(service_with_workers.workers) == initial_count - 1

    @pytest.mark.asyncio
    async def test_consecutive_failures_tracking(self, service_with_workers):
        """Test that consecutive failures are tracked."""
        worker = service_with_workers.workers[0]

        with patch.object(
            service_with_workers, "_check_endpoint"
        ) as mock_check:
            # Both endpoints fail
            mock_check.return_value = (False, 10.0, "Error")

            # First failure
            result1 = await service_with_workers.check_worker_health(
                worker, use_cache=False
            )
            assert result1.status == WorkerHealthStatus.DEGRADED

            # Second failure
            result2 = await service_with_workers.check_worker_health(
                worker, use_cache=False
            )
            assert result2.status == WorkerHealthStatus.DEGRADED

            # Third failure - should be unhealthy
            result3 = await service_with_workers.check_worker_health(
                worker, use_cache=False
            )
            assert result3.status == WorkerHealthStatus.UNHEALTHY


class TestGetWorkerHealthService:
    """Test singleton factory."""

    def test_get_worker_health_service_creates_singleton(self):
        """Test that get_worker_health_service returns same instance."""
        # Reset singleton
        import src.services.worker_health_service as module

        module._worker_health_service = None

        service1 = get_worker_health_service()
        service2 = get_worker_health_service()

        assert service1 is service2

        # Cleanup
        module._worker_health_service = None
