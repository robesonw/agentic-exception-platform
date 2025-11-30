"""
Re-Run and What-If Simulation API for Phase 3.

Allows operators to:
- Re-run an exception with minor parameter changes
- Run "what-if" scenarios (e.g., different severity or policy settings)
- Run in simulation mode (no persistent side effects)

Matches specification from phase3-mvp-issues.md P3-14.
"""

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, Field

from src.models.domain_pack import DomainPack
from src.models.exception_record import Severity
from src.models.tenant_policy import TenantPolicyPack
from src.orchestrator.simulation import SimulationError, get_simulation_result, run_simulation
from src.orchestrator.store import get_exception_store
from src.services.simulation_compare import compare_runs

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ui", tags=["operator-ui"])


# Request/Response models
class RerunRequest(BaseModel):
    """Request model for rerun endpoint."""

    tenant_id: str = Field(..., description="Tenant identifier")
    overrides: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Optional overrides: severity, policies, playbook",
    )
    simulation: bool = Field(
        default=True, description="Whether to run in simulation mode (default: True)"
    )


class RerunResponse(BaseModel):
    """Response model for rerun endpoint."""

    simulation_id: str = Field(..., description="Simulation identifier")
    original_exception_id: str = Field(..., description="Original exception ID")
    simulated_exception: dict = Field(..., description="Simulated exception record")
    pipeline_result: dict = Field(..., description="Pipeline processing result")
    overrides_applied: dict = Field(..., description="Overrides that were applied")
    timestamp: str = Field(..., description="Simulation timestamp")
    comparison: Optional[dict] = Field(None, description="Comparison with original run (if available)")


class SimulationResponse(BaseModel):
    """Response model for simulation retrieval endpoint."""

    simulation_id: str = Field(..., description="Simulation identifier")
    original_exception_id: str = Field(..., description="Original exception ID")
    simulated_exception: dict = Field(..., description="Simulated exception record")
    pipeline_result: dict = Field(..., description="Pipeline processing result")
    overrides_applied: dict = Field(..., description="Overrides that were applied")
    timestamp: str = Field(..., description="Simulation timestamp")
    comparison: Optional[dict] = Field(None, description="Comparison with original run")


@router.post("/exceptions/{exception_id}/rerun", response_model=RerunResponse)
async def rerun_exception(
    exception_id: str = Path(..., description="Exception identifier"),
    request: RerunRequest = None,
    domain_pack: Optional[DomainPack] = None,
    tenant_policy: Optional[TenantPolicyPack] = None,
) -> RerunResponse:
    """
    Re-run an exception with optional overrides in simulation mode.
    
    This endpoint allows operators to:
    - Re-run an exception with minor parameter changes
    - Test "what-if" scenarios (e.g., different severity or policy settings)
    - Run in simulation mode (no persistent side effects)
    
    Args:
        exception_id: Exception identifier to re-run
        request: Rerun request with tenant_id, overrides, and simulation flag
        domain_pack: Optional DomainPack (should be loaded from tenant config)
        tenant_policy: Optional TenantPolicyPack (should be loaded from tenant config)
        
    Returns:
        RerunResponse with simulation result and comparison
        
    Raises:
        HTTPException: If exception not found or simulation fails
    """
    if request is None:
        raise HTTPException(status_code=400, detail="Request body is required")
    
    # Get original exception from store
    exception_store = get_exception_store()
    original_result = exception_store.get_exception(request.tenant_id, exception_id)
    if not original_result:
        raise HTTPException(status_code=404, detail=f"Exception {exception_id} not found")
    
    original_exception, original_pipeline_result = original_result
    
    # Load domain pack and tenant policy from storage if not provided
    if domain_pack is None or tenant_policy is None:
        try:
            from src.domainpack.storage import DomainPackStorage
            from src.tenantpack.loader import TenantPolicyRegistry
            
            # Get domain name from exception context
            domain_name = None
            if hasattr(original_exception, "normalized_context") and original_exception.normalized_context:
                domain_name = original_exception.normalized_context.get("domain")
            
            if not domain_name:
                # Try to infer from exception type or use a default
                domain_name = "default"  # MVP: use default domain
            
            # Load domain pack from storage
            domain_storage = DomainPackStorage()
            # Get latest version for tenant (None = latest version)
            domain_pack = domain_storage.get_pack(request.tenant_id, domain_name, version=None)
            if not domain_pack:
                raise HTTPException(
                    status_code=404,
                    detail=f"Domain pack not found for domain: {domain_name}",
                )
            
            # Load tenant policy from registry
            policy_registry = TenantPolicyRegistry()
            tenant_policy = policy_registry.get(request.tenant_id)
            if not tenant_policy:
                raise HTTPException(
                    status_code=404,
                    detail=f"Tenant policy not found for tenant: {request.tenant_id}",
                )
        except (ImportError, AttributeError) as e:
            # Fallback: try to load from files if storage not available
            logger.warning(f"Could not load from storage: {e}. Domain pack and tenant policy must be provided.")
            raise HTTPException(
                status_code=400,
                detail="Domain pack and tenant policy must be loaded from tenant configuration. "
                       "Please ensure domain pack storage and tenant policy registry are configured.",
            )
    
    # Parse severity override if provided
    overrides = request.overrides.copy() if request.overrides else {}
    if "severity" in overrides and isinstance(overrides["severity"], str):
        try:
            overrides["severity"] = Severity(overrides["severity"].upper())
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {overrides['severity']}")
    
    try:
        # Run simulation
        simulation_result = await run_simulation(
            exception_record=original_exception,
            domain_pack=domain_pack,
            tenant_policy=tenant_policy,
            overrides=overrides,
            tenant_id=request.tenant_id,
        )
        
        # Compare with original run
        comparison = None
        try:
            # Build original run structure for comparison
            original_run = {
                "exception": original_exception,
                "stages": original_pipeline_result.get("stages", {}),
            }
            
            simulated_run = {
                "exception": simulation_result["simulated_exception"],
                "stages": simulation_result["pipeline_result"].get("stages", {}),
            }
            
            comparison = compare_runs(original_run, simulated_run)
        except Exception as e:
            logger.warning(f"Failed to generate comparison: {e}")
            # Comparison is optional, so we continue
        
        return RerunResponse(
            simulation_id=simulation_result["simulation_id"],
            original_exception_id=simulation_result["original_exception_id"],
            simulated_exception=simulation_result["simulated_exception"],
            pipeline_result=simulation_result["pipeline_result"],
            overrides_applied=simulation_result["overrides_applied"],
            timestamp=simulation_result["timestamp"],
            comparison=comparison,
        )
        
    except SimulationError as e:
        logger.error(f"Simulation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error in rerun: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to run simulation: {e}")


@router.get("/simulations/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(
    simulation_id: str = Path(..., description="Simulation identifier"),
    tenant_id: str = Query(..., description="Tenant identifier"),
) -> SimulationResponse:
    """
    Get simulation result by simulation ID.
    
    Returns:
    - Simulation result including decisions, evidence
    - Comparison to original run (if original exception is available)
    
    Args:
        simulation_id: Simulation identifier
        tenant_id: Tenant identifier
        
    Returns:
        SimulationResponse with simulation result and comparison
        
    Raises:
        HTTPException: If simulation not found
    """
    # Retrieve simulation result
    simulation_result = get_simulation_result(tenant_id, simulation_id)
    if not simulation_result:
        raise HTTPException(status_code=404, detail=f"Simulation {simulation_id} not found")
    
    # Try to get original exception for comparison
    comparison = None
    try:
        exception_store = get_exception_store()
        original_exception_id = simulation_result.get("original_exception_id")
        if original_exception_id:
            original_result = exception_store.get_exception(tenant_id, original_exception_id)
            if original_result:
                original_exception, original_pipeline_result = original_result
                
                # Build comparison
                original_run = {
                    "exception": original_exception,
                    "stages": original_pipeline_result.get("stages", {}),
                }
                
                simulated_run = {
                    "exception": simulation_result["simulated_exception"],
                    "stages": simulation_result["pipeline_result"].get("stages", {}),
                }
                
                comparison = compare_runs(original_run, simulated_run)
    except Exception as e:
        logger.warning(f"Failed to generate comparison: {e}")
        # Comparison is optional
    
    return SimulationResponse(
        simulation_id=simulation_result["simulation_id"],
        original_exception_id=simulation_result["original_exception_id"],
        simulated_exception=simulation_result["simulated_exception"],
        pipeline_result=simulation_result["pipeline_result"],
        overrides_applied=simulation_result["overrides_applied"],
        timestamp=simulation_result["timestamp"],
        comparison=comparison,
    )

