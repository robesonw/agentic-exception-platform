"""
Tests for Re-Run and What-If Simulation API (P3-14).

Tests cover:
- Re-running exceptions with overrides
- Simulation mode (no persistence)
- Comparison with original runs
- Retrieving simulation results
"""

import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, SeverityRule
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.orchestrator.store import get_exception_store

# Test client
client = TestClient(app)

# Default API key for tests
DEFAULT_API_KEY = "test-api-key-123"


@pytest.fixture
def reset_store():
    """Reset exception store before each test."""
    store = get_exception_store()
    store.clear_all()
    yield
    store.clear_all()


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack for testing."""
    return DomainPack(
        domain_name="TestDomain",
        version="1.0.0",
        exception_types={
            "DataQualityFailure": ExceptionTypeDefinition(
                name="DataQualityFailure",
                description="Data quality failure",
                severity_rules=[
                    SeverityRule(
                        condition="payload.error_code == 'DQ001'",
                        severity="HIGH",
                    )
                ],
            )
        },
        playbooks=[],
        tools={},
    )


@pytest.fixture
def sample_tenant_policy():
    """Create a sample tenant policy for testing."""
    return TenantPolicyPack(
        tenant_id="tenant_001",
        domain_name="TestDomain",
        custom_guardrails={},
        custom_playbooks=[],
    )


@pytest.fixture
def sample_exception():
    """Create a sample exception record."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        exception_type="DataQualityFailure",
        severity=Severity.MEDIUM,
        resolution_status=ResolutionStatus.OPEN,
        source_system="test_system",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"error": "test error", "error_code": "DQ001"},
        normalized_context={"domain": "TestDomain"},
    )


@pytest.fixture
def sample_pipeline_result():
    """Create a sample pipeline result."""
    return {
        "exceptionId": "exc_001",
        "status": "OPEN",
        "stages": {
            "intake": {"decision": "ACCEPTED", "confidence": 0.9},
            "triage": {"decision": "CLASSIFIED", "confidence": 0.85},
            "policy": {"decision": "ALLOW", "confidence": 0.8},
        },
        "evidence": ["Evidence 1", "Evidence 2"],
    }


@pytest.fixture
def registered_exception(reset_store, sample_exception, sample_pipeline_result):
    """Register an exception in the store."""
    store = get_exception_store()
    store.store_exception(sample_exception, sample_pipeline_result)
    return sample_exception


class TestSimulationAPI:
    """Test suite for simulation API endpoints."""

    def test_rerun_exception_basic(self, registered_exception, sample_domain_pack, sample_tenant_policy):
        """Test basic rerun without overrides."""
        with patch("src.api.routes.router_simulation.DomainPackStorage") as mock_storage, \
             patch("src.api.routes.router_simulation.TenantPolicyRegistry") as mock_registry:
            
            # Mock storage and registry
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_latest.return_value = sample_domain_pack
            mock_storage.return_value = mock_storage_instance
            
            mock_registry_instance = MagicMock()
            mock_registry_instance.get.return_value = sample_tenant_policy
            mock_registry.return_value = mock_registry_instance
            
            # Mock simulation run
            with patch("src.api.routes.router_simulation.run_simulation") as mock_run:
                mock_run.return_value = {
                    "simulation_id": "sim_001",
                    "original_exception_id": "exc_001",
                    "simulated_exception": registered_exception.model_dump(),
                    "pipeline_result": {"stages": {}},
                    "overrides_applied": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                
                response = client.post(
                    "/ui/exceptions/exc_001/rerun",
                    json={
                        "tenant_id": "tenant_001",
                        "overrides": {},
                        "simulation": True,
                    },
                    headers={"X-API-KEY": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "simulation_id" in data
                assert data["original_exception_id"] == "exc_001"
                assert "simulated_exception" in data
                assert "pipeline_result" in data

    def test_rerun_exception_with_severity_override(self, registered_exception, sample_domain_pack, sample_tenant_policy):
        """Test rerun with severity override."""
        with patch("src.api.routes.router_simulation.DomainPackStorage") as mock_storage, \
             patch("src.api.routes.router_simulation.TenantPolicyRegistry") as mock_registry:
            
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_latest.return_value = sample_domain_pack
            mock_storage.return_value = mock_storage_instance
            
            mock_registry_instance = MagicMock()
            mock_registry_instance.get.return_value = sample_tenant_policy
            mock_registry.return_value = mock_registry_instance
            
            with patch("src.api.routes.router_simulation.run_simulation") as mock_run:
                mock_run.return_value = {
                    "simulation_id": "sim_002",
                    "original_exception_id": "exc_001",
                    "simulated_exception": registered_exception.model_dump(),
                    "pipeline_result": {"stages": {}},
                    "overrides_applied": {"severity": "HIGH"},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                
                response = client.post(
                    "/ui/exceptions/exc_001/rerun",
                    json={
                        "tenant_id": "tenant_001",
                        "overrides": {"severity": "HIGH"},
                        "simulation": True,
                    },
                    headers={"X-API-KEY": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert data["overrides_applied"]["severity"] == "HIGH"

    def test_rerun_exception_not_found(self, reset_store):
        """Test rerun when exception not found."""
        response = client.post(
            "/ui/exceptions/nonexistent/rerun",
            json={
                "tenant_id": "tenant_001",
                "overrides": {},
                "simulation": True,
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    def test_rerun_exception_invalid_severity(self, registered_exception):
        """Test rerun with invalid severity override."""
        response = client.post(
            "/ui/exceptions/exc_001/rerun",
            json={
                "tenant_id": "tenant_001",
                "overrides": {"severity": "INVALID"},
                "simulation": True,
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "invalid severity" in response.json()["detail"].lower()

    def test_get_simulation_result(self, sample_domain_pack, sample_tenant_policy):
        """Test retrieving simulation result."""
        # Create a temporary simulation result file
        with tempfile.TemporaryDirectory() as tmpdir:
            sim_dir = Path(tmpdir) / "simulations" / "tenant_001"
            sim_dir.mkdir(parents=True, exist_ok=True)
            
            simulation_data = {
                "simulation_id": "sim_003",
                "original_exception_id": "exc_001",
                "simulated_exception": {"exception_id": "exc_001"},
                "pipeline_result": {"stages": {}},
                "overrides_applied": {},
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            
            sim_file = sim_dir / "sim_003.json"
            with open(sim_file, "w") as f:
                json.dump(simulation_data, f)
            
            # Mock the simulation directory
            with patch("src.orchestrator.simulation.Path") as mock_path:
                mock_path.return_value = sim_file
                
                # Override get_simulation_result to read from our temp file
                from src.orchestrator.simulation import get_simulation_result
                
                # Read the file directly
                with open(sim_file, "r") as f:
                    loaded_data = json.load(f)
                
                with patch("src.api.routes.router_simulation.get_simulation_result") as mock_get:
                    mock_get.return_value = loaded_data
                    
                    response = client.get(
                        "/ui/simulations/sim_003?tenant_id=tenant_001",
                        headers={"X-API-KEY": DEFAULT_API_KEY},
                    )
                    
                    assert response.status_code == 200
                    data = response.json()
                    assert data["simulation_id"] == "sim_003"
                    assert data["original_exception_id"] == "exc_001"

    def test_get_simulation_result_not_found(self):
        """Test retrieving non-existent simulation result."""
        with patch("src.api.routes.router_simulation.get_simulation_result") as mock_get:
            mock_get.return_value = None
            
            response = client.get(
                "/ui/simulations/nonexistent?tenant_id=tenant_001",
                headers={"X-API-KEY": DEFAULT_API_KEY},
            )
            
            assert response.status_code == 404
            assert "not found" in response.json()["detail"].lower()

    def test_simulation_does_not_persist_exception(self, registered_exception, sample_domain_pack, sample_tenant_policy):
        """Test that simulation mode does not update main exception record."""
        store = get_exception_store()
        original_status = registered_exception.resolution_status
        
        with patch("src.api.routes.router_simulation.DomainPackStorage") as mock_storage, \
             patch("src.api.routes.router_simulation.TenantPolicyRegistry") as mock_registry:
            
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_latest.return_value = sample_domain_pack
            mock_storage.return_value = mock_storage_instance
            
            mock_registry_instance = MagicMock()
            mock_registry_instance.get.return_value = sample_tenant_policy
            mock_registry.return_value = mock_registry_instance
            
            with patch("src.api.routes.router_simulation.run_simulation") as mock_run:
                # Simulate a different status in simulation
                simulated_exception = registered_exception.model_dump()
                simulated_exception["resolution_status"] = "RESOLVED"
                
                mock_run.return_value = {
                    "simulation_id": "sim_004",
                    "original_exception_id": "exc_001",
                    "simulated_exception": simulated_exception,
                    "pipeline_result": {"stages": {}},
                    "overrides_applied": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                
                response = client.post(
                    "/ui/exceptions/exc_001/rerun",
                    json={
                        "tenant_id": "tenant_001",
                        "overrides": {},
                        "simulation": True,
                    },
                    headers={"X-API-KEY": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 200
                
                # Verify original exception status unchanged
                stored_exception, _ = store.get_exception("tenant_001", "exc_001")
                assert stored_exception.resolution_status == original_status

    def test_simulation_comparison_generated(self, registered_exception, sample_domain_pack, sample_tenant_policy):
        """Test that comparison is generated when original run is available."""
        with patch("src.api.routes.router_simulation.DomainPackStorage") as mock_storage, \
             patch("src.api.routes.router_simulation.TenantPolicyRegistry") as mock_registry:
            
            mock_storage_instance = MagicMock()
            mock_storage_instance.get_latest.return_value = sample_domain_pack
            mock_storage.return_value = mock_storage_instance
            
            mock_registry_instance = MagicMock()
            mock_registry_instance.get.return_value = sample_tenant_policy
            mock_registry.return_value = mock_registry_instance
            
            with patch("src.api.routes.router_simulation.run_simulation") as mock_run, \
                 patch("src.api.routes.router_simulation.compare_runs") as mock_compare:
                
                mock_run.return_value = {
                    "simulation_id": "sim_005",
                    "original_exception_id": "exc_001",
                    "simulated_exception": registered_exception.model_dump(),
                    "pipeline_result": {"stages": {}},
                    "overrides_applied": {},
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
                
                mock_compare.return_value = {
                    "differences": {
                        "severity": {"changed": False},
                        "decisions": {},
                        "actions": {},
                        "approvals_required": {"changed": False},
                    },
                    "summary": {"total_differences": 0, "critical_changes": []},
                }
                
                response = client.post(
                    "/ui/exceptions/exc_001/rerun",
                    json={
                        "tenant_id": "tenant_001",
                        "overrides": {},
                        "simulation": True,
                    },
                    headers={"X-API-KEY": DEFAULT_API_KEY},
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "comparison" in data
                assert data["comparison"] is not None

