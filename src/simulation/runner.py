"""
Multi-domain simulation and testing harness.

Phase 2: Multi-Domain Simulation and Testing (Issue 45)
- Load multiple domain packs
- Generate synthetic exception batches
- Run through orchestrator
- Collect performance metrics
- Verify no cross-domain leakage
"""

import argparse
import asyncio
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.domainpack.loader import DomainPackRegistry, load_domain_pack
from src.models.domain_pack import DomainPack
from src.models.tenant_policy import TenantPolicyPack
from src.observability.metrics import MetricsCollector
from src.orchestrator.runner import run_pipeline
from src.tenantpack.loader import load_tenant_policy, validate_tenant_policy

logger = logging.getLogger(__name__)


@dataclass
class SimulationMetrics:
    """Performance metrics for a simulation run."""

    total_exceptions: int = 0
    total_domains: int = 0
    total_tenants: int = 0
    total_duration_seconds: float = 0.0
    exceptions_per_second: float = 0.0
    domain_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    tenant_metrics: dict[str, dict[str, Any]] = field(default_factory=dict)
    cross_domain_leakage_detected: bool = False
    leakage_details: list[str] = field(default_factory=list)


@dataclass
class SimulationResult:
    """Result of a simulation run."""

    simulation_id: str
    domains: list[str]
    tenants: list[str]
    metrics: SimulationMetrics
    results: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)


class ExceptionGenerator:
    """Generates synthetic exceptions based on domain pack exception types."""

    def __init__(self, domain_pack: DomainPack):
        """
        Initialize exception generator.
        
        Args:
            domain_pack: Domain pack to generate exceptions for
        """
        self.domain_pack = domain_pack
        self.exception_types = list(domain_pack.exception_types.keys()) if domain_pack.exception_types else []

    def generate_exception(
        self,
        exception_type: Optional[str] = None,
        tenant_id: Optional[str] = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Generate a synthetic exception.
        
        Args:
            exception_type: Optional exception type (random if not provided)
            tenant_id: Optional tenant ID
            **kwargs: Additional fields to include in exception
            
        Returns:
            Synthetic exception dictionary
        """
        if not self.exception_types:
            # Fallback if no exception types defined
            exception_type = exception_type or "UNKNOWN_EXCEPTION"
        else:
            exception_type = exception_type or self.exception_types[
                hash(str(uuid.uuid4())) % len(self.exception_types)
            ]
        
        tenant_id = tenant_id or f"TENANT_{self.domain_pack.domain_name.upper()}"
        
        # Generate base exception structure
        exception = {
            "exceptionId": f"exc_{uuid.uuid4().hex[:12]}",
            "tenantId": tenant_id,
            "domainName": self.domain_pack.domain_name,
            "exceptionType": exception_type,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "rawPayload": {
                "source": "simulation",
                "domain": self.domain_pack.domain_name,
                "exceptionType": exception_type,
                **kwargs,
            },
        }
        
        # Add domain-specific fields based on entities
        if self.domain_pack.entities:
            # Add sample entity data based on domain
            if "TradeOrder" in self.domain_pack.entities:
                # Finance domain
                exception["rawPayload"].update({
                    "orderId": f"ORD_{uuid.uuid4().hex[:8]}",
                    "tradeDate": time.strftime("%Y-%m-%d"),
                    "trader": f"TRADER_{hash(exception_type) % 100}",
                    "buySell": ["BUY", "SELL"][hash(exception_type) % 2],
                    "cusip": f"CUSIP_{uuid.uuid4().hex[:9]}",
                    "price": round(100.0 + (hash(exception_type) % 1000), 2),
                    "quantity": hash(exception_type) % 10000,
                })
            elif "Claim" in self.domain_pack.entities:
                # Healthcare domain
                exception["rawPayload"].update({
                    "claimId": f"CLM_{uuid.uuid4().hex[:8]}",
                    "patientId": f"PAT_{uuid.uuid4().hex[:8]}",
                    "providerId": f"PROV_{uuid.uuid4().hex[:8]}",
                    "procedureCodes": ["99213", "99214"][hash(exception_type) % 2],
                    "amount": round(100.0 + (hash(exception_type) % 5000), 2),
                    "serviceDate": time.strftime("%Y-%m-%d"),
                })
        
        return exception

    def generate_batch(self, count: int, tenant_id: Optional[str] = None) -> list[dict[str, Any]]:
        """
        Generate a batch of synthetic exceptions.
        
        Args:
            count: Number of exceptions to generate
            tenant_id: Optional tenant ID
            
        Returns:
            List of synthetic exceptions
        """
        exceptions = []
        for _ in range(count):
            exception_type = (
                self.exception_types[hash(str(uuid.uuid4())) % len(self.exception_types)]
                if self.exception_types
                else None
            )
            exceptions.append(self.generate_exception(exception_type=exception_type, tenant_id=tenant_id))
        return exceptions


class SimulationRunner:
    """
    Multi-domain simulation runner.
    
    Loads multiple domain packs, generates synthetic exceptions,
    runs them through the orchestrator, and collects metrics.
    """

    def __init__(
        self,
        domain_packs_dir: str = "domainpacks",
        tenant_packs_dir: str = "tenantpacks",
        output_dir: str = "runtime/simulation",
    ):
        """
        Initialize simulation runner.
        
        Args:
            domain_packs_dir: Directory containing domain pack files
            tenant_packs_dir: Directory containing tenant policy pack files
            output_dir: Directory for simulation outputs
        """
        self.domain_packs_dir = Path(domain_packs_dir)
        self.tenant_packs_dir = Path(tenant_packs_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self.domain_packs: dict[str, DomainPack] = {}
        self.tenant_policies: dict[str, TenantPolicyPack] = {}
        self.registry = DomainPackRegistry()
        self.metrics_collector = MetricsCollector()

    def load_domain_packs(self, domain_names: list[str]) -> dict[str, DomainPack]:
        """
        Load domain packs for specified domains.
        
        Args:
            domain_names: List of domain names to load
            
        Returns:
            Dictionary mapping domain names to DomainPack instances
            
        Raises:
            FileNotFoundError: If domain pack file not found
            Exception: If loading or validation fails
        """
        loaded_packs = {}
        
        for domain_name in domain_names:
            # Try to find domain pack file
            possible_files = [
                self.domain_packs_dir / f"{domain_name}.sample.json",
                self.domain_packs_dir / f"{domain_name}.json",
                self.domain_packs_dir / f"{domain_name.lower()}.sample.json",
                self.domain_packs_dir / f"{domain_name.lower()}.json",
            ]
            
            pack_file = None
            for file_path in possible_files:
                if file_path.exists():
                    pack_file = file_path
                    break
            
            if not pack_file:
                raise FileNotFoundError(
                    f"Domain pack file not found for domain '{domain_name}'. "
                    f"Tried: {[str(p) for p in possible_files]}"
                )
            
            logger.info(f"Loading domain pack from {pack_file}")
            domain_pack = load_domain_pack(str(pack_file))
            
            # Register in registry
            tenant_id = f"TENANT_{domain_name.upper()}"
            self.registry.register(domain_pack, version="1.0.0", tenant_id=tenant_id)
            
            loaded_packs[domain_name] = domain_pack
            self.domain_packs[domain_name] = domain_pack
        
        return loaded_packs

    def load_tenant_policies(self, domain_names: list[str]) -> dict[str, TenantPolicyPack]:
        """
        Load tenant policy packs for specified domains.
        
        Args:
            domain_names: List of domain names to load policies for
            
        Returns:
            Dictionary mapping domain names to TenantPolicyPack instances
        """
        loaded_policies = {}
        
        for domain_name in domain_names:
            # Try to find tenant policy pack file
            possible_files = [
                self.tenant_packs_dir / f"tenant_{domain_name}.sample.json",
                self.tenant_packs_dir / f"tenant_{domain_name}.json",
                self.tenant_packs_dir / f"{domain_name}.sample.json",
                self.tenant_packs_dir / f"{domain_name}.json",
            ]
            
            policy_file = None
            for file_path in possible_files:
                if file_path.exists():
                    policy_file = file_path
                    break
            
            if policy_file:
                logger.info(f"Loading tenant policy from {policy_file}")
                tenant_policy = load_tenant_policy(str(policy_file))
                loaded_policies[domain_name] = tenant_policy
                self.tenant_policies[domain_name] = tenant_policy
            else:
                # Create a minimal tenant policy if file not found
                logger.warning(
                    f"Tenant policy file not found for domain '{domain_name}', creating minimal policy"
                )
                tenant_id = f"TENANT_{domain_name.upper()}"
                tenant_policy = TenantPolicyPack(
                    tenant_id=tenant_id,
                    domain_name=domain_name,
                    approved_tools=list(self.domain_packs[domain_name].tools.keys())
                    if domain_name in self.domain_packs
                    else [],
                )
                loaded_policies[domain_name] = tenant_policy
                self.tenant_policies[domain_name] = tenant_policy
        
        return loaded_policies

    async def run_simulation(
        self,
        domain_names: list[str],
        batch_size: int = 100,
        exceptions_per_domain: Optional[int] = None,
    ) -> SimulationResult:
        """
        Run a multi-domain simulation.
        
        Args:
            domain_names: List of domain names to simulate
            batch_size: Number of exceptions per batch
            exceptions_per_domain: Optional number of exceptions per domain (defaults to batch_size)
            
        Returns:
            SimulationResult with metrics and results
        """
        simulation_id = f"sim_{uuid.uuid4().hex[:12]}"
        start_time = time.time()
        
        logger.info(f"Starting simulation {simulation_id} for domains: {domain_names}")
        
        # Load domain packs
        try:
            domain_packs = self.load_domain_packs(domain_names)
        except Exception as e:
            return SimulationResult(
                simulation_id=simulation_id,
                domains=domain_names,
                tenants=[],
                metrics=SimulationMetrics(),
                errors=[f"Failed to load domain packs: {str(e)}"],
            )
        
        # Load tenant policies
        tenant_policies = self.load_tenant_policies(domain_names)
        
        # Validate tenant policies against domain packs
        for domain_name in domain_names:
            if domain_name in tenant_policies and domain_name in domain_packs:
                try:
                    validate_tenant_policy(tenant_policies[domain_name], domain_packs[domain_name])
                except Exception as e:
                    logger.warning(f"Tenant policy validation failed for {domain_name}: {e}")
        
        # Generate exceptions and run pipeline for each domain
        exceptions_per_domain = exceptions_per_domain or batch_size
        tenants = []
        domain_results = {}
        domain_metrics = {}
        errors = []
        
        for domain_name in domain_names:
            if domain_name not in domain_packs:
                errors.append(f"Domain pack not loaded for {domain_name}")
                continue
            
            domain_pack = domain_packs[domain_name]
            tenant_policy = tenant_policies.get(domain_name)
            
            if not tenant_policy:
                errors.append(f"Tenant policy not found for {domain_name}")
                continue
            
            tenant_id = tenant_policy.tenant_id
            tenants.append(tenant_id)
            
            logger.info(f"Generating {exceptions_per_domain} exceptions for domain {domain_name}")
            
            # Generate synthetic exceptions
            generator = ExceptionGenerator(domain_pack)
            exceptions_batch = generator.generate_batch(exceptions_per_domain, tenant_id=tenant_id)
            
            # Run pipeline
            domain_start_time = time.time()
            try:
                result = await run_pipeline(
                    domain_pack=domain_pack,
                    tenant_policy=tenant_policy,
                    exceptions_batch=exceptions_batch,
                    metrics_collector=self.metrics_collector,
                    enable_parallel=True,
                )
                domain_duration = time.time() - domain_start_time
                
                domain_results[domain_name] = result
                domain_metrics[domain_name] = {
                    "exceptions_processed": len(exceptions_batch),
                    "duration_seconds": domain_duration,
                    "exceptions_per_second": len(exceptions_batch) / domain_duration if domain_duration > 0 else 0,
                    "results_count": len(result.get("results", [])),
                }
                
                if domain_duration > 0:
                    logger.info(
                        f"Domain {domain_name} processed {len(exceptions_batch)} exceptions "
                        f"in {domain_duration:.2f}s ({len(exceptions_batch)/domain_duration:.2f} ex/s)"
                    )
                else:
                    logger.info(
                        f"Domain {domain_name} processed {len(exceptions_batch)} exceptions "
                        f"in {domain_duration:.2f}s"
                    )
            except Exception as e:
                error_msg = f"Pipeline execution failed for domain {domain_name}: {str(e)}"
                logger.error(error_msg, exc_info=True)
                errors.append(error_msg)
        
        # Check for cross-domain leakage
        leakage_detected, leakage_details = self._check_cross_domain_leakage(domain_results)
        
        # Calculate overall metrics
        total_duration = time.time() - start_time
        total_exceptions = sum(m.get("exceptions_processed", 0) for m in domain_metrics.values())
        
        metrics = SimulationMetrics(
            total_exceptions=total_exceptions,
            total_domains=len(domain_names),
            total_tenants=len(tenants),
            total_duration_seconds=total_duration,
            exceptions_per_second=total_exceptions / total_duration if total_duration > 0 else 0,
            domain_metrics=domain_metrics,
            tenant_metrics={},  # Can be populated from metrics_collector if needed
            cross_domain_leakage_detected=leakage_detected,
            leakage_details=leakage_details,
        )
        
        result = SimulationResult(
            simulation_id=simulation_id,
            domains=domain_names,
            tenants=tenants,
            metrics=metrics,
            results=domain_results,
            errors=errors,
        )
        
        # Save results
        self._save_results(result)
        
        logger.info(
            f"Simulation {simulation_id} completed: {total_exceptions} exceptions "
            f"across {len(domain_names)} domains in {total_duration:.2f}s"
        )
        
        return result

    def _check_cross_domain_leakage(self, domain_results: dict[str, Any]) -> tuple[bool, list[str]]:
        """
        Check for cross-domain data leakage.
        
        Args:
            domain_results: Dictionary of domain results
            
        Returns:
            Tuple of (leakage_detected, leakage_details)
        """
        leakage_detected = False
        leakage_details = []
        
        # Extract domain names and tenant IDs from results
        domain_tenant_map = {}
        for domain_name, result in domain_results.items():
            tenant_id = result.get("tenantId")
            if tenant_id:
                domain_tenant_map[domain_name] = tenant_id
        
        # If no domain packs loaded, skip detailed checking
        if not self.domain_packs:
            return False, []
        
        # Check each result for cross-domain references
        for domain_name, result in domain_results.items():
            tenant_id = domain_tenant_map.get(domain_name)
            if not tenant_id:
                continue
            
            # Check results for any references to other domains
            for item in result.get("results", []):
                exception = item.get("exception", {})
                # Check both camelCase and snake_case field names
                exception_domain = exception.get("domainName") or exception.get("domain_name")
                exception_tenant = exception.get("tenantId") or exception.get("tenant_id")
                
                # Get expected domain name from domain pack
                expected_domain_name = None
                if domain_name in self.domain_packs:
                    expected_domain_name = self.domain_packs[domain_name].domain_name
                
                # Check if exception belongs to wrong domain
                if exception_domain and expected_domain_name and exception_domain != expected_domain_name:
                    leakage_detected = True
                    leakage_details.append(
                        f"Domain {domain_name} (expected: {expected_domain_name}) processed exception from domain {exception_domain}"
                    )
                
                # Check if exception belongs to wrong tenant
                if exception_tenant and exception_tenant != tenant_id:
                    leakage_detected = True
                    leakage_details.append(
                        f"Tenant {tenant_id} (domain {domain_name}) processed exception for tenant {exception_tenant}"
                    )
        
        return leakage_detected, leakage_details

    def _save_results(self, result: SimulationResult) -> None:
        """
        Save simulation results to file.
        
        Args:
            result: SimulationResult to save
        """
        output_file = self.output_dir / f"{result.simulation_id}.json"
        
        # Convert to dict for JSON serialization
        result_dict = {
            "simulation_id": result.simulation_id,
            "domains": result.domains,
            "tenants": result.tenants,
            "metrics": asdict(result.metrics),
            "errors": result.errors,
            "summary": {
                "total_exceptions": result.metrics.total_exceptions,
                "total_domains": result.metrics.total_domains,
                "total_duration_seconds": result.metrics.total_duration_seconds,
                "exceptions_per_second": result.metrics.exceptions_per_second,
                "cross_domain_leakage_detected": result.metrics.cross_domain_leakage_detected,
            },
        }
        
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2, default=str)
        
        logger.info(f"Simulation results saved to {output_file}")


async def main():
    """CLI entry point for simulation runner."""
    parser = argparse.ArgumentParser(description="Multi-domain simulation and testing harness")
    parser.add_argument(
        "--domains",
        type=str,
        required=True,
        help="Comma-separated list of domain names (e.g., finance,healthcare)",
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=100,
        help="Number of exceptions per domain (default: 100)",
    )
    parser.add_argument(
        "--domain-packs-dir",
        type=str,
        default="domainpacks",
        help="Directory containing domain pack files (default: domainpacks)",
    )
    parser.add_argument(
        "--tenant-packs-dir",
        type=str,
        default="tenantpacks",
        help="Directory containing tenant policy pack files (default: tenantpacks)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="runtime/simulation",
        help="Directory for simulation outputs (default: runtime/simulation)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    
    # Parse domains
    domain_names = [d.strip() for d in args.domains.split(",")]
    
    # Run simulation
    runner = SimulationRunner(
        domain_packs_dir=args.domain_packs_dir,
        tenant_packs_dir=args.tenant_packs_dir,
        output_dir=args.output_dir,
    )
    
    result = await runner.run_simulation(
        domain_names=domain_names,
        batch_size=args.batch,
        exceptions_per_domain=args.batch,
    )
    
    # Print summary
    print("\n" + "=" * 80)
    print("SIMULATION SUMMARY")
    print("=" * 80)
    print(f"Simulation ID: {result.simulation_id}")
    print(f"Domains: {', '.join(result.domains)}")
    print(f"Tenants: {', '.join(result.tenants)}")
    print(f"Total Exceptions: {result.metrics.total_exceptions}")
    print(f"Total Duration: {result.metrics.total_duration_seconds:.2f}s")
    print(f"Throughput: {result.metrics.exceptions_per_second:.2f} exceptions/second")
    print(f"Cross-Domain Leakage: {'DETECTED' if result.metrics.cross_domain_leakage_detected else 'NONE'}")
    
    if result.metrics.cross_domain_leakage_detected:
        print("\nLeakage Details:")
        for detail in result.metrics.leakage_details:
            print(f"  - {detail}")
    
    if result.errors:
        print("\nErrors:")
        for error in result.errors:
            print(f"  - {error}")
    
    print("\nDomain Metrics:")
    for domain_name, metrics in result.metrics.domain_metrics.items():
        print(f"  {domain_name}:")
        print(f"    Exceptions: {metrics.get('exceptions_processed', 0)}")
        print(f"    Duration: {metrics.get('duration_seconds', 0):.2f}s")
        print(f"    Throughput: {metrics.get('exceptions_per_second', 0):.2f} ex/s")
    
    print("=" * 80)
    
    # Exit with error code if leakage detected or errors occurred
    if result.metrics.cross_domain_leakage_detected or result.errors:
        exit(1)


if __name__ == "__main__":
    asyncio.run(main())

