"""
Quota Integration Wrappers (P3-26).

Provides quota-aware wrappers for VectorStore and integration helpers
for ExecutionEngine.
"""

import logging
from typing import Any, Optional

from src.memory.vector_store import SearchResult, VectorPoint, VectorStore

logger = logging.getLogger(__name__)


class QuotaAwareVectorStore(VectorStore):
    """
    Wrapper around VectorStore that enforces quota limits.
    
    Checks quotas before operations and records usage after operations.
    """

    def __init__(
        self,
        vector_store: VectorStore,
        quota_enforcer: Optional[Any] = None,
    ):
        """
        Initialize quota-aware vector store wrapper.
        
        Args:
            vector_store: Underlying VectorStore instance
            quota_enforcer: Optional QuotaEnforcer instance
        """
        self.vector_store = vector_store
        self.quota_enforcer = quota_enforcer

    def upsert_points(self, tenant_id: str, points: list[VectorPoint]) -> None:
        """
        Upsert vector points with quota checking.
        
        Args:
            tenant_id: Tenant identifier
            points: List of vector points to upsert
        """
        if not points:
            return

        # Phase 3: Check quota before operation (P3-26)
        if self.quota_enforcer:
            try:
                # Estimate storage delta (rough: ~1KB per point for MVP)
                # In production, would calculate actual vector size
                storage_mb_delta = len(points) * 0.001  # 1KB per point = 0.001 MB
                
                self.quota_enforcer.check_vector_quota(
                    tenant_id=tenant_id,
                    write_count=len(points),
                    storage_mb_delta=storage_mb_delta,
                )
            except Exception as e:
                if hasattr(e, 'quota_type'):  # QuotaExceeded
                    logger.error(f"Vector quota exceeded for tenant {tenant_id}: {e}")
                    raise
                raise

        # Perform operation
        self.vector_store.upsert_points(tenant_id, points)

        # Phase 3: Record usage after operation
        if self.quota_enforcer:
            try:
                storage_mb_delta = len(points) * 0.001
                self.quota_enforcer.record_vector_usage(
                    tenant_id=tenant_id,
                    write_count=len(points),
                    storage_mb_delta=storage_mb_delta,
                )
            except Exception as e:
                logger.warning(f"Failed to record vector usage: {e}")

    def search(
        self,
        tenant_id: str,
        query_vector: list[float],
        limit: int = 10,
        score_threshold: Optional[float] = None,
    ) -> list[SearchResult]:
        """
        Search for similar vectors with quota checking.
        
        Args:
            tenant_id: Tenant identifier
            query_vector: Query vector for similarity search
            limit: Maximum number of results to return
            score_threshold: Optional minimum similarity score threshold
            
        Returns:
            List of search results sorted by similarity (descending)
        """
        # Phase 3: Check quota before operation (P3-26)
        if self.quota_enforcer:
            try:
                self.quota_enforcer.check_vector_quota(
                    tenant_id=tenant_id,
                    query_count=1,
                )
            except Exception as e:
                if hasattr(e, 'quota_type'):  # QuotaExceeded
                    logger.error(f"Vector quota exceeded for tenant {tenant_id}: {e}")
                    raise
                raise

        # Perform operation
        results = self.vector_store.search(tenant_id, query_vector, limit, score_threshold)

        # Phase 3: Record usage after operation
        if self.quota_enforcer:
            try:
                self.quota_enforcer.record_vector_usage(
                    tenant_id=tenant_id,
                    query_count=1,
                )
            except Exception as e:
                logger.warning(f"Failed to record vector usage: {e}")

        return results

    def delete_points(self, tenant_id: str, point_ids: list[str]) -> None:
        """
        Delete vector points (decreases storage).
        
        Args:
            tenant_id: Tenant identifier
            point_ids: List of point IDs to delete
        """
        # Phase 3: Record storage decrease
        if self.quota_enforcer and point_ids:
            try:
                # Estimate storage decrease
                storage_mb_delta = -len(point_ids) * 0.001  # Negative for decrease
                self.quota_enforcer.record_vector_usage(
                    tenant_id=tenant_id,
                    storage_mb_delta=storage_mb_delta,
                )
            except Exception as e:
                logger.warning(f"Failed to record vector usage: {e}")

        self.vector_store.delete_points(tenant_id, point_ids)

    def get_collection_name(self, tenant_id: str) -> str:
        """Get collection name for tenant."""
        return self.vector_store.get_collection_name(tenant_id)

    def ensure_collection(self, tenant_id: str, vector_size: int) -> None:
        """Ensure collection exists for tenant."""
        self.vector_store.ensure_collection(tenant_id, vector_size)

    def export_collection(self, tenant_id: str) -> dict[str, Any]:
        """Export collection data for backup."""
        return self.vector_store.export_collection(tenant_id)

    def restore_collection(self, tenant_id: str, data: dict[str, Any]) -> None:
        """Restore collection from backup data."""
        self.vector_store.restore_collection(tenant_id, data)


def wrap_vector_store_with_quota(
    vector_store: VectorStore, quota_enforcer: Optional[Any] = None
) -> VectorStore:
    """
    Wrap a VectorStore with quota enforcement.
    
    Args:
        vector_store: VectorStore instance to wrap
        quota_enforcer: Optional QuotaEnforcer instance
        
    Returns:
        QuotaAwareVectorStore wrapper (or original if quota_enforcer is None)
    """
    if quota_enforcer is None:
        return vector_store
    return QuotaAwareVectorStore(vector_store, quota_enforcer)

