"""
Comprehensive tests for Notification Service.

Tests:
- Email notifications (SMTP)
- Webhook notifications (Teams/Slack)
- Notification routing by group
- Integration with TenantPolicyPack
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from email.mime.multipart import MIMEMultipart

from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.models.tenant_policy import NotificationPolicies, TenantPolicyPack
from src.notify.service import NotificationService, NotificationError
from datetime import datetime, timezone


@pytest.fixture
def notification_service():
    """Notification service for testing."""
    return NotificationService(
        smtp_host="smtp.test.com",
        smtp_port=587,
        smtp_user="test@example.com",
        smtp_password="testpass",
        smtp_use_tls=True,
    )


@pytest.fixture
def sample_exception():
    """Sample exception record for testing."""
    return ExceptionRecord(
        exceptionId="EX001",
        tenantId="TENANT_A",
        sourceSystem="ERP",
        exceptionType="SETTLEMENT_FAIL",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"orderId": "ORD001"},
        resolutionStatus=ResolutionStatus.ESCALATED,
    )


@pytest.fixture
def notification_policies():
    """Sample notification policies."""
    return NotificationPolicies(
        channels=["email", "teamsWebhook"],
        recipientsByGroup={
            "BillingOps": ["billing-ops@example.com"],
            "SETTLEMENT_FAIL": ["settlement-ops@example.com"],
        },
        webhookUrls={
            "teamsWebhook": "https://outlook.office.com/webhook/test",
            "slackWebhook": "https://hooks.slack.com/services/test",
        },
        smtpConfig={
            "host": "smtp.test.com",
            "port": 587,
            "user": "test@example.com",
            "password": "testpass",
            "useTls": True,
        },
    )


class TestEmailNotifications:
    """Tests for email notification channel."""

    @patch("smtplib.SMTP")
    def test_send_email_success(self, mock_smtp_class, notification_service):
        """Test successful email sending."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        
        result = notification_service._send_email(
            recipients=["test@example.com"],
            subject="Test Subject",
            message="Test message",
            payload_link="https://example.com/details",
        )
        
        assert result["sent"] is True
        assert result["error"] is None
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@example.com", "testpass")
        mock_smtp.send_message.assert_called_once()

    @patch("smtplib.SMTP")
    def test_send_email_without_tls(self, mock_smtp_class, notification_service):
        """Test email sending without TLS."""
        notification_service.smtp_use_tls = False
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        
        result = notification_service._send_email(
            recipients=["test@example.com"],
            subject="Test Subject",
            message="Test message",
        )
        
        assert result["sent"] is True
        mock_smtp.starttls.assert_not_called()

    @patch("smtplib.SMTP")
    def test_send_email_without_auth(self, mock_smtp_class):
        """Test email sending without authentication."""
        service = NotificationService(smtp_host="smtp.test.com", smtp_port=587)
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        
        result = service._send_email(
            recipients=["test@example.com"],
            subject="Test Subject",
            message="Test message",
        )
        
        assert result["sent"] is True
        mock_smtp.login.assert_not_called()

    @patch("smtplib.SMTP")
    def test_send_email_failure(self, mock_smtp_class, notification_service):
        """Test email sending failure."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        mock_smtp.send_message.side_effect = Exception("SMTP error")
        
        result = notification_service._send_email(
            recipients=["test@example.com"],
            subject="Test Subject",
            message="Test message",
        )
        
        assert result["sent"] is False
        assert "SMTP error" in result["error"]

    def test_send_email_no_host_configured(self):
        """Test email sending when SMTP host is not configured."""
        service = NotificationService()
        
        result = service._send_email(
            recipients=["test@example.com"],
            subject="Test Subject",
            message="Test message",
        )
        
        assert result["sent"] is False
        assert "SMTP host not configured" in result["error"]

    @patch("smtplib.SMTP")
    def test_send_email_with_smtp_config_override(self, mock_smtp_class, notification_service):
        """Test email sending with SMTP config override."""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp
        
        smtp_config = {
            "host": "smtp.override.com",
            "port": 465,
            "user": "override@example.com",
            "password": "overridepass",
            "useTls": False,
        }
        
        result = notification_service._send_email(
            recipients=["test@example.com"],
            subject="Test Subject",
            message="Test message",
            smtp_config=smtp_config,
        )
        
        assert result["sent"] is True
        mock_smtp_class.assert_called_with("smtp.override.com", 465)
        mock_smtp.starttls.assert_not_called()
        mock_smtp.login.assert_called_once_with("override@example.com", "overridepass")


class TestWebhookNotifications:
    """Tests for webhook notification channel."""

    @patch("httpx.Client")
    def test_send_webhook_slack_success(self, mock_client_class, notification_service):
        """Test successful Slack webhook sending."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        result = notification_service._send_webhook(
            webhook_url="https://hooks.slack.com/services/test",
            subject="Test Subject",
            message="Test message",
            payload_link="https://example.com/details",
            channel_type="slackWebhook",
        )
        
        assert result["sent"] is True
        assert result["error"] is None
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert call_args[0][0] == "https://hooks.slack.com/services/test"
        assert "blocks" in call_args[1]["json"]

    @patch("httpx.Client")
    def test_send_webhook_teams_success(self, mock_client_class, notification_service):
        """Test successful Teams webhook sending."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        result = notification_service._send_webhook(
            webhook_url="https://outlook.office.com/webhook/test",
            subject="Test Subject",
            message="Test message",
            payload_link="https://example.com/details",
            channel_type="teamsWebhook",
        )
        
        assert result["sent"] is True
        assert result["error"] is None
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "@type" in call_args[1]["json"]
        assert call_args[1]["json"]["@type"] == "MessageCard"

    @patch("httpx.Client")
    def test_send_webhook_generic_success(self, mock_client_class, notification_service):
        """Test successful generic webhook sending."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        result = notification_service._send_webhook(
            webhook_url="https://example.com/webhook",
            subject="Test Subject",
            message="Test message",
            channel_type="webhook",
        )
        
        assert result["sent"] is True
        assert result["error"] is None
        mock_client.post.assert_called_once()

    @patch("httpx.Client")
    def test_send_webhook_failure(self, mock_client_class, notification_service):
        """Test webhook sending failure."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = Exception("HTTP error")
        mock_client.post.return_value = mock_response
        mock_client_class.return_value.__enter__.return_value = mock_client
        
        result = notification_service._send_webhook(
            webhook_url="https://example.com/webhook",
            subject="Test Subject",
            message="Test message",
        )
        
        assert result["sent"] is False
        assert "HTTP error" in result["error"]


class TestNotificationService:
    """Tests for NotificationService integration."""

    @patch.object(NotificationService, "_send_email")
    @patch.object(NotificationService, "_send_webhook")
    def test_send_notification_email_and_webhook(
        self, mock_send_webhook, mock_send_email, notification_service, notification_policies
    ):
        """Test sending notification via both email and webhook."""
        mock_send_email.return_value = {"sent": True, "error": None}
        mock_send_webhook.return_value = {"sent": True, "error": None}
        
        notif_policies_dict = notification_policies.model_dump(by_alias=True)
        
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="BillingOps",
            subject="Test Subject",
            message="Test message",
            payload_link="https://example.com/details",
            notification_policies=notif_policies_dict,
        )
        
        assert result["success"] is True
        assert "email" in result["channels"]
        assert "teamsWebhook" in result["channels"]
        mock_send_email.assert_called_once()
        mock_send_webhook.assert_called_once()

    @patch.object(NotificationService, "_send_email")
    def test_send_notification_email_only(
        self, mock_send_email, notification_service, notification_policies
    ):
        """Test sending notification via email only."""
        notification_policies.channels = ["email"]
        mock_send_email.return_value = {"sent": True, "error": None}
        
        notif_policies_dict = notification_policies.model_dump(by_alias=True)
        
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="BillingOps",
            subject="Test Subject",
            message="Test message",
            notification_policies=notif_policies_dict,
        )
        
        assert result["success"] is True
        assert "email" in result["channels"]
        assert len(result["channels"]) == 1

    @patch.object(NotificationService, "_send_webhook")
    def test_send_notification_webhook_only(
        self, mock_send_webhook, notification_service, notification_policies
    ):
        """Test sending notification via webhook only."""
        notification_policies.channels = ["teamsWebhook"]
        mock_send_webhook.return_value = {"sent": True, "error": None}
        
        notif_policies_dict = notification_policies.model_dump(by_alias=True)
        
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="BillingOps",
            subject="Test Subject",
            message="Test message",
            notification_policies=notif_policies_dict,
        )
        
        assert result["success"] is True
        assert "teamsWebhook" in result["channels"]

    def test_send_notification_no_recipients(self, notification_service):
        """Test sending notification when no recipients configured."""
        notification_policies = NotificationPolicies(
            channels=["email"],
            recipientsByGroup={},
        )
        
        notif_policies_dict = notification_policies.model_dump(by_alias=True)
        
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="UnknownGroup",
            subject="Test Subject",
            message="Test message",
            notification_policies=notif_policies_dict,
        )
        
        assert result["success"] is False
        assert len(result["channels"]) == 0

    @patch.object(NotificationService, "_send_email")
    @patch.object(NotificationService, "_send_webhook")
    def test_send_notification_partial_failure(
        self, mock_send_webhook, mock_send_email, notification_service, notification_policies
    ):
        """Test notification when one channel fails."""
        mock_send_email.return_value = {"sent": True, "error": None}
        mock_send_webhook.return_value = {"sent": False, "error": "Webhook error"}
        
        notif_policies_dict = notification_policies.model_dump(by_alias=True)
        
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="BillingOps",
            subject="Test Subject",
            message="Test message",
            notification_policies=notif_policies_dict,
        )
        
        assert result["success"] is True  # At least one channel succeeded
        assert result["channels"]["email"]["sent"] is True
        assert result["channels"]["teamsWebhook"]["sent"] is False

    @patch.object(NotificationService, "_send_email")
    @patch.object(NotificationService, "_send_webhook")
    def test_send_notification_all_failures(
        self, mock_send_webhook, mock_send_email, notification_service, notification_policies
    ):
        """Test notification when all channels fail."""
        mock_send_email.return_value = {"sent": False, "error": "Email error"}
        mock_send_webhook.return_value = {"sent": False, "error": "Webhook error"}
        
        notif_policies_dict = notification_policies.model_dump(by_alias=True)
        
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="BillingOps",
            subject="Test Subject",
            message="Test message",
            notification_policies=notif_policies_dict,
        )
        
        assert result["success"] is False
        assert result["channels"]["email"]["sent"] is False
        assert result["channels"]["teamsWebhook"]["sent"] is False

    def test_send_notification_no_policies(self, notification_service):
        """Test sending notification without policies."""
        result = notification_service.send_notification(
            tenant_id="TENANT_A",
            group="BillingOps",
            subject="Test Subject",
            message="Test message",
            notification_policies=None,
        )
        
        assert result["success"] is False
        assert len(result["channels"]) == 0

