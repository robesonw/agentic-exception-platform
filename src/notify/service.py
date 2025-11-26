"""
Notification Service for alerts and updates.

Phase 2: Supports email (SMTP) and webhook (Teams/Slack) channels.
Matches specification from phase2-mvp-issues.md Issue 42.
"""

import json
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Any, Optional
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised when notification operations fail."""

    pass


class NotificationService:
    """
    Notification service for sending alerts and updates.
    
    Supports:
    - Email (SMTP)
    - Webhook (Teams/Slack)
    
    Phase 2: Notification preferences per tenant via TenantPolicyPack.notificationPolicies.
    """

    def __init__(
        self,
        smtp_host: Optional[str] = None,
        smtp_port: int = 587,
        smtp_user: Optional[str] = None,
        smtp_password: Optional[str] = None,
        smtp_use_tls: bool = True,
        webhook_timeout: float = 10.0,
    ):
        """
        Initialize notification service.
        
        Args:
            smtp_host: SMTP server hostname (e.g., 'smtp.gmail.com')
            smtp_port: SMTP server port (default: 587)
            smtp_user: SMTP username for authentication
            smtp_password: SMTP password for authentication
            smtp_use_tls: Whether to use TLS (default: True)
            webhook_timeout: Timeout for webhook requests in seconds (default: 10.0)
        """
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.smtp_use_tls = smtp_use_tls
        self.webhook_timeout = webhook_timeout

    def send_notification(
        self,
        tenant_id: str,
        group: str,
        subject: str,
        message: str,
        payload_link: Optional[str] = None,
        notification_policies: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send notification to configured channels for a tenant group.
        
        Args:
            tenant_id: Tenant identifier
            group: Notification group (e.g., 'BillingOps', 'CareOpsTier2')
            subject: Notification subject
            message: Notification message body
            payload_link: Optional link to exception details
            notification_policies: Optional notification policies from TenantPolicyPack.
                Format: {
                    "channels": ["email", "teamsWebhook", "slackWebhook"],
                    "recipientsByGroup": {
                        "BillingOps": ["billing-ops@example.com"],
                        ...
                    },
                    "webhookUrls": {
                        "teamsWebhook": "https://outlook.office.com/webhook/...",
                        "slackWebhook": "https://hooks.slack.com/services/..."
                    },
                    "smtpConfig": {
                        "host": "smtp.gmail.com",
                        "port": 587,
                        "user": "user@example.com",
                        "password": "password",
                        "useTls": true
                    }
                }
        
        Returns:
            Dictionary with notification results:
            {
                "success": bool,
                "channels": {
                    "email": {"sent": bool, "error": Optional[str]},
                    "webhook": {"sent": bool, "error": Optional[str]}
                }
            }
        """
        if notification_policies is None:
            notification_policies = {}
        
        channels = notification_policies.get("channels", [])
        recipients_by_group = notification_policies.get("recipientsByGroup", {})
        webhook_urls = notification_policies.get("webhookUrls", {})
        smtp_config = notification_policies.get("smtpConfig", {})
        
        results = {
            "success": False,
            "channels": {},
        }
        
        # Get recipients for this group
        recipients = recipients_by_group.get(group, [])
        
        if not recipients and not webhook_urls:
            logger.warning(
                f"No recipients or webhooks configured for tenant {tenant_id}, group {group}"
            )
            return results
        
        # Send via email if configured
        if "email" in channels and recipients:
            email_result = self._send_email(
                recipients=recipients,
                subject=subject,
                message=message,
                payload_link=payload_link,
                smtp_config=smtp_config,
            )
            results["channels"]["email"] = email_result
        
        # Send via webhook if configured
        webhook_channels = [ch for ch in channels if ch in ["teamsWebhook", "slackWebhook", "webhook"]]
        if webhook_channels:
            for channel in webhook_channels:
                webhook_url = webhook_urls.get(channel)
                if webhook_url:
                    webhook_result = self._send_webhook(
                        webhook_url=webhook_url,
                        subject=subject,
                        message=message,
                        payload_link=payload_link,
                        channel_type=channel,
                    )
                    results["channels"][channel] = webhook_result
        
        # Overall success if at least one channel succeeded
        results["success"] = any(
            ch_result.get("sent", False)
            for ch_result in results["channels"].values()
        )
        
        return results

    def _send_email(
        self,
        recipients: list[str],
        subject: str,
        message: str,
        payload_link: Optional[str] = None,
        smtp_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Send email notification via SMTP.
        
        Args:
            recipients: List of email addresses
            subject: Email subject
            message: Email body
            payload_link: Optional link to exception details
            smtp_config: Optional SMTP configuration (overrides instance config)
        
        Returns:
            Dictionary with result: {"sent": bool, "error": Optional[str]}
        """
        # Use provided config or fall back to instance config
        smtp_host = smtp_config.get("host") if smtp_config else self.smtp_host
        smtp_port = smtp_config.get("port", 587) if smtp_config else self.smtp_port
        smtp_user = smtp_config.get("user") if smtp_config else self.smtp_user
        smtp_password = smtp_config.get("password") if smtp_config else self.smtp_password
        smtp_use_tls = smtp_config.get("useTls", True) if smtp_config else self.smtp_use_tls
        
        if not smtp_host:
            return {"sent": False, "error": "SMTP host not configured"}
        
        try:
            # Create message
            msg = MIMEMultipart()
            msg["From"] = smtp_user or "noreply@agentic-platform.local"
            msg["To"] = ", ".join(recipients)
            msg["Subject"] = subject
            
            # Build email body
            body = message
            if payload_link:
                body += f"\n\nView details: {payload_link}"
            
            msg.attach(MIMEText(body, "plain"))
            
            # Send email
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                if smtp_use_tls:
                    server.starttls()
                
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                
                server.send_message(msg)
            
            logger.info(f"Email notification sent to {len(recipients)} recipients")
            return {"sent": True, "error": None}
        
        except Exception as e:
            error_msg = f"Failed to send email: {str(e)}"
            logger.error(error_msg)
            return {"sent": False, "error": error_msg}

    def _send_webhook(
        self,
        webhook_url: str,
        subject: str,
        message: str,
        payload_link: Optional[str] = None,
        channel_type: str = "webhook",
    ) -> dict[str, Any]:
        """
        Send webhook notification (Teams/Slack).
        
        Args:
            webhook_url: Webhook URL
            subject: Notification subject
            message: Notification message
            payload_link: Optional link to exception details
            channel_type: Channel type ('teamsWebhook', 'slackWebhook', or 'webhook')
        
        Returns:
            Dictionary with result: {"sent": bool, "error": Optional[str]}
        """
        try:
            # Format payload based on channel type
            if channel_type == "slackWebhook":
                payload = {
                    "text": subject,
                    "blocks": [
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"*{subject}*\n\n{message}",
                            },
                        },
                    ],
                }
                if payload_link:
                    payload["blocks"].append(
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"<{payload_link}|View Details>",
                            },
                        }
                    )
            elif channel_type == "teamsWebhook":
                payload = {
                    "@type": "MessageCard",
                    "@context": "https://schema.org/extensions",
                    "summary": subject,
                    "themeColor": "0078D4",
                    "title": subject,
                    "text": message,
                }
                if payload_link:
                    payload["potentialAction"] = [
                        {
                            "@type": "OpenUri",
                            "name": "View Details",
                            "targets": [{"os": "default", "uri": payload_link}],
                        }
                    ]
            else:
                # Generic webhook
                payload = {
                    "subject": subject,
                    "message": message,
                }
                if payload_link:
                    payload["link"] = payload_link
            
            # Send webhook
            with httpx.Client(timeout=self.webhook_timeout) as client:
                response = client.post(
                    webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
            
            logger.info(f"Webhook notification sent to {webhook_url}")
            return {"sent": True, "error": None}
        
        except Exception as e:
            error_msg = f"Failed to send webhook: {str(e)}"
            logger.error(error_msg)
            return {"sent": False, "error": error_msg}

