"""
CI-ready multi-domain simulation test.

This test runs a small batch multi-domain simulation suitable for CI/CD.
It verifies:
- Multi-domain processing works
- No cross-domain leakage
- Performance metrics are collected
- Results are saved correctly
"""

import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from src.simulation.runner import SimulationRunner
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition
from src.models.tenant_policy import TenantPolicyPack


@pytest.fixture
def ci_test_setup(tmp_path):
    """Setup test environment for CI simulation."""
    domain_packs_dir = tmp_path / "domainpacks"
    domain_packs_dir.mkdir()
    
    tenant_packs_dir = tmp_path / "tenantpacks"
    tenant_packs_dir.mkdir()
    
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    # Create finance domain pack
    finance_pack = DomainPack(
        domain_name="CapitalMarketsTrading",
        exception_types={
            "TRADE_SETTLEMENT_FAIL": ExceptionTypeDefinition(description="Trade settlement failed"),
            "TRADE_MISMATCH": ExceptionTypeDefinition(description="Trade data mismatch"),
        },
    )
    
    with open(domain_packs_dir / "finance.sample.json", "w") as f:
        json.dump(finance_pack.model_dump(), f, default=str)
    
    # Create healthcare domain pack
    healthcare_pack = DomainPack(
        domain_name="HealthcareClaimsAndCareOps",
        exception_types={
            "CLAIM_MISSING_AUTH": ExceptionTypeDefinition(description="Claim missing authorization"),
            "CLAIM_CODE_MISMATCH": ExceptionTypeDefinition(description="Claim code mismatch"),
        },
    )
    
    with open(domain_packs_dir / "healthcare.sample.json", "w") as f:
        json.dump(healthcare_pack.model_dump(), f, default=str)
    
    # Create tenant policy files
    finance_policy = TenantPolicyPack(
        tenant_id="TENANT_FINANCE",
        domain_name="CapitalMarketsTrading",
        approved_tools=[],
    )
    
    with open(tenant_packs_dir / "tenant_finance.sample.json", "w") as f:
        json.dump(finance_policy.model_dump(), f, default=str)
    
    healthcare_policy = TenantPolicyPack(
        tenant_id="TENANT_HEALTHCARE",
        domain_name="HealthcareClaimsAndCareOps",
        approved_tools=[],
    )
    
    with open(tenant_packs_dir / "tenant_healthcare.sample.json", "w") as f:
        json.dump(healthcare_policy.model_dump(), f, default=str)
    
    return {
        "domain_packs_dir": domain_packs_dir,
        "tenant_packs_dir": tenant_packs_dir,
        "output_dir": output_dir,
    }


@pytest.mark.asyncio
async def test_ci_multi_domain_simulation_small_batch(ci_test_setup):
    """
    CI-ready multi-domain simulation test with small batch.
    
    This test is designed to run quickly in CI/CD pipelines.
    """
    setup = ci_test_setup
    
    runner = SimulationRunner(
        domain_packs_dir=str(setup["domain_packs_dir"]),
        tenant_packs_dir=str(setup["tenant_packs_dir"]),
        output_dir=str(setup["output_dir"]),
    )
    
    # Mock run_pipeline to avoid actual agent execution in CI
    with patch("src.simulation.runner.run_pipeline") as mock_run:
        def mock_pipeline_result(domain_name, tenant_id):
            return {
                "tenantId": tenant_id,
                "runId": "ci_test_run",
                "results": [
                    {
                        "exceptionId": f"exc_{domain_name}_{i}",
                        "status": "completed",
                        "exception": {
                            "exception_id": f"exc_{domain_name}_{i}",
                            "tenant_id": tenant_id,
                            "domain_name": domain_name,
                        },
                    }
                    for i in range(3)  # Small batch for CI
                ],
            }
        
        mock_run.side_effect = [
            mock_pipeline_result("CapitalMarketsTrading", "TENANT_FINANCE"),
            mock_pipeline_result("HealthcareClaimsAndCareOps", "TENANT_HEALTHCARE"),
        ]
        
        result = await runner.run_simulation(
            domain_names=["finance", "healthcare"],
            batch_size=3,
            exceptions_per_domain=3,
        )
    
    # Verify simulation completed successfully
    assert result.simulation_id is not None
    assert len(result.domains) == 2
    assert "finance" in result.domains
    assert "healthcare" in result.domains
    
    # Verify metrics
    assert result.metrics.total_exceptions == 6  # 3 per domain
    assert result.metrics.total_domains == 2
    assert result.metrics.total_duration_seconds >= 0
    assert result.metrics.exceptions_per_second >= 0
    
    # Verify no cross-domain leakage
    assert not result.metrics.cross_domain_leakage_detected, \
        f"Cross-domain leakage detected: {result.metrics.leakage_details}"
    
    # Verify results were saved
    output_file = setup["output_dir"] / f"{result.simulation_id}.json"
    assert output_file.exists()
    
    # Verify output file content
    with open(output_file) as f:
        saved_data = json.load(f)
    
    assert saved_data["simulation_id"] == result.simulation_id
    assert saved_data["metrics"]["total_exceptions"] == 6
    assert saved_data["metrics"]["cross_domain_leakage_detected"] is False
    
    # Verify no errors
    assert len(result.errors) == 0, f"Simulation errors: {result.errors}"

