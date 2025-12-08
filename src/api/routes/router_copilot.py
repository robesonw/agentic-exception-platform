"""
Copilot REST API for Phase 5 - AI Co-Pilot.

Provides REST endpoint for Co-Pilot chat functionality.

Reference: docs/phase5-copilot-mvp.md Section 3 (REST API: POST /api/copilot/chat)
"""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from src.copilot.models import CopilotRequest, CopilotResponse
from src.copilot.orchestrator import CopilotOrchestrator
from src.llm.factory import LLMProviderError, load_llm_provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotResponse)
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
    
    # Process request through orchestrator
    http_status = 200
    try:
        response = await orchestrator.process(request)
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

