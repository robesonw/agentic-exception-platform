"""
Test live server endpoints to populate copilot tables.
"""
import requests
import json
import time

def test_live_chat_endpoint():
    """Test the live chat endpoint to populate copilot_messages."""
    
    print("💬 TESTING LIVE CHAT ENDPOINT")
    print("="*50)
    
    base_url = "http://127.0.0.1:8000"
    headers = {
        'x-api-key': 'test_api_key_tenant_001',
        'Content-Type': 'application/json'
    }
    
    try:
        # Step 1: Create a session first
        print("1. Creating session...")
        session_data = {"title": "Live Test Session for Messages"}
        
        response = requests.post(
            f"{base_url}/api/copilot/sessions", 
            headers=headers, 
            json=session_data,
            timeout=10
        )
        
        if response.status_code == 200:
            session_json = response.json()
            session_id = session_json["session_id"]
            print(f"✅ Session created: {session_id}")
            
            # Step 2: Send chat message to Phase 13 endpoint
            print("\\n2. Sending chat message...")
            chat_data = {
                "message": "Help me analyze this NullPointerException in the payment service. It seems to happen during transaction processing.",
                "session_id": session_id,
                "domain": "finance",
                "context": {
                    "exception_id": "exc_live_test_001",
                    "severity": "high"
                }
            }
            
            response = requests.post(
                f"{base_url}/api/copilot/chat",
                headers=headers,
                json=chat_data,
                timeout=30
            )
            
            print(f"Status: {response.status_code}")
            
            if response.status_code == 200:
                chat_json = response.json()
                print(f"✅ Chat successful!")
                print(f"Request ID: {chat_json.get('request_id')}")
                print(f"Session ID: {chat_json.get('session_id')}")
                print(f"Answer: {chat_json.get('answer', '')[:100]}...")
                print(f"Intent: {chat_json.get('intent')}")
                return True, session_id
            else:
                print(f"❌ Chat failed: {response.status_code}")
                print(f"Response: {response.text}")
                return False, session_id
        else:
            print(f"❌ Session creation failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False, None

def test_live_indexing_endpoint():
    """Test the live indexing endpoint to populate copilot_documents."""
    
    print("\\n📄 TESTING LIVE INDEXING ENDPOINT")
    print("="*50)
    
    base_url = "http://127.0.0.1:8000"
    headers = {
        'x-api-key': 'test_api_key_tenant_001',
        'Content-Type': 'application/json'
    }
    
    try:
        print("1. Starting index rebuild...")
        index_data = {
            "tenant_id": "TENANT_001",
            "sources": ["policy_doc", "resolved_exception"],
            "full_rebuild": False
        }
        
        response = requests.post(
            f"{base_url}/api/copilot/index/rebuild",
            headers=headers,
            json=index_data,
            timeout=30
        )
        
        print(f"Status: {response.status_code}")
        
        if response.status_code == 200:
            index_json = response.json()
            job_id = index_json.get("job_id")
            print(f"✅ Index rebuild started!")
            print(f"Job ID: {job_id}")
            print(f"Message: {index_json.get('message')}")
            
            # Check status
            print("\\n2. Checking rebuild status...")
            time.sleep(2)  # Give it a moment
            
            status_response = requests.get(
                f"{base_url}/api/copilot/index/rebuild/{job_id}",
                headers=headers,
                timeout=10
            )
            
            print(f"Status check: {status_response.status_code}")
            if status_response.status_code == 200:
                status_json = status_response.json()
                print(f"Job status: {status_json.get('status')}")
                print(f"Progress: {status_json.get('progress_current', 0)}/{status_json.get('progress_total', 'unknown')}")
                
            return True, job_id
        else:
            print(f"❌ Index rebuild failed: {response.status_code}")
            print(f"Response: {response.text}")
            return False, None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Request failed: {e}")
        return False, None

def check_database_results():
    """Check the database for new data."""
    
    print("\\n🔍 CHECKING DATABASE RESULTS")
    print("="*50)
    
    try:
        import asyncio
        from sqlalchemy import text
        from src.infrastructure.db.session import get_db_session_context
        
        async def check():
            async with get_db_session_context() as session:
                # Check sessions
                result = await session.execute(text("SELECT COUNT(*) FROM copilot_sessions"))
                sessions_count = result.scalar()
                
                # Check messages
                result = await session.execute(text("SELECT COUNT(*) FROM copilot_messages"))
                messages_count = result.scalar()
                
                # Check documents
                result = await session.execute(text("SELECT COUNT(*) FROM copilot_documents"))
                docs_count = result.scalar()
                
                # Check index jobs
                result = await session.execute(text("SELECT COUNT(*) FROM copilot_index_jobs"))
                jobs_count = result.scalar()
                
                print(f"📊 Database Counts:")
                print(f"  Sessions: {sessions_count}")
                print(f"  Messages: {messages_count}")
                print(f"  Documents: {docs_count}")
                print(f"  Index Jobs: {jobs_count}")
                
                # Show sample messages if any exist
                if messages_count > 0:
                    print(f"\\n✅ MESSAGES FOUND! Sample records:")
                    result = await session.execute(text(
                        "SELECT message_type, content, session_id, created_at "
                        "FROM copilot_messages ORDER BY created_at DESC LIMIT 5"
                    ))
                    messages = result.fetchall()
                    for msg_type, content, session_id, created_at in messages:
                        print(f"  - {msg_type}: {content[:50]}... (session: {str(session_id)[:8]})")
                
                return sessions_count, messages_count, docs_count, jobs_count
        
        return asyncio.run(check())
        
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return None, None, None, None

def main():
    print("🧪 TESTING LIVE SERVER TO POPULATE COPILOT TABLES")
    print("="*70)
    
    # Test 1: Chat endpoint (should populate copilot_messages)
    chat_success, session_id = test_live_chat_endpoint()
    
    # Test 2: Indexing endpoint (should populate copilot_documents)
    index_success, job_id = test_live_indexing_endpoint()
    
    # Wait a moment for async operations to complete
    print("\\n⏱️  Waiting for operations to complete...")
    time.sleep(3)
    
    # Check results
    sessions, messages, docs, jobs = check_database_results()
    
    print(f"\\n📋 FINAL RESULTS:")
    print(f"="*50)
    print(f"Chat endpoint: {'✅ SUCCESS' if chat_success else '❌ FAILED'}")
    print(f"Index endpoint: {'✅ SUCCESS' if index_success else '❌ FAILED'}")
    print(f"Messages stored: {'✅ YES' if messages and messages > 0 else '❌ NO'}")
    print(f"Documents indexed: {'✅ YES' if docs and docs > 0 else '❌ NO'}")
    print(f"Index jobs created: {'✅ YES' if jobs and jobs > 0 else '❌ NO'}")
    
    if messages and messages > 0:
        print(f"\\n🎉 SUCCESS! copilot_messages table now has {messages} records!")
    if docs and docs > 0:
        print(f"🎉 SUCCESS! copilot_documents table now has {docs} records!")
    if jobs and jobs > 0:
        print(f"🎉 SUCCESS! copilot_index_jobs table now has {jobs} records!")
        
    return chat_success and (messages and messages > 0), index_success and (docs and docs > 0)

if __name__ == "__main__":
    main()