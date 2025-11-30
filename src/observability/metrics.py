"""
Metrics collector for tracking exception processing metrics per tenant.

Phase 2: Extended with rich metrics including:
- Per-playbook success rates
- Per-tool latency, retry counts, failure rates
- Approval queue aging
- Recurrence stats by exceptionType
- Confidence distribution

Matches specification from docs/master_project_instruction_full.md and phase2-mvp-issues.md Issue 40.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class PlaybookMetrics:
    """Metrics for a single playbook."""

    playbook_id: str
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_execution_time_seconds: float = 0.0

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count

    def get_avg_execution_time(self) -> float:
        """Calculate average execution time."""
        if self.execution_count == 0:
            return 0.0
        return self.total_execution_time_seconds / self.execution_count


@dataclass
class ToolMetrics:
    """Metrics for a single tool."""

    tool_name: str
    invocation_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_retry_count: int = 0
    total_latency_seconds: float = 0.0
    latency_samples: list[float] = field(default_factory=list)

    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.invocation_count == 0:
            return 0.0
        return self.success_count / self.invocation_count

    def get_failure_rate(self) -> float:
        """Calculate failure rate."""
        if self.invocation_count == 0:
            return 0.0
        return self.failure_count / self.invocation_count

    def get_avg_latency(self) -> float:
        """Calculate average latency."""
        if self.invocation_count == 0:
            return 0.0
        return self.total_latency_seconds / self.invocation_count

    def get_avg_retries(self) -> float:
        """Calculate average retry count."""
        if self.invocation_count == 0:
            return 0.0
        return self.total_retry_count / self.invocation_count

    def get_p50_latency(self) -> float:
        """Calculate 50th percentile latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        index = len(sorted_samples) // 2
        return sorted_samples[index]

    def get_p95_latency(self) -> float:
        """Calculate 95th percentile latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        index = int(len(sorted_samples) * 0.95)
        return sorted_samples[min(index, len(sorted_samples) - 1)]

    def get_p99_latency(self) -> float:
        """Calculate 99th percentile latency."""
        if not self.latency_samples:
            return 0.0
        sorted_samples = sorted(self.latency_samples)
        index = int(len(sorted_samples) * 0.99)
        return sorted_samples[min(index, len(sorted_samples) - 1)]


@dataclass
class ApprovalQueueMetrics:
    """Metrics for approval queue."""

    pending_count: int = 0
    total_pending_age_seconds: float = 0.0
    oldest_pending_age_seconds: float = 0.0
    approval_count: int = 0
    rejection_count: int = 0
    timeout_count: int = 0

    def get_avg_pending_age(self) -> float:
        """Calculate average age of pending approvals."""
        if self.pending_count == 0:
            return 0.0
        return self.total_pending_age_seconds / self.pending_count


@dataclass
class ExceptionTypeRecurrence:
    """Recurrence statistics for an exception type."""

    exception_type: str
    occurrence_count: int = 0
    first_seen: datetime | None = None
    last_seen: datetime | None = None
    unique_exception_ids: set[str] = field(default_factory=set)

    def get_unique_count(self) -> int:
        """Get count of unique exceptions."""
        return len(self.unique_exception_ids)

    def get_recurrence_rate(self) -> float:
        """Calculate recurrence rate (occurrences per unique exception)."""
        unique = self.get_unique_count()
        if unique == 0:
            return 0.0
        return self.occurrence_count / unique


@dataclass
class ConfidenceDistribution:
    """Confidence score distribution."""

    samples: list[float] = field(default_factory=list)
    count_by_range: dict[str, int] = field(default_factory=lambda: {
        "0.0-0.5": 0,
        "0.5-0.7": 0,
        "0.7-0.9": 0,
        "0.9-1.0": 0,
    })

    def add_sample(self, confidence: float) -> None:
        """Add a confidence sample."""
        self.samples.append(confidence)
        # Update range counts
        if confidence < 0.5:
            self.count_by_range["0.0-0.5"] += 1
        elif confidence < 0.7:
            self.count_by_range["0.5-0.7"] += 1
        elif confidence < 0.9:
            self.count_by_range["0.7-0.9"] += 1
        else:
            self.count_by_range["0.9-1.0"] += 1

    def get_avg_confidence(self) -> float:
        """Calculate average confidence."""
        if not self.samples:
            return 0.0
        return sum(self.samples) / len(self.samples)

    def get_median_confidence(self) -> float:
        """Calculate median confidence."""
        if not self.samples:
            return 0.0
        sorted_samples = sorted(self.samples)
        index = len(sorted_samples) // 2
        return sorted_samples[index]


@dataclass
class ViolationMetrics:
    """Metrics for violations."""

    policy_violation_count: int = 0
    tool_violation_count: int = 0
    violation_count_by_severity: dict[str, int] = field(default_factory=lambda: {
        "LOW": 0,
        "MEDIUM": 0,
        "HIGH": 0,
        "CRITICAL": 0,
    })


@dataclass
class TenantMetrics:
    """Metrics for a single tenant."""

    tenant_id: str
    exception_count: int = 0
    auto_resolution_count: int = 0
    actionable_approved_count: int = 0
    actionable_non_approved_count: int = 0
    non_actionable_count: int = 0
    escalated_count: int = 0
    total_resolution_time_seconds: float = 0.0
    resolution_timestamps: list[datetime] = field(default_factory=list)
    
    # Phase 2: Rich metrics
    playbook_metrics: dict[str, PlaybookMetrics] = field(default_factory=dict)
    tool_metrics: dict[str, ToolMetrics] = field(default_factory=dict)
    approval_queue_metrics: ApprovalQueueMetrics = field(default_factory=ApprovalQueueMetrics)
    exception_type_recurrence: dict[str, ExceptionTypeRecurrence] = field(default_factory=dict)
    confidence_distribution: ConfidenceDistribution = field(default_factory=ConfidenceDistribution)
    
    # Phase 3: Violation metrics
    violation_metrics: ViolationMetrics = field(default_factory=ViolationMetrics)
    
    # Phase 3: Explanation metrics (P3-31)
    explanations_generated_total: int = 0
    explanations_per_exception: dict[str, int] = field(default_factory=dict)  # exception_id -> count
    explanation_latency_samples: list[float] = field(default_factory=list)  # in milliseconds
    explanation_quality_scores: list[float] = field(default_factory=list)  # quality scores

    def get_or_create_playbook_metrics(self, playbook_id: str) -> PlaybookMetrics:
        """Get or create playbook metrics."""
        if playbook_id not in self.playbook_metrics:
            self.playbook_metrics[playbook_id] = PlaybookMetrics(playbook_id=playbook_id)
        return self.playbook_metrics[playbook_id]

    def get_or_create_tool_metrics(self, tool_name: str) -> ToolMetrics:
        """Get or create tool metrics."""
        if tool_name not in self.tool_metrics:
            self.tool_metrics[tool_name] = ToolMetrics(tool_name=tool_name)
        return self.tool_metrics[tool_name]

    def get_or_create_exception_type_recurrence(self, exception_type: str) -> ExceptionTypeRecurrence:
        """Get or create exception type recurrence."""
        if exception_type not in self.exception_type_recurrence:
            self.exception_type_recurrence[exception_type] = ExceptionTypeRecurrence(
                exception_type=exception_type
            )
        return self.exception_type_recurrence[exception_type]

    def get_auto_resolution_rate(self) -> float:
        """
        Calculate auto-resolution rate.
        
        Returns:
            Auto-resolution rate as float between 0.0 and 1.0
        """
        if self.exception_count == 0:
            return 0.0
        return self.auto_resolution_count / self.exception_count

    def get_mttr_seconds(self) -> float:
        """
        Calculate Mean Time To Resolution (MTTR) in seconds.
        
        For MVP, this is approximate based on resolution timestamps.
        
        Returns:
            MTTR in seconds, or 0.0 if no resolutions
        """
        if not self.resolution_timestamps:
            return 0.0
        
        # For MVP, calculate average time between exception creation and resolution
        # In production, this would track actual resolution times
        if len(self.resolution_timestamps) < 2:
            return 0.0
        
        # Calculate average time between timestamps
        total_time = 0.0
        for i in range(1, len(self.resolution_timestamps)):
            time_diff = (
                self.resolution_timestamps[i] - self.resolution_timestamps[i - 1]
            ).total_seconds()
            total_time += time_diff
        
        return total_time / (len(self.resolution_timestamps) - 1) if len(self.resolution_timestamps) > 1 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """
        Convert metrics to dictionary for API response.
        
        Returns:
            Dictionary with all metrics
        """
        # Convert playbook metrics
        playbook_metrics_dict = {}
        for playbook_id, metrics in self.playbook_metrics.items():
            playbook_metrics_dict[playbook_id] = {
                "executionCount": metrics.execution_count,
                "successCount": metrics.success_count,
                "failureCount": metrics.failure_count,
                "successRate": metrics.get_success_rate(),
                "avgExecutionTimeSeconds": metrics.get_avg_execution_time(),
            }
        
        # Convert tool metrics
        tool_metrics_dict = {}
        for tool_name, metrics in self.tool_metrics.items():
            tool_metrics_dict[tool_name] = {
                "invocationCount": metrics.invocation_count,
                "successCount": metrics.success_count,
                "failureCount": metrics.failure_count,
                "successRate": metrics.get_success_rate(),
                "failureRate": metrics.get_failure_rate(),
                "avgLatencySeconds": metrics.get_avg_latency(),
                "avgRetries": metrics.get_avg_retries(),
                "p50LatencySeconds": metrics.get_p50_latency(),
                "p95LatencySeconds": metrics.get_p95_latency(),
                "p99LatencySeconds": metrics.get_p99_latency(),
            }
        
        # Convert approval queue metrics
        approval_metrics_dict = {
            "pendingCount": self.approval_queue_metrics.pending_count,
            "avgPendingAgeSeconds": self.approval_queue_metrics.get_avg_pending_age(),
            "oldestPendingAgeSeconds": self.approval_queue_metrics.oldest_pending_age_seconds,
            "approvalCount": self.approval_queue_metrics.approval_count,
            "rejectionCount": self.approval_queue_metrics.rejection_count,
            "timeoutCount": self.approval_queue_metrics.timeout_count,
        }
        
        # Convert exception type recurrence
        recurrence_dict = {}
        for exception_type, recurrence in self.exception_type_recurrence.items():
            recurrence_dict[exception_type] = {
                "occurrenceCount": recurrence.occurrence_count,
                "uniqueCount": recurrence.get_unique_count(),
                "recurrenceRate": recurrence.get_recurrence_rate(),
                "firstSeen": recurrence.first_seen.isoformat() if recurrence.first_seen else None,
                "lastSeen": recurrence.last_seen.isoformat() if recurrence.last_seen else None,
                "uniqueExceptionIds": list(recurrence.unique_exception_ids),  # For persistence
            }
        
        # Convert confidence distribution
        confidence_dict = {
            "sampleCount": len(self.confidence_distribution.samples),
            "avgConfidence": self.confidence_distribution.get_avg_confidence(),
            "medianConfidence": self.confidence_distribution.get_median_confidence(),
            "countByRange": self.confidence_distribution.count_by_range.copy(),
        }
        
        return {
            "tenantId": self.tenant_id,
            "exceptionCount": self.exception_count,
            "autoResolutionRate": self.get_auto_resolution_rate(),
            "mttrSeconds": self.get_mttr_seconds(),
            "actionableApprovedCount": self.actionable_approved_count,
            "actionableNonApprovedCount": self.actionable_non_approved_count,
            "nonActionableCount": self.non_actionable_count,
            "escalatedCount": self.escalated_count,
            "autoResolutionCount": self.auto_resolution_count,
            # Phase 2: Rich metrics
            "playbookMetrics": playbook_metrics_dict,
            "toolMetrics": tool_metrics_dict,
            "approvalQueueMetrics": approval_metrics_dict,
            "exceptionTypeRecurrence": recurrence_dict,
            "confidenceDistribution": confidence_dict,
        }

    def to_dict_for_persistence(self) -> dict[str, Any]:
        """
        Convert metrics to dictionary for persistence (includes all data).
        
        Returns:
            Dictionary suitable for JSON serialization
        """
        data = self.to_dict()
        # Add additional fields for persistence
        data["lastUpdated"] = datetime.now(timezone.utc).isoformat()
        return data


class MetricsCollector:
    """
    Metrics collector with per-tenant isolation.
    
    Phase 2: Extended with rich metrics collection and persistence.
    
    Tracks exception processing metrics per tenant:
    - Basic metrics (exceptionCount, autoResolutionRate, mttrSeconds, etc.)
    - Per-playbook success rates
    - Per-tool latency, retry counts, failure rates
    - Approval queue aging
    - Recurrence stats by exceptionType
    - Confidence distribution
    """

    def __init__(self, storage_root: str = "./runtime/metrics"):
        """
        Initialize metrics collector.
        
        Args:
            storage_root: Root directory for metrics persistence
        """
        self._metrics: dict[str, TenantMetrics] = {}
        self.storage_root = Path(storage_root)
        self.storage_root.mkdir(parents=True, exist_ok=True)

    def get_or_create_metrics(self, tenant_id: str) -> TenantMetrics:
        """
        Get or create metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            TenantMetrics instance
        """
        if tenant_id not in self._metrics:
            self._metrics[tenant_id] = TenantMetrics(tenant_id=tenant_id)
            logger.info(f"Created metrics tracking for tenant {tenant_id}")
        
        return self._metrics[tenant_id]

    def record_exception(
        self,
        tenant_id: str,
        status: str,
        actionability: str | None = None,
        resolution_time_seconds: float = 0.0,
        exception_type: str | None = None,
        exception_id: str | None = None,
        confidence: float | None = None,
    ) -> None:
        """
        Record an exception processing result.
        
        Args:
            tenant_id: Tenant identifier
            status: Final status (RESOLVED, ESCALATED, IN_PROGRESS, OPEN)
            actionability: Actionability classification (if available)
            resolution_time_seconds: Time taken to resolve (for MVP, approximate)
            exception_type: Exception type (for recurrence tracking)
            exception_id: Exception ID (for recurrence tracking)
            confidence: Confidence score (for distribution tracking)
        """
        metrics = self.get_or_create_metrics(tenant_id)
        metrics.exception_count += 1
        
        # Track actionability
        if actionability == "ACTIONABLE_APPROVED_PROCESS":
            metrics.actionable_approved_count += 1
        elif actionability == "ACTIONABLE_NON_APPROVED_PROCESS":
            metrics.actionable_non_approved_count += 1
        elif actionability == "NON_ACTIONABLE_INFO_ONLY":
            metrics.non_actionable_count += 1
        
        # Track resolution status
        if status == "RESOLVED":
            metrics.auto_resolution_count += 1
            if resolution_time_seconds > 0:
                metrics.total_resolution_time_seconds += resolution_time_seconds
                metrics.resolution_timestamps.append(datetime.now(timezone.utc))
        elif status == "ESCALATED":
            metrics.escalated_count += 1
        
        # Track exception type recurrence
        if exception_type:
            recurrence = metrics.get_or_create_exception_type_recurrence(exception_type)
            recurrence.occurrence_count += 1
            now = datetime.now(timezone.utc)
            if recurrence.first_seen is None:
                recurrence.first_seen = now
            recurrence.last_seen = now
            if exception_id:
                recurrence.unique_exception_ids.add(exception_id)
        
        # Track confidence distribution
        if confidence is not None:
            metrics.confidence_distribution.add_sample(confidence)
        
        logger.debug(
            f"Recorded exception for tenant {tenant_id}: status={status}, "
            f"actionability={actionability}, exception_type={exception_type}"
        )

    def record_playbook_execution(
        self,
        tenant_id: str,
        playbook_id: str,
        success: bool,
        execution_time_seconds: float = 0.0,
    ) -> None:
        """
        Record a playbook execution.
        
        Args:
            tenant_id: Tenant identifier
            playbook_id: Playbook identifier
            success: Whether execution was successful
            execution_time_seconds: Execution time in seconds
        """
        metrics = self.get_or_create_metrics(tenant_id)
        playbook_metrics = metrics.get_or_create_playbook_metrics(playbook_id)
        
        playbook_metrics.execution_count += 1
        if success:
            playbook_metrics.success_count += 1
        else:
            playbook_metrics.failure_count += 1
        
        playbook_metrics.total_execution_time_seconds += execution_time_seconds
        
        logger.debug(
            f"Recorded playbook execution for tenant {tenant_id}: "
            f"playbook={playbook_id}, success={success}, time={execution_time_seconds}s"
        )

    def record_tool_invocation(
        self,
        tenant_id: str,
        tool_name: str,
        success: bool,
        latency_seconds: float = 0.0,
        retry_count: int = 0,
    ) -> None:
        """
        Record a tool invocation.
        
        Args:
            tenant_id: Tenant identifier
            tool_name: Tool name
            success: Whether invocation was successful
            latency_seconds: Latency in seconds
            retry_count: Number of retries
        """
        metrics = self.get_or_create_metrics(tenant_id)
        tool_metrics = metrics.get_or_create_tool_metrics(tool_name)
        
        tool_metrics.invocation_count += 1
        if success:
            tool_metrics.success_count += 1
        else:
            tool_metrics.failure_count += 1
        
        tool_metrics.total_retry_count += retry_count
        tool_metrics.total_latency_seconds += latency_seconds
        tool_metrics.latency_samples.append(latency_seconds)
        
        # Keep only last 1000 samples for percentile calculations
        if len(tool_metrics.latency_samples) > 1000:
            tool_metrics.latency_samples = tool_metrics.latency_samples[-1000:]
        
        logger.debug(
            f"Recorded tool invocation for tenant {tenant_id}: "
            f"tool={tool_name}, success={success}, latency={latency_seconds}s, retries={retry_count}"
        )

    def update_approval_queue_metrics(
        self,
        tenant_id: str,
        pending_approvals: list[dict[str, Any]],
        approval_count: int = 0,
        rejection_count: int = 0,
        timeout_count: int = 0,
    ) -> None:
        """
        Update approval queue metrics.
        
        Args:
            tenant_id: Tenant identifier
            pending_approvals: List of pending approval dicts with 'submitted_at' timestamp
            approval_count: Total approval count (incremental)
            rejection_count: Total rejection count (incremental)
            timeout_count: Total timeout count (incremental)
        """
        metrics = self.get_or_create_metrics(tenant_id)
        queue_metrics = metrics.approval_queue_metrics
        
        queue_metrics.pending_count = len(pending_approvals)
        queue_metrics.approval_count += approval_count
        queue_metrics.rejection_count += rejection_count
        queue_metrics.timeout_count += timeout_count
        
        # Calculate aging metrics
        now = datetime.now(timezone.utc)
        total_age = 0.0
        oldest_age = 0.0
        
        for approval in pending_approvals:
            submitted_at_str = approval.get("submitted_at")
            if submitted_at_str:
                try:
                    if isinstance(submitted_at_str, str):
                        submitted_at = datetime.fromisoformat(submitted_at_str.replace("Z", "+00:00"))
                    else:
                        submitted_at = submitted_at_str
                    
                    age_seconds = (now - submitted_at).total_seconds()
                    total_age += age_seconds
                    oldest_age = max(oldest_age, age_seconds)
                except Exception as e:
                    logger.warning(f"Failed to parse approval timestamp: {e}")
        
        queue_metrics.total_pending_age_seconds = total_age
        queue_metrics.oldest_pending_age_seconds = oldest_age
        
        logger.debug(
            f"Updated approval queue metrics for tenant {tenant_id}: "
            f"pending={queue_metrics.pending_count}, avg_age={queue_metrics.get_avg_pending_age()}s"
        )

    def record_explanation_generated(
        self,
        tenant_id: str,
        exception_id: str,
        latency_ms: float,
        quality_score: Optional[float] = None,
    ) -> None:
        """
        Record explanation generation metrics.
        
        Phase 3: Tracks explanation generation for analytics (P3-31).
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            latency_ms: Generation latency in milliseconds
            quality_score: Optional quality score
        """
        metrics = self.get_or_create_metrics(tenant_id)
        
        # Increment total count
        metrics.explanations_generated_total += 1
        
        # Track per-exception count
        if exception_id not in metrics.explanations_per_exception:
            metrics.explanations_per_exception[exception_id] = 0
        metrics.explanations_per_exception[exception_id] += 1
        
        # Record latency
        metrics.explanation_latency_samples.append(latency_ms)
        
        # Record quality score if provided
        if quality_score is not None:
            metrics.explanation_quality_scores.append(quality_score)
        
        logger.debug(
            f"Recorded explanation metrics for tenant {tenant_id}, "
            f"exception {exception_id}, latency={latency_ms}ms, quality={quality_score}"
        )

    def record_violation(
        self,
        tenant_id: str,
        violation_type: str,
        severity: str,
    ) -> None:
        """
        Record a violation (policy or tool).
        
        Args:
            tenant_id: Tenant identifier
            violation_type: Type of violation ("policy" or "tool")
            severity: Severity level ("LOW", "MEDIUM", "HIGH", "CRITICAL")
        """
        metrics = self.get_or_create_metrics(tenant_id)
        violation_metrics = metrics.violation_metrics
        
        if violation_type == "policy":
            violation_metrics.policy_violation_count += 1
        elif violation_type == "tool":
            violation_metrics.tool_violation_count += 1
        
        # Track by severity
        if severity in violation_metrics.violation_count_by_severity:
            violation_metrics.violation_count_by_severity[severity] += 1
        
        logger.debug(
            f"Recorded violation for tenant {tenant_id}: "
            f"type={violation_type}, severity={severity}"
        )

    def record_pipeline_run(
        self, tenant_id: str, results: list[dict[str, Any]]
    ) -> None:
        """
        Record metrics from a pipeline run.
        
        Args:
            tenant_id: Tenant identifier
            results: List of exception processing results from pipeline
        """
        for result in results:
            status = result.get("status", "UNKNOWN")
            actionability = None
            
            # Extract actionability from stages if available
            stages = result.get("stages", {})
            if "policy" in stages and isinstance(stages["policy"], dict):
                policy_evidence = stages["policy"].get("evidence", [])
                for evidence in policy_evidence:
                    if "Actionability:" in evidence:
                        actionability = evidence.split("Actionability:")[1].strip()
                        break
            
            # Extract confidence from stages
            confidence = None
            for stage_name, stage_data in stages.items():
                if isinstance(stage_data, dict) and "confidence" in stage_data:
                    confidence = stage_data.get("confidence")
                    break
            
            # Extract exception type and ID
            exception_type = None
            exception_id = None
            exception = result.get("exception")
            if exception:
                if isinstance(exception, dict):
                    exception_type = exception.get("exception_type") or exception.get("exceptionType")
                    exception_id = exception.get("exception_id") or exception.get("exceptionId")
                else:
                    exception_type = getattr(exception, "exception_type", None)
                    exception_id = getattr(exception, "exception_id", None)
            
            # Calculate approximate resolution time (for MVP)
            # In production, this would track actual timestamps
            resolution_time_seconds = 0.0
            if status == "RESOLVED":
                # Approximate: assume 1 second per stage completed
                completed_stages = sum(
                    1 for stage in stages.values() if isinstance(stage, dict) and "error" not in stage
                )
                resolution_time_seconds = completed_stages * 1.0
            
            self.record_exception(
                tenant_id,
                status,
                actionability,
                resolution_time_seconds,
                exception_type=exception_type,
                exception_id=exception_id,
                confidence=confidence,
            )

    def get_metrics(self, tenant_id: str) -> dict[str, Any]:
        """
        Get metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with all metrics for the tenant
        """
        metrics = self.get_or_create_metrics(tenant_id)
        return metrics.to_dict()

    def get_all_metrics(self) -> dict[str, dict[str, Any]]:
        """
        Get metrics for all tenants.
        
        Returns:
            Dictionary mapping tenant_id to metrics
        """
        return {tenant_id: metrics.to_dict() for tenant_id, metrics in self._metrics.items()}

    def persist_metrics(self, tenant_id: str) -> None:
        """
        Persist metrics for a tenant to disk.
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id not in self._metrics:
            return
        
        metrics = self._metrics[tenant_id]
        metrics_file = self.storage_root / f"{tenant_id}.json"
        
        try:
            data = metrics.to_dict_for_persistence()
            with open(metrics_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.debug(f"Persisted metrics for tenant {tenant_id} to {metrics_file}")
        except Exception as e:
            logger.error(f"Failed to persist metrics for tenant {tenant_id}: {e}")

    def persist_all_metrics(self) -> None:
        """Persist metrics for all tenants."""
        for tenant_id in self._metrics.keys():
            self.persist_metrics(tenant_id)

    def load_metrics(self, tenant_id: str) -> bool:
        """
        Load metrics for a tenant from disk.
        
        Args:
            tenant_id: Tenant identifier
            
        Returns:
            True if metrics were loaded, False otherwise
        """
        metrics_file = self.storage_root / f"{tenant_id}.json"
        
        if not metrics_file.exists():
            return False
        
        try:
            with open(metrics_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Reconstruct metrics from data
            metrics = TenantMetrics(tenant_id=tenant_id)
            
            # Load basic metrics
            metrics.exception_count = data.get("exceptionCount", 0)
            metrics.auto_resolution_count = data.get("autoResolutionCount", 0)
            metrics.actionable_approved_count = data.get("actionableApprovedCount", 0)
            metrics.actionable_non_approved_count = data.get("actionableNonApprovedCount", 0)
            metrics.non_actionable_count = data.get("nonActionableCount", 0)
            metrics.escalated_count = data.get("escalatedCount", 0)
            
            # Load playbook metrics
            playbook_data = data.get("playbookMetrics", {})
            for playbook_id, pm_data in playbook_data.items():
                pm = PlaybookMetrics(playbook_id=playbook_id)
                pm.execution_count = pm_data.get("executionCount", 0)
                pm.success_count = pm_data.get("successCount", 0)
                pm.failure_count = pm_data.get("failureCount", 0)
                pm.total_execution_time_seconds = pm_data.get("avgExecutionTimeSeconds", 0.0) * pm.execution_count
                metrics.playbook_metrics[playbook_id] = pm
            
            # Load tool metrics
            tool_data = data.get("toolMetrics", {})
            for tool_name, tm_data in tool_data.items():
                tm = ToolMetrics(tool_name=tool_name)
                tm.invocation_count = tm_data.get("invocationCount", 0)
                tm.success_count = tm_data.get("successCount", 0)
                tm.failure_count = tm_data.get("failureCount", 0)
                tm.total_retry_count = int(tm_data.get("avgRetries", 0.0) * tm.invocation_count)
                avg_latency = tm_data.get("avgLatencySeconds", 0.0)
                tm.total_latency_seconds = avg_latency * tm.invocation_count
                # Reconstruct samples from percentiles (approximate)
                if tm.invocation_count > 0:
                    p50 = tm_data.get("p50LatencySeconds", avg_latency)
                    p95 = tm_data.get("p95LatencySeconds", avg_latency * 1.5)
                    p99 = tm_data.get("p99LatencySeconds", avg_latency * 2.0)
                    # Create approximate samples
                    samples = [avg_latency] * max(1, tm.invocation_count // 10)
                    samples.extend([p50] * max(1, tm.invocation_count // 2))
                    samples.extend([p95] * max(1, tm.invocation_count // 20))
                    samples.extend([p99] * max(1, tm.invocation_count // 100))
                    tm.latency_samples = samples[:1000]  # Limit to 1000
                metrics.tool_metrics[tool_name] = tm
            
            # Load approval queue metrics
            approval_data = data.get("approvalQueueMetrics", {})
            metrics.approval_queue_metrics = ApprovalQueueMetrics(
                pending_count=approval_data.get("pendingCount", 0),
                total_pending_age_seconds=approval_data.get("avgPendingAgeSeconds", 0.0) * approval_data.get("pendingCount", 0),
                oldest_pending_age_seconds=approval_data.get("oldestPendingAgeSeconds", 0.0),
                approval_count=approval_data.get("approvalCount", 0),
                rejection_count=approval_data.get("rejectionCount", 0),
                timeout_count=approval_data.get("timeoutCount", 0),
            )
            
            # Load exception type recurrence
            recurrence_data = data.get("exceptionTypeRecurrence", {})
            for exception_type, rec_data in recurrence_data.items():
                rec = ExceptionTypeRecurrence(exception_type=exception_type)
                rec.occurrence_count = rec_data.get("occurrenceCount", 0)
                rec.unique_exception_ids = set(rec_data.get("uniqueExceptionIds", []))
                first_seen_str = rec_data.get("firstSeen")
                if first_seen_str:
                    rec.first_seen = datetime.fromisoformat(first_seen_str.replace("Z", "+00:00"))
                last_seen_str = rec_data.get("lastSeen")
                if last_seen_str:
                    rec.last_seen = datetime.fromisoformat(last_seen_str.replace("Z", "+00:00"))
                metrics.exception_type_recurrence[exception_type] = rec
            
            # Load confidence distribution
            conf_data = data.get("confidenceDistribution", {})
            metrics.confidence_distribution = ConfidenceDistribution()
            metrics.confidence_distribution.count_by_range = conf_data.get("countByRange", {
                "0.0-0.5": 0,
                "0.5-0.7": 0,
                "0.7-0.9": 0,
                "0.9-1.0": 0,
            })
            # Reconstruct samples from average (approximate)
            avg_conf = conf_data.get("avgConfidence", 0.0)
            sample_count = conf_data.get("sampleCount", 0)
            if sample_count > 0:
                metrics.confidence_distribution.samples = [avg_conf] * min(sample_count, 1000)
            
            self._metrics[tenant_id] = metrics
            logger.info(f"Loaded metrics for tenant {tenant_id} from {metrics_file}")
            return True
        except Exception as e:
            logger.error(f"Failed to load metrics for tenant {tenant_id}: {e}")
            return False

    def reset_metrics(self, tenant_id: str) -> None:
        """
        Reset metrics for a tenant.
        
        Args:
            tenant_id: Tenant identifier
        """
        if tenant_id in self._metrics:
            self._metrics[tenant_id] = TenantMetrics(tenant_id=tenant_id)
            logger.info(f"Reset metrics for tenant {tenant_id}")

    def clear_all_metrics(self) -> None:
        """Clear all metrics for all tenants."""
        self._metrics.clear()
        logger.info("Cleared all metrics")
