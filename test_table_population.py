"""
Test endpoints that should populate copilot_messages and copilot_documents tables.
"""
import json
from fastapi.testclient import TestClient
from src.api.main import app

def test_chat_endpoint_to_populate_messages():
    """Test the chat endpoint to populate copilot_messages table."""
    
    print("💬 TESTING CHAT ENDPOINT TO POPULATE copilot_messages")
    print("="*60)
    
    client = TestClient(app)
    
    # First, create a session
    headers = {
        'x-api-key': 'test_api_key_tenant_001',
        'Content-Type': 'application/json'
    }
    
    session_data = {"title": "Test Chat Session for Messages"}
    
    print("1. Creating session...")
    session_response = client.post("/api/copilot/sessions", headers=headers, json=session_data)
    
    if session_response.status_code == 200:
        session_json = session_response.json()
        session_id = session_json["session_id"]
        print(f"✅ Session created: {session_id}")
        
        # Now test the Phase 13 chat endpoint (that stores messages)
        print("\\n2. Sending chat message to Phase 13 endpoint...")
        chat_data = {
            "message": "Help me analyze this exception: NullPointerException in payment service", 
            "session_id": session_id,  # Use the created session
            "domain": "finance",
            "context": {
                "exception_id": "exc_001"
            }
        }
        
        # Check if we have the new chat endpoint
        try:
            print(f"Testing POST /api/copilot/chat (Phase 13)...")
            chat_response = client.post("/api/copilot/chat", headers=headers, json=chat_data)
            
            print(f"Status: {chat_response.status_code}")
            print(f"Response: {chat_response.text}")
            
            if chat_response.status_code == 200:
                chat_json = chat_response.json()
                print(f"\\n✅ Chat successful!")
                print(f"Response: {chat_json.get('answer', 'No answer')[:100]}...")
                return True
            else:
                print(f"❌ Chat failed with status {chat_response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Chat endpoint error: {e}")
            return False
    else:
        print(f"❌ Session creation failed: {session_response.status_code}")
        return False

def test_document_indexing_to_populate_documents():
    """Test document indexing endpoints to populate copilot_documents table."""
    
    print("\\n📄 TESTING INDEXING ENDPOINTS TO POPULATE copilot_documents")
    print("="*60)
    
    client = TestClient(app)
    
    headers = {
        'x-api-key': 'test_api_key_tenant_001',
        'Content-Type': 'application/json'
    }
    
    # Test index rebuild endpoint
    print("1. Testing index rebuild endpoint...")
    
    rebuild_data = {
        "tenant_id": "TENANT_001",
        "sources": ["policy_doc", "resolved_exception"],
        "full_rebuild": False
    }
    
    try:
        rebuild_response = client.post("/api/copilot/index/rebuild", headers=headers, json=rebuild_data)
        
        print(f"Status: {rebuild_response.status_code}")
        print(f"Response: {rebuild_response.text}")
        
        if rebuild_response.status_code == 200:
            rebuild_json = rebuild_response.json()
            job_id = rebuild_json.get("job_id")
            print(f"\\n✅ Index rebuild started!")
            print(f"Job ID: {job_id}")
            print(f"Message: {rebuild_json.get('message')}")
            
            # Check rebuild status
            print("\\n2. Checking rebuild status...")
            status_response = client.get(f"/api/copilot/index/rebuild/{job_id}", headers=headers)
            print(f"Status check: {status_response.status_code}")
            print(f"Status response: {status_response.text}")
            
            return True
        else:
            print(f"❌ Index rebuild failed with status {rebuild_response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Index rebuild error: {e}")
        return False

def check_database_after_tests():
    """Check database tables after running the tests."""
    
    print("\\n🔍 CHECKING DATABASE AFTER TESTS")
    print("="*60)
    
    # Use a simple database query
    try:
        client = TestClient(app)
        
        # For now, we'll just indicate what to check manually
        print("To verify data was inserted, check:")
        print("1. copilot_sessions table - should have test sessions")
        print("2. copilot_messages table - should have chat messages if chat worked")
        print("3. copilot_documents table - should have indexed docs if indexing worked")
        print("\\nRun this in PostgreSQL:")
        print("SELECT 'sessions' as table_name, COUNT(*) as count FROM copilot_sessions")
        print("UNION ALL")
        print("SELECT 'messages' as table_name, COUNT(*) as count FROM copilot_messages") 
        print("UNION ALL")
        print("SELECT 'documents' as table_name, COUNT(*) as count FROM copilot_documents;")
        
    except Exception as e:
        print(f"❌ Database check error: {e}")

def main():
    print("🧪 TESTING ENDPOINTS TO POPULATE COPILOT TABLES")
    print("="*70)
    
    # Test 1: Chat endpoint (should populate copilot_messages)
    chat_success = test_chat_endpoint_to_populate_messages()
    
    # Test 2: Document indexing (should populate copilot_documents) 
    index_success = test_document_indexing_to_populate_documents()
    
    # Check results
    check_database_after_tests()
    
    print(f"\\n📊 TEST RESULTS:")
    print(f"  Chat endpoint (messages): {'✅ TESTED' if chat_success else '❌ FAILED'}")
    print(f"  Index endpoint (documents): {'✅ TESTED' if index_success else '❌ FAILED'}")
    
    print(f"\\n🎯 NEXT STEPS:")
    print(f"  1. Check database tables for new data")
    print(f"  2. If no data, check service implementations")
    print(f"  3. Verify message storage in chat service")
    print(f"  4. Verify document processing in index service")

if __name__ == "__main__":
    main()