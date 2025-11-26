"""
Alert Rules and Escalation System.

Phase 2: Configurable alert rules based on metrics and conditions.
Supports alert escalation via ToolExecutionEngine and notifications.

Matches specification from phase2-mvp-issues.md Issue 43.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from src.models.tenant_policy import TenantPolicyPack
from src.notify.service import NotificationService
from src.observability.metrics import MetricsCollector, TenantMetrics
from src.tools.execution_engine import ToolExecutionEngine

logger = logging.getLogger(__name__)


class AlertSeverity(str, Enum):
    """Alert severity levels."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertRuleType(str, Enum):
    """Types of alert rules."""

    HIGH_EXCEPTION_VOLUME = "HIGH_EXCEPTION_VOLUME"
    REPEATED_CRITICAL_BREAKS = "REPEATED_CRITICAL_BREAKS"
    TOOL_CIRCUIT_BREAKER_OPEN = "TOOL_CIRCUIT_BREAKER_OPEN"
    APPROVAL_QUEUE_AGING = "APPROVAL_QUEUE_AGING"


@dataclass
class AlertRule:
    """Configuration for an alert rule."""

    rule_type: AlertRuleType
    enabled: bool = True
    threshold: Optional[float] = None  # Threshold value for rule
    window_minutes: int = 60  # Time window for evaluation
    severity: AlertSeverity = AlertSeverity.MEDIUM
    escalation_tool: Optional[str] = None  # Tool to call on trigger (e.g., "openCase", "escalateCase")
    notification_group: Optional[str] = None  # Group for notification routing


@dataclass
class Alert:
    """A triggered alert."""

    alert_id: str
    tenant_id: str
    rule_type: AlertRuleType
    severity: AlertSeverity
    message: str
    triggered_at: datetime
    metrics_snapshot: dict[str, Any] = field(default_factory=dict)
    resolved_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert alert to dictionary."""
        return {
            "alertId": self.alert_id,
            "tenantId": self.tenant_id,
            "ruleType": self.rule_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "triggeredAt": self.triggered_at.isoformat(),
            "metricsSnapshot": self.metrics_snapshot,
            "resolvedAt": self.resolved_at.isoformat() if self.resolved_at else None,
            "acknowledgedBy": self.acknowledged_by,
            "acknowledgedAt": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
        }


class AlertEvaluator:
    """
    Evaluates alert rules against metrics.
    
    Supports:
    - High exception volume detection
    - Repeated CRITICAL breaks detection
    - Tool circuit breaker open detection
    - Approval queue aging detection
    """

    def __init__(
        self,
        metrics_collector: MetricsCollector,
        tool_execution_engine: Optional[ToolExecutionEngine] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        """
        Initialize alert evaluator.
        
        Args:
            metrics_collector: Metrics collector instance
            tool_execution_engine: Optional tool execution engine for escalation
            notification_service: Optional notification service for alerts
        """
        self.metrics_collector = metrics_collector
        self.tool_execution_engine = tool_execution_engine
        self.notification_service = notification_service
        # Track triggered alerts to prevent duplicates
        self._active_alerts: dict[str, Alert] = {}  # alert_id -> Alert

    def evaluate_alerts(
        self,
        tenant_id: str,
        tenant_policy: TenantPolicyPack,
        alert_rules: Optional[list[AlertRule]] = None,
    ) -> list[Alert]:
        """
        Evaluate alert rules for a tenant.
        
        Args:
            tenant_id: Tenant identifier
            tenant_policy: Tenant policy pack
            alert_rules: Optional list of alert rules (if None, uses defaults)
        
        Returns:
            List of triggered alerts
        """
        if alert_rules is None:
            alert_rules = self._get_default_alert_rules()
        
        # Get metrics for tenant (returns TenantMetrics object)
        metrics = self.metrics_collector.get_or_create_metrics(tenant_id)
        
        triggered_alerts = []
        
        for rule in alert_rules:
            if not rule.enabled:
                continue
            
            alert = self._evaluate_rule(rule, tenant_id, metrics, tenant_policy)
            if alert:
                # Check if this alert is already active (deduplication)
                alert_key = f"{tenant_id}:{rule.rule_type.value}"
                if alert_key not in self._active_alerts:
                    self._active_alerts[alert_key] = alert
                    triggered_alerts.append(alert)
                    
                    # Handle alert: escalate and notify
                    self._handle_alert(alert, rule, tenant_policy)
                else:
                    logger.debug(f"Alert {alert_key} already active, skipping duplicate")
        
        return triggered_alerts

    def _get_default_alert_rules(self) -> list[AlertRule]:
        """Get default alert rules."""
        return [
            AlertRule(
                rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
                enabled=True,
                threshold=100.0,  # 100 exceptions per hour
                window_minutes=60,
                severity=AlertSeverity.HIGH,
                escalation_tool="openCase",
                notification_group="OpsTeam",
            ),
            AlertRule(
                rule_type=AlertRuleType.REPEATED_CRITICAL_BREAKS,
                enabled=True,
                threshold=5.0,  # 5+ occurrences of same CRITICAL exception
                window_minutes=60,
                severity=AlertSeverity.CRITICAL,
                escalation_tool="escalateCase",
                notification_group="OnCall",
            ),
            AlertRule(
                rule_type=AlertRuleType.TOOL_CIRCUIT_BREAKER_OPEN,
                enabled=True,
                severity=AlertSeverity.HIGH,
                escalation_tool="openCase",
                notification_group="DevOps",
            ),
            AlertRule(
                rule_type=AlertRuleType.APPROVAL_QUEUE_AGING,
                enabled=True,
                threshold=3600.0,  # 1 hour in seconds
                window_minutes=60,
                severity=AlertSeverity.MEDIUM,
                escalation_tool="escalateCase",
                notification_group="ApprovalTeam",
            ),
        ]

    def _evaluate_rule(
        self,
        rule: AlertRule,
        tenant_id: str,
        metrics: TenantMetrics,
        tenant_policy: TenantPolicyPack,
    ) -> Optional[Alert]:
        """
        Evaluate a single alert rule.
        
        Args:
            rule: Alert rule to evaluate
            tenant_id: Tenant identifier
            metrics: Tenant metrics
            tenant_policy: Tenant policy pack
        
        Returns:
            Alert if rule triggered, None otherwise
        """
        if rule.rule_type == AlertRuleType.HIGH_EXCEPTION_VOLUME:
            return self._check_high_exception_volume(rule, tenant_id, metrics)
        elif rule.rule_type == AlertRuleType.REPEATED_CRITICAL_BREAKS:
            return self._check_repeated_critical_breaks(rule, tenant_id, metrics)
        elif rule.rule_type == AlertRuleType.TOOL_CIRCUIT_BREAKER_OPEN:
            return self._check_tool_circuit_breaker_open(rule, tenant_id, metrics)
        elif rule.rule_type == AlertRuleType.APPROVAL_QUEUE_AGING:
            return self._check_approval_queue_aging(rule, tenant_id, metrics)
        else:
            logger.warning(f"Unknown alert rule type: {rule.rule_type}")
            return None

    def _check_high_exception_volume(
        self, rule: AlertRule, tenant_id: str, metrics: TenantMetrics
    ) -> Optional[Alert]:
        """Check for high exception volume."""
        if rule.threshold is None:
            return None
        
        # For MVP, use total exception count
        # In production, would filter by time window
        if metrics.exception_count >= rule.threshold:
            return Alert(
                alert_id=f"alert_{tenant_id}_high_volume_{datetime.now(timezone.utc).timestamp()}",
                tenant_id=tenant_id,
                rule_type=rule.rule_type,
                severity=rule.severity,
                message=f"High exception volume detected: {metrics.exception_count} exceptions (threshold: {rule.threshold})",
                triggered_at=datetime.now(timezone.utc),
                metrics_snapshot={"exceptionCount": metrics.exception_count},
            )
        return None

    def _check_repeated_critical_breaks(
        self, rule: AlertRule, tenant_id: str, metrics: TenantMetrics
    ) -> Optional[Alert]:
        """Check for repeated CRITICAL exception breaks."""
        if rule.threshold is None:
            return None
        
        # Check exception type recurrence for CRITICAL severity
        critical_exceptions = []
        for exception_type, recurrence in metrics.exception_type_recurrence.items():
            # For MVP, check if recurrence rate is high
            # In production, would check severity from exception records
            if recurrence.occurrence_count >= rule.threshold:
                critical_exceptions.append({
                    "exceptionType": exception_type,
                    "occurrenceCount": recurrence.occurrence_count,
                    "recurrenceRate": recurrence.get_recurrence_rate(),
                })
        
        if critical_exceptions:
            return Alert(
                alert_id=f"alert_{tenant_id}_critical_breaks_{datetime.now(timezone.utc).timestamp()}",
                tenant_id=tenant_id,
                rule_type=rule.rule_type,
                severity=rule.severity,
                message=f"Repeated CRITICAL breaks detected: {len(critical_exceptions)} exception types with {rule.threshold}+ occurrences",
                triggered_at=datetime.now(timezone.utc),
                metrics_snapshot={"criticalExceptions": critical_exceptions},
            )
        return None

    def _check_tool_circuit_breaker_open(
        self, rule: AlertRule, tenant_id: str, metrics: TenantMetrics
    ) -> Optional[Alert]:
        """Check for tool circuit breaker open."""
        if not self.tool_execution_engine:
            return None
        
        # Check circuit breakers for all tools
        open_circuit_breakers = []
        for tool_name, tool_metrics in metrics.tool_metrics.items():
            # Get circuit breaker state
            circuit_breaker = self.tool_execution_engine._get_circuit_breaker(tool_name)
            if circuit_breaker.get_state().value == "open":
                open_circuit_breakers.append({
                    "toolName": tool_name,
                    "failureCount": circuit_breaker.failure_count,
                    "state": circuit_breaker.get_state().value,
                })
        
        if open_circuit_breakers:
            return Alert(
                alert_id=f"alert_{tenant_id}_circuit_breaker_{datetime.now(timezone.utc).timestamp()}",
                tenant_id=tenant_id,
                rule_type=rule.rule_type,
                severity=rule.severity,
                message=f"Tool circuit breaker open: {len(open_circuit_breakers)} tools with open circuit breakers",
                triggered_at=datetime.now(timezone.utc),
                metrics_snapshot={"openCircuitBreakers": open_circuit_breakers},
            )
        return None

    def _check_approval_queue_aging(
        self, rule: AlertRule, tenant_id: str, metrics: TenantMetrics
    ) -> Optional[Alert]:
        """Check for approval queue aging."""
        if rule.threshold is None:
            return None
        
        approval_metrics = metrics.approval_queue_metrics
        
        # Check if oldest pending approval exceeds threshold
        if approval_metrics.oldest_pending_age_seconds >= rule.threshold:
            return Alert(
                alert_id=f"alert_{tenant_id}_approval_aging_{datetime.now(timezone.utc).timestamp()}",
                tenant_id=tenant_id,
                rule_type=rule.rule_type,
                severity=rule.severity,
                message=f"Approval queue aging: oldest pending approval is {approval_metrics.oldest_pending_age_seconds:.0f} seconds old (threshold: {rule.threshold} seconds)",
                triggered_at=datetime.now(timezone.utc),
                metrics_snapshot={
                    "pendingCount": approval_metrics.pending_count,
                    "oldestPendingAgeSeconds": approval_metrics.oldest_pending_age_seconds,
                    "avgPendingAgeSeconds": approval_metrics.get_avg_pending_age(),
                },
            )
        return None

    def _handle_alert(
        self, alert: Alert, rule: AlertRule, tenant_policy: TenantPolicyPack
    ) -> None:
        """
        Handle a triggered alert: escalate and notify.
        
        Args:
            alert: Triggered alert
            rule: Alert rule that triggered
            tenant_policy: Tenant policy pack
        """
        logger.warning(f"Alert triggered: {alert.message}")
        
        # Escalate via tool if configured
        if rule.escalation_tool and self.tool_execution_engine:
            self._escalate_via_tool(alert, rule, tenant_policy)
        
        # Send notification if configured
        if self.notification_service and tenant_policy.notification_policies:
            self._send_alert_notification(alert, rule, tenant_policy)

    def _escalate_via_tool(
        self, alert: Alert, rule: AlertRule, tenant_policy: TenantPolicyPack
    ) -> None:
        """
        Escalate alert via ToolExecutionEngine.
        
        Args:
            alert: Triggered alert
            rule: Alert rule that triggered
            tenant_policy: Tenant policy pack
        """
        try:
            # For MVP, we'll log the escalation attempt
            # In production, would call actual tool (openCase/escalateCase)
            escalation_args = {
                "alertId": alert.alert_id,
                "tenantId": alert.tenant_id,
                "ruleType": alert.rule_type.value,
                "severity": alert.severity.value,
                "message": alert.message,
                "metricsSnapshot": alert.metrics_snapshot,
            }
            
            logger.info(
                f"Escalating alert {alert.alert_id} via tool {rule.escalation_tool} "
                f"with args: {escalation_args}"
            )
            
            # Note: Actual tool execution would require DomainPack and tool definition
            # For MVP, we log the escalation attempt
            # In production, would use:
            # await self.tool_execution_engine.execute(
            #     tool_name=rule.escalation_tool,
            #     args=escalation_args,
            #     tenant_policy=tenant_policy,
            #     domain_pack=domain_pack,
            #     mode="sync",
            # )
        
        except Exception as e:
            logger.error(f"Failed to escalate alert {alert.alert_id} via tool: {e}")

    def _send_alert_notification(
        self, alert: Alert, rule: AlertRule, tenant_policy: TenantPolicyPack
    ) -> None:
        """
        Send notification for alert.
        
        Args:
            alert: Triggered alert
            rule: Alert rule that triggered
            tenant_policy: Tenant policy pack
        """
        try:
            group = rule.notification_group or "DefaultOps"
            subject = f"Alert: {alert.severity.value} - {alert.rule_type.value}"
            message = (
                f"Alert triggered for tenant {alert.tenant_id}:\n\n"
                f"{alert.message}\n\n"
                f"Severity: {alert.severity.value}\n"
                f"Rule Type: {alert.rule_type.value}\n"
                f"Triggered At: {alert.triggered_at.isoformat()}\n"
            )
            
            # Build payload link
            payload_link = f"/ui/alerts/{alert.tenant_id}/{alert.alert_id}"
            
            # Convert notification policies to dict
            notif_policies_dict = tenant_policy.notification_policies.model_dump(by_alias=True)
            
            self.notification_service.send_notification(
                tenant_id=alert.tenant_id,
                group=group,
                subject=subject,
                message=message,
                payload_link=payload_link,
                notification_policies=notif_policies_dict,
            )
        
        except Exception as e:
            logger.error(f"Failed to send alert notification for {alert.alert_id}: {e}")

    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        """
        Acknowledge an alert.
        
        Args:
            alert_id: Alert identifier
            user: User who acknowledged
        
        Returns:
            True if alert was found and acknowledged, False otherwise
        """
        for alert in self._active_alerts.values():
            if alert.alert_id == alert_id:
                alert.acknowledged_by = user
                alert.acknowledged_at = datetime.now(timezone.utc)
                logger.info(f"Alert {alert_id} acknowledged by {user}")
                return True
        return False

    def resolve_alert(self, alert_id: str) -> bool:
        """
        Resolve an alert.
        
        Args:
            alert_id: Alert identifier
        
        Returns:
            True if alert was found and resolved, False otherwise
        """
        for alert_key, alert in list(self._active_alerts.items()):
            if alert.alert_id == alert_id:
                alert.resolved_at = datetime.now(timezone.utc)
                del self._active_alerts[alert_key]
                logger.info(f"Alert {alert_id} resolved")
                return True
        return False

    def get_active_alerts(self, tenant_id: Optional[str] = None) -> list[Alert]:
        """
        Get active alerts.
        
        Args:
            tenant_id: Optional tenant ID to filter by
        
        Returns:
            List of active alerts
        """
        if tenant_id:
            return [
                alert
                for alert in self._active_alerts.values()
                if alert.tenant_id == tenant_id and alert.resolved_at is None
            ]
        return [alert for alert in self._active_alerts.values() if alert.resolved_at is None]

