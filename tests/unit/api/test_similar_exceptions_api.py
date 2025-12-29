"""
Unit tests for similar exceptions API endpoint.

Tests GET /api/copilot/similar/{exception_id} endpoint functionality including:
- Basic endpoint functionality
- Parameter validation
- Response format validation  
- Tenant isolation
- Error handling
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from src.api.routes.router_copilot import router, SimilarExceptionsListResponse, SimilarExceptionResponse
from src.services.copilot.similarity.similar_exceptions import SimilarException


class TestSimilarExceptionsAPI:
    """Test the similar exceptions API endpoint."""

    @pytest.fixture
    def mock_finder(self):
        """Create a mock SimilarExceptionsFinder."""
        return AsyncMock()

    @pytest.fixture
    def sample_similar_exceptions(self):
        """Create sample similar exceptions for testing."""
        return [
            SimilarException(
                exception_id="EX-2024-5678",
                similarity_score=0.89,
                outcome_summary="Payment failed due to insufficient funds. Resolved by updating payment method.",
                closed_at="2024-12-20T10:30:00Z",
                link_url="/exceptions/EX-2024-5678"
            ),
            SimilarException(
                exception_id="EX-2024-9012",
                similarity_score=0.76,
                outcome_summary="Gateway timeout error. Resolved by retry mechanism.",
                closed_at="2024-12-19T15:45:00Z",
                link_url="/exceptions/EX-2024-9012"
            )
        ]

    async def test_get_similar_exceptions_success(self, mock_finder, sample_similar_exceptions):
        """Test successful similar exceptions retrieval."""
        # Mock the finder
        with patch('src.api.routes.router_copilot.SimilarExceptionsFinder') as MockFinder, \
             patch('src.api.routes.router_copilot.get_db_session_context') as mock_db_context, \
             patch('src.api.routes.router_copilot.EmbeddingService') as MockEmbeddingService, \
             patch('src.api.routes.router_copilot.CopilotDocumentRepository') as MockDocRepo, \
             patch('src.api.routes.router_copilot.RetrievalService') as MockRetrievalService, \
             patch('src.api.routes.router_copilot.ExceptionRepository') as MockExceptionRepo:
            
            # Setup mocks
            mock_session = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_session
            
            mock_finder_instance = AsyncMock()
            MockFinder.return_value = mock_finder_instance
            mock_finder_instance.find_similar.return_value = sample_similar_exceptions

            # Import the endpoint function for testing
            from src.api.routes.router_copilot import get_similar_exceptions

            # Execute
            result = await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123",
                top_n=5
            )

            # Verify
            assert isinstance(result, SimilarExceptionsListResponse)
            assert result.total_count == 2
            assert len(result.similar_exceptions) == 2
            
            first_result = result.similar_exceptions[0]
            assert first_result.exception_id == "EX-2024-5678"
            assert first_result.similarity_score == 0.89
            assert "insufficient funds" in first_result.outcome_summary
            assert first_result.closed_at == "2024-12-20T10:30:00Z"
            
            # Verify finder was called correctly
            mock_finder_instance.find_similar.assert_called_once_with(
                tenant_id="tenant-123",
                exception_id="EX-2024-1234",
                top_n=5
            )

    async def test_get_similar_exceptions_empty_exception_id(self):
        """Test validation error for empty exception_id."""
        from src.api.routes.router_copilot import get_similar_exceptions

        with pytest.raises(HTTPException) as exc_info:
            await get_similar_exceptions(
                exception_id="",
                tenant_id="tenant-123",
                top_n=5
            )
        
        assert exc_info.value.status_code == 400
        assert "exception_id cannot be empty" in exc_info.value.detail

    async def test_get_similar_exceptions_whitespace_exception_id(self):
        """Test validation error for whitespace-only exception_id."""
        from src.api.routes.router_copilot import get_similar_exceptions

        with pytest.raises(HTTPException) as exc_info:
            await get_similar_exceptions(
                exception_id="   ",
                tenant_id="tenant-123",
                top_n=5
            )
        
        assert exc_info.value.status_code == 400
        assert "exception_id cannot be empty" in exc_info.value.detail

    async def test_get_similar_exceptions_empty_tenant_id(self):
        """Test validation error for empty tenant_id."""
        from src.api.routes.router_copilot import get_similar_exceptions

        with pytest.raises(HTTPException) as exc_info:
            await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="",
                top_n=5
            )
        
        assert exc_info.value.status_code == 400
        assert "tenant_id cannot be empty" in exc_info.value.detail

    async def test_get_similar_exceptions_invalid_top_n_zero(self):
        """Test validation error for top_n = 0."""
        from src.api.routes.router_copilot import get_similar_exceptions

        with pytest.raises(HTTPException) as exc_info:
            await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123",
                top_n=0
            )
        
        assert exc_info.value.status_code == 400
        assert "top_n must be between 1 and 20" in exc_info.value.detail

    async def test_get_similar_exceptions_invalid_top_n_negative(self):
        """Test validation error for negative top_n."""
        from src.api.routes.router_copilot import get_similar_exceptions

        with pytest.raises(HTTPException) as exc_info:
            await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123",
                top_n=-1
            )
        
        assert exc_info.value.status_code == 400
        assert "top_n must be between 1 and 20" in exc_info.value.detail

    async def test_get_similar_exceptions_invalid_top_n_too_large(self):
        """Test validation error for top_n > 20."""
        from src.api.routes.router_copilot import get_similar_exceptions

        with pytest.raises(HTTPException) as exc_info:
            await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123",
                top_n=25
            )
        
        assert exc_info.value.status_code == 400
        assert "top_n must be between 1 and 20" in exc_info.value.detail

    async def test_get_similar_exceptions_value_error_from_finder(self):
        """Test handling of ValueError from SimilarExceptionsFinder."""
        with patch('src.api.routes.router_copilot.SimilarExceptionsFinder') as MockFinder, \
             patch('src.api.routes.router_copilot.get_db_session_context') as mock_db_context, \
             patch('src.api.routes.router_copilot.EmbeddingService'), \
             patch('src.api.routes.router_copilot.CopilotDocumentRepository'), \
             patch('src.api.routes.router_copilot.RetrievalService'), \
             patch('src.api.routes.router_copilot.ExceptionRepository'):
            
            # Setup mocks
            mock_session = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_session
            
            mock_finder_instance = AsyncMock()
            MockFinder.return_value = mock_finder_instance
            mock_finder_instance.find_similar.side_effect = ValueError("Exception EX-9999 not found for tenant tenant-123")

            from src.api.routes.router_copilot import get_similar_exceptions

            with pytest.raises(HTTPException) as exc_info:
                await get_similar_exceptions(
                    exception_id="EX-9999",
                    tenant_id="tenant-123",
                    top_n=5
                )
            
            assert exc_info.value.status_code == 400
            assert "Exception EX-9999 not found" in exc_info.value.detail

    async def test_get_similar_exceptions_internal_error(self):
        """Test handling of internal errors."""
        with patch('src.api.routes.router_copilot.SimilarExceptionsFinder') as MockFinder, \
             patch('src.api.routes.router_copilot.get_db_session_context') as mock_db_context, \
             patch('src.api.routes.router_copilot.EmbeddingService'), \
             patch('src.api.routes.router_copilot.CopilotDocumentRepository'), \
             patch('src.api.routes.router_copilot.RetrievalService'), \
             patch('src.api.routes.router_copilot.ExceptionRepository'):
            
            # Setup mocks
            mock_session = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_session
            
            mock_finder_instance = AsyncMock()
            MockFinder.return_value = mock_finder_instance
            mock_finder_instance.find_similar.side_effect = Exception("Database connection failed")

            from src.api.routes.router_copilot import get_similar_exceptions

            with pytest.raises(HTTPException) as exc_info:
                await get_similar_exceptions(
                    exception_id="EX-2024-1234",
                    tenant_id="tenant-123",
                    top_n=5
                )
            
            assert exc_info.value.status_code == 500
            assert "Internal server error" in exc_info.value.detail

    async def test_get_similar_exceptions_empty_results(self):
        """Test handling when no similar exceptions are found."""
        with patch('src.api.routes.router_copilot.SimilarExceptionsFinder') as MockFinder, \
             patch('src.api.routes.router_copilot.get_db_session_context') as mock_db_context, \
             patch('src.api.routes.router_copilot.EmbeddingService'), \
             patch('src.api.routes.router_copilot.CopilotDocumentRepository'), \
             patch('src.api.routes.router_copilot.RetrievalService'), \
             patch('src.api.routes.router_copilot.ExceptionRepository'):
            
            # Setup mocks
            mock_session = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_session
            
            mock_finder_instance = AsyncMock()
            MockFinder.return_value = mock_finder_instance
            mock_finder_instance.find_similar.return_value = []

            from src.api.routes.router_copilot import get_similar_exceptions

            result = await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123",
                top_n=5
            )

            assert isinstance(result, SimilarExceptionsListResponse)
            assert result.total_count == 0
            assert len(result.similar_exceptions) == 0

    async def test_get_similar_exceptions_default_top_n(self):
        """Test that default top_n value is used correctly."""
        with patch('src.api.routes.router_copilot.SimilarExceptionsFinder') as MockFinder, \
             patch('src.api.routes.router_copilot.get_db_session_context') as mock_db_context, \
             patch('src.api.routes.router_copilot.EmbeddingService'), \
             patch('src.api.routes.router_copilot.CopilotDocumentRepository'), \
             patch('src.api.routes.router_copilot.RetrievalService'), \
             patch('src.api.routes.router_copilot.ExceptionRepository'):
            
            # Setup mocks
            mock_session = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_session
            
            mock_finder_instance = AsyncMock()
            MockFinder.return_value = mock_finder_instance
            mock_finder_instance.find_similar.return_value = []

            from src.api.routes.router_copilot import get_similar_exceptions

            # Call without explicit top_n (should default to 5)
            await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123"
            )

            # Verify default top_n=5 was used
            mock_finder_instance.find_similar.assert_called_once_with(
                tenant_id="tenant-123",
                exception_id="EX-2024-1234",
                top_n=5
            )

    async def test_get_similar_exceptions_custom_top_n(self):
        """Test that custom top_n value is used correctly."""
        with patch('src.api.routes.router_copilot.SimilarExceptionsFinder') as MockFinder, \
             patch('src.api.routes.router_copilot.get_db_session_context') as mock_db_context, \
             patch('src.api.routes.router_copilot.EmbeddingService'), \
             patch('src.api.routes.router_copilot.CopilotDocumentRepository'), \
             patch('src.api.routes.router_copilot.RetrievalService'), \
             patch('src.api.routes.router_copilot.ExceptionRepository'):
            
            # Setup mocks
            mock_session = AsyncMock()
            mock_db_context.return_value.__aenter__.return_value = mock_session
            
            mock_finder_instance = AsyncMock()
            MockFinder.return_value = mock_finder_instance
            mock_finder_instance.find_similar.return_value = []

            from src.api.routes.router_copilot import get_similar_exceptions

            # Call with custom top_n
            await get_similar_exceptions(
                exception_id="EX-2024-1234",
                tenant_id="tenant-123",
                top_n=10
            )

            # Verify custom top_n=10 was used
            mock_finder_instance.find_similar.assert_called_once_with(
                tenant_id="tenant-123",
                exception_id="EX-2024-1234",
                top_n=10
            )

    def test_similar_exception_response_model(self):
        """Test SimilarExceptionResponse model validation."""
        response = SimilarExceptionResponse(
            exception_id="EX-2024-1234",
            similarity_score=0.85,
            outcome_summary="Test outcome summary",
            closed_at="2024-12-20T10:30:00Z",
            link_url="/exceptions/EX-2024-1234"
        )
        
        assert response.exception_id == "EX-2024-1234"
        assert response.similarity_score == 0.85
        assert response.outcome_summary == "Test outcome summary"
        assert response.closed_at == "2024-12-20T10:30:00Z"
        assert response.link_url == "/exceptions/EX-2024-1234"

    def test_similar_exceptions_list_response_model(self):
        """Test SimilarExceptionsListResponse model validation."""
        similar_exceptions = [
            SimilarExceptionResponse(
                exception_id="EX-2024-1234",
                similarity_score=0.85,
                outcome_summary="Test outcome summary"
            )
        ]
        
        response = SimilarExceptionsListResponse(
            similar_exceptions=similar_exceptions,
            total_count=1
        )
        
        assert len(response.similar_exceptions) == 1
        assert response.total_count == 1
        assert response.similar_exceptions[0].exception_id == "EX-2024-1234"