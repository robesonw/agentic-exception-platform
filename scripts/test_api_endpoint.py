"""
Test script to verify the API can connect to the database and list exceptions.
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
except ImportError:
    pass

async def test_api_connection():
    """Test API database connection."""
    from src.infrastructure.db.session import get_db_session_context
    from src.repository.exceptions_repository import ExceptionRepository
    from src.repository.dto import ExceptionFilter
    
    print("[TEST] Testing API database connection...")
    
    try:
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            
            # Try to list exceptions (should work even if empty)
            result = await repo.list_exceptions(
                tenant_id="test_tenant",
                filters=ExceptionFilter(),
                page=1,
                page_size=10,
            )
            
            print(f"[SUCCESS] API can connect to database!")
            print(f"   Found {result.total} exceptions for test_tenant")
            print(f"   Items returned: {len(result.items)}")
            return True
            
    except Exception as e:
        print(f"[ERROR] API database connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_api_connection())
    sys.exit(0 if success else 1)

