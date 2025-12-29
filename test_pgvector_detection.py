import asyncio
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context

async def test_detection():
    async with get_db_session_context() as session:
        try:
            # Test the detection query
            result = await session.execute(text("SELECT 1 WHERE 'vector' = ANY(SELECT extname FROM pg_extension)"))
            has_pgvector = result.fetchone() is not None
            print(f'Detection result: has_pgvector = {has_pgvector}')
        except Exception as e:
            print(f'Detection failed: {e}')
            
asyncio.run(test_detection())