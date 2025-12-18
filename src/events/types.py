"""
Canonical Event Types for Phase 9.

Defines all event type classes that extend CanonicalEvent.
Each event type represents a specific occurrence in the exception processing pipeline.

Reference: docs/phase9-async-scale-mvp.md Section 4
"""

from typing import Any, Optional

from pydantic import Field

from src.events.schema import CanonicalEvent


# ============================================================================
# Inbound Events
# ============================================================================


class ExceptionIngested(CanonicalEvent):
    """
    Event emitted when a raw exception is ingested via API.
    
    Phase 9 P9-16: First event in the pipeline, published by ingestion API.
    """
    
    event_type: str = Field(default="ExceptionIngested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        raw_payload: dict[str, Any],
        source_system: str,
        ingestion_method: str = "api",
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ExceptionIngested":
        """Create ExceptionIngested event."""
        payload = {
            "raw_payload": raw_payload,
            "source_system": source_system,
            "ingestion_method": ingestion_method,
        }
        return super().create(
            event_type="ExceptionIngested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class ExceptionNormalized(CanonicalEvent):
    """
    Event emitted when an exception is normalized by IntakeWorker.
    
    Phase 9 P9-16: Published by IntakeWorker after normalization.
    """
    
    event_type: str = Field(default="ExceptionNormalized", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        normalized_exception: dict[str, Any],
        normalization_rules: Optional[dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ExceptionNormalized":
        """Create ExceptionNormalized event."""
        payload = {
            "normalized_exception": normalized_exception,
            "normalization_rules": normalization_rules or {},
        }
        return super().create(
            event_type="ExceptionNormalized",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class ManualExceptionCreated(CanonicalEvent):
    """
    Event emitted when an exception is manually created (not ingested).
    
    Phase 9: For manual exception creation via UI or admin API.
    """
    
    event_type: str = Field(default="ManualExceptionCreated", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        exception_data: dict[str, Any],
        created_by: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ManualExceptionCreated":
        """Create ManualExceptionCreated event."""
        payload = {
            "exception_data": exception_data,
            "created_by": created_by,
        }
        return super().create(
            event_type="ManualExceptionCreated",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


# ============================================================================
# Agent Events
# ============================================================================


class TriageRequested(CanonicalEvent):
    """
    Event emitted when triage is requested for an exception.
    
    Phase 9: Published by TriageWorker before processing.
    """
    
    event_type: str = Field(default="TriageRequested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "TriageRequested":
        """Create TriageRequested event."""
        return super().create(
            event_type="TriageRequested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload={},
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class TriageCompleted(CanonicalEvent):
    """
    Event emitted when triage is completed for an exception.
    
    Phase 9: Published by TriageWorker after classification.
    """
    
    event_type: str = Field(default="TriageCompleted", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        triage_result: dict[str, Any],
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "TriageCompleted":
        """Create TriageCompleted event."""
        return super().create(
            event_type="TriageCompleted",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=triage_result,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class PolicyEvaluationRequested(CanonicalEvent):
    """
    Event emitted when policy evaluation is requested.
    
    Phase 9: Published by PolicyWorker before evaluation.
    """
    
    event_type: str = Field(default="PolicyEvaluationRequested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "PolicyEvaluationRequested":
        """Create PolicyEvaluationRequested event."""
        return super().create(
            event_type="PolicyEvaluationRequested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload={},
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class PolicyEvaluationCompleted(CanonicalEvent):
    """
    Event emitted when policy evaluation is completed.
    
    Phase 9: Published by PolicyWorker after evaluation.
    """
    
    event_type: str = Field(default="PolicyEvaluationCompleted", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        policy_result: dict[str, Any],
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "PolicyEvaluationCompleted":
        """Create PolicyEvaluationCompleted event."""
        return super().create(
            event_type="PolicyEvaluationCompleted",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=policy_result,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class PlaybookMatched(CanonicalEvent):
    """
    Event emitted when a playbook is matched to an exception.
    
    Phase 9: Published by PolicyWorker when playbook is assigned.
    """
    
    event_type: str = Field(default="PlaybookMatched", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        playbook_id: int,
        playbook_name: str,
        match_reason: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "PlaybookMatched":
        """Create PlaybookMatched event."""
        payload = {
            "playbook_id": playbook_id,
            "playbook_name": playbook_name,
            "match_reason": match_reason,
        }
        return super().create(
            event_type="PlaybookMatched",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class PlaybookRecalculationRequested(CanonicalEvent):
    """
    Event emitted when playbook recalculation is requested.
    
    Phase 9 P9-17: Published by API when recalculation is requested.
    """
    
    event_type: str = Field(default="PlaybookRecalculationRequested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        requested_by: str,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "PlaybookRecalculationRequested":
        """Create PlaybookRecalculationRequested event."""
        payload = {
            "requested_by": requested_by,
        }
        return super().create(
            event_type="PlaybookRecalculationRequested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class PlaybookStepCompletionRequested(CanonicalEvent):
    """
    Event emitted when playbook step completion is requested.
    
    Phase 9 P9-17: Published by API when step completion is requested.
    """
    
    event_type: str = Field(default="PlaybookStepCompletionRequested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        step_order: int,
        actor_type: str,
        actor_id: str,
        notes: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "PlaybookStepCompletionRequested":
        """Create PlaybookStepCompletionRequested event."""
        payload = {
            "step_order": step_order,
            "actor_type": actor_type,
            "actor_id": actor_id,
            "notes": notes,
        }
        return super().create(
            event_type="PlaybookStepCompletionRequested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class StepExecutionRequested(CanonicalEvent):
    """
    Event emitted when a playbook step execution is requested.
    
    Phase 9: Published by PlaybookWorker for step execution.
    """
    
    event_type: str = Field(default="StepExecutionRequested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        playbook_id: int,
        step_order: int,
        step_action: dict[str, Any],
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "StepExecutionRequested":
        """Create StepExecutionRequested event."""
        payload = {
            "playbook_id": playbook_id,
            "step_order": step_order,
            "step_action": step_action,
        }
        return super().create(
            event_type="StepExecutionRequested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class ToolExecutionRequested(CanonicalEvent):
    """
    Event emitted when tool execution is requested.
    
    Phase 9 P9-18: Published by API when tool execution is requested.
    """
    
    event_type: str = Field(default="ToolExecutionRequested", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        tool_id: int,
        execution_id: str,
        input_payload: dict[str, Any],
        exception_id: Optional[str] = None,
        requested_by_actor_type: str = "system",
        requested_by_actor_id: str = "api",
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ToolExecutionRequested":
        """Create ToolExecutionRequested event."""
        payload = {
            "tool_id": tool_id,
            "execution_id": execution_id,
            "input_payload": input_payload,
            "requested_by_actor_type": requested_by_actor_type,
            "requested_by_actor_id": requested_by_actor_id,
        }
        return super().create(
            event_type="ToolExecutionRequested",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class ToolExecutionCompleted(CanonicalEvent):
    """
    Event emitted when tool execution is completed.
    
    Phase 9: Published by ToolWorker after execution.
    """
    
    event_type: str = Field(default="ToolExecutionCompleted", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        tool_id: int,
        execution_id: str,
        status: str,
        output_payload: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "ToolExecutionCompleted":
        """Create ToolExecutionCompleted event."""
        payload = {
            "tool_id": tool_id,
            "execution_id": execution_id,
            "status": status,
            "output_payload": output_payload,
            "error_message": error_message,
        }
        return super().create(
            event_type="ToolExecutionCompleted",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class FeedbackCaptured(CanonicalEvent):
    """
    Event emitted when feedback is captured for an exception.
    
    Phase 9: Published by FeedbackWorker after resolution.
    """
    
    event_type: str = Field(default="FeedbackCaptured", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        feedback_data: dict[str, Any],
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "FeedbackCaptured":
        """Create FeedbackCaptured event."""
        return super().create(
            event_type="FeedbackCaptured",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=feedback_data,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


# ============================================================================
# Control & Ops Events
# ============================================================================


class RetryScheduled(CanonicalEvent):
    """
    Event emitted when an event is scheduled for retry.
    
    Phase 9: Published by RetryScheduler.
    """
    
    event_type: str = Field(default="RetryScheduled", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        original_event_id: str,
        retry_count: int,
        retry_after_seconds: float,
        error_message: str,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "RetryScheduled":
        """Create RetryScheduled event."""
        payload = {
            "original_event_id": original_event_id,
            "retry_count": retry_count,
            "retry_after_seconds": retry_after_seconds,
            "error_message": error_message,
        }
        return super().create(
            event_type="RetryScheduled",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id,
            metadata=metadata,
            **kwargs,
        )


class DeadLettered(CanonicalEvent):
    """
    Event emitted when an event is moved to Dead Letter Queue.
    
    Phase 9: Published by RetryScheduler after max retries exceeded.
    """
    
    event_type: str = Field(default="DeadLettered", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        original_event_id: str,
        original_event_type: str,
        failure_reason: str,
        retry_count: int,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "DeadLettered":
        """Create DeadLettered event."""
        payload = {
            "original_event_id": original_event_id,
            "original_event_type": original_event_type,
            "failure_reason": failure_reason,
            "retry_count": retry_count,
        }
        return super().create(
            event_type="DeadLettered",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id,
            metadata=metadata,
            **kwargs,
        )


class SLAImminent(CanonicalEvent):
    """
    Event emitted when SLA deadline is approaching.
    
    Phase 9 P9-22: Published by SLAMonitorWorker at threshold.
    """
    
    event_type: str = Field(default="SLAImminent", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        sla_deadline: str,
        time_remaining_seconds: float,
        threshold_percent: float,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "SLAImminent":
        """Create SLAImminent event."""
        payload = {
            "sla_deadline": sla_deadline,
            "time_remaining_seconds": time_remaining_seconds,
            "threshold_percent": threshold_percent,
        }
        return super().create(
            event_type="SLAImminent",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class SLAExpired(CanonicalEvent):
    """
    Event emitted when SLA deadline is breached.
    
    Phase 9 P9-22: Published by SLAMonitorWorker at breach.
    """
    
    event_type: str = Field(default="SLAExpired", frozen=True)
    
    @classmethod
    def create(
        cls,
        tenant_id: str,
        exception_id: str,
        sla_deadline: str,
        breach_seconds: float,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "SLAExpired":
        """Create SLAExpired event."""
        payload = {
            "sla_deadline": sla_deadline,
            "breach_seconds": breach_seconds,
        }
        return super().create(
            event_type="SLAExpired",
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload=payload,
            correlation_id=correlation_id or exception_id,
            metadata=metadata,
            **kwargs,
        )


class BackpressureDetected(CanonicalEvent):
    """
    Event emitted when backpressure is detected (rate limit exceeded).

    Phase 9 P9-27: Backpressure Protection.

    Payload structure:
        tenant_id: Tenant identifier
        rate_limit_type: Type of rate limit ("events_per_second", "events_per_minute", "burst")
        current_rate: Current rate (events per time unit)
        limit: Configured limit
        wait_seconds: Estimated wait time before retry
    """

    event_type: str = Field(default="BackpressureDetected", frozen=True)

    @classmethod
    def create(
        cls,
        tenant_id: str,
        rate_limit_type: str,
        current_rate: float,
        limit: float,
        wait_seconds: float,
        exception_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        metadata: Optional[dict[str, Any]] = None,
        **kwargs: Any,
    ) -> "BackpressureDetected":
        """Create BackpressureDetected event."""
        payload = {
            "rate_limit_type": rate_limit_type,
            "current_rate": current_rate,
            "limit": limit,
            "wait_seconds": wait_seconds,
        }
        return super().create(
            event_type="BackpressureDetected",
            tenant_id=tenant_id,
            payload=payload,
            exception_id=exception_id,
            correlation_id=correlation_id,
            metadata=metadata,
            **kwargs,
        )
