"""
Direct test of copilot session creation endpoint logic without server.
"""
import asyncio
import json
from src.api.routes.router_copilot import CreateSessionRequest, CreateSessionResponse
from src.services.copilot.service_factory import create_copilot_service
from src.infrastructure.db.session import get_db_session_context

async def test_copilot_session_creation():
    """Test the copilot session creation logic directly."""
    
    # Create test request
    request = CreateSessionRequest(
        title="Test Session",
        context="Testing Copilot session creation"
    )
    
    # Mock user context (normally from authentication middleware)
    class MockUser:
        def __init__(self):
            self.tenant_id = "tenant_001"
            self.user_id = "test_user"
            self.role = "user"
    
    user = MockUser()
    
    try:
        # Use database session context manager
        async with get_db_session_context() as session:
            # Create copilot service with database session
            print("Creating copilot service...")
            copilot_service = await create_copilot_service(session)
            print(f"✅ CopilotService created: {type(copilot_service).__name__}")
            
            # Create session using copilot service
            print("Creating session...")
            session_id = await copilot_service.create_session(
                tenant_id=user.tenant_id,
                user_id=user.user_id,
                title=request.title
            )
            print(f"✅ Session created with ID: {session_id}")
            
            # Create response
            response = CreateSessionResponse(
                session_id=session_id,
                status="created"
            )
            
            print(f"✅ Success! Response: {response.dict()}")
            return response
            
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_copilot_session_creation())
    if result:
        print("\n🎉 Test completed successfully!")
        print(f"Response: {json.dumps(result.dict(), indent=2)}")
    else:
        print("\n💥 Test failed!")