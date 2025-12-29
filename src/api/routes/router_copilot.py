"""
Copilot REST API for Phase 13 - Copilot Intelligence MVP.

Provides REST endpoints for Copilot chat, session management, and evidence debugging.

Reference: docs/phase13-copilot-intelligence-mvp.md Section 6 (API Endpoints)
"""

import logging
import time
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, HTTPException, Request, Depends
from pydantic import BaseModel

from src.copilot.models import CopilotRequest, CopilotResponse
from src.copilot.orchestrator import CopilotOrchestrator
from src.services.copilot.copilot_service import CopilotService, CopilotRequest as NewCopilotRequest, CopilotSessionResponse
from src.infrastructure.db.session import get_db_session_context
from src.llm.factory import LLMProviderError, load_llm_provider
from src.services.copilot.indexing.rebuild_service import IndexRebuildService, IndexRebuildError
from src.services.copilot.chunking_service import DocumentChunkingService
from src.services.copilot.embedding_service import EmbeddingService
from src.infrastructure.repositories.copilot_document_repository import CopilotDocumentRepository
from src.services.copilot.similarity import SimilarExceptionsFinder
from src.services.copilot.retrieval import RetrievalService
from src.repository.exceptions_repository import ExceptionRepository
from src.api.routes.onboarding import require_admin_role
from src.api.auth import Role, get_auth_manager

logger = logging.getLogger(__name__)


def require_authenticated_user(request: Request) -> dict:
    """
    Extract authenticated user context from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        dict: User context with user_id, tenant_id, role
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not hasattr(request.state, "user_context"):
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    user_context = request.state.user_context
    return {
        "user_id": user_context.user_id,
        "tenant_id": user_context.tenant_id,
        "role": user_context.role
    }

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


class IndexRebuildRequest(BaseModel):
    """Request model for index rebuild operations."""
    tenant_id: Optional[str] = None  # None for global rebuild
    sources: List[str]  # List of source types: policy_doc, resolved_exception, audit_event, tool_registry
    full_rebuild: bool = False  # True for full rebuild, False for incremental


class IndexRebuildResponse(BaseModel):
    """Response model for index rebuild start operations."""
    job_id: str
    message: str


class SimilarExceptionResponse(BaseModel):
    """Response model for similar exception results."""
    exception_id: str
    similarity_score: float


# Phase 13 Models
class ChatRequest(BaseModel):
    """Request model for copilot chat."""
    message: str
    session_id: Optional[str] = None
    context: Optional[Dict[str, Any]] = None
    domain: Optional[str] = None


class ChatResponse(BaseModel):
    """Response model for copilot chat."""
    request_id: str
    session_id: str
    answer: str
    bullets: List[str]
    citations: List[Dict[str, Any]]
    recommended_playbook: Optional[Dict[str, Any]]
    similar_exceptions: Optional[List[Dict[str, Any]]]
    intent: str
    confidence: float
    processing_time_ms: int
    safety: Dict[str, Any]


class CreateSessionRequest(BaseModel):
    """Request model for creating a new session."""
    title: Optional[str] = None


class CreateSessionResponse(BaseModel):
    """Response model for session creation."""
    session_id: str
    title: str
    created_at: str


class SessionDetailResponse(BaseModel):
    """Response model for session details."""
    session_id: str
    tenant_id: str
    user_id: str
    title: str
    created_at: Optional[str]
    updated_at: Optional[str]
    messages: List[Dict[str, Any]]


class EvidenceDebugResponse(BaseModel):
    """Response model for evidence debugging (admin-only)."""
    request_id: str
    tenant_id: str
    retrieval_debug: Dict[str, Any]
    intent_debug: Dict[str, Any]
    processing_timeline: List[Dict[str, Any]]
    outcome_summary: str
    closed_at: Optional[str] = None
    link_url: Optional[str] = None


class SimilarExceptionsListResponse(BaseModel):
    """Response model for list of similar exceptions."""
    similar_exceptions: List[SimilarExceptionResponse]
    total_count: int


class IndexRebuildStatusResponse(BaseModel):
    """Response model for index rebuild status operations."""
    id: str
    tenant_id: Optional[str]
    sources: List[str]
    full_rebuild: bool
    state: str
    progress: dict
    counts: dict
    last_error: Optional[str]
    error_details: Optional[dict]
    created_at: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


@router.post("/chat/legacy", response_model=CopilotResponse)
async def copilot_chat(
    request: CopilotRequest,
    http_request: Request = None,
) -> CopilotResponse:
    """
    Process a Co-Pilot chat request and generate a response.
    
    POST /api/copilot/chat
    
    Accepts CopilotRequest in request body:
    - message: User's message/question
    - tenant_id: Tenant identifier
    - domain: Domain identifier
    - context: Optional context dictionary
    
    Returns CopilotResponse:
    - answer: Generated answer text
    - answer_type: Type of answer (EXPLANATION, SUMMARY, POLICY_HINT, UNKNOWN)
    - citations: List of citations used
    - raw_llm_trace_id: Optional trace ID from LLM provider
    
    Rules:
    - Validates request body against CopilotRequest model
    - Enforces tenant isolation (rejects mismatches)
    - Strictly no state-changing operations
    - Handles errors safely
    
    Raises:
    - HTTPException 400: If request validation fails
    - HTTPException 403: If tenant ID mismatch detected
    - HTTPException 500: If LLM provider fails or other internal errors occur
    """
    # Record start time for latency tracking
    start_time = time.perf_counter()
    
    # Truncate message for logging (first 120 chars)
    truncated_message = request.message[:120] + "..." if len(request.message) > 120 else request.message
    
    logger.info(
        f"Copilot chat request received: tenant_id={request.tenant_id}, "
        f"domain={request.domain}, message_preview={truncated_message!r}"
    )
    
    # Enforce tenant isolation: verify tenant_id matches authenticated tenant if available
    if http_request and hasattr(http_request.state, "tenant_id"):
        authenticated_tenant_id = http_request.state.tenant_id
        if authenticated_tenant_id != request.tenant_id:
            logger.warning(
                f"Tenant mismatch: authenticated={authenticated_tenant_id}, "
                f"request={request.tenant_id} for {http_request.url.path}"
            )
            raise HTTPException(
                status_code=403,
                detail=f"Tenant ID mismatch: authenticated tenant '{authenticated_tenant_id}' "
                f"does not match request tenant '{request.tenant_id}'",
            )
        # Use authenticated tenant ID for consistency
        request.tenant_id = authenticated_tenant_id
    
    # Validate request (Pydantic model validation is automatic, but we can add custom checks)
    if not request.message or not request.message.strip():
        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty",
        )
    
    if not request.tenant_id or not request.tenant_id.strip():
        raise HTTPException(
            status_code=400,
            detail="tenant_id cannot be empty",
        )
    
    if not request.domain or not request.domain.strip():
        raise HTTPException(
            status_code=400,
            detail="domain cannot be empty",
        )
    
    # Load LLM provider using factory with domain/tenant-aware routing (LR-6)
    try:
        llm_client = load_llm_provider(
            domain=request.domain,
            tenant_id=request.tenant_id,
        )
        logger.debug(
            f"Loaded LLM provider: {type(llm_client).__name__} "
            f"for domain={request.domain}, tenant_id={request.tenant_id}"
        )
    except LLMProviderError as e:
        logger.error(f"Failed to load LLM provider: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize LLM provider: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Unexpected error loading LLM provider: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error: Failed to initialize LLM provider",
        )
    
    # Create orchestrator with LLM client
    try:
        orchestrator = CopilotOrchestrator(llm=llm_client)
    except Exception as e:
        logger.error(f"Failed to create CopilotOrchestrator: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error: Failed to initialize orchestrator",
        )
    
    # Process request through orchestrator with database session
    http_status = 200
    try:
        # Get database session for repository access
        async with get_db_session_context() as session:
            response = await orchestrator.process(request, session=session)
        
        # Calculate latency
        latency_ms = (time.perf_counter() - start_time) * 1000
        
        logger.info(
            f"Copilot chat request completed: tenant_id={request.tenant_id}, "
            f"domain={request.domain}, status=success, "
            f"latency_ms={latency_ms:.2f}, answer_type={response.answer_type}"
        )
        return response
    except HTTPException as e:
        # Calculate latency for failed requests too
        latency_ms = (time.perf_counter() - start_time) * 1000
        http_status = e.status_code
        
        logger.warning(
            f"Copilot chat request failed: tenant_id={request.tenant_id}, "
            f"domain={request.domain}, status={http_status}, "
            f"latency_ms={latency_ms:.2f}, error={e.detail}"
        )
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Calculate latency for failed requests too
        latency_ms = (time.perf_counter() - start_time) * 1000
        http_status = 500
        
        logger.error(
            f"Copilot chat request error: tenant_id={request.tenant_id}, "
            f"domain={request.domain}, status={http_status}, "
            f"latency_ms={latency_ms:.2f}, error={str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: Failed to process request: {str(e)}",
        )


@router.post("/index/rebuild", response_model=IndexRebuildResponse)
async def start_index_rebuild(
    request: IndexRebuildRequest,
    api_request: Request,
) -> IndexRebuildResponse:
    """
    Start a copilot index rebuild operation.
    
    POST /api/copilot/index/rebuild
    
    Accepts IndexRebuildRequest:
    - tenant_id: Tenant to rebuild for (null for global)
    - sources: List of source types to rebuild
    - full_rebuild: Whether to do full or incremental rebuild
    
    Returns IndexRebuildResponse:
    - job_id: Unique identifier for tracking progress
    - message: Success message
    
    Admin only endpoint for managing index rebuilds.
    """
    # Require admin role
    require_admin_role(api_request)
    
    logger.info(
        f"Index rebuild requested: tenant={request.tenant_id}, "
        f"sources={request.sources}, full={request.full_rebuild}"
    )
    
    # Validate sources
    valid_sources = {"policy_doc", "resolved_exception", "audit_event", "tool_registry"}
    invalid_sources = set(request.sources) - valid_sources
    if invalid_sources:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid source types: {list(invalid_sources)}. Valid sources: {list(valid_sources)}",
        )
    
    if not request.sources:
        raise HTTPException(
            status_code=400,
            detail="At least one source type must be specified",
        )
    
    try:
        async with get_db_session_context() as session:
            # Initialize services
            embedding_service = EmbeddingService()
            chunking_service = DocumentChunkingService()
            document_repository = CopilotDocumentRepository(session)
            
            rebuild_service = IndexRebuildService(
                session,
                embedding_service,
                chunking_service,
                document_repository,
            )
            
            job_id = await rebuild_service.start_rebuild(
                tenant_id=request.tenant_id,
                sources=request.sources,
                full_rebuild=request.full_rebuild,
            )
            
            return IndexRebuildResponse(
                job_id=job_id,
                message=f"Index rebuild job started successfully. Use job ID {job_id} to track progress.",
            )
    
    except IndexRebuildError as e:
        logger.error(f"Index rebuild failed to start: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to start index rebuild: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Index rebuild error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/index/rebuild/{job_id}", response_model=IndexRebuildStatusResponse)
async def get_index_rebuild_status(
    job_id: str,
    api_request: Request,
) -> IndexRebuildStatusResponse:
    """
    Get status of an index rebuild operation.
    
    GET /api/copilot/index/rebuild/{job_id}
    
    Returns IndexRebuildStatusResponse with:
    - state: Current job status (pending, running, completed, failed, cancelled)
    - progress: Current and total progress with percentage
    - counts: Documents processed, failed, and chunks indexed
    - error information if job failed
    - timestamps for created, started, completed
    
    Admin only endpoint for monitoring rebuild progress.
    """
    # Require admin role
    require_admin_role(api_request)
    
    logger.info(f"Index rebuild status requested: job_id={job_id}")
    
    try:
        async with get_db_session_context() as session:
            # Initialize services
            embedding_service = EmbeddingService()
            chunking_service = DocumentChunkingService()
            document_repository = CopilotDocumentRepository(session)
            
            rebuild_service = IndexRebuildService(
                session,
                embedding_service,
                chunking_service,
                document_repository,
            )
            
            status = await rebuild_service.get_status(job_id)
            
            return IndexRebuildStatusResponse(**status)
    
    except IndexRebuildError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"Rebuild job not found: {job_id}",
            )
        logger.error(f"Failed to get rebuild status: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to get rebuild status: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Index rebuild status error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.delete("/index/rebuild/{job_id}")
async def cancel_index_rebuild(
    job_id: str,
    api_request: Request,
) -> dict:
    """
    Cancel a running or pending index rebuild operation.
    
    DELETE /api/copilot/index/rebuild/{job_id}
    
    Returns:
    - success: Whether the cancellation was successful
    - message: Result message
    
    Admin only endpoint for cancelling rebuild jobs.
    """
    # Require admin role
    require_admin_role(api_request)
    
    logger.info(f"Index rebuild cancellation requested: job_id={job_id}")
    
    try:
        async with get_db_session_context() as session:
            # Initialize services
            embedding_service = EmbeddingService()
            chunking_service = DocumentChunkingService()
            document_repository = CopilotDocumentRepository(session)
            
            rebuild_service = IndexRebuildService(
                session,
                embedding_service,
                chunking_service,
                document_repository,
            )
            
            cancelled = await rebuild_service.cancel_job(job_id)
            
            if cancelled:
                return {
                    "success": True,
                    "message": f"Rebuild job {job_id} has been cancelled.",
                }
            else:
                return {
                    "success": False,
                    "message": f"Rebuild job {job_id} cannot be cancelled (already completed or failed).",
                }
    
    except IndexRebuildError as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404,
                detail=f"Rebuild job not found: {job_id}",
            )
        logger.error(f"Failed to cancel rebuild: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=f"Failed to cancel rebuild: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Index rebuild cancel error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}",
        )


@router.get("/similar/{exception_id}", response_model=SimilarExceptionsListResponse)
async def get_similar_exceptions(
    exception_id: str,
    tenant_id: str,
    top_n: int = 5,
    http_request: Request = None,
) -> SimilarExceptionsListResponse:
    """
    Find similar resolved exceptions for a given exception.
    
    GET /api/copilot/similar/{exception_id}?tenant_id={tenant_id}&top_n={top_n}
    
    Args:
        exception_id: Exception ID to find similar cases for
        tenant_id: Tenant identifier for isolation (query parameter)
        top_n: Maximum number of similar exceptions to return (default: 5, max: 20)
        http_request: FastAPI request object
    
    Returns:
        SimilarExceptionsListResponse with list of similar exceptions
        
    Raises:
        HTTPException 400: Invalid parameters or exception not found
        HTTPException 403: Tenant access denied
        HTTPException 500: Internal server error
    """
    # Validate parameters
    if not exception_id or not exception_id.strip():
        raise HTTPException(
            status_code=400,
            detail="exception_id cannot be empty"
        )
    
    if not tenant_id or not tenant_id.strip():
        raise HTTPException(
            status_code=400,
            detail="tenant_id cannot be empty"
        )
    
    # Limit top_n to prevent excessive resource usage
    if top_n <= 0 or top_n > 20:
        raise HTTPException(
            status_code=400,
            detail="top_n must be between 1 and 20"
        )

    logger.info(
        f"Similar exceptions request: exception_id={exception_id}, "
        f"tenant_id={tenant_id}, top_n={top_n}"
    )

    try:
        async with get_db_session_context() as session:
            # Initialize services
            embedding_service = EmbeddingService()
            document_repository = CopilotDocumentRepository(session)
            retrieval_service = RetrievalService(embedding_service, document_repository)
            exception_repository = ExceptionRepository(session)
            
            # Initialize the similar exceptions finder
            finder = SimilarExceptionsFinder(exception_repository, retrieval_service)
            
            # Find similar exceptions
            similar_exceptions = await finder.find_similar(
                tenant_id=tenant_id,
                exception_id=exception_id,
                top_n=top_n
            )
            
            # Convert to response format
            response_items = [
                SimilarExceptionResponse(
                    exception_id=sim.exception_id,
                    similarity_score=sim.similarity_score,
                    outcome_summary=sim.outcome_summary,
                    closed_at=sim.closed_at,
                    link_url=sim.link_url
                )
                for sim in similar_exceptions
            ]
            
            logger.info(
                f"Found {len(response_items)} similar exceptions for {exception_id}"
            )
            
            return SimilarExceptionsListResponse(
                similar_exceptions=response_items,
                total_count=len(response_items)
            )

    except ValueError as e:
        logger.warning(f"Invalid request for similar exceptions: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error finding similar exceptions for {exception_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


# Phase 13 Endpoints

def get_copilot_service() -> CopilotService:
    """Dependency to get copilot service instance."""
    # This is a FastAPI dependency that will be replaced at runtime
    # The actual service creation happens in the endpoint functions
    # to access the database session properly
    raise NotImplementedError("Use create_copilot_service_for_request() in endpoints")


def require_authenticated_user(request: Request) -> dict:
    """
    Get authenticated user context from request state.
    
    Returns:
        dict: User context with user_id and tenant_id
        
    Raises:
        HTTPException: If user is not authenticated
    """
    if not hasattr(request.state, "user_context"):
        logger.error("Authentication failed: no user_context in request.state")
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )
    
    user_context = request.state.user_context
    logger.info(f"Authentication context: user_id={user_context.user_id}, tenant_id={user_context.tenant_id}")
    
    # Validate user_id is present
    if not user_context.user_id:
        logger.error(f"Authentication failed: user_id is missing or empty")
        raise HTTPException(
            status_code=401,
            detail="User ID is required"
        )
    
    return {
        "user_id": user_context.user_id,
        "tenant_id": user_context.tenant_id
    }


@router.post("/chat", response_model=ChatResponse)
async def copilot_chat_new(
    request: ChatRequest,
    http_request: Request
) -> ChatResponse:
    """
    Process a copilot chat message with full orchestration.
    
    POST /api/copilot/chat
    
    This is the Phase 13 implementation with complete orchestration flow:
    1. Session management
    2. Intent detection
    3. Evidence retrieval
    4. Similar cases analysis
    5. Playbook recommendations
    6. Response generation with safety
    
    Enforces READ_ONLY mode - no state-changing operations.
    
    Args:
        request: Chat request with message and optional session context
        http_request: HTTP request for extracting auth context
        
    Returns:
        ChatResponse: Complete structured response with citations and metadata
        
    Raises:
        HTTPException 400: If request validation fails
        HTTPException 401: If user is not authenticated
        HTTPException 500: If processing fails
    """
    # Get authenticated user context
    auth_context = require_authenticated_user(http_request)
    
    logger.info(
        f"Phase 13 copilot chat: user_id={auth_context['user_id']}, "
        f"tenant_id={auth_context['tenant_id']}, "
        f"session_id={request.session_id}, message_len={len(request.message)}"
    )
    
    try:
        async with get_db_session_context() as session:
            # Create copilot service with database session
            from src.services.copilot.service_factory import create_copilot_service
            copilot_service = await create_copilot_service(session)
            
            # Create service request
            service_request = NewCopilotRequest(
                message=request.message,
                tenant_id=auth_context['tenant_id'],
                user_id=auth_context['user_id'],
                session_id=request.session_id,
                context=request.context,
                domain=request.domain
            )
            
            # Process through service
            response = await copilot_service.process_message(service_request)
            
            # Convert to API response
            return ChatResponse(
                request_id=response.request_id,
                session_id=str(response.session_id),  # Convert UUID to string
                answer=response.answer,
                bullets=response.bullets,
                citations=[{
                    "id": c.id,
                    "source_type": c.source_type,
                    "title": c.title,
                    "snippet": c.snippet,
                    "relevance_score": c.relevance_score,
                    "metadata": c.metadata
                } for c in response.citations],
                recommended_playbook=response.recommended_playbook,
                similar_exceptions=response.similar_exceptions,
                intent=response.intent,
                confidence=response.confidence,
                processing_time_ms=response.processing_time_ms,
                safety=response.safety
            )
        
    except Exception as e:
        logger.error(
            f"Error in copilot chat for user {auth_context['user_id']}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process chat message: {str(e)}"
        )


@router.post("/sessions", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    http_request: Request
) -> CreateSessionResponse:
    """
    Create a new copilot conversation session.
    
    POST /api/copilot/sessions
    
    Creates a new session for organizing conversation history.
    Each session is isolated to the authenticated user and tenant.
    
    Args:
        request: Session creation request with optional title
        http_request: HTTP request for extracting auth context
        
    Returns:
        CreateSessionResponse: New session details
    """
    # Get authenticated user context
    auth_context = require_authenticated_user(http_request)
    
    logger.info(
        f"Creating copilot session: user_id='{auth_context['user_id']}', "
        f"tenant_id='{auth_context['tenant_id']}', title='{request.title}'"
    )
    
    # Additional debug validation
    if not auth_context.get('user_id'):
        logger.error(f"Auth context user_id is empty or None: {auth_context}")
        raise HTTPException(
            status_code=400,
            detail="Authentication context is invalid - user_id missing"
        )
    
    try:
        async with get_db_session_context() as session:
            # Create copilot service with database session
            from src.services.copilot.service_factory import create_copilot_service
            copilot_service = await create_copilot_service(session)
            
            session_id = await copilot_service.create_session(
                tenant_id=auth_context['tenant_id'],
                user_id=auth_context['user_id'],
                title=request.title
            )
            
            logger.info(f"Session created successfully: {session_id}")
            
            return CreateSessionResponse(
                session_id=str(session_id),
                title=request.title or f"New Conversation {int(time.time())}",
                created_at=str(time.time())
            )
        
    except Exception as e:
        logger.error(
            f"Error creating session for user {auth_context['user_id']}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create session: {str(e)}"
        )


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: str,
    http_request: Request
) -> SessionDetailResponse:
    """
    Get details for a specific copilot session.
    
    GET /api/copilot/sessions/{session_id}
    
    Returns session metadata and conversation history.
    Enforces that users can only access their own sessions.
    
    Args:
        session_id: Session ID to retrieve
        http_request: HTTP request for extracting auth context
        
    Returns:
        SessionDetailResponse: Session details with message history
        
    Raises:
        HTTPException 404: If session not found or access denied
    """
    # Get authenticated user context
    auth_context = require_authenticated_user(http_request)
    
    logger.info(
        f"Getting copilot session: session_id={session_id}, "
        f"user_id={auth_context['user_id']}, tenant_id={auth_context['tenant_id']}"
    )
    
    try:
        async with get_db_session_context() as session:
            # Create copilot service with database session
            from src.services.copilot.service_factory import create_copilot_service
            copilot_service = await create_copilot_service(session)
            
            session_data = await copilot_service.get_session(session_id, auth_context['tenant_id'])
            
            if not session_data:
                raise HTTPException(
                    status_code=404,
                    detail="Session not found"
                )
            
            # Verify user owns this session
            if session_data["user_id"] != auth_context['user_id']:
                raise HTTPException(
                    status_code=404,  # Return 404 to avoid revealing session existence
                    detail="Session not found"
                )
            
            return SessionDetailResponse(**session_data)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting session {session_id} for user {auth_context['user_id']}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get session: {str(e)}"
        )


@router.get("/evidence/{request_id}", response_model=EvidenceDebugResponse)
async def get_evidence_debug(
    request_id: str,
    http_request: Request
) -> EvidenceDebugResponse:
    """
    Get evidence debug information for a specific request (admin-only).
    
    GET /api/copilot/evidence/{request_id}
    
    Returns detailed debugging information about evidence retrieval,
    intent detection, and processing timeline for a specific request.
    
    This endpoint is restricted to admin users only.
    
    Args:
        request_id: The request ID to debug
        http_request: HTTP request for extracting auth context
        
    Returns:
        EvidenceDebugResponse: Debug information
        
    Raises:
        HTTPException 401: If user is not authenticated
        HTTPException 403: If user is not admin
        HTTPException 404: If request not found
    """
    # Require admin role
    require_admin_role(http_request)
    
    # Get authenticated user context
    auth_context = require_authenticated_user(http_request)
    
    logger.info(
        f"Getting evidence debug: request_id={request_id}, "
        f"admin_user_id={auth_context['user_id']}, tenant_id={auth_context['tenant_id']}"
    )
    
    try:
        async with get_db_session_context() as session:
            # Create copilot service with database session
            from src.services.copilot.service_factory import create_copilot_service
            copilot_service = await create_copilot_service(session)
            
            debug_info = await copilot_service.get_evidence_debug_info(
                request_id, auth_context['tenant_id']
            )
            
            if not debug_info:
                raise HTTPException(
                    status_code=404,
                    detail="Request debug information not found"
                )
            
            return EvidenceDebugResponse(**debug_info)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Error getting evidence debug for request {request_id}: {e}",
            exc_info=True
        )
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get debug information: {str(e)}"
        )

