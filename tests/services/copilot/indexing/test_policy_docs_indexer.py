"""
Unit tests for PolicyDocsIndexer.

Tests policy document indexing with:
- Mock embedding generation
- Tenant isolation enforcement
- Incremental indexing with change detection
- Batch processing and error handling

References:
- src/services/copilot/indexing/policy_docs_indexer.py
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-4
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.db.models import CopilotDocumentSourceType
from src.infrastructure.repositories.copilot_document_repository import (
    CopilotDocumentRepository,
    DocumentChunk as RepositoryDocumentChunk,
)
from src.services.copilot.chunking_service import (
    ChunkingConfig,
    DocumentChunk,
    DocumentChunkingService,
    SourceDocument,
)
from src.services.copilot.embedding_service import (
    EmbeddingConfig,
    EmbeddingProvider,
    EmbeddingResult,
    EmbeddingService,
)
from src.services.copilot.indexing.policy_docs_indexer import (
    PolicyDoc,
    PolicyDocsIndexer,
)
from src.services.copilot.indexing.types import IndexingResult


@pytest.fixture
def mock_document_repository():
    """Mock CopilotDocumentRepository."""
    repo = MagicMock(spec=CopilotDocumentRepository)
    repo.upsert_chunks_batch = AsyncMock(return_value=2)  # Mock 2 chunks upserted
    repo.find_by_source = AsyncMock(return_value=[])  # No existing docs by default
    return repo


@pytest.fixture
def mock_embedding_service():
    """Mock EmbeddingService with mock provider."""
    config = EmbeddingConfig(
        provider=EmbeddingProvider.MOCK,
        model="mock-model",
        dimension=384,
    )
    service = EmbeddingService(config)
    return service


@pytest.fixture
def mock_chunking_service():
    """Mock DocumentChunkingService."""
    service = MagicMock(spec=DocumentChunkingService)
    
    # Mock chunk_document to return 2 chunks
    def mock_chunk_document(document: SourceDocument) -> list[DocumentChunk]:
        return [
            DocumentChunk(
                chunk_id=f"{document.source_id}-chunk-0",
                chunk_index=0,
                content=f"First chunk of {document.title or document.source_id}",
                source_type=document.source_type,
                source_id=document.source_id,
                domain=document.domain,
                version=document.version,
                metadata={"title": document.title, "chunk_type": "intro"},
                start_position=0,
                end_position=50,
                total_chunks=2,
            ),
            DocumentChunk(
                chunk_id=f"{document.source_id}-chunk-1",
                chunk_index=1,
                content=f"Second chunk of {document.title or document.source_id}",
                source_type=document.source_type,
                source_id=document.source_id,
                domain=document.domain,
                version=document.version,
                metadata={"title": document.title, "chunk_type": "details"},
                start_position=50,
                end_position=100,
                total_chunks=2,
            ),
        ]
    
    service.chunk_document.side_effect = mock_chunk_document
    return service


@pytest.fixture
def policy_docs_indexer(
    mock_document_repository,
    mock_embedding_service,
    mock_chunking_service,
):
    """PolicyDocsIndexer with mocked dependencies."""
    return PolicyDocsIndexer(
        document_repository=mock_document_repository,
        embedding_service=mock_embedding_service,
        chunking_service=mock_chunking_service,
    )


@pytest.fixture
def sample_policy_docs():
    """Sample policy documents for testing."""
    return [
        PolicyDoc(
            doc_id="POL-001",
            title="Data Privacy Policy",
            content="This policy outlines how we handle personal data and ensure privacy protection for all users.",
            description="Core data privacy guidelines",
            category="privacy",
            tags=["privacy", "data", "compliance"],
            url="https://company.com/policies/privacy",
            metadata={"version": "2.1", "approved_by": "Legal"},
        ),
        PolicyDoc(
            doc_id="POL-002",
            title="Security Standards",
            content="Security requirements and standards for all systems and processes within the organization.",
            description="Information security standards",
            category="security",
            tags=["security", "standards", "compliance"],
            metadata={"version": "1.5", "classification": "internal"},
        ),
    ]


class TestPolicyDoc:
    """Tests for PolicyDoc data class."""
    
    def test_policy_doc_creation(self):
        """Test PolicyDoc creation with basic fields."""
        doc = PolicyDoc(
            doc_id="TEST-001",
            title="Test Policy",
            content="Test content",
        )
        
        assert doc.doc_id == "TEST-001"
        assert doc.title == "Test Policy"
        assert doc.content == "Test content"
        assert doc.description is None
        assert doc.tags == []
        assert doc.metadata == {}
    
    def test_policy_doc_with_metadata(self):
        """Test PolicyDoc creation with full metadata."""
        doc = PolicyDoc(
            doc_id="TEST-001",
            title="Test Policy",
            content="Test content",
            description="Test description",
            url="https://example.com",
            category="test",
            tags=["test", "sample"],
            metadata={"version": "1.0"},
        )
        
        assert doc.description == "Test description"
        assert doc.url == "https://example.com"
        assert doc.category == "test"
        assert doc.tags == ["test", "sample"]
        assert doc.metadata == {"version": "1.0"}
    
    def test_to_source_document(self):
        """Test conversion to SourceDocument."""
        doc = PolicyDoc(
            doc_id="TEST-001",
            title="Test Policy",
            content="Test content",
            description="Test description",
            tags=["test"],
            metadata={"custom": "value"},
        )
        
        source_doc = doc.to_source_document(
            domain="Finance",
            pack_version="1.2.3",
        )
        
        assert source_doc.source_type == CopilotDocumentSourceType.POLICY_DOC.value
        assert source_doc.source_id == "TEST-001"
        assert source_doc.content == "Test content"
        assert source_doc.domain == "Finance"
        assert source_doc.version == "1.2.3"
        assert source_doc.title == "Test Policy"
        
        # Check metadata merging
        assert source_doc.metadata["description"] == "Test description"
        assert source_doc.metadata["tags"] == ["test"]
        assert source_doc.metadata["custom"] == "value"


class TestPolicyDocsIndexer:
    """Tests for PolicyDocsIndexer."""
    
    def test_source_type(self, policy_docs_indexer):
        """Test that source type is correctly set."""
        assert policy_docs_indexer.source_type == CopilotDocumentSourceType.POLICY_DOC
    
    def test_supports_tenant_valid(self, policy_docs_indexer):
        """Test tenant validation with valid tenant IDs."""
        valid_tenants = ["TENANT_001", "company-dept", "org_123"]
        
        for tenant_id in valid_tenants:
            assert policy_docs_indexer.supports_tenant(tenant_id)
    
    def test_supports_tenant_invalid(self, policy_docs_indexer):
        """Test tenant validation with invalid tenant IDs."""
        invalid_tenants = ["", None, "tenant with spaces", "tenant@invalid"]
        
        for tenant_id in invalid_tenants:
            assert not policy_docs_indexer.supports_tenant(tenant_id)
    
    @pytest.mark.asyncio
    async def test_index_policy_docs_success(
        self,
        policy_docs_indexer,
        sample_policy_docs,
        mock_document_repository,
        mock_chunking_service,
    ):
        """Test successful indexing of policy documents."""
        result = await policy_docs_indexer.index_policy_docs(
            tenant_id="TENANT_001",
            policy_docs=sample_policy_docs,
            domain="Finance",
            pack_version="1.0.0",
        )
        
        assert result.success
        assert result.tenant_id == "TENANT_001"
        assert result.source_type == CopilotDocumentSourceType.POLICY_DOC
        assert result.chunks_processed == 4  # 2 docs × 2 chunks each
        assert result.chunks_indexed == 4  # 2 docs × 2 upserted chunks each
        assert result.chunks_failed == 0
        assert result.source_version == "1.0.0"
        assert result.metadata["domain"] == "Finance"
        assert result.metadata["total_documents"] == 2
        
        # Verify chunking service was called
        assert mock_chunking_service.chunk_document.call_count == 2
        
        # Verify repository upsert was called
        assert mock_document_repository.upsert_chunks_batch.call_count == 2
    
    @pytest.mark.asyncio
    async def test_index_policy_docs_empty_list(self, policy_docs_indexer):
        """Test indexing with empty policy docs list."""
        result = await policy_docs_indexer.index_policy_docs(
            tenant_id="TENANT_001",
            policy_docs=[],
        )
        
        assert result.success
        assert result.chunks_processed == 0
        assert result.chunks_indexed == 0
        assert result.chunks_skipped == 0
    
    @pytest.mark.asyncio
    async def test_index_policy_docs_tenant_isolation(
        self,
        policy_docs_indexer,
        sample_policy_docs,
        mock_document_repository,
    ):
        """Test that tenant isolation is enforced."""
        # Index for tenant A
        await policy_docs_indexer.index_policy_docs(
            tenant_id="TENANT_A",
            policy_docs=sample_policy_docs,
        )
        
        # Index for tenant B
        await policy_docs_indexer.index_policy_docs(
            tenant_id="TENANT_B",
            policy_docs=sample_policy_docs,
        )
        
        # Verify each tenant's chunks were stored separately
        assert mock_document_repository.upsert_chunks_batch.call_count == 4
        
        # Check that tenant IDs were passed correctly
        calls = mock_document_repository.upsert_chunks_batch.call_args_list
        
        # First two calls should be for TENANT_A
        assert calls[0][1]["tenant_id"] == "TENANT_A"
        assert calls[1][1]["tenant_id"] == "TENANT_A"
        
        # Next two calls should be for TENANT_B
        assert calls[2][1]["tenant_id"] == "TENANT_B"
        assert calls[3][1]["tenant_id"] == "TENANT_B"
    
    @pytest.mark.asyncio
    async def test_index_incremental_new_document(
        self,
        policy_docs_indexer,
        mock_document_repository,
        mock_chunking_service,
    ):
        """Test incremental indexing of a new document."""
        # Mock no existing documents
        mock_document_repository.find_by_source.return_value = []
        
        result = await policy_docs_indexer.index_incremental(
            tenant_id="TENANT_001",
            source_id="POL-NEW",
            content="New policy content for testing incremental indexing.",
            metadata={
                "title": "New Policy",
                "description": "A new policy document",
                "category": "testing",
            },
            domain="Test",
            source_version="1.0",
        )
        
        assert result.success
        assert result.source_id == "POL-NEW"
        assert result.tenant_id == "TENANT_001"
        assert result.chunks_processed == 2  # Mocked chunking returns 2 chunks
        assert result.chunks_indexed == 2   # Mock upsert returns 2
        
        # Verify chunking was called
        mock_chunking_service.chunk_document.assert_called_once()
        
        # Verify repository operations
        mock_document_repository.find_by_source.assert_called_once_with(
            tenant_id="TENANT_001",
            source_type=CopilotDocumentSourceType.POLICY_DOC,
            source_id="POL-NEW",
        )
        mock_document_repository.upsert_chunks_batch.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_index_incremental_unchanged_document(
        self,
        policy_docs_indexer,
        mock_document_repository,
    ):
        """Test incremental indexing skips unchanged documents."""
        content = "Unchanged policy content"
        metadata = {"title": "Unchanged Policy", "version": "1.0"}
        
        # Mock existing document with same content
        from src.infrastructure.db.models import CopilotDocument
        existing_doc = MagicMock(spec=CopilotDocument)
        existing_doc.content = content
        existing_doc.metadata_json = metadata
        existing_doc.version = "1.0"
        
        mock_document_repository.find_by_source.return_value = [existing_doc]
        
        result = await policy_docs_indexer.index_incremental(
            tenant_id="TENANT_001",
            source_id="POL-UNCHANGED",
            content=content,
            metadata=metadata,
            source_version="1.0",
        )
        
        assert result.success
        assert result.chunks_processed == 1
        assert result.chunks_skipped == 1
        assert result.chunks_indexed == 0
        
        # Should not call upsert since document is unchanged
        mock_document_repository.upsert_chunks_batch.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_index_full_not_implemented(self, policy_docs_indexer):
        """Test that full indexing returns empty list (not implemented)."""
        results = await policy_docs_indexer.index_full(
            tenant_id="TENANT_001",
        )
        
        assert results == []
    
    @pytest.mark.asyncio
    async def test_index_policy_docs_with_chunking_failure(
        self,
        policy_docs_indexer,
        sample_policy_docs,
        mock_chunking_service,
    ):
        """Test handling of chunking failures."""
        # Mock chunking service to return empty chunks for one document
        def mock_chunk_with_failure(document: SourceDocument) -> list[DocumentChunk]:
            if "POL-001" in document.source_id:
                return []  # No chunks for first document
            return [
                DocumentChunk(
                    chunk_id=f"{document.source_id}-chunk-0",
                    chunk_index=0,
                    content="Test chunk",
                    source_type=document.source_type,
                    source_id=document.source_id,
                    total_chunks=1,
                )
            ]
        
        mock_chunking_service.chunk_document.side_effect = mock_chunk_with_failure
        
        result = await policy_docs_indexer.index_policy_docs(
            tenant_id="TENANT_001",
            policy_docs=sample_policy_docs,
        )
        
        assert result.success
        # Should process both docs, but only get chunks from one
        assert result.chunks_processed == 1  # Only POL-002 produces chunks
        # Embeddings will be processed for the chunks that were actually chunked
        assert result.chunks_indexed >= 1  # At least 1 chunk processed
    @pytest.mark.asyncio
    async def test_remove_nonexistent_document(
        self,
        policy_docs_indexer,
        mock_document_repository,
    ):
        """Test removal of nonexistent document."""
        # Mock no documents removed
        mock_document_repository.delete_by_source.return_value = 0
        
        result = await policy_docs_indexer.remove_document(
            tenant_id="TENANT_001",
            source_id="NONEXISTENT",
        )
        
        assert result is False

    @pytest.mark.asyncio
    async def test_invalid_tenant_raises_error(self, policy_docs_indexer, sample_policy_docs):
        """Test that invalid tenant ID returns failure."""
        # Test with empty tenant ID
        result = await policy_docs_indexer.index_policy_docs(
            tenant_id="",
            policy_docs=sample_policy_docs,
        )
        assert not result.success
        assert result.error_message and "Tenant ID is required" in result.error_message
        
        # Test with None tenant ID  
        result = await policy_docs_indexer.index_policy_docs(
            tenant_id=None,
            policy_docs=sample_policy_docs,
        )
        assert not result.success
        assert result.error_message and "Tenant ID is required" in result.error_message
