"""
Backpressure and Rate Control for Streaming (P3-19).

Protects vector DB, tool execution engine, and orchestrator from overload
via backpressure, rate limiting, and adaptive control.

Matches specification from phase3-mvp-issues.md P3-19.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class BackpressureState(Enum):
    """Backpressure state."""

    NORMAL = "normal"  # No backpressure, normal operation
    WARNING = "warning"  # Approaching limits, slow down
    CRITICAL = "critical"  # At limits, pause consumption
    OVERLOADED = "overloaded"  # Over limits, drop low-priority messages


@dataclass
class QueueMetrics:
    """Metrics for a queue."""

    current_depth: int = 0
    max_depth: int = 0
    total_enqueued: int = 0
    total_dequeued: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_utilization(self) -> float:
        """Calculate queue utilization (0.0 to 1.0)."""
        if self.max_depth == 0:
            return 0.0
        return min(1.0, self.current_depth / self.max_depth)

    def update_depth(self, depth: int) -> None:
        """Update current depth."""
        self.current_depth = depth
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class InFlightMetrics:
    """Metrics for in-flight exceptions."""

    current_count: int = 0
    max_count: int = 0
    total_processed: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_utilization(self) -> float:
        """Calculate in-flight utilization (0.0 to 1.0)."""
        if self.max_count == 0:
            return 0.0
        return min(1.0, self.current_count / self.max_count)

    def increment(self) -> None:
        """Increment in-flight count."""
        self.current_count += 1
        self.total_processed += 1
        self.last_updated = datetime.now(timezone.utc)

    def decrement(self) -> None:
        """Decrement in-flight count."""
        if self.current_count > 0:
            self.current_count -= 1
        self.last_updated = datetime.now(timezone.utc)


@dataclass
class RateLimitMetrics:
    """Metrics for rate limiting per tenant."""

    tenant_id: str
    current_rate: float = 0.0  # Messages per second
    max_rate: float = 0.0  # Maximum allowed rate
    window_start: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0
    window_seconds: float = 1.0  # Time window for rate calculation

    def update_rate(self, messages: int, elapsed_seconds: float) -> None:
        """Update current rate."""
        if elapsed_seconds > 0:
            self.current_rate = messages / elapsed_seconds
        else:
            self.current_rate = 0.0
        self.message_count = messages
        self.last_updated = datetime.now(timezone.utc)

    def get_utilization(self) -> float:
        """Calculate rate limit utilization (0.0 to 1.0)."""
        if self.max_rate == 0:
            return 0.0
        return min(1.0, self.current_rate / self.max_rate)


@dataclass
class BackpressurePolicy:
    """
    Backpressure policy configuration.
    
    Defines thresholds and behavior for backpressure control.
    """

    max_queue_depth: int = 1000
    max_in_flight_exceptions: int = 100
    rate_limit_per_tenant: float = 100.0  # Messages per second per tenant
    warning_threshold: float = 0.7  # Warning at 70% utilization
    critical_threshold: float = 0.9  # Critical at 90% utilization
    drop_low_priority_enabled: bool = False  # Enable dropping low-priority messages in MVP
    adaptive_control_enabled: bool = True  # Enable adaptive rate control

    def get_state(
        self,
        queue_utilization: float,
        in_flight_utilization: float,
        rate_utilization: float,
    ) -> BackpressureState:
        """
        Determine backpressure state based on utilizations.
        
        Args:
            queue_utilization: Queue depth utilization (0.0 to 1.0)
            in_flight_utilization: In-flight exceptions utilization (0.0 to 1.0)
            rate_utilization: Rate limit utilization (0.0 to 1.0)
            
        Returns:
            BackpressureState
        """
        # Use maximum utilization across all metrics
        max_utilization = max(queue_utilization, in_flight_utilization, rate_utilization)
        
        if max_utilization >= self.critical_threshold:
            return BackpressureState.OVERLOADED
        elif max_utilization >= self.warning_threshold:
            return BackpressureState.CRITICAL
        elif max_utilization >= self.warning_threshold * 0.5:  # 35% for warning
            return BackpressureState.WARNING
        else:
            return BackpressureState.NORMAL


class BackpressureController:
    """
    Controller for backpressure and rate limiting.
    
    Monitors queue depth, in-flight exceptions, and rate limits.
    Provides control signals to slow down or pause consumption.
    """

    def __init__(
        self,
        policy: Optional[BackpressurePolicy] = None,
        metrics_collector: Optional[Any] = None,
    ):
        """
        Initialize backpressure controller.
        
        Args:
            policy: Backpressure policy (uses default if not provided)
            metrics_collector: Optional metrics collector for exposing metrics
        """
        self.policy = policy or BackpressurePolicy()
        self.metrics_collector = metrics_collector
        
        # Queue metrics
        self.queue_metrics = QueueMetrics()
        self.queue_metrics.max_depth = self.policy.max_queue_depth
        
        # In-flight metrics
        self.in_flight_metrics = InFlightMetrics()
        self.in_flight_metrics.max_count = self.policy.max_in_flight_exceptions
        
        # Rate limit metrics per tenant
        self.rate_limit_metrics: dict[str, RateLimitMetrics] = {}
        
        # Current state
        self.current_state = BackpressureState.NORMAL
        
        # Event callbacks
        self.on_state_change: Optional[Callable[[BackpressureState], None]] = None
        
        # Alert tracking
        self._last_alert_time: Optional[datetime] = None
        self._alert_cooldown_seconds = 60.0  # Don't alert more than once per minute

    def update_queue_depth(self, depth: int) -> None:
        """
        Update queue depth.
        
        Args:
            depth: Current queue depth
        """
        self.queue_metrics.update_depth(depth)
        self._check_state()

    def increment_in_flight(self) -> bool:
        """
        Increment in-flight exceptions count.
        
        Returns:
            True if allowed, False if limit exceeded
        """
        if self.in_flight_metrics.current_count >= self.policy.max_in_flight_exceptions:
            return False
        
        self.in_flight_metrics.increment()
        self._check_state()
        return True

    def decrement_in_flight(self) -> None:
        """Decrement in-flight exceptions count."""
        self.in_flight_metrics.decrement()
        self._check_state()

    def check_rate_limit(self, tenant_id: str, message_count: int = 1) -> bool:
        """
        Check if rate limit allows processing a message.
        
        Args:
            tenant_id: Tenant identifier
            message_count: Number of messages to check
            
        Returns:
            True if allowed, False if rate limit exceeded
        """
        # Get or create rate limit metrics for tenant
        if tenant_id not in self.rate_limit_metrics:
            self.rate_limit_metrics[tenant_id] = RateLimitMetrics(
                tenant_id=tenant_id,
                max_rate=self.policy.rate_limit_per_tenant,
            )
        
        metrics = self.rate_limit_metrics[tenant_id]
        
        # Calculate elapsed time since window start
        now = datetime.now(timezone.utc)
        elapsed = (now - metrics.window_start).total_seconds()
        
        # Reset window if it's been more than window_seconds
        if elapsed >= metrics.window_seconds:
            metrics.window_start = now
            metrics.message_count = 0
            elapsed = 0.0
        
        # Update rate
        new_count = metrics.message_count + message_count
        metrics.update_rate(new_count, elapsed + metrics.window_seconds)
        
        # Check if rate limit exceeded
        if metrics.current_rate > metrics.max_rate:
            return False
        
        # Update message count
        metrics.message_count = new_count
        self._check_state()
        return True

    def should_consume(self) -> bool:
        """
        Check if consumption should continue.
        
        Returns:
            True if consumption should continue, False if should pause
        """
        return self.current_state not in [BackpressureState.CRITICAL, BackpressureState.OVERLOADED]

    def should_drop_low_priority(self) -> bool:
        """
        Check if low-priority messages should be dropped.
        
        Returns:
            True if low-priority messages should be dropped
        """
        return (
            self.policy.drop_low_priority_enabled
            and self.current_state == BackpressureState.OVERLOADED
        )

    def get_adaptive_delay(self) -> float:
        """
        Get adaptive delay in seconds based on current state.
        
        Returns:
            Delay in seconds (0.0 for normal, increasing for warning/critical)
        """
        if self.current_state == BackpressureState.NORMAL:
            return 0.0
        elif self.current_state == BackpressureState.WARNING:
            return 0.1  # 100ms delay
        elif self.current_state == BackpressureState.CRITICAL:
            return 0.5  # 500ms delay
        else:  # OVERLOADED
            return 1.0  # 1 second delay

    def _check_state(self) -> None:
        """Check current state and emit alerts if needed."""
        queue_util = self.queue_metrics.get_utilization()
        in_flight_util = self.in_flight_metrics.get_utilization()
        
        # Calculate average rate utilization across all tenants
        rate_utils = [
            m.get_utilization() for m in self.rate_limit_metrics.values()
        ]
        rate_util = max(rate_utils) if rate_utils else 0.0
        
        new_state = self.policy.get_state(queue_util, in_flight_util, rate_util)
        
        if new_state != self.current_state:
            old_state = self.current_state
            self.current_state = new_state
            
            logger.warning(
                f"Backpressure state changed: {old_state.value} -> {new_state.value} "
                f"(queue_util={queue_util:.2f}, in_flight_util={in_flight_util:.2f}, "
                f"rate_util={rate_util:.2f})"
            )
            
            # Emit alert if cooldown expired
            now = datetime.now(timezone.utc)
            if (
                self._last_alert_time is None
                or (now - self._last_alert_time).total_seconds() >= self._alert_cooldown_seconds
            ):
                self._emit_alert(new_state, queue_util, in_flight_util, rate_util)
                self._last_alert_time = now
            
            # Call state change callback
            if self.on_state_change:
                try:
                    self.on_state_change(new_state)
                except Exception as e:
                    logger.error(f"Error in state change callback: {e}")

    def _emit_alert(
        self,
        state: BackpressureState,
        queue_util: float,
        in_flight_util: float,
        rate_util: float,
    ) -> None:
        """
        Emit alert for backpressure state change.
        
        Args:
            state: New backpressure state
            queue_util: Queue utilization
            in_flight_util: In-flight utilization
            rate_util: Rate utilization
        """
        alert_data = {
            "type": "backpressure_alert",
            "state": state.value,
            "queue_utilization": queue_util,
            "in_flight_utilization": in_flight_util,
            "rate_utilization": rate_util,
            "queue_depth": self.queue_metrics.current_depth,
            "max_queue_depth": self.queue_metrics.max_depth,
            "in_flight_count": self.in_flight_metrics.current_count,
            "max_in_flight": self.in_flight_metrics.max_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.warning(f"Backpressure alert: {alert_data}")
        
        # Expose metrics if metrics collector is available
        if self.metrics_collector:
            # Note: MetricsCollector doesn't have a direct method for backpressure metrics,
            # but we can log them or extend the metrics system in the future
            pass

    def get_metrics(self) -> dict[str, Any]:
        """
        Get current backpressure metrics.
        
        Returns:
            Dictionary with current metrics
        """
        rate_metrics = {}
        for tenant_id, metrics in self.rate_limit_metrics.items():
            rate_metrics[tenant_id] = {
                "current_rate": metrics.current_rate,
                "max_rate": metrics.max_rate,
                "utilization": metrics.get_utilization(),
            }
        
        return {
            "state": self.current_state.value,
            "queue": {
                "current_depth": self.queue_metrics.current_depth,
                "max_depth": self.queue_metrics.max_depth,
                "utilization": self.queue_metrics.get_utilization(),
            },
            "in_flight": {
                "current_count": self.in_flight_metrics.current_count,
                "max_count": self.in_flight_metrics.max_count,
                "utilization": self.in_flight_metrics.get_utilization(),
            },
            "rate_limits": rate_metrics,
        }


# Global backpressure controller instance
_backpressure_controller: Optional[BackpressureController] = None


def get_backpressure_controller(
    policy: Optional[BackpressurePolicy] = None,
    metrics_collector: Optional[Any] = None,
) -> BackpressureController:
    """
    Get the global backpressure controller instance.
    
    Args:
        policy: Optional backpressure policy (uses default if not provided)
        metrics_collector: Optional metrics collector
        
    Returns:
        BackpressureController instance
    """
    global _backpressure_controller
    if _backpressure_controller is None:
        _backpressure_controller = BackpressureController(policy, metrics_collector)
    return _backpressure_controller

