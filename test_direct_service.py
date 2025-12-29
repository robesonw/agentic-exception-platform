"""
Test the CopilotService directly to populate tables.
"""
import asyncio
import uuid
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context
from src.services.copilot.service_factory import create_copilot_service
from src.services.copilot.copilot_service import CopilotRequest

async def test_direct_copilot_service():
    """Test the CopilotService directly to store messages."""
    
    print("🔧 TESTING DIRECT COPILOT SERVICE")
    print("="*50)
    
    try:
        async with get_db_session_context() as session:
            print("1. Creating CopilotService...")
            copilot_service = await create_copilot_service(session)
            print(f"✅ Service created: {type(copilot_service).__name__}")
            
            print("\\n2. Creating copilot request...")
            request = CopilotRequest(
                message="Help me debug this NullPointerException that occurs during payment processing. It seems to happen when the amount is null.",
                tenant_id="TENANT_001",
                user_id="test_user_direct",
                session_id=None,  # Let it create a new session
                domain="finance",
                context={
                    "exception_id": "direct_test_001",
                    "severity": "high",
                    "component": "payment-service"
                }
            )
            
            print(f"✅ Request created: {request.message[:50]}...")
            
            print("\\n3. Processing message through service...")
            response = await copilot_service.process_message(request)
            
            print(f"✅ Message processed successfully!")
            print(f"Request ID: {response.request_id}")
            print(f"Session ID: {response.session_id}")
            print(f"Answer: {response.answer[:100]}...")
            print(f"Processing time: {response.processing_time_ms}ms")
            
            return True, response.session_id
            
    except Exception as e:
        print(f"❌ Direct service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

async def test_index_rebuild_direct():
    """Test index rebuild service directly."""
    
    print("\\n📄 TESTING DIRECT INDEX REBUILD")
    print("="*50)
    
    try:
        from src.services.copilot.indexing.rebuild_service import IndexRebuildService
        from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
        from src.services.copilot.embedding_service import EmbeddingService
        from src.services.copilot.chunking_service import DocumentChunkingService, ChunkingConfig
        
        async with get_db_session_context() as session:
            print("1. Creating indexing services...")
            
            # Create required services
            document_repository = CopilotDocumentRepository(session)
            embedding_service = EmbeddingService()
            chunking_service = DocumentChunkingService(ChunkingConfig.default())
            
            # Create rebuild service
            rebuild_service = IndexRebuildService(
                session, embedding_service, chunking_service, document_repository
            )
            
            print("✅ IndexRebuildService created")
            
            print("\\n2. Starting rebuild job...")
            job_id = await rebuild_service.start_rebuild(
                tenant_id="TENANT_001",
                sources=["policy_doc"],
                full_rebuild=False
            )
            
            print(f"✅ Rebuild started with job ID: {job_id}")
            
            # Check job status
            print("\\n3. Checking job status...")
            status = await rebuild_service.get_status(job_id)
            print(f"Job status: {status['status']}")
            print(f"Progress: {status.get('progress_current', 0)}/{status.get('progress_total', 'unknown')}")
            
            return True, job_id
            
    except Exception as e:
        print(f"❌ Direct indexing test failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

async def check_tables_after_direct_test():
    """Check database tables after direct service test."""
    
    print("\\n🔍 CHECKING DATABASE AFTER DIRECT TESTS")
    print("="*50)
    
    try:
        async with get_db_session_context() as session:
            # Check all copilot tables
            tables_to_check = [
                ('copilot_sessions', 'Sessions'),
                ('copilot_messages', 'Messages'), 
                ('copilot_documents', 'Documents'),
                ('copilot_index_jobs', 'Index Jobs')
            ]
            
            results = {}
            
            for table, label in tables_to_check:
                result = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                results[table] = count
                print(f"📊 {label}: {count} records")
            
            # Show sample data if available
            if results['copilot_messages'] > 0:
                print(f"\\n✅ MESSAGES FOUND! Sample records:")
                result = await session.execute(text(
                    "SELECT message_type, content, session_id, request_id, created_at "
                    "FROM copilot_messages ORDER BY created_at DESC LIMIT 3"
                ))
                messages = result.fetchall()
                for msg_type, content, session_id, request_id, created_at in messages:
                    print(f"  - {msg_type}: {content[:60]}... (session: {str(session_id)[:8]}, req: {request_id[:8]})")
            
            if results['copilot_documents'] > 0:
                print(f"\\n✅ DOCUMENTS FOUND! Sample records:")
                result = await session.execute(text(
                    "SELECT source_type, title, tenant_id, created_at "
                    "FROM copilot_documents ORDER BY created_at DESC LIMIT 3"
                ))
                docs = result.fetchall()
                for source_type, title, tenant_id, created_at in docs:
                    print(f"  - {source_type}: {title[:50]}... (tenant: {tenant_id})")
            
            return results
            
    except Exception as e:
        print(f"❌ Database check failed: {e}")
        return {}

async def main():
    print("🧪 TESTING DIRECT SERVICES TO POPULATE COPILOT TABLES")
    print("="*70)
    
    # Test 1: Direct copilot service (should store messages)
    service_success, session_id = await test_direct_copilot_service()
    
    # Test 2: Direct index rebuild (should create jobs and potentially docs)
    index_success, job_id = await test_index_rebuild_direct()
    
    # Check results
    results = await check_tables_after_direct_test()
    
    print(f"\\n📋 FINAL SUMMARY:")
    print(f"="*50)
    print(f"Direct copilot service: {'✅ SUCCESS' if service_success else '❌ FAILED'}")
    print(f"Direct index rebuild: {'✅ SUCCESS' if index_success else '❌ FAILED'}")
    
    if results:
        messages_stored = results.get('copilot_messages', 0) > 0
        docs_stored = results.get('copilot_documents', 0) > 0
        jobs_created = results.get('copilot_index_jobs', 0) > 0
        
        print(f"Messages stored: {'✅ YES' if messages_stored else '❌ NO'}")
        print(f"Documents indexed: {'✅ YES' if docs_stored else '❌ NO'}")
        print(f"Index jobs created: {'✅ YES' if jobs_created else '❌ NO'}")
        
        if messages_stored:
            print(f"\\n🎉 SUCCESS! copilot_messages table populated with {results['copilot_messages']} records!")
        if docs_stored:
            print(f"🎉 SUCCESS! copilot_documents table populated with {results['copilot_documents']} records!")
        if jobs_created:
            print(f"🎉 SUCCESS! copilot_index_jobs table populated with {results['copilot_index_jobs']} records!")
    
    print(f"\\n🎯 SUMMARY: Both tables should now have data if the tests succeeded!")

if __name__ == "__main__":
    asyncio.run(main())