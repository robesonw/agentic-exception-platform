"""
Exception ingestion and status API routes.
Handles raw exception ingestion and normalization.

Phase 6 P6-22: Updated to use DB-backed repositories for all operations.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from src.agents.intake import IntakeAgent, IntakeAgentError
from src.infrastructure.db.models import ActorType, ExceptionSeverity, ExceptionStatus
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.repository.dto import EventFilter, ExceptionFilter, ExceptionUpdateDTO

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


class ExceptionListResponse(BaseModel):
    """Response model for listing exceptions."""

    items: list[dict[str, Any]] = Field(..., description="List of exception records")
    total: int = Field(..., description="Total number of exceptions matching filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class ExceptionUpdateRequest(BaseModel):
    """Request model for updating an exception."""

    domain: Optional[str] = Field(None, description="Domain name")
    type: Optional[str] = Field(None, description="Exception type")
    severity: Optional[str] = Field(None, description="Exception severity (low, medium, high, critical)")
    status: Optional[str] = Field(None, description="Exception status (open, analyzing, resolved, escalated)")
    source_system: Optional[str] = Field(None, description="Source system name")
    entity: Optional[str] = Field(None, description="Entity identifier")
    amount: Optional[float] = Field(None, description="Amount associated with exception")
    sla_deadline: Optional[datetime] = Field(None, description="SLA deadline timestamp")
    owner: Optional[str] = Field(None, description="Owner (user or agent identifier)")
    current_playbook_id: Optional[int] = Field(None, description="Current playbook identifier")
    current_step: Optional[int] = Field(None, description="Current step number in playbook")


class ExceptionEventListResponse(BaseModel):
    """Response model for listing exception events."""

    items: list[dict[str, Any]] = Field(..., description="List of event records")
    total: int = Field(..., description="Total number of events matching filters")
    page: int = Field(..., description="Current page number (1-indexed)")
    page_size: int = Field(..., description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")


class PlaybookRecalculationResponse(BaseModel):
    """Response model for playbook recalculation."""

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    current_playbook_id: Optional[int] = Field(None, alias="currentPlaybookId", description="Current playbook identifier")
    current_step: Optional[int] = Field(None, alias="currentStep", description="Current step number in playbook")
    playbook_name: Optional[str] = Field(None, alias="playbookName", description="Name of the selected playbook")
    playbook_version: Optional[int] = Field(None, alias="playbookVersion", description="Version of the selected playbook")
    reasoning: Optional[str] = Field(None, description="Reasoning for playbook selection")

    model_config = {"json_schema_extra": {"example": {"exceptionId": "exc_001", "currentPlaybookId": 1, "currentStep": 1, "playbookName": "PaymentFailurePlaybook", "playbookVersion": 1}}}


class PlaybookStepStatus(BaseModel):
    """Status information for a playbook step."""

    step_order: int = Field(..., alias="stepOrder", description="Step order number (1-indexed)")
    name: str = Field(..., description="Step name")
    action_type: str = Field(..., alias="actionType", description="Action type (e.g., notify, call_tool)")
    status: str = Field(..., description="Step status: pending, completed, or skipped")


class PlaybookStatusResponse(BaseModel):
    """Response model for playbook status."""

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    playbook_id: Optional[int] = Field(None, alias="playbookId", description="Playbook identifier")
    playbook_name: Optional[str] = Field(None, alias="playbookName", description="Playbook name")
    playbook_version: Optional[int] = Field(None, alias="playbookVersion", description="Playbook version")
    conditions: Optional[dict[str, Any]] = Field(None, description="Playbook matching conditions")
    steps: list[PlaybookStepStatus] = Field(default_factory=list, description="List of playbook steps with status")
    current_step: Optional[int] = Field(None, alias="currentStep", description="Current step number (1-indexed)")

    model_config = {"json_schema_extra": {"example": {"exceptionId": "exc_001", "playbookId": 1, "playbookName": "PaymentFailurePlaybook", "playbookVersion": 1, "steps": [{"stepOrder": 1, "name": "Notify Team", "actionType": "notify", "status": "completed"}], "currentStep": 2}}}


class StepCompletionRequest(BaseModel):
    """Request model for completing a playbook step."""

    actor_type: str = Field(..., alias="actorType", description="Actor type: human, agent, or system")
    actor_id: str = Field(..., alias="actorId", description="Actor identifier (user ID or agent name)")
    notes: Optional[str] = Field(None, description="Optional notes about step completion")

    model_config = {"json_schema_extra": {"example": {"actorType": "human", "actorId": "user_123", "notes": "Step completed successfully"}}}


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
            
            # Phase 6: Persist to PostgreSQL
            try:
                from src.infrastructure.db.session import get_db_session_context
                from src.repository.dto import ExceptionCreateOrUpdateDTO
                from src.repository.exception_events_repository import ExceptionEventRepository
                from src.repository.exceptions_repository import ExceptionRepository
                from src.infrastructure.db.models import ExceptionSeverity, ExceptionStatus, ActorType, Tenant, TenantStatus
                from sqlalchemy import select
                from uuid import uuid4
                
                async with get_db_session_context() as session:
                    # Ensure tenant exists in database
                    result = await session.execute(
                        select(Tenant).where(Tenant.tenant_id == tenant_id)
                    )
                    existing_tenant = result.scalar_one_or_none()
                    
                    if existing_tenant is None:
                        # Create tenant if it doesn't exist
                        # Use raw SQL to avoid enum conversion issues
                        from sqlalchemy import text
                        await session.execute(
                            text(
                                "INSERT INTO tenant (tenant_id, name, status) "
                                "VALUES (:tenant_id, :name, :status) "
                                "ON CONFLICT (tenant_id) DO NOTHING"
                            ),
                            {
                                "tenant_id": tenant_id,
                                "name": f"Tenant {tenant_id}",
                                "status": "active",  # Use lowercase string directly
                            },
                        )
                        await session.flush()
                        logger.info(f"Created tenant {tenant_id} in PostgreSQL")
                    
                    # Map ExceptionRecord to database Exception model
                    # Extract domain from normalized_context
                    domain = normalized.normalized_context.get("domain", "Generic")
                    
                    # Map severity (ExceptionRecord uses uppercase, DB uses lowercase)
                    severity_map = {
                        "LOW": ExceptionSeverity.LOW,
                        "MEDIUM": ExceptionSeverity.MEDIUM,
                        "HIGH": ExceptionSeverity.HIGH,
                        "CRITICAL": ExceptionSeverity.CRITICAL,
                    }
                    db_severity = severity_map.get(
                        normalized.severity.value if normalized.severity else "MEDIUM",
                        ExceptionSeverity.MEDIUM
                    )
                    
                    # Map resolution status to exception status
                    status_map = {
                        "OPEN": ExceptionStatus.OPEN,
                        "IN_PROGRESS": ExceptionStatus.ANALYZING,
                        "RESOLVED": ExceptionStatus.RESOLVED,
                        "ESCALATED": ExceptionStatus.ESCALATED,
                        "PENDING_APPROVAL": ExceptionStatus.ANALYZING,
                    }
                    db_status = status_map.get(
                        normalized.resolution_status.value,
                        ExceptionStatus.OPEN
                    )
                    
                    # Create exception DTO for upsert (idempotent)
                    upsert_data = ExceptionCreateOrUpdateDTO(
                        exception_id=normalized.exception_id,
                        tenant_id=normalized.tenant_id,
                        domain=domain,
                        type=normalized.exception_type or "Unknown",
                        severity=db_severity,
                        status=db_status,
                        source_system=normalized.source_system,
                        entity=normalized.normalized_context.get("entity"),
                        amount=normalized.normalized_context.get("amount"),
                        sla_deadline=normalized.normalized_context.get("sla_deadline"),
                    )
                    
                    # Save to database using upsert (idempotent)
                    repo = ExceptionRepository(session)
                    await repo.upsert_exception(tenant_id, upsert_data)
                    await session.flush()  # Flush to ensure exception exists before creating event
                    logger.debug(f"Saved/upserted exception {normalized.exception_id} to PostgreSQL")
                    
                    # Log creation event
                    event_repo = ExceptionEventRepository(session)
                    from src.repository.dto import ExceptionEventCreateDTO
                    
                    event_data = ExceptionEventCreateDTO(
                        event_id=uuid4(),
                        exception_id=normalized.exception_id,
                        tenant_id=tenant_id,
                        event_type="ExceptionCreated",
                        actor_type=ActorType.SYSTEM,
                        payload={
                            "source": "api_ingestion",
                            "normalized_context": normalized.normalized_context,
                            "decision": decision.decision,
                        },
                    )
                    
                    # Use idempotent append
                    await event_repo.append_event_if_new(event_data)
                    await session.flush()
                    logger.debug(f"Logged event for exception {normalized.exception_id}")
                    # Note: session.commit() is called automatically by get_db_session_context
                    
            except Exception as db_error:
                # Log but don't fail the ingestion if DB save fails
                import traceback
                error_trace = traceback.format_exc()
                logger.error(
                    f"Failed to persist exception {normalized.exception_id} to PostgreSQL: {db_error}\n"
                    f"Traceback: {error_trace}"
                )
                # Re-raise in development to see the error, but catch in production
                # For now, log the error but continue
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


# IMPORTANT: More specific routes must come BEFORE less specific ones
# FastAPI matches routes in order, so /{exception_id}/events must come before /{tenant_id}
@router.get("/{exception_id}/events", response_model=ExceptionEventListResponse)
async def get_exception_events(
    exception_id: str = Path(..., description="Exception identifier"),
    tenant_id: str = Query(..., description="Tenant identifier (required for isolation)"),
    event_type: Optional[str] = Query(None, description="Filter by event type (comma-separated list)"),
    actor_type: Optional[str] = Query(None, description="Filter by actor type (agent, user, system)"),
    date_from: Optional[datetime] = Query(None, description="Filter by created_at >= date_from"),
    date_to: Optional[datetime] = Query(None, description="Filter by created_at <= date_to"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
    request: Request = None,
) -> ExceptionEventListResponse:
    """
    Get event timeline for a specific exception.
    
    GET /exceptions/{exception_id}/events
    
    Query Parameters:
    - tenant_id: Tenant identifier (required for isolation)
    - event_type: Optional event type filter (comma-separated list, e.g., "ExceptionCreated,TriageCompleted")
    - actor_type: Optional actor type filter (agent, user, system)
    - date_from: Optional start date filter
    - date_to: Optional end date filter
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 100)
    
    Returns:
    - Paginated list of events in chronological order (oldest first)
    - Total count and pagination metadata
    
    Raises:
    - HTTPException 400 if tenant_id is missing or invalid
    - HTTPException 404 if exception not found or doesn't belong to tenant
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"query={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match query tenant '{tenant_id}'",
            )
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Retrieving events for exception {exception_id}, tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exception_events_repository import ExceptionEventRepository
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
            # First, verify that the exception exists and belongs to the tenant
            exception_repo = ExceptionRepository(session)
            db_exception = await exception_repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                logger.warning(
                    f"Exception {exception_id} not found for tenant {tenant_id} "
                    "or doesn't belong to tenant"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Build event filter from query parameters
            event_filters = EventFilter()
            
            if event_type:
                # Parse comma-separated event types
                event_types_list = [et.strip() for et in event_type.split(",") if et.strip()]
                if event_types_list:
                    event_filters.event_types = event_types_list
            
            if actor_type:
                # Map string actor_type to ActorType enum
                actor_type_map = {
                    "agent": ActorType.AGENT,
                    "user": ActorType.USER,
                    "system": ActorType.SYSTEM,
                }
                db_actor_type = actor_type_map.get(actor_type.lower())
                if db_actor_type is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid actor_type value: {actor_type}. Must be one of: agent, user, system",
                    )
                event_filters.actor_type = db_actor_type
            
            if date_from:
                event_filters.date_from = date_from
            if date_to:
                event_filters.date_to = date_to
            
            # Get events from repository (returns list, not paginated result)
            event_repo = ExceptionEventRepository(session)
            all_events = await event_repo.get_events_for_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                filters=event_filters,
            )
            
            # Apply pagination manually
            total = len(all_events)
            total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_events = all_events[start_idx:end_idx]
            
            # Transform to response format
            events = []
            for event in paginated_events:
                events.append({
                    "eventId": str(event.event_id),
                    "exceptionId": event.exception_id,
                    "tenantId": event.tenant_id,
                    "eventType": event.event_type,
                    "actorType": event.actor_type.value if hasattr(event.actor_type, "value") else str(event.actor_type),
                    "actorId": event.actor_id,
                    "payload": event.payload if isinstance(event.payload, dict) else {},
                    "createdAt": event.created_at.isoformat() if hasattr(event.created_at, "isoformat") else str(event.created_at),
                })
            
            return ExceptionEventListResponse(
                items=events,
                total=total,
                page=page,
                page_size=page_size,
                total_pages=total_pages,
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving events from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to retrieve events: {str(e)}",
        )


@router.get("/{tenant_id}", response_model=ExceptionListResponse)
async def list_exceptions(
    tenant_id: str = Path(..., description="Tenant identifier"),
    domain: Optional[str] = Query(None, description="Filter by domain name"),
    status: Optional[str] = Query(None, description="Filter by status (open, analyzing, resolved, escalated)"),
    severity: Optional[str] = Query(None, description="Filter by severity (low, medium, high, critical)"),
    created_from: Optional[datetime] = Query(None, description="Filter by created_at >= created_from"),
    created_to: Optional[datetime] = Query(None, description="Filter by created_at <= created_to"),
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Number of items per page (max 100)"),
    request: Request = None,
) -> ExceptionListResponse:
    """
    List exceptions for a tenant with filtering and pagination.
    
    GET /exceptions/{tenant_id}
    
    Query Parameters:
    - domain: Optional domain filter
    - status: Optional status filter (open, analyzing, resolved, escalated)
    - severity: Optional severity filter (low, medium, high, critical)
    - created_from: Optional start date filter
    - created_to: Optional end date filter
    - page: Page number (default: 1)
    - page_size: Items per page (default: 50, max: 100)
    
    Returns:
    - Paginated list of exceptions
    - Total count and pagination metadata
    
    Raises:
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 500 if database error occurs
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
        tenant_id = authenticated_tenant_id
    
    logger.info(f"Listing exceptions for tenant {tenant_id} (page={page}, page_size={page_size})")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            
            # Build filter from query parameters
            filters = ExceptionFilter()
            if domain:
                filters.domain = domain
            if status:
                # Map string status to ExceptionStatus enum
                status_map = {
                    "open": ExceptionStatus.OPEN,
                    "analyzing": ExceptionStatus.ANALYZING,
                    "resolved": ExceptionStatus.RESOLVED,
                    "escalated": ExceptionStatus.ESCALATED,
                }
                db_status = status_map.get(status.lower())
                if db_status is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid status value: {status}. Must be one of: open, analyzing, resolved, escalated",
                    )
                filters.status = db_status
            if severity:
                # Map string severity to ExceptionSeverity enum
                severity_map = {
                    "low": ExceptionSeverity.LOW,
                    "medium": ExceptionSeverity.MEDIUM,
                    "high": ExceptionSeverity.HIGH,
                    "critical": ExceptionSeverity.CRITICAL,
                }
                db_severity = severity_map.get(severity.lower())
                if db_severity is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid severity value: {severity}. Must be one of: low, medium, high, critical",
                    )
                filters.severity = db_severity
            if created_from:
                filters.created_from = created_from
            if created_to:
                filters.created_to = created_to
            
            # List exceptions with pagination
            result = await repo.list_exceptions(
                tenant_id=tenant_id,
                filters=filters,
                page=page,
                page_size=page_size,
            )
            
            # Convert database exceptions to API format
            items = []
            for db_exc in result.items:
                # Map to ExceptionRecord format
                severity_map = {
                    "low": Severity.LOW,
                    "medium": Severity.MEDIUM,
                    "high": Severity.HIGH,
                    "critical": Severity.CRITICAL,
                }
                severity_enum = severity_map.get(
                    db_exc.severity.value if hasattr(db_exc.severity, 'value') else str(db_exc.severity).lower(),
                    Severity.MEDIUM
                )
                
                status_map = {
                    "open": ResolutionStatus.OPEN,
                    "analyzing": ResolutionStatus.IN_PROGRESS,
                    "resolved": ResolutionStatus.RESOLVED,
                    "escalated": ResolutionStatus.ESCALATED,
                }
                resolution_status = status_map.get(
                    db_exc.status.value if hasattr(db_exc.status, 'value') else str(db_exc.status).lower(),
                    ResolutionStatus.OPEN
                )
                
                # Build normalized context
                normalized_context = {"domain": db_exc.domain}
                if db_exc.entity:
                    normalized_context["entity"] = db_exc.entity
                if db_exc.amount is not None:
                    normalized_context["amount"] = float(db_exc.amount)
                if db_exc.sla_deadline:
                    normalized_context["sla_deadline"] = db_exc.sla_deadline.isoformat()
                
                # Create ExceptionRecord
                exception = ExceptionRecord(
                    exception_id=db_exc.exception_id,
                    tenant_id=db_exc.tenant_id,
                    source_system=db_exc.source_system,
                    exception_type=db_exc.type,
                    severity=severity_enum,
                    timestamp=db_exc.created_at or datetime.now(),
                    raw_payload={},
                    normalized_context=normalized_context,
                    resolution_status=resolution_status,
                    audit_trail=[],
                )
                
                items.append(exception.model_dump(by_alias=True))
            
            logger.info(
                f"Listed {len(items)} exceptions for tenant {tenant_id} "
                f"(total: {result.total}, page: {page}/{result.total_pages})"
            )
            
            return ExceptionListResponse(
                items=items,
                total=result.total,
                page=result.page,
                page_size=result.page_size,
                total_pages=result.total_pages,
            )
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid request parameters: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing exceptions from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to list exceptions: {str(e)}",
        )


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
    
    # Phase 6: Read from PostgreSQL
    try:
        from src.infrastructure.db.session import get_db_session
        from src.repository.exceptions_repository import ExceptionRepository
        from src.repository.exception_events_repository import ExceptionEventRepository
        from src.models.exception_record import ExceptionRecord, Severity, ResolutionStatus
        from datetime import datetime, timezone
        
        # Get database session
        from src.infrastructure.db.session import get_db_session_context
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            
            # Retrieve exception from PostgreSQL
            db_exception = await repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                logger.warning(f"Exception {exception_id} not found for tenant {tenant_id} in PostgreSQL")
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Map database Exception to ExceptionRecord
            # Map severity (DB uses lowercase, ExceptionRecord uses uppercase)
            severity_map = {
                "low": Severity.LOW,
                "medium": Severity.MEDIUM,
                "high": Severity.HIGH,
                "critical": Severity.CRITICAL,
            }
            severity = severity_map.get(
                db_exception.severity.value if hasattr(db_exception.severity, 'value') else str(db_exception.severity).lower(),
                Severity.MEDIUM
            )
            
            # Map status (DB uses lowercase, ExceptionRecord uses uppercase)
            status_map = {
                "open": ResolutionStatus.OPEN,
                "analyzing": ResolutionStatus.IN_PROGRESS,
                "resolved": ResolutionStatus.RESOLVED,
                "escalated": ResolutionStatus.ESCALATED,
            }
            resolution_status = status_map.get(
                db_exception.status.value if hasattr(db_exception.status, 'value') else str(db_exception.status).lower(),
                ResolutionStatus.OPEN
            )
            
            # Build normalized context from database fields
            normalized_context = {
                "domain": db_exception.domain,
            }
            if db_exception.entity:
                normalized_context["entity"] = db_exception.entity
            if db_exception.amount:
                normalized_context["amount"] = float(db_exception.amount)
            if db_exception.sla_deadline:
                normalized_context["sla_deadline"] = db_exception.sla_deadline
            
            # Create ExceptionRecord from database model
            exception = ExceptionRecord(
                exception_id=db_exception.exception_id,
                tenant_id=db_exception.tenant_id,
                source_system=db_exception.source_system,
                exception_type=db_exception.type,
                severity=severity,
                timestamp=db_exception.created_at or datetime.now(timezone.utc),
                raw_payload={},  # Not stored in DB, would need separate table for full payload
                normalized_context=normalized_context,
                resolution_status=resolution_status,
                audit_trail=[],  # Will be populated from events
            )
            
            # Get events for audit trail
            event_repo = ExceptionEventRepository(session)
            events = await event_repo.get_events_for_exception(tenant_id, exception_id)
            
            # Build audit trail from events
            audit_trail = []
            for event in events:
                from src.models.exception_record import AuditEntry
                actor_type = event.actor_type.value if hasattr(event.actor_type, 'value') else str(event.actor_type)
                audit_trail.append(
                    AuditEntry(
                        action=event.event_type,
                        timestamp=event.created_at,
                        actor=f"{actor_type}:{event.actor_id or 'system'}",
                    )
                )
            exception.audit_trail = audit_trail
            
            # Build pipeline result from events
            pipeline_result = {
                "status": "COMPLETED" if resolution_status == ResolutionStatus.RESOLVED else "IN_PROGRESS",
                "stages": {},
                "evidence": [],
            }
            
            # Extract stage information from events
            for event in events:
                if event.event_type.endswith("Completed"):
                    stage_name = event.event_type.replace("Completed", "").lower()
                    pipeline_result["stages"][stage_name] = {
                        "status": "completed",
                        "timestamp": event.created_at.isoformat(),
                    }
            
            # Build response with canonical exception schema + audit trail
            response = exception.model_dump(by_alias=True)
            
            # Add pipeline result information
            response["pipelineResult"] = pipeline_result
            
            logger.info(
                f"Retrieved exception {exception_id} for tenant {tenant_id} "
                f"(status: {exception.resolution_status.value})"
            )
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving exception from PostgreSQL: {e}", exc_info=True)
        # Fallback to in-memory store for backward compatibility
        from src.orchestrator.store import get_exception_store
        exception_store = get_exception_store()
        stored = exception_store.get_exception(tenant_id, exception_id)
        
        if stored is None:
            raise HTTPException(
                status_code=404,
                detail=f"Exception {exception_id} not found for tenant {tenant_id}",
            )
        
        exception, pipeline_result = stored
        response = exception.model_dump(by_alias=True)
        response["pipelineResult"] = {
            "status": pipeline_result.get("status", "UNKNOWN"),
            "stages": pipeline_result.get("stages", {}),
            "evidence": pipeline_result.get("evidence", []),
        }
        if "errors" in pipeline_result:
            response["pipelineResult"]["errors"] = pipeline_result["errors"]
        return response


@router.put("/{tenant_id}/{exception_id}")
async def update_exception(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    update_request: ExceptionUpdateRequest = None,
    request: Request = None,
) -> dict[str, Any]:
    """
    Update an existing exception.
    
    PUT /exceptions/{tenant_id}/{exception_id}
    
    Request Body:
    - All fields are optional - only provided fields will be updated
    
    Returns:
    - Updated exception record
    
    Raises:
    - HTTPException 404 if exception not found
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 400 if invalid update data
    - HTTPException 500 if database error occurs
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
        tenant_id = authenticated_tenant_id
    
    if update_request is None:
        raise HTTPException(status_code=400, detail="Request body is required")
    
    logger.info(f"Updating exception {exception_id} for tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
            repo = ExceptionRepository(session)
            
            # Build update DTO from request
            update_dto = ExceptionUpdateDTO()
            if update_request.domain is not None:
                update_dto.domain = update_request.domain
            if update_request.type is not None:
                update_dto.type = update_request.type
            if update_request.severity is not None:
                # Map string severity to ExceptionSeverity enum
                severity_map = {
                    "low": ExceptionSeverity.LOW,
                    "medium": ExceptionSeverity.MEDIUM,
                    "high": ExceptionSeverity.HIGH,
                    "critical": ExceptionSeverity.CRITICAL,
                }
                db_severity = severity_map.get(update_request.severity.lower())
                if db_severity is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid severity value: {update_request.severity}. Must be one of: low, medium, high, critical",
                    )
                update_dto.severity = db_severity
            if update_request.status is not None:
                # Map string status to ExceptionStatus enum
                status_map = {
                    "open": ExceptionStatus.OPEN,
                    "analyzing": ExceptionStatus.ANALYZING,
                    "resolved": ExceptionStatus.RESOLVED,
                    "escalated": ExceptionStatus.ESCALATED,
                }
                db_status = status_map.get(update_request.status.lower())
                if db_status is None:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Invalid status value: {update_request.status}. Must be one of: open, analyzing, resolved, escalated",
                    )
                update_dto.status = db_status
            if update_request.source_system is not None:
                update_dto.source_system = update_request.source_system
            if update_request.entity is not None:
                update_dto.entity = update_request.entity
            if update_request.amount is not None:
                update_dto.amount = update_request.amount
            if update_request.sla_deadline is not None:
                update_dto.sla_deadline = update_request.sla_deadline
            if update_request.owner is not None:
                update_dto.owner = update_request.owner
            if update_request.current_playbook_id is not None:
                update_dto.current_playbook_id = update_request.current_playbook_id
            if update_request.current_step is not None:
                update_dto.current_step = update_request.current_step
            
            # Update exception
            updated = await repo.update_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                updates=update_dto,
            )
            
            if updated is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Map to ExceptionRecord format for response
            severity_map = {
                "low": Severity.LOW,
                "medium": Severity.MEDIUM,
                "high": Severity.HIGH,
                "critical": Severity.CRITICAL,
            }
            severity_enum = severity_map.get(
                updated.severity.value if hasattr(updated.severity, 'value') else str(updated.severity).lower(),
                Severity.MEDIUM
            )
            
            status_map = {
                "open": ResolutionStatus.OPEN,
                "analyzing": ResolutionStatus.IN_PROGRESS,
                "resolved": ResolutionStatus.RESOLVED,
                "escalated": ResolutionStatus.ESCALATED,
            }
            resolution_status = status_map.get(
                updated.status.value if hasattr(updated.status, 'value') else str(updated.status).lower(),
                ResolutionStatus.OPEN
            )
            
            # Build normalized context
            normalized_context = {"domain": updated.domain}
            if updated.entity:
                normalized_context["entity"] = updated.entity
            if updated.amount is not None:
                normalized_context["amount"] = float(updated.amount)
            if updated.sla_deadline:
                normalized_context["sla_deadline"] = updated.sla_deadline.isoformat()
            
            # Create ExceptionRecord
            exception = ExceptionRecord(
                exception_id=updated.exception_id,
                tenant_id=updated.tenant_id,
                source_system=updated.source_system,
                exception_type=updated.type,
                severity=severity_enum,
                timestamp=updated.created_at or datetime.now(),
                raw_payload={},
                normalized_context=normalized_context,
                resolution_status=resolution_status,
                audit_trail=[],
            )
            
            logger.info(f"Updated exception {exception_id} for tenant {tenant_id}")
            
            return exception.model_dump(by_alias=True)
            
    except HTTPException:
        raise
    except ValueError as e:
        logger.error(f"Invalid update data: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error updating exception in database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to update exception: {str(e)}",
        )


@router.post("/{tenant_id}/{exception_id}/playbook/recalculate", response_model=PlaybookRecalculationResponse)
async def recalculate_playbook(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    request: Request = None,
) -> PlaybookRecalculationResponse:
    """
    Recalculate and update the playbook assignment for an exception.
    
    POST /exceptions/{exception_id}/playbook/recalculate
    
    Phase 7 P7-8: Re-runs playbook matching and updates exception playbook assignment.
    
    This endpoint:
    - Loads the exception from the database
    - Re-runs playbook matching using the Playbook Matching Service
    - Updates exception.current_playbook_id and exception.current_step
    - Emits a PlaybookRecalculated event (idempotent - only if assignment changed)
    
    Query Parameters:
    - tenant_id: Tenant identifier (required for isolation)
    
    Returns:
    - Exception ID
    - Current playbook ID (or None if no playbook matched)
    - Current step (or None if no playbook matched)
    - Playbook metadata (name, version) if available
    - Reasoning for playbook selection
    
    Raises:
    - HTTPException 400 if tenant_id is missing or invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found or doesn't belong to tenant
    - HTTPException 500 if database or matching service error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
    if request and hasattr(request.state, "tenant_id"):
        authenticated_tenant_id = request.state.tenant_id
        if authenticated_tenant_id != tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"query={tenant_id} for {request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match query tenant '{tenant_id}'",
            )
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Recalculating playbook for exception {exception_id}, tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        from src.repository.exception_events_repository import ExceptionEventRepository
        from src.repository.dto import ExceptionUpdateDTO, ExceptionEventDTO
        from src.infrastructure.repositories.playbook_repository import PlaybookRepository
        from src.playbooks.matching_service import PlaybookMatchingService
        from src.models.exception_record import ExceptionRecord, Severity, ResolutionStatus
        from src.infrastructure.db.models import ActorType
        from datetime import datetime, timezone
        import uuid
        import hashlib
        
        async with get_db_session_context() as session:
            # Load exception from database
            exception_repo = ExceptionRepository(session)
            db_exception = await exception_repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                logger.warning(
                    f"Exception {exception_id} not found for tenant {tenant_id} "
                    "or doesn't belong to tenant"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Store previous playbook assignment for idempotency check
            previous_playbook_id = db_exception.current_playbook_id
            previous_step = db_exception.current_step
            
            # Convert DB Exception to ExceptionRecord for matching service
            severity_map = {
                "low": Severity.LOW,
                "medium": Severity.MEDIUM,
                "high": Severity.HIGH,
                "critical": Severity.CRITICAL,
            }
            severity = severity_map.get(
                db_exception.severity.value if hasattr(db_exception.severity, 'value') else str(db_exception.severity).lower(),
                Severity.MEDIUM
            )
            
            status_map = {
                "open": ResolutionStatus.OPEN,
                "analyzing": ResolutionStatus.IN_PROGRESS,
                "resolved": ResolutionStatus.RESOLVED,
                "escalated": ResolutionStatus.ESCALATED,
            }
            resolution_status = status_map.get(
                db_exception.status.value if hasattr(db_exception.status, 'value') else str(db_exception.status).lower(),
                ResolutionStatus.OPEN
            )
            
            # Build normalized context from database fields
            normalized_context = {
                "domain": db_exception.domain,
            }
            if db_exception.entity:
                normalized_context["entity"] = db_exception.entity
            if db_exception.amount:
                normalized_context["amount"] = float(db_exception.amount)
            if db_exception.sla_deadline:
                normalized_context["sla_deadline"] = db_exception.sla_deadline
            
            # Create ExceptionRecord from database model
            exception_record = ExceptionRecord(
                exception_id=db_exception.exception_id,
                tenant_id=db_exception.tenant_id,
                source_system=db_exception.source_system,
                exception_type=db_exception.type,
                severity=severity,
                timestamp=db_exception.created_at or datetime.now(timezone.utc),
                raw_payload={},
                normalized_context=normalized_context,
                resolution_status=resolution_status,
                audit_trail=[],
            )
            
            # Load TenantPolicyPack if available (optional for matching)
            tenant_policy = None
            try:
                from src.tenantpack.loader import load_tenant_policy
                from src.domainpack.registry import DomainPackRegistry
                registry = DomainPackRegistry()
                domain_pack = registry.get_latest(tenant_id)
                if domain_pack:
                    # Try to load tenant policy from the same directory structure
                    # This is a simplified approach - in production, this would come from a config
                    tenant_policy = None  # Optional, matching service can work without it
            except Exception as e:
                logger.debug(f"Could not load tenant policy for tenant {tenant_id}: {e}")
                tenant_policy = None
            
            # Initialize Playbook Matching Service
            playbook_repo = PlaybookRepository(session)
            matching_service = PlaybookMatchingService(playbook_repo)
            
            # Run playbook matching
            matching_result = await matching_service.match_playbook(
                tenant_id=tenant_id,
                exception=exception_record,
                tenant_policy=tenant_policy,
            )
            
            # Determine new playbook assignment
            new_playbook_id = matching_result.playbook.playbook_id if matching_result.playbook is not None else None
            new_step = 1 if matching_result.playbook is not None else None  # Reset to first step if playbook assigned
            
            # Check if playbook assignment changed (for idempotency)
            playbook_changed = (
                previous_playbook_id != new_playbook_id or
                (new_playbook_id is not None and previous_step != new_step)
            )
            
            # Update exception with new playbook assignment
            await exception_repo.update_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                updates=ExceptionUpdateDTO(
                    current_playbook_id=new_playbook_id,
                    current_step=new_step,
                ),
            )
            
            # Emit PlaybookRecalculated event (only if playbook assignment changed)
            event_repo = ExceptionEventRepository(session)
            if playbook_changed:
                # Generate deterministic event ID based on exception_id and new assignment for idempotency
                # This ensures re-running recalculation with same result doesn't create duplicate events
                event_id_str = f"{exception_id}:{new_playbook_id}:{new_step}:recalculated"
                event_id_bytes = hashlib.md5(event_id_str.encode()).digest()
                event_id = uuid.UUID(bytes=event_id_bytes[:16])
                
                event = ExceptionEventDTO(
                    event_id=event_id,
                    exception_id=exception_id,
                    tenant_id=tenant_id,
                    event_type="PlaybookRecalculated",
                    actor_type=ActorType.SYSTEM,
                    actor_id="PlaybookRecalculationAPI",
                    payload={
                        "previous_playbook_id": previous_playbook_id,
                        "previous_step": previous_step,
                        "new_playbook_id": new_playbook_id,
                        "new_step": new_step,
                        "playbook_name": matching_result.playbook.name if matching_result.playbook is not None else None,
                        "playbook_version": matching_result.playbook.version if matching_result.playbook is not None else None,
                        "reasoning": matching_result.reasoning,
                    },
                )
                
                # Use idempotent event insertion
                event_created = await event_repo.append_event_if_new(event)
                if event_created:
                    logger.info(
                        f"Recalculated playbook for exception {exception_id}: "
                        f"playbook_id={previous_playbook_id} -> {new_playbook_id}, "
                        f"step={previous_step} -> {new_step}"
                    )
                else:
                    logger.info(
                        f"PlaybookRecalculated event already exists for exception {exception_id} "
                        f"with playbook_id={new_playbook_id}, step={new_step}. Skipping duplicate event."
                    )
            else:
                logger.info(
                    f"Playbook recalculation for exception {exception_id} resulted in same assignment "
                    f"(playbook_id={new_playbook_id}, step={new_step}). No event emitted."
                )
            
            # Build response (use aliases for JSON serialization)
            response = PlaybookRecalculationResponse(
                exceptionId=exception_id,  # Use alias
                currentPlaybookId=new_playbook_id,  # Use alias
                currentStep=new_step,  # Use alias
                playbookName=matching_result.playbook.name if matching_result.playbook is not None else None,  # Use alias
                playbookVersion=matching_result.playbook.version if matching_result.playbook is not None else None,  # Use alias
                reasoning=matching_result.reasoning,
            )
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error recalculating playbook: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to recalculate playbook: {str(e)}")


def _derive_step_status_from_events(
    steps: list[Any],
    events: list[Any],
    current_step: Optional[int],
) -> dict[int, str]:
    """
    Derive step status from playbook events.
    
    Phase 7 P7-9: Helper function to determine step status from events.
    
    Status logic:
    - If PlaybookCompleted event exists: all steps are "completed"
    - If PlaybookStepCompleted event exists for a step: that step is "completed"
    - Steps before current_step are "completed" (if current_step is set)
    - Steps after current_step are "pending" (if current_step is set)
    - Steps with no events and before current_step are "pending"
    - Steps can be "skipped" if explicitly marked (not implemented in MVP)
    
    Args:
        steps: List of PlaybookStep instances (ordered by step_order)
        events: List of ExceptionEvent instances for the exception
        current_step: Current step number from exception (1-indexed, or None)
        
    Returns:
        Dictionary mapping step_order -> status ("pending", "completed", or "skipped")
    """
    step_status: dict[int, str] = {}
    
    # Initialize all steps as "pending"
    for step in steps:
        step_status[step.step_order] = "pending"
    
    # Check for PlaybookCompleted event (all steps completed)
    playbook_completed = any(
        e.event_type == "PlaybookCompleted" for e in events
    )
    
    if playbook_completed:
        # All steps are completed
        for step in steps:
            step_status[step.step_order] = "completed"
        return step_status
    
    # Check for PlaybookStepCompleted events
    completed_step_orders = set()
    for event in events:
        if event.event_type == "PlaybookStepCompleted":
            payload = event.payload if isinstance(event.payload, dict) else {}
            step_order = payload.get("step_order")
            if step_order is not None:
                completed_step_orders.add(int(step_order))
    
    # Mark completed steps
    for step_order in completed_step_orders:
        if step_order in step_status:
            step_status[step_order] = "completed"
    
    # If current_step is set, mark steps before it as completed (if not already marked)
    if current_step is not None:
        for step in steps:
            if step.step_order < current_step and step_status.get(step.step_order) == "pending":
                step_status[step.step_order] = "completed"
    
    return step_status


@router.get("/{tenant_id}/{exception_id}/playbook", response_model=PlaybookStatusResponse)
async def get_playbook_status(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    request: Request = None,
) -> PlaybookStatusResponse:
    """
    Get playbook status for an exception.
    
    GET /exceptions/{tenant_id}/{exception_id}/playbook
    
    Phase 7 P7-9: Returns playbook metadata and step statuses derived from events.
    
    This endpoint:
    - Loads the exception and verifies tenant ownership
    - Loads the current playbook (if any) and its ordered steps
    - Derives per-step status from events (PlaybookStarted, PlaybookStepCompleted, PlaybookCompleted)
    - Returns playbook metadata and step statuses
    
    Returns:
    - Exception ID
    - Playbook metadata (id, name, version, conditions)
    - Steps list with status (pending/completed/skipped)
    - Current step indicator
    
    Raises:
    - HTTPException 400 if tenant_id is missing or invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found or doesn't belong to tenant
    - HTTPException 500 if database error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
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
    
    logger.info(f"Getting playbook status for exception {exception_id}, tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        from src.repository.exception_events_repository import ExceptionEventRepository
        from src.repository.dto import EventFilter
        from src.infrastructure.repositories.playbook_repository import PlaybookRepository
        from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
        import json
        
        async with get_db_session_context() as session:
            # Load exception and verify tenant ownership
            exception_repo = ExceptionRepository(session)
            db_exception = await exception_repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                logger.warning(
                    f"Exception {exception_id} not found for tenant {tenant_id} "
                    "or doesn't belong to tenant"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # If no playbook assigned, return empty response
            if db_exception.current_playbook_id is None:
                return PlaybookStatusResponse(
                    exceptionId=exception_id,  # Use alias for JSON serialization
                    playbookId=None,
                    playbookName=None,
                    playbookVersion=None,
                    conditions=None,
                    steps=[],
                    currentStep=None,
                )
            
            # Load playbook with tenant isolation
            playbook_repo = PlaybookRepository(session)
            playbook = await playbook_repo.get_playbook(
                db_exception.current_playbook_id,
                tenant_id,
            )
            
            if playbook is None:
                logger.warning(
                    f"Playbook {db_exception.current_playbook_id} not found for tenant {tenant_id}"
                )
                # Playbook was deleted or doesn't belong to tenant
                return PlaybookStatusResponse(
                    exceptionId=exception_id,  # Use alias for JSON serialization
                    playbookId=db_exception.current_playbook_id,
                    playbookName=None,
                    playbookVersion=None,
                    conditions=None,
                    steps=[],
                    currentStep=db_exception.current_step,
                )
            
            # Load ordered steps
            step_repo = PlaybookStepRepository(session)
            steps = await step_repo.get_steps_ordered(
                db_exception.current_playbook_id,
                tenant_id,
            )
            
            # Load playbook-related events
            event_repo = ExceptionEventRepository(session)
            event_filter = EventFilter(
                event_types=["PlaybookStarted", "PlaybookStepCompleted", "PlaybookCompleted"],
            )
            events = await event_repo.get_events_for_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                filters=event_filter,
            )
            
            # Derive step status from events
            step_status_map = _derive_step_status_from_events(
                steps=steps,
                events=events,
                current_step=db_exception.current_step,
            )
            
            # Build step status list
            step_statuses = []
            for step in steps:
                status = step_status_map.get(step.step_order, "pending")
                step_statuses.append(
                    PlaybookStepStatus(
                        stepOrder=step.step_order,  # Use alias for JSON serialization
                        name=step.name,
                        actionType=step.action_type,  # Use alias for JSON serialization
                        status=status,
                    )
                )
            
            # Parse conditions from JSON if stored as string
            conditions = None
            if playbook.conditions:
                if isinstance(playbook.conditions, str):
                    try:
                        conditions = json.loads(playbook.conditions)
                    except (json.JSONDecodeError, TypeError):
                        conditions = {}
                elif isinstance(playbook.conditions, dict):
                    conditions = playbook.conditions
            
            # Build response
            response = PlaybookStatusResponse(
                exceptionId=exception_id,  # Use alias for JSON serialization
                playbookId=playbook.playbook_id,
                playbookName=playbook.name,
                playbookVersion=playbook.version,
                conditions=conditions,
                steps=step_statuses,
                currentStep=db_exception.current_step,
            )
            
            logger.info(
                f"Retrieved playbook status for exception {exception_id}: "
                f"playbook_id={playbook.playbook_id}, steps={len(steps)}, "
                f"current_step={db_exception.current_step}"
            )
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving playbook status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve playbook status: {str(e)}")


@router.post("/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete", response_model=PlaybookStatusResponse)
async def complete_playbook_step(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    step_order: int = Path(..., description="Step order number to complete (1-indexed)"),
    request_body: StepCompletionRequest = ...,
    request: Request = None,
) -> PlaybookStatusResponse:
    """
    Complete a playbook step for an exception.
    
    POST /exceptions/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete
    
    Phase 7 P7-10: Completes a playbook step and returns updated playbook status.
    
    This endpoint:
    - Validates tenant ownership of the exception
    - Validates the step is the next expected step
    - Calls PlaybookExecutionService to complete the step
    - Executes safe actions for the step (if applicable)
    - Emits PlaybookStepCompleted event
    - Updates exception.current_step
    - Returns updated playbook status
    
    Request Body:
    - actorType: "human", "agent", or "system"
    - actorId: User ID or agent name
    - notes: Optional notes about completion
    
    Returns:
    - Updated playbook status (same structure as GET /playbook endpoint)
    
    Raises:
    - HTTPException 400 if request body is invalid or actor_type is invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found or doesn't belong to tenant
    - HTTPException 400 if no playbook is assigned
    - HTTPException 400 if step_order is invalid or not the next expected step
    - HTTPException 500 if execution service error occurs
    """
    # Verify tenant ID matches authenticated tenant if available
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
    
    if step_order < 1:
        raise HTTPException(status_code=400, detail="step_order must be >= 1")
    
    logger.info(
        f"Completing step {step_order} for exception {exception_id}, tenant {tenant_id} "
        f"(actor: {request_body.actor_type}/{request_body.actor_id})"
    )
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        from src.infrastructure.repositories.playbook_repository import PlaybookRepository
        from src.infrastructure.repositories.playbook_step_repository import PlaybookStepRepository
        from src.repository.exception_events_repository import ExceptionEventRepository
        from src.playbooks.execution_service import PlaybookExecutionService, PlaybookExecutionError
        from src.infrastructure.db.models import ActorType
        import json
        
        async with get_db_session_context() as session:
            # Load exception and verify tenant ownership
            exception_repo = ExceptionRepository(session)
            db_exception = await exception_repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                logger.warning(
                    f"Exception {exception_id} not found for tenant {tenant_id} "
                    "or doesn't belong to tenant"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Validate playbook is assigned
            if db_exception.current_playbook_id is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"Exception {exception_id} has no playbook assigned",
                )
            
            # Map actor_type string to ActorType enum
            actor_type_map = {
                "human": ActorType.USER,
                "agent": ActorType.AGENT,
                "system": ActorType.SYSTEM,
            }
            actor_type_str = request_body.actor_type.lower()
            if actor_type_str not in actor_type_map:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid actor_type: {request_body.actor_type}. Must be one of: human, agent, system",
                )
            actor_type = actor_type_map[actor_type_str]
            
            # Initialize Playbook Execution Service
            event_repo = ExceptionEventRepository(session)
            playbook_repo = PlaybookRepository(session)
            step_repo = PlaybookStepRepository(session)
            
            execution_service = PlaybookExecutionService(
                exception_repository=exception_repo,
                event_repository=event_repo,
                playbook_repository=playbook_repo,
                step_repository=step_repo,
            )
            
            # Complete the step
            try:
                await execution_service.complete_step(
                    tenant_id=tenant_id,
                    exception_id=exception_id,
                    playbook_id=db_exception.current_playbook_id,
                    step_order=step_order,
                    actor_type=actor_type,
                    actor_id=request_body.actor_id,
                    notes=request_body.notes,
                )
            except PlaybookExecutionError as e:
                # Convert PlaybookExecutionError to appropriate HTTP status
                error_msg = str(e)
                if "not found" in error_msg.lower():
                    raise HTTPException(status_code=404, detail=error_msg)
                elif "not the next expected step" in error_msg.lower() or "not active" in error_msg.lower():
                    raise HTTPException(status_code=400, detail=error_msg)
                elif "requires human approval" in error_msg.lower():
                    raise HTTPException(status_code=403, detail=error_msg)
                else:
                    raise HTTPException(status_code=400, detail=error_msg)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))
            
            # Commit the transaction to ensure updates are persisted
            await session.commit()
            
            # Refresh the exception object to get the latest state from the database
            await session.refresh(db_exception)
            
            # After completion, fetch updated playbook status (reuse logic from GET endpoint)
            # Use the refreshed exception object
            
            # Load playbook (use the refreshed exception's playbook_id)
            playbook_id = db_exception.current_playbook_id
            playbook = await playbook_repo.get_playbook(
                playbook_id,
                tenant_id,
            )
            
            if playbook is None:
                # Playbook was deleted (shouldn't happen, but handle gracefully)
                return PlaybookStatusResponse(
                    exceptionId=exception_id,
                    playbookId=db_exception.current_playbook_id,
                    playbookName=None,
                    playbookVersion=None,
                    conditions=None,
                    steps=[],
                    currentStep=db_exception.current_step,
                )
            
            # Load ordered steps
            steps = await step_repo.get_steps_ordered(
                db_exception.current_playbook_id,
                tenant_id,
            )
            
            # Load playbook-related events
            from src.repository.dto import EventFilter
            event_filter = EventFilter(
                event_types=["PlaybookStarted", "PlaybookStepCompleted", "PlaybookCompleted"],
            )
            events = await event_repo.get_events_for_exception(
                tenant_id=tenant_id,
                exception_id=exception_id,
                filters=event_filter,
            )
            
            # Derive step status from events
            step_status_map = _derive_step_status_from_events(
                steps=steps,
                events=events,
                current_step=db_exception.current_step,
            )
            
            # Build step status list
            step_statuses = []
            for step in steps:
                status = step_status_map.get(step.step_order, "pending")
                step_statuses.append(
                    PlaybookStepStatus(
                        stepOrder=step.step_order,
                        name=step.name,
                        actionType=step.action_type,
                        status=status,
                    )
                )
            
            # Parse conditions from JSON if stored as string
            conditions = None
            if playbook.conditions:
                if isinstance(playbook.conditions, str):
                    try:
                        conditions = json.loads(playbook.conditions)
                    except (json.JSONDecodeError, TypeError):
                        conditions = {}
                elif isinstance(playbook.conditions, dict):
                    conditions = playbook.conditions
            
            # Build response
            response = PlaybookStatusResponse(
                exceptionId=exception_id,
                playbookId=playbook.playbook_id,
                playbookName=playbook.name,
                playbookVersion=playbook.version,
                conditions=conditions,
                steps=step_statuses,
                currentStep=db_exception.current_step,
            )
            
            logger.info(
                f"Completed step {step_order} for exception {exception_id}: "
                f"playbook_id={playbook.playbook_id}, new current_step={db_exception.current_step}"
            )
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing playbook step: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to complete playbook step: {str(e)}")

