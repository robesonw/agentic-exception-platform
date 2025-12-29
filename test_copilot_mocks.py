"""
Test of copilot session creation with mock services (no database required).
"""
import asyncio
import json
from src.api.routes.router_copilot import CreateSessionRequest, CreateSessionResponse
from src.services.copilot.service_factory import create_copilot_service

async def test_copilot_session_creation_mock():
    """Test the copilot session creation logic with mock services."""
    
    # Create test request
    request = CreateSessionRequest(
        title="Test Session",
        context="Testing Copilot session creation with mocks"
    )
    
    # Mock user context (normally from authentication middleware)
    class MockUser:
        def __init__(self):
            self.tenant_id = "tenant_001"
            self.user_id = "test_user"
            self.role = "user"
    
    user = MockUser()
    
    try:
        # Create copilot service without database session (will use mocks)
        print("Creating copilot service with mock dependencies...")
        copilot_service = await create_copilot_service(db_session=None)
        print(f"✅ CopilotService created: {type(copilot_service).__name__}")
        
        print("Service components:")
        print(f"  - Session repository: {type(copilot_service.session_repository).__name__}")
        print(f"  - Message repository: {type(copilot_service.message_repository).__name__}")
        print(f"  - Intent router: {type(copilot_service.intent_router).__name__}")
        print(f"  - Retrieval service: {type(copilot_service.retrieval_service).__name__}")
        print(f"  - Similar exceptions: {type(copilot_service.similar_exceptions_finder).__name__}")
        print(f"  - Playbook recommender: {type(copilot_service.playbook_recommender).__name__}")
        print(f"  - Response generator: {type(copilot_service.response_generator).__name__}")
        print(f"  - Safety service: {type(copilot_service.safety_service).__name__}")
        
        # Test session creation with mock repository
        print("\nCreating session with mock repository...")
        session_id = await copilot_service.create_session(
            tenant_id=user.tenant_id,
            user_id=user.user_id,
            title=request.title
        )
        print(f"✅ Session created with ID: {session_id}")
        
        # Test chat processing
        print("\nTesting chat processing...")
        chat_request = {
            "message": "What's the status of exception EX-001?",
            "session_id": session_id,
            "tenant_id": user.tenant_id,
            "user_id": user.user_id
        }
        
        response = await copilot_service.process_message(chat_request)
        print(f"✅ Chat response received: {len(json.dumps(response))} chars")
        print(f"  Answer: {response.get('answer', 'N/A')[:100]}...")
        print(f"  Safety level: {response.get('safety', {}).get('level', 'unknown')}")
        print(f"  Recommended playbook: {response.get('recommended_playbook', 'N/A')}")
        
        # Create API response
        session_response = CreateSessionResponse(
            session_id=session_id,
            status="created"
        )
        
        print(f"\n✅ Success! Session API Response: {session_response.dict()}")
        print(f"✅ Success! Chat Response Structure: {list(response.keys())}")
        
        return session_response, response
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    session_result, chat_result = asyncio.run(test_copilot_session_creation_mock())
    if session_result and chat_result:
        print("\n🎉 All tests completed successfully!")
        print(f"\nSession Response:")
        print(json.dumps(session_result.dict(), indent=2))
        print(f"\nChat Response Sample:")
        print(json.dumps({k: v for k, v in chat_result.items() if k in ['answer', 'safety', 'recommended_playbook']}, indent=2))
    else:
        print("\n💥 Tests failed!")