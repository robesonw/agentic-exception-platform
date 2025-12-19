# Operations Alerting Guide

**Phase 10: Alerting System**  
Reference: `docs/phase10-ops-governance-mvp.md` Section 6

## Overview

The alerting system provides configurable, per-tenant alerts for operational issues. Alerts can be sent via webhook or email, with support for quiet hours, escalation policies, and alert history tracking.

## Alert Types

The platform supports the following alert types:

| Alert Type | Trigger Condition | Default Threshold | Severity |
|------------|------------------|-------------------|----------|
| **SLA_BREACH** | Exception SLA expired | Immediate | Critical |
| **SLA_IMMINENT** | Exception approaching SLA deadline | 80% of SLA window elapsed | Warning |
| **DLQ_GROWTH** | DLQ entries exceed threshold | 100 entries | Warning |
| **WORKER_UNHEALTHY** | Worker health check fails | 3 consecutive failures | Critical |
| **ERROR_RATE_HIGH** | Error rate exceeds threshold | 5% over 5 minutes | Warning |
| **THROUGHPUT_LOW** | Events/sec below threshold | 50% drop from baseline | Warning |

## Alert Configuration

### Creating an Alert Configuration

Use the Alert Configuration API to create or update alert rules:

```bash
# Create/update SLA breach alert
PUT /alerts/config/SLA_BREACH?tenant_id=TENANT_001
{
  "alert_type": "SLA_BREACH",
  "enabled": true,
  "threshold": null,
  "threshold_unit": null,
  "channels": [
    {
      "type": "webhook",
      "url": "https://your-webhook-endpoint.com/alerts"
    },
    {
      "type": "email",
      "address": "ops-team@example.com"
    }
  ],
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00",
  "escalation_minutes": 30
}
```

### Alert Configuration Fields

- **alert_type**: One of the alert types listed above
- **enabled**: Whether the alert is active (default: true)
- **threshold**: Numeric threshold value (varies by alert type)
- **threshold_unit**: Unit for threshold (e.g., "percent", "count", "seconds")
- **channels**: List of notification channels (webhook or email)
- **quiet_hours_start**: Start time for quiet hours (HH:MM format, 24-hour)
- **quiet_hours_end**: End time for quiet hours (HH:MM format, 24-hour)
- **escalation_minutes**: Minutes before escalating unacknowledged alerts

### Notification Channels

#### Webhook Channel

Webhook alerts are sent as HTTP POST requests with JSON payload:

```json
{
  "alert_id": "ALT-001",
  "alert_type": "SLA_BREACH",
  "tenant_id": "TENANT_001",
  "severity": "critical",
  "title": "SLA Breach: Exception EXC-123",
  "message": "Exception EXC-123 exceeded SLA deadline by 2 hours",
  "timestamp": "2025-01-15T10:30:00Z",
  "details": {
    "exception_id": "EXC-123",
    "sla_deadline": "2025-01-15T08:30:00Z",
    "current_status": "open"
  }
}
```

**HMAC Signing**: For security, webhook payloads can be signed with HMAC-SHA256. Include the signature in the `X-Alert-Signature` header:

```
X-Alert-Signature: sha256=<hmac_signature>
```

#### Email Channel

Email alerts are sent via configured SMTP or SendGrid provider. The email includes:
- Alert title and message
- Alert details (formatted JSON)
- Links to acknowledge/resolve (if configured)

**Email Configuration**: Set SMTP or SendGrid credentials in environment variables:
- `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`
- Or `SENDGRID_API_KEY`

## Alert Thresholds

### SLA_BREACH
- **Threshold**: Not applicable (triggers immediately when SLA expires)
- **Evaluation**: Checks exceptions where `sla_deadline < now()` and status is not resolved

### SLA_IMMINENT
- **Threshold**: Percentage of SLA window elapsed (default: 80%)
- **Evaluation**: Checks exceptions where `(now() - created_at) / sla_window >= threshold`

### DLQ_GROWTH
- **Threshold**: Number of DLQ entries (default: 100)
- **Evaluation**: Counts pending DLQ entries for tenant

### WORKER_UNHEALTHY
- **Threshold**: Number of consecutive failures (default: 3)
- **Evaluation**: Tracks worker health check failures

### ERROR_RATE_HIGH
- **Threshold**: Error rate percentage (default: 5%)
- **Evaluation**: Calculates `failed_events / total_events` over time window (default: 5 minutes)

### THROUGHPUT_LOW
- **Threshold**: Percentage drop from baseline (default: 50%)
- **Evaluation**: Compares current `events/sec` to baseline (calculated from last 24 hours)

## Alert Lifecycle

1. **Triggered**: Alert condition is met, notification sent
2. **Acknowledged**: Operator acknowledges the alert (via API or UI)
3. **Resolved**: Issue is resolved, alert marked as resolved
4. **Suppressed**: Alert suppressed during quiet hours or by policy

### Acknowledging Alerts

```bash
# Acknowledge an alert
POST /alerts/history/{alert_id}/acknowledge?tenant_id=TENANT_001&acknowledged_by=operator@example.com
```

### Resolving Alerts

```bash
# Resolve an alert
POST /alerts/history/{alert_id}/resolve?tenant_id=TENANT_001&resolved_by=operator@example.com
```

## Alert History

View alert history with filtering:

```bash
# List alerts
GET /alerts/history?tenant_id=TENANT_001&status=triggered&alert_type=SLA_BREACH&page=1&page_size=50

# Get alert details
GET /alerts/history/{alert_id}?tenant_id=TENANT_001

# Get alert counts
GET /alerts/counts?tenant_id=TENANT_001
```

## Quiet Hours

Configure quiet hours to suppress non-critical alerts during off-hours:

```json
{
  "quiet_hours_start": "22:00",
  "quiet_hours_end": "08:00"
}
```

- Alerts with severity "critical" are **never suppressed**
- Alerts with severity "warning" are suppressed during quiet hours
- Quiet hours are evaluated in UTC

## Escalation Policy

If an alert is not acknowledged within the escalation timeout, it can trigger additional notifications:

```json
{
  "escalation_minutes": 30
}
```

After 30 minutes, if the alert is still unacknowledged, escalation notifications are sent to configured escalation channels.

## Troubleshooting Alerts

### Alert Not Triggering

1. **Check alert is enabled**:
   ```bash
   GET /alerts/config/{alert_type}?tenant_id=TENANT_001
   ```
   Verify `enabled: true`

2. **Check threshold values**: Ensure threshold is appropriate for your workload
   - For ERROR_RATE_HIGH: Check if error rate is actually above threshold
   - For THROUGHPUT_LOW: Verify baseline calculation is correct

3. **Check quiet hours**: Verify alert is not being suppressed during quiet hours

4. **Check evaluation service**: Ensure alert evaluation service is running
   - Evaluation runs every 1 minute (configurable)
   - Check backend logs for evaluation errors

### Alert Triggering Too Frequently

1. **Adjust threshold**: Increase threshold value to reduce sensitivity
   ```bash
   PUT /alerts/config/ERROR_RATE_HIGH?tenant_id=TENANT_001
   {
     "threshold": 10.0,  # Increase from 5% to 10%
     "threshold_unit": "percent"
   }
   ```

2. **Enable quiet hours**: Suppress alerts during off-hours

3. **Check for underlying issues**: Frequent alerts may indicate real problems
   - High error rate: Investigate worker failures
   - DLQ growth: Check DLQ entries for patterns

### Notifications Not Received

1. **Verify channel configuration**:
   ```bash
   GET /alerts/config/{alert_type}?tenant_id=TENANT_001
   ```
   Check `channels` array contains valid webhook URL or email address

2. **Test webhook endpoint**:
   ```bash
   # Use curl to test webhook
   curl -X POST https://your-webhook-endpoint.com/alerts \
     -H "Content-Type: application/json" \
     -d '{"test": true}'
   ```

3. **Check email configuration**: Verify SMTP/SendGrid credentials are set correctly

4. **Check notification delivery status**:
   ```bash
   GET /alerts/history/{alert_id}?tenant_id=TENANT_001
   ```
   Check `notification_sent` field

5. **Review backend logs**: Check for notification delivery errors
   ```bash
   docker-compose logs backend | grep -i alert
   ```

### Alert Evaluation Errors

If alert evaluation fails:

1. **Check service health**: Verify alert evaluation service is running
2. **Check database connectivity**: Alert evaluation requires database access
3. **Review evaluation logs**: Check for specific error messages
4. **Verify data availability**: Ensure metrics data exists for evaluation

## Best Practices

1. **Start with conservative thresholds**: Begin with higher thresholds and adjust down as needed
2. **Use quiet hours**: Configure quiet hours to reduce alert fatigue
3. **Set escalation policies**: Configure escalation for critical alerts
4. **Monitor alert history**: Regularly review alert patterns to tune thresholds
5. **Test webhook endpoints**: Verify webhook endpoints respond correctly
6. **Use alert severity**: Configure critical alerts to never be suppressed
7. **Acknowledge alerts promptly**: Acknowledge alerts to track response times
8. **Resolve alerts when fixed**: Mark alerts as resolved to maintain accurate history

## API Reference

### Alert Configuration

- `GET /alerts/config?tenant_id=...` - List alert configs
- `GET /alerts/config/{alert_type}?tenant_id=...` - Get alert config
- `PUT /alerts/config/{alert_type}?tenant_id=...` - Create/update alert config
- `DELETE /alerts/config/{alert_type}?tenant_id=...` - Delete alert config

### Alert History

- `GET /alerts/history?tenant_id=...` - List alerts
- `GET /alerts/history/{alert_id}?tenant_id=...` - Get alert details
- `POST /alerts/history/{alert_id}/acknowledge` - Acknowledge alert
- `POST /alerts/history/{alert_id}/resolve` - Resolve alert
- `GET /alerts/counts?tenant_id=...` - Get alert counts

## Related Documentation

- `docs/phase10-ops-governance-mvp.md` - Phase 10 specification
- `docs/ops-runbook.md` - Operations runbook
- API documentation: `http://localhost:8000/docs` (when running locally)

