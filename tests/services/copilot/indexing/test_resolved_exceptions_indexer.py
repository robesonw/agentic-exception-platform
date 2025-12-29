"""
Tests for ResolvedExceptionsIndexer (Phase 13 P13-5).

Tests resolved exceptions indexing with incremental watermarking,
tenant isolation, and resolution information extraction.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

from src.services.copilot.indexing.resolved_exceptions_indexer import (
    ResolvedExceptionsIndexer,
    ResolvedExceptionDoc,
)
from src.services.copilot.indexing.types import IndexingResult
from src.infrastructure.db.models import (
    Exception,
    ExceptionEvent,
    ExceptionStatus,
    ExceptionSeverity,
    IndexingState,
    CopilotDocumentSourceType,
    ActorType,
)
from src.services.copilot.chunking_service import DocumentChunk


class TestResolvedExceptionDoc:
    """Test the ResolvedExceptionDoc data class."""

    def test_resolved_exception_doc_creation(self):
        """Test creating a resolved exception doc."""
        closed_at = datetime.now(timezone.utc)
        doc = ResolvedExceptionDoc(
            exception_id="EX-2025-001",
            tenant_id="TENANT_001",
            domain="finance",
            type="payment_mismatch",
            severity="high",
            source_system="Murex",
            entity="COUNTERPARTY_123",
            amount=1000000.50,
            owner="agent_001",
            resolution_summary="Reconciled with manual adjustment",
            resolution_details="Found root cause in currency conversion logic. Applied manual fix.",
            status="resolved",
            closed_at=closed_at,
            metadata={"sla_deadline": "2025-01-01T00:00:00Z"},
        )

        assert doc.exception_id == "EX-2025-001"
        assert doc.tenant_id == "TENANT_001" 
        assert doc.domain == "finance"
        assert doc.severity == "high"
        assert doc.amount == 1000000.50
        assert doc.resolution_summary == "Reconciled with manual adjustment"
        assert doc.closed_at == closed_at

    def test_to_source_document(self):
        """Test conversion to SourceDocument."""
        closed_at = datetime(2025, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        doc = ResolvedExceptionDoc(
            exception_id="EX-2025-002",
            tenant_id="TENANT_001",
            domain="healthcare",
            type="claim_processing_error",
            severity="medium",
            source_system="ClaimsApp",
            entity="PATIENT_456",
            amount=5000.0,
            owner="user_001",
            resolution_summary="Claim reprocessed successfully",
            resolution_details="Updated patient demographics and resubmitted claim",
            status="resolved",
            closed_at=closed_at,
        )

        source_doc = doc.to_source_document()

        assert source_doc.source_id == "EX-2025-002"
        assert source_doc.source_type == CopilotDocumentSourceType.RESOLVED_EXCEPTION
        assert source_doc.metadata["tenant_id"] == "TENANT_001"
        
        # Check content structure
        assert "Exception Details:" in source_doc.content
        assert "EX-2025-002" in source_doc.content
        assert "claim_processing_error" in source_doc.content
        assert "Resolution:" in source_doc.content
        assert "Claim reprocessed successfully" in source_doc.content
        assert "Updated patient demographics" in source_doc.content
        
        # Check metadata
        metadata = source_doc.metadata
        assert metadata["exception_id"] == "EX-2025-002"
        assert metadata["domain"] == "healthcare"
        assert metadata["severity"] == "medium"
        assert metadata["status"] == "resolved"
        assert metadata["closed_at"] == closed_at.isoformat()


class TestResolvedExceptionsIndexer:
    """Test the ResolvedExceptionsIndexer class."""

    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        return AsyncMock()

    @pytest.fixture
    def mock_embedding_service(self):
        """Mock embedding service."""
        service = AsyncMock()
        service.generate_embeddings.return_value = [[0.1, 0.2, 0.3]]  # Mock embedding
        return service

    @pytest.fixture
    def mock_chunking_service(self):
        """Mock chunking service."""
        # Create a simple Mock object without spec to avoid AsyncMock behavior
        service = Mock()
        
        # Define a simple side effect function
        def mock_chunk_document(document):
            return [
                DocumentChunk(
                    chunk_id=f"{document.source_id}-chunk-0",
                    chunk_index=0,
                    content="Test chunk content",
                    source_type=document.source_type,
                    source_id=document.source_id,
                    total_chunks=1,
                )
            ]
        
        # Assign the side effect directly
        service.chunk_document = Mock(side_effect=mock_chunk_document)
        return service

    @pytest.fixture
    def mock_document_repository(self):
        """Mock document repository."""
        repo = AsyncMock()
        repo.upsert_documents_batch.return_value = 1  # Mock 1 document upserted
        repo.delete_by_source.return_value = 1  # Mock 1 document deleted
        return repo

    @pytest.fixture
    def resolved_exceptions_indexer(
        self,
        mock_db_session,
        mock_embedding_service,
        mock_chunking_service,
        mock_document_repository,
    ):
        """Create ResolvedExceptionsIndexer with mocked dependencies."""
        return ResolvedExceptionsIndexer(
            db_session=mock_db_session,
            embedding_service=mock_embedding_service,
            chunking_service=mock_chunking_service,
            document_repository=mock_document_repository,
        )

    @pytest.fixture
    def sample_resolved_exceptions(self):
        """Sample resolved exception docs for testing."""
        closed_at1 = datetime(2025, 1, 15, 10, 0, 0, tzinfo=timezone.utc)
        closed_at2 = datetime(2025, 1, 15, 11, 0, 0, tzinfo=timezone.utc)
        
        return [
            ResolvedExceptionDoc(
                exception_id="EX-2025-001",
                tenant_id="TENANT_001",
                domain="finance",
                type="payment_mismatch",
                severity="high",
                source_system="Murex",
                entity="COUNTERPARTY_123",
                amount=1000000.0,
                owner="agent_001",
                resolution_summary="Payment reconciled",
                resolution_details="Found duplicate payment entry and corrected",
                status="resolved",
                closed_at=closed_at1,
            ),
            ResolvedExceptionDoc(
                exception_id="EX-2025-002", 
                tenant_id="TENANT_001",
                domain="healthcare",
                type="claim_error",
                severity="medium",
                source_system="ClaimsApp",
                entity="PATIENT_456",
                amount=5000.0,
                owner="user_001",
                resolution_summary="Claim reprocessed",
                resolution_details="Updated patient data and resubmitted",
                status="resolved",
                closed_at=closed_at2,
            ),
        ]

    def test_source_type(self, resolved_exceptions_indexer):
        """Test source type property."""
        assert resolved_exceptions_indexer.source_type == CopilotDocumentSourceType.RESOLVED_EXCEPTION

    def test_supports_tenant_valid(self, resolved_exceptions_indexer):
        """Test tenant validation with valid tenant IDs."""
        valid_tenants = ["TENANT_001", "tenant-123", "TENANT_ABC_123"]
        
        for tenant_id in valid_tenants:
            assert resolved_exceptions_indexer.supports_tenant(tenant_id)

    def test_supports_tenant_invalid(self, resolved_exceptions_indexer):
        """Test tenant validation with invalid tenant IDs."""
        invalid_tenants = ["", None, "tenant with spaces", "tenant@invalid"]
        
        for tenant_id in invalid_tenants:
            assert not resolved_exceptions_indexer.supports_tenant(tenant_id)

    @pytest.mark.asyncio
    async def test_index_resolved_exceptions_success(
        self,
        sample_resolved_exceptions,
        mock_document_repository,
        mock_db_session,
        mock_embedding_service,
    ):
        """Test successful indexing of resolved exceptions."""
        # Create a properly working mock for the chunking service
        mock_chunking_service = Mock()
        
        def create_chunk(document):
            return [
                DocumentChunk(
                    chunk_id=f"{document.source_id}-chunk-0",
                    chunk_index=0,
                    content="Test chunk content",
                    source_type=document.source_type,
                    source_id=document.source_id,
                    total_chunks=1,
                )
            ]
        
        mock_chunking_service.chunk_document = Mock(side_effect=create_chunk)
        
        # Create indexer manually with our mock
        indexer = ResolvedExceptionsIndexer(
            db_session=mock_db_session,
            embedding_service=mock_embedding_service,
            chunking_service=mock_chunking_service,
            document_repository=mock_document_repository,
        )
        
        result = await indexer.index_resolved_exceptions(
            tenant_id="TENANT_001",
            resolved_exceptions=sample_resolved_exceptions,
        )

        assert result.success
        assert result.tenant_id == "TENANT_001"
        assert result.chunks_processed == 2  # 2 exceptions, 1 chunk each
        assert result.chunks_indexed == 1  # Mock returns 1 for batch upsert
        assert result.metadata["total_exceptions"] == 2

        # Verify chunking was called for each exception
        assert mock_chunking_service.chunk_document.call_count == 2
        
        # Verify batch upsert was called
        mock_document_repository.upsert_documents_batch.assert_called_once()
        
    @pytest.mark.asyncio
    async def test_index_resolved_exceptions_empty_list(
        self,
        resolved_exceptions_indexer,
        mock_document_repository,
    ):
        """Test indexing with empty exception list."""
        result = await resolved_exceptions_indexer.index_resolved_exceptions(
            tenant_id="TENANT_001",
            resolved_exceptions=[],
        )

        assert result.success
        assert result.chunks_processed == 0
        assert result.chunks_indexed == 0
        assert result.metadata["total_exceptions"] == 0

        # Repository should not be called for empty list
        mock_document_repository.upsert_documents_batch.assert_not_called()

    @pytest.mark.asyncio
    async def test_index_resolved_exceptions_tenant_isolation(
        self,
        resolved_exceptions_indexer,
        sample_resolved_exceptions,
        mock_document_repository,
    ):
        """Test that tenant ID is properly enforced."""
        # Test with different tenant
        result1 = await resolved_exceptions_indexer.index_resolved_exceptions(
            tenant_id="TENANT_001",
            resolved_exceptions=sample_resolved_exceptions,
        )
        
        result2 = await resolved_exceptions_indexer.index_resolved_exceptions(
            tenant_id="TENANT_002",
            resolved_exceptions=sample_resolved_exceptions,
        )

        # Both should succeed but be isolated
        assert result1.success and result1.tenant_id == "TENANT_001"
        assert result2.success and result2.tenant_id == "TENANT_002"
        
        # Verify repository was called with correct tenant IDs
        calls = mock_document_repository.upsert_documents_batch.call_args_list
        assert len(calls) == 2
        assert calls[0][1]["tenant_id"] == "TENANT_001"  # keyword args
        assert calls[1][1]["tenant_id"] == "TENANT_002"

    @pytest.mark.asyncio 
    async def test_invalid_tenant_raises_error(self, resolved_exceptions_indexer, sample_resolved_exceptions):
        """Test that invalid tenant ID returns failure."""
        # Test with empty tenant ID
        result = await resolved_exceptions_indexer.index_resolved_exceptions(
            tenant_id="",
            resolved_exceptions=sample_resolved_exceptions,
        )
        assert not result.success
        assert result.error_message and "Tenant ID is required" in result.error_message
        
        # Test with None tenant ID
        result = await resolved_exceptions_indexer.index_resolved_exceptions(
            tenant_id=None,
            resolved_exceptions=sample_resolved_exceptions,
        )
        assert not result.success
        assert result.error_message and "Tenant ID is required" in result.error_message

    @pytest.mark.asyncio
    async def test_index_resolved_exceptions_with_chunking_failure(
        self,
        resolved_exceptions_indexer,
        sample_resolved_exceptions,
        mock_chunking_service,
    ):
        """Test handling of chunking failures."""
        # Mock chunking service to return empty chunks for first exception
        def mock_chunk_with_failure(document):
            if "EX-2025-001" in document.source_id:
                return []  # No chunks for first exception
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

        result = await resolved_exceptions_indexer.index_resolved_exceptions(
            tenant_id="TENANT_001",
            resolved_exceptions=sample_resolved_exceptions,
        )

        assert result.success
        # Should process both exceptions, but only get chunks from one
        assert result.chunks_processed == 1  # Only EX-2025-002 produces chunks
        assert result.chunks_indexed >= 1  # At least 1 chunk processed

    @pytest.mark.asyncio
    async def test_incremental_indexing_with_watermark(
        self,
        resolved_exceptions_indexer,
        mock_db_session,
        sample_resolved_exceptions,
    ):
        """Test incremental indexing with watermark tracking."""
        # Mock existing watermark
        mock_state = MagicMock()
        mock_state.last_indexed_at = datetime(2025, 1, 14, tzinfo=timezone.utc)
        
        # Mock database queries
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_state
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = []  # No new exceptions

        result = await resolved_exceptions_indexer.index_incremental("TENANT_001")

        assert result.success
        assert result.chunks_processed == 0  # No new exceptions
        
        # Should have queried for watermark
        assert mock_db_session.execute.call_count >= 1

    @pytest.mark.asyncio
    async def test_incremental_indexing_force_rebuild(
        self,
        resolved_exceptions_indexer,
        mock_db_session,
        sample_resolved_exceptions,
    ):
        """Test force rebuild ignores watermark."""
        # Mock database to return sample exceptions
        mock_exception1 = MagicMock()
        mock_exception1.exception_id = "EX-2025-001"
        mock_exception1.tenant_id = "TENANT_001"
        mock_exception1.domain = "finance"
        mock_exception1.type = "payment_error"
        mock_exception1.severity = ExceptionSeverity.HIGH
        mock_exception1.status = ExceptionStatus.RESOLVED
        mock_exception1.source_system = "Murex"
        mock_exception1.entity = "ENTITY_123"
        mock_exception1.amount = 1000.0
        mock_exception1.owner = "agent_001"
        mock_exception1.sla_deadline = None
        mock_exception1.current_playbook_id = None
        mock_exception1.current_step = None

        # Mock resolution event
        mock_event = MagicMock()
        mock_event.event_type = "ExceptionResolved"
        mock_event.payload = {
            "resolution_summary": "Test resolution",
            "resolution_details": "Test details"
        }
        mock_event.created_at = datetime.now(timezone.utc)

        # Configure mock returns
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_exception1]
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_event

        result = await resolved_exceptions_indexer.index_incremental(
            tenant_id="TENANT_001",
            force_rebuild=True
        )

        assert result.success
        # Should have processed the exception despite any existing watermark

    @pytest.mark.asyncio
    async def test_remove_document(
        self,
        resolved_exceptions_indexer,
        mock_document_repository,
    ):
        """Test document removal."""
        # Mock successful removal
        mock_document_repository.delete_by_source.return_value = 1

        result = await resolved_exceptions_indexer.remove_document(
            tenant_id="TENANT_001",
            source_id="EX-2025-001",
        )

        assert result is True
        mock_document_repository.delete_by_source.assert_called_once_with(
            tenant_id="TENANT_001",
            source_type=CopilotDocumentSourceType.RESOLVED_EXCEPTION,
            source_id="EX-2025-001",
        )

    @pytest.mark.asyncio
    async def test_remove_nonexistent_document(
        self,
        resolved_exceptions_indexer,
        mock_document_repository,
    ):
        """Test removal of nonexistent document."""
        # Mock no documents removed
        mock_document_repository.delete_by_source.return_value = 0

        result = await resolved_exceptions_indexer.remove_document(
            tenant_id="TENANT_001",
            source_id="NONEXISTENT",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_resolution_info_from_event(self, resolved_exceptions_indexer, mock_db_session):
        """Test extraction of resolution info from events."""
        # Mock resolution event
        mock_event = MagicMock()
        mock_event.event_type = "ExceptionResolved"
        mock_event.payload = {
            "resolution_summary": "Payment reconciled successfully",
            "resolution_details": "Found duplicate entry in payment system",
        }
        mock_event.created_at = datetime.now(timezone.utc)

        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_event

        # Access private method for testing
        resolution_info = await resolved_exceptions_indexer._get_resolution_info(
            "EX-2025-001", 
            "TENANT_001"
        )

        assert resolution_info is not None
        assert resolution_info["summary"] == "Payment reconciled successfully"
        assert resolution_info["details"] == "Found duplicate entry in payment system"
        assert resolution_info["closed_at"] == mock_event.created_at

    @pytest.mark.asyncio
    async def test_get_resolution_info_fallback(self, resolved_exceptions_indexer, mock_db_session):
        """Test fallback resolution info extraction."""
        # Mock event without specific resolution event type
        mock_event = MagicMock()
        mock_event.event_type = "StatusChanged"
        mock_event.payload = {
            "outcome": "Manual fix applied",
            "notes": "Corrected currency conversion error",
        }
        mock_event.created_at = datetime.now(timezone.utc)

        # Configure mock to return no specific resolution events first, then fallback event
        mock_db_session.execute.return_value.scalars.return_value.first.side_effect = [None]
        mock_db_session.execute.return_value.scalars.return_value.all.return_value = [mock_event]

        resolution_info = await resolved_exceptions_indexer._get_resolution_info(
            "EX-2025-001",
            "TENANT_001"
        )

        assert resolution_info is not None
        assert "Manual fix applied" in resolution_info["summary"]
        assert "Corrected currency conversion error" in resolution_info["details"]

    @pytest.mark.asyncio
    async def test_watermark_management(self, resolved_exceptions_indexer, mock_db_session):
        """Test watermark creation and updates."""
        # Test creating new watermark
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = None
        
        test_timestamp = datetime.now(timezone.utc)
        await resolved_exceptions_indexer._update_indexing_watermark("TENANT_001", test_timestamp)
        
        # Should add new IndexingState to session
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()

        # Test updating existing watermark
        mock_db_session.reset_mock()
        mock_state = MagicMock()
        mock_db_session.execute.return_value.scalars.return_value.first.return_value = mock_state
        
        new_timestamp = datetime.now(timezone.utc)
        await resolved_exceptions_indexer._update_indexing_watermark("TENANT_001", new_timestamp)
        
        # Should update existing state
        assert mock_state.last_indexed_at == new_timestamp
        mock_db_session.commit.assert_called_once()
        mock_db_session.add.assert_not_called()  # No new object added