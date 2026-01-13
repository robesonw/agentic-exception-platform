"""
Quick script to verify playbooks were extracted to database after domain pack upload.
"""
import asyncio
from sqlalchemy import text
from src.db.session import get_db_session_context

async def check_playbooks():
    async with get_db_session_context() as session:
        # Count playbooks for ACME_CAPITAL
        result = await session.execute(
            text("SELECT COUNT(*) FROM playbooks WHERE tenant_id = 'ACME_CAPITAL'")
        )
        count = result.scalar()
        print(f"Total playbooks for ACME_CAPITAL: {count}")
        
        # List all playbooks
        result = await session.execute(
            text("""
                SELECT name, version, created_at 
                FROM playbooks 
                WHERE tenant_id = 'ACME_CAPITAL' 
                ORDER BY created_at DESC
            """)
        )
        rows = result.fetchall()
        print("\nPlaybooks:")
        for row in rows:
            print(f"  - {row[0]} (v{row[1]}) - {row[2]}")

if __name__ == "__main__":
    asyncio.run(check_playbooks())
