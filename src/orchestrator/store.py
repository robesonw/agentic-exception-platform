"""
In-memory exception store for MVP.
Stores exception records with pipeline results for status API retrieval.

Phase 3: Enhanced with partitioning hooks for multi-tenant scaling.
"""

import logging
from typing import Any

from src.infrastructure.partitioning import PartitioningHelper
from src.models.exception_record import ExceptionRecord

logger = logging.getLogger(__name__)


class ExceptionStore:
    """
    In-memory store for exception records with pipeline results.
    
    Provides per-tenant isolation and stores the latest state of each exception.
    """

    def __init__(self):
        """Initialize the exception store."""
        # Structure: {tenant_id: {exception_id: (ExceptionRecord, pipeline_result)}}
        self._store: dict[str, dict[str, tuple[ExceptionRecord, dict[str, Any]]]] = {}

    def store_exception(
        self, exception: ExceptionRecord, pipeline_result: dict[str, Any]
    ) -> None:
        """
        Store an exception record with its pipeline result.
        
        Phase 3: Uses partitioning by tenant_id (and optionally domain) for scaling.
        
        Args:
            exception: ExceptionRecord to store
            pipeline_result: Pipeline processing result dictionary
        """
        tenant_id = exception.tenant_id
        exception_id = exception.exception_id
        
        # Phase 3: Extract partition key (tenant_id + domain)
        domain = exception.normalized_context.get("domain") if exception.normalized_context else None
        partition_key = PartitioningHelper.create_partition_key(tenant_id, domain)
        
        if tenant_id not in self._store:
            self._store[tenant_id] = {}
        
        self._store[tenant_id][exception_id] = (exception, pipeline_result)
        logger.debug(
            f"Stored exception {exception_id} for tenant {tenant_id} "
            f"(domain: {domain}, status: {exception.resolution_status.value})"
        )

    def get_exception(
        self, tenant_id: str, exception_id: str
    ) -> tuple[ExceptionRecord, dict[str, Any]] | None:
        """
        Retrieve an exception record with its pipeline result.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            
        Returns:
            Tuple of (ExceptionRecord, pipeline_result) or None if not found
        """
        if tenant_id not in self._store:
            logger.debug(f"No exceptions found for tenant {tenant_id}")
            return None
        
        if exception_id not in self._store[tenant_id]:
            logger.debug(f"Exception {exception_id} not found for tenant {tenant_id}")
            return None
        
        return self._store[tenant_id][exception_id]

    def get_tenant_exceptions(self, tenant_id: str) -> list[tuple[ExceptionRecord, dict[str, Any]]]:
        """
        Get all exceptions for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            List of tuples (ExceptionRecord, pipeline_result)
        """
        if tenant_id not in self._store:
            return []
        
        return list(self._store[tenant_id].values())

    def clear_tenant(self, tenant_id: str) -> None:
        """
        Clear all exceptions for a tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._store:
            del self._store[tenant_id]
            logger.info(f"Cleared all exceptions for tenant {tenant_id}")

    def clear_all(self) -> None:
        """Clear all exceptions from the store."""
        self._store.clear()
        logger.info("Cleared all exceptions from store")


# Global singleton instance
_exception_store: ExceptionStore | None = None


def get_exception_store() -> ExceptionStore:
    """
    Get the global exception store instance.
    
    Returns:
        ExceptionStore instance
    """
    global _exception_store
    if _exception_store is None:
        _exception_store = ExceptionStore()
    return _exception_store

