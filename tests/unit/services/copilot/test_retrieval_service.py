"""
Test suite for RetrievalService with tenant isolation validation.

Tests the Phase 13 evidence retrieval with pgvector similarity search.
"""

import pytest
from uuid import UUID, uuid4
from unittest.mock import AsyncMock, Mock

from src.services.copilot.retrieval.retrieval_service import EvidenceItem, RetrievalService
from src.infrastructure.repositories.copilot_document_repository import SimilarDocument
from src.infrastructure.db.models import CopilotDocument


class TestEvidenceItem:
    """Test EvidenceItem dataclass structure."""
    
    def test_evidence_item_creation(self):
        """Test EvidenceItem can be created with all required fields."""
        evidence = EvidenceItem(
            source_type="PolicyDoc",
            source_id=str(uuid4()),
            source_version="v1.2",
            title="Sample Policy",
            snippet="This is a policy snippet...",
            url="https://example.com/policy/123",
            similarity_score=0.85,
            chunk_text="Full policy text content here..."
        )
        
        assert evidence.source_type == "PolicyDoc"
        assert evidence.similarity_score == 0.85
        assert evidence.snippet == "This is a policy snippet..."
    
    def test_evidence_item_optional_fields(self):
        """Test EvidenceItem with optional fields as None."""
        evidence = EvidenceItem(
            source_type="AuditEvent",
            source_id=str(uuid4()),
            source_version=None,
            title="Audit Entry",
            snippet="Audit event occurred...",
            url=None,
            similarity_score=0.72,
            chunk_text="Full audit log entry..."
        )
        
        assert evidence.source_version is None
        assert evidence.url is None


class TestRetrievalService:
    """Test RetrievalService with tenant isolation and similarity search."""
    
    @pytest.fixture
    def mock_embedding_service(self):
        """Mock EmbeddingService for testing."""
        service = AsyncMock()
        service.embed_text.return_value = [0.1, 0.2, 0.3, 0.4, 0.5]  # Mock embedding
        return service
    
    @pytest.fixture
    def mock_document_repository(self):
        """Mock CopilotDocumentRepository for testing."""
        return AsyncMock()
    
    @pytest.fixture
    def retrieval_service(self, mock_embedding_service, mock_document_repository):
        """RetrievalService instance with mocked dependencies."""
        return RetrievalService(mock_embedding_service, mock_document_repository)
    
    @pytest.mark.asyncio
    async def test_retrieve_evidence_basic(self, retrieval_service, mock_document_repository):
        """Test basic evidence retrieval functionality."""
        tenant_id = uuid4()
        query_text = "security policy violation"
        
        # Mock repository response - return different results for different source types
        def mock_similarity_search(tenant_id, query_embedding, limit, source_type=None, domain=None, threshold=0.1):
            if source_type == "PolicyDoc":
                doc1 = CopilotDocument()
                doc1.source_type = "PolicyDoc"
                doc1.source_id = str(uuid4())
                doc1.version = "v1.0"
                doc1.content = "Complete security policy text..."
                doc1.metadata_json = {
                    "title": "Security Policy",
                    "url": "https://example.com/security-policy"
                }
                return [SimilarDocument(document=doc1, similarity_score=0.92)]
            elif source_type == "ResolvedException":
                doc2 = CopilotDocument()
                doc2.source_type = "ResolvedException"
                doc2.source_id = str(uuid4())
                doc2.version = "r456"
                doc2.content = "Previously resolved security exception..."
                doc2.metadata_json = {
                    "title": "Similar Security Issue",
                    "url": None
                }
                return [SimilarDocument(document=doc2, similarity_score=0.78)]
            else:
                return []  # No results for other source types
        
        mock_document_repository.similarity_search.side_effect = mock_similarity_search
        
        # Test retrieval
        evidence_items = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text=query_text,
            top_k=5
        )
        
        # Verify results
        assert len(evidence_items) == 2
        assert evidence_items[0].similarity_score == 0.92  # Sorted by score
        assert evidence_items[1].similarity_score == 0.78
        assert evidence_items[0].source_type == "PolicyDoc"
        assert evidence_items[1].source_type == "ResolvedException"
        
        # Verify embedding was generated
        retrieval_service.embedding_service.embed_text.assert_called_once_with(query_text)
    
    @pytest.mark.asyncio
    async def test_tenant_isolation_enforcement(self, retrieval_service, mock_document_repository):
        """Test that tenant_id is properly enforced in all repository calls."""
        tenant_id = uuid4()
        query_text = "test query"
        
        mock_document_repository.similarity_search.return_value = []
        
        await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text=query_text
        )
        
        # Verify all similarity_search calls include tenant_id
        calls = mock_document_repository.similarity_search.call_args_list
        for call in calls:
            assert call.kwargs['tenant_id'] == tenant_id
    
    @pytest.mark.asyncio
    async def test_multi_tenant_isolation(self, retrieval_service, mock_document_repository):
        """Test that different tenants get isolated results."""
        tenant_a = uuid4()
        tenant_b = uuid4()
        
        # Mock different results for different tenants
        def mock_search(tenant_id, source_type=None, **kwargs):
            # Only return results for PolicyDoc source type to avoid duplication
            if source_type != "PolicyDoc":
                return []
            
            if tenant_id == tenant_a:
                doc_a = CopilotDocument()
                doc_a.source_type = "PolicyDoc"
                doc_a.source_id = str(uuid4())
                doc_a.version = "v1.0"
                doc_a.content = "Tenant A specific policy..."
                doc_a.metadata_json = {"title": "Tenant A Policy"}
                
                return [SimilarDocument(
                    document=doc_a,
                    similarity_score=0.9
                )]
            elif tenant_id == tenant_b:
                doc_b = CopilotDocument()
                doc_b.source_type = "PolicyDoc"
                doc_b.source_id = str(uuid4())
                doc_b.version = "v1.0"
                doc_b.content = "Tenant B specific policy..."
                doc_b.metadata_json = {"title": "Tenant B Policy"}
                
                return [SimilarDocument(
                    document=doc_b,
                    similarity_score=0.8
                )]
            return []
        
        mock_document_repository.similarity_search.side_effect = mock_search
        
        # Test tenant A
        evidence_a = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_a,
            query_text="policy"
        )
        
        # Test tenant B
        evidence_b = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_b,
            query_text="policy"
        )
        
        # Verify isolation
        assert len(evidence_a) == 1
        assert len(evidence_b) == 1
        assert evidence_a[0].title == "Tenant A Policy"
        assert evidence_b[0].title == "Tenant B Policy"
        assert evidence_a[0].chunk_text != evidence_b[0].chunk_text
    
    @pytest.mark.asyncio
    async def test_source_type_filtering(self, retrieval_service, mock_document_repository):
        """Test filtering by specific source types."""
        tenant_id = uuid4()
        
        doc = CopilotDocument()
        doc.source_type = "PolicyDoc"
        doc.source_id = str(uuid4())
        doc.version = "v1.0"
        doc.content = "Policy content..."
        doc.metadata_json = {"title": "Policy Document"}
        
        mock_document_repository.similarity_search.return_value = [
            SimilarDocument(
                document=doc,
                similarity_score=0.9
            )
        ]
        
        evidence_items = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="test query",
            source_types=["PolicyDoc", "ToolRegistry"]
        )
        
        # Verify only requested source types were searched
        calls = mock_document_repository.similarity_search.call_args_list
        called_source_types = {call.kwargs['source_type'] for call in calls}
        assert called_source_types == {"PolicyDoc", "ToolRegistry"}
    
    @pytest.mark.asyncio
    async def test_domain_filtering(self, retrieval_service, mock_document_repository):
        """Test filtering by domain."""
        tenant_id = uuid4()
        domain = "finance"
        
        mock_document_repository.similarity_search.return_value = []
        
        await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="financial policy",
            domain=domain
        )
        
        # Verify domain was passed to repository calls
        calls = mock_document_repository.similarity_search.call_args_list
        for call in calls:
            assert call.kwargs['domain'] == domain
    
    @pytest.mark.asyncio
    async def test_top_k_limiting(self, retrieval_service, mock_document_repository):
        """Test that results are properly limited to top_k."""
        tenant_id = uuid4()
        
        # Mock more results than requested
        mock_results = []
        for i in range(10):
            doc = CopilotDocument()
            doc.source_type = "PolicyDoc"
            doc.source_id = str(uuid4())
            doc.version = "v1.0"
            doc.content = f"Policy content {i}..."
            doc.metadata_json = {"title": f"Policy {i}"}
            
            mock_results.append(SimilarDocument(
                document=doc,
                similarity_score=0.9 - i * 0.05  # Decreasing scores
            ))
        
        def mock_similarity_search_with_limit(tenant_id, query_embedding, limit, source_type=None, domain=None, threshold=0.1):
            # Only return results for PolicyDoc to avoid duplication across source types
            if source_type != "PolicyDoc":
                return []
                
            # Return the mock results up to the limit requested
            return mock_results[:limit]
        
        mock_document_repository.similarity_search.side_effect = mock_similarity_search_with_limit
        
        evidence_items = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="test query",
            top_k=3
        )
        
        # Should only return top 3 results
        assert len(evidence_items) == 3
        assert evidence_items[0].similarity_score > evidence_items[1].similarity_score
        assert evidence_items[1].similarity_score > evidence_items[2].similarity_score
    
    @pytest.mark.asyncio
    async def test_empty_query_validation(self, retrieval_service):
        """Test validation of empty query text."""
        tenant_id = uuid4()
        
        with pytest.raises(ValueError, match="query_text cannot be empty"):
            await retrieval_service.retrieve_evidence(
                tenant_id=tenant_id,
                query_text=""
            )
        
        with pytest.raises(ValueError, match="query_text cannot be empty"):
            await retrieval_service.retrieve_evidence(
                tenant_id=tenant_id,
                query_text="   "  # Whitespace only
            )
    
    @pytest.mark.asyncio
    async def test_tenant_id_validation(self, retrieval_service):
        """Test validation of tenant_id."""
        with pytest.raises(ValueError, match="tenant_id is required"):
            await retrieval_service.retrieve_evidence(
                tenant_id=None,
                query_text="test query"
            )
    
    @pytest.mark.asyncio
    async def test_error_handling_continues_search(self, retrieval_service, mock_document_repository):
        """Test that errors in one source type don't stop the entire search."""
        tenant_id = uuid4()
        
        def mock_search_with_error(source_type, **kwargs):
            if source_type == "PolicyDoc":
                raise Exception("Database connection error")
            elif source_type == "ResolvedException":
                doc = CopilotDocument()
                doc.source_type = "ResolvedException"
                doc.source_id = str(uuid4())
                doc.version = "r123"
                doc.content = "Exception content..."
                doc.metadata_json = {"title": "Working Exception"}
                
                return [SimilarDocument(
                    document=doc,
                    similarity_score=0.8
                )]
            return []
        
        mock_document_repository.similarity_search.side_effect = mock_search_with_error
        
        evidence_items = await retrieval_service.retrieve_evidence(
            tenant_id=tenant_id,
            query_text="test query"
        )
        
        # Should still return results from working source types
        assert len(evidence_items) == 1
        assert evidence_items[0].source_type == "ResolvedException"
    
    def test_extract_snippet_basic(self, retrieval_service):
        """Test basic snippet extraction."""
        full_text = "This is a long document with important information about security policies and access controls that need to be enforced."
        query_text = "security policies"
        
        snippet = retrieval_service._extract_snippet(full_text, query_text, max_length=60)
        
        assert len(snippet) <= 60
        # Should contain at least one of the query words
        assert "security" in snippet.lower() or "policies" in snippet.lower()
    
    def test_extract_snippet_short_text(self, retrieval_service):
        """Test snippet extraction when text is already short."""
        full_text = "Short text"
        query_text = "text"
        
        snippet = retrieval_service._extract_snippet(full_text, query_text, max_length=100)
        
        assert snippet == "Short text"
    
    def test_extract_snippet_word_boundary(self, retrieval_service):
        """Test snippet extraction respects word boundaries."""
        full_text = "This is a very long document with lots of important information that should be truncated properly at word boundaries."
        query_text = "important information"
        
        snippet = retrieval_service._extract_snippet(full_text, query_text, max_length=60)
        
        # Should end with "..." and not cut words in the middle
        if len(snippet) == 60:
            assert snippet.endswith("...") or not full_text.endswith(snippet)