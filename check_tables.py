"""
Check what tables exist and identify missing ones.
"""
import asyncio
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context

async def check_tables():
    """Check what copilot tables exist."""
    
    print("🔍 CHECKING DATABASE TABLES")
    print("="*50)
    
    try:
        async with get_db_session_context() as session:
            # Check all copilot tables
            result = await session.execute(text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_name LIKE 'copilot%' "
                "ORDER BY table_name"
            ))
            tables = result.fetchall()
            
            print(f"📋 Found {len(tables)} copilot tables:")
            for (table_name,) in tables:
                print(f"  ✅ {table_name}")
                
            # Check specifically for the missing table
            expected_tables = [
                'copilot_sessions',
                'copilot_messages', 
                'copilot_documents',
                'copilot_index_jobs'
            ]
            
            existing_table_names = [table[0] for table in tables]
            missing_tables = [t for t in expected_tables if t not in existing_table_names]
            
            if missing_tables:
                print(f"\\n❌ Missing tables:")
                for table in missing_tables:
                    print(f"  - {table}")
            else:
                print(f"\\n✅ All expected tables exist!")
                
            return existing_table_names, missing_tables
            
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return [], []

if __name__ == "__main__":
    asyncio.run(check_tables())