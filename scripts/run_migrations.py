"""
Helper script to run Alembic migrations.

This script runs: alembic upgrade head

Make sure:
1. Database is running
2. DATABASE_URL environment variable is set correctly
3. Database user has permissions to create tables
"""

import subprocess
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent

def run_migrations():
    """Run Alembic migrations."""
    print("Running Alembic migrations...")
    print("=" * 60)
    
    try:
        # Run alembic upgrade head
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=project_root,
            capture_output=True,
            text=True,
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode == 0:
            print("\n" + "=" * 60)
            print("SUCCESS: Migrations completed!")
            return True
        else:
            print("\n" + "=" * 60)
            print(f"ERROR: Migration failed with code {result.returncode}")
            return False
    except FileNotFoundError:
        print("ERROR: alembic command not found")
        print("Make sure alembic is installed: pip install alembic")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

if __name__ == "__main__":
    success = run_migrations()
    sys.exit(0 if success else 1)

