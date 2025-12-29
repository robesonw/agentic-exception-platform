"""
Debug copilot database tables to see current state and identify missing data flows.
"""
import asyncio
import logging
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context

async def check_copilot_tables():
    """Check the current state of copilot tables."""
    
    print("🔍 DEBUGGING COPILOT DATABASE TABLES")
    print("="*60)
    
    try:
        async with get_db_session_context() as session:
            
            # Check copilot_sessions
            print("📋 COPILOT_SESSIONS:")
            result = await session.execute(text("SELECT COUNT(*), tenant_id FROM copilot_sessions GROUP BY tenant_id"))
            sessions_data = result.fetchall()
            if sessions_data:
                for count, tenant_id in sessions_data:
                    print(f"  ✅ {count} sessions for tenant {tenant_id}")
            else:
                print("  ❌ No sessions found")
                
            # Check copilot_documents  
            print("\n📄 COPILOT_DOCUMENTS:")
            result = await session.execute(text("SELECT COUNT(*), tenant_id, source_type FROM copilot_documents GROUP BY tenant_id, source_type"))
            docs_data = result.fetchall()
            if docs_data:
                for count, tenant_id, source_type in docs_data:
                    print(f"  ✅ {count} documents for tenant {tenant_id}, source: {source_type}")
            else:
                print("  ❌ No documents found")
                
            # Check copilot_messages
            print("\n💬 COPILOT_MESSAGES:")
            result = await session.execute(text("SELECT COUNT(*), session_id, message_type FROM copilot_messages GROUP BY session_id, message_type"))
            messages_data = result.fetchall()
            if messages_data:
                for count, session_id, message_type in messages_data:
                    print(f"  ✅ {count} messages in session {session_id}, type: {message_type}")
            else:
                print("  ❌ No messages found")
                
            # Show table structures
            print("\n🏗️  TABLE STRUCTURES:")
            
            # copilot_documents structure
            result = await session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'copilot_documents' ORDER BY ordinal_position"))
            docs_cols = result.fetchall()
            print(f"\ncopilot_documents ({len(docs_cols)} columns):")
            for col_name, data_type in docs_cols:
                print(f"  - {col_name}: {data_type}")
                
            # copilot_messages structure  
            result = await session.execute(text("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'copilot_messages' ORDER BY ordinal_position"))
            msgs_cols = result.fetchall()
            print(f"\ncopilot_messages ({len(msgs_cols)} columns):")
            for col_name, data_type in msgs_cols:
                print(f"  - {col_name}: {data_type}")
                
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        import traceback
        traceback.print_exc()

async def identify_missing_flows():
    """Identify what operations would populate the missing tables."""
    
    print("\n🔧 MISSING DATA FLOW ANALYSIS")
    print("="*60)
    
    print("📄 COPILOT_DOCUMENTS should be populated by:")
    print("  1. Document indexing operations (POST /api/copilot/index/rebuild)")
    print("  2. RAG document ingestion") 
    print("  3. Policy documents, resolved exceptions, audit events being indexed")
    print("  4. Embedding and chunking services")
    
    print("\n💬 COPILOT_MESSAGES should be populated by:")
    print("  1. Chat conversations (POST /api/copilot/chat)")
    print("  2. User messages and AI responses")
    print("  3. Session-based conversations")
    
    print("\n🎯 TO POPULATE THESE TABLES, WE NEED TO:")
    print("  ✅ Test chat endpoint with actual messages")
    print("  ✅ Test document indexing endpoint") 
    print("  ✅ Verify embedding/chunking services")
    print("  ✅ Check if there's sample data to index")

if __name__ == "__main__":
    asyncio.run(check_copilot_tables())
    asyncio.run(identify_missing_flows())