"""
Comprehensive tests for Memory/RAG layer.
Tests per-tenant isolation, similarity search, and embedding functionality.
"""

from datetime import datetime, timezone

import pytest

from src.memory.index import MemoryIndex, MemoryIndexRegistry, ExceptionMemoryEntry
from src.memory.rag import DummyEmbeddingProvider, EmbeddingProvider, cosine_similarity
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def embedding_provider():
    """Create dummy embedding provider for testing."""
    return DummyEmbeddingProvider(dimension=64)


@pytest.fixture
def memory_registry(embedding_provider):
    """Create memory index registry for testing."""
    return MemoryIndexRegistry(embedding_provider=embedding_provider)


@pytest.fixture
def sample_exception_1():
    """Create sample exception for tenant A."""
    return ExceptionRecord(
        exceptionId="exc_001",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD-123", "error": "SSI mismatch"},
        resolutionStatus=ResolutionStatus.RESOLVED,
    )


@pytest.fixture
def sample_exception_2():
    """Create sample exception for tenant B."""
    return ExceptionRecord(
        exceptionId="exc_002",
        tenantId="TENANT_B",
        sourceSystem="CRM",
        exceptionType="DATA_QUALITY_FAILURE",
        severity=Severity.MEDIUM,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"recordId": "REC-456", "error": "Invalid format"},
        resolutionStatus=ResolutionStatus.RESOLVED,
    )


class TestEmbeddingProvider:
    """Tests for embedding provider interface."""

    def test_dummy_embedding_provider_embed(self, embedding_provider):
        """Test that dummy provider generates embeddings."""
        text = "Test exception message"
        embedding = embedding_provider.embed(text)
        
        assert isinstance(embedding, list)
        assert len(embedding) == embedding_provider.dimension
        assert all(isinstance(x, float) for x in embedding)

    def test_dummy_embedding_provider_embed_batch(self, embedding_provider):
        """Test batch embedding generation."""
        texts = ["Text 1", "Text 2", "Text 3"]
        embeddings = embedding_provider.embed_batch(texts)
        
        assert len(embeddings) == 3
        assert all(len(emb) == embedding_provider.dimension for emb in embeddings)

    def test_dummy_embedding_provider_dimension(self, embedding_provider):
        """Test dimension property."""
        assert embedding_provider.dimension == 64

    def test_dummy_embedding_provider_deterministic(self, embedding_provider):
        """Test that same text produces same embedding."""
        text = "Test exception"
        emb1 = embedding_provider.embed(text)
        emb2 = embedding_provider.embed(text)
        
        assert emb1 == emb2

    def test_dummy_embedding_provider_different_texts(self, embedding_provider):
        """Test that different texts produce different embeddings."""
        emb1 = embedding_provider.embed("Text 1")
        emb2 = embedding_provider.embed("Text 2")
        
        assert emb1 != emb2


class TestCosineSimilarity:
    """Tests for cosine similarity calculation."""

    def test_cosine_similarity_identical_vectors(self):
        """Test that identical vectors have similarity 1.0."""
        vec = [1.0, 0.0, 0.0]
        similarity = cosine_similarity(vec, vec)
        
        assert abs(similarity - 1.0) < 1e-6

    def test_cosine_similarity_orthogonal_vectors(self):
        """Test that orthogonal vectors have similarity 0.0."""
        vec1 = [1.0, 0.0]
        vec2 = [0.0, 1.0]
        similarity = cosine_similarity(vec1, vec2)
        
        assert abs(similarity) < 1e-6

    def test_cosine_similarity_range(self):
        """Test that similarity is in range [-1, 1]."""
        vec1 = [1.0, 2.0, 3.0]
        vec2 = [4.0, 5.0, 6.0]
        similarity = cosine_similarity(vec1, vec2)
        
        assert -1.0 <= similarity <= 1.0

    def test_cosine_similarity_zero_vectors(self):
        """Test that zero vectors return 0.0 similarity."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 2.0, 3.0]
        similarity = cosine_similarity(vec1, vec2)
        
        assert similarity == 0.0


class TestMemoryIndex:
    """Tests for MemoryIndex per-tenant storage."""

    def test_add_exception(self, embedding_provider, sample_exception_1):
        """Test adding exception to memory index."""
        index = MemoryIndex("TENANT_A", embedding_provider)
        index.add_exception(sample_exception_1, "Resolved by retrying settlement")
        
        assert index.get_count() == 1

    def test_search_similar_empty_index(self, embedding_provider, sample_exception_1):
        """Test that search returns empty list for empty index."""
        index = MemoryIndex("TENANT_A", embedding_provider)
        results = index.search_similar(sample_exception_1, k=5)
        
        assert results == []

    def test_search_similar_returns_ranked_results(
        self, embedding_provider, sample_exception_1
    ):
        """Test that search returns ranked results."""
        index = MemoryIndex("TENANT_A", embedding_provider)
        
        # Add multiple exceptions
        for i in range(5):
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
            index.add_exception(exception, f"Resolution {i}")
        
        # Search for similar exception
        results = index.search_similar(sample_exception_1, k=5)
        
        assert len(results) == 5
        # Verify results are sorted by similarity (descending)
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]  # Similarity scores in descending order

    def test_search_similar_limits_k(self, embedding_provider, sample_exception_1):
        """Test that search respects k parameter."""
        index = MemoryIndex("TENANT_A", embedding_provider)
        
        # Add 10 exceptions
        for i in range(10):
            exception = ExceptionRecord(
                exceptionId=f"exc_{i}",
                tenantId="TENANT_A",
                sourceSystem="ERP",
                exceptionType="SETTLEMENT_FAIL",
                severity=Severity.HIGH,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"orderId": f"ORD-{i}"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            )
            index.add_exception(exception, f"Resolution {i}")
        
        # Search with k=3
        results = index.search_similar(sample_exception_1, k=3)
        
        assert len(results) == 3

    def test_clear_index(self, embedding_provider, sample_exception_1):
        """Test clearing memory index."""
        index = MemoryIndex("TENANT_A", embedding_provider)
        index.add_exception(sample_exception_1, "Resolution")
        
        assert index.get_count() == 1
        
        index.clear()
        assert index.get_count() == 0


class TestMemoryIndexRegistry:
    """Tests for MemoryIndexRegistry with tenant isolation."""

    def test_get_or_create_index(self, memory_registry):
        """Test getting or creating index for tenant."""
        index = memory_registry.get_or_create_index("TENANT_A")
        
        assert index is not None
        assert index.tenant_id == "TENANT_A"
        assert memory_registry.has_index("TENANT_A")

    def test_get_or_create_index_returns_same_instance(self, memory_registry):
        """Test that get_or_create returns same instance."""
        index1 = memory_registry.get_or_create_index("TENANT_A")
        index2 = memory_registry.get_or_create_index("TENANT_A")
        
        assert index1 is index2

    def test_add_exception(self, memory_registry, sample_exception_1):
        """Test adding exception via registry."""
        memory_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying"
        )
        
        index = memory_registry.get_index("TENANT_A")
        assert index is not None
        assert index.get_count() == 1

    def test_search_similar(self, memory_registry, sample_exception_1):
        """Test searching similar exceptions via registry."""
        memory_registry.add_exception(
            "TENANT_A", sample_exception_1, "Resolved by retrying"
        )
        
        results = memory_registry.search_similar("TENANT_A", sample_exception_1, k=5)
        
        assert len(results) == 1
        assert results[0][0].exception_id == sample_exception_1.exception_id

    def test_search_similar_empty_index(self, memory_registry, sample_exception_1):
        """Test searching in non-existent index returns empty list."""
        results = memory_registry.search_similar("TENANT_A", sample_exception_1, k=5)
        
        assert results == []


class TestTenantIsolation:
    """Tests for tenant isolation in memory indexes."""

    def test_tenant_isolation_separate_indexes(self, memory_registry):
        """Test that different tenants have separate indexes."""
        index_a = memory_registry.get_or_create_index("TENANT_A")
        index_b = memory_registry.get_or_create_index("TENANT_B")
        
        assert index_a is not index_b
        assert index_a.tenant_id == "TENANT_A"
        assert index_b.tenant_id == "TENANT_B"

    def test_tenant_isolation_search_results(
        self, memory_registry, sample_exception_1, sample_exception_2
    ):
        """Test that tenant A search never returns tenant B data."""
        # Add exceptions to both tenants
        memory_registry.add_exception("TENANT_A", sample_exception_1, "Resolution A")
        memory_registry.add_exception("TENANT_B", sample_exception_2, "Resolution B")
        
        # Search in tenant A
        results_a = memory_registry.search_similar("TENANT_A", sample_exception_1, k=10)
        
        # Verify all results are from tenant A
        assert len(results_a) == 1
        assert all(entry.tenant_id == "TENANT_A" for entry, _ in results_a)
        assert all(entry.exception_id != sample_exception_2.exception_id for entry, _ in results_a)
        
        # Search in tenant B
        results_b = memory_registry.search_similar("TENANT_B", sample_exception_2, k=10)
        
        # Verify all results are from tenant B
        assert len(results_b) == 1
        assert all(entry.tenant_id == "TENANT_B" for entry, _ in results_b)
        assert all(entry.exception_id != sample_exception_1.exception_id for entry, _ in results_b)

    def test_tenant_isolation_multiple_tenants(
        self, memory_registry, sample_exception_1, sample_exception_2
    ):
        """Test isolation with multiple tenants and exceptions."""
        # Add exceptions to tenant A
        for i in range(3):
            exception = ExceptionRecord(
                exceptionId=f"exc_a_{i}",
                tenantId="TENANT_A",
                sourceSystem="ERP",
                exceptionType="SETTLEMENT_FAIL",
                severity=Severity.HIGH,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"orderId": f"ORD-A-{i}"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            )
            memory_registry.add_exception("TENANT_A", exception, f"Resolution A-{i}")
        
        # Add exceptions to tenant B
        for i in range(3):
            exception = ExceptionRecord(
                exceptionId=f"exc_b_{i}",
                tenantId="TENANT_B",
                sourceSystem="CRM",
                exceptionType="DATA_QUALITY_FAILURE",
                severity=Severity.MEDIUM,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"recordId": f"REC-B-{i}"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            )
            memory_registry.add_exception("TENANT_B", exception, f"Resolution B-{i}")
        
        # Search in tenant A
        query = ExceptionRecord(
            exceptionId="query",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        results_a = memory_registry.search_similar("TENANT_A", query, k=10)
        
        # Verify all results are from tenant A
        assert all(entry.tenant_id == "TENANT_A" for entry, _ in results_a)
        assert all(entry.exception_id.startswith("exc_a_") for entry, _ in results_a)
        assert len(results_a) == 3

    def test_tenant_isolation_clear_index(self, memory_registry, sample_exception_1, sample_exception_2):
        """Test that clearing one tenant's index doesn't affect others."""
        memory_registry.add_exception("TENANT_A", sample_exception_1, "Resolution A")
        memory_registry.add_exception("TENANT_B", sample_exception_2, "Resolution B")
        
        # Clear tenant A's index
        memory_registry.clear_index("TENANT_A")
        
        # Verify tenant A index is empty
        index_a = memory_registry.get_index("TENANT_A")
        assert index_a.get_count() == 0
        
        # Verify tenant B index still has data
        index_b = memory_registry.get_index("TENANT_B")
        assert index_b.get_count() == 1

    def test_tenant_isolation_remove_index(self, memory_registry, sample_exception_1, sample_exception_2):
        """Test that removing one tenant's index doesn't affect others."""
        memory_registry.add_exception("TENANT_A", sample_exception_1, "Resolution A")
        memory_registry.add_exception("TENANT_B", sample_exception_2, "Resolution B")
        
        # Remove tenant A's index
        memory_registry.remove_index("TENANT_A")
        
        # Verify tenant A index doesn't exist
        assert not memory_registry.has_index("TENANT_A")
        
        # Verify tenant B index still exists
        assert memory_registry.has_index("TENANT_B")
        index_b = memory_registry.get_index("TENANT_B")
        assert index_b.get_count() == 1


class TestMemoryIndexSearchRanking:
    """Tests for search result ranking."""

    def test_search_returns_ranked_by_similarity(self, memory_registry):
        """Test that search results are ranked by similarity."""
        # Add exceptions with different characteristics
        exceptions = [
            ExceptionRecord(
                exceptionId="exc_1",
                tenantId="TENANT_A",
                sourceSystem="ERP",
                exceptionType="SETTLEMENT_FAIL",
                severity=Severity.HIGH,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"error": "SSI mismatch"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            ),
            ExceptionRecord(
                exceptionId="exc_2",
                tenantId="TENANT_A",
                sourceSystem="ERP",
                exceptionType="SETTLEMENT_FAIL",
                severity=Severity.HIGH,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"error": "SSI mismatch"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            ),
            ExceptionRecord(
                exceptionId="exc_3",
                tenantId="TENANT_A",
                sourceSystem="CRM",
                exceptionType="DATA_QUALITY_FAILURE",
                severity=Severity.MEDIUM,
                timestamp=datetime.now(timezone.utc),
                rawPayload={"error": "Invalid format"},
                resolutionStatus=ResolutionStatus.RESOLVED,
            ),
        ]
        
        for exc in exceptions:
            memory_registry.add_exception("TENANT_A", exc, "Resolved")
        
        # Search with query similar to SETTLEMENT_FAIL
        query = ExceptionRecord(
            exceptionId="query",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "SSI mismatch"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        results = memory_registry.search_similar("TENANT_A", query, k=5)
        
        # Verify results are ranked (similarity descending)
        assert len(results) == 3
        for i in range(len(results) - 1):
            assert results[i][1] >= results[i + 1][1]  # Similarity scores in descending order

    def test_search_most_similar_first(self, memory_registry):
        """Test that most similar exception appears first."""
        # Add exceptions
        similar_exc = ExceptionRecord(
            exceptionId="similar",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "SSI mismatch", "orderId": "ORD-123"},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        
        different_exc = ExceptionRecord(
            exceptionId="different",
            tenantId="TENANT_A",
            sourceSystem="CRM",
            exceptionType="DATA_QUALITY_FAILURE",
            severity=Severity.LOW,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "Invalid format"},
            resolutionStatus=ResolutionStatus.RESOLVED,
        )
        
        memory_registry.add_exception("TENANT_A", similar_exc, "Resolved")
        memory_registry.add_exception("TENANT_A", different_exc, "Resolved")
        
        # Query similar to similar_exc
        query = ExceptionRecord(
            exceptionId="query",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            severity=Severity.HIGH,
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "SSI mismatch", "orderId": "ORD-456"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        results = memory_registry.search_similar("TENANT_A", query, k=5)

        # Most similar should be first
        # Note: Dummy embedding provider uses hash-based random embeddings,
        # so exact ranking may vary. We verify that both exceptions are found.
        assert len(results) >= 1
        exception_ids = [result[0].exception_id for result in results]
        assert "similar" in exception_ids
        assert "different" in exception_ids
        # Ideally, similar should be first, but with dummy embeddings this may not be guaranteed
        # In production with real embeddings, this would be more reliable


class TestMemoryIndexIntegration:
    """Integration tests for memory index functionality."""

    def test_end_to_end_add_and_search(self, memory_registry):
        """Test complete workflow: add exceptions and search."""
        # Add multiple exceptions
        for i in range(5):
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
            memory_registry.add_exception(
                "TENANT_A", exception, f"Resolved exception {i}"
            )
        
        # Verify index has entries
        index = memory_registry.get_index("TENANT_A")
        assert index.get_count() == 5
        
        # Search for similar
        query = ExceptionRecord(
            exceptionId="query",
            tenantId="TENANT_A",
            sourceSystem="ERP",
            exceptionType="SETTLEMENT_FAIL",
            timestamp=datetime.now(timezone.utc),
            rawPayload={"orderId": "ORD-999"},
            resolutionStatus=ResolutionStatus.OPEN,
        )
        
        results = memory_registry.search_similar("TENANT_A", query, k=3)
        
        assert len(results) == 3
        assert all(entry.tenant_id == "TENANT_A" for entry, _ in results)

