"""
Test direct database connection using the credentials from .env.
"""
import asyncio
import asyncpg
import os
from pathlib import Path

# Load .env file
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    load_dotenv(env_path)
except ImportError:
    pass

async def test_db_connection():
    """Test direct connection to PostgreSQL."""
    
    # Get connection details from environment
    db_user = os.getenv("DB_USER", "sentinai")
    db_password = os.getenv("DB_PASSWORD", "sentinai")  
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "5432"))
    db_name = os.getenv("DB_NAME", "sentinai")
    
    print(f"Testing connection to PostgreSQL:")
    print(f"  Host: {db_host}:{db_port}")
    print(f"  Database: {db_name}")
    print(f"  User: {db_user}")
    print(f"  Password: {'*' * len(db_password)}")
    
    try:
        # Test basic connection
        conn = await asyncpg.connect(
            user=db_user,
            password=db_password,
            host=db_host,
            port=db_port,
            database=db_name
        )
        
        print("✅ Database connection successful!")
        
        # Test a simple query
        version = await conn.fetchval("SELECT version()")
        print(f"✅ PostgreSQL version: {version}")
        
        # Check if our tables exist
        tables = await conn.fetch("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        print(f"✅ Found {len(tables)} tables in database:")
        for table in tables:
            print(f"  - {table['table_name']}")
        
        await conn.close()
        print("✅ Connection closed successfully")
        return True
        
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        print(f"Error type: {type(e)}")
        return False

if __name__ == "__main__":
    success = asyncio.run(test_db_connection())
    if success:
        print("\n🎉 Database is accessible and working!")
    else:
        print("\n💥 Database connection issue needs to be resolved.")