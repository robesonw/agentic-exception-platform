"""
Database configuration settings for Phase 6.

Reads database connection settings from environment variables.
"""

import os
from typing import Optional


def get_database_url() -> str:
    """
    Get database URL from environment variable.
    
    Supports both sync (postgresql://) and async (postgresql+asyncpg://) URLs.
    If DATABASE_URL is set, it's used as-is. Otherwise, constructs from individual components.
    
    Returns:
        Database URL string (converted to async format if needed)
    """
    database_url = os.getenv("DATABASE_URL")
    
    if database_url:
        # If URL doesn't specify driver, assume asyncpg for async operations
        if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
            database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return database_url
    
    # Fallback: construct from individual components
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "sentinai")
    
    if db_password:
        return f"postgresql+asyncpg://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    else:
        return f"postgresql+asyncpg://{db_user}@{db_host}:{db_port}/{db_name}"


def get_db_pool_size() -> int:
    """Get database connection pool size from environment variable."""
    # Increase default pool size to handle concurrent workers
    return int(os.getenv("DB_POOL_SIZE", "20"))


def get_db_max_overflow() -> int:
    """Get database connection pool max overflow from environment variable."""
    # Increase default max overflow to handle concurrent workers
    return int(os.getenv("DB_MAX_OVERFLOW", "10"))


def get_db_pool_timeout() -> int:
    """Get database connection pool timeout from environment variable."""
    return int(os.getenv("DB_POOL_TIMEOUT", "30"))


def get_db_echo() -> bool:
    """Get database echo setting (SQL logging) from environment variable."""
    return os.getenv("DB_ECHO", "false").lower() in ("true", "1", "yes")


# Export settings as a simple object for easy access
class DatabaseSettings:
    """Database configuration settings."""
    
    def __init__(self):
        self.database_url = get_database_url()
        self.pool_size = get_db_pool_size()
        self.max_overflow = get_db_max_overflow()
        self.pool_timeout = get_db_pool_timeout()
        self.echo = get_db_echo()


# Global settings instance
_settings: Optional[DatabaseSettings] = None


def get_database_settings() -> DatabaseSettings:
    """
    Get database settings instance.
    
    Returns:
        DatabaseSettings instance
    """
    global _settings
    if _settings is None:
        _settings = DatabaseSettings()
    return _settings

