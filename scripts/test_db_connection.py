"""
Quick script to test database connection with current DATABASE_URL.
"""
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load .env if it exists
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"[OK] Loaded .env file from {env_path}")
    else:
        print(f"[WARN] .env file not found at {env_path}")
except ImportError:
    print("[WARN] python-dotenv not installed, skipping .env loading")

async def test_connection():
    """Test database connection."""
    from src.infrastructure.db.settings import get_database_url
    from src.infrastructure.db.session import get_engine, check_database_connection
    
    # Get database URL
    database_url = get_database_url()
    
    # Mask password for display
    safe_url = database_url
    if "@" in database_url and "://" in database_url:
        parts = database_url.split("://", 1)
        if len(parts) == 2:
            scheme = parts[0]
            rest = parts[1]
            if "@" in rest:
                auth_part, host_part = rest.split("@", 1)
                if ":" in auth_part:
                    user, _ = auth_part.split(":", 1)
                    safe_url = f"{scheme}://{user}:***@{host_part}"
    
    print(f"\n[INFO] Database Configuration:")
    print(f"   URL: {safe_url}")
    print(f"   From env: {'DATABASE_URL' if os.getenv('DATABASE_URL') else 'DB_* variables or defaults'}")
    
    print(f"\n[TEST] Testing connection...")
    
    try:
        # Create engine
        engine = get_engine()
        
        # Test connection
        connected = await check_database_connection(retries=1, initial_delay=0.5)
        
        if connected:
            print("[SUCCESS] Database connection successful!")
            return True
        else:
            print("[FAILED] Database connection failed!")
            print("\n[TIPS] Troubleshooting:")
            print("   1. Verify PostgreSQL is running")
            print("   2. Check database credentials in .env file")
            print("   3. Ensure database user exists and has correct password")
            print("   4. Verify database name exists")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error connecting to database: {e}")
        print("\n[TIPS] Common issues:")
        print("   - PostgreSQL not running")
        print("   - Wrong username/password")
        print("   - Database doesn't exist")
        print("   - Connection string format incorrect")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)

