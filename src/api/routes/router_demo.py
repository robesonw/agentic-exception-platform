"""
Demo API Routes - Backend APIs for demo mode management.

Provides endpoints for:
- Platform settings (demo-related)
- Demo bootstrap
- Demo status and run management
- Demo data reset
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.db.session import get_db_session
from src.infrastructure.repositories.demo_run_repository import DemoRunConflictError, DemoRunRepository
from src.infrastructure.repositories.platform_settings_repository import PlatformSettingsRepository
from src.demo.bootstrapper import DemoBootstrapperService
from src.demo.scenario_engine import DemoScenarioEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["demo"])


# =============================================================================
# Request/Response Models
# =============================================================================


class DemoSettingsResponse(BaseModel):
    """Demo settings response."""
    
    enabled: bool = Field(..., description="Demo mode enabled")
    catalog_path: Optional[str] = None
    catalog_version: Optional[str] = None
    bootstrap_on_start: bool = False
    
    scenarios_enabled: bool = True
    scenarios_mode: str = "continuous"
    scenarios_active: list[str] = []
    scenarios_tenants: list[str] = []
    
    frequency_seconds: int = 120
    duration_seconds: int = 120
    burst_count: int = 25
    intensity_multiplier: float = 1.0
    
    last_run_at: Optional[str] = None
    bootstrap_last_at: Optional[str] = None


class DemoSettingsUpdate(BaseModel):
    """Demo settings update request."""
    
    enabled: Optional[bool] = None
    scenarios_enabled: Optional[bool] = None
    scenarios_mode: Optional[str] = None
    scenarios_active: Optional[list[str]] = None
    scenarios_tenants: Optional[list[str]] = None
    frequency_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    burst_count: Optional[int] = None
    intensity_multiplier: Optional[float] = None


class DemoStatusResponse(BaseModel):
    """Demo status response."""
    
    enabled: bool
    bootstrap_complete: bool
    bootstrap_last_at: Optional[str] = None
    
    tenant_count: int
    exception_count: int
    playbook_count: int = 0
    tool_count: int = 0
    
    scenarios_available: list[str] = []
    scenarios_active: list[str] = []
    
    active_run: Optional[dict[str, Any]] = None


class DemoBootstrapResponse(BaseModel):
    """Demo bootstrap response."""
    
    success: bool
    message: Optional[str] = None
    tenants_created: int = 0
    tenants_existing: int = 0
    domain_packs_created: int = 0
    tenant_packs_created: int = 0
    playbooks_created: int = 0
    tools_created: int = 0
    exceptions_created: int = 0
    errors: list[str] = []


class DemoRunStartRequest(BaseModel):
    """Demo run start request."""
    
    mode: str = Field(..., description="Run mode: burst, scheduled, continuous")
    scenario_ids: list[str] = Field(default=[], description="Scenario IDs to run (empty=all)")
    tenant_keys: list[str] = Field(default=[], description="Target tenant keys (empty=all demo)")
    frequency_seconds: Optional[int] = Field(default=2, description="Generation frequency")
    duration_seconds: Optional[int] = Field(default=120, description="Scheduled run duration")
    burst_count: Optional[int] = Field(default=25, description="Burst mode count")
    intensity_multiplier: Optional[float] = Field(default=1.0, description="Intensity multiplier")


class DemoRunResponse(BaseModel):
    """Demo run response."""
    
    run_id: str
    status: str
    mode: str
    scenario_ids: list[str] = []
    tenant_keys: list[str] = []
    frequency_seconds: Optional[int] = None
    duration_seconds: Optional[int] = None
    burst_count: Optional[int] = None
    started_at: Optional[str] = None
    ends_at: Optional[str] = None
    generated_count: int = 0
    error: Optional[str] = None


class DemoResetRequest(BaseModel):
    """Demo reset request."""
    
    confirm: bool = Field(..., description="Must be true to confirm reset")
    tenant_keys: Optional[list[str]] = Field(default=None, description="Specific tenants to reset (None=all demo)")


class DemoResetResponse(BaseModel):
    """Demo reset response."""
    
    success: bool
    message: str
    tenants_reset: list[str] = []
    exceptions_deleted: int = 0


# =============================================================================
# Settings Endpoints
# =============================================================================


@router.get("/platform/settings/demo", response_model=DemoSettingsResponse)
async def get_demo_settings(
    session: AsyncSession = Depends(get_db_session),
) -> DemoSettingsResponse:
    """
    Get all demo-related platform settings.
    
    Returns current demo configuration including enabled state,
    scenario settings, and run parameters.
    """
    repo = PlatformSettingsRepository(session)
    
    # Get all demo settings
    enabled = await repo.get_value("demo.enabled", False)
    catalog_path = await repo.get_value("demo.catalog.path")
    catalog_version = await repo.get_value("demo.catalog.version")
    bootstrap_on_start = await repo.get_value("demo.bootstrap.onStart", True)
    
    scenarios_enabled = await repo.get_value("demo.scenarios.enabled", True)
    scenarios_mode = await repo.get_value("demo.scenarios.mode", "continuous")
    scenarios_active = await repo.get_value("demo.scenarios.active", [])
    scenarios_tenants = await repo.get_value("demo.scenarios.tenants", [])
    
    frequency_seconds = await repo.get_value("demo.scenarios.frequencySeconds", 120)
    duration_seconds = await repo.get_value("demo.scenarios.durationSeconds", 120)
    burst_count = await repo.get_value("demo.scenarios.burstCount", 25)
    intensity_multiplier = await repo.get_value("demo.scenarios.intensityMultiplier", 1.0)
    
    last_run_at = await repo.get_value("demo.scenarios.lastRunAt")
    bootstrap_last_at = await repo.get_value("demo.bootstrap.lastAt")
    
    return DemoSettingsResponse(
        enabled=enabled,
        catalog_path=catalog_path,
        catalog_version=catalog_version,
        bootstrap_on_start=bootstrap_on_start,
        scenarios_enabled=scenarios_enabled,
        scenarios_mode=scenarios_mode,
        scenarios_active=scenarios_active or [],
        scenarios_tenants=scenarios_tenants or [],
        frequency_seconds=frequency_seconds,
        duration_seconds=duration_seconds,
        burst_count=burst_count,
        intensity_multiplier=intensity_multiplier,
        last_run_at=last_run_at.isoformat() if last_run_at else None,
        bootstrap_last_at=bootstrap_last_at.isoformat() if bootstrap_last_at else None,
    )


@router.put("/platform/settings/demo", response_model=DemoSettingsResponse)
async def update_demo_settings(
    update: DemoSettingsUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> DemoSettingsResponse:
    """
    Update demo-related platform settings.
    
    Only provided fields will be updated. All changes are audited.
    """
    repo = PlatformSettingsRepository(session)
    
    # Map update fields to setting keys
    field_mapping = {
        "enabled": "demo.enabled",
        "scenarios_enabled": "demo.scenarios.enabled",
        "scenarios_mode": "demo.scenarios.mode",
        "scenarios_active": "demo.scenarios.active",
        "scenarios_tenants": "demo.scenarios.tenants",
        "frequency_seconds": "demo.scenarios.frequencySeconds",
        "duration_seconds": "demo.scenarios.durationSeconds",
        "burst_count": "demo.scenarios.burstCount",
        "intensity_multiplier": "demo.scenarios.intensityMultiplier",
    }
    
    # Update provided fields
    for field, key in field_mapping.items():
        value = getattr(update, field, None)
        if value is not None:
            await repo.set(
                key=key,
                value=value,
                updated_by="api",
                audit_reason="Settings update via API",
            )
    
    await session.commit()
    
    # Return updated settings
    return await get_demo_settings(session)


# =============================================================================
# Demo Management Endpoints
# =============================================================================


@router.get("/demo/status", response_model=DemoStatusResponse)
async def get_demo_status(
    session: AsyncSession = Depends(get_db_session),
) -> DemoStatusResponse:
    """
    Get current demo system status.
    
    Returns counts of demo entities, available scenarios,
    and active run information.
    """
    engine = DemoScenarioEngine(session)
    status_data = await engine.get_status()
    
    return DemoStatusResponse(
        enabled=status_data["enabled"],
        bootstrap_complete=status_data["bootstrap_complete"],
        bootstrap_last_at=status_data.get("bootstrap_last_at"),
        tenant_count=status_data["tenant_count"],
        exception_count=status_data["exception_count"],
        playbook_count=status_data.get("playbook_count", 0),
        tool_count=status_data.get("tool_count", 0),
        scenarios_available=status_data["scenarios_available"],
        scenarios_active=status_data["scenarios_active"],
        active_run=status_data["active_run"],
    )


@router.post("/demo/bootstrap", response_model=DemoBootstrapResponse)
async def run_demo_bootstrap(
    force: bool = False,
    session: AsyncSession = Depends(get_db_session),
) -> DemoBootstrapResponse:
    """
    Run demo data bootstrap.
    
    Creates demo tenants, domain packs, playbooks, tools, and seed exceptions.
    Operations are idempotent - existing data won't be duplicated.
    
    Args:
        force: Force bootstrap even if demo mode is disabled.
    """
    bootstrapper = DemoBootstrapperService(session)
    result = await bootstrapper.bootstrap(force=force)
    
    return DemoBootstrapResponse(
        success=result["success"],
        message=result.get("message"),
        tenants_created=result["tenants_created"],
        tenants_existing=result["tenants_existing"],
        domain_packs_created=result["domain_packs_created"],
        tenant_packs_created=result.get("tenant_packs_created", 0),
        playbooks_created=result["playbooks_created"],
        tools_created=result["tools_created"],
        exceptions_created=result["exceptions_created"],
        errors=result["errors"],
    )


@router.post("/demo/run/start", response_model=DemoRunResponse)
async def start_demo_run(
    request: DemoRunStartRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DemoRunResponse:
    """
    Start a demo scenario run.
    
    Supports three modes:
    - burst: Generate exceptions immediately
    - scheduled: Generate at intervals for a duration
    - continuous: Generate continuously until stopped
    
    Only one run can be active at a time.
    """
    engine = DemoScenarioEngine(session)
    
    try:
        if request.mode == "burst":
            result = await engine.start_burst_run(
                scenario_ids=request.scenario_ids,
                tenant_keys=request.tenant_keys,
                burst_count=request.burst_count or 25,
                created_by="api",
            )
        elif request.mode == "scheduled":
            result = await engine.start_scheduled_run(
                scenario_ids=request.scenario_ids,
                tenant_keys=request.tenant_keys,
                frequency_seconds=request.frequency_seconds or 2,
                duration_seconds=request.duration_seconds or 120,
                intensity_multiplier=request.intensity_multiplier or 1.0,
                created_by="api",
            )
        elif request.mode == "continuous":
            result = await engine.start_continuous_run(
                scenario_ids=request.scenario_ids,
                tenant_keys=request.tenant_keys,
                frequency_seconds=request.frequency_seconds or 120,
                intensity_multiplier=request.intensity_multiplier or 1.0,
                created_by="api",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid mode: {request.mode}. Must be burst, scheduled, or continuous.",
            )
        
        return DemoRunResponse(
            run_id=result["run_id"],
            status=result["status"],
            mode=result["mode"],
            scenario_ids=result.get("scenario_ids", []),
            tenant_keys=result.get("tenant_keys", []),
            frequency_seconds=result.get("frequency_seconds"),
            duration_seconds=result.get("duration_seconds"),
            burst_count=result.get("burst_count"),
            started_at=result.get("started_at"),
            ends_at=result.get("ends_at"),
            generated_count=result.get("generated_count", 0),
            error=result.get("error"),
        )
        
    except DemoRunConflictError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A demo run is already active: {e.active_run_id}. Stop it first.",
        )


@router.post("/demo/run/stop", response_model=Optional[DemoRunResponse])
async def stop_demo_run(
    session: AsyncSession = Depends(get_db_session),
) -> Optional[DemoRunResponse]:
    """
    Stop the currently active demo run.
    
    Returns the stopped run info or null if no active run.
    """
    engine = DemoScenarioEngine(session)
    result = await engine.stop_run()
    
    if not result:
        return None
    
    return DemoRunResponse(
        run_id=result["run_id"],
        status=result["status"],
        mode=result["mode"],
        scenario_ids=result.get("scenario_ids", []),
        tenant_keys=result.get("tenant_keys", []),
        frequency_seconds=result.get("frequency_seconds"),
        duration_seconds=result.get("duration_seconds"),
        burst_count=result.get("burst_count"),
        started_at=result.get("started_at"),
        ends_at=result.get("ends_at"),
        generated_count=result.get("generated_count", 0),
        error=result.get("error"),
    )


@router.post("/demo/reset", response_model=DemoResetResponse)
async def reset_demo_data(
    request: DemoResetRequest,
    session: AsyncSession = Depends(get_db_session),
) -> DemoResetResponse:
    """
    Reset demo data and re-bootstrap.
    
    WARNING: This deletes all demo-tagged data including exceptions,
    playbooks, tools, and optionally tenants.
    
    Requires confirmation (confirm=true).
    """
    if not request.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must set confirm=true to reset demo data",
        )
    
    # Stop any active run first
    engine = DemoScenarioEngine(session)
    await engine.stop_run()
    
    # Get demo tenants to reset
    from sqlalchemy import select
    from src.infrastructure.db.models import Tenant
    
    query = select(Tenant).where(Tenant.tags.contains(["demo"]))
    if request.tenant_keys:
        query = query.where(Tenant.tenant_id.in_(request.tenant_keys))
    
    result = await session.execute(query)
    demo_tenants = list(result.scalars().all())
    
    if not demo_tenants:
        return DemoResetResponse(
            success=True,
            message="No demo tenants found to reset",
            tenants_reset=[],
            exceptions_deleted=0,
        )
    
    # Reset each tenant's data
    from src.demo.seeder import DemoDataSeeder
    
    seeder = DemoDataSeeder(session)
    tenants_reset = []
    total_deleted = 0
    
    for tenant in demo_tenants:
        try:
            await seeder.reset_tenant_data(tenant.tenant_id)
            tenants_reset.append(tenant.tenant_id)
        except Exception as e:
            logger.error(f"Error resetting tenant {tenant.tenant_id}: {e}")
    
    # Re-bootstrap
    bootstrapper = DemoBootstrapperService(session)
    await bootstrapper.bootstrap(force=True)
    
    await session.commit()
    
    return DemoResetResponse(
        success=True,
        message=f"Reset {len(tenants_reset)} demo tenants and re-bootstrapped",
        tenants_reset=tenants_reset,
        exceptions_deleted=total_deleted,
    )


# =============================================================================
# Catalog Endpoint
# =============================================================================


@router.get("/demo/catalog")
async def get_demo_catalog(
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """
    Get the demo catalog configuration.
    
    Returns available tenants, scenarios, and their configurations.
    """
    try:
        from src.demo.catalog_loader import DemoCatalogLoader
        
        catalog = DemoCatalogLoader.load()
        
        return {
            "version": catalog.version,
            "tenants": [
                {
                    "tenant_key": t.tenant_key,
                    "display_name": t.display_name,
                    "industry": t.industry.value,
                    "tags": t.tags,
                }
                for t in catalog.demo_tenants
            ],
            "scenarios": [
                {
                    "scenario_id": s.scenario_id,
                    "name": s.name,
                    "description": s.description,
                    "industry": s.industry.value,
                    "tags": s.tags,
                }
                for s in catalog.scenarios
            ],
            "domain_packs": [
                {
                    "domain_name": p.domain_name,
                    "version": p.version,
                    "industry": p.industry.value,
                }
                for p in catalog.domain_packs
            ],
        }
        
    except Exception as e:
        logger.error(f"Error loading demo catalog: {e}")
        return {
            "version": "unknown",
            "tenants": [],
            "scenarios": [],
            "domain_packs": [],
            "error": str(e),
        }
