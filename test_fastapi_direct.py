"""
Direct test of the FastAPI copilot endpoints without running a server.
"""
import asyncio
from fastapi.testclient import TestClient
from src.api.main import app

def test_copilot_session_creation():
    """Test the copilot session creation endpoint directly."""
    
    print("=== TESTING FASTAPI COPILOT ENDPOINT DIRECTLY ===")
    
    # Create test client
    client = TestClient(app)
    
    # Test data
    headers = {
        "X-API-KEY": "test_api_key_tenant_001",
        "Content-Type": "application/json"
    }
    
    data = {
        "title": "My Exception Analysis Session"
    }
    
    print(f"Testing POST /api/copilot/sessions")
    print(f"Headers: {headers}")
    print(f"Data: {data}")
    
    try:
        # Make the request
        response = client.post("/api/copilot/sessions", headers=headers, json=data)
        
        print(f"\\nResponse:")
        print(f"Status code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")
        print(f"Content: {response.text}")
        
        if response.status_code == 200:
            json_response = response.json()
            print(f"\\n✅ SUCCESS!")
            print(f"Session ID: {json_response.get('session_id')}")
            print(f"Title: {json_response.get('title')}")
            print(f"Created at: {json_response.get('created_at')}")
            return True
        else:
            print(f"\\n❌ FAILED with status {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error: {error_detail}")
            except:
                print(f"Raw error: {response.text}")
            return False
            
    except Exception as e:
        print(f"\\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_evidence_debug_admin():
    """Test the evidence debug endpoint with admin access."""
    
    print("\\n=== TESTING EVIDENCE DEBUG ENDPOINT (ADMIN) ===")
    
    # Create test client
    client = TestClient(app)
    
    # Test data - admin API key
    headers = {
        "X-API-KEY": "test_api_key_tenant_001",  # ADMIN role
        "Content-Type": "application/json"
    }
    
    print(f"Testing GET /api/copilot/evidence/req_12345")
    print(f"Headers: {headers}")
    
    try:
        # Make the request
        response = client.get("/api/copilot/evidence/req_12345", headers=headers)
        
        print(f"\\nResponse:")
        print(f"Status code: {response.status_code}")
        print(f"Content: {response.text}")
        
        if response.status_code == 200:
            json_response = response.json()
            print(f"\\n✅ ADMIN ACCESS SUCCESS!")
            print(f"Request ID: {json_response.get('request_id')}")
            print(f"Tenant ID: {json_response.get('tenant_id')}")
            print(f"Outcome Summary: {json_response.get('outcome_summary')}")
            print(f"Has retrieval_debug: {'retrieval_debug' in json_response}")
            print(f"Has intent_debug: {'intent_debug' in json_response}")
            return True
        else:
            print(f"\\n❌ FAILED with status {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error: {error_detail}")
            except:
                print(f"Raw error: {response.text}")
            return False
            
    except Exception as e:
        print(f"\\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_evidence_debug_non_admin():
    """Test the evidence debug endpoint with non-admin access."""
    
    print("\\n=== TESTING EVIDENCE DEBUG ENDPOINT (NON-ADMIN) ===")
    
    # Create test client
    client = TestClient(app)
    
    # Test data - non-admin API key
    headers = {
        "X-API-KEY": "test_api_key_tenant_002",  # OPERATOR role
        "Content-Type": "application/json"
    }
    
    print(f"Testing GET /api/copilot/evidence/req_12345")
    print(f"Headers: {headers}")
    
    try:
        # Make the request
        response = client.get("/api/copilot/evidence/req_12345", headers=headers)
        
        print(f"\\nResponse:")
        print(f"Status code: {response.status_code}")
        print(f"Content: {response.text}")
        
        if response.status_code == 403:
            print(f"\\n✅ NON-ADMIN CORRECTLY BLOCKED (403)!")
            try:
                error_detail = response.json()
                print(f"Expected 403 error: {error_detail}")
            except:
                print(f"Raw error: {response.text}")
            return True
        else:
            print(f"\\n❌ UNEXPECTED STATUS - should be 403 but got {response.status_code}")
            try:
                error_detail = response.json()
                print(f"Error: {error_detail}")
            except:
                print(f"Raw error: {response.text}")
            return False
            
    except Exception as e:
        print(f"\\n❌ EXCEPTION: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🧪 TESTING COPILOT ENDPOINTS")
    
    # Test 1: Session creation
    session_success = test_copilot_session_creation()
    
    # Test 2: Admin evidence debug
    admin_success = test_evidence_debug_admin()
    
    # Test 3: Non-admin evidence debug (should be blocked)
    non_admin_success = test_evidence_debug_non_admin()
    
    print(f"\\n📊 TEST RESULTS:")
    print(f"  Session creation: {'✅ PASS' if session_success else '❌ FAIL'}")
    print(f"  Admin evidence debug: {'✅ PASS' if admin_success else '❌ FAIL'}")
    print(f"  Non-admin blocked: {'✅ PASS' if non_admin_success else '❌ FAIL'}")
    
    overall_success = session_success and admin_success and non_admin_success
    
    if overall_success:
        print("\\n🎉 All FastAPI endpoint tests successful!")
    else:
        print("\\n💥 Some tests failed!")