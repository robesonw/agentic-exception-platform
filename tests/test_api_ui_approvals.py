"""
Comprehensive tests for Approval UI API endpoints.

Tests:
- GET /ui/approvals/{tenantId}
- Pending approvals with evidence + plan
- Status filtering
- UI-friendly output format
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from src.api.main import app
from src.workflow.approval import ApprovalQueue, ApprovalQueueRegistry, ApprovalRequest, ApprovalStatus


@pytest.fixture
def approval_registry():
    """Approval queue registry for testing."""
    from pathlib import Path
    import tempfile
    
    with tempfile.TemporaryDirectory() as tmpdir:
        registry = ApprovalQueueRegistry(storage_path=Path(tmpdir))
        yield registry


@pytest.fixture
def client(approval_registry):
    """Test client with mocked approval registry."""
    from src.api.routes import approval_ui
    approval_ui.set_approval_registry(approval_registry)
    
    return TestClient(app)


@pytest.fixture
def sample_approval_request():
    """Sample approval request data."""
    return {
        "exceptionId": "exc_1",
        "plan": {
            "resolvedPlan": [
                {"stepNumber": 1, "action": "retry_settlement", "toolName": "retry_settlement"},
            ],
            "exception": {
                "exceptionId": "exc_1",
                "exceptionType": "SETTLEMENT_FAIL",
                "severity": "HIGH",
            },
        },
        "evidence": [
            "TriageAgent: Classified as SETTLEMENT_FAIL",
            "PolicyAgent: Actionable and approved",
            "ResolutionAgent: Plan created with 1 step",
        ],
    }


DEFAULT_API_KEY = "test_api_key_tenant_001"  # Valid API key from auth.py


@pytest.fixture
def setup_api_key():
    """Setup API key for testing."""
    from src.api.auth import get_api_key_auth
    auth = get_api_key_auth()
    yield auth
    # Cleanup not needed as tests use different tenant IDs


class TestApprovalUIAPI:
    """Tests for Approval UI API endpoints."""

    def test_get_pending_approvals_success(self, client, approval_registry, sample_approval_request, setup_api_key):
        """Test successful retrieval of pending approvals."""
        # Submit an approval
        tenant_id = "TENANT_A"
        approval_queue = approval_registry.get_or_create_queue(tenant_id)
        
        approval_id = approval_queue.submit_for_approval(
            exception_id=sample_approval_request["exceptionId"],
            plan=sample_approval_request["plan"],
            evidence=sample_approval_request["evidence"],
        )
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Get pending approvals via UI API
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["total"] == 1
        assert len(data["approvals"]) == 1
        
        approval = data["approvals"][0]
        assert approval["approvalId"] == approval_id
        assert approval["exceptionId"] == sample_approval_request["exceptionId"]
        assert approval["status"] == "PENDING"
        assert "plan" in approval
        assert "evidence" in approval
        assert "summary" in approval
        assert approval["submittedAt"] is not None

    def test_get_pending_approvals_with_status_filter(self, client, approval_registry, sample_approval_request, setup_api_key):
        """Test filtering approvals by status."""
        tenant_id = "TENANT_A"
        approval_queue = approval_registry.get_or_create_queue(tenant_id)
        
        # Submit and approve an approval
        approval_id = approval_queue.submit_for_approval(
            exception_id=sample_approval_request["exceptionId"],
            plan=sample_approval_request["plan"],
            evidence=sample_approval_request["evidence"],
        )
        approval_queue.approve(approval_id, user="test_user", comments="Approved for testing")
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Get approved approvals
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            params={"status": "APPROVED"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["total"] == 1
        assert data["approvals"][0]["status"] == "APPROVED"
        assert data["approvals"][0]["approvedBy"] == "test_user"

    def test_get_pending_approvals_with_limit(self, client, approval_registry, sample_approval_request, setup_api_key):
        """Test limiting number of approvals returned."""
        tenant_id = "TENANT_A"
        approval_queue = approval_registry.get_or_create_queue(tenant_id)
        
        # Submit multiple approvals
        for i in range(5):
            approval_queue.submit_for_approval(
                exception_id=f"exc_{i}",
                plan=sample_approval_request["plan"],
                evidence=sample_approval_request["evidence"],
            )
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        # Get with limit
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            params={"limit": 3},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["approvals"]) == 3
        assert data["total"] == 3  # Limited to 3

    def test_get_pending_approvals_invalid_status(self, client, approval_registry, setup_api_key):
        """Test that invalid status filter returns 400."""
        tenant_id = "TENANT_A"
        approval_registry.get_or_create_queue(tenant_id)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            params={"status": "INVALID_STATUS"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400
        assert "Invalid status" in response.json()["detail"]

    def test_get_pending_approvals_empty_queue(self, client, approval_registry, setup_api_key):
        """Test getting approvals from empty queue."""
        tenant_id = "TENANT_A"
        approval_registry.get_or_create_queue(tenant_id)
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["tenantId"] == tenant_id
        assert data["total"] == 0
        assert len(data["approvals"]) == 0

    def test_get_pending_approvals_includes_plan_and_evidence(self, client, approval_registry, sample_approval_request, setup_api_key):
        """Test that approvals include plan and evidence."""
        tenant_id = "TENANT_A"
        approval_queue = approval_registry.get_or_create_queue(tenant_id)
        
        approval_queue.submit_for_approval(
            exception_id=sample_approval_request["exceptionId"],
            plan=sample_approval_request["plan"],
            evidence=sample_approval_request["evidence"],
        )
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        approval = data["approvals"][0]
        assert "plan" in approval
        assert approval["plan"] == sample_approval_request["plan"]
        assert "evidence" in approval
        assert approval["evidence"] == sample_approval_request["evidence"]
        assert "summary" in approval
        assert isinstance(approval["summary"], str)
        assert len(approval["summary"]) > 0

    def test_get_pending_approvals_ui_friendly_format(self, client, approval_registry, sample_approval_request, setup_api_key):
        """Test that output is UI-friendly format."""
        tenant_id = "TENANT_A"
        approval_queue = approval_registry.get_or_create_queue(tenant_id)
        
        approval_queue.submit_for_approval(
            exception_id=sample_approval_request["exceptionId"],
            plan=sample_approval_request["plan"],
            evidence=sample_approval_request["evidence"],
        )
        
        # Register API key for tenant
        setup_api_key.register_api_key(DEFAULT_API_KEY, tenant_id)
        
        response = client.get(
            f"/ui/approvals/{tenant_id}",
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Verify UI-friendly structure
        assert "tenantId" in data
        assert "approvals" in data
        assert "total" in data
        
        approval = data["approvals"][0]
        # Verify all required UI fields
        assert "approvalId" in approval
        assert "exceptionId" in approval
        assert "status" in approval
        assert "submittedAt" in approval
        assert "plan" in approval
        assert "evidence" in approval
        assert "summary" in approval
        
        # Verify timestamps are ISO format strings
        assert isinstance(approval["submittedAt"], str)
        # Should be valid ISO format (basic check)
        assert "T" in approval["submittedAt"] or approval["submittedAt"].endswith("Z")
