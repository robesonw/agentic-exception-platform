"""
Test script to verify UI endpoints are working with PostgreSQL.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx
from src.infrastructure.db.session import get_db_session_context
from src.repository.exceptions_repository import ExceptionRepository
from src.repository.dto import ExceptionFilter


async def test_direct_db_read():
    """Test reading directly from PostgreSQL."""
    print("\n" + "=" * 70)
    print("1. Testing Direct PostgreSQL Read")
    print("=" * 70)
    
    try:
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            
            # List exceptions for TENANT_FINANCE_001
            result = await repo.list_exceptions(
                tenant_id="TENANT_FINANCE_001",
                filters=ExceptionFilter(),
                page=1,
                page_size=10,
            )
            
            print(f"[OK] Found {result.total} exceptions for TENANT_FINANCE_001")
            print(f"[OK] Retrieved {len(result.items)} items in first page")
            
            if result.items:
                exc = result.items[0]
                print(f"[OK] Sample exception: {exc.exception_id}")
                print(f"     - Domain: {exc.domain}")
                print(f"     - Severity: {exc.severity.value if hasattr(exc.severity, 'value') else exc.severity}")
                print(f"     - Status: {exc.status.value if hasattr(exc.status, 'value') else exc.status}")
                return True
            else:
                print("[WARNING] No exceptions found in database")
                return False
                
    except Exception as e:
        print(f"[FAILED] Error reading from PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_api_endpoint():
    """Test the UI status API endpoint."""
    print("\n" + "=" * 70)
    print("2. Testing UI Status API Endpoint")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Test with API key
            headers = {
                "X-API-KEY": "test_api_key_tenant_finance",
            }
            
            url = "http://localhost:8000/ui/status/TENANT_FINANCE_001?limit=5"
            print(f"[INFO] Calling: {url}")
            
            response = await client.get(url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned data")
                print(f"     - Total: {data.get('total', 0)}")
                print(f"     - Exceptions returned: {len(data.get('exceptions', []))}")
                
                if data.get('exceptions'):
                    exc = data['exceptions'][0]
                    print(f"[OK] Sample exception from API:")
                    print(f"     - ID: {exc.get('exceptionId')}")
                    print(f"     - Type: {exc.get('exceptionType')}")
                    print(f"     - Severity: {exc.get('severity')}")
                    print(f"     - Status: {exc.get('status')}")
                    print(f"     - Domain: {exc.get('domain', 'N/A')}")
                    return True
                else:
                    print("[WARNING] API returned empty exceptions list")
                    print(f"     Response: {data}")
                    return False
            else:
                print(f"[FAILED] API returned error: {response.status_code}")
                print(f"     Response: {response.text}")
                return False
                
    except httpx.ConnectError:
        print("[FAILED] Could not connect to API server. Is it running?")
        return False
    except Exception as e:
        print(f"[FAILED] Error calling API: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_exception_detail_endpoint():
    """Test the exception detail API endpoint."""
    print("\n" + "=" * 70)
    print("3. Testing Exception Detail API Endpoint")
    print("=" * 70)
    
    try:
        # First get an exception ID from database
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            result = await repo.list_exceptions(
                tenant_id="TENANT_FINANCE_001",
                filters=ExceptionFilter(),
                page=1,
                page_size=1,
            )
            
            if not result.items:
                print("[SKIP] No exceptions found to test detail endpoint")
                return True
            
            exception_id = result.items[0].exception_id
            print(f"[INFO] Testing with exception: {exception_id}")
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                headers = {
                    "X-API-KEY": "test_api_key_tenant_finance",
                }
                
                url = f"http://localhost:8000/exceptions/TENANT_FINANCE_001/{exception_id}"
                print(f"[INFO] Calling: {url}")
                
                response = await client.get(url, headers=headers)
                
                print(f"[INFO] Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    print(f"[OK] API returned exception details")
                    print(f"     - Exception ID: {data.get('exceptionId')}")
                    print(f"     - Tenant ID: {data.get('tenantId')}")
                    print(f"     - Status: {data.get('resolutionStatus')}")
                    return True
                else:
                    print(f"[FAILED] API returned error: {response.status_code}")
                    print(f"     Response: {response.text}")
                    return False
                    
    except Exception as e:
        print(f"[FAILED] Error testing detail endpoint: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all tests."""
    print("=" * 70)
    print("UI Endpoint Integration Test")
    print("=" * 70)
    
    results = []
    
    results.append(("Direct DB Read", await test_direct_db_read()))
    results.append(("UI Status API", await test_api_endpoint()))
    results.append(("Exception Detail API", await test_exception_detail_endpoint()))
    
    print("\n" + "=" * 70)
    print("Test Summary")
    print("=" * 70)
    
    for name, result in results:
        status = "[OK]" if result else "[FAILED]"
        print(f"{status} {name}")
    
    all_ok = all(result for _, result in results)
    
    if not all_ok:
        print("\n" + "=" * 70)
        print("Troubleshooting")
        print("=" * 70)
        print("1. Ensure API server is running:")
        print("   uvicorn src.api.main:app --reload")
        print("\n2. Ensure DATABASE_URL is set in API server environment:")
        print('   $env:DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/sentinai"')
        print("\n3. Check API server logs for errors")
        print("\n4. Verify data exists in database:")
        print('   docker exec sentinai-postgres psql -U postgres -d sentinai -c "SELECT COUNT(*) FROM exception;"')
    
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

