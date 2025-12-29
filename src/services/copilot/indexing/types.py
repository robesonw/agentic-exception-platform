"""
Types for Phase 13 Copilot Indexing Foundation.

Provides core data structures for indexing operations:
- IndexJobStatus for tracking indexing progress
- IndexingResult for operation outcomes
- Reuses CopilotDocumentSourceType for source classification

References:
- docs/phase13-copilot-intelligence-mvp.md Section 4.2
- .github/issue_template/phase13-copilot-intelligence-issues.md P13-4, P13-5
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

# Reuse existing source types from models
from src.infrastructure.db.models import CopilotDocumentSourceType


class IndexJobStatus(str, Enum):
    """Status of indexing jobs."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class IndexingResult:
    """Result of an indexing operation."""
    
    # Core result data
    source_type: CopilotDocumentSourceType
    source_id: str
    tenant_id: str
    success: bool
    
    # Processing metrics
    chunks_processed: int = 0
    chunks_indexed: int = 0
    chunks_skipped: int = 0
    chunks_failed: int = 0
    
    # Timing information
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    
    # Error tracking
    error_message: Optional[str] = None
    error_details: Optional[dict[str, Any]] = None
    
    # Metadata
    content_hash: Optional[str] = None
    source_version: Optional[str] = None
    embedding_model: Optional[str] = None
    embedding_dimension: Optional[int] = None
    
    # Additional context
    metadata: dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """Calculate duration from start/end times."""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return self.processing_time_seconds
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate of chunk processing."""
        if self.chunks_processed == 0:
            return 0.0
        return self.chunks_indexed / self.chunks_processed
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_type": self.source_type.value,
            "source_id": self.source_id,
            "tenant_id": self.tenant_id,
            "success": self.success,
            "chunks_processed": self.chunks_processed,
            "chunks_indexed": self.chunks_indexed,
            "chunks_skipped": self.chunks_skipped,
            "chunks_failed": self.chunks_failed,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "processing_time_seconds": self.duration_seconds,
            "error_message": self.error_message,
            "error_details": self.error_details,
            "content_hash": self.content_hash,
            "source_version": self.source_version,
            "embedding_model": self.embedding_model,
            "embedding_dimension": self.embedding_dimension,
            "success_rate": self.success_rate,
            "metadata": self.metadata,
        }
