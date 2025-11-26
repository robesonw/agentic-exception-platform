"""
Human-in-the-Loop Approval Workflow for Phase 2.

Provides:
- ApprovalQueue (per tenant)
- submit_for_approval, approve, reject
- timeout + escalation
- approval history persistence

Matches specification from phase2-mvp-issues.md Issue 31.
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of an approval request."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    TIMED_OUT = "TIMED_OUT"
    ESCALATED = "ESCALATED"


@dataclass
class ApprovalRequest:
    """Single approval request."""

    approval_id: str
    tenant_id: str
    exception_id: str
    plan: dict[str, Any]  # Resolution plan from ResolutionAgent
    evidence: list[str]  # Evidence from agents
    status: ApprovalStatus
    submitted_at: datetime
    timeout_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    rejected_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    approval_comments: Optional[str] = None
    rejection_comments: Optional[str] = None
    escalated_at: Optional[datetime] = None
    escalation_reason: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        # Convert datetime to ISO format
        for key, value in data.items():
            if isinstance(value, datetime):
                data[key] = value.isoformat()
            elif isinstance(value, ApprovalStatus):
                data[key] = value.value
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ApprovalRequest":
        """Create from dictionary."""
        # Convert ISO format strings back to datetime
        for key in ["submitted_at", "timeout_at", "approved_at", "rejected_at", "escalated_at"]:
            if key in data and data[key]:
                data[key] = datetime.fromisoformat(data[key])
        
        # Convert status string to enum
        if "status" in data:
            data["status"] = ApprovalStatus(data["status"])
        
        return cls(**data)


class ApprovalQueue:
    """
    Per-tenant approval queue with persistence.
    
    Manages approval requests, timeout handling, and escalation.
    """

    def __init__(
        self,
        tenant_id: str,
        storage_path: Path,
        default_timeout_minutes: int = 60,
        escalation_timeout_minutes: Optional[int] = None,
    ):
        """
        Initialize approval queue for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            storage_path: Base path for storing approval history
            default_timeout_minutes: Default timeout in minutes (default: 60)
            escalation_timeout_minutes: Timeout before escalation (default: 2x default_timeout)
        """
        self.tenant_id = tenant_id
        self.storage_path = storage_path
        self.default_timeout_minutes = default_timeout_minutes
        self.escalation_timeout_minutes = escalation_timeout_minutes or (
            default_timeout_minutes * 2
        )
        
        # In-memory queue: {approval_id: ApprovalRequest}
        self._queue: dict[str, ApprovalRequest] = {}
        
        # Ensure storage directory exists
        self._approval_file = storage_path / "approvals" / f"{tenant_id}.jsonl"
        self._approval_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Load existing approvals from disk
        self._load_approvals()

    def _load_approvals(self) -> None:
        """Load approval history from disk."""
        if not self._approval_file.exists():
            return
        
        try:
            with open(self._approval_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        approval = ApprovalRequest.from_dict(data)
                        # Only load pending approvals into active queue
                        if approval.status == ApprovalStatus.PENDING:
                            self._queue[approval.approval_id] = approval
                    except Exception as e:
                        logger.warning(f"Failed to load approval from history: {e}")
        except Exception as e:
            logger.error(f"Failed to load approval history: {e}")

    def _persist_approval(self, approval: ApprovalRequest) -> None:
        """
        Persist approval to history file.
        
        Args:
            approval: ApprovalRequest to persist
        """
        try:
            with open(self._approval_file, "a", encoding="utf-8") as f:
                json.dump(approval.to_dict(), f)
                f.write("\n")
        except Exception as e:
            logger.error(f"Failed to persist approval {approval.approval_id}: {e}")

    def submit_for_approval(
        self,
        exception_id: str,
        plan: dict[str, Any],
        evidence: list[str],
        timeout_minutes: Optional[int] = None,
    ) -> str:
        """
        Submit a resolution plan for human approval.
        
        Args:
            exception_id: Exception identifier
            plan: Resolution plan from ResolutionAgent
            evidence: Evidence from agents
            timeout_minutes: Optional timeout override
            
        Returns:
            Approval ID
        """
        approval_id = str(uuid.uuid4())
        timeout_minutes = timeout_minutes or self.default_timeout_minutes
        submitted_at = datetime.now(timezone.utc)
        timeout_at = submitted_at + timedelta(minutes=timeout_minutes)
        
        approval = ApprovalRequest(
            approval_id=approval_id,
            tenant_id=self.tenant_id,
            exception_id=exception_id,
            plan=plan,
            evidence=evidence,
            status=ApprovalStatus.PENDING,
            submitted_at=submitted_at,
            timeout_at=timeout_at,
        )
        
        self._queue[approval_id] = approval
        self._persist_approval(approval)
        
        logger.info(
            f"Submitted approval request {approval_id} for exception {exception_id} "
            f"(tenant: {self.tenant_id}, timeout: {timeout_at.isoformat()})"
        )
        
        return approval_id

    def approve(
        self, approval_id: str, user: str, comments: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Approve a pending request.
        
        Args:
            approval_id: Approval identifier
            user: User who approved
            comments: Optional approval comments
            
        Returns:
            Updated ApprovalRequest
            
        Raises:
            ValueError: If approval not found or not pending
        """
        if approval_id not in self._queue:
            raise ValueError(f"Approval {approval_id} not found")
        
        approval = self._queue[approval_id]
        
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval {approval_id} is not pending (status: {approval.status})")
        
        approval.status = ApprovalStatus.APPROVED
        approval.approved_by = user
        approval.approved_at = datetime.now(timezone.utc)
        approval.approval_comments = comments
        
        self._persist_approval(approval)
        
        logger.info(f"Approval {approval_id} approved by {user}")
        
        return approval

    def reject(
        self, approval_id: str, user: str, comments: Optional[str] = None
    ) -> ApprovalRequest:
        """
        Reject a pending request.
        
        Args:
            approval_id: Approval identifier
            user: User who rejected
            comments: Optional rejection comments
            
        Returns:
            Updated ApprovalRequest
            
        Raises:
            ValueError: If approval not found or not pending
        """
        if approval_id not in self._queue:
            raise ValueError(f"Approval {approval_id} not found")
        
        approval = self._queue[approval_id]
        
        if approval.status != ApprovalStatus.PENDING:
            raise ValueError(f"Approval {approval_id} is not pending (status: {approval.status})")
        
        approval.status = ApprovalStatus.REJECTED
        approval.rejected_by = user
        approval.rejected_at = datetime.now(timezone.utc)
        approval.rejection_comments = comments
        
        self._persist_approval(approval)
        
        logger.info(f"Approval {approval_id} rejected by {user}")
        
        return approval

    def get_approval(self, approval_id: str) -> Optional[ApprovalRequest]:
        """
        Get approval request by ID.
        
        Args:
            approval_id: Approval identifier
            
        Returns:
            ApprovalRequest or None if not found
        """
        return self._queue.get(approval_id)

    def list_pending(self) -> list[ApprovalRequest]:
        """
        List all pending approvals.
        
        Returns:
            List of pending ApprovalRequest objects
        """
        return [
            approval
            for approval in self._queue.values()
            if approval.status == ApprovalStatus.PENDING
        ]

    def list_all(self, status: Optional[ApprovalStatus] = None) -> list[ApprovalRequest]:
        """
        List all approvals, optionally filtered by status.
        
        Args:
            status: Optional status filter
            
        Returns:
            List of ApprovalRequest objects
        """
        approvals = list(self._queue.values())
        if status:
            approvals = [a for a in approvals if a.status == status]
        return approvals

    def check_timeouts(self) -> list[ApprovalRequest]:
        """
        Check for timed-out approvals and escalate if needed.
        
        Returns:
            List of approvals that were timed out or escalated
        """
        now = datetime.now(timezone.utc)
        timed_out = []
        
        for approval in list(self._queue.values()):
            if approval.status != ApprovalStatus.PENDING:
                continue
            
            if approval.timeout_at and now >= approval.timeout_at:
                # Check if we should escalate or just timeout
                escalation_deadline = approval.submitted_at + timedelta(
                    minutes=self.escalation_timeout_minutes
                )
                
                if now >= escalation_deadline:
                    # Escalate
                    approval.status = ApprovalStatus.ESCALATED
                    approval.escalated_at = now
                    approval.escalation_reason = "Approval timeout exceeded escalation deadline"
                    self._persist_approval(approval)
                    timed_out.append(approval)
                    logger.warning(
                        f"Approval {approval.approval_id} escalated due to timeout "
                        f"(exception: {approval.exception_id})"
                    )
                else:
                    # Just timeout (can still be approved/rejected manually)
                    approval.status = ApprovalStatus.TIMED_OUT
                    self._persist_approval(approval)
                    timed_out.append(approval)
                    logger.warning(
                        f"Approval {approval.approval_id} timed out "
                        f"(exception: {approval.exception_id})"
                    )
        
        return timed_out

    def get_approval_history(
        self, exception_id: Optional[str] = None
    ) -> list[ApprovalRequest]:
        """
        Get approval history, optionally filtered by exception_id.
        
        Args:
            exception_id: Optional exception identifier filter
            
        Returns:
            List of ApprovalRequest objects from history
        """
        history = []
        
        if not self._approval_file.exists():
            return history
        
        try:
            with open(self._approval_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        data = json.loads(line)
                        approval = ApprovalRequest.from_dict(data)
                        if exception_id is None or approval.exception_id == exception_id:
                            history.append(approval)
                    except Exception as e:
                        logger.warning(f"Failed to load approval from history: {e}")
        except Exception as e:
            logger.error(f"Failed to read approval history: {e}")
        
        return history


class ApprovalQueueRegistry:
    """
    Registry for managing per-tenant approval queues.
    
    Ensures strict tenant isolation.
    """

    def __init__(self, storage_path: Path = Path("./runtime/approvals")):
        """
        Initialize approval queue registry.
        
        Args:
            storage_path: Base path for storing approval history
        """
        self.storage_path = storage_path
        self._queues: dict[str, ApprovalQueue] = {}

    def get_or_create_queue(
        self, tenant_id: str, default_timeout_minutes: int = 60
    ) -> ApprovalQueue:
        """
        Get or create approval queue for tenant.
        
        Args:
            tenant_id: Tenant identifier
            default_timeout_minutes: Default timeout in minutes
            
        Returns:
            ApprovalQueue instance
        """
        if tenant_id not in self._queues:
            self._queues[tenant_id] = ApprovalQueue(
                tenant_id=tenant_id,
                storage_path=self.storage_path,
                default_timeout_minutes=default_timeout_minutes,
            )
            logger.info(f"Created approval queue for tenant {tenant_id}")
        
        return self._queues[tenant_id]

    def get_queue(self, tenant_id: str) -> Optional[ApprovalQueue]:
        """
        Get approval queue for tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            ApprovalQueue instance or None if not found
        """
        return self._queues.get(tenant_id)

