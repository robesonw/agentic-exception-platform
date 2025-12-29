"""
Test SQLAlchemy async connection using the same configuration as the app.
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

async def test_sqlalchemy_connection():
    """Test SQLAlchemy async connection."""
    
    try:
        # Import and test the database session module
        from src.infrastructure.db.session import get_engine, get_db_session_context
        from sqlalchemy import text
        
        print("Testing SQLAlchemy async connection...")
        
        # Test engine creation
        engine = get_engine()
        print(f"✅ Engine created: {engine}")
        
        # Test basic query with engine
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
            print(f"✅ Engine query successful: {version}")
        
        # Test session context manager (what the copilot service uses)
        async with get_db_session_context() as session:
            result = await session.execute(text("SELECT count(*) FROM copilot_sessions"))
            count = result.scalar()
            print(f"✅ Session context successful: {count} copilot sessions in database")
            
            # Test copilot table structure
            result = await session.execute(text("""
                SELECT column_name, data_type 
                FROM information_schema.columns 
                WHERE table_name = 'copilot_sessions' 
                ORDER BY ordinal_position
            """))
            columns = result.fetchall()
            print(f"✅ Copilot sessions table structure:")
            for col_name, col_type in columns:
                print(f"  - {col_name}: {col_type}")
        
        return True
        
    except Exception as e:
        print(f"❌ SQLAlchemy connection failed: {e}")
        print(f"Error type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_sqlalchemy_connection())
    if success:
        print("\n🎉 SQLAlchemy connection is working!")
    else:
        print("\n💥 SQLAlchemy connection issue needs investigation.")