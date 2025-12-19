"""
Alert Repository for Phase 10 (P10-5 through P10-9).

Provides CRUD operations for alert configuration and history with tenant isolation.

Reference: docs/phase10-ops-governance-mvp.md Section 6
"""

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import and_, desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.models import (
    AlertConfig,
    AlertHistory,
    AlertStatus,
    AlertType,
)
from src.repository.base import AbstractBaseRepository, PaginatedResult

logger = logging.getLogger(__name__)


def generate_alert_id() -> str:
    """Generate a unique alert ID."""
    return f"ALT-{uuid.uuid4().hex[:12].upper()}"


@dataclass
class AlertConfigSummary:
    """Summary of alert configuration for a tenant."""
    tenant_id: str
    total_configs: int
    enabled_count: int
    disabled_count: int
    by_type: dict[str, bool]


class AlertConfigRepository(AbstractBaseRepository[AlertConfig]):
    """
    Repository for alert configuration management.

    Provides:
    - Create/update alert configuration
    - Get alert config by tenant and type
    - List all configs for a tenant
    - Enable/disable alerts

    All operations enforce tenant isolation.
    """

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[AlertConfig]:
        """Get alert config by ID with tenant isolation."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        try:
            config_id = int(id)
        except (ValueError, TypeError):
            return None

        query = (
            select(AlertConfig)
            .where(AlertConfig.id == config_id)
            .where(AlertConfig.tenant_id == tenant_id)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[AlertConfig]:
        """List alert configs for a tenant with pagination."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(AlertConfig).where(AlertConfig.tenant_id == tenant_id)

        if filters.get("enabled") is not None:
            query = query.where(AlertConfig.enabled == filters["enabled"])
        if filters.get("alert_type"):
            query = query.where(AlertConfig.alert_type == filters["alert_type"])

        query = query.order_by(AlertConfig.alert_type)

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_config(
        self, tenant_id: str, alert_type: str
    ) -> Optional[AlertConfig]:
        """
        Get alert configuration for a specific type.

        Args:
            tenant_id: Tenant identifier
            alert_type: Alert type (sla_breach, dlq_growth, etc.)

        Returns:
            AlertConfig or None if not configured
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(AlertConfig)
            .where(AlertConfig.tenant_id == tenant_id)
            .where(AlertConfig.alert_type == alert_type)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def create_or_update_config(
        self,
        tenant_id: str,
        alert_type: str,
        enabled: bool = True,
        threshold: Optional[float] = None,
        threshold_unit: Optional[str] = None,
        channels: Optional[list[dict]] = None,
        quiet_hours_start: Optional[str] = None,
        quiet_hours_end: Optional[str] = None,
        escalation_minutes: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> AlertConfig:
        """
        Create or update alert configuration.

        Args:
            tenant_id: Tenant identifier
            alert_type: Alert type
            enabled: Whether alert is enabled
            threshold: Alert threshold value
            threshold_unit: Unit for threshold
            channels: Notification channels
            quiet_hours_start: Start of quiet hours (HH:MM)
            quiet_hours_end: End of quiet hours (HH:MM)
            escalation_minutes: Minutes before escalation
            metadata: Additional configuration

        Returns:
            Created or updated AlertConfig
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        # Check if config exists
        existing = await self.get_config(tenant_id, alert_type)

        if existing:
            # Update existing
            existing.enabled = enabled
            if threshold is not None:
                existing.threshold = threshold
            if threshold_unit is not None:
                existing.threshold_unit = threshold_unit
            if channels is not None:
                existing.channels = channels
            if quiet_hours_start is not None:
                from datetime import time
                h, m = map(int, quiet_hours_start.split(":"))
                existing.quiet_hours_start = time(h, m)
            if quiet_hours_end is not None:
                from datetime import time
                h, m = map(int, quiet_hours_end.split(":"))
                existing.quiet_hours_end = time(h, m)
            if escalation_minutes is not None:
                existing.escalation_minutes = escalation_minutes
            if metadata is not None:
                existing.config_metadata = metadata

            await self.session.flush()
            await self.session.refresh(existing)

            logger.info(
                f"Updated alert config: tenant_id={tenant_id}, "
                f"alert_type={alert_type}, enabled={enabled}"
            )
            return existing
        else:
            # Create new
            config = AlertConfig(
                tenant_id=tenant_id,
                alert_type=alert_type,
                enabled=enabled,
                threshold=threshold,
                threshold_unit=threshold_unit,
                channels=channels or [],
                escalation_minutes=escalation_minutes,
                config_metadata=metadata,
            )

            if quiet_hours_start:
                from datetime import time
                h, m = map(int, quiet_hours_start.split(":"))
                config.quiet_hours_start = time(h, m)
            if quiet_hours_end:
                from datetime import time
                h, m = map(int, quiet_hours_end.split(":"))
                config.quiet_hours_end = time(h, m)

            self.session.add(config)
            await self.session.flush()
            await self.session.refresh(config)

            logger.info(
                f"Created alert config: tenant_id={tenant_id}, "
                f"alert_type={alert_type}, enabled={enabled}"
            )
            return config

    async def set_enabled(
        self, tenant_id: str, alert_type: str, enabled: bool
    ) -> Optional[AlertConfig]:
        """Enable or disable an alert type."""
        config = await self.get_config(tenant_id, alert_type)
        if not config:
            return None

        config.enabled = enabled
        await self.session.flush()
        await self.session.refresh(config)

        logger.info(
            f"Alert config enabled={enabled}: tenant_id={tenant_id}, "
            f"alert_type={alert_type}"
        )
        return config

    async def delete_config(self, tenant_id: str, alert_type: str) -> bool:
        """Delete an alert configuration."""
        config = await self.get_config(tenant_id, alert_type)
        if not config:
            return False

        await self.session.delete(config)
        await self.session.flush()

        logger.info(
            f"Deleted alert config: tenant_id={tenant_id}, alert_type={alert_type}"
        )
        return True

    async def get_enabled_configs(self, tenant_id: str) -> list[AlertConfig]:
        """Get all enabled alert configs for a tenant."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(AlertConfig)
            .where(AlertConfig.tenant_id == tenant_id)
            .where(AlertConfig.enabled == True)
            .order_by(AlertConfig.alert_type)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())


class AlertHistoryRepository(AbstractBaseRepository[AlertHistory]):
    """
    Repository for alert history management.

    Provides:
    - Create alert entries
    - Update alert status (acknowledge, resolve)
    - List alerts by tenant with filtering
    - Get alert statistics

    All operations enforce tenant isolation.
    """

    async def get_by_id(self, id: str, tenant_id: str) -> Optional[AlertHistory]:
        """Get alert by alert_id with tenant isolation."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(AlertHistory)
            .where(AlertHistory.alert_id == id)
            .where(AlertHistory.tenant_id == tenant_id)
        )

        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_tenant(
        self,
        tenant_id: str,
        page: int = 1,
        page_size: int = 50,
        **filters,
    ) -> PaginatedResult[AlertHistory]:
        """List alerts for a tenant with pagination."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = select(AlertHistory).where(AlertHistory.tenant_id == tenant_id)

        if filters.get("status"):
            query = query.where(AlertHistory.status == filters["status"])
        if filters.get("alert_type"):
            query = query.where(AlertHistory.alert_type == filters["alert_type"])
        if filters.get("severity"):
            query = query.where(AlertHistory.severity == filters["severity"])
        if filters.get("from_date"):
            query = query.where(AlertHistory.triggered_at >= filters["from_date"])
        if filters.get("to_date"):
            query = query.where(AlertHistory.triggered_at <= filters["to_date"])

        query = query.order_by(desc(AlertHistory.triggered_at))

        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.session.execute(count_query)
        total = count_result.scalar() or 0

        # Apply pagination
        offset = (page - 1) * page_size
        query = query.limit(page_size).offset(offset)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_alert(
        self,
        tenant_id: str,
        alert_type: str,
        severity: str,
        title: str,
        message: Optional[str] = None,
        details: Optional[dict] = None,
    ) -> AlertHistory:
        """
        Create a new alert entry.

        Args:
            tenant_id: Tenant identifier
            alert_type: Type of alert
            severity: Alert severity (info, warning, critical)
            title: Short alert title
            message: Detailed message
            details: Additional context

        Returns:
            Created AlertHistory entry
        """
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required")

        alert = AlertHistory(
            alert_id=generate_alert_id(),
            tenant_id=tenant_id,
            alert_type=alert_type,
            severity=severity,
            title=title,
            message=message,
            details=details,
            status=AlertStatus.TRIGGERED.value,
            triggered_at=datetime.now(timezone.utc),
        )

        self.session.add(alert)
        await self.session.flush()
        await self.session.refresh(alert)

        logger.info(
            f"Created alert: alert_id={alert.alert_id}, tenant_id={tenant_id}, "
            f"alert_type={alert_type}, severity={severity}"
        )
        return alert

    async def acknowledge_alert(
        self, alert_id: str, tenant_id: str, acknowledged_by: str
    ) -> Optional[AlertHistory]:
        """
        Acknowledge an alert.

        Args:
            alert_id: Alert identifier
            tenant_id: Tenant identifier
            acknowledged_by: User who acknowledged

        Returns:
            Updated AlertHistory or None if not found
        """
        alert = await self.get_by_id(alert_id, tenant_id)
        if not alert:
            return None

        alert.status = AlertStatus.ACKNOWLEDGED.value
        alert.acknowledged_at = datetime.now(timezone.utc)
        alert.acknowledged_by = acknowledged_by

        await self.session.flush()
        await self.session.refresh(alert)

        logger.info(
            f"Alert acknowledged: alert_id={alert_id}, "
            f"acknowledged_by={acknowledged_by}"
        )
        return alert

    async def resolve_alert(
        self, alert_id: str, tenant_id: str, resolved_by: str
    ) -> Optional[AlertHistory]:
        """
        Resolve an alert.

        Args:
            alert_id: Alert identifier
            tenant_id: Tenant identifier
            resolved_by: User who resolved

        Returns:
            Updated AlertHistory or None if not found
        """
        alert = await self.get_by_id(alert_id, tenant_id)
        if not alert:
            return None

        alert.status = AlertStatus.RESOLVED.value
        alert.resolved_at = datetime.now(timezone.utc)
        alert.resolved_by = resolved_by

        await self.session.flush()
        await self.session.refresh(alert)

        logger.info(
            f"Alert resolved: alert_id={alert_id}, resolved_by={resolved_by}"
        )
        return alert

    async def update_notification_status(
        self,
        alert_id: str,
        tenant_id: str,
        success: bool,
        error: Optional[str] = None,
    ) -> Optional[AlertHistory]:
        """Update notification delivery status."""
        alert = await self.get_by_id(alert_id, tenant_id)
        if not alert:
            return None

        alert.notification_sent = success
        alert.notification_error = error

        await self.session.flush()
        await self.session.refresh(alert)

        return alert

    async def get_active_alerts(
        self, tenant_id: str, limit: int = 100
    ) -> list[AlertHistory]:
        """Get triggered (non-resolved) alerts for a tenant."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(AlertHistory)
            .where(AlertHistory.tenant_id == tenant_id)
            .where(AlertHistory.status.in_([
                AlertStatus.TRIGGERED.value,
                AlertStatus.ACKNOWLEDGED.value,
            ]))
            .order_by(desc(AlertHistory.triggered_at))
            .limit(limit)
        )

        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_alert_counts(self, tenant_id: str) -> dict[str, int]:
        """Get alert counts by status for a tenant."""
        if not tenant_id or not tenant_id.strip():
            raise ValueError("tenant_id is required for tenant isolation")

        query = (
            select(
                AlertHistory.status,
                func.count(AlertHistory.id).label("count"),
            )
            .where(AlertHistory.tenant_id == tenant_id)
            .group_by(AlertHistory.status)
        )

        result = await self.session.execute(query)
        return {row[0]: row[1] for row in result.fetchall()}
