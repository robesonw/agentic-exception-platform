"""
Unit tests for SimilarExceptionsFinder service.

Tests the similar exceptions finding functionality including:
- Query text building from exception fields
- Vector similarity retrieval integration
- Outcome summary generation
- Tenant isolation enforcement
- Error handling
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from decimal import Decimal

from src.services.copilot.similarity.similar_exceptions import (
    SimilarExceptionsFinder,
    SimilarException
)
from src.infrastructure.db.models import Exception, ExceptionSeverity, ExceptionStatus
from src.services.copilot.retrieval.retrieval_service import EvidenceItem


class TestSimilarException:
    """Test the SimilarException dataclass."""

    def test_similar_exception_creation(self):
        """Test creating a SimilarException with all fields."""
        similar = SimilarException(
            exception_id="EX-2024-5678",
            similarity_score=0.85,
            outcome_summary="Resolved by updating customer data",
            closed_at="2024-12-20T10:30:00Z",
            link_url="/exceptions/EX-2024-5678"
        )
        
        assert similar.exception_id == "EX-2024-5678"
        assert similar.similarity_score == 0.85
        assert similar.outcome_summary == "Resolved by updating customer data"
        assert similar.closed_at == "2024-12-20T10:30:00Z"
        assert similar.link_url == "/exceptions/EX-2024-5678"

    def test_similar_exception_optional_fields(self):
        """Test creating a SimilarException with minimal fields."""
        similar = SimilarException(
            exception_id="EX-2024-9999",
            similarity_score=0.92,
            outcome_summary="Issue auto-resolved"
        )
        
        assert similar.exception_id == "EX-2024-9999"
        assert similar.similarity_score == 0.92
        assert similar.outcome_summary == "Issue auto-resolved"
        assert similar.closed_at is None
        assert similar.link_url is None


class TestSimilarExceptionsFinder:
    """Test the SimilarExceptionsFinder service."""

    @pytest.fixture
    def mock_exception_repository(self):
        """Create a mock exception repository."""
        return AsyncMock()

    @pytest.fixture
    def mock_retrieval_service(self):
        """Create a mock retrieval service."""
        return AsyncMock()

    @pytest.fixture
    def finder(self, mock_exception_repository, mock_retrieval_service):
        """Create a SimilarExceptionsFinder with mocked dependencies."""
        return SimilarExceptionsFinder(mock_exception_repository, mock_retrieval_service)

    @pytest.fixture
    def sample_exception(self):
        """Create a sample exception for testing."""
        exception = MagicMock()
        exception.exception_id = "EX-2024-1234"
        exception.tenant_id = "tenant-123"
        exception.domain = "finance"
        exception.type = "payment_failed"
        exception.severity = ExceptionSeverity.HIGH
        exception.status = ExceptionStatus.OPEN
        exception.source_system = "PaymentGateway"
        exception.entity = "customer-456"
        exception.amount = Decimal("1500.00")
        return exception

    async def test_find_similar_basic_functionality(self, finder, mock_exception_repository, 
                                                  mock_retrieval_service, sample_exception):
        """Test basic similar exceptions finding functionality."""
        # Setup mocks
        mock_exception_repository.get_exception.return_value = sample_exception
        
        mock_evidence = [
            EvidenceItem(
                source_type="resolved_exception",
                source_id="EX-2024-5678",
                source_version="2024-12-20T10:30:00Z",
                title="Payment Failed - Resolved",
                snippet="Payment failed due to insufficient funds. Resolved by contacting customer and updating payment method.",
                url="/exceptions/EX-2024-5678",
                similarity_score=0.89,
                chunk_text="Full text of resolved exception..."
            ),
            EvidenceItem(
                source_type="resolved_exception",
                source_id="EX-2024-9012",
                source_version="2024-12-19T15:45:00Z",
                title="Payment Processing Error",
                snippet="Gateway timeout error. Resolved by retry mechanism.",
                url="/exceptions/EX-2024-9012",
                similarity_score=0.76,
                chunk_text="Full text of another resolved exception..."
            )
        ]
        mock_retrieval_service.retrieve_evidence.return_value = mock_evidence

        # Execute
        result = await finder.find_similar(
            tenant_id="tenant-123",
            exception_id="EX-2024-1234",
            top_n=5
        )

        # Verify calls
        mock_exception_repository.get_exception.assert_called_once_with("tenant-123", "EX-2024-1234")
        mock_retrieval_service.retrieve_evidence.assert_called_once_with(
            tenant_id="tenant-123",
            query_text="Exception type: payment_failed Domain: finance Source system: PaymentGateway Entity: customer-456 Severity: high Amount: 1500.00",
            domain="finance",
            source_types=["resolved_exception"],
            top_k=5
        )

        # Verify results
        assert len(result) == 2
        
        first_result = result[0]
        assert first_result.exception_id == "EX-2024-5678"
        assert first_result.similarity_score == 0.89
        assert "Payment failed due to insufficient funds" in first_result.outcome_summary
        assert first_result.closed_at == "2024-12-20T10:30:00Z"
        assert first_result.link_url == "/exceptions/EX-2024-5678"
        
        second_result = result[1]
        assert second_result.exception_id == "EX-2024-9012"
        assert second_result.similarity_score == 0.76
        assert "Gateway timeout error" in second_result.outcome_summary

    async def test_tenant_isolation_enforcement(self, finder, mock_exception_repository, 
                                              mock_retrieval_service, sample_exception):
        """Test that tenant isolation is properly enforced."""
        mock_exception_repository.get_exception.return_value = sample_exception
        mock_retrieval_service.retrieve_evidence.return_value = []

        # Test with different tenant_id
        await finder.find_similar(
            tenant_id="tenant-456",
            exception_id="EX-2024-1234",
            top_n=3
        )

        # Verify tenant_id is passed correctly to all services
        mock_exception_repository.get_exception.assert_called_once_with("tenant-456", "EX-2024-1234")
        mock_retrieval_service.retrieve_evidence.assert_called_once()
        call_args = mock_retrieval_service.retrieve_evidence.call_args
        assert call_args.kwargs['tenant_id'] == "tenant-456"

    async def test_exception_not_found(self, finder, mock_exception_repository, mock_retrieval_service):
        """Test behavior when exception is not found."""
        mock_exception_repository.get_exception.return_value = None

        with pytest.raises(ValueError, match="Exception EX-2024-9999 not found"):
            await finder.find_similar(
                tenant_id="tenant-123",
                exception_id="EX-2024-9999",
                top_n=5
            )

        mock_exception_repository.get_exception.assert_called_once_with("tenant-123", "EX-2024-9999")
        mock_retrieval_service.retrieve_evidence.assert_not_called()

    async def test_input_validation(self, finder):
        """Test input validation for find_similar method."""
        # Test empty tenant_id
        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            await finder.find_similar(tenant_id="", exception_id="EX-123", top_n=5)

        with pytest.raises(ValueError, match="tenant_id cannot be empty"):
            await finder.find_similar(tenant_id="   ", exception_id="EX-123", top_n=5)

        # Test empty exception_id
        with pytest.raises(ValueError, match="exception_id cannot be empty"):
            await finder.find_similar(tenant_id="tenant-123", exception_id="", top_n=5)

        with pytest.raises(ValueError, match="exception_id cannot be empty"):
            await finder.find_similar(tenant_id="tenant-123", exception_id="   ", top_n=5)

        # Test invalid top_n
        with pytest.raises(ValueError, match="top_n must be greater than 0"):
            await finder.find_similar(tenant_id="tenant-123", exception_id="EX-123", top_n=0)

        with pytest.raises(ValueError, match="top_n must be greater than 0"):
            await finder.find_similar(tenant_id="tenant-123", exception_id="EX-123", top_n=-1)

    def test_build_query_text_comprehensive(self, finder):
        """Test building query text from exception with all fields."""
        exception = MagicMock()
        exception.type = "data_validation_error"
        exception.domain = "healthcare"
        exception.source_system = "HealthRecords"
        exception.entity = "patient-789"
        exception.severity = ExceptionSeverity.MEDIUM
        exception.amount = Decimal("2500.50")

        query_text = finder._build_query_text(exception)

        expected_parts = [
            "Exception type: data_validation_error",
            "Domain: healthcare",
            "Source system: HealthRecords",
            "Entity: patient-789",
            "Severity: medium",
            "Amount: 2500.50"
        ]

        for part in expected_parts:
            assert part in query_text

    def test_build_query_text_minimal(self, finder):
        """Test building query text from exception with minimal fields."""
        exception = MagicMock()
        exception.type = "connection_timeout"
        exception.domain = "trading"
        exception.source_system = None
        exception.entity = None
        exception.severity = None
        exception.amount = None

        query_text = finder._build_query_text(exception)

        assert "Exception type: connection_timeout" in query_text
        assert "Domain: trading" in query_text
        assert query_text.strip()  # Should not be empty

    def test_build_query_text_empty_exception(self, finder):
        """Test building query text from exception with no meaningful fields."""
        exception = MagicMock()
        exception.type = None
        exception.domain = None
        exception.source_system = None
        exception.entity = None
        exception.severity = None
        exception.amount = None

        query_text = finder._build_query_text(exception)

        # Should fall back to default text
        assert "Exception in unknown domain" in query_text

    def test_create_outcome_summary_short_text(self, finder):
        """Test outcome summary creation for short snippets."""
        short_snippet = "Payment processed successfully"
        summary = finder._create_outcome_summary(short_snippet)
        assert summary == "Payment processed successfully"

    def test_create_outcome_summary_long_text(self, finder):
        """Test outcome summary creation for long snippets."""
        long_snippet = (
            "Payment processing failed due to insufficient funds in the customer account. "
            "After contacting the customer service team, we discovered that the customer had "
            "recently made a large transaction that wasn't reflected in our system due to "
            "a synchronization delay. The issue was resolved by updating the account balance "
            "and reprocessing the payment transaction through the backup gateway."
        )
        
        summary = finder._create_outcome_summary(long_snippet)
        
        # Should be truncated but end properly
        assert len(summary) <= 150
        # Since it's a long snippet, it should use sentence boundary (first sentence)
        assert summary == "Payment processing failed due to insufficient funds in the customer account."

    def test_create_outcome_summary_sentence_boundary(self, finder):
        """Test outcome summary respects sentence boundaries."""
        snippet_with_sentences = (
            "Payment failed due to timeout. Customer was notified automatically. "
            "Issue resolved by retry mechanism."
        )
        
        summary = finder._create_outcome_summary(snippet_with_sentences)
        
        # Since this text is under 150 chars, it should be returned as-is
        assert summary == snippet_with_sentences

    def test_create_outcome_summary_sentence_boundary_long(self, finder):
        """Test outcome summary respects sentence boundaries with long text."""
        long_snippet_with_sentences = (
            "Payment processing failed due to insufficient funds in customer account. "
            "After extensive investigation by our customer service team, we discovered "
            "that the customer had recently made a large transaction that wasn't reflected "
            "in our internal systems due to a synchronization delay between our primary "
            "and backup payment processing services."
        )
        
        summary = finder._create_outcome_summary(long_snippet_with_sentences)
        
        # Should use first sentence when it's reasonable length
        assert summary == "Payment processing failed due to insufficient funds in customer account."

    def test_create_outcome_summary_empty(self, finder):
        """Test outcome summary creation for empty snippet."""
        summary = finder._create_outcome_summary("")
        assert summary == "Resolution details not available"

        summary = finder._create_outcome_summary(None)
        assert summary == "Resolution details not available"

    async def test_error_handling_retrieval_failure(self, finder, mock_exception_repository, 
                                                   mock_retrieval_service, sample_exception):
        """Test error handling when retrieval service fails."""
        mock_exception_repository.get_exception.return_value = sample_exception
        mock_retrieval_service.retrieve_evidence.side_effect = RuntimeError("Vector search failed")

        with pytest.raises(RuntimeError, match="Vector search failed"):
            await finder.find_similar(
                tenant_id="tenant-123",
                exception_id="EX-2024-1234",
                top_n=5
            )

    async def test_empty_results(self, finder, mock_exception_repository, 
                                mock_retrieval_service, sample_exception):
        """Test handling when no similar exceptions are found."""
        mock_exception_repository.get_exception.return_value = sample_exception
        mock_retrieval_service.retrieve_evidence.return_value = []

        result = await finder.find_similar(
            tenant_id="tenant-123",
            exception_id="EX-2024-1234",
            top_n=5
        )

        assert result == []

    async def test_domain_filtering(self, finder, mock_exception_repository, 
                                  mock_retrieval_service, sample_exception):
        """Test that domain filtering is applied correctly."""
        mock_exception_repository.get_exception.return_value = sample_exception
        mock_retrieval_service.retrieve_evidence.return_value = []

        await finder.find_similar(
            tenant_id="tenant-123",
            exception_id="EX-2024-1234",
            top_n=5
        )

        # Verify domain parameter is passed to retrieval service
        call_args = mock_retrieval_service.retrieve_evidence.call_args
        assert call_args.kwargs['domain'] == "finance"
        assert call_args.kwargs['source_types'] == ["resolved_exception"]