"""
Alert API routes for Phase 10 (P10-6, P10-9).

Provides endpoints for alert configuration and history management.

Reference: docs/phase10-ops-governance-mvp.md Section 6
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi import status as http_status
from pydantic import BaseModel, Field

from src.infrastructure.db.session import get_db_session_context
from src.infrastructure.db.models import AlertConfig
from src.infrastructure.repositories.alert_repository import (
    AlertConfigRepository,
    AlertHistoryRepository,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/alerts", tags=["alerts"])


# =============================================================================
# P10-6: Alert Configuration Models and Endpoints
# =============================================================================


class ChannelConfig(BaseModel):
    """Notification channel configuration."""
    type: str = Field(..., description="Channel type (webhook, email)")
    url: Optional[str] = Field(None, description="Webhook URL")
    address: Optional[str] = Field(None, description="Email address")


class AlertConfigRequest(BaseModel):
    """Request body for creating/updating alert config."""
    alert_type: Optional[str] = Field(None, description="Alert type (sla_breach, dlq_growth, etc.)")
    alertType: Optional[str] = Field(None, description="Alert type (camelCase for frontend)")
    name: Optional[str] = Field(None, description="Alert name")
    enabled: bool = Field(True, description="Whether alert is enabled")
    threshold: Optional[float] = Field(None, description="Alert threshold value")
    thresholdValue: Optional[float] = Field(None, description="Alert threshold value (camelCase)")
    threshold_unit: Optional[str] = Field(None, description="Threshold unit")
    thresholdUnit: Optional[str] = Field(None, description="Threshold unit (camelCase)")
    channels: Optional[list] = Field(default_factory=list, description="Notification channels (can be ChannelConfig, dict, or string)")
    quiet_hours_start: Optional[str] = Field(None, description="Quiet hours start (HH:MM)")
    quiet_hours_end: Optional[str] = Field(None, description="Quiet hours end (HH:MM)")
    escalation_minutes: Optional[int] = Field(None, description="Escalation timeout in minutes")


class AlertConfigResponse(BaseModel):
    """Response model for alert configuration."""
    id: str = Field(..., description="Configuration ID (as string for frontend compatibility)")
    tenant_id: str = Field(..., description="Tenant identifier")
    alert_type: str = Field(..., description="Alert type")
    name: Optional[str] = Field(None, description="Alert name (from metadata)")
    enabled: bool = Field(..., description="Whether enabled")
    threshold: Optional[float] = Field(None, description="Threshold value")
    threshold_unit: Optional[str] = Field(None, description="Threshold unit")
    channels: list[dict] = Field(..., description="Notification channels")
    quiet_hours_start: Optional[str] = Field(None, description="Quiet hours start")
    quiet_hours_end: Optional[str] = Field(None, description="Quiet hours end")
    escalation_minutes: Optional[int] = Field(None, description="Escalation minutes")
    created_at: str = Field(..., description="Created timestamp")
    updated_at: str = Field(..., description="Updated timestamp")


class AlertConfigListResponse(BaseModel):
    """Response model for alert config list."""
    items: list[AlertConfigResponse] = Field(..., description="Alert configurations")
    total: int = Field(..., description="Total count")


@router.get("/config", response_model=AlertConfigListResponse)
async def list_alert_configs(
    tenant_id: str = Query(..., description="Tenant identifier"),
    enabled: Optional[bool] = Query(None, description="Filter by enabled status"),
) -> AlertConfigListResponse:
    """
    List alert configurations for a tenant.

    GET /alerts/config?tenant_id=...&enabled=true
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertConfigRepository(session)
            result = await repo.list_by_tenant(
                tenant_id=tenant_id,
                page=1,
                page_size=100,
                enabled=enabled,
            )

            items = [
                AlertConfigResponse(
                    id=str(c.id),
                    tenant_id=c.tenant_id,
                    alert_type=c.alert_type,
                    name=(c.config_metadata or {}).get("name") if c.config_metadata else None,
                    enabled=c.enabled,
                    threshold=float(c.threshold) if c.threshold else None,
                    threshold_unit=c.threshold_unit,
                    channels=c.channels or [],
                    quiet_hours_start=c.quiet_hours_start.strftime("%H:%M") if c.quiet_hours_start else None,
                    quiet_hours_end=c.quiet_hours_end.strftime("%H:%M") if c.quiet_hours_end else None,
                    escalation_minutes=c.escalation_minutes,
                    created_at=c.created_at.isoformat() if c.created_at else "",
                    updated_at=c.updated_at.isoformat() if c.updated_at else "",
                )
                for c in result.items
            ]

            return AlertConfigListResponse(items=items, total=result.total)
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to list alert configs: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert configurations: {str(e)}",
        )


@router.get("/config/{alert_type}", response_model=AlertConfigResponse)
async def get_alert_config(
    alert_type: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> AlertConfigResponse:
    """
    Get alert configuration for a specific type.

    GET /alerts/config/{alert_type}?tenant_id=...
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertConfigRepository(session)
            config = await repo.get_config(tenant_id, alert_type)

            if not config:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Alert config not found: {alert_type}",
                )

            return AlertConfigResponse(
                id=str(config.id),
                tenant_id=config.tenant_id,
                alert_type=config.alert_type,
                name=(config.config_metadata or {}).get("name") if config.config_metadata else None,
                enabled=config.enabled,
                threshold=float(config.threshold) if config.threshold else None,
                threshold_unit=config.threshold_unit,
                channels=config.channels or [],
                quiet_hours_start=config.quiet_hours_start.strftime("%H:%M") if config.quiet_hours_start else None,
                quiet_hours_end=config.quiet_hours_end.strftime("%H:%M") if config.quiet_hours_end else None,
                escalation_minutes=config.escalation_minutes,
                created_at=config.created_at.isoformat() if config.created_at else "",
                updated_at=config.updated_at.isoformat() if config.updated_at else "",
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get alert config: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert configuration: {str(e)}",
        )


def _normalize_alert_config_request(body: dict | AlertConfigRequest) -> dict:
    """Normalize frontend request to backend format."""
    # Handle both dict (from FastAPI) and AlertConfigRequest
    if isinstance(body, dict):
        alert_type = body.get("alert_type") or body.get("alertType")
        threshold = body.get("threshold") or body.get("thresholdValue")
        threshold_unit = body.get("threshold_unit") or body.get("thresholdUnit")
        enabled = body.get("enabled", True)
        channels = body.get("channels", [])
        name = body.get("name")
        quiet_hours_start = body.get("quiet_hours_start")
        quiet_hours_end = body.get("quiet_hours_end")
        escalation_minutes = body.get("escalation_minutes")
    else:
        # AlertConfigRequest object
        alert_type = body.alert_type or body.alertType
        threshold = body.threshold or body.thresholdValue
        threshold_unit = body.threshold_unit or body.thresholdUnit
        enabled = body.enabled
        channels = body.channels or []
        name = body.name
        quiet_hours_start = body.quiet_hours_start
        quiet_hours_end = body.quiet_hours_end
        escalation_minutes = body.escalation_minutes
    
    if not alert_type:
        raise ValueError("alert_type or alertType is required")
    
    # Convert to lowercase with underscores for backend
    alert_type = alert_type.lower().replace("-", "_")
    
    # Normalize channels - convert string[] to ChannelConfig objects
    normalized_channels = []
    if channels:
        for ch in channels:
            if isinstance(ch, str):
                # Frontend sends string[], convert to dict
                normalized_channels.append({"type": ch})
            elif isinstance(ch, dict):
                normalized_channels.append(ch)
            elif hasattr(ch, "model_dump"):
                normalized_channels.append(ch.model_dump())
            else:
                normalized_channels.append(ch)
    
    # Build metadata with name if provided
    metadata = {}
    if name:
        metadata["name"] = name
    
    return {
        "alert_type": alert_type,
        "enabled": enabled,
        "threshold": threshold,
        "threshold_unit": threshold_unit,
        "channels": normalized_channels,
        "quiet_hours_start": quiet_hours_start,
        "quiet_hours_end": quiet_hours_end,
        "escalation_minutes": escalation_minutes,
        "metadata": metadata if metadata else None,
    }


@router.post("/config", response_model=AlertConfigResponse)
async def create_alert_config(
    tenant_id: str = Query(..., description="Tenant identifier"),
    body: dict = ...,  # Accept dict to handle frontend format flexibly
) -> AlertConfigResponse:
    """
    Create a new alert configuration.

    POST /alerts/config?tenant_id=...
    """
    try:
        normalized = _normalize_alert_config_request(body)
        
        async with get_db_session_context() as session:
            repo = AlertConfigRepository(session)
            config = await repo.create_or_update_config(
                tenant_id=tenant_id,
                alert_type=normalized["alert_type"],
                enabled=normalized["enabled"],
                threshold=normalized["threshold"],
                threshold_unit=normalized["threshold_unit"],
                channels=normalized["channels"],
                quiet_hours_start=normalized["quiet_hours_start"],
                quiet_hours_end=normalized["quiet_hours_end"],
                escalation_minutes=normalized["escalation_minutes"],
                metadata=normalized["metadata"],
            )

            await session.commit()

            return AlertConfigResponse(
                id=str(config.id),
                tenant_id=config.tenant_id,
                alert_type=config.alert_type,
                name=(config.config_metadata or {}).get("name") if config.config_metadata else None,
                enabled=config.enabled,
                threshold=float(config.threshold) if config.threshold else None,
                threshold_unit=config.threshold_unit,
                channels=config.channels or [],
                quiet_hours_start=config.quiet_hours_start.strftime("%H:%M") if config.quiet_hours_start else None,
                quiet_hours_end=config.quiet_hours_end.strftime("%H:%M") if config.quiet_hours_end else None,
                escalation_minutes=config.escalation_minutes,
                created_at=config.created_at.isoformat() if config.created_at else "",
                updated_at=config.updated_at.isoformat() if config.updated_at else "",
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create alert config: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create alert configuration: {str(e)}",
        )


@router.put("/config/{alert_type_or_id}", response_model=AlertConfigResponse)
async def create_or_update_alert_config(
    alert_type_or_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
    body: dict = ...,  # Accept dict to handle frontend format flexibly
) -> AlertConfigResponse:
    """
    Create or update alert configuration.

    PUT /alerts/config/{alert_type}?tenant_id=... (uses alert_type from path)
    PUT /alerts/config/{id}?tenant_id=... (uses id from path, alert_type from body)
    """
    try:
        # Determine if alert_type_or_id is an ID (numeric) or alert_type (string)
        is_id = False
        try:
            int(alert_type_or_id)
            is_id = True
        except ValueError:
            pass
        
        normalized = _normalize_alert_config_request(body)
        
        if is_id:
            # ID-based update - get existing config first
            async with get_db_session_context() as session:
                repo = AlertConfigRepository(session)
                existing = await repo.get_by_id(alert_type_or_id, tenant_id)
                if not existing:
                    raise HTTPException(
                        status_code=http_status.HTTP_404_NOT_FOUND,
                        detail=f"Alert config not found: {alert_type_or_id}",
                    )
                alert_type = existing.alert_type
        else:
            # Use alert_type from path, but override if provided in body
            alert_type = alert_type_or_id.lower().replace("-", "_")
            if normalized["alert_type"]:
                alert_type = normalized["alert_type"]
        
        async with get_db_session_context() as session:
            repo = AlertConfigRepository(session)
            config = await repo.create_or_update_config(
                tenant_id=tenant_id,
                alert_type=alert_type,
                enabled=normalized["enabled"],
                threshold=normalized["threshold"],
                threshold_unit=normalized["threshold_unit"],
                channels=normalized["channels"],
                quiet_hours_start=normalized["quiet_hours_start"],
                quiet_hours_end=normalized["quiet_hours_end"],
                escalation_minutes=normalized["escalation_minutes"],
                metadata=normalized["metadata"],
            )

            await session.commit()

            return AlertConfigResponse(
                id=str(config.id),
                tenant_id=config.tenant_id,
                alert_type=config.alert_type,
                name=(config.config_metadata or {}).get("name") if config.config_metadata else None,
                enabled=config.enabled,
                threshold=float(config.threshold) if config.threshold else None,
                threshold_unit=config.threshold_unit,
                channels=config.channels or [],
                quiet_hours_start=config.quiet_hours_start.strftime("%H:%M") if config.quiet_hours_start else None,
                quiet_hours_end=config.quiet_hours_end.strftime("%H:%M") if config.quiet_hours_end else None,
                escalation_minutes=config.escalation_minutes,
                created_at=config.created_at.isoformat() if config.created_at else "",
                updated_at=config.updated_at.isoformat() if config.updated_at else "",
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to create/update alert config: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create/update alert configuration: {str(e)}",
        )


@router.delete("/config/{alert_type_or_id}")
async def delete_alert_config(
    alert_type_or_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict:
    """
    Delete alert configuration.

    DELETE /alerts/config/{alert_type}?tenant_id=... (uses alert_type from path)
    DELETE /alerts/config/{id}?tenant_id=... (uses id from path)
    """
    try:
        # Determine if alert_type_or_id is an ID (numeric) or alert_type (string)
        is_id = False
        try:
            config_id = int(alert_type_or_id)
            is_id = True
        except ValueError:
            pass
        
        async with get_db_session_context() as session:
            repo = AlertConfigRepository(session)
            
            if is_id:
                # ID-based delete
                existing = await repo.get_by_id(alert_type_or_id, tenant_id)
                if not existing:
                    raise HTTPException(
                        status_code=http_status.HTTP_404_NOT_FOUND,
                        detail=f"Alert config not found: {alert_type_or_id}",
                    )
                alert_type = existing.alert_type
                # Delete by ID
                from sqlalchemy import delete
                stmt = delete(AlertConfig).where(
                    AlertConfig.id == config_id,
                    AlertConfig.tenant_id == tenant_id
                )
                await session.execute(stmt)
                deleted = True
            else:
                # Alert type-based delete
                alert_type = alert_type_or_id.lower().replace("-", "_")
                deleted = await repo.delete_config(tenant_id, alert_type)

            if not deleted:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Alert config not found: {alert_type_or_id}",
                )

            await session.commit()

            return {"deleted": True, "alert_type": alert_type if not is_id else None, "id": alert_type_or_id if is_id else None}
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to delete alert config: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete alert configuration: {str(e)}",
        )


# =============================================================================
# P10-9: Alert History/Log Endpoints
# =============================================================================


class AlertHistoryResponse(BaseModel):
    """Response model for alert history entry."""
    alert_id: str = Field(..., description="Alert identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    alert_type: str = Field(..., description="Alert type")
    severity: str = Field(..., description="Alert severity")
    title: str = Field(..., description="Alert title")
    message: Optional[str] = Field(None, description="Alert message")
    details: Optional[dict] = Field(None, description="Alert details")
    status: str = Field(..., description="Alert status")
    triggered_at: str = Field(..., description="When triggered")
    acknowledged_at: Optional[str] = Field(None, description="When acknowledged")
    acknowledged_by: Optional[str] = Field(None, description="Who acknowledged")
    resolved_at: Optional[str] = Field(None, description="When resolved")
    resolved_by: Optional[str] = Field(None, description="Who resolved")
    notification_sent: bool = Field(..., description="Whether notification was sent")


class AlertHistoryListResponse(BaseModel):
    """Response model for alert history list."""
    items: list[AlertHistoryResponse] = Field(..., description="Alert history entries")
    total: int = Field(..., description="Total count")
    page: int = Field(..., description="Current page")
    page_size: int = Field(..., description="Page size")


class AlertCountsResponse(BaseModel):
    """Response model for alert counts."""
    tenant_id: str = Field(..., description="Tenant identifier")
    triggered: int = Field(0, description="Triggered count")
    acknowledged: int = Field(0, description="Acknowledged count")
    resolved: int = Field(0, description="Resolved count")
    suppressed: int = Field(0, description="Suppressed count")


@router.get("/history", response_model=AlertHistoryListResponse)
async def list_alert_history(
    tenant_id: str = Query(..., description="Tenant identifier"),
    status: Optional[str] = Query(None, description="Filter by status"),
    alert_type: Optional[str] = Query(None, description="Filter by type"),
    severity: Optional[str] = Query(None, description="Filter by severity"),
    from_date: Optional[str] = Query(None, description="From date (ISO format)"),
    to_date: Optional[str] = Query(None, description="To date (ISO format)"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=500, description="Page size"),
) -> AlertHistoryListResponse:
    """
    List alert history for a tenant.

    GET /alerts/history?tenant_id=...&status=triggered&page=1
    """
    # Parse dates
    from_dt = None
    to_dt = None
    if from_date:
        try:
            from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if to_date:
        try:
            to_dt = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    try:
        async with get_db_session_context() as session:
            repo = AlertHistoryRepository(session)
            result = await repo.list_by_tenant(
                tenant_id=tenant_id,
                page=page,
                page_size=page_size,
                status=status,
                alert_type=alert_type,
                severity=severity,
                from_date=from_dt,
                to_date=to_dt,
            )

            items = [
                AlertHistoryResponse(
                    alert_id=a.alert_id,
                    tenant_id=a.tenant_id,
                    alert_type=a.alert_type,
                    severity=a.severity,
                    title=a.title,
                    message=a.message,
                    details=a.details,
                    status=a.status,
                    triggered_at=a.triggered_at.isoformat() if a.triggered_at else "",
                    acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                    acknowledged_by=a.acknowledged_by,
                    resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
                    resolved_by=a.resolved_by,
                    notification_sent=a.notification_sent,
                )
                for a in result.items
            ]

            return AlertHistoryListResponse(
                items=items,
                total=result.total,
                page=page,
                page_size=page_size,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        # Check if it's a table doesn't exist error
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "no such table" in error_msg or "relation" in error_msg:
            logger.warning(f"Alert history table may not exist yet: {e}. Returning empty results.")
            return AlertHistoryListResponse(
                items=[],
                total=0,
                page=page,
                page_size=page_size,
            )
        logger.error(f"Failed to list alert history: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert history: {str(e)}",
        )


@router.get("/history/{alert_id}", response_model=AlertHistoryResponse)
async def get_alert(
    alert_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> AlertHistoryResponse:
    """
    Get a specific alert by ID.

    GET /alerts/history/{alert_id}?tenant_id=...
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertHistoryRepository(session)
            alert = await repo.get_by_id(alert_id, tenant_id)

            if not alert:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Alert not found: {alert_id}",
                )

            return AlertHistoryResponse(
                alert_id=alert.alert_id,
                tenant_id=alert.tenant_id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                message=alert.message,
                details=alert.details,
                status=alert.status,
                triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else "",
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                acknowledged_by=alert.acknowledged_by,
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
                resolved_by=alert.resolved_by,
                notification_sent=alert.notification_sent,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert: {str(e)}",
        )


@router.post("/history/{alert_id}/acknowledge", response_model=AlertHistoryResponse)
async def acknowledge_alert(
    alert_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
    acknowledged_by: str = Query(..., description="User acknowledging"),
) -> AlertHistoryResponse:
    """
    Acknowledge an alert.

    POST /alerts/history/{alert_id}/acknowledge?tenant_id=...&acknowledged_by=...
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertHistoryRepository(session)
            alert = await repo.acknowledge_alert(alert_id, tenant_id, acknowledged_by)

            if not alert:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Alert not found: {alert_id}",
                )

            await session.commit()

            return AlertHistoryResponse(
                alert_id=alert.alert_id,
                tenant_id=alert.tenant_id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                message=alert.message,
                details=alert.details,
                status=alert.status,
                triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else "",
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                acknowledged_by=alert.acknowledged_by,
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
                resolved_by=alert.resolved_by,
                notification_sent=alert.notification_sent,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to acknowledge alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to acknowledge alert: {str(e)}",
        )


@router.post("/history/{alert_id}/resolve", response_model=AlertHistoryResponse)
async def resolve_alert(
    alert_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
    resolved_by: str = Query(..., description="User resolving"),
) -> AlertHistoryResponse:
    """
    Resolve an alert.

    POST /alerts/history/{alert_id}/resolve?tenant_id=...&resolved_by=...
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertHistoryRepository(session)
            alert = await repo.resolve_alert(alert_id, tenant_id, resolved_by)

            if not alert:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail=f"Alert not found: {alert_id}",
                )

            await session.commit()

            return AlertHistoryResponse(
                alert_id=alert.alert_id,
                tenant_id=alert.tenant_id,
                alert_type=alert.alert_type,
                severity=alert.severity,
                title=alert.title,
                message=alert.message,
                details=alert.details,
                status=alert.status,
                triggered_at=alert.triggered_at.isoformat() if alert.triggered_at else "",
                acknowledged_at=alert.acknowledged_at.isoformat() if alert.acknowledged_at else None,
                acknowledged_by=alert.acknowledged_by,
                resolved_at=alert.resolved_at.isoformat() if alert.resolved_at else None,
                resolved_by=alert.resolved_by,
                notification_sent=alert.notification_sent,
            )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to resolve alert: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resolve alert: {str(e)}",
        )


@router.get("/active", response_model=AlertHistoryListResponse)
async def get_active_alerts(
    tenant_id: str = Query(..., description="Tenant identifier"),
    limit: int = Query(100, ge=1, le=500, description="Maximum results"),
) -> AlertHistoryListResponse:
    """
    Get active (non-resolved) alerts for a tenant.

    GET /alerts/active?tenant_id=...
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertHistoryRepository(session)
            alerts = await repo.get_active_alerts(tenant_id, limit)

            items = [
                AlertHistoryResponse(
                    alert_id=a.alert_id,
                    tenant_id=a.tenant_id,
                    alert_type=a.alert_type,
                    severity=a.severity,
                    title=a.title,
                    message=a.message,
                    details=a.details,
                    status=a.status,
                    triggered_at=a.triggered_at.isoformat() if a.triggered_at else "",
                    acknowledged_at=a.acknowledged_at.isoformat() if a.acknowledged_at else None,
                    acknowledged_by=a.acknowledged_by,
                    resolved_at=a.resolved_at.isoformat() if a.resolved_at else None,
                    resolved_by=a.resolved_by,
                    notification_sent=a.notification_sent,
                )
                for a in alerts
            ]

            return AlertHistoryListResponse(
                items=items,
                total=len(items),
                page=1,
                page_size=limit,
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get active alerts: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get active alerts: {str(e)}",
        )


@router.get("/counts", response_model=AlertCountsResponse)
async def get_alert_counts(
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> AlertCountsResponse:
    """
    Get alert counts by status for a tenant.

    GET /alerts/counts?tenant_id=...
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertHistoryRepository(session)
            counts = await repo.get_alert_counts(tenant_id)

            return AlertCountsResponse(
                tenant_id=tenant_id,
                triggered=counts.get("triggered", 0),
                acknowledged=counts.get("acknowledged", 0),
                resolved=counts.get("resolved", 0),
                suppressed=counts.get("suppressed", 0),
            )
    except ValueError as e:
        raise HTTPException(
            status_code=http_status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Failed to get alert counts: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get alert counts: {str(e)}",
        )


# =============================================================================
# Alert Channels Endpoints (for UI compatibility)
# =============================================================================


class AlertChannelResponse(BaseModel):
    """Response model for alert channel."""
    id: str = Field(..., description="Channel identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    channel_type: str = Field(..., description="Channel type (webhook, email)")
    config: dict = Field(..., description="Channel configuration")
    verified: bool = Field(False, description="Whether channel is verified")
    created_at: Optional[str] = Field(None, description="Created timestamp")


class AlertChannelListResponse(BaseModel):
    """Response model for alert channel list."""
    items: list[AlertChannelResponse] = Field(..., description="Alert channels")


@router.get("/channels", response_model=AlertChannelListResponse)
async def list_alert_channels(
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> AlertChannelListResponse:
    """
    List alert channels for a tenant.

    GET /alerts/channels?tenant_id=...
    
    Note: Channels are currently stored as part of alert configurations.
    This endpoint extracts unique channels from all alert configs.
    """
    try:
        async with get_db_session_context() as session:
            repo = AlertConfigRepository(session)
            result = await repo.list_by_tenant(
                tenant_id=tenant_id,
                page=1,
                page_size=1000,  # Get all configs to extract channels
            )
            
            # Extract unique channels from all alert configs
            channels_map: dict[str, AlertChannelResponse] = {}
            for config in result.items:
                if config.channels:
                    for idx, channel_data in enumerate(config.channels):
                        if isinstance(channel_data, dict):
                            channel_type = channel_data.get("type", "webhook")
                            # Create a unique ID for this channel (config_id + index)
                            channel_id = f"{config.id}-{idx}"
                            if channel_id not in channels_map:
                                channels_map[channel_id] = AlertChannelResponse(
                                    id=channel_id,
                                    tenant_id=tenant_id,
                                    channel_type=channel_type,
                                    config=channel_data,
                                    verified=False,  # TODO: Implement verification status
                                    created_at=config.created_at.isoformat() if config.created_at else None,
                                )
            
            return AlertChannelListResponse(items=list(channels_map.values()))
    except Exception as e:
        # Check if it's a table doesn't exist error
        error_msg = str(e).lower()
        if "does not exist" in error_msg or "no such table" in error_msg or "relation" in error_msg:
            logger.warning(f"Alert config table may not exist yet: {e}. Returning empty results.")
            return AlertChannelListResponse(items=[])
        logger.error(f"Failed to list alert channels: {e}", exc_info=True)
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list alert channels: {str(e)}",
        )


@router.post("/channels", response_model=AlertChannelResponse)
async def create_alert_channel(
    tenant_id: str = Query(..., description="Tenant identifier"),
    body: dict = ...,  # Accept flexible body for channel creation
) -> AlertChannelResponse:
    """
    Create a new alert channel.

    POST /alerts/channels?tenant_id=...
    
    Note: This is a stub implementation. Channels are managed as part of alert configurations.
    """
    raise HTTPException(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        detail="Direct channel creation is not yet supported. Channels are managed via alert configurations.",
    )


@router.post("/channels/{channel_id}/verify")
async def verify_alert_channel(
    channel_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict:
    """
    Verify an alert channel.

    POST /alerts/channels/{channel_id}/verify?tenant_id=...
    """
    raise HTTPException(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        detail="Channel verification is not yet implemented.",
    )


@router.delete("/channels/{channel_id}")
async def delete_alert_channel(
    channel_id: str,
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> dict:
    """
    Delete an alert channel.

    DELETE /alerts/channels/{channel_id}?tenant_id=...
    
    Note: This is a stub implementation. Channels are managed as part of alert configurations.
    """
    raise HTTPException(
        status_code=http_status.HTTP_501_NOT_IMPLEMENTED,
        detail="Direct channel deletion is not yet supported. Channels are managed via alert configurations.",
    )