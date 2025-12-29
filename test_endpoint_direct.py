"""
Direct test of the session creation endpoint logic to isolate the user_id issue.
"""
import asyncio
import sys
import os
sys.path.append(os.getcwd())

from src.api.auth import AuthManager
from src.api.routes.router_copilot import CreateSessionRequest
from src.services.copilot.service_factory import create_copilot_service
from src.infrastructure.db.session import get_db_session_context

async def test_endpoint_logic_direct():
    """Test the exact logic from the endpoint."""
    
    print("=== TESTING SESSION CREATION ENDPOINT LOGIC ===")
    
    # Step 1: Test authentication (simulate middleware)
    auth_manager = AuthManager()
    api_key = "test_api_key_tenant_001"
    
    try:
        user_context = auth_manager.authenticate(api_key=api_key)
        print(f"✅ Step 1 - Authentication successful:")
        print(f"    user_id: '{user_context.user_id}'")
        print(f"    tenant_id: '{user_context.tenant_id}'")
    except Exception as e:
        print(f"❌ Step 1 - Authentication failed: {e}")
        return
    
    # Step 2: Create auth context dict (simulate require_authenticated_user)
    auth_context = {
        "user_id": user_context.user_id,
        "tenant_id": user_context.tenant_id
    }
    print(f"✅ Step 2 - Auth context created:")
    print(f"    auth_context['user_id']: '{auth_context['user_id']}'")
    print(f"    type: {type(auth_context['user_id'])}")
    print(f"    bool: {bool(auth_context['user_id'])}")
    
    # Step 3: Create request object
    request = CreateSessionRequest(title="Direct Test Session")
    print(f"✅ Step 3 - Request created: title='{request.title}'")
    
    # Step 4: Test database session and service creation
    try:
        async with get_db_session_context() as session:
            print(f"✅ Step 4a - Database session created")
            
            # Create copilot service
            copilot_service = await create_copilot_service(session)
            print(f"✅ Step 4b - CopilotService created: {type(copilot_service).__name__}")
            
            # Step 5: Call create_session (the actual failing call)
            print(f"\\n🔥 Step 5 - Calling copilot_service.create_session...")
            print(f"    tenant_id: '{auth_context['tenant_id']}'")
            print(f"    user_id: '{auth_context['user_id']}'") 
            print(f"    title: '{request.title}'")
            
            session_id = await copilot_service.create_session(
                tenant_id=auth_context['tenant_id'],
                user_id=auth_context['user_id'],
                title=request.title
            )
            
            print(f"✅ Step 5 - Session created successfully!")
            print(f"    session_id: {session_id}")
            return session_id
            
    except Exception as e:
        print(f"❌ Step 4/5 failed: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    result = asyncio.run(test_endpoint_logic_direct())
    if result:
        print(f"\\n🎉 SUCCESS: Session created with ID {result}")
    else:
        print(f"\\n💥 FAILED: Could not create session")