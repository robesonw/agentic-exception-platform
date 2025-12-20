"""
Test script for Phase 12 onboarding endpoints.

This script:
1. Checks if database tables exist
2. Tests the /admin/packs/domain endpoint
3. Provides helpful error messages

Run this after running: alembic upgrade head
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from fastapi.testclient import TestClient
from src.api.main import app

client = TestClient(app)


def test_domain_packs_endpoint():
    """Test the domain packs listing endpoint."""
    print("Testing GET /admin/packs/domain...")
    
    # Test without auth (should get 401 or 403)
    response = client.get("/admin/packs/domain")
    print(f"  Status without auth: {response.status_code}")
    
    # Test with API key (if available)
    response = client.get(
        "/admin/packs/domain",
        headers={"X-API-KEY": "test_api_key"},
    )
    print(f"  Status with API key: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  SUCCESS! Found {data.get('total', 0)} domain packs")
        print(f"  Items: {len(data.get('items', []))}")
        return True
    elif response.status_code == 503:
        print(f"  WARNING: Service Unavailable: {response.json().get('detail', 'Unknown error')}")
        print("  -> Run: alembic upgrade head")
        return False
    elif response.status_code == 401 or response.status_code == 403:
        print(f"  WARNING: Auth required: {response.status_code}")
        print("  -> Make sure you have a valid API key")
        return False
    else:
        print(f"  ERROR {response.status_code}: {response.text}")
        return False


def check_database_tables():
    """Check if Phase 12 database tables exist."""
    print("\nChecking database tables...")
    try:
        from src.infrastructure.db.session import get_db_session_context
        from sqlalchemy import text
        
        async def check_tables():
            async with get_db_session_context() as session:
                # Check if domain_packs table exists
                result = await session.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'domain_packs')")
                )
                domain_packs_exists = result.scalar()
                
                result = await session.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tenant_packs')")
                )
                tenant_packs_exists = result.scalar()
                
                result = await session.execute(
                    text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'tenant_active_config')")
                )
                active_config_exists = result.scalar()
                
                return domain_packs_exists, tenant_packs_exists, active_config_exists
        
        domain_exists, tenant_exists, config_exists = asyncio.run(check_tables())
        
        print(f"  domain_packs: {'OK' if domain_exists else 'MISSING'}")
        print(f"  tenant_packs: {'OK' if tenant_exists else 'MISSING'}")
        print(f"  tenant_active_config: {'OK' if config_exists else 'MISSING'}")
        
        if not (domain_exists and tenant_exists and config_exists):
            print("\n  WARNING: Missing tables! Run: alembic upgrade head")
            return False
        
        return True
    except Exception as e:
        print(f"  ERROR checking tables: {e}")
        print("  -> Make sure database is running and DATABASE_URL is set")
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Phase 12 Endpoint Test")
    print("=" * 60)
    
    # Check tables first
    tables_ok = check_database_tables()
    
    if tables_ok:
        # Test endpoint
        test_domain_packs_endpoint()
    else:
        print("\nWARNING: Please run migrations first:")
        print("   alembic upgrade head")
    
    print("\n" + "=" * 60)

