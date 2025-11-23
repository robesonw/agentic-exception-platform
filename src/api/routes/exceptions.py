"""
Exception ingestion and status API routes.
Handles raw exception ingestion and normalization.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Path, Request
from pydantic import BaseModel, Field

from src.agents.intake import IntakeAgent, IntakeAgentError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


class ExceptionIngestionRequest(BaseModel):
    """Request model for exception ingestion."""

    exception: dict[str, Any] | None = Field(None, description="Single exception payload")
    exceptions: list[dict[str, Any]] | None = Field(None, description="Batch of exception payloads")

    model_config = {"json_schema_extra": {"example": {"exception": {"sourceSystem": "ERP", "rawPayload": {}}}}}


class ExceptionIngestionResponse(BaseModel):
    """Response model for exception ingestion."""

    exceptionIds: list[str] = Field(..., description="List of normalized exception IDs")
    count: int = Field(..., description="Number of exceptions ingested")

    model_config = {"json_schema_extra": {"example": {"exceptionIds": ["exc_001"], "count": 1}}}


@router.post("/{tenant_id}", response_model=ExceptionIngestionResponse)
async def ingest_exception(
    tenant_id: str = Path(..., description="Tenant identifier"),
    request: ExceptionIngestionRequest | None = None,
    http_request: Request = None,
) -> ExceptionIngestionResponse:
    """
    Ingest raw exception payload(s) and normalize via IntakeAgent.
    
    Accepts either:
    - Single exception: {"exception": {...}}
    - Batch: {"exceptions": [{...}, {...}]}
    
    Returns:
    - List of normalized exception IDs
    - Count of ingested exceptions
    """
    # Verify tenant ID matches authenticated tenant
    if http_request and hasattr(http_request.state, "tenant_id"):
        authenticated_tenant_id = http_request.state.tenant_id
        if authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"path={tenant_id} for {http_request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match path tenant '{tenant_id}'",
            )
        # Use authenticated tenant ID
        tenant_id = authenticated_tenant_id
    
    # Handle request body (can be None if sent as raw JSON)
    if request is None:
        raise HTTPException(status_code=400, detail="Request body is required")
    
    # Determine if single or batch
    raw_exceptions: list[dict[str, Any]] = []
    
    if request.exception:
        raw_exceptions.append(request.exception)
    elif request.exceptions:
        raw_exceptions = request.exceptions
    else:
        raise HTTPException(status_code=400, detail="Either 'exception' or 'exceptions' field is required")
    
    if not raw_exceptions:
        raise HTTPException(status_code=400, detail="No exceptions provided")
    
    # Log ingestion event
    logger.info(f"Ingesting {len(raw_exceptions)} exception(s) for tenant {tenant_id}")
    
    # Get domain pack for tenant (for validation)
    # Note: In MVP, we'll try to get from registry, but allow None for flexibility
    domain_pack = None
    try:
        from src.domainpack.loader import DomainPackRegistry
        
        registry = DomainPackRegistry()
        domain_pack = registry.get_latest(tenant_id)
    except Exception:
        # If no domain pack available, IntakeAgent will handle gracefully
        logger.warning(f"No domain pack found for tenant {tenant_id}, proceeding without validation")
    
    # Initialize IntakeAgent
    intake_agent = IntakeAgent(domain_pack=domain_pack)
    
    # Normalize each exception
    exception_ids = []
    errors = []
    
    for raw_exception in raw_exceptions:
        try:
            # Ensure tenantId is set in raw exception
            if "tenantId" not in raw_exception:
                raw_exception["tenantId"] = tenant_id
            
            # Normalize via IntakeAgent
            normalized, decision = await intake_agent.process(
                raw_exception=raw_exception,
                tenant_id=tenant_id,
            )
            
            exception_ids.append(normalized.exception_id)
            logger.info(
                f"Normalized exception {normalized.exception_id} for tenant {tenant_id}: "
                f"{decision.decision}"
            )
        except IntakeAgentError as e:
            error_msg = f"Failed to normalize exception: {str(e)}"
            logger.error(f"{error_msg} for tenant {tenant_id}")
            errors.append(error_msg)
        except Exception as e:
            error_msg = f"Unexpected error normalizing exception: {str(e)}"
            logger.error(f"{error_msg} for tenant {tenant_id}")
            errors.append(error_msg)
    
    if not exception_ids and errors:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to normalize any exceptions: {', '.join(errors)}",
        )
    
    # Log completion
    logger.info(f"Ingested {len(exception_ids)} exception(s) for tenant {tenant_id}")
    
    return ExceptionIngestionResponse(exceptionIds=exception_ids, count=len(exception_ids))


@router.get("/{tenant_id}/{exception_id}")
async def get_exception_status(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    request: Request = None,
) -> dict[str, Any]:
    """
    Get exception status and full schema.
    
    GET /exceptions/{tenantId}/{exceptionId}
    
    Returns:
    - Full exception schema with current resolutionStatus
    - Audit trail from pipeline processing
    - Pipeline result stages
    
    Raises:
    - HTTPException 404 if exception not found
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if tenant isolation violation (exception belongs to different tenant)
    """
    # Verify tenant ID matches authenticated tenant
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"path={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match path tenant '{tenant_id}'",
            )
        # Use authenticated tenant ID
        tenant_id = authenticated_tenant_id
    
    logger.info(f"Retrieving exception {exception_id} for tenant {tenant_id}")
    
    # Get exception store
    from src.orchestrator.store import get_exception_store
    
    exception_store = get_exception_store()
    
    # Retrieve exception
    stored = exception_store.get_exception(tenant_id, exception_id)
    
    if stored is None:
        logger.warning(f"Exception {exception_id} not found for tenant {tenant_id}")
        raise HTTPException(
            status_code=404,
            detail=f"Exception {exception_id} not found for tenant {tenant_id}",
        )
    
    exception, pipeline_result = stored
    
    # Verify tenant isolation (double-check)
    if exception.tenant_id != tenant_id:
        logger.error(
            f"Tenant isolation violation: Exception {exception_id} belongs to "
            f"tenant {exception.tenant_id}, not {tenant_id}"
        )
        raise HTTPException(
            status_code=404,
            detail=f"Exception {exception_id} not found for tenant {tenant_id}",
        )
    
    # Build response with canonical exception schema + audit trail
    response = exception.model_dump(by_alias=True)
    
    # Add pipeline result information
    response["pipelineResult"] = {
        "status": pipeline_result.get("status", "UNKNOWN"),
        "stages": pipeline_result.get("stages", {}),
        "evidence": pipeline_result.get("evidence", []),
    }
    
    if "errors" in pipeline_result:
        response["pipelineResult"]["errors"] = pipeline_result["errors"]
    
    logger.info(
        f"Retrieved exception {exception_id} for tenant {tenant_id} "
        f"(status: {exception.resolution_status.value})"
    )
    
    return response

