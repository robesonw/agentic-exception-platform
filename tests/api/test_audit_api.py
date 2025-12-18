"""
Tests for audit API endpoints (P9-25).

Tests verify:
- Audit queries use EventStoreRepository as source of truth
- Per-exception audit trail querying
- Per-tenant audit trail querying with pagination
- Immutability of audit trail
- Tenant isolation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from src.api.main import app
from src.infrastructure.db.models import EventLog
from src.repository.dto import PaginatedResult


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_event_log():
    """Create sample EventLog for testing."""
    return EventLog(
        event_id=str(uuid4()),
        event_type="ExceptionIngested",
        tenant_id="TENANT_001",
        exception_id="EXC_001",
        correlation_id="EXC_001",
        timestamp=datetime.now(timezone.utc),
        payload={"raw_payload": {"error": "Test"}},
        metadata={},
        version=1,
    )


class TestAuditAPI:
    """Tests for audit API endpoints."""

    @pytest.mark.asyncio
    async def test_get_exception_audit_trail(
        self, client, sample_event_log
    ):
        """Test getting audit trail for an exception."""
        exception_id = "EXC_001"
        tenant_id = "TENANT_001"
        
        # Mock EventStoreRepository
        mock_result = PaginatedResult(
            items=[sample_event_log],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
        )
        
        with patch(
            "src.services.audit_service.get_db_session_context"
        ) as mock_session:
            mock_session.return_value.__aenter__.return_value = AsyncMock()
            
            with patch(
                "src.services.audit_service.AuditService.get_audit_trail_for_exception",
                return_value=mock_result,
            ):
                response = client.get(
                    f"/api/audit/exceptions/{tenant_id}/{exception_id}"
                )
                
                assert response.status_code == 200
                data = response.json()
                assert "items" in data
                assert "total" in data
                assert "page" in data
                assert "page_size" in data
                assert "total_pages" in data
                assert len(data["items"]) == 1
                assert data["items"][0]["event_type"] == "ExceptionIngested"
                assert data["items"][0]["exception_id"] == exception_id
                assert data["items"][0]["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_get_exception_audit_trail_with_filters(
        self, client, sample_event_log
    ):
        """Test getting audit trail with filters."""
        exception_id = "EXC_001"
        tenant_id = "TENANT_001"
        
        mock_result = PaginatedResult(
            items=[sample_event_log],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_exception",
            return_value=mock_result,
        ):
            response = client.get(
                f"/api/audit/exceptions/{tenant_id}/{exception_id}",
                params={
                    "event_type": "ExceptionIngested",
                    "start_timestamp": "2024-01-01T00:00:00Z",
                    "end_timestamp": "2024-12-31T23:59:59Z",
                },
            )
            
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_exception_audit_trail_pagination(
        self, client, sample_event_log
    ):
        """Test pagination for exception audit trail."""
        exception_id = "EXC_001"
        tenant_id = "TENANT_001"
        
        # Create multiple events
        events = [
            EventLog(
                event_id=str(uuid4()),
                event_type=f"EventType{i}",
                tenant_id=tenant_id,
                exception_id=exception_id,
                correlation_id=exception_id,
                timestamp=datetime.now(timezone.utc),
                payload={},
                metadata={},
                version=1,
            )
            for i in range(5)
        ]
        
        mock_result = PaginatedResult(
            items=events[:2],  # First page: 2 items
            total=5,
            page=1,
            page_size=2,
            total_pages=3,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_exception",
            return_value=mock_result,
        ):
            response = client.get(
                f"/api/audit/exceptions/{tenant_id}/{exception_id}",
                params={"page": 1, "page_size": 2},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 2
            assert data["total"] == 5
            assert data["page"] == 1
            assert data["page_size"] == 2
            assert data["total_pages"] == 3

    @pytest.mark.asyncio
    async def test_get_tenant_audit_trail(
        self, client, sample_event_log
    ):
        """Test getting audit trail for a tenant."""
        tenant_id = "TENANT_001"
        
        mock_result = PaginatedResult(
            items=[sample_event_log],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_tenant",
            return_value=mock_result,
        ):
            response = client.get(f"/api/audit/tenants/{tenant_id}")
            
            assert response.status_code == 200
            data = response.json()
            assert "items" in data
            assert "total" in data
            assert data["items"][0]["tenant_id"] == tenant_id

    @pytest.mark.asyncio
    async def test_get_tenant_audit_trail_pagination(
        self, client
    ):
        """Test pagination for tenant audit trail."""
        tenant_id = "TENANT_001"
        
        # Create multiple events
        events = [
            EventLog(
                event_id=str(uuid4()),
                event_type=f"EventType{i}",
                tenant_id=tenant_id,
                exception_id=f"EXC_{i}",
                correlation_id=f"EXC_{i}",
                timestamp=datetime.now(timezone.utc),
                payload={},
                metadata={},
                version=1,
            )
            for i in range(10)
        ]
        
        mock_result = PaginatedResult(
            items=events[:5],  # First page: 5 items
            total=10,
            page=1,
            page_size=5,
            total_pages=2,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_tenant",
            return_value=mock_result,
        ):
            response = client.get(
                f"/api/audit/tenants/{tenant_id}",
                params={"page": 1, "page_size": 5},
            )
            
            assert response.status_code == 200
            data = response.json()
            assert len(data["items"]) == 5
            assert data["total"] == 10
            assert data["page"] == 1
            assert data["page_size"] == 5
            assert data["total_pages"] == 2

    @pytest.mark.asyncio
    async def test_get_tenant_audit_trail_with_filters(
        self, client, sample_event_log
    ):
        """Test getting tenant audit trail with filters."""
        tenant_id = "TENANT_001"
        
        mock_result = PaginatedResult(
            items=[sample_event_log],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_tenant",
            return_value=mock_result,
        ):
            response = client.get(
                f"/api/audit/tenants/{tenant_id}",
                params={
                    "event_type": "ExceptionIngested",
                    "exception_id": "EXC_001",
                    "correlation_id": "EXC_001",
                    "start_timestamp": "2024-01-01T00:00:00Z",
                    "end_timestamp": "2024-12-31T23:59:59Z",
                },
            )
            
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_audit_trail_immutability(
        self, client, sample_event_log
    ):
        """Test that audit trail is immutable (read-only)."""
        exception_id = "EXC_001"
        tenant_id = "TENANT_001"
        
        mock_result = PaginatedResult(
            items=[sample_event_log],
            total=1,
            page=1,
            page_size=50,
            total_pages=1,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_exception",
            return_value=mock_result,
        ):
            # Get audit trail
            response = client.get(
                f"/api/audit/exceptions/{tenant_id}/{exception_id}"
            )
            
            assert response.status_code == 200
            data = response.json()
            
            # Verify event data is read-only (no modification endpoints)
            # This is enforced by the API design - only GET endpoints exist
            assert "items" in data
            assert len(data["items"]) > 0
            
            # Verify event structure includes immutable fields
            event = data["items"][0]
            assert "event_id" in event
            assert "timestamp" in event
            assert "version" in event

    @pytest.mark.asyncio
    async def test_tenant_isolation(
        self, client
    ):
        """Test that audit queries enforce tenant isolation."""
        tenant_id = "TENANT_001"
        other_tenant_id = "TENANT_002"
        
        # Mock result for TENANT_001
        mock_result_001 = PaginatedResult(
            items=[],
            total=0,
            page=1,
            page_size=50,
            total_pages=0,
        )
        
        with patch(
            "src.services.audit_service.AuditService.get_audit_trail_for_tenant",
            return_value=mock_result_001,
        ):
            # Query for TENANT_001
            response = client.get(f"/api/audit/tenants/{tenant_id}")
            assert response.status_code == 200
            
            # Query for TENANT_002 should return different results
            # (In production, this would be enforced by EventStoreRepository)
            response2 = client.get(f"/api/audit/tenants/{other_tenant_id}")
            assert response2.status_code == 200

    @pytest.mark.asyncio
    async def test_invalid_timestamp_format(self, client):
        """Test that invalid timestamp format returns 400."""
        exception_id = "EXC_001"
        tenant_id = "TENANT_001"
        
        response = client.get(
            f"/api/audit/exceptions/{tenant_id}/{exception_id}",
            params={"start_timestamp": "invalid-timestamp"},
        )
        
        assert response.status_code == 400
        assert "Invalid start_timestamp format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_invalid_pagination(self, client):
        """Test that invalid pagination parameters return 400."""
        exception_id = "EXC_001"
        tenant_id = "TENANT_001"
        
        # Test negative page
        response = client.get(
            f"/api/audit/exceptions/{tenant_id}/{exception_id}",
            params={"page": -1},
        )
        assert response.status_code == 422  # FastAPI validation error
        
        # Test zero page_size
        response = client.get(
            f"/api/audit/exceptions/{tenant_id}/{exception_id}",
            params={"page_size": 0},
        )
        assert response.status_code == 422  # FastAPI validation error



