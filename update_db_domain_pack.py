"""
Update domain pack in database with playbooks from file.
"""
import json
import hashlib
import asyncio
from sqlalchemy import text
import sys
sys.path.insert(0, '/app')

from src.db.session import get_db_session_context

async def update_domain_pack():
    # Load the file with playbooks
    with open('/app/runtime/domainpacks/ACME_CAPITAL/CapitalMarketsTrading/1.0.0.json') as f:
        pack_data = json.load(f)
    
    print(f"File has {len(pack_data.get('playbooks', []))} playbooks")
    
    # Compute checksum
    checksum = hashlib.sha256(json.dumps(pack_data, sort_keys=True).encode()).hexdigest()[:16]
    
    async with get_db_session_context() as session:
        # Update the database record
        result = await session.execute(
            text("""
                UPDATE domain_packs 
                SET content_json = :content, checksum = :checksum
                WHERE domain = 'CapitalMarketsTrading' AND version = '1.0'
                RETURNING id
            """),
            {"content": json.dumps(pack_data), "checksum": checksum}
        )
        updated = result.fetchone()
        await session.commit()
        
        if updated:
            print(f"Updated domain pack id={updated[0]}")
        else:
            print("No record found to update")
        
        # Verify
        result = await session.execute(
            text("SELECT jsonb_array_length(content_json->'playbooks') FROM domain_packs WHERE domain = 'CapitalMarketsTrading'")
        )
        count = result.scalar()
        print(f"Database now has {count} playbooks")

if __name__ == "__main__":
    asyncio.run(update_domain_pack())
