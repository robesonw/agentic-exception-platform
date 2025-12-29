"""
Test the exact curl command the user is experiencing issues with.
"""
from fastapi.testclient import TestClient
from src.api.main import app

def test_exact_user_request():
    """Test the exact request the user is making."""
    
    print("🧪 TESTING EXACT USER CURL COMMAND")
    print("="*50)
    
    client = TestClient(app)
    
    # Exact headers from user's curl command
    headers = {
        'x-api-key': 'test_api_key_tenant_001',
        'Content-Type': 'application/json', 
        'x-tenant-id': 'TENANT_FINANCE_001'
    }
    
    print(f"Request: GET /api/copilot/evidence/req_12345")
    print(f"Headers: {headers}")
    
    try:
        response = client.get("/api/copilot/evidence/req_12345", headers=headers)
        
        print(f"\\nResponse:")
        print(f"Status: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Content: {response.text}")
        
        if response.status_code == 200:
            try:
                json_response = response.json()
                print(f"\\n✅ SUCCESS - JSON Response:")
                print(f"  request_id: {json_response.get('request_id')}")
                print(f"  tenant_id: {json_response.get('tenant_id')}")
                print(f"  outcome_summary: {json_response.get('outcome_summary')}")
                print(f"  Has debug info: {bool(json_response.get('retrieval_debug'))}")
                return True
            except Exception as json_err:
                print(f"❌ JSON parse error: {json_err}")
                return False
        else:
            print(f"\\n❌ HTTP {response.status_code} Error")
            return False
            
    except Exception as e:
        print(f"\\n💥 Request failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_exact_user_request()
    if success:
        print("\\n🎉 User's curl command should work!")
    else:
        print("\\n💥 User's curl command has issues that need fixing.")