"""
Integration tests for similar exceptions API endpoint.

Tests the complete flow of finding similar exceptions through the API
with real database interactions and service integration.
"""

import pytest
from decimal import Decimal
from datetime import datetime, timezone
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import Exception, ExceptionSeverity, ExceptionStatus


@pytest.mark.integration
class TestSimilarExceptionsAPIIntegration:
    """Integration tests for similar exceptions API endpoint."""

    @pytest.fixture
    async def sample_exceptions(self, test_session: AsyncSession):
        """Create sample exceptions for testing."""
        # Create source exception
        source_exception = Exception(
            exception_id="EX-2024-1234",
            tenant_id="tenant-123",
            domain="finance",
            type="payment_failed",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.OPEN,
            source_system="PaymentGateway",
            entity="customer-456",
            amount=Decimal("1500.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Create similar resolved exceptions
        similar1 = Exception(
            exception_id="EX-2024-5678",
            tenant_id="tenant-123",
            domain="finance",
            type="payment_failed",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.RESOLVED,
            source_system="PaymentGateway",
            entity="customer-789",
            amount=Decimal("2000.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        similar2 = Exception(
            exception_id="EX-2024-9012",
            tenant_id="tenant-123",
            domain="finance", 
            type="payment_timeout",
            severity=ExceptionSeverity.MEDIUM,
            status=ExceptionStatus.RESOLVED,
            source_system="PaymentGateway",
            entity="customer-101",
            amount=Decimal("750.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )
        
        # Exception from different tenant (should not appear in results)
        different_tenant = Exception(
            exception_id="EX-2024-3333",
            tenant_id="tenant-456",
            domain="finance",
            type="payment_failed",
            severity=ExceptionSeverity.HIGH,
            status=ExceptionStatus.RESOLVED,
            source_system="PaymentGateway", 
            entity="customer-999",
            amount=Decimal("1500.00"),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc)
        )

        async with test_session() as session:
            session.add_all([source_exception, similar1, similar2, different_tenant])
            await session.commit()
            
            return {
                "source": source_exception,
                "similar1": similar1,
                "similar2": similar2,
                "different_tenant": different_tenant
            }

    async def test_similar_exceptions_endpoint_integration(self, async_client: AsyncClient, 
                                                         sample_exceptions):
        """Test the complete similar exceptions endpoint flow."""
        # Note: This test assumes the vector search infrastructure is set up
        # In a real implementation, you would need:
        # 1. Embeddings generated for the resolved exceptions
        # 2. Vector store populated with the exception data
        # 3. Proper indexing of resolved exceptions
        
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={
                "tenant_id": "tenant-123",
                "top_n": 5
            }
        )
        
        assert response.status_code == 200
        
        data = response.json()
        assert "similar_exceptions" in data
        assert "total_count" in data
        
        # Verify response structure
        similar_exceptions = data["similar_exceptions"]
        assert isinstance(similar_exceptions, list)
        
        # Each similar exception should have required fields
        for similar in similar_exceptions:
            assert "exception_id" in similar
            assert "similarity_score" in similar
            assert "outcome_summary" in similar
            # Optional fields
            assert "closed_at" in similar
            assert "link_url" in similar

    async def test_similar_exceptions_tenant_isolation(self, async_client: AsyncClient,
                                                      sample_exceptions):
        """Test that tenant isolation is enforced in the API."""
        # Request similar exceptions for different tenant
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-3333",
            params={
                "tenant_id": "tenant-456",
                "top_n": 5
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should not include exceptions from tenant-123
        similar_exceptions = data["similar_exceptions"]
        for similar in similar_exceptions:
            # Verify no results from tenant-123 appear
            assert similar["exception_id"] not in ["EX-2024-1234", "EX-2024-5678", "EX-2024-9012"]

    async def test_similar_exceptions_validation_errors(self, async_client: AsyncClient):
        """Test API validation errors."""
        # Test missing tenant_id
        response = await async_client.get("/api/copilot/similar/EX-2024-1234")
        assert response.status_code == 422  # FastAPI validation error
        
        # Test empty tenant_id
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={"tenant_id": ""}
        )
        assert response.status_code == 400
        
        # Test invalid top_n
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={
                "tenant_id": "tenant-123",
                "top_n": 0
            }
        )
        assert response.status_code == 400
        
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234", 
            params={
                "tenant_id": "tenant-123",
                "top_n": 25
            }
        )
        assert response.status_code == 400

    async def test_similar_exceptions_not_found(self, async_client: AsyncClient):
        """Test behavior when exception is not found."""
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-9999",
            params={
                "tenant_id": "tenant-123",
                "top_n": 5
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_similar_exceptions_cross_tenant_not_found(self, async_client: AsyncClient,
                                                           sample_exceptions):
        """Test that exceptions from wrong tenant are treated as not found."""
        # Try to access EX-2024-1234 (tenant-123) with different tenant ID
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={
                "tenant_id": "tenant-456",
                "top_n": 5
            }
        )
        
        assert response.status_code == 400
        data = response.json()
        assert "not found" in data["detail"].lower()

    async def test_similar_exceptions_default_parameters(self, async_client: AsyncClient,
                                                        sample_exceptions):
        """Test that default parameters work correctly."""
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={"tenant_id": "tenant-123"}
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Default top_n should be 5, so max 5 results
        assert len(data["similar_exceptions"]) <= 5

    async def test_similar_exceptions_response_format(self, async_client: AsyncClient,
                                                     sample_exceptions):
        """Test that response format matches the expected schema."""
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={
                "tenant_id": "tenant-123", 
                "top_n": 3
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Validate top-level structure
        assert isinstance(data["similar_exceptions"], list)
        assert isinstance(data["total_count"], int)
        assert data["total_count"] == len(data["similar_exceptions"])
        
        # Validate each similar exception structure
        for similar in data["similar_exceptions"]:
            assert isinstance(similar["exception_id"], str)
            assert isinstance(similar["similarity_score"], (int, float))
            assert isinstance(similar["outcome_summary"], str)
            assert 0.0 <= similar["similarity_score"] <= 1.0
            
            # Optional fields can be None
            if similar["closed_at"] is not None:
                assert isinstance(similar["closed_at"], str)
            if similar["link_url"] is not None:
                assert isinstance(similar["link_url"], str)
                assert similar["link_url"].startswith("/exceptions/")
                
            # Verify link URL format
            if similar["link_url"]:
                expected_url = f"/exceptions/{similar['exception_id']}"
                assert similar["link_url"] == expected_url

    async def test_similar_exceptions_top_n_limiting(self, async_client: AsyncClient,
                                                    sample_exceptions):
        """Test that top_n parameter properly limits results."""
        # Request with top_n=1
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={
                "tenant_id": "tenant-123",
                "top_n": 1
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have at most 1 result
        assert len(data["similar_exceptions"]) <= 1
        assert data["total_count"] == len(data["similar_exceptions"])
        
        # Request with top_n=20 (maximum)
        response = await async_client.get(
            "/api/copilot/similar/EX-2024-1234",
            params={
                "tenant_id": "tenant-123", 
                "top_n": 20
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Should have at most 20 results (probably fewer due to limited test data)
        assert len(data["similar_exceptions"]) <= 20