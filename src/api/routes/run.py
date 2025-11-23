"""
Pipeline Run API routes.
Handles full pipeline execution via orchestrator.
"""

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from src.domainpack.loader import DomainPackValidationError, load_domain_pack
from src.observability.metrics import MetricsCollector
from src.orchestrator.runner import run_pipeline
from src.orchestrator.store import get_exception_store
from src.tenantpack.loader import TenantPolicyValidationError, load_tenant_policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/run", tags=["run"])


class RunPipelineRequest(BaseModel):
    """Request model for pipeline execution."""

    domainPackPath: str = Field(..., description="Path to Domain Pack JSON file")
    tenantPolicyPath: str = Field(..., description="Path to Tenant Policy Pack JSON file")
    exceptions: list[dict[str, Any]] = Field(..., description="List of raw exception payloads")

    model_config = {
        "json_schema_extra": {
            "example": {
                "domainPackPath": "domainpacks/finance.sample.json",
                "tenantPolicyPath": "tenantpacks/tenant_finance.sample.json",
                "exceptions": [{"sourceSystem": "ERP", "rawPayload": {}}],
            }
        }
    }


class RunPipelineResponse(BaseModel):
    """Response model for pipeline execution."""

    tenantId: str = Field(..., description="Tenant identifier")
    runId: str = Field(..., description="Unique run identifier")
    results: list[dict[str, Any]] = Field(..., description="List of exception processing results")

    model_config = {
        "json_schema_extra": {
            "example": {
                "tenantId": "TENANT_FINANCE_001",
                "runId": "run_123",
                "results": [{"exceptionId": "exc_001", "status": "IN_PROGRESS"}],
            }
        }
    }


@router.post("", response_model=RunPipelineResponse)
async def execute_pipeline(
    request: RunPipelineRequest, http_request: Request = None
) -> RunPipelineResponse:
    """
    Execute the full agent pipeline for a batch of exceptions.
    
    Loads Domain Pack and Tenant Policy Pack, then runs the full pipeline:
    IntakeAgent → TriageAgent → PolicyAgent → ResolutionAgent → FeedbackAgent
    
    Returns:
    - Pipeline execution results with all stages and evidence
    """
    # Validate file paths exist
    domain_pack_path = Path(request.domainPackPath)
    if not domain_pack_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Domain Pack file not found: {request.domainPackPath}",
        )
    
    tenant_policy_path = Path(request.tenantPolicyPath)
    if not tenant_policy_path.exists():
        raise HTTPException(
            status_code=400,
            detail=f"Tenant Policy Pack file not found: {request.tenantPolicyPath}",
        )
    
    # Get authenticated tenant ID from request state
    authenticated_tenant_id = None
    if http_request and hasattr(http_request.state, "tenant_id"):
        authenticated_tenant_id = http_request.state.tenant_id
    
    # Validate exceptions list
    if not request.exceptions:
        raise HTTPException(status_code=400, detail="No exceptions provided")
    
    # Log pipeline execution start
    logger.info(
        f"Starting pipeline execution for {len(request.exceptions)} exception(s) "
        f"with domain pack: {request.domainPackPath}, "
        f"tenant policy: {request.tenantPolicyPath}"
    )
    
    # Load Domain Pack
    try:
        domain_pack = load_domain_pack(str(domain_pack_path))
        logger.info(f"Loaded domain pack: {domain_pack.domain_name}")
    except DomainPackValidationError as e:
        logger.error(f"Domain Pack validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Domain Pack validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to load Domain Pack: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load Domain Pack: {str(e)}")
    
    # Load Tenant Policy Pack
    try:
        tenant_policy = load_tenant_policy(str(tenant_policy_path))
        logger.info(f"Loaded tenant policy for tenant: {tenant_policy.tenant_id}")
    except TenantPolicyValidationError as e:
        logger.error(f"Tenant Policy validation failed: {e}")
        raise HTTPException(status_code=400, detail=f"Tenant Policy validation failed: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to load Tenant Policy Pack: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load Tenant Policy Pack: {str(e)}")
    
    # Validate tenant policy against domain pack
    from src.tenantpack.loader import validate_tenant_policy
    try:
        validate_tenant_policy(tenant_policy, domain_pack)
    except TenantPolicyValidationError as e:
        logger.error(f"Tenant Policy validation against domain pack failed: {e}")
        raise HTTPException(
            status_code=400,
            detail=f"Tenant Policy validation against domain pack failed: {str(e)}"
        )
    
    # Verify tenant ID matches authenticated tenant (if available)
    if authenticated_tenant_id:
        if tenant_policy.tenant_id != authenticated_tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"policy={tenant_policy.tenant_id} for pipeline execution"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match tenant policy tenant '{tenant_policy.tenant_id}'",
            )
        # Use authenticated tenant ID
        tenant_policy.tenant_id = authenticated_tenant_id
    
    # Validate domain pack matches tenant policy
    if domain_pack.domain_name != tenant_policy.domain_name:
        logger.warning(
            f"Domain pack name '{domain_pack.domain_name}' does not match "
            f"tenant policy domain name '{tenant_policy.domain_name}'"
        )
    
    # Ensure tenantId is set in all exceptions
    for exception in request.exceptions:
        if "tenantId" not in exception:
            exception["tenantId"] = tenant_policy.tenant_id
    
    # Get metrics collector (global instance)
    from src.api.routes.metrics import get_metrics_collector
    
    metrics_collector = get_metrics_collector()
    exception_store = get_exception_store()
    
    # Execute pipeline
    try:
        result = await run_pipeline(
            domain_pack=domain_pack,
            tenant_policy=tenant_policy,
            exceptions_batch=request.exceptions,
            metrics_collector=metrics_collector,
            exception_store=exception_store,
        )
        
        logger.info(
            f"Pipeline execution completed: runId={result['runId']}, "
            f"processed {len(result['results'])} exception(s)"
        )
        
        return RunPipelineResponse(**result)
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")

