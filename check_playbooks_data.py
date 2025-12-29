"""Check playbooks data structure in domain packs."""
import asyncio
import json
import sys
sys.path.insert(0, '.')

from src.infrastructure.db.session import get_db_session_context
from sqlalchemy import text


async def check():
    async with get_db_session_context() as session:
        # Check domain pack content
        query = "SELECT id, domain, content_json FROM domain_packs WHERE status = 'active' LIMIT 3"
        result = await session.execute(text(query))
        rows = result.fetchall()
        
        for row in rows:
            print(f"\n=== Domain Pack {row[0]} ({row[1]}) ===")
            content = row[2]
            if isinstance(content, str):
                content = json.loads(content)
            
            playbooks = content.get('playbooks', [])
            print(f"  playbooks type: {type(playbooks)}")
            print(f"  playbooks count: {len(playbooks)}")
            
            if playbooks:
                first = playbooks[0]
                print(f"  first playbook type: {type(first)}")
                if isinstance(first, str):
                    print(f"  first playbook (string): {first[:200]}")
                elif isinstance(first, dict):
                    print(f"  first playbook keys: {list(first.keys())}")
                else:
                    print(f"  first playbook value: {str(first)[:200]}")


if __name__ == "__main__":
    asyncio.run(check())
