"""
API tests for approval workflow endpoints.

Tests:
- POST /approvals/{tenantId}
- GET /approvals/{tenantId}
- POST /approvals/{tenantId}/{approvalId}/approve
- POST /approvals/{tenantId}/{approvalId}/reject
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.api.routes.approvals import set_approval_registry
from src.workflow.approval import ApprovalQueueRegistry
from pathlib import Path

# Test API key (matches test auth setup)
DEFAULT_API_KEY = "test_api_key_tenant_001"


@pytest.fixture
def approval_registry(tmp_path):
    """Fixture for approval registry."""
    registry = ApprovalQueueRegistry(storage_path=tmp_path)
    set_approval_registry(registry)
    return registry


@pytest.fixture
def client(approval_registry):
    """Fixture for test client."""
    return TestClient(app)


class TestApprovalAPI:
    """Tests for approval API endpoints."""

    def test_submit_approval(self, client, approval_registry):
        """Test POST /approvals/{tenantId}."""
        response = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": [{"action": "retry"}]},
                "evidence": ["Evidence 1"],
                "timeoutMinutes": 60,
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "approvalId" in data
        assert data["tenantId"] == "TENANT_A"
        assert data["exceptionId"] == "exc_1"
        assert data["status"] == "PENDING"
        assert "submittedAt" in data

    def test_list_approvals(self, client, approval_registry):
        """Test GET /approvals/{tenantId}."""
        # Submit some approvals
        response1 = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id1 = response1.json()["approvalId"]
        
        response2 = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_2",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id2 = response2.json()["approvalId"]
        
        # List all approvals
        response = client.get("/approvals/TENANT_A", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 2
        approval_ids = {a["approvalId"] for a in data}
        assert approval_id1 in approval_ids
        assert approval_id2 in approval_ids

    def test_list_approvals_filtered_by_status(self, client, approval_registry):
        """Test GET /approvals/{tenantId} with status filter."""
        # Submit and approve an approval
        response = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id = response.json()["approvalId"]
        
        client.post(
            f"/approvals/TENANT_A/{approval_id}/approve",
            json={"user": "reviewer1", "comments": "Approved"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        # List only approved
        response = client.get("/approvals/TENANT_A?status=APPROVED", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert all(a["status"] == "APPROVED" for a in data)
        assert any(a["approvalId"] == approval_id for a in data)

    def test_approve_request(self, client, approval_registry):
        """Test POST /approvals/{tenantId}/{approvalId}/approve."""
        # Submit approval
        response = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id = response.json()["approvalId"]
        
        # Approve
        response = client.post(
            f"/approvals/TENANT_A/{approval_id}/approve",
            json={"user": "reviewer1", "comments": "Looks good"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "APPROVED"
        assert data["approvedBy"] == "reviewer1"
        assert data["approvalComments"] == "Looks good"
        assert data["approvedAt"] is not None

    def test_reject_request(self, client, approval_registry):
        """Test POST /approvals/{tenantId}/{approvalId}/reject."""
        # Submit approval
        response = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id = response.json()["approvalId"]
        
        # Reject
        response = client.post(
            f"/approvals/TENANT_A/{approval_id}/reject",
            json={"user": "reviewer1", "comments": "Not safe"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "REJECTED"
        assert data["rejectedBy"] == "reviewer1"
        assert data["rejectionComments"] == "Not safe"
        assert data["rejectedAt"] is not None

    def test_approve_non_existent_raises_404(self, client, approval_registry):
        """Test that approving non-existent approval raises 404."""
        response = client.post(
            "/approvals/TENANT_A/non-existent-id/approve",
            json={"user": "reviewer1"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 404

    def test_approve_already_approved_raises_400(self, client, approval_registry):
        """Test that approving already approved request raises 400."""
        # Submit and approve
        response = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id = response.json()["approvalId"]
        
        client.post(
            f"/approvals/TENANT_A/{approval_id}/approve",
            json={"user": "reviewer1"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        # Try to approve again
        response = client.post(
            f"/approvals/TENANT_A/{approval_id}/approve",
            json={"user": "reviewer2"},
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        
        assert response.status_code == 400

    def test_get_approval(self, client, approval_registry):
        """Test GET /approvals/{tenantId}/{approvalId}."""
        # Submit approval
        response = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id = response.json()["approvalId"]
        
        # Get approval
        response = client.get(f"/approvals/TENANT_A/{approval_id}", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 200
        data = response.json()
        assert data["approvalId"] == approval_id
        assert data["exceptionId"] == "exc_1"
        assert data["status"] == "PENDING"

    def test_get_non_existent_approval_raises_404(self, client, approval_registry):
        """Test that getting non-existent approval raises 404."""
        response = client.get("/approvals/TENANT_A/non-existent-id", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 404

    def test_invalid_status_filter_raises_400(self, client, approval_registry):
        """Test that invalid status filter raises 400."""
        response = client.get("/approvals/TENANT_A?status=INVALID", headers={"X-API-KEY": DEFAULT_API_KEY})
        
        assert response.status_code == 400

    def test_tenant_isolation(self, client, approval_registry):
        """Test that approvals are isolated per tenant."""
        # Submit to tenant A
        response_a = client.post(
            "/approvals/TENANT_A",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id_a = response_a.json()["approvalId"]
        
        # Submit to tenant B
        response_b = client.post(
            "/approvals/TENANT_B",
            json={
                "exceptionId": "exc_1",
                "plan": {"steps": []},
                "evidence": [],
            },
            headers={"X-API-KEY": DEFAULT_API_KEY},
        )
        approval_id_b = response_b.json()["approvalId"]
        
        # Tenant A should not see tenant B's approvals
        response = client.get("/approvals/TENANT_A", headers={"X-API-KEY": DEFAULT_API_KEY})
        data = response.json()
        approval_ids = {a["approvalId"] for a in data}
        assert approval_id_a in approval_ids
        assert approval_id_b not in approval_ids
        
        # Tenant B should not see tenant A's approvals
        response = client.get("/approvals/TENANT_B", headers={"X-API-KEY": DEFAULT_API_KEY})
        data = response.json()
        approval_ids = {a["approvalId"] for a in data}
        assert approval_id_b in approval_ids
        assert approval_id_a not in approval_ids

