#!/usr/bin/env python3
"""Check copilot_messages table structure and data."""

import asyncio
from sqlalchemy import text
from src.infrastructure.db.session import get_db_session_context

async def check_table():
    async with get_db_session_context() as session:
        # Get the table structure
        result = await session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name = 'copilot_messages' AND table_schema = 'public' ORDER BY ordinal_position"))
        columns = [row[0] for row in result.fetchall()]
        print(f'Available columns: {columns}')
        
        # Get a sample message
        result = await session.execute(text('SELECT role, content, session_id, request_id, created_at FROM copilot_messages ORDER BY created_at DESC LIMIT 3'))
        rows = result.fetchall()
        print(f'Messages: {len(rows)} records')
        for row in rows:
            print(f'  - {row[0]}: {row[1][:50]}... (session: {row[2]}, request: {row[3]})')

if __name__ == "__main__":
    asyncio.run(check_table())