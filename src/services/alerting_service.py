"""
Alerting Service for Phase 10 (P10-7, P10-8).

Provides alert evaluation and notification dispatch functionality.

Reference: docs/phase10-ops-governance-mvp.md Section 6
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from typing import Optional

import httpx

from src.infrastructure.db.models import AlertConfig, AlertHistory, AlertType, AlertSeverity

logger = logging.getLogger(__name__)


@dataclass
class AlertCondition:
    """Represents a condition that may trigger an alert."""
    alert_type: str
    severity: str
    title: str
    message: str
    details: dict
    tenant_id: str


@dataclass
class NotificationResult:
    """Result of a notification attempt."""
    success: bool
    channel_type: str
    error: Optional[str] = None


class AlertingService:
    """
    Service for evaluating alert conditions and dispatching notifications.

    Responsibilities:
    - Evaluate conditions against thresholds
    - Check quiet hours and suppression rules
    - Dispatch notifications via webhook/email
    - Track notification status
    """

    # Default thresholds per alert type
    DEFAULT_THRESHOLDS = {
        AlertType.SLA_BREACH.value: {"threshold": 0, "unit": "immediate"},
        AlertType.SLA_IMMINENT.value: {"threshold": 80, "unit": "percent"},
        AlertType.DLQ_GROWTH.value: {"threshold": 100, "unit": "count"},
        AlertType.WORKER_UNHEALTHY.value: {"threshold": 3, "unit": "consecutive_failures"},
        AlertType.ERROR_RATE_HIGH.value: {"threshold": 5, "unit": "percent"},
        AlertType.THROUGHPUT_LOW.value: {"threshold": 50, "unit": "percent_drop"},
    }

    def __init__(
        self,
        http_client: Optional[httpx.AsyncClient] = None,
        timeout: float = 10.0,
    ):
        """
        Initialize the alerting service.

        Args:
            http_client: Optional HTTP client for webhooks
            timeout: Request timeout for notifications
        """
        self._client = http_client
        self._timeout = timeout
        self._owned_client = False

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self._timeout)
            self._owned_client = True
        return self._client

    async def close(self):
        """Close HTTP client if owned."""
        if self._owned_client and self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def is_in_quiet_hours(
        self,
        config: AlertConfig,
        current_time: Optional[datetime] = None,
    ) -> bool:
        """
        Check if current time is within quiet hours.

        Args:
            config: Alert configuration
            current_time: Time to check (defaults to now)

        Returns:
            True if in quiet hours, False otherwise
        """
        if not config.quiet_hours_start or not config.quiet_hours_end:
            return False

        if current_time is None:
            current_time = datetime.now(timezone.utc)

        current = current_time.time()
        start = config.quiet_hours_start
        end = config.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00 to 06:00)
        if start <= end:
            return start <= current <= end
        else:
            return current >= start or current <= end

    def should_trigger_alert(
        self,
        config: Optional[AlertConfig],
        current_value: float,
        alert_type: str,
        severity: str = "warning",
    ) -> bool:
        """
        Determine if an alert should be triggered.

        Args:
            config: Alert configuration (may be None for defaults)
            current_value: Current metric value
            alert_type: Type of alert
            severity: Alert severity

        Returns:
            True if alert should trigger, False otherwise
        """
        # If no config, use defaults
        if config is None:
            threshold = self.DEFAULT_THRESHOLDS.get(alert_type, {}).get("threshold", 0)
        elif not config.enabled:
            return False
        else:
            threshold = float(config.threshold) if config.threshold else 0

        # Check quiet hours for non-critical alerts
        if config and severity != "critical":
            if self.is_in_quiet_hours(config):
                logger.debug(f"Alert suppressed during quiet hours: {alert_type}")
                return False

        # Compare value against threshold
        # Different alert types have different comparison logic
        if alert_type == AlertType.SLA_BREACH.value:
            # SLA breach is immediate - always trigger
            return True
        elif alert_type == AlertType.SLA_IMMINENT.value:
            # Trigger when % of SLA window elapsed exceeds threshold
            return current_value >= threshold
        elif alert_type == AlertType.DLQ_GROWTH.value:
            # Trigger when DLQ count exceeds threshold
            return current_value >= threshold
        elif alert_type == AlertType.WORKER_UNHEALTHY.value:
            # Trigger after N consecutive failures
            return current_value >= threshold
        elif alert_type == AlertType.ERROR_RATE_HIGH.value:
            # Trigger when error rate % exceeds threshold
            return current_value >= threshold
        elif alert_type == AlertType.THROUGHPUT_LOW.value:
            # Trigger when throughput drops by threshold %
            return current_value >= threshold
        else:
            # Unknown type - use simple comparison
            return current_value >= threshold

    async def send_webhook(
        self,
        url: str,
        payload: dict,
    ) -> NotificationResult:
        """
        Send alert notification via webhook.

        Args:
            url: Webhook URL
            payload: JSON payload

        Returns:
            NotificationResult with status
        """
        try:
            client = await self._get_client()
            response = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook sent successfully: {url}")
                return NotificationResult(success=True, channel_type="webhook")
            else:
                error = f"HTTP {response.status_code}: {response.text[:200]}"
                logger.warning(f"Webhook failed: {url}, {error}")
                return NotificationResult(
                    success=False, channel_type="webhook", error=error
                )
        except httpx.TimeoutException:
            error = "Request timed out"
            logger.warning(f"Webhook timeout: {url}")
            return NotificationResult(
                success=False, channel_type="webhook", error=error
            )
        except Exception as e:
            error = str(e)
            logger.error(f"Webhook error: {url}, {error}")
            return NotificationResult(
                success=False, channel_type="webhook", error=error
            )

    async def send_email(
        self,
        address: str,
        subject: str,
        body: str,
    ) -> NotificationResult:
        """
        Send alert notification via email.

        Note: Email sending requires SMTP or email service configuration.
        This is a placeholder that logs the email for MVP.

        Args:
            address: Email address
            subject: Email subject
            body: Email body

        Returns:
            NotificationResult with status
        """
        # MVP: Log email instead of sending
        # In production, integrate with SMTP or SendGrid
        logger.info(
            f"Email notification (not sent in MVP): "
            f"to={address}, subject={subject}"
        )
        return NotificationResult(
            success=True,
            channel_type="email",
            error="Email sending not configured in MVP",
        )

    def build_webhook_payload(
        self,
        alert: AlertHistory,
    ) -> dict:
        """
        Build webhook payload for an alert.

        Args:
            alert: Alert history entry

        Returns:
            Webhook payload dict
        """
        return {
            "alert_id": alert.alert_id,
            "alert_type": alert.alert_type,
            "tenant_id": alert.tenant_id,
            "severity": alert.severity,
            "title": alert.title,
            "message": alert.message,
            "timestamp": alert.triggered_at.isoformat() if alert.triggered_at else None,
            "details": alert.details or {},
        }

    async def dispatch_notifications(
        self,
        alert: AlertHistory,
        channels: list[dict],
    ) -> list[NotificationResult]:
        """
        Dispatch notifications for an alert to all configured channels.

        Args:
            alert: Alert history entry
            channels: List of channel configs [{type: "webhook", url: "..."}, ...]

        Returns:
            List of NotificationResults
        """
        results = []
        payload = self.build_webhook_payload(alert)

        for channel in channels:
            channel_type = channel.get("type", "").lower()

            if channel_type == "webhook":
                url = channel.get("url")
                if url:
                    result = await self.send_webhook(url, payload)
                    results.append(result)
            elif channel_type == "email":
                address = channel.get("address")
                if address:
                    result = await self.send_email(
                        address=address,
                        subject=f"[SentinAI Alert] {alert.title}",
                        body=alert.message or alert.title,
                    )
                    results.append(result)
            else:
                logger.warning(f"Unknown channel type: {channel_type}")

        return results


class AlertEvaluator:
    """
    Evaluates system metrics against alert thresholds.

    Used by background workers to periodically check for alert conditions.
    """

    def __init__(self, alerting_service: AlertingService):
        """
        Initialize the evaluator.

        Args:
            alerting_service: AlertingService for notifications
        """
        self.alerting_service = alerting_service

    async def evaluate_sla_breach(
        self,
        tenant_id: str,
        exception_id: str,
        sla_deadline: datetime,
        current_status: str,
    ) -> Optional[AlertCondition]:
        """
        Evaluate if an SLA breach alert should trigger.

        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            sla_deadline: SLA deadline
            current_status: Current exception status

        Returns:
            AlertCondition if alert should trigger, None otherwise
        """
        now = datetime.now(timezone.utc)

        if current_status != "resolved" and now > sla_deadline:
            hours_overdue = (now - sla_deadline).total_seconds() / 3600
            return AlertCondition(
                alert_type=AlertType.SLA_BREACH.value,
                severity=AlertSeverity.CRITICAL.value,
                title=f"SLA Breach: Exception {exception_id}",
                message=f"Exception {exception_id} exceeded SLA deadline by {hours_overdue:.1f} hours",
                details={
                    "exception_id": exception_id,
                    "sla_deadline": sla_deadline.isoformat(),
                    "current_status": current_status,
                    "hours_overdue": round(hours_overdue, 2),
                },
                tenant_id=tenant_id,
            )
        return None

    async def evaluate_dlq_growth(
        self,
        tenant_id: str,
        dlq_count: int,
        threshold: int = 100,
    ) -> Optional[AlertCondition]:
        """
        Evaluate if DLQ growth alert should trigger.

        Args:
            tenant_id: Tenant identifier
            dlq_count: Current DLQ entry count
            threshold: Alert threshold

        Returns:
            AlertCondition if alert should trigger, None otherwise
        """
        if dlq_count >= threshold:
            return AlertCondition(
                alert_type=AlertType.DLQ_GROWTH.value,
                severity=AlertSeverity.WARNING.value,
                title=f"DLQ Growth Alert: {dlq_count} entries",
                message=f"Dead letter queue has {dlq_count} entries (threshold: {threshold})",
                details={
                    "dlq_count": dlq_count,
                    "threshold": threshold,
                },
                tenant_id=tenant_id,
            )
        return None

    async def evaluate_worker_health(
        self,
        tenant_id: str,
        worker_type: str,
        consecutive_failures: int,
        threshold: int = 3,
    ) -> Optional[AlertCondition]:
        """
        Evaluate if worker unhealthy alert should trigger.

        Args:
            tenant_id: Tenant identifier
            worker_type: Worker type
            consecutive_failures: Number of consecutive health check failures
            threshold: Alert threshold

        Returns:
            AlertCondition if alert should trigger, None otherwise
        """
        if consecutive_failures >= threshold:
            return AlertCondition(
                alert_type=AlertType.WORKER_UNHEALTHY.value,
                severity=AlertSeverity.CRITICAL.value,
                title=f"Worker Unhealthy: {worker_type}",
                message=f"Worker {worker_type} has failed {consecutive_failures} consecutive health checks",
                details={
                    "worker_type": worker_type,
                    "consecutive_failures": consecutive_failures,
                    "threshold": threshold,
                },
                tenant_id=tenant_id,
            )
        return None

    async def evaluate_error_rate(
        self,
        tenant_id: str,
        worker_type: str,
        error_rate_percent: float,
        threshold: float = 5.0,
    ) -> Optional[AlertCondition]:
        """
        Evaluate if error rate alert should trigger.

        Args:
            tenant_id: Tenant identifier
            worker_type: Worker type
            error_rate_percent: Current error rate percentage
            threshold: Alert threshold percentage

        Returns:
            AlertCondition if alert should trigger, None otherwise
        """
        if error_rate_percent >= threshold:
            severity = (
                AlertSeverity.CRITICAL.value
                if error_rate_percent >= 10.0
                else AlertSeverity.WARNING.value
            )
            return AlertCondition(
                alert_type=AlertType.ERROR_RATE_HIGH.value,
                severity=severity,
                title=f"High Error Rate: {worker_type} at {error_rate_percent:.1f}%",
                message=f"Worker {worker_type} error rate is {error_rate_percent:.1f}% (threshold: {threshold}%)",
                details={
                    "worker_type": worker_type,
                    "error_rate_percent": round(error_rate_percent, 2),
                    "threshold": threshold,
                },
                tenant_id=tenant_id,
            )
        return None


# Singleton instance for dependency injection
_alerting_service: Optional[AlertingService] = None


def get_alerting_service() -> AlertingService:
    """Get or create the alerting service singleton."""
    global _alerting_service
    if _alerting_service is None:
        _alerting_service = AlertingService()
    return _alerting_service
