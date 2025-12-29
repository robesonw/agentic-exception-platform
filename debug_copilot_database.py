"""
Debug test to check what database settings are being used during copilot service creation.
"""
import asyncio
import os
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

async def debug_copilot_service_database():
    """Debug database settings during copilot service creation."""
    
    print("=== DEBUGGING DATABASE SETTINGS IN COPILOT SERVICE ===")
    
    # Step 1: Check environment variables at start
    print("\\n1. Environment Variables:")
    print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
    print(f"DB_USER: {os.getenv('DB_USER')}")
    print(f"DB_PASSWORD: {os.getenv('DB_PASSWORD')}")
    
    # Step 2: Check database settings module
    from src.infrastructure.db.settings import get_database_settings
    settings = get_database_settings()
    print(f"\\n2. Database Settings:")
    print(f"database_url: {settings.database_url}")
    print(f"pool_size: {settings.pool_size}")
    
    # Step 3: Check engine creation
    from src.infrastructure.db.session import get_engine
    engine = get_engine()
    print(f"\\n3. Engine Info:")
    print(f"engine: {engine}")
    print(f"engine.url: {engine.url}")
    
    # Step 4: Try to create session and repository directly
    print("\\n4. Testing Repository Creation:")
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.infrastructure.repositories.copilot_session_repository import CopilotSessionRepository
        
        async with get_db_session_context() as session:
            print(f"Session created: {session}")
            print(f"Session bind: {session.bind}")
            if hasattr(session.bind, 'url'):
                print(f"Session bind URL: {session.bind.url}")
            
            # Try to create repository
            repo = CopilotSessionRepository(session)
            print(f"Repository created: {repo}")
            
            # Try a simple query
            from sqlalchemy import text
            result = await session.execute(text("SELECT current_user, current_database()"))
            user_db = result.fetchone()
            print(f"Connected as user: {user_db[0]}, database: {user_db[1]}")
            
    except Exception as e:
        print(f"❌ Repository creation failed: {e}")
        import traceback
        traceback.print_exc()
    
    # Step 5: Try copilot service creation
    print("\\n5. Testing CopilotService Creation:")
    try:
        from src.services.copilot.service_factory import create_copilot_service
        
        async with get_db_session_context() as session:
            service = await create_copilot_service(session)
            print(f"CopilotService created: {service}")
            
            # Try to create a test session
            print("\\n6. Testing Session Creation:")
            session_id = await service.create_session(
                tenant_id="TEST_TENANT",
                user_id="test_user",
                title="Debug Test Session"
            )
            print(f"✅ Session created successfully: {session_id}")
            
    except Exception as e:
        print(f"❌ CopilotService creation/usage failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(debug_copilot_service_database())