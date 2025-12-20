"""
Check database connection and show current DATABASE_URL configuration.
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to load .env file
try:
    from dotenv import load_dotenv
    env_path = project_root / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"Loaded .env file from {env_path}")
    else:
        print("No .env file found")
except ImportError:
    print("python-dotenv not installed, skipping .env loading")

print("\n" + "=" * 60)
print("Database Configuration Check")
print("=" * 60)

# Check DATABASE_URL
database_url = os.getenv("DATABASE_URL")
if database_url:
    # Mask password in output
    if "@" in database_url:
        parts = database_url.split("@")
        if ":" in parts[0]:
            user_pass = parts[0].split(":")
            if len(user_pass) == 2:
                masked = f"{user_pass[0]}:****@{parts[1]}"
            else:
                masked = database_url.replace("postgres", "postgres").replace(":", ":****@", 1) if ":" in database_url else database_url
        else:
            masked = database_url
    else:
        masked = database_url
    print(f"\nDATABASE_URL: {masked}")
else:
    print("\nDATABASE_URL: Not set")
    print("\nUsing individual components:")
    print(f"  DB_USER: {os.getenv('DB_USER', 'postgres')}")
    print(f"  DB_PASSWORD: {'****' if os.getenv('DB_PASSWORD') else '(not set)'}")
    print(f"  DB_HOST: {os.getenv('DB_HOST', 'localhost')}")
    print(f"  DB_PORT: {os.getenv('DB_PORT', '5432')}")
    print(f"  DB_NAME: {os.getenv('DB_NAME', 'sentinai')}")

print("\n" + "=" * 60)
print("To fix the password error:")
print("=" * 60)
print("\nOption 1: Set DATABASE_URL environment variable")
print('  Example: $env:DATABASE_URL="postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/sentinai"')
print("\nOption 2: Set individual components")
print('  $env:DB_PASSWORD="YOUR_PASSWORD"')
print('  $env:DB_USER="postgres"')
print('  $env:DB_HOST="localhost"')
print('  $env:DB_PORT="5432"')
print('  $env:DB_NAME="sentinai"')
print("\nOption 3: Create a .env file in the project root:")
print('  DATABASE_URL=postgresql+asyncpg://postgres:YOUR_PASSWORD@localhost:5432/sentinai')
print("\n" + "=" * 60)
