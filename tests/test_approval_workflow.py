"""
Comprehensive tests for Phase 2 Human-in-the-Loop Approval Workflow.

Tests:
- ApprovalQueue behavior
- Timeout and escalation
- Audit trail
- Per-tenant isolation
"""

import json
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from src.workflow.approval import (
    ApprovalQueue,
    ApprovalQueueRegistry,
    ApprovalRequest,
    ApprovalStatus,
)


@pytest.fixture
def tmp_storage_path(tmp_path):
    """Fixture for temporary storage path."""
    return tmp_path


@pytest.fixture
def approval_queue(tmp_storage_path):
    """Fixture for approval queue."""
    return ApprovalQueue(
        tenant_id="TENANT_A",
        storage_path=tmp_storage_path,
        default_timeout_minutes=60,
    )


@pytest.fixture
def approval_registry(tmp_storage_path):
    """Fixture for approval queue registry."""
    return ApprovalQueueRegistry(storage_path=tmp_storage_path)


class TestApprovalRequest:
    """Tests for ApprovalRequest dataclass."""

    def test_approval_request_creation(self):
        """Test creating ApprovalRequest."""
        request = ApprovalRequest(
            approval_id="approval_1",
            tenant_id="TENANT_A",
            exception_id="exc_1",
            plan={"steps": []},
            evidence=["Evidence 1"],
            status=ApprovalStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
        )
        
        assert request.approval_id == "approval_1"
        assert request.tenant_id == "TENANT_A"
        assert request.exception_id == "exc_1"
        assert request.status == ApprovalStatus.PENDING

    def test_approval_request_to_dict(self):
        """Test converting ApprovalRequest to dictionary."""
        request = ApprovalRequest(
            approval_id="approval_1",
            tenant_id="TENANT_A",
            exception_id="exc_1",
            plan={"steps": []},
            evidence=[],
            status=ApprovalStatus.PENDING,
            submitted_at=datetime.now(timezone.utc),
        )
        
        data = request.to_dict()
        
        assert data["approval_id"] == "approval_1"
        assert data["status"] == "PENDING"
        assert isinstance(data["submitted_at"], str)  # ISO format

    def test_approval_request_from_dict(self):
        """Test creating ApprovalRequest from dictionary."""
        data = {
            "approval_id": "approval_1",
            "tenant_id": "TENANT_A",
            "exception_id": "exc_1",
            "plan": {"steps": []},
            "evidence": [],
            "status": "PENDING",
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        
        request = ApprovalRequest.from_dict(data)
        
        assert request.approval_id == "approval_1"
        assert request.status == ApprovalStatus.PENDING
        assert isinstance(request.submitted_at, datetime)


class TestApprovalQueue:
    """Tests for ApprovalQueue."""

    def test_submit_for_approval(self, approval_queue):
        """Test submitting for approval."""
        approval_id = approval_queue.submit_for_approval(
            exception_id="exc_1",
            plan={"steps": [{"action": "retry"}]},
            evidence=["Evidence 1", "Evidence 2"],
        )
        
        assert approval_id is not None
        assert len(approval_id) > 0
        
        # Verify approval is in queue
        approval = approval_queue.get_approval(approval_id)
        assert approval is not None
        assert approval.exception_id == "exc_1"
        assert approval.status == ApprovalStatus.PENDING
        assert approval.timeout_at is not None

    def test_approve_request(self, approval_queue):
        """Test approving a request."""
        approval_id = approval_queue.submit_for_approval(
            exception_id="exc_1",
            plan={"steps": []},
            evidence=[],
        )
        
        approval = approval_queue.approve(approval_id, user="user1", comments="Looks good")
        
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.approved_by == "user1"
        assert approval.approval_comments == "Looks good"
        assert approval.approved_at is not None

    def test_reject_request(self, approval_queue):
        """Test rejecting a request."""
        approval_id = approval_queue.submit_for_approval(
            exception_id="exc_1",
            plan={"steps": []},
            evidence=[],
        )
        
        approval = approval_queue.reject(approval_id, user="user1", comments="Not safe")
        
        assert approval.status == ApprovalStatus.REJECTED
        assert approval.rejected_by == "user1"
        assert approval.rejection_comments == "Not safe"
        assert approval.rejected_at is not None

    def test_approve_non_pending_raises_error(self, approval_queue):
        """Test that approving non-pending request raises error."""
        approval_id = approval_queue.submit_for_approval(
            exception_id="exc_1",
            plan={"steps": []},
            evidence=[],
        )
        
        # Approve once
        approval_queue.approve(approval_id, user="user1")
        
        # Try to approve again - should raise error
        with pytest.raises(ValueError, match="not pending"):
            approval_queue.approve(approval_id, user="user2")

    def test_reject_non_pending_raises_error(self, approval_queue):
        """Test that rejecting non-pending request raises error."""
        approval_id = approval_queue.submit_for_approval(
            exception_id="exc_1",
            plan={"steps": []},
            evidence=[],
        )
        
        # Reject once
        approval_queue.reject(approval_id, user="user1")
        
        # Try to reject again - should raise error
        with pytest.raises(ValueError, match="not pending"):
            approval_queue.reject(approval_id, user="user2")

    def test_list_pending(self, approval_queue):
        """Test listing pending approvals."""
        # Submit multiple approvals
        approval_id1 = approval_queue.submit_for_approval("exc_1", {"steps": []}, [])
        approval_id2 = approval_queue.submit_for_approval("exc_2", {"steps": []}, [])
        approval_id3 = approval_queue.submit_for_approval("exc_3", {"steps": []}, [])
        
        # Approve one
        approval_queue.approve(approval_id2, user="user1")
        
        # List pending
        pending = approval_queue.list_pending()
        
        assert len(pending) == 2
        approval_ids = {a.approval_id for a in pending}
        assert approval_id1 in approval_ids
        assert approval_id3 in approval_ids
        assert approval_id2 not in approval_ids

    def test_list_all(self, approval_queue):
        """Test listing all approvals."""
        # Submit and process approvals
        approval_id1 = approval_queue.submit_for_approval("exc_1", {"steps": []}, [])
        approval_id2 = approval_queue.submit_for_approval("exc_2", {"steps": []}, [])
        approval_queue.approve(approval_id1, user="user1")
        approval_queue.reject(approval_id2, user="user1")
        
        # List all
        all_approvals = approval_queue.list_all()
        assert len(all_approvals) == 2
        
        # List by status
        approved = approval_queue.list_all(status=ApprovalStatus.APPROVED)
        assert len(approved) == 1
        assert approved[0].approval_id == approval_id1
        
        rejected = approval_queue.list_all(status=ApprovalStatus.REJECTED)
        assert len(rejected) == 1
        assert rejected[0].approval_id == approval_id2

    def test_persistence(self, tmp_storage_path):
        """Test that approvals are persisted to disk."""
        # Create queue and submit approval
        queue1 = ApprovalQueue("TENANT_A", tmp_storage_path)
        approval_id = queue1.submit_for_approval("exc_1", {"steps": []}, [])
        
        # Create new queue instance (simulates restart)
        queue2 = ApprovalQueue("TENANT_A", tmp_storage_path)
        
        # Should load pending approval
        approval = queue2.get_approval(approval_id)
        assert approval is not None
        assert approval.approval_id == approval_id

    def test_timeout_detection(self, tmp_storage_path):
        """Test timeout detection."""
        # Create queue with short timeout
        queue = ApprovalQueue(
            tenant_id="TENANT_A",
            storage_path=tmp_storage_path,
            default_timeout_minutes=1,  # 1 minute timeout
            escalation_timeout_minutes=2,  # 2 minutes escalation
        )
        
        # Submit approval with past timeout
        approval_id = queue.submit_for_approval("exc_1", {"steps": []}, [])
        approval = queue.get_approval(approval_id)
        
        # Manually set timeout and submitted_at to past (past escalation deadline)
        now = datetime.now(timezone.utc)
        approval.timeout_at = now - timedelta(minutes=5)
        approval.submitted_at = now - timedelta(minutes=10)  # Past escalation deadline
        queue._queue[approval_id] = approval
        
        # Check timeouts
        timed_out = queue.check_timeouts()
        
        assert len(timed_out) == 1
        assert timed_out[0].approval_id == approval_id
        # Should be escalated since it's past escalation deadline
        assert timed_out[0].status == ApprovalStatus.ESCALATED

    def test_timeout_before_escalation(self, tmp_storage_path):
        """Test timeout before escalation deadline."""
        # Create queue
        queue = ApprovalQueue(
            tenant_id="TENANT_A",
            storage_path=tmp_storage_path,
            default_timeout_minutes=1,
            escalation_timeout_minutes=5,  # 5 minutes escalation
        )
        
        approval_id = queue.submit_for_approval("exc_1", {"steps": []}, [])
        approval = queue.get_approval(approval_id)
        
        # Set timeout to past but before escalation
        approval.timeout_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        approval.submitted_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        queue._queue[approval_id] = approval
        
        # Check timeouts
        timed_out = queue.check_timeouts()
        
        assert len(timed_out) == 1
        # Should be timed out but not escalated yet
        assert timed_out[0].status == ApprovalStatus.TIMED_OUT

    def test_get_approval_history(self, approval_queue):
        """Test getting approval history."""
        # Submit and process approvals
        approval_id1 = approval_queue.submit_for_approval("exc_1", {"steps": []}, [])
        approval_id2 = approval_queue.submit_for_approval("exc_2", {"steps": []}, [])
        approval_queue.approve(approval_id1, user="user1")
        
        # Get history
        history = approval_queue.get_approval_history()
        
        assert len(history) >= 2
        
        # Filter by exception_id
        history_exc1 = approval_queue.get_approval_history(exception_id="exc_1")
        assert len(history_exc1) >= 1
        assert all(a.exception_id == "exc_1" for a in history_exc1)


class TestApprovalQueueRegistry:
    """Tests for ApprovalQueueRegistry."""

    def test_get_or_create_queue(self, approval_registry):
        """Test getting or creating queue."""
        queue1 = approval_registry.get_or_create_queue("TENANT_A")
        queue2 = approval_registry.get_or_create_queue("TENANT_A")
        
        # Should return same instance
        assert queue1 is queue2
        
        # Different tenant should get different queue
        queue3 = approval_registry.get_or_create_queue("TENANT_B")
        assert queue3 is not queue1

    def test_get_queue(self, approval_registry):
        """Test getting queue."""
        # Get non-existent queue
        queue = approval_registry.get_queue("TENANT_A")
        assert queue is None
        
        # Create queue
        created = approval_registry.get_or_create_queue("TENANT_A")
        
        # Get should return it
        queue = approval_registry.get_queue("TENANT_A")
        assert queue is created

    def test_tenant_isolation(self, approval_registry):
        """Test that queues are isolated per tenant."""
        queue_a = approval_registry.get_or_create_queue("TENANT_A")
        queue_b = approval_registry.get_or_create_queue("TENANT_B")
        
        # Submit to tenant A
        approval_id_a = queue_a.submit_for_approval("exc_1", {"steps": []}, [])
        
        # Submit to tenant B
        approval_id_b = queue_b.submit_for_approval("exc_1", {"steps": []}, [])
        
        # Tenant B should not see tenant A's approvals
        pending_b = queue_b.list_pending()
        assert len(pending_b) == 1
        assert pending_b[0].approval_id == approval_id_b
        
        # Tenant A should not see tenant B's approvals
        pending_a = queue_a.list_pending()
        assert len(pending_a) == 1
        assert pending_a[0].approval_id == approval_id_a


class TestApprovalWorkflowIntegration:
    """Tests for approval workflow integration."""

    def test_approval_lifecycle(self, approval_queue):
        """Test complete approval lifecycle."""
        # Submit
        approval_id = approval_queue.submit_for_approval(
            exception_id="exc_1",
            plan={"steps": [{"action": "retry"}]},
            evidence=["Evidence 1"],
        )
        
        assert approval_queue.get_approval(approval_id).status == ApprovalStatus.PENDING
        
        # Approve
        approval = approval_queue.approve(approval_id, user="reviewer1", comments="Approved")
        
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.approved_by == "reviewer1"
        
        # Verify it's no longer pending
        pending = approval_queue.list_pending()
        assert approval_id not in {a.approval_id for a in pending}

    def test_approval_with_comments(self, approval_queue):
        """Test approval with comments."""
        approval_id = approval_queue.submit_for_approval("exc_1", {"steps": []}, [])
        
        approval = approval_queue.approve(
            approval_id, user="reviewer1", comments="This looks safe to execute"
        )
        
        assert approval.approval_comments == "This looks safe to execute"
        
        # Reject with comments
        approval_id2 = approval_queue.submit_for_approval("exc_2", {"steps": []}, [])
        rejection = approval_queue.reject(
            approval_id2, user="reviewer1", comments="Too risky, needs more review"
        )
        
        assert rejection.rejection_comments == "Too risky, needs more review"

