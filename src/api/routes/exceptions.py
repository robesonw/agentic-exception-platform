"""
Exception ingestion and status API routes.
Handles raw exception ingestion and normalization.

Phase 6 P6-22: Updated to use DB-backed repositories for all operations.
Phase 9 P9-16: POST /exceptions transformed to async command pattern - events published to broker.
"""

import logging
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Path, Query, Request, status
from pydantic import BaseModel, Field

from src.events.types import ExceptionIngested, PlaybookRecalculationRequested, PlaybookStepCompletionRequested
from src.infrastructure.db.models import ActorType, ExceptionSeverity, ExceptionStatus
from src.messaging.event_publisher import EventPublisherService
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.repository.dto import EventFilter, ExceptionFilter, ExceptionUpdateDTO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/exceptions", tags=["exceptions"])

# IMPORTANT: More specific routes must come BEFORE less specific ones
# FastAPI matches routes in order, so specific routes like /{tenant_id}/{exception_id}/reprocess
# must come before general routes like /{tenant_id}


class ExceptionIngestionRequest(BaseModel):
    """Request model for exception ingestion."""

    exception: dict[str, Any] | None = Field(None, description="Single exception payload")
    exceptions: list[dict[str, Any]] | None = Field(None, description="Batch of exception payloads")
    source_system: Optional[str] = Field(None, description="Source system name (if not in payload)")
    ingestion_method: Optional[str] = Field(None, description="Ingestion method (e.g., 'api', 'webhook', 'file')")

    model_config = {"json_schema_extra": {"example": {"exception": {"error": "Test error"}, "source_system": "ERP"}}}


class ExceptionIngestionResponse(BaseModel):
    """Response model for exception ingestion (202 Accepted)."""

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier (generated)")
    status: str = Field(default="accepted", description="Status: 'accepted'")
    message: str = Field(default="Exception ingestion request accepted", description="Status message")

    model_config = {"json_schema_extra": {"example": {"exceptionId": "exc_001", "status": "accepted", "message": "Exception ingestion request accepted"}}}


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
    correlation_id: Optional[str] = Field(None, description="Correlation ID for tracing (equals exception_id)")

    model_config = {"json_schema_extra": {"example": {"items": [], "total": 0, "page": 1, "page_size": 50, "total_pages": 0, "correlation_id": "exc_001"}}}


class PlaybookRecalculationResponse(BaseModel):
    """Response model for playbook recalculation (202 Accepted)."""

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    status: str = Field(default="accepted", description="Status: 'accepted'")
    message: str = Field(default="Playbook recalculation request accepted", description="Status message")

    model_config = {"json_schema_extra": {"example": {"exceptionId": "exc_001", "status": "accepted", "message": "Playbook recalculation request accepted"}}}


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


def get_event_publisher() -> EventPublisherService:
    """
    Get the global event publisher service instance.
    
    In production, this would be injected via dependency injection.
    
    Returns:
        EventPublisherService instance
    """
    # For MVP, create a singleton instance
    # In production, use dependency injection
    from src.messaging.settings import get_broker_settings
    from src.messaging.kafka_broker import KafkaBroker
    from src.messaging.event_store import DatabaseEventStore
    
    # Get broker settings and create broker
    broker_settings = get_broker_settings()
    broker = KafkaBroker(settings=broker_settings)
    
    # Create event store (database-backed)
    # Note: In production, this would be injected
    event_store = DatabaseEventStore()
    
    return EventPublisherService(broker=broker, event_store=event_store)


# Reprocess route must come BEFORE the general POST /{tenant_id} route
# to ensure FastAPI matches it first (more specific routes must come first)
@router.post("/{tenant_id}/{exception_id}/reprocess", response_model=ExceptionIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def reprocess_exception(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    request: Request = None,
) -> ExceptionIngestionResponse:
    """
    Manually trigger processing for an existing exception.
    
    This endpoint allows you to reprocess an exception that exists in the database
    but hasn't been processed through the pipeline (e.g., if workers weren't running
    when it was ingested, or if it was created directly in the database).
    
    It:
    1. Retrieves the exception from the database
    2. Creates an ExceptionIngested event with the exception's data
    3. Publishes it to Kafka so workers can process it
    
    Returns:
    - 202 Accepted
    - exception_id
    - status: "accepted"
    
    Raises:
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found
    - HTTPException 500 if event publishing fails
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
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Reprocessing exception {exception_id} for tenant {tenant_id}")
    
    # Get exception from database
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
            exception_repo = ExceptionRepository(session)
            db_exception = await exception_repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                logger.warning(
                    f"Exception {exception_id} not found for tenant {tenant_id}"
                )
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Reconstruct raw_payload from exception data
            # Try to get raw_payload from exception metadata or reconstruct from fields
            raw_payload = {}
            
            # If there's a raw_payload field in the database, use it
            # Otherwise, reconstruct from exception fields
            if hasattr(db_exception, 'raw_payload') and db_exception.raw_payload:
                import json
                if isinstance(db_exception.raw_payload, dict):
                    raw_payload = db_exception.raw_payload
                elif isinstance(db_exception.raw_payload, str):
                    try:
                        raw_payload = json.loads(db_exception.raw_payload)
                    except json.JSONDecodeError:
                        raw_payload = {"error": db_exception.raw_payload}
            else:
                # Reconstruct from exception fields
                raw_payload = {
                    "exception_id": db_exception.exception_id,
                    "tenant_id": db_exception.tenant_id,
                    "source_system": db_exception.source_system or "UNKNOWN",
                    "exception_type": db_exception.type,
                    "severity": db_exception.severity.value if hasattr(db_exception.severity, 'value') else str(db_exception.severity),
                    "status": db_exception.status.value if hasattr(db_exception.status, 'value') else str(db_exception.status),
                    "domain": db_exception.domain,
                    "entity": db_exception.entity,
                    "amount": float(db_exception.amount) if db_exception.amount else None,
                    "timestamp": db_exception.created_at.isoformat() if db_exception.created_at else None,
                }
                # Remove None values
                raw_payload = {k: v for k, v in raw_payload.items() if v is not None}
            
            # Determine source system
            source_system = db_exception.source_system or raw_payload.get("sourceSystem") or raw_payload.get("source_system") or "UNKNOWN"
            
            # Phase 9 P9-24: Redact PII at reprocessing
            from src.security.pii_redaction import get_pii_redaction_service
            
            pii_service = get_pii_redaction_service()
            redacted_payload, redaction_metadata = pii_service.redact_pii(
                data=raw_payload,
                tenant_id=tenant_id,
            )
            
            # Ensure secrets never logged
            redacted_payload = pii_service.ensure_secrets_never_logged(redacted_payload, tenant_id)
            
            # Create ExceptionIngested event
            try:
                exception_ingested_event = ExceptionIngested.create(
                    tenant_id=tenant_id,
                    exception_id=exception_id,
                    raw_payload=redacted_payload,
                    source_system=source_system,
                    ingestion_method="reprocess",  # Mark as reprocessed
                    correlation_id=exception_id,
                    metadata={
                        "redaction_metadata": redaction_metadata,
                        "reprocessed": True,
                        "original_created_at": db_exception.created_at.isoformat() if db_exception.created_at else None,
                    },
                )
            except Exception as e:
                logger.error(f"Failed to create ExceptionIngested event: {e}", exc_info=True)
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to create event: {str(e)}",
                )
            
            # Publish event
            from src.messaging.event_store import DatabaseEventStore
            from src.messaging.settings import get_broker_settings
            from src.messaging.kafka_broker import KafkaBroker
            
            broker_settings = get_broker_settings()
            broker = KafkaBroker(settings=broker_settings)
            event_store = DatabaseEventStore(session=session)
            event_publisher = EventPublisherService(broker=broker, event_store=event_store)
            
            await event_publisher.publish_event(
                topic="exceptions",
                event=exception_ingested_event.model_dump(by_alias=True),
            )
            
            logger.info(
                f"Published ExceptionIngested event for reprocessing: exception_id={exception_id}, "
                f"tenant_id={tenant_id}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to reprocess exception {exception_id}: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to reprocess exception: {str(e)}",
        )
    
    # Return 202 Accepted
    return ExceptionIngestionResponse(
        exceptionId=exception_id,
        status="accepted",
        message="Exception reprocessing request accepted and queued for processing",
    )


@router.post("/{tenant_id}", response_model=ExceptionIngestionResponse, status_code=status.HTTP_202_ACCEPTED)
async def ingest_exception(
    tenant_id: str = Path(..., description="Tenant identifier"),
    request: ExceptionIngestionRequest | None = None,
    http_request: Request = None,
) -> ExceptionIngestionResponse:
    """
    Ingest raw exception payload(s) and publish ExceptionIngested event.
    
    Phase 9 P9-16: Transformed to async command pattern.
    - Validates request
    - Creates ExceptionIngested event
    - Stores event in EventStore
    - Publishes to message broker
    - Returns 202 Accepted with exception_id
    
    Accepts either:
    - Single exception: {"exception": {...}}
    - Batch: {"exceptions": [{...}, {...}]}
    
    Returns:
    - 202 Accepted
    - exception_id (generated UUID)
    - status: "accepted"
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
    
    # Validate raw exceptions
    for raw_exception in raw_exceptions:
        if not isinstance(raw_exception, dict):
            raise HTTPException(status_code=400, detail="Each exception must be a JSON object")
        if not raw_exception:
            raise HTTPException(status_code=400, detail="Exception payload cannot be empty")
    
    # Log ingestion event
    logger.info(f"Ingesting {len(raw_exceptions)} exception(s) for tenant {tenant_id}")
    
    # Generate exception_id for the first exception (for MVP, we handle one at a time)
    # In production, we'd handle batch ingestion differently
    exception_id = str(uuid4())
    
    # For MVP, process first exception only
    # In production, we'd emit multiple ExceptionIngested events for batch
    raw_payload = raw_exceptions[0]
    
    # Phase 9 P9-24: Redact PII at ingestion
    from src.security.pii_redaction import get_pii_redaction_service
    
    pii_service = get_pii_redaction_service()
    redacted_payload, redaction_metadata = pii_service.redact_pii(
        data=raw_payload,
        tenant_id=tenant_id,
    )
    
    # Ensure secrets never logged - additional defensive redaction
    redacted_payload = pii_service.ensure_secrets_never_logged(redacted_payload, tenant_id)
    
    # Log redaction if any fields were redacted
    if redaction_metadata.get("redaction_count", 0) > 0:
        logger.info(
            f"Redacted {redaction_metadata['redaction_count']} PII field(s) for exception {exception_id}, "
            f"tenant {tenant_id}: {', '.join(redaction_metadata['redacted_fields'][:5])}"
        )
    
    # Ensure tenantId is set in redacted exception
    if "tenantId" not in redacted_payload:
        redacted_payload["tenantId"] = tenant_id
    
    # Determine source system
    source_system = request.source_system or redacted_payload.get("sourceSystem") or redacted_payload.get("source_system") or "UNKNOWN"
    
    # Determine ingestion method
    ingestion_method = request.ingestion_method or "api"
    
    # Create ExceptionIngested event with redacted payload
    # Phase 9 P9-21: correlation_id = exception_id for distributed tracing
    # Phase 9 P9-24: Use redacted payload to ensure PII/secrets never logged
    try:
        exception_ingested_event = ExceptionIngested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            raw_payload=redacted_payload,  # Use redacted payload
            source_system=source_system,
            ingestion_method=ingestion_method,
            correlation_id=exception_id,  # Explicitly set correlation_id = exception_id
            metadata={
                "redaction_metadata": redaction_metadata,  # Store redaction metadata in event
            },
        )
    except Exception as e:
        logger.error(f"Failed to create ExceptionIngested event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create event: {str(e)}",
        )
    
    # Publish event (this will store in EventStore and publish to broker)
    # Create event publisher with database session context
    from src.infrastructure.db.session import get_db_session_context
    from src.messaging.event_store import DatabaseEventStore
    
    try:
        async with get_db_session_context() as session:
            # Create event store with session
            event_store = DatabaseEventStore(session=session)
            
            # Get broker and create event publisher
            from src.messaging.settings import get_broker_settings
            from src.messaging.kafka_broker import KafkaBroker
            
            broker_settings = get_broker_settings()
            broker = KafkaBroker(settings=broker_settings)
            event_publisher = EventPublisherService(broker=broker, event_store=event_store)
            
            await event_publisher.publish_event(
                topic="exceptions",
                event=exception_ingested_event.model_dump(by_alias=True),
            )
        
        logger.info(
            f"Published ExceptionIngested event: exception_id={exception_id}, "
            f"tenant_id={tenant_id}, source_system={source_system}"
        )
    except Exception as e:
        logger.error(
            f"Failed to publish ExceptionIngested event: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish event: {str(e)}",
        )
    
    # Return 202 Accepted
    return ExceptionIngestionResponse(
        exceptionId=exception_id,
        status="accepted",
        message="Exception ingestion request accepted and queued for processing",
    )


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
    Get event timeline for a specific exception (trace).
    
    Phase 9 P9-21: Trace query helper - returns all events for an exception.
    Queries by both exception_id and correlation_id (which equals exception_id) to get complete trace.
    
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
    - All events in the trace (correlation_id = exception_id)
    
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
            
            # Phase 9 P9-21: Use TraceService for trace querying (queries by correlation_id = exception_id)
            from src.infrastructure.repositories.event_store_repository import EventStoreRepository
            from src.services.trace_service import TraceService
            
            event_store_repo = EventStoreRepository(session)
            trace_service = TraceService(event_store_repo)
            
            # Parse event type filter (TraceService.get_trace_for_exception accepts single event_type string)
            event_type_filter = None
            if event_type:
                # Parse comma-separated event types (use first one for TraceService)
                event_types_list = [et.strip() for et in event_type.split(",") if et.strip()]
                if event_types_list:
                    event_type_filter = event_types_list[0]
            
            # Get trace for exception (queries by correlation_id = exception_id)
            trace_result = await trace_service.get_trace_for_exception(
                exception_id=exception_id,
                tenant_id=tenant_id,
                event_type=event_type_filter,
                start_timestamp=date_from,
                end_timestamp=date_to,
                page=page,
                page_size=page_size,
            )
            
            # Transform EventLog to response format
            events = []
            for event_log in trace_result.items:
                events.append({
                    "eventId": str(event_log.event_id),
                    "exceptionId": event_log.exception_id,
                    "tenantId": event_log.tenant_id,
                    "eventType": event_log.event_type,
                    "actorType": "system",  # Default, can be extracted from metadata
                    "actorId": "system",
                    "payload": event_log.payload if isinstance(event_log.payload, dict) else {},
                    "createdAt": event_log.timestamp.isoformat() if event_log.timestamp else None,
                    "correlationId": event_log.correlation_id,  # Phase 9 P9-21: Include correlation_id
                })
            
            return ExceptionEventListResponse(
                items=events,
                total=trace_result.total,
                page=trace_result.page,
                page_size=trace_result.page_size,
                total_pages=trace_result.total_pages,
                correlation_id=exception_id,  # Phase 9 P9-21: correlation_id = exception_id
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving events from database: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to retrieve events: {str(e)}",
        )


@router.get("/{tenant_id}/{exception_id}/trace", response_model=dict)
async def get_exception_trace(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    request: Request = None,
) -> dict[str, Any]:
    """
    Get trace summary for an exception.
    
    Phase 9 P9-21: Trace query helper - returns trace summary including:
    - Total event count
    - Event types and counts
    - First and last event timestamps
    - Worker types involved
    - Duration
    
    GET /exceptions/{tenant_id}/{exception_id}/trace
    
    Returns:
    - Trace summary with event counts, types, timestamps, and worker types
    
    Raises:
    - HTTPException 400 if tenant_id is missing
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found
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
        tenant_id = authenticated_tenant_id
    
    logger.info(f"Getting trace summary for exception {exception_id}, tenant {tenant_id}")
    
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.infrastructure.repositories.event_store_repository import EventStoreRepository
        from src.services.trace_service import TraceService
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
            # Verify exception exists
            exception_repo = ExceptionRepository(session)
            db_exception = await exception_repo.get_exception(tenant_id, exception_id)
            
            if db_exception is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Exception {exception_id} not found for tenant {tenant_id}",
                )
            
            # Get trace summary
            event_store_repo = EventStoreRepository(session)
            trace_service = TraceService(event_store_repo)
            
            trace_summary = await trace_service.get_trace_summary(
                exception_id=exception_id,
                tenant_id=tenant_id,
            )
            
            return trace_summary
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving trace summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to retrieve trace summary: {str(e)}",
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


@router.post("/{tenant_id}/{exception_id}/playbook/recalculate", response_model=PlaybookRecalculationResponse, status_code=status.HTTP_202_ACCEPTED)
async def recalculate_playbook(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    request: Request = None,
) -> PlaybookRecalculationResponse:
    """
    Request playbook recalculation for an exception.
    
    Phase 9 P9-17: Transformed to async command pattern.
    - Validates request
    - Creates PlaybookRecalculationRequested event
    - Stores event in EventStore
    - Publishes to message broker
    - Returns 202 Accepted
    
    For demo mode (when workers aren't running), also performs synchronous
    playbook matching and assignment.
    
    Returns:
    - 202 Accepted
    - exception_id
    - status: "accepted"
    
    Raises:
    - HTTPException 400 if tenant_id is missing or invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found or doesn't belong to tenant
    - HTTPException 500 if event publishing fails
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
        tenant_id = authenticated_tenant_id
    
    if not tenant_id:
        raise HTTPException(status_code=400, detail="tenant_id is required")
    
    logger.info(f"Requesting playbook recalculation for exception {exception_id}, tenant {tenant_id}")
    
    # Verify exception exists and do synchronous playbook matching
    matched_playbook_name = None
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        from src.infrastructure.repositories.playbook_repository import PlaybookRepository
        from src.playbooks.matching_service import PlaybookMatchingService
        from src.models.exception_record import ExceptionRecord
        
        async with get_db_session_context() as session:
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
            
            # Perform synchronous playbook matching for demo mode
            # This ensures playbooks work without workers running
            playbook_repo = PlaybookRepository(session)
            matching_service = PlaybookMatchingService(playbook_repo)
            
            # Convert DB exception to ExceptionRecord for matching
            # Need to handle enum conversion and required fields
            from src.models.exception_record import Severity
            from datetime import datetime, timezone
            
            # Convert severity enum to Severity enum expected by ExceptionRecord
            severity_value = None
            if db_exception.severity:
                severity_str = db_exception.severity.value.upper() if hasattr(db_exception.severity, 'value') else str(db_exception.severity).upper()
                try:
                    severity_value = Severity(severity_str)
                except ValueError:
                    logger.warning(f"Unknown severity value: {severity_str}")
            
            exception_record = ExceptionRecord(
                exception_id=db_exception.exception_id,
                tenant_id=db_exception.tenant_id,
                exception_type=db_exception.type,
                severity=severity_value,
                source_system=db_exception.source_system or "unknown",
                timestamp=db_exception.created_at or datetime.now(timezone.utc),
                raw_payload={},
                normalized_context={
                    "domain": db_exception.domain,
                    "type": db_exception.type,
                },
            )
            
            # Match playbook
            matching_result = await matching_service.match_playbook(
                tenant_id=tenant_id,
                exception=exception_record,
            )
            
            if matching_result.playbook:
                # Update exception with matched playbook
                db_exception.current_playbook_id = matching_result.playbook.playbook_id
                db_exception.current_step = 1  # Start at step 1
                await session.commit()
                matched_playbook_name = matching_result.playbook.name
                logger.info(
                    f"Matched playbook '{matched_playbook_name}' for exception {exception_id}"
                )
            else:
                logger.info(f"No matching playbook found for exception {exception_id}: {matching_result.reasoning}")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during playbook matching: {e}", exc_info=True)
        # Continue to return success if synchronous matching fails
    
    # Try to publish event for async processing (if workers are running)
    # This is optional - synchronous matching already worked
    try:
        event_publisher = get_event_publisher()
        
        # Create PlaybookRecalculationRequested event
        playbook_recalculation_event = PlaybookRecalculationRequested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            requested_by="api",
        )
        
        # Publish event (this will store in EventStore and publish to broker)
        await event_publisher.publish_event(
            topic="exceptions",
            event=playbook_recalculation_event.model_dump(by_alias=True),
        )
        
        logger.info(
            f"Published PlaybookRecalculationRequested event: exception_id={exception_id}, "
            f"tenant_id={tenant_id}"
        )
    except Exception as e:
        # Don't fail - we already did sync matching
        logger.warning(
            f"Failed to publish PlaybookRecalculationRequested event (workers may not be running): {e}"
        )
    
    # Return 202 Accepted with info about matched playbook
    message = "Playbook recalculation request accepted"
    if matched_playbook_name:
        message = f"Playbook '{matched_playbook_name}' matched and assigned"
    
    return PlaybookRecalculationResponse(
        exceptionId=exception_id,
        status="accepted",
        message=message,
    )


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


@router.post("/{tenant_id}/{exception_id}/playbook/steps/{step_order}/complete", response_model=PlaybookStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def complete_playbook_step(
    tenant_id: str = Path(..., description="Tenant identifier"),
    exception_id: str = Path(..., description="Exception identifier"),
    step_order: int = Path(..., description="Step order number to complete (1-indexed)"),
    request_body: StepCompletionRequest = ...,
    request: Request = None,
) -> PlaybookStatusResponse:
    """
    Request playbook step completion for an exception.
    
    Phase 9 P9-17: Transformed to async command pattern.
    - Validates request
    - Creates PlaybookStepCompletionRequested event
    - Stores event in EventStore
    - Publishes to message broker
    - Returns 202 Accepted
    
    Request Body:
    - actorType: "human", "agent", or "system"
    - actorId: User ID or agent name
    - notes: Optional notes about completion
    
    Returns:
    - 202 Accepted
    - exception_id
    - status: "accepted"
    
    Raises:
    - HTTPException 400 if request body is invalid or step_order is invalid
    - HTTPException 403 if tenant ID mismatch
    - HTTPException 404 if exception not found or doesn't belong to tenant
    - HTTPException 500 if event publishing fails
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
    
    # Validate actor_type
    if request_body.actor_type not in ["human", "agent", "system"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid actor_type: {request_body.actor_type}. Must be 'human', 'agent', or 'system'",
        )
    
    logger.info(
        f"Requesting step {step_order} completion for exception {exception_id}, tenant {tenant_id} "
        f"(actor: {request_body.actor_type}/{request_body.actor_id})"
    )
    
    # Verify exception exists (basic validation)
    try:
        from src.infrastructure.db.session import get_db_session_context
        from src.repository.exceptions_repository import ExceptionRepository
        
        async with get_db_session_context() as session:
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
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error validating exception: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to validate exception: {str(e)}")
    
    # Get event publisher
    event_publisher = get_event_publisher()
    
    # Create PlaybookStepCompletionRequested event
    try:
        step_completion_event = PlaybookStepCompletionRequested.create(
            tenant_id=tenant_id,
            exception_id=exception_id,
            step_order=step_order,
            actor_type=request_body.actor_type,
            actor_id=request_body.actor_id,
            notes=request_body.notes,
        )
    except Exception as e:
        logger.error(f"Failed to create PlaybookStepCompletionRequested event: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create event: {str(e)}",
        )
    
    # Publish event (this will store in EventStore and publish to broker)
    try:
        await event_publisher.publish_event(
            topic="exceptions",
            event=step_completion_event.model_dump(by_alias=True),
        )
        
        logger.info(
            f"Published PlaybookStepCompletionRequested event: exception_id={exception_id}, "
            f"step_order={step_order}, tenant_id={tenant_id}"
        )
    except Exception as e:
        logger.error(
            f"Failed to publish PlaybookStepCompletionRequested event: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to publish event: {str(e)}",
        )
    
    # Return 202 Accepted with minimal response
    # Note: Full playbook status would be available via GET endpoint after async processing
    return PlaybookStatusResponse(
        exceptionId=exception_id,
        playbookId=None,  # Will be populated after async processing
        playbookName=None,
        playbookVersion=None,
        conditions=None,
        steps=[],
        currentStep=None,
    )

