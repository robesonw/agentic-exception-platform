"""
Tests for multi-domain simulation runner.

Tests:
- Domain pack loading
- Synthetic exception generation
- Pipeline execution
- Performance metrics collection
- Cross-domain leakage detection
"""

import asyncio
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.domain_pack import DomainPack, ExceptionTypeDefinition
from src.models.tenant_policy import TenantPolicyPack
from src.simulation.runner import ExceptionGenerator, SimulationRunner, SimulationMetrics


@pytest.fixture
def sample_domain_pack_finance():
    """Sample finance domain pack."""
    from src.models.domain_pack import EntityDefinition
    
    return DomainPack(
        domain_name="CapitalMarketsTrading",
        entities={
            "TradeOrder": EntityDefinition(
                attributes={
                    "orderId": {"type": "string", "required": True},
                    "tradeDate": {"type": "string", "required": True},
                }
            )
        },
        exception_types={
            "TRADE_SETTLEMENT_FAIL": ExceptionTypeDefinition(
                description="Trade settlement failed",
            ),
            "TRADE_MISMATCH": ExceptionTypeDefinition(
                description="Trade data mismatch",
            ),
        },
        severity_rules=[],
        tools={},
        playbooks=[],
        guardrails={},
    )


@pytest.fixture
def sample_domain_pack_healthcare():
    """Sample healthcare domain pack."""
    from src.models.domain_pack import EntityDefinition
    
    return DomainPack(
        domain_name="HealthcareClaimsAndCareOps",
        entities={
            "Claim": EntityDefinition(
                attributes={
                    "claimId": {"type": "string", "required": True},
                    "patientId": {"type": "string", "required": True},
                }
            )
        },
        exception_types={
            "CLAIM_MISSING_AUTH": ExceptionTypeDefinition(
                description="Claim missing authorization",
            ),
            "CLAIM_CODE_MISMATCH": ExceptionTypeDefinition(
                description="Claim code mismatch",
            ),
        },
        severity_rules=[],
        tools={},
        playbooks=[],
        guardrails={},
    )


@pytest.fixture
def sample_tenant_policy():
    """Sample tenant policy pack."""
    return TenantPolicyPack(
        tenant_id="TENANT_TEST",
        domain_name="CapitalMarketsTrading",
        approved_tools=[],
    )


@pytest.fixture
def temp_dirs():
    """Create temporary directories for domain packs and tenant packs."""
    with tempfile.TemporaryDirectory() as temp_dir:
        domain_dir = Path(temp_dir) / "domainpacks"
        tenant_dir = Path(temp_dir) / "tenantpacks"
        output_dir = Path(temp_dir) / "output"
        
        domain_dir.mkdir()
        tenant_dir.mkdir()
        output_dir.mkdir()
        
        yield {
            "base": Path(temp_dir),
            "domainpacks": domain_dir,
            "tenantpacks": tenant_dir,
            "output": output_dir,
        }


class TestExceptionGenerator:
    """Tests for ExceptionGenerator."""

    def test_generate_exception(self, sample_domain_pack_finance):
        """Test exception generation."""
        generator = ExceptionGenerator(sample_domain_pack_finance)
        
        exception = generator.generate_exception()
        
        assert "exceptionId" in exception
        assert "tenantId" in exception
        assert "domainName" in exception
        assert exception["domainName"] == "CapitalMarketsTrading"
        assert "exceptionType" in exception
        assert "rawPayload" in exception

    def test_generate_exception_with_type(self, sample_domain_pack_finance):
        """Test exception generation with specific type."""
        generator = ExceptionGenerator(sample_domain_pack_finance)
        
        exception = generator.generate_exception(exception_type="TRADE_SETTLEMENT_FAIL")
        
        assert exception["exceptionType"] == "TRADE_SETTLEMENT_FAIL"

    def test_generate_exception_with_tenant(self, sample_domain_pack_finance):
        """Test exception generation with specific tenant."""
        generator = ExceptionGenerator(sample_domain_pack_finance)
        
        exception = generator.generate_exception(tenant_id="TENANT_CUSTOM")
        
        assert exception["tenantId"] == "TENANT_CUSTOM"

    def test_generate_batch(self, sample_domain_pack_finance):
        """Test batch exception generation."""
        generator = ExceptionGenerator(sample_domain_pack_finance)
        
        batch = generator.generate_batch(count=10)
        
        assert len(batch) == 10
        assert all("exceptionId" in exc for exc in batch)
        assert all(exc["domainName"] == "CapitalMarketsTrading" for exc in batch)


class TestSimulationRunner:
    """Tests for SimulationRunner."""

    def test_init(self, temp_dirs):
        """Test initialization."""
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        assert runner.domain_packs_dir == temp_dirs["domainpacks"]
        assert runner.tenant_packs_dir == temp_dirs["tenantpacks"]
        assert runner.output_dir == temp_dirs["output"]

    def test_load_domain_packs(self, temp_dirs, sample_domain_pack_finance):
        """Test loading domain packs."""
        # Create domain pack file
        domain_file = temp_dirs["domainpacks"] / "finance.sample.json"
        with open(domain_file, "w") as f:
            json.dump(sample_domain_pack_finance.model_dump(), f, default=str)
        
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        packs = runner.load_domain_packs(["finance"])
        
        assert "finance" in packs
        assert packs["finance"].domain_name == "CapitalMarketsTrading"

    def test_load_domain_packs_not_found(self, temp_dirs):
        """Test loading domain packs when file not found."""
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        with pytest.raises(FileNotFoundError):
            runner.load_domain_packs(["nonexistent"])

    def test_load_tenant_policies(self, temp_dirs, sample_tenant_policy):
        """Test loading tenant policies."""
        # Create tenant policy file
        policy_file = temp_dirs["tenantpacks"] / "tenant_finance.sample.json"
        with open(policy_file, "w") as f:
            json.dump(sample_tenant_policy.model_dump(), f, default=str)
        
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        # Need to load domain pack first
        domain_file = temp_dirs["domainpacks"] / "finance.sample.json"
        with open(domain_file, "w") as f:
            json.dump(
                DomainPack(
                    domain_name="CapitalMarketsTrading",
                    exception_types={
                        "TEST_EXCEPTION": ExceptionTypeDefinition(description="Test exception"),
                    },
                ).model_dump(),
                f,
                default=str,
            )
        
        runner.load_domain_packs(["finance"])
        policies = runner.load_tenant_policies(["finance"])
        
        assert "finance" in policies
        assert policies["finance"].tenant_id == "TENANT_TEST"

    def test_load_tenant_policies_creates_minimal(self, temp_dirs):
        """Test that minimal tenant policy is created if file not found."""
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        # Create domain pack file
        domain_file = temp_dirs["domainpacks"] / "finance.sample.json"
        with open(domain_file, "w") as f:
            json.dump(
                DomainPack(
                    domain_name="CapitalMarketsTrading",
                    exception_types={
                        "TEST_EXCEPTION": ExceptionTypeDefinition(description="Test exception"),
                    },
                    tools={},
                ).model_dump(),
                f,
                default=str,
            )
        
        runner.load_domain_packs(["finance"])
        policies = runner.load_tenant_policies(["finance"])
        
        assert "finance" in policies
        assert policies["finance"].tenant_id == "TENANT_FINANCE"

    @pytest.mark.asyncio
    async def test_run_simulation_small_batch(self, temp_dirs, sample_domain_pack_finance, sample_tenant_policy):
        """Test running simulation with small batch."""
        # Create domain pack file
        domain_file = temp_dirs["domainpacks"] / "finance.sample.json"
        with open(domain_file, "w") as f:
            json.dump(sample_domain_pack_finance.model_dump(), f, default=str)
        
        # Create tenant policy file
        policy_file = temp_dirs["tenantpacks"] / "tenant_finance.sample.json"
        with open(policy_file, "w") as f:
            json.dump(sample_tenant_policy.model_dump(), f, default=str)
        
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        # Mock the run_pipeline function to avoid actual agent execution
        with patch("src.simulation.runner.run_pipeline") as mock_run:
            mock_run.return_value = {
                "tenantId": "TENANT_TEST",
                "runId": "test_run",
                "results": [
                    {
                        "exceptionId": f"exc_{i}",
                        "status": "completed",
                        "exception": {
                            "exception_id": f"exc_{i}",
                            "tenant_id": "TENANT_TEST",
                            "domain_name": "CapitalMarketsTrading",
                        },
                    }
                    for i in range(5)
                ],
            }
            
            result = await runner.run_simulation(
                domain_names=["finance"],
                batch_size=5,
                exceptions_per_domain=5,
            )
        
        assert result.simulation_id is not None
        assert "finance" in result.domains
        assert result.metrics.total_exceptions == 5
        assert result.metrics.total_domains == 1
        assert not result.metrics.cross_domain_leakage_detected

    @pytest.mark.asyncio
    async def test_run_simulation_multiple_domains(self, temp_dirs, sample_domain_pack_finance, sample_domain_pack_healthcare):
        """Test running simulation with multiple domains."""
        # Create domain pack files
        finance_file = temp_dirs["domainpacks"] / "finance.sample.json"
        with open(finance_file, "w") as f:
            json.dump(sample_domain_pack_finance.model_dump(), f, default=str)
        
        healthcare_file = temp_dirs["domainpacks"] / "healthcare.sample.json"
        with open(healthcare_file, "w") as f:
            json.dump(sample_domain_pack_healthcare.model_dump(), f, default=str)
        
        # Create tenant policy files
        finance_policy = TenantPolicyPack(
            tenant_id="TENANT_FINANCE",
            domain_name="CapitalMarketsTrading",
            approved_tools=[],
        )
        policy_file = temp_dirs["tenantpacks"] / "tenant_finance.sample.json"
        with open(policy_file, "w") as f:
            json.dump(finance_policy.model_dump(), f, default=str)
        
        healthcare_policy = TenantPolicyPack(
            tenant_id="TENANT_HEALTHCARE",
            domain_name="HealthcareClaimsAndCareOps",
            approved_tools=[],
        )
        policy_file = temp_dirs["tenantpacks"] / "tenant_healthcare.sample.json"
        with open(policy_file, "w") as f:
            json.dump(healthcare_policy.model_dump(), f, default=str)
        
        runner = SimulationRunner(
            domain_packs_dir=str(temp_dirs["domainpacks"]),
            tenant_packs_dir=str(temp_dirs["tenantpacks"]),
            output_dir=str(temp_dirs["output"]),
        )
        
        # Mock the run_pipeline function
        with patch("src.simulation.runner.run_pipeline") as mock_run:
            def mock_pipeline_result(domain_name, tenant_id):
                return {
                    "tenantId": tenant_id,
                    "runId": "test_run",
                    "results": [
                        {
                            "exceptionId": f"exc_{i}",
                            "status": "completed",
                            "exception": {
                                "exception_id": f"exc_{i}",
                                "tenant_id": tenant_id,
                                "domain_name": domain_name,
                            },
                        }
                        for i in range(3)
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
        
        assert result.simulation_id is not None
        assert len(result.domains) == 2
        assert "finance" in result.domains
        assert "healthcare" in result.domains
        assert result.metrics.total_exceptions == 6
        assert result.metrics.total_domains == 2
        assert not result.metrics.cross_domain_leakage_detected

    def test_check_cross_domain_leakage_no_leakage(self):
        """Test cross-domain leakage detection with no leakage."""
        runner = SimulationRunner()
        
        # Use domain names that match the domain pack domain names
        domain_results = {
            "finance": {
                "tenantId": "TENANT_FINANCE",
                "results": [
                    {
                        "exception": {
                            "domain_name": "CapitalMarketsTrading",  # Use domain_name from exception record
                            "tenant_id": "TENANT_FINANCE",
                        }
                    }
                ],
            },
            "healthcare": {
                "tenantId": "TENANT_HEALTHCARE",
                "results": [
                    {
                        "exception": {
                            "domain_name": "HealthcareClaimsAndCareOps",
                            "tenant_id": "TENANT_HEALTHCARE",
                        }
                    }
                ],
            },
        }
        
        leakage_detected, leakage_details = runner._check_cross_domain_leakage(domain_results)
        
        assert not leakage_detected
        assert len(leakage_details) == 0

    def test_check_cross_domain_leakage_detected(self):
        """Test cross-domain leakage detection with leakage."""
        runner = SimulationRunner()
        
        # Set up domain packs for the runner
        from src.models.domain_pack import EntityDefinition
        finance_pack = DomainPack(
            domain_name="CapitalMarketsTrading",
            exception_types={
                "TEST_EXCEPTION": ExceptionTypeDefinition(description="Test exception"),
            },
        )
        runner.domain_packs["finance"] = finance_pack
        
        domain_results = {
            "finance": {
                "tenantId": "TENANT_FINANCE",
                "results": [
                    {
                        "exception": {
                            "domain_name": "HealthcareClaimsAndCareOps",  # Wrong domain!
                            "tenant_id": "TENANT_FINANCE",
                        }
                    }
                ],
            },
        }
        
        leakage_detected, leakage_details = runner._check_cross_domain_leakage(domain_results)
        
        assert leakage_detected
        assert len(leakage_details) > 0
        assert any("HealthcareClaimsAndCareOps" in detail for detail in leakage_details)

    def test_save_results(self, temp_dirs):
        """Test saving simulation results."""
        runner = SimulationRunner(output_dir=str(temp_dirs["output"]))
        
        result = type("SimulationResult", (), {
            "simulation_id": "test_sim",
            "domains": ["finance"],
            "tenants": ["TENANT_FINANCE"],
            "metrics": SimulationMetrics(total_exceptions=10),
            "errors": [],
        })()
        
        runner._save_results(result)
        
        output_file = temp_dirs["output"] / "test_sim.json"
        assert output_file.exists()
        
        with open(output_file) as f:
            data = json.load(f)
        
        assert data["simulation_id"] == "test_sim"
        assert data["metrics"]["total_exceptions"] == 10

