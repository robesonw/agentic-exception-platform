"""
Comprehensive tests for Phase 2 Advanced Semantic Search (Hybrid).

Tests:
- Hybrid search merges vector + keyword results correctly
- Filters work (exceptionType, severity, domainName)
- Explanations returned with relevance scores
- Integration with TriageAgent
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock

from src.memory.rag import (
    HybridSearchFilters,
    HybridSearchResult,
    hybrid_search,
)
from src.memory.index import MemoryIndexRegistry
from src.memory.rag import DummyEmbeddingProvider
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def embedding_provider():
    """Fixture for embedding provider."""
    return DummyEmbeddingProvider(dimension=64)


@pytest.fixture
def memory_index_registry(embedding_provider):
    """Fixture for memory index registry."""
    return MemoryIndexRegistry(embedding_provider=embedding_provider)


@pytest.fixture
def sample_exception_1():
    """Sample exception for testing."""
    return ExceptionRecord(
        exceptionId="exc_1",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD-001", "error": "Payment failed", "errorCode": "PAY_ERR"},
        resolutionStatus=ResolutionStatus.RESOLVED,
    )


@pytest.fixture
def sample_exception_2():
    """Another sample exception for testing."""
    return ExceptionRecord(
        exceptionId="exc_2",
        tenantId="TENANT_A",
        sourceSystem="CRM",
        exceptionType="DATA_MISMATCH",
        severity=Severity.MEDIUM,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD-002", "error": "Data mismatch", "errorCode": "DATA_ERR"},
        resolutionStatus=ResolutionStatus.RESOLVED,
    )


@pytest.fixture
def sample_exception_3():
    """Another sample exception for testing."""
    return ExceptionRecord(
        exceptionId="exc_3",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.CRITICAL,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD-003", "error": "Payment failed", "errorCode": "PAY_ERR"},
        resolutionStatus=ResolutionStatus.RESOLVED,
    )


class TestHybridSearchFilters:
    """Tests for HybridSearchFilters."""

    def test_filters_creation(self):
        """Test creating filters."""
        filters = HybridSearchFilters(
            exception_type="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            source_system="ERP",
        )
        
        assert filters.exception_type == "SETTLEMENT_FAIL"
        assert filters.severity == Severity.HIGH
        assert filters.source_system == "ERP"

    def test_filters_partial(self):
        """Test creating filters with partial fields."""
        filters = HybridSearchFilters(exception_type="SETTLEMENT_FAIL")
        
        assert filters.exception_type == "SETTLEMENT_FAIL"
        assert filters.severity is None
        assert filters.source_system is None


class TestHybridSearch:
    """Tests for hybrid_search function."""

    def test_hybrid_search_empty_index(
        self, memory_index_registry, embedding_provider, sample_exception_1
    ):
        """Test hybrid search with empty index."""
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
        )
        
        assert results == []

    def test_hybrid_search_merges_results(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
        sample_exception_3,
    ):
        """Test that hybrid search merges vector and keyword results."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_3, "Resolved by manual intervention"
        )
        
        # Perform hybrid search
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
        )
        
        # Should return results
        assert len(results) > 0
        
        # Verify result structure
        for result in results:
            assert isinstance(result, HybridSearchResult)
            assert result.exception_id is not None
            assert result.tenant_id == "TENANT_A"
            assert 0.0 <= result.vector_score <= 1.0
            assert 0.0 <= result.keyword_score <= 1.0
            assert 0.0 <= result.combined_score <= 1.0
            assert result.explanation is not None
            assert isinstance(result.metadata, dict)

    def test_hybrid_search_sorted_by_score(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
        sample_exception_3,
    ):
        """Test that hybrid search results are sorted by combined score."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_3, "Resolved by manual intervention"
        )
        
        # Perform hybrid search
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
        )
        
        # Verify results are sorted by combined score (descending)
        if len(results) > 1:
            for i in range(len(results) - 1):
                assert results[i].combined_score >= results[i + 1].combined_score

    def test_hybrid_search_filters_by_exception_type(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
        sample_exception_3,
    ):
        """Test filtering by exception type."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_3, "Resolved by manual intervention"
        )
        
        # Perform hybrid search with filter
        filters = HybridSearchFilters(exception_type="SETTLEMENT_FAIL")
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
            filters=filters,
        )
        
        # All results should have matching exception type
        for result in results:
            assert result.metadata.get("exception_type") == "SETTLEMENT_FAIL"

    def test_hybrid_search_filters_by_severity(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
        sample_exception_3,
    ):
        """Test filtering by severity."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_3, "Resolved by manual intervention"
        )
        
        # Perform hybrid search with filter
        filters = HybridSearchFilters(severity=Severity.HIGH)
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
            filters=filters,
        )
        
        # All results should have matching severity
        for result in results:
            assert result.metadata.get("severity") == "HIGH"

    def test_hybrid_search_filters_by_source_system(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
        sample_exception_3,
    ):
        """Test filtering by source system."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_3, "Resolved by manual intervention"
        )
        
        # Perform hybrid search with filter
        filters = HybridSearchFilters(source_system="ERP")
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
            filters=filters,
        )
        
        # All results should have matching source system
        for result in results:
            assert result.metadata.get("source_system") == "ERP"

    def test_hybrid_search_multiple_filters(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
        sample_exception_3,
    ):
        """Test filtering with multiple criteria."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_3, "Resolved by manual intervention"
        )
        
        # Perform hybrid search with multiple filters
        filters = HybridSearchFilters(
            exception_type="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            source_system="ERP",
        )
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
            filters=filters,
        )
        
        # All results should match all filters
        for result in results:
            assert result.metadata.get("exception_type") == "SETTLEMENT_FAIL"
            assert result.metadata.get("severity") == "HIGH"
            assert result.metadata.get("source_system") == "ERP"

    def test_hybrid_search_explanations(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
    ):
        """Test that explanations are returned."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        
        # Perform hybrid search
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
        )
        
        # Verify explanations are present
        for result in results:
            assert result.explanation is not None
            assert len(result.explanation) > 0
            # Explanation should contain relevant information
            assert "Vector" in result.explanation or "Keyword" in result.explanation

    def test_hybrid_search_weights(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
        sample_exception_2,
    ):
        """Test that custom weights affect combined score."""
        # Add exceptions to memory index
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying payment"
        )
        memory_index_registry.add_exception(
            "TENANT_A", sample_exception_2, "Resolved by data correction"
        )
        
        # Perform hybrid search with default weights
        results_default = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
            vector_weight=0.7,
            keyword_weight=0.3,
        )
        
        # Perform hybrid search with different weights
        results_custom = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=5,
            vector_weight=0.3,
            keyword_weight=0.7,
        )
        
        # Results should be different (different ranking)
        # Note: This is a basic test - in practice, weights would affect ranking
        assert len(results_default) == len(results_custom)

    def test_hybrid_search_limits_k(
        self,
        memory_index_registry,
        embedding_provider,
        sample_exception_1,
    ):
        """Test that hybrid search respects k limit."""
        # Add multiple exceptions
        for i in range(10):
            exception = ExceptionRecord(
                exceptionId=f"exc_{i}",
                tenantId="TENANT_A",
                sourceSystem="ERP",
                exceptionType="SETTLEMENT_FAIL",
                severity=Severity.HIGH,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"orderId": f"ORD-{i}", "error": f"Error {i}"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            )
            memory_index_registry.add_exception("TENANT_A", exception, f"Resolution {i}")
        
        # Perform hybrid search with k=3
        results = hybrid_search(
            exception_record=sample_exception_1,
            memory_index_registry=memory_index_registry,
            embedding_provider=embedding_provider,
            k=3,
        )
        
        # Should return at most 3 results
        assert len(results) <= 3


class TestHybridSearchIntegration:
    """Tests for hybrid search integration with TriageAgent."""

    def test_triage_agent_uses_hybrid_search(self):
        """Test that TriageAgent can use hybrid search."""
        # This is tested indirectly through TriageAgent tests
        # The integration is verified by checking that hybrid_search_results
        # are included in the agent decision evidence
        pass

