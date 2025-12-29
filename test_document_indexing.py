#!/usr/bin/env python3
"""Test document indexing to populate copilot_documents table."""

import asyncio
import time
from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository, DocumentChunk

async def test_document_indexing():
    """Test document storage in copilot_documents table."""
    print("🧪 TESTING DOCUMENT INDEXING TO POPULATE COPILOT_DOCUMENTS")
    print("=" * 60)
    
    async with get_db_session_context() as session:
        print("1. Creating document repository...")
        doc_repo = CopilotDocumentRepository(session)
        
        tenant_id = "TENANT_001"
        
        print("\\n2. Creating test document chunk...")
        test_chunk = DocumentChunk(
            source_type="PolicyDoc",
            source_id="policy_001",
            chunk_id="chunk_001",
            chunk_index=0,
            content="This is a test policy document for debugging exception handling procedures.",
            embedding=[0.1, 0.2, 0.3, 0.4, 0.5] * 256,  # 1280 dimensions
            embedding_model="test-model",
            embedding_dimension=1280,
            domain="testing",
            version="1.0",
            metadata={"test": True, "title": "Test Policy Document"}
        )
        
        test_doc = await doc_repo.upsert_chunk(
            tenant_id=tenant_id,
            chunk=test_chunk
        )
        print(f"✅ Document created: ID={test_doc.id}")
        
        print("\\n3. Creating another document chunk...")
        test_chunk2 = DocumentChunk(
            source_type="ResolvedException",
            source_id="exc_resolved_001", 
            chunk_id="chunk_001",
            chunk_index=0,
            content="This is a resolved NullPointerException with debugging steps and solution.",
            embedding=[0.2, 0.3, 0.4, 0.5, 0.6] * 256,  # 1280 dimensions
            embedding_model="test-model",
            embedding_dimension=1280,
            domain="testing",
            version="1.0",
            metadata={"test": True, "title": "Test Resolved Exception", "severity": "high"}
        )
        
        test_doc2 = await doc_repo.upsert_chunk(
            tenant_id=tenant_id,
            chunk=test_chunk2
        )
        print(f"✅ Second document created: ID={test_doc2.id}")
        
        print("\\n4. Retrieving documents...")
        result = await doc_repo.list_by_tenant(
            tenant_id=tenant_id,
            page=1,
            page_size=10
        )
        
        print(f"✅ Retrieved {len(result.items)} documents:")
        for doc in result.items:
            print(f"   - {doc.source_type}: {doc.content[:40]}... (ID: {doc.id})")
        
        # Commit the transaction
        await session.commit()
        print("\\n✅ Transaction committed successfully!")
        
        return len(result.items)

async def verify_documents_state():
    """Verify the copilot_documents table state."""
    print("\\n📊 VERIFYING COPILOT_DOCUMENTS TABLE STATE")
    print("=" * 50)
    
    async with get_db_session_context() as session:
        from sqlalchemy import text
        
        # Check document count
        result = await session.execute(text('SELECT COUNT(*) FROM copilot_documents'))
        doc_count = result.scalar()
        print(f"Documents: {doc_count} records")
        
        # Check latest documents
        result = await session.execute(text('''
            SELECT source_type, title, tenant_id, source_id 
            FROM copilot_documents 
            ORDER BY created_at DESC 
            LIMIT 5
        '''))
        documents = result.fetchall()
        
        print("\\nLatest documents:")
        for source_type, title, tenant, source_id in documents:
            print(f"   - {source_type}: {title[:40]}... (tenant: {tenant}, source: {source_id})")
        
        return doc_count

async def main():
    """Run the document indexing test."""
    try:
        print("🎯 Starting document indexing test...")
        
        # Test document creation
        doc_count = await test_document_indexing()
        
        # Verify final state
        final_doc_count = await verify_documents_state()
        
        print("\\n" + "=" * 60)
        print("🎉 DOCUMENT INDEXING TEST COMPLETE!")
        print(f"✅ Documents created in session: {doc_count}")
        print(f"✅ Total documents in DB: {final_doc_count}")
        
        if final_doc_count >= 2:
            print("\\n🎯 SUCCESS: Documents indexed correctly in copilot_documents table!")
            return True
        else:
            print(f"\\n❌ PARTIAL: Only {final_doc_count} documents found (expected 2+)")
            return False
            
    except Exception as e:
        print(f"\\n❌ DOCUMENT TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)