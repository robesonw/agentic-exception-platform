#!/usr/bin/env python3
"""
Multi-Tenant Performance Smoke Test (P3-24).

Spins up synthetic tenants/domains, sends traffic, and logs latency + resource usage.

Usage:
    python scripts/run_multitenant_smoke.py [--tenants N] [--domains-per-tenant M] [--exceptions-per-domain K]
"""

import argparse
import asyncio
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.cache import get_domain_pack_cache
from src.infrastructure.resources import get_resource_pool_registry
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import get_exception_store

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def create_synthetic_domain_pack(domain_name: str) -> DomainPack:
    """Create a synthetic domain pack for testing."""
    from src.models.domain_pack import (
        ExceptionTypeDefinition,
        Guardrails,
        SeverityRule,
    )
    
    return DomainPack(
        domain_name=domain_name,
        exception_types={
            "TestException": ExceptionTypeDefinition(
                name="TestException",
                description="Test exception type",
                detection_rules=["test"],
                severity_rules=[],
            )
        },
        severity_rules=[
            SeverityRule(condition="true", severity="MEDIUM", priority_score=5)
        ],
        guardrails=Guardrails(),
    )


def create_synthetic_exception(
    tenant_id: str, domain: str, exception_id: str
) -> ExceptionRecord:
    """Create a synthetic exception record."""
    return ExceptionRecord(
        exception_id=exception_id,
        tenant_id=tenant_id,
        exception_type="TestException",
        severity=Severity.MEDIUM,
        resolution_status=ResolutionStatus.OPEN,
        source_system="smoke_test",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"test": "data"},
        normalized_context={"domain": domain},
    )


async def simulate_tenant_traffic(
    tenant_id: str,
    domains: list[str],
    exceptions_per_domain: int,
    exception_store,
    domain_pack_cache,
) -> dict[str, Any]:
    """
    Simulate traffic for a single tenant across multiple domains.
    
    Returns:
        Dictionary with performance metrics
    """
    start_time = time.time()
    total_exceptions = 0
    cache_hits = 0
    cache_misses = 0
    
    # Load domain packs (simulating cache usage)
    for domain in domains:
        pack = create_synthetic_domain_pack(domain)
        domain_pack_cache.put_pack(tenant_id, domain, "1.0.0", pack)
        
        # Simulate exception processing
        for i in range(exceptions_per_domain):
            exception_id = f"{tenant_id}_{domain}_{i}"
            exception = create_synthetic_exception(tenant_id, domain, exception_id)
            
            # Store exception
            exception_store.store_exception(exception, {"test": "result"})
            total_exceptions += 1
            
            # Simulate cache access
            cached_pack = domain_pack_cache.get_pack(tenant_id, domain, "1.0.0")
            if cached_pack:
                cache_hits += 1
            else:
                cache_misses += 1
    
    elapsed_time = time.time() - start_time
    
    return {
        "tenant_id": tenant_id,
        "domains": len(domains),
        "total_exceptions": total_exceptions,
        "elapsed_time_seconds": elapsed_time,
        "exceptions_per_second": total_exceptions / elapsed_time if elapsed_time > 0 else 0,
        "cache_hits": cache_hits,
        "cache_misses": cache_misses,
    }


async def run_smoke_test(
    num_tenants: int = 10,
    domains_per_tenant: int = 5,
    exceptions_per_domain: int = 20,
) -> dict[str, Any]:
    """
    Run multi-tenant smoke test.
    
    Args:
        num_tenants: Number of synthetic tenants
        domains_per_tenant: Number of domains per tenant
        exceptions_per_domain: Number of exceptions per domain
        
    Returns:
        Dictionary with overall test results
    """
    logger.info("=" * 60)
    logger.info("Multi-Tenant Performance Smoke Test")
    logger.info("=" * 60)
    logger.info(f"Tenants: {num_tenants}")
    logger.info(f"Domains per tenant: {domains_per_tenant}")
    logger.info(f"Exceptions per domain: {exceptions_per_domain}")
    logger.info("")
    
    # Initialize components
    exception_store = get_exception_store()
    domain_pack_cache = get_domain_pack_cache()
    resource_pool_registry = get_resource_pool_registry()
    
    # Clear existing data
    exception_store.clear_all()
    domain_pack_cache.clear()
    
    # Generate tenant and domain names
    tenants = [f"tenant_{i:03d}" for i in range(num_tenants)]
    all_domains = [f"domain_{i:03d}" for i in range(domains_per_tenant)]
    
    # Run tests
    start_time = time.time()
    tenant_results = []
    
    for tenant_id in tenants:
        logger.info(f"Processing tenant: {tenant_id}")
        result = await simulate_tenant_traffic(
            tenant_id,
            all_domains,
            exceptions_per_domain,
            exception_store,
            domain_pack_cache,
        )
        tenant_results.append(result)
        logger.info(
            f"  Processed {result['total_exceptions']} exceptions in "
            f"{result['elapsed_time_seconds']:.2f}s "
            f"({result['exceptions_per_second']:.2f} ex/s)"
        )
    
    total_elapsed = time.time() - start_time
    
    # Get cache stats
    cache_stats = domain_pack_cache.get_stats()
    resource_stats = resource_pool_registry.get_stats()
    
    # Aggregate results
    total_exceptions = sum(r["total_exceptions"] for r in tenant_results)
    total_cache_hits = sum(r["cache_hits"] for r in tenant_results)
    total_cache_misses = sum(r["cache_misses"] for r in tenant_results)
    
    results = {
        "test_config": {
            "num_tenants": num_tenants,
            "domains_per_tenant": domains_per_tenant,
            "exceptions_per_domain": exceptions_per_domain,
        },
        "performance": {
            "total_elapsed_seconds": total_elapsed,
            "total_exceptions": total_exceptions,
            "exceptions_per_second": total_exceptions / total_elapsed if total_elapsed > 0 else 0,
            "avg_time_per_tenant": total_elapsed / num_tenants if num_tenants > 0 else 0,
        },
        "cache": {
            "hits": total_cache_hits,
            "misses": total_cache_misses,
            "hit_rate_percent": (
                total_cache_hits / (total_cache_hits + total_cache_misses) * 100
                if (total_cache_hits + total_cache_misses) > 0
                else 0
            ),
            "cache_size": cache_stats["size"],
            "cache_max_size": cache_stats["max_size"],
        },
        "resources": {
            "total_pools": resource_stats["total_pools"],
            "tenant_ids": len(resource_stats["tenant_ids"]),
        },
        "tenant_results": tenant_results,
    }
    
    return results


def print_results(results: dict[str, Any]) -> None:
    """Print test results in a readable format."""
    logger.info("")
    logger.info("=" * 60)
    logger.info("Test Results")
    logger.info("=" * 60)
    
    perf = results["performance"]
    logger.info(f"Total Time: {perf['total_elapsed_seconds']:.2f}s")
    logger.info(f"Total Exceptions: {perf['total_exceptions']}")
    logger.info(f"Throughput: {perf['exceptions_per_second']:.2f} exceptions/second")
    logger.info(f"Avg Time per Tenant: {perf['avg_time_per_tenant']:.2f}s")
    
    cache = results["cache"]
    logger.info("")
    logger.info("Cache Performance:")
    logger.info(f"  Hits: {cache['hits']}")
    logger.info(f"  Misses: {cache['misses']}")
    logger.info(f"  Hit Rate: {cache['hit_rate_percent']:.2f}%")
    logger.info(f"  Cache Size: {cache['cache_size']}/{cache['cache_max_size']}")
    
    resources = results["resources"]
    logger.info("")
    logger.info("Resource Pools:")
    logger.info(f"  Total Pools: {resources['total_pools']}")
    logger.info(f"  Active Tenants: {resources['tenant_ids']}")
    
    logger.info("")
    logger.info("=" * 60)


def main():
    """Main entry point for smoke test."""
    parser = argparse.ArgumentParser(
        description="Run multi-tenant performance smoke test"
    )
    parser.add_argument(
        "--tenants",
        type=int,
        default=10,
        help="Number of synthetic tenants (default: 10)",
    )
    parser.add_argument(
        "--domains-per-tenant",
        type=int,
        default=5,
        help="Number of domains per tenant (default: 5)",
    )
    parser.add_argument(
        "--exceptions-per-domain",
        type=int,
        default=20,
        help="Number of exceptions per domain (default: 20)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Optional output file for JSON results",
    )
    
    args = parser.parse_args()
    
    # Run test
    results = asyncio.run(
        run_smoke_test(
            num_tenants=args.tenants,
            domains_per_tenant=args.domains_per_tenant,
            exceptions_per_domain=args.exceptions_per_domain,
        )
    )
    
    # Print results
    print_results(results)
    
    # Write to file if requested
    if args.output:
        import json
        
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, default=str)
        logger.info(f"Results written to {output_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

