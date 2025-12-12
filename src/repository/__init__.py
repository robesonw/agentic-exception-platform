"""
Repository layer for Phase 6 Persistence MVP.

This module provides base repository abstractions and implementations for
database access with tenant isolation and dependency injection.

All repositories follow the pattern:
- Async operations only
- Tenant isolation enforced
- Dependency injection (no global singletons)
- Session passed via constructor
"""

from src.repository.base import (
    AbstractBaseRepository,
    BaseRepository,
    PaginatedResult,
)
from src.repository.dto import (
    EventFilter,
    ExceptionCreateDTO,
    ExceptionCreateOrUpdateDTO,
    ExceptionEventCreateDTO,
    ExceptionEventDTO,
    ExceptionFilter,
    ExceptionUpdateDTO,
)
from src.repository.exception_events_repository import ExceptionEventRepository
from src.repository.exceptions_repository import ExceptionRepository

__all__ = [
    # Base classes
    "BaseRepository",
    "AbstractBaseRepository",
    "PaginatedResult",
    # DTOs
    "ExceptionCreateDTO",
    "ExceptionCreateOrUpdateDTO",
    "ExceptionUpdateDTO",
    "ExceptionFilter",
    "ExceptionEventCreateDTO",
    "ExceptionEventDTO",
    "EventFilter",
    # Repositories
    "ExceptionRepository",
    "ExceptionEventRepository",
]

