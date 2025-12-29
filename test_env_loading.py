"""
Test if environment variables are being loaded correctly from .env file.
"""
import os
from pathlib import Path

# Manually load .env file like the app does
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).parent / ".env"
    print(f"Looking for .env file at: {env_path}")
    print(f".env file exists: {env_path.exists()}")
    
    if env_path.exists():
        result = load_dotenv(env_path)
        print(f"load_dotenv result: {result}")
    else:
        print("❌ .env file not found!")
        
except ImportError:
    print("❌ python-dotenv not installed")

# Check database environment variables
print(f"\n=== Database Environment Variables ===")
print(f"DATABASE_URL: {os.getenv('DATABASE_URL', 'NOT SET')}")
print(f"DB_USER: {os.getenv('DB_USER', 'NOT SET')}")
print(f"DB_PASSWORD: {os.getenv('DB_PASSWORD', 'NOT SET')}")
print(f"DB_HOST: {os.getenv('DB_HOST', 'NOT SET')}")
print(f"DB_PORT: {os.getenv('DB_PORT', 'NOT SET')}")
print(f"DB_NAME: {os.getenv('DB_NAME', 'NOT SET')}")

# Test the database settings module
print(f"\n=== Database Settings Module ===")
try:
    from src.infrastructure.db.settings import get_database_settings
    settings = get_database_settings()
    print(f"Database URL: {settings.database_url}")
    print(f"Pool size: {settings.pool_size}")
    print(f"Max overflow: {settings.max_overflow}")
    print(f"Pool timeout: {settings.pool_timeout}")
    print(f"Echo: {settings.echo}")
except Exception as e:
    print(f"❌ Error loading database settings: {e}")
    import traceback
    traceback.print_exc()