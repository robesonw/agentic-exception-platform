"""
Worker configuration module for Phase 9.

Provides environment-driven worker settings for horizontal scaling.

Phase 9 P9-26: Worker Scaling Configuration.
Reference: docs/phase9-async-scale-mvp.md Section 9
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


class WorkerConfig:
    """
    Worker configuration loaded from environment variables.
    
    Phase 9 P9-26: Environment-driven worker settings for horizontal scaling.
    Supports:
    - WORKER_TYPE: Type of worker to run (e.g., "intake", "triage", "policy")
    - CONCURRENCY: Number of parallel event processors (default: 1)
    - GROUP_ID: Consumer group ID for load balancing (default: worker type)
    """
    
    def __init__(
        self,
        worker_type: Optional[str] = None,
        concurrency: Optional[int] = None,
        group_id: Optional[str] = None,
    ):
        """
        Initialize worker configuration.
        
        Args:
            worker_type: Worker type (e.g., "intake", "triage", "policy")
            concurrency: Number of parallel event processors (default: 1)
            group_id: Consumer group ID (default: worker_type)
        """
        # Load from environment if not provided
        self.worker_type = worker_type or os.getenv("WORKER_TYPE")
        concurrency_str = os.getenv("CONCURRENCY")
        self.concurrency = concurrency or (int(concurrency_str) if concurrency_str else 1)
        self.group_id = group_id or os.getenv("GROUP_ID") or self.worker_type
        
        # Validate
        if not self.worker_type:
            raise ValueError(
                "WORKER_TYPE environment variable is required. "
                "Set WORKER_TYPE to one of: intake, triage, policy, playbook, tool, feedback, sla_monitor"
            )
        
        if self.concurrency < 1:
            raise ValueError(f"CONCURRENCY must be >= 1, got {self.concurrency}")
        
        if not self.group_id:
            raise ValueError("GROUP_ID is required (or set WORKER_TYPE)")
        
        logger.info(
            f"Worker configuration: worker_type={self.worker_type}, "
            f"concurrency={self.concurrency}, group_id={self.group_id}"
        )
    
    @classmethod
    def from_env(cls) -> "WorkerConfig":
        """
        Create WorkerConfig from environment variables.
        
        Returns:
            WorkerConfig instance
            
        Raises:
            ValueError: If required environment variables are missing
        """
        return cls()
    
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"WorkerConfig(worker_type={self.worker_type}, "
            f"concurrency={self.concurrency}, group_id={self.group_id})"
        )


# Supported worker types
SUPPORTED_WORKER_TYPES = {
    "intake": "IntakeWorker",
    "triage": "TriageWorker",
    "policy": "PolicyWorker",
    "playbook": "PlaybookWorker",
    "tool": "ToolWorker",
    "feedback": "FeedbackWorker",
    "sla_monitor": "SLAMonitorWorker",
}


def get_worker_class_name(worker_type: str) -> Optional[str]:
    """
    Get worker class name for a worker type.
    
    Args:
        worker_type: Worker type (e.g., "intake", "triage")
        
    Returns:
        Worker class name or None if not found
    """
    return SUPPORTED_WORKER_TYPES.get(worker_type.lower())


