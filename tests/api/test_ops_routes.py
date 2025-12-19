"""
Tests for Operations API routes (P10-1 through P10-4).

Tests worker health, metrics, SLA, and DLQ management endpoints.
"""

import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from src.api.routes.ops import router


@pytest.fixture
def app():
    """Create a test FastAPI app with ops router."""
    test_app = FastAPI()
    test_app.include_router(router)
    return test_app


@pytest.fixture
def client(app):
    """Create a sync test client."""
    return TestClient(app)


class TestWorkerHealthEndpoint:
    """Test P10-1 worker health endpoint."""

    def test_get_worker_health_success(self, client):
        """Test successful health check retrieval."""
        from src.services.worker_health_service import WorkerHealthResult, WorkerHealthStatus

        mock_results = [
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
                error_message="Not ready",
            ),
        ]

        with patch(
            "src.api.routes.ops.get_worker_health_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_all_worker_health = AsyncMock(return_value=mock_results)
            mock_get_service.return_value = mock_service

            response = client.get("/ops/workers/health")

            assert response.status_code == 200
            data = response.json()
            assert data["total_workers"] == 2
            assert data["status_counts"]["healthy"] == 1
            assert data["status_counts"]["degraded"] == 1

    def test_get_worker_health_with_refresh(self, client):
        """Test health check with refresh flag."""
        from src.services.worker_health_service import WorkerHealthResult, WorkerHealthStatus

        mock_results = [
            WorkerHealthResult(
                worker_type="intake",
                instance_id="intake-1",
                status=WorkerHealthStatus.HEALTHY,
                healthz_ok=True,
                readyz_ok=True,
                last_check=datetime.utcnow(),
            ),
        ]

        with patch(
            "src.api.routes.ops.get_worker_health_service"
        ) as mock_get_service:
            mock_service = MagicMock()
            mock_service.get_all_worker_health = AsyncMock(return_value=mock_results)
            mock_get_service.return_value = mock_service

            response = client.get("/ops/workers/health?refresh=true")

            assert response.status_code == 200
            mock_service.get_all_worker_health.assert_called_once_with(use_cache=False)


class TestThroughputEndpoint:
    """Test P10-2 throughput metrics endpoint."""

    def test_get_throughput_success(self, client):
        """Test successful throughput retrieval."""
        from src.services.metrics_aggregation_service import WorkerThroughput

        mock_results = [
            WorkerThroughput(
                worker_type="intake",
                events_per_second=10.5,
                total_events=1000,
                time_range="1h",
                calculated_at=datetime.utcnow(),
            ),
        ]

        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.services.metrics_aggregation_service.MetricsAggregationService"
            ) as MockService:
                mock_service = MagicMock()
                mock_service.get_throughput_by_worker = AsyncMock(
                    return_value=mock_results
                )
                MockService.return_value = mock_service

                response = client.get("/ops/workers/throughput?time_range=1h")

                assert response.status_code == 200
                data = response.json()
                assert data["time_range"] == "1h"
                assert len(data["items"]) == 1


class TestLatencyEndpoint:
    """Test P10-2 latency metrics endpoint."""

    def test_get_latency_success(self, client):
        """Test successful latency retrieval."""
        from src.services.metrics_aggregation_service import WorkerLatency

        mock_results = [
            WorkerLatency(
                worker_type="intake",
                p50_ms=10.0,
                p95_ms=50.0,
                p99_ms=100.0,
                avg_ms=25.0,
                time_range="1h",
                sample_count=1000,
                calculated_at=datetime.utcnow(),
            ),
        ]

        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.services.metrics_aggregation_service.MetricsAggregationService"
            ) as MockService:
                mock_service = MagicMock()
                mock_service.get_latency_by_worker = AsyncMock(
                    return_value=mock_results
                )
                MockService.return_value = mock_service

                response = client.get("/ops/workers/latency")

                assert response.status_code == 200
                data = response.json()
                assert len(data["items"]) == 1


class TestErrorRateEndpoint:
    """Test P10-2 error rate endpoint."""

    def test_get_errors_success(self, client):
        """Test successful error rate retrieval."""
        from src.services.metrics_aggregation_service import WorkerErrorRate

        mock_results = [
            WorkerErrorRate(
                worker_type="intake",
                error_rate_percent=5.5,
                total_processed=1000,
                total_failed=55,
                time_range="1h",
                calculated_at=datetime.utcnow(),
            ),
        ]

        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.services.metrics_aggregation_service.MetricsAggregationService"
            ) as MockService:
                mock_service = MagicMock()
                mock_service.get_error_rates_by_worker = AsyncMock(
                    return_value=mock_results
                )
                MockService.return_value = mock_service

                response = client.get("/ops/workers/errors")

                assert response.status_code == 200
                data = response.json()
                assert len(data["items"]) == 1


class TestSLAComplianceEndpoint:
    """Test P10-3 SLA compliance endpoint."""

    def test_get_sla_compliance_success(self, client):
        """Test successful SLA compliance retrieval."""
        from src.services.sla_metrics_service import SLAComplianceRate

        mock_result = SLAComplianceRate(
            tenant_id="tenant_1",
            period="day",
            compliance_rate_percent=95.5,
            total_exceptions=100,
            met_sla_count=95,
            breached_sla_count=5,
            in_progress_count=0,
            calculated_at=datetime.utcnow(),
        )

        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.services.sla_metrics_service.SLAMetricsService"
            ) as MockService:
                mock_service = MagicMock()
                mock_service.get_compliance_rate = AsyncMock(return_value=mock_result)
                MockService.return_value = mock_service

                response = client.get("/ops/sla/compliance?tenant_id=tenant_1")

                assert response.status_code == 200
                data = response.json()
                assert data["tenant_id"] == "tenant_1"
                assert data["compliance_rate_percent"] == 95.5

    def test_get_sla_compliance_requires_tenant_id(self, client):
        """Test that SLA compliance requires tenant_id."""
        response = client.get("/ops/sla/compliance")
        assert response.status_code == 422  # Validation error


class TestSLABreachesEndpoint:
    """Test P10-3 SLA breaches endpoint."""

    def test_get_sla_breaches_success(self, client):
        """Test successful SLA breaches retrieval."""
        from src.services.sla_metrics_service import SLABreach

        mock_breaches = [
            SLABreach(
                exception_id="exc_001",
                tenant_id="tenant_1",
                severity="critical",
                sla_deadline=datetime.utcnow(),
                breached_at=datetime.utcnow(),
                breach_duration_hours=2.5,
                current_status="open",
            ),
        ]

        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.services.sla_metrics_service.SLAMetricsService"
            ) as MockService:
                mock_service = MagicMock()
                mock_service.get_breaches = AsyncMock(
                    return_value=(mock_breaches, 1)
                )
                MockService.return_value = mock_service

                response = client.get("/ops/sla/breaches?tenant_id=tenant_1")

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 1
                assert len(data["items"]) == 1


class TestDLQEndpoints:
    """Test P10-4 DLQ management endpoints."""

    def test_list_dlq_entries_requires_tenant_id(self, client):
        """Test that DLQ list requires tenant_id."""
        response = client.get("/ops/dlq")
        assert response.status_code == 400
        assert "tenant_id is required" in response.json()["detail"]

    def test_get_dlq_stats_requires_tenant_id(self, client):
        """Test that DLQ stats requires tenant_id."""
        response = client.get("/ops/dlq/stats")
        assert response.status_code == 422  # Validation error

    def test_get_dlq_stats_success(self, client):
        """Test successful DLQ stats retrieval."""
        from src.infrastructure.repositories.dead_letter_repository import DLQStats

        mock_stats = DLQStats(
            tenant_id="tenant_1",
            total=100,
            pending=50,
            retrying=10,
            discarded=30,
            succeeded=10,
            by_event_type={"test.event": 80},
            by_worker_type={"intake": 60},
        )

        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.api.routes.ops.DeadLetterEventRepository"
            ) as MockRepo:
                mock_repo = MagicMock()
                mock_repo.get_stats = AsyncMock(return_value=mock_stats)
                MockRepo.return_value = mock_repo

                response = client.get("/ops/dlq/stats?tenant_id=tenant_1")

                assert response.status_code == 200
                data = response.json()
                assert data["tenant_id"] == "tenant_1"
                assert data["total"] == 100
                assert data["pending"] == 50

    def test_get_dlq_entry_not_found(self, client):
        """Test DLQ entry not found."""
        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.api.routes.ops.DeadLetterEventRepository"
            ) as MockRepo:
                mock_repo = MagicMock()
                mock_repo.get_dlq_entry_by_id = AsyncMock(return_value=None)
                MockRepo.return_value = mock_repo

                response = client.get("/ops/dlq/999?tenant_id=tenant_1")

                assert response.status_code == 404

    def test_retry_dlq_entry_not_found(self, client):
        """Test retry DLQ entry not found."""
        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.api.routes.ops.DeadLetterEventRepository"
            ) as MockRepo:
                mock_repo = MagicMock()
                mock_repo.mark_retrying = AsyncMock(return_value=None)
                MockRepo.return_value = mock_repo

                response = client.post("/ops/dlq/999/retry?tenant_id=tenant_1")

                assert response.status_code == 404

    def test_discard_dlq_entry_not_found(self, client):
        """Test discard DLQ entry not found."""
        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.api.routes.ops.DeadLetterEventRepository"
            ) as MockRepo:
                mock_repo = MagicMock()
                mock_repo.mark_discarded = AsyncMock(return_value=None)
                MockRepo.return_value = mock_repo

                response = client.post("/ops/dlq/999/discard?tenant_id=tenant_1")

                assert response.status_code == 404

    def test_batch_retry_success(self, client):
        """Test successful batch retry."""
        with patch(
            "src.api.routes.ops.get_db_session_context"
        ) as mock_context:
            mock_session = AsyncMock()
            mock_context.return_value.__aenter__.return_value = mock_session

            with patch(
                "src.api.routes.ops.DeadLetterEventRepository"
            ) as MockRepo:
                mock_repo = MagicMock()
                mock_repo.batch_update_status = AsyncMock(return_value=3)
                MockRepo.return_value = mock_repo

                response = client.post(
                    "/ops/dlq/retry-batch?tenant_id=tenant_1",
                    json={"dlq_ids": [1, 2, 3], "reason": "test retry"},
                )

                assert response.status_code == 200
                data = response.json()
                assert data["updated_count"] == 3
                assert data["requested_count"] == 3
