#!/usr/bin/env python3
"""Comprehensive test to verify copilot message storage functionality."""

import asyncio
import time
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.copilot_session_repository import CopilotSessionRepository

async def test_message_storage():
    """Test that both user and assistant messages can be stored."""
    print("🧪 TESTING COMPLETE MESSAGE STORAGE FUNCTIONALITY")
    print("=" * 60)
    
    async with get_db_session_context() as session:
        print("1. Creating repository...")
        repo = CopilotSessionRepository(session)
        
        tenant_id = "TENANT_001"
        user_id = "test_user_123"
        
        print("\\n2. Creating session...")
        copilot_session = await repo.create_session(
            tenant_id=tenant_id,
            user_id=user_id,
            title="Test Message Storage Session"
        )
        session_id = str(copilot_session.id)
        print(f"✅ Session created: {session_id}")
        
        print("\\n3. Adding user message...")
        user_message = await repo.add_message(
            session_id=session_id,
            tenant_id=tenant_id,
            role="user",
            content="Test user message for storage verification",
            metadata={"test": True, "timestamp": time.time()},
            request_id="test_req_001"
        )
        print(f"✅ User message stored: ID={user_message.id}")
        
        print("\\n4. Adding assistant message...")
        assistant_message = await repo.add_message(
            session_id=session_id,
            tenant_id=tenant_id,
            role="assistant", 
            content="Test assistant response for storage verification",
            metadata={
                "test": True,
                "timestamp": time.time(),
                "intent": "test",
                "confidence": 1.0,
                "bullets": ["Point 1", "Point 2"],
                "citations": [{"source": "test", "url": "test.com"}]
            },
            request_id="test_req_001"
        )
        print(f"✅ Assistant message stored: ID={assistant_message.id}")
        
        print("\\n5. Retrieving messages...")
        messages = await repo.get_messages(
            session_id=session_id,
            tenant_id=tenant_id,
            limit=10
        )
        
        print(f"✅ Retrieved {len(messages)} messages:")
        for msg in messages:
            print(f"   - {msg.role}: {msg.content[:50]}... (ID: {msg.id})")
        
        # Commit the transaction
        await session.commit()
        print("\\n✅ Transaction committed successfully!")
        
        return session_id, len(messages)

async def verify_database_state():
    """Verify the final database state."""
    print("\\n📊 VERIFYING FINAL DATABASE STATE")
    print("=" * 40)
    
    async with get_db_session_context() as session:
        from sqlalchemy import text
        
        # Check session count
        result = await session.execute(text('SELECT COUNT(*) FROM copilot_sessions'))
        session_count = result.scalar()
        print(f"Sessions: {session_count} records")
        
        # Check message count
        result = await session.execute(text('SELECT COUNT(*) FROM copilot_messages'))
        message_count = result.scalar()
        print(f"Messages: {message_count} records")
        
        # Check latest messages
        result = await session.execute(text('''
            SELECT role, content, session_id, request_id 
            FROM copilot_messages 
            ORDER BY created_at DESC 
            LIMIT 5
        '''))
        messages = result.fetchall()
        
        print("\\nLatest messages:")
        for role, content, sess_id, req_id in messages:
            print(f"   - {role}: {content[:40]}... (session: {str(sess_id)[:8]}...)")
        
        return session_count, message_count

async def main():
    """Run the complete test."""
    try:
        print("🎯 Starting comprehensive message storage test...")
        
        # Test message storage
        session_id, message_count = await test_message_storage()
        
        # Verify database state
        final_session_count, final_message_count = await verify_database_state()
        
        print("\\n" + "=" * 60)
        print("🎉 TEST COMPLETE!")
        print(f"✅ Session created: {session_id[:8]}...")
        print(f"✅ Messages in session: {message_count}")
        print(f"✅ Total messages in DB: {final_message_count}")
        print(f"✅ Total sessions in DB: {final_session_count}")
        
        if message_count >= 2:
            print("\\n🎯 SUCCESS: Both user and assistant messages stored correctly!")
            return True
        else:
            print(f"\\n❌ PARTIAL: Only {message_count} messages stored (expected 2)")
            return False
            
    except Exception as e:
        print(f"\\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)