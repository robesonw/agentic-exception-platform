#!/usr/bin/env python3
"""
Demo data seeder CLI for SentinAI platform.

Usage:
    python scripts/seed_demo_data.py --tenant TENANT_FINANCE_001 --domain Finance --count 200 --reset
    python scripts/seed_demo_data.py --all-tenants --count 500 --reset
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv(project_root / ".env")
except ImportError:
    # python-dotenv not installed, skip .env loading
    pass

from sqlalchemy.ext.asyncio import AsyncSession

from src.demo.seeder import DemoDataSeeder
from src.infrastructure.db.session import get_session_factory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# Tenant configuration
TENANT_CONFIG = {
    "TENANT_FINANCE_001": {
        "name": "Finance Trading Demo Tenant",
        "domain": "CapitalMarketsTrading",
    },
    "TENANT_HEALTH_001": {
        "name": "Healthcare Claims Demo Tenant",
        "domain": "HealthcareClaimsAndCareOps",
    },
}


async def seed_tenant(
    tenant_id: str,
    domain: str,
    count: int,
    reset: bool,
    seed: int | None = None,
) -> None:
    """Seed a single tenant."""
    session_factory = get_session_factory()
    
    async with session_factory() as session:
        seeder = DemoDataSeeder(session, seed=seed)
        
        try:
            if reset:
                await seeder.reset_tenant_data(tenant_id)
            
            # Seed tenant, domain pack, policy pack, playbooks, tools
            await seeder.seed_tenant(
                tenant_id=tenant_id,
                tenant_name=TENANT_CONFIG[tenant_id]["name"],
                domain=domain,
            )
            
            # Seed exceptions with timelines
            await seeder.seed_exceptions(tenant_id=tenant_id, domain=domain, count=count)
            
            logger.info(f"✅ Successfully seeded tenant: {tenant_id}")
        except Exception as e:
            logger.error(f"❌ Error seeding tenant {tenant_id}: {e}", exc_info=True)
            await session.rollback()
            raise


async def seed_all_tenants(count: int, reset: bool, seed: int | None = None) -> None:
    """Seed all configured tenants."""
    for tenant_id, config in TENANT_CONFIG.items():
        logger.info(f"\n{'='*60}")
        logger.info(f"Seeding tenant: {tenant_id}")
        logger.info(f"{'='*60}\n")
        
        await seed_tenant(
            tenant_id=tenant_id,
            domain=config["domain"],
            count=count,
            reset=reset,
            seed=seed,
        )


def main() -> None:
    """Main CLI entrypoint."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Seed demo data for SentinAI platform",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Seed single tenant
  python scripts/seed_demo_data.py --tenant TENANT_FINANCE_001 --domain CapitalMarketsTrading --count 200 --reset
  
  # Seed all tenants
  python scripts/seed_demo_data.py --all-tenants --count 500 --reset
  
  # Deterministic seed
  python scripts/seed_demo_data.py --all-tenants --count 100 --seed 42
        """,
    )
    
    parser.add_argument(
        "--tenant",
        type=str,
        help="Tenant ID to seed (e.g., TENANT_FINANCE_001)",
    )
    parser.add_argument(
        "--domain",
        type=str,
        help="Domain name (CapitalMarketsTrading or HealthcareClaimsAndCareOps)",
    )
    parser.add_argument(
        "--all-tenants",
        action="store_true",
        help="Seed all configured tenants",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of exceptions to generate per tenant (default: 100)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset existing demo data for tenant(s) before seeding",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for deterministic generation",
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.all_tenants:
        if args.tenant or args.domain:
            parser.error("--all-tenants cannot be used with --tenant or --domain")
    else:
        if not args.tenant:
            parser.error("Either --tenant or --all-tenants must be specified")
        if not args.domain:
            parser.error("--domain is required when using --tenant")
        if args.tenant not in TENANT_CONFIG:
            parser.error(f"Unknown tenant: {args.tenant}. Available: {list(TENANT_CONFIG.keys())}")
        if args.domain != TENANT_CONFIG[args.tenant]["domain"]:
            logger.warning(
                f"Domain mismatch: provided '{args.domain}', expected '{TENANT_CONFIG[args.tenant]['domain']}'. "
                f"Using expected domain."
            )
            args.domain = TENANT_CONFIG[args.tenant]["domain"]
    
    # Run seeding
    try:
        if args.all_tenants:
            asyncio.run(seed_all_tenants(count=args.count, reset=args.reset, seed=args.seed))
        else:
            asyncio.run(
                seed_tenant(
                    tenant_id=args.tenant,
                    domain=args.domain,
                    count=args.count,
                    reset=args.reset,
                    seed=args.seed,
                )
            )
        
        logger.info("\n✅ Demo data seeding completed successfully!")
    except KeyboardInterrupt:
        logger.info("\n⚠️  Seeding interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"\n❌ Seeding failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

