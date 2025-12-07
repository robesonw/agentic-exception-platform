#!/usr/bin/env python3
"""
Quick script to re-seed UI data.
This is a convenience wrapper around seed_ui_data_simple.py.

Usage:
    python scripts/reseed_data.py
"""

import subprocess
import sys
from pathlib import Path

def main():
    """Run the seed script."""
    script_path = Path(__file__).parent / "seed_ui_data_simple.py"
    
    if not script_path.exists():
        print(f"Error: Seed script not found at {script_path}")
        sys.exit(1)
    
    print("=" * 60)
    print("Re-seeding UI data...")
    print("=" * 60)
    print()
    
    try:
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=Path(__file__).parent.parent,
            check=True
        )
        print()
        print("=" * 60)
        print("Data seeding completed successfully!")
        print("=" * 60)
        print()
        print("You can now view the data in the UI:")
        print("1. Make sure the UI dev server is running: cd ui && npm run dev")
        print("2. Navigate to http://localhost:5173/login")
        print("3. Select tenant: TENANT_FINANCE_001")
        print("4. Select API key: test_api_key_tenant_finance")
        print("5. Click 'Login' and navigate to Exceptions page")
        return 0
    except subprocess.CalledProcessError as e:
        print(f"Error running seed script: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nSeeding cancelled by user")
        return 1

if __name__ == "__main__":
    sys.exit(main())

