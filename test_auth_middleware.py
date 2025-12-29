"""
Test the authentication middleware directly.
"""
import sys
import traceback

try:
    print("Testing imports...")
    
    print("1. Testing FastAPI imports...")
    from fastapi import FastAPI, Request, HTTPException
    from starlette.middleware.base import BaseHTTPMiddleware
    print("✅ FastAPI imports successful")
    
    print("2. Testing auth imports...")
    from src.api.auth import get_auth_manager, AuthenticationError
    print("✅ Auth imports successful")
    
    print("3. Testing main app import...")
    from src.api.main import app
    print("✅ Main app import successful")
    
    print("4. Testing FastAPI client...")
    from fastapi.testclient import TestClient
    client = TestClient(app)
    print("✅ TestClient created successfully")
    
    print("5. Testing simple endpoint...")
    response = client.get("/")
    print(f"✅ Root endpoint test: status={response.status_code}")
    
    print("6. Testing authentication with test endpoint...")
    headers = {'x-api-key': 'test_api_key_tenant_001', 'Content-Type': 'application/json'}
    
    # Try the evidence endpoint 
    try:
        response = client.get("/api/copilot/evidence/test123", headers=headers)
        print(f"✅ Evidence endpoint test: status={response.status_code}")
        if response.status_code != 200:
            print(f"Response: {response.text}")
    except Exception as e:
        print(f"❌ Evidence endpoint error: {e}")
        traceback.print_exc()
    
    print("\\n🎉 All tests completed!")
    
except Exception as e:
    print(f"❌ Error: {e}")
    traceback.print_exc()
    sys.exit(1)