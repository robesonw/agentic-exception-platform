"""
Check the database directly to see if chat messages were stored.
"""
import asyncio
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context

async def check_messages_table():
    """Check if chat messages were stored."""
    
    print("🔍 CHECKING DATABASE FOR CHAT MESSAGES")
    print("="*50)
    
    try:
        async with get_db_session_context() as session:
            # Check copilot_sessions count
            result = await session.execute(text("SELECT COUNT(*) FROM copilot_sessions"))
            sessions_count = result.scalar()
            print(f"📋 copilot_sessions: {sessions_count} records")
            
            # Check copilot_messages count  
            result = await session.execute(text("SELECT COUNT(*) FROM copilot_messages"))
            messages_count = result.scalar()
            print(f"💬 copilot_messages: {messages_count} records")
            
            # Check copilot_documents count
            result = await session.execute(text("SELECT COUNT(*) FROM copilot_documents"))
            docs_count = result.scalar()
            print(f"📄 copilot_documents: {docs_count} records")
            
            # If messages exist, show sample
            if messages_count > 0:
                print(f"\\n✅ MESSAGES FOUND! Sample records:")
                result = await session.execute(text(
                    "SELECT session_id, message_type, content, created_at "
                    "FROM copilot_messages ORDER BY created_at DESC LIMIT 3"
                ))
                messages = result.fetchall()
                for session_id, msg_type, content, created_at in messages:
                    print(f"  - {msg_type}: {content[:50]}... (session: {session_id})")
            else:
                print(f"\\n❌ NO MESSAGES FOUND")
                print(f"This suggests the chat endpoint doesn't store messages.")
                
            return sessions_count, messages_count, docs_count
            
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return None, None, None

if __name__ == "__main__":
    asyncio.run(check_messages_table())