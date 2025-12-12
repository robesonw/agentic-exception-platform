"""
Test the actual UI endpoint that the frontend calls: GET /ui/exceptions
"""

import asyncio
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import httpx


async def test_ui_exceptions_endpoint():
    """Test GET /ui/exceptions endpoint."""
    print("=" * 70)
    print("Testing UI Exceptions Endpoint (GET /ui/exceptions)")
    print("=" * 70)
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            headers = {
                "X-API-KEY": "test_api_key_tenant_finance",
            }
            
            # Test with tenant_id query parameter
            url = "http://localhost:8000/ui/exceptions?tenant_id=TENANT_FINANCE_001&page=1&page_size=10"
            print(f"\n[INFO] Calling: {url}")
            
            response = await client.get(url, headers=headers)
            
            print(f"[INFO] Response status: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"[OK] API returned data successfully")
                print(f"     - Total: {data.get('total', 0)}")
                print(f"     - Page: {data.get('page', 0)}")
                print(f"     - Page size: {data.get('page_size', 0)}")
                print(f"     - Total pages: {data.get('total_pages', 0)}")
                print(f"     - Items returned: {len(data.get('items', []))}")
                
                if data.get('items'):
                    item = data['items'][0]
                    # Response uses ExceptionListItem which has snake_case fields
                    print(f"\n[OK] Sample exception (raw item):")
                    print(f"     - Exception ID: {item.get('exception_id')}")
                    print(f"     - Tenant ID: {item.get('tenant_id')}")
                    print(f"     - Domain: {item.get('domain')}")
                    print(f"     - Type: {item.get('exception_type')}")
                    print(f"     - Severity: {item.get('severity')}")
                    print(f"     - Status: {item.get('resolution_status')}")
                    print(f"     - Source System: {item.get('source_system')}")
                    print(f"     - Timestamp: {item.get('timestamp')}")
                    return True
                else:
                    print("[WARNING] API returned empty items list")
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
        print(f"[FAILED] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    result = await test_ui_exceptions_endpoint()
    
    print("\n" + "=" * 70)
    if result:
        print("[SUCCESS] UI exceptions endpoint is working!")
        print("\nThe UI should now be able to fetch exceptions from PostgreSQL.")
    else:
        print("[FAILED] UI exceptions endpoint test failed.")
        print("\nTroubleshooting:")
        print("1. Ensure API server is running with DATABASE_URL set")
        print("2. Check API server logs for errors")
        print("3. Verify data exists in database")
    print("=" * 70)
    
    return 0 if result else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

