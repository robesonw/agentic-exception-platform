"""
Test the exceptions list endpoint that was failing.
"""
import requests
import sys

def test_exceptions_endpoint():
    """Test the GET /ui/exceptions endpoint."""
    base_url = "http://localhost:8000"
    
    # Test endpoint that was failing
    endpoint = f"{base_url}/ui/exceptions"
    
    print(f"[TEST] Testing endpoint: {endpoint}")
    print(f"[INFO] This endpoint requires tenant_id query parameter")
    
    # Use a test API key (from src/api/auth.py)
    # test-api-key-123 maps to tenant_001
    api_key = "test-api-key-123"
    tenant_id = "tenant_001"
    
    # Test with a tenant_id
    params = {
        "tenant_id": tenant_id,
        "page": 1,
        "page_size": 10
    }
    
    headers = {
        "X-API-KEY": api_key
    }
    
    try:
        print(f"\n[REQUEST] GET {endpoint}")
        print(f"         Params: {params}")
        print(f"         Headers: X-API-KEY: {api_key[:10]}...")
        
        response = requests.get(endpoint, params=params, headers=headers, timeout=10)
        
        print(f"\n[RESPONSE] Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"[SUCCESS] Endpoint works!")
            print(f"   Total: {data.get('total', 0)}")
            print(f"   Items: {len(data.get('items', []))}")
            print(f"   Page: {data.get('page', 1)}")
            return True
        else:
            print(f"[ERROR] Endpoint returned error:")
            print(f"   Status: {response.status_code}")
            print(f"   Response: {response.text[:500]}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Could not connect to API server at {base_url}")
        print(f"        Make sure the server is running: uvicorn src.api.main:app --reload")
        return False
    except Exception as e:
        print(f"[ERROR] Request failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_exceptions_endpoint()
    sys.exit(0 if success else 1)

