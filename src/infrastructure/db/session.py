"""
Async database session management for Phase 6.

Provides async SQLAlchemy engine, connection pool, and FastAPI dependency injection.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.infrastructure.db.settings import get_database_settings

logger = logging.getLogger(__name__)

# Global engine and session factory
_engine: Optional[AsyncEngine] = None
_SessionLocal: Optional[async_sessionmaker[AsyncSession]] = None


def get_engine() -> AsyncEngine:
    """
    Get or create the async database engine.
    
    Returns:
        AsyncEngine instance
    """
    global _engine
    if _engine is None:
        settings = get_database_settings()
        
        logger.info(
            f"Creating async database engine (pool_size={settings.pool_size}, "
            f"max_overflow={settings.max_overflow}, timeout={settings.pool_timeout})"
        )
        
        # Mask password in URL for logging
        safe_url = _mask_password_in_url(settings.database_url)
        logger.debug(f"Database URL: {safe_url}")
        
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.pool_size,
            max_overflow=settings.max_overflow,
            pool_timeout=settings.pool_timeout,
            echo=settings.echo,
        )
        
        logger.info("Database engine created successfully")
    
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """
    Get or create the async session factory.
    
    Returns:
        async_sessionmaker instance
    """
    global _SessionLocal
    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = async_sessionmaker(
            bind=engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        logger.info("Session factory created successfully")
    
    return _SessionLocal


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency for getting database sessions.
    
    Yields:
        AsyncSession instance
        
    Example:
        @router.get("/items")
        async def get_items(session: AsyncSession = Depends(get_db_session)):
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


@asynccontextmanager
async def get_db_session_context() -> AsyncGenerator[AsyncSession, None]:
    """
    Context manager for database sessions (for use outside FastAPI).
    
    Yields:
        AsyncSession instance
        
    Example:
        async with get_db_session_context() as session:
            result = await session.execute(select(Item))
            return result.scalars().all()
    """
    session_factory = get_session_factory()
    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def close_engine() -> None:
    """
    Close the database engine and cleanup connections.
    
    Should be called on application shutdown.
    """
    global _engine, _SessionLocal
    if _engine is not None:
        logger.info("Closing database engine...")
        await _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("Database engine closed")


def _mask_password_in_url(url: str) -> str:
    """
    Mask password in database URL for safe logging.
    
    Args:
        url: Database URL
        
    Returns:
        URL with password masked
    """
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


async def check_database_connection(retries: int = 3, initial_delay: float = 1.0) -> bool:
    """
    Check database connection with retry logic and exponential backoff.
    
    Args:
        retries: Number of retry attempts
        initial_delay: Initial delay in seconds (doubles with each retry)
        
    Returns:
        True if connection successful, False otherwise
    """
    engine = get_engine()
    delay = initial_delay
    
    for attempt in range(retries):
        try:
            async with engine.connect() as conn:
                result = await conn.execute(text("SELECT 1"))
                result.scalar()
                logger.info("Database connection check successful")
                return True
        except Exception as e:
            error_msg = str(e)
            # Mask any potential secrets in error messages
            if "password" in error_msg.lower():
                error_msg = "Connection error (credentials masked)"
            
            if attempt < retries - 1:
                logger.warning(
                    f"Database connection check failed (attempt {attempt + 1}/{retries}): "
                    f"{error_msg}. Retrying in {delay}s..."
                )
                await asyncio.sleep(delay)
                delay *= 2  # Exponential backoff
            else:
                logger.error(
                    f"Database connection check failed after {retries} attempts: {error_msg}"
                )
                return False
    
    return False


async def initialize_database() -> bool:
    """
    Initialize database connection and verify connectivity.
    
    This should be called at application startup to ensure the database is available.
    
    Returns:
        True if initialization successful, False otherwise
    """
    logger.info("Initializing database connection...")
    
    try:
        # Create engine (lazy initialization)
        engine = get_engine()
        
        # Check connection with retries
        connected = await check_database_connection()
        
        if connected:
            logger.info("Database initialization successful")
        else:
            logger.error("Database initialization failed: connection check failed")
        
        return connected
    except Exception as e:
        logger.error(f"Database initialization failed: {e}", exc_info=True)
        return False

