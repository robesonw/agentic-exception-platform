"""
Comprehensive tests for Alert Rules and Escalation.

Tests:
- Alert rule evaluation
- High exception volume detection
- Repeated CRITICAL breaks detection
- Tool circuit breaker open detection
- Approval queue aging detection
- Alert escalation and notification
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

from src.models.tenant_policy import NotificationPolicies, TenantPolicyPack
from src.notify.service import NotificationService
from src.observability.alerts import (
    Alert,
    AlertEvaluator,
    AlertRule,
    AlertRuleType,
    AlertSeverity,
)
from src.observability.metrics import (
    ApprovalQueueMetrics,
    ExceptionTypeRecurrence,
    MetricsCollector,
    TenantMetrics,
    ToolMetrics,
)
from src.tools.execution_engine import CircuitBreaker, CircuitState, ToolExecutionEngine


@pytest.fixture
def metrics_collector():
    """Metrics collector for testing."""
    return MetricsCollector()


@pytest.fixture
def tool_execution_engine():
    """Tool execution engine for testing."""
    return ToolExecutionEngine()


@pytest.fixture
def notification_service():
    """Notification service for testing."""
    return NotificationService()


@pytest.fixture
def tenant_policy():
    """Sample tenant policy for testing."""
    return TenantPolicyPack(
        tenantId="TENANT_A",
        domainName="Finance",
        notificationPolicies=NotificationPolicies(
            channels=["email"],
            recipientsByGroup={"OpsTeam": ["ops@example.com"]},
        ),
    )


@pytest.fixture
def alert_evaluator(metrics_collector, tool_execution_engine, notification_service):
    """Alert evaluator for testing."""
    return AlertEvaluator(
        metrics_collector=metrics_collector,
        tool_execution_engine=tool_execution_engine,
        notification_service=notification_service,
    )


class TestHighExceptionVolume:
    """Tests for high exception volume alert rule."""

    def test_high_exception_volume_triggered(self, alert_evaluator, tenant_policy):
        """Test high exception volume alert is triggered."""
        # Setup metrics with high volume
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150  # Above threshold of 100
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        assert alerts[0].rule_type == AlertRuleType.HIGH_EXCEPTION_VOLUME
        assert alerts[0].severity == AlertSeverity.HIGH
        assert "150 exceptions" in alerts[0].message

    def test_high_exception_volume_not_triggered(self, alert_evaluator, tenant_policy):
        """Test high exception volume alert is not triggered when below threshold."""
        # Setup metrics with low volume
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 50  # Below threshold of 100
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 0

    def test_high_exception_volume_disabled(self, alert_evaluator, tenant_policy):
        """Test high exception volume alert is not triggered when disabled."""
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=False,  # Disabled
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 0


class TestRepeatedCriticalBreaks:
    """Tests for repeated CRITICAL breaks alert rule."""

    def test_repeated_critical_breaks_triggered(self, alert_evaluator, tenant_policy):
        """Test repeated CRITICAL breaks alert is triggered."""
        # Setup metrics with repeated CRITICAL exceptions
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        recurrence = ExceptionTypeRecurrence(
            exception_type="CRITICAL_FAILURE",
            occurrence_count=10,  # Above threshold of 5
        )
        metrics.exception_type_recurrence["CRITICAL_FAILURE"] = recurrence
        
        rule = AlertRule(
            rule_type=AlertRuleType.REPEATED_CRITICAL_BREAKS,
            enabled=True,
            threshold=5.0,
            severity=AlertSeverity.CRITICAL,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        assert alerts[0].rule_type == AlertRuleType.REPEATED_CRITICAL_BREAKS
        assert alerts[0].severity == AlertSeverity.CRITICAL
        assert "CRITICAL breaks" in alerts[0].message

    def test_repeated_critical_breaks_not_triggered(self, alert_evaluator, tenant_policy):
        """Test repeated CRITICAL breaks alert is not triggered when below threshold."""
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        recurrence = ExceptionTypeRecurrence(
            exception_type="CRITICAL_FAILURE",
            occurrence_count=3,  # Below threshold of 5
        )
        metrics.exception_type_recurrence["CRITICAL_FAILURE"] = recurrence
        
        rule = AlertRule(
            rule_type=AlertRuleType.REPEATED_CRITICAL_BREAKS,
            enabled=True,
            threshold=5.0,
            severity=AlertSeverity.CRITICAL,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 0


class TestToolCircuitBreakerOpen:
    """Tests for tool circuit breaker open alert rule."""

    def test_circuit_breaker_open_triggered(self, alert_evaluator, tenant_policy):
        """Test circuit breaker open alert is triggered."""
        # Setup metrics with tool that has open circuit breaker
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        tool_metrics = ToolMetrics(tool_name="failing_tool")
        metrics.tool_metrics["failing_tool"] = tool_metrics
        
        # Open circuit breaker for the tool
        circuit_breaker = alert_evaluator.tool_execution_engine._get_circuit_breaker("failing_tool")
        for _ in range(6):  # Exceed failure threshold
            circuit_breaker.record_failure()
        
        rule = AlertRule(
            rule_type=AlertRuleType.TOOL_CIRCUIT_BREAKER_OPEN,
            enabled=True,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        assert alerts[0].rule_type == AlertRuleType.TOOL_CIRCUIT_BREAKER_OPEN
        assert "circuit breaker open" in alerts[0].message.lower()

    def test_circuit_breaker_open_not_triggered(self, alert_evaluator, tenant_policy):
        """Test circuit breaker open alert is not triggered when all breakers are closed."""
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        tool_metrics = ToolMetrics(tool_name="working_tool")
        metrics.tool_metrics["working_tool"] = tool_metrics
        
        # Circuit breaker should be closed by default
        rule = AlertRule(
            rule_type=AlertRuleType.TOOL_CIRCUIT_BREAKER_OPEN,
            enabled=True,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 0


class TestApprovalQueueAging:
    """Tests for approval queue aging alert rule."""

    def test_approval_queue_aging_triggered(self, alert_evaluator, tenant_policy):
        """Test approval queue aging alert is triggered."""
        # Setup metrics with aged approval queue
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.approval_queue_metrics = ApprovalQueueMetrics(
            pending_count=5,
            oldest_pending_age_seconds=7200.0,  # 2 hours, above threshold of 1 hour
        )
        
        rule = AlertRule(
            rule_type=AlertRuleType.APPROVAL_QUEUE_AGING,
            enabled=True,
            threshold=3600.0,  # 1 hour
            severity=AlertSeverity.MEDIUM,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        assert alerts[0].rule_type == AlertRuleType.APPROVAL_QUEUE_AGING
        assert "Approval queue aging" in alerts[0].message

    def test_approval_queue_aging_not_triggered(self, alert_evaluator, tenant_policy):
        """Test approval queue aging alert is not triggered when below threshold."""
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.approval_queue_metrics = ApprovalQueueMetrics(
            pending_count=2,
            oldest_pending_age_seconds=1800.0,  # 30 minutes, below threshold of 1 hour
        )
        
        rule = AlertRule(
            rule_type=AlertRuleType.APPROVAL_QUEUE_AGING,
            enabled=True,
            threshold=3600.0,  # 1 hour
            severity=AlertSeverity.MEDIUM,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 0


class TestAlertEscalation:
    """Tests for alert escalation and notification."""

    @patch.object(NotificationService, "send_notification")
    def test_alert_escalation_sends_notification(
        self, mock_send_notification, alert_evaluator, tenant_policy
    ):
        """Test alert escalation sends notification."""
        mock_send_notification.return_value = {"success": True, "channels": {}}
        
        # Setup metrics to trigger alert
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
            escalation_tool="openCase",
            notification_group="OpsTeam",
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        # Verify notification was sent
        mock_send_notification.assert_called_once()
        call_args = mock_send_notification.call_args
        assert call_args[1]["tenant_id"] == "TENANT_A"
        assert call_args[1]["group"] == "OpsTeam"

    def test_alert_deduplication(self, alert_evaluator, tenant_policy):
        """Test alert deduplication prevents duplicate alerts."""
        # Setup metrics to trigger alert
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        # Evaluate twice - should only trigger once
        alerts1 = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        alerts2 = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts1) == 1
        assert len(alerts2) == 0  # Duplicate should be suppressed


class TestAlertManagement:
    """Tests for alert acknowledgment and resolution."""

    def test_acknowledge_alert(self, alert_evaluator, tenant_policy):
        """Test alert acknowledgment."""
        # Trigger an alert
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        alert_id = alerts[0].alert_id
        
        # Acknowledge alert
        result = alert_evaluator.acknowledge_alert(alert_id, "user@example.com")
        assert result is True
        
        # Verify alert is acknowledged
        active_alerts = alert_evaluator.get_active_alerts("TENANT_A")
        assert len(active_alerts) == 1
        assert active_alerts[0].acknowledged_by == "user@example.com"
        assert active_alerts[0].acknowledged_at is not None

    def test_resolve_alert(self, alert_evaluator, tenant_policy):
        """Test alert resolution."""
        # Trigger an alert
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts) == 1
        alert_id = alerts[0].alert_id
        
        # Resolve alert
        result = alert_evaluator.resolve_alert(alert_id)
        assert result is True
        
        # Verify alert is resolved
        active_alerts = alert_evaluator.get_active_alerts("TENANT_A")
        assert len(active_alerts) == 0

    def test_get_active_alerts(self, alert_evaluator, tenant_policy):
        """Test getting active alerts."""
        # Trigger alerts for two tenants
        metrics_a = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics_a.exception_count = 150
        
        metrics_b = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_B")
        metrics_b.exception_count = 200
        
        rule = AlertRule(
            rule_type=AlertRuleType.HIGH_EXCEPTION_VOLUME,
            enabled=True,
            threshold=100.0,
            severity=AlertSeverity.HIGH,
        )
        
        alerts_a = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        alerts_b = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_B",
            tenant_policy=tenant_policy,
            alert_rules=[rule],
        )
        
        assert len(alerts_a) == 1
        assert len(alerts_b) == 1
        
        # Get all active alerts
        all_active = alert_evaluator.get_active_alerts()
        assert len(all_active) == 2
        
        # Get active alerts for specific tenant
        tenant_a_active = alert_evaluator.get_active_alerts("TENANT_A")
        assert len(tenant_a_active) == 1
        assert tenant_a_active[0].tenant_id == "TENANT_A"


class TestDefaultAlertRules:
    """Tests for default alert rules."""

    def test_default_alert_rules(self, alert_evaluator, tenant_policy):
        """Test default alert rules are applied when none provided."""
        # Setup metrics to trigger multiple alerts
        metrics = alert_evaluator.metrics_collector.get_or_create_metrics("TENANT_A")
        metrics.exception_count = 150  # High volume
        metrics.approval_queue_metrics = ApprovalQueueMetrics(
            pending_count=5,
            oldest_pending_age_seconds=7200.0,  # Aged queue
        )
        
        # Evaluate with default rules
        alerts = alert_evaluator.evaluate_alerts(
            tenant_id="TENANT_A",
            tenant_policy=tenant_policy,
            alert_rules=None,  # Use defaults
        )
        
        # Should trigger at least high volume and approval queue aging
        assert len(alerts) >= 2
        alert_types = {alert.rule_type for alert in alerts}
        assert AlertRuleType.HIGH_EXCEPTION_VOLUME in alert_types
        assert AlertRuleType.APPROVAL_QUEUE_AGING in alert_types

