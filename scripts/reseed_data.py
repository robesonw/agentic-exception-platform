#!/usr/bin/env python3
"""
Quick script to re-seed UI data.

This script can use either:
1. In-memory store (seed_ui_data_simple.py) - for Phase 1-2
2. PostgreSQL via API (seed_postgres_via_api.py) - for Phase 6+

Usage:
    python scripts/reseed_data.py [--use-postgres]
"""

import argparse
import subprocess
import sys
from pathlib import Path

def main():
    """Run the seed script."""
    parser = argparse.ArgumentParser(description="Re-seed UI data")
    parser.add_argument(
        "--use-postgres",
        action="store_true",
        help="Use PostgreSQL seeding via API (Phase 6+) instead of in-memory store",
    )
    parser.add_argument(
        "--api-url",
        default="http://localhost:8000",
        help="API server URL (only used with --use-postgres)",
    )
    
    args = parser.parse_args()
    
    if args.use_postgres:
        script_path = Path(__file__).parent / "seed_postgres_via_api.py"
        print("=" * 60)
        print("Re-seeding PostgreSQL database via API...")
        print("=" * 60)
        print()
        print("Prerequisites:")
        print("  1. PostgreSQL must be running: .\\scripts\\docker_db.ps1 start")
        print("  2. Migrations applied: alembic upgrade head")
        print("  3. API server running: uvicorn src.api.main:app --reload")
        print()
    else:
        script_path = Path(__file__).parent / "seed_ui_data_simple.py"
        print("=" * 60)
        print("Re-seeding UI data (in-memory store)...")
        print("=" * 60)
        print()
    
    if not script_path.exists():
        print(f"Error: Seed script not found at {script_path}")
        sys.exit(1)
    
    try:
        cmd = [sys.executable, str(script_path)]
        if args.use_postgres and args.api_url:
            cmd.extend(["--api-url", args.api_url])
        
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).parent.parent,
            check=True
        )
        print()
        print("=" * 60)
        print("Data seeding completed successfully!")
        print("=" * 60)
        print()
        
        if args.use_postgres:
            print("Data is now in PostgreSQL and visible in UI:")
            print("1. Verify in database:")
            print("   docker exec sentinai-postgres psql -U postgres -d sentinai -c \"SELECT COUNT(*) FROM exception;\"")
            print("2. View in UI:")
        else:
            print("You can now view the data in the UI:")
        
        print("   - Make sure the UI dev server is running: cd ui && npm run dev")
        print("   - Navigate to http://localhost:5173/login")
        print("   - Select tenant: TENANT_FINANCE_001")
        print("   - Select API key: test_api_key_tenant_finance")
        print("   - Click 'Login' and navigate to Exceptions page")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error running seed script: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nSeeding cancelled by user")
        return 1

if __name__ == "__main__":
    sys.exit(main())

