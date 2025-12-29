#!/usr/bin/env python3
"""Check database schema and pgvector setup."""

import asyncio
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context

async def check_database():
    """Check the database setup for pgvector and embedding column."""
    print("🔍 CHECKING DATABASE SETUP FOR PGVECTOR")
    print("=" * 50)
    
    try:
        async with get_db_session_context() as session:
            # 1. Check if pgvector extension exists
            print("1. Checking pgvector extension...")
            result = await session.execute(text("SELECT extname, extversion FROM pg_extension WHERE extname = 'vector'"))
            extensions = result.fetchall()
            
            if extensions:
                for ext in extensions:
                    print(f"   ✅ {ext[0]} v{ext[1]} installed")
            else:
                print("   ❌ pgvector extension NOT installed")
            
            # 2. Check copilot_documents table structure  
            print("\\n2. Checking copilot_documents table...")
            result = await session.execute(text("""
                SELECT column_name, data_type, udt_name 
                FROM information_schema.columns 
                WHERE table_name = 'copilot_documents'
                ORDER BY ordinal_position
            """))
            
            columns = result.fetchall()
            print(f"   Table has {len(columns)} columns:")
            for col, dtype, udt in columns:
                print(f"     - {col}: {dtype} ({udt})")
            
            # 3. Check embedding column specifically
            print("\\n3. Checking embedding column type...")
            result = await session.execute(text("""
                SELECT column_name, data_type, udt_name, is_nullable
                FROM information_schema.columns 
                WHERE table_name = 'copilot_documents' 
                AND column_name = 'embedding'
            """))
            
            embedding_info = result.fetchall()
            if embedding_info:
                col, dtype, udt, nullable = embedding_info[0]
                print(f"   ✅ embedding column: {dtype} ({udt}), nullable: {nullable}")
            else:
                print("   ❌ embedding column NOT found")
            
            # 4. Check if we have any data
            print("\\n4. Checking sample data...")
            result = await session.execute(text("SELECT COUNT(*) FROM copilot_documents"))
            count = result.scalar()
            print(f"   📄 {count} documents in table")
            
            if count > 0:
                # Check a sample embedding
                result = await session.execute(text("""
                    SELECT id, embedding IS NOT NULL as has_embedding, 
                           pg_typeof(embedding) as embedding_type
                    FROM copilot_documents 
                    LIMIT 1
                """))
                
                sample = result.fetchall()
                if sample:
                    doc_id, has_emb, emb_type = sample[0]
                    print(f"   📋 Sample document: ID={doc_id}, has_embedding={has_emb}, type={emb_type}")
                    
                    # Test a simple similarity query
                    print("\\n5. Testing vector operations...")
                    try:
                        result = await session.execute(text("""
                            SELECT COUNT(*) FROM copilot_documents 
                            WHERE embedding IS NOT NULL
                        """))
                        with_embeddings = result.scalar()
                        print(f"   ✅ Documents with embeddings: {with_embeddings}")
                        
                        # Test basic pgvector operation if extension is installed
                        if extensions:
                            result = await session.execute(text("""
                                SELECT embedding <-> embedding as zero_distance
                                FROM copilot_documents 
                                WHERE embedding IS NOT NULL 
                                LIMIT 1
                            """))
                            test_result = result.fetchall()
                            if test_result:
                                print(f"   ✅ Vector operation test: distance={test_result[0][0]}")
                    
                    except Exception as e:
                        print(f"   ❌ Vector operation failed: {str(e)}")
            
            await session.commit()
            return True
            
    except Exception as e:
        print(f"❌ Database check failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(check_database())
    exit(0 if success else 1)