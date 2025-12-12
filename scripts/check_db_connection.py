"""
Script to check database connection configuration and test connectivity.

This script displays the database connection details (with password masked)
and tests the connection.
"""

import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.infrastructure.db.settings import get_database_settings, get_database_url
from src.infrastructure.db.session import check_database_connection, get_engine


def mask_password_in_url(url: str) -> str:
    """Mask password in database URL for safe display."""
    if "@" in url and "://" in url:
        parts = url.split("://", 1)
        if len(parts) == 2:
            scheme = parts[0]
            rest = parts[1]
            if "@" in rest:
                auth_part, host_part = rest.split("@", 1)
                if ":" in auth_part:
                    user, _ = auth_part.split(":", 1)
                    return f"{scheme}://{user}:***@{host_part}"
    return url


def parse_database_url(url: str) -> dict:
    """
    Parse database URL to extract components.
    
    Returns:
        Dictionary with user, password (masked), host, port, database
    """
    if not url or "://" not in url:
        return {}
    
    # Remove driver prefix if present
    clean_url = url.replace("postgresql+asyncpg://", "postgresql://")
    clean_url = clean_url.replace("postgresql://", "")
    
    if "@" in clean_url:
        auth_part, host_part = clean_url.split("@", 1)
        if ":" in auth_part:
            user, password = auth_part.split(":", 1)
        else:
            user = auth_part
            password = ""
        
        if "/" in host_part:
            host_port, database = host_part.split("/", 1)
        else:
            host_port = host_part
            database = ""
        
        if ":" in host_port:
            host, port = host_port.split(":", 1)
        else:
            host = host_port
            port = "5432"
        
        return {
            "user": user,
            "password": "***" if password else "(none)",
            "host": host,
            "port": port,
            "database": database,
        }
    
    return {}


def print_environment_variables():
    """Print relevant environment variables."""
    print("\n" + "=" * 70)
    print("Environment Variables")
    print("=" * 70)
    
    # Check DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        print(f"[OK] DATABASE_URL is set (masked): {mask_password_in_url(database_url)}")
    else:
        print("[NOT SET] DATABASE_URL is not set")
    
    # Check individual components
    print("\nIndividual Components:")
    db_user = os.getenv("DB_USER", "postgres (default)")
    db_password = os.getenv("DB_PASSWORD", "(not set)")
    db_host = os.getenv("DB_HOST", "localhost (default)")
    db_port = os.getenv("DB_PORT", "5432 (default)")
    db_name = os.getenv("DB_NAME", "sentinai (default)")
    
    print(f"  DB_USER: {db_user}")
    print(f"  DB_PASSWORD: {'***' if db_password != '(not set)' else '(not set)'}")
    print(f"  DB_HOST: {db_host}")
    print(f"  DB_PORT: {db_port}")
    print(f"  DB_NAME: {db_name}")


def print_connection_details():
    """Print parsed connection details."""
    print("\n" + "=" * 70)
    print("Database Connection Details")
    print("=" * 70)
    
    try:
        database_url = get_database_url()
        safe_url = mask_password_in_url(database_url)
        print(f"Connection URL (masked): {safe_url}")
        
        # Parse and display components
        components = parse_database_url(database_url)
        if components:
            print("\nParsed Components:")
            print(f"  Username: {components.get('user', 'N/A')}")
            print(f"  Password: {components.get('password', 'N/A')}")
            print(f"  Host: {components.get('host', 'N/A')}")
            print(f"  Port: {components.get('port', 'N/A')}")
            print(f"  Database: {components.get('database', 'N/A')}")
        
        # Pool settings
        settings = get_database_settings()
        print("\nConnection Pool Settings:")
        print(f"  Pool Size: {settings.pool_size}")
        print(f"  Max Overflow: {settings.max_overflow}")
        print(f"  Pool Timeout: {settings.pool_timeout} seconds")
        print(f"  Echo SQL: {settings.echo}")
        
    except Exception as e:
        print(f"[ERROR] Error getting connection details: {e}")


async def test_connection():
    """Test database connection."""
    print("\n" + "=" * 70)
    print("Testing Database Connection")
    print("=" * 70)
    
    try:
        # Test connection
        print("Attempting to connect...")
        is_connected = await check_database_connection(retries=1, initial_delay=0.5)
        
        if is_connected:
            print("[SUCCESS] Database connection successful!")
            
            # Try to get engine and check if tables exist
            try:
                engine = get_engine()
                print(f"[OK] Database engine created successfully")
                print(f"  Engine URL (masked): {mask_password_in_url(str(engine.url))}")
            except Exception as e:
                print(f"[WARNING] Engine creation warning: {e}")
        else:
            print("[FAILED] Database connection failed!")
            print("\nTroubleshooting:")
            print("  1. Check if PostgreSQL is running:")
            print("     - Windows: Check Services or run 'pg_isready'")
            print("     - Linux/Mac: Run 'pg_isready' or 'psql -U postgres -c \"SELECT 1\"'")
            print("  2. Verify DATABASE_URL or individual DB_* environment variables")
            print("  3. Check database credentials (username, password)")
            print("  4. Ensure database 'sentinai' exists:")
            print("     createdb -U postgres sentinai")
            print("  5. Check firewall/network settings")
            
    except Exception as e:
        print(f"[ERROR] Connection test error: {e}")
        print("\nTroubleshooting:")
        print("  1. Ensure PostgreSQL is installed and running")
        print("  2. Check environment variables are set correctly")
        print("  3. Verify database exists and credentials are correct")


async def main():
    """Main function."""
    print("=" * 70)
    print("Database Connection Checker")
    print("=" * 70)
    
    print_environment_variables()
    print_connection_details()
    await test_connection()
    
    print("\n" + "=" * 70)
    print("Done")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())

