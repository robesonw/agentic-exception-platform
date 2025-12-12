"""
Copilot Orchestrator for Phase 5 - AI Co-Pilot.

Provides intent classification and orchestration logic for the Co-Pilot.

Reference: docs/phase5-copilot-mvp.md Section 5.3 (Copilot Orchestrator)
"""

import json
import logging
import re
from typing import Literal, Tuple

from src.copilot.guardrails import check_guardrails
from src.copilot.models import CopilotCitation, CopilotRequest, CopilotResponse
from src.copilot.retrieval import (
    get_domain_pack_summary,
    get_exception_by_id,
    get_exception_timeline,
    get_exceptions_by_entity,
    get_imminent_sla_breaches,
    get_policy_pack_summary,
    get_recent_exceptions,
    get_similar_exceptions,
)
from src.llm.base import LLMClient, LLMResponse

# Intent types matching CopilotResponse.answer_type
IntentType = Literal["EXPLANATION", "SUMMARY", "POLICY_HINT", "UNKNOWN"]

# Exception ID pattern: EX- followed by digits (e.g., EX-12345, EX-001)
EXCEPTION_ID_PATTERN = re.compile(r"EX-(\d+)", re.IGNORECASE)

logger = logging.getLogger(__name__)


def classify_intent(message: str) -> Tuple[IntentType, list[str]]:
    """
    Classify user intent from message using simple keyword-based matching.
    
    This is a pure function with no side effects or database access.
    It uses keyword matching and regex to determine intent and extract exception IDs.
    
    Patterns:
    - SUMMARY: Contains keywords "today", "summary", or "exceptions"
    - POLICY_HINT: Contains keywords "policy", "rule", or "domain pack"
    - EXPLANATION: Contains keywords "explain" or "why" AND an exception ID pattern (EX-####)
    - UNKNOWN: Fallback for unrecognized patterns
    
    Args:
        message: User's message/question to the Co-Pilot
        
    Returns:
        Tuple of (intent_type, extracted_exception_ids):
        - intent_type: One of "EXPLANATION", "SUMMARY", "POLICY_HINT", "UNKNOWN"
        - extracted_exception_ids: List of exception IDs found (e.g., ["EX-12345"])
        
    Example:
        >>> classify_intent("Show me today's exceptions")
        ('SUMMARY', [])
        
        >>> classify_intent("Explain EX-12345")
        ('EXPLANATION', ['EX-12345'])
        
        >>> classify_intent("What is the policy for settlement failures?")
        ('POLICY_HINT', [])
        
        >>> classify_intent("Why did EX-001 fail?")
        ('EXPLANATION', ['EX-001'])
        
        >>> classify_intent("Hello, how are you?")
        ('UNKNOWN', [])
    """
    if not message or not isinstance(message, str):
        return ("UNKNOWN", [])
    
    # Normalize message to lowercase for keyword matching
    message_lower = message.lower()
    
    # Extract exception IDs using regex (case-insensitive)
    exception_ids = []
    matches = EXCEPTION_ID_PATTERN.findall(message)
    for match in matches:
        # Reconstruct with EX- prefix (preserve original case from message if possible)
        # For simplicity, use uppercase EX-
        exception_id = f"EX-{match}"
        if exception_id not in exception_ids:
            exception_ids.append(exception_id)
    
    # Check for EXPLANATION intent: "explain" or "why" + exception ID
    explanation_keywords = ["explain", "why", "what happened", "what's wrong", "what went wrong"]
    has_explanation_keyword = any(keyword in message_lower for keyword in explanation_keywords)
    
    if has_explanation_keyword and exception_ids:
        return ("EXPLANATION", exception_ids)
    
    # Check for POLICY_HINT intent: "policy", "rule", "domain pack"
    # Check this before SUMMARY to avoid conflicts (e.g., "show me the rules")
    policy_keywords = ["policy", "rule", "rules", "domain pack", "domainpack", "guardrail", "guard rail"]
    has_policy_keyword = any(keyword in message_lower for keyword in policy_keywords)
    
    if has_policy_keyword:
        return ("POLICY_HINT", exception_ids)
    
    # Check for SUMMARY intent: "today", "summary", "exceptions"
    # Check this after POLICY_HINT to avoid conflicts
    summary_keywords = ["today", "summary", "exceptions", "list", "show me", "what are"]
    has_summary_keyword = any(keyword in message_lower for keyword in summary_keywords)
    
    if has_summary_keyword:
        return ("SUMMARY", exception_ids)
    
    # If we found exception IDs but no clear intent keyword, still classify as EXPLANATION
    # (user might be asking about an exception without using "explain" or "why")
    if exception_ids:
        return ("EXPLANATION", exception_ids)
    
    # Fallback to UNKNOWN
    return ("UNKNOWN", [])


class CopilotOrchestrator:
    """
    Copilot Orchestrator for Phase 5 - AI Co-Pilot.
    
    Orchestrates the Co-Pilot workflow:
    1. Classify user intent
    2. Retrieve required grounding data
    3. Build read-only safety prompt
    4. Call LLM to generate response
    5. Wrap response with citations
    
    Phase 6 P6-21: Integrated with PostgreSQL repositories.
    
    Reference: docs/phase5-copilot-mvp.md Section 5.3 (Copilot Orchestrator)
    """
    
    def __init__(self, llm: LLMClient, session=None):
        """
        Initialize Copilot Orchestrator.
        
        Args:
            llm: LLMClient instance for generating responses
            session: Optional AsyncSession for database access (required for repository calls)
        """
        self.llm = llm
        self.session = session
        logger.debug("CopilotOrchestrator initialized")
    
    async def process(self, request: CopilotRequest, session=None) -> CopilotResponse:
        """
        Process a Copilot request and generate a response.
        
        Flow:
        1. Classify intent from user message
        2. Retrieve required grounding data based on intent
        3. Build read-only safety prompt with context
        4. Call LLM to generate response
        5. Wrap response into CopilotResponse with citations
        
        Args:
            request: CopilotRequest with user message, tenant, domain, and context
            
        Returns:
            CopilotResponse with answer, answer_type, citations, and trace ID
            
        Raises:
            Exception: If LLM generation fails or other errors occur
        """
        # Step 1: Classify intent
        intent_type, extracted_exception_ids = classify_intent(request.message)
        logger.info(
            f"Copilot request processing: tenant_id={request.tenant_id}, "
            f"domain={request.domain}, intent_type={intent_type}, "
            f"exception_ids={extracted_exception_ids if extracted_exception_ids else 'none'}"
        )
        
        # Step 2: Retrieve required grounding data based on intent
        # Use provided session or instance session
        db_session = session or self.session
        context_data = await self._gather_context(
            request=request,
            intent_type=intent_type,
            extracted_exception_ids=extracted_exception_ids,
            session=db_session,
        )
        
        # Step 3: Build rich context dict for LLM
        rich_context = self._build_rich_context(
            request=request,
            intent_type=intent_type,
            context_data=context_data,
        )
        
        # Step 4: Build read-only safety prompt
        prompt = self._build_prompt(
            request=request,
            intent_type=intent_type,
            context_data=context_data,
        )
        
        # Step 5: Call LLM to generate response with rich context
        # TODO (LR-10): Consider using call_with_fallback_chain() for provider-specific fallback chains
        # For now, use direct LLM call. Future enhancement: route through fallback chains
        # Example:
        #   from src.llm.fallbacks import call_with_fallback_chain
        #   llm_response = await call_with_fallback_chain(
        #       prompt=prompt,
        #       context=rich_context,
        #       domain=request.domain,
        #       tenant_id=request.tenant_id,
        #   )
        try:
            llm_response = await self.llm.generate(prompt, context=rich_context)
        except Exception as e:
            logger.error(f"LLM generation failed: {e}", exc_info=True)
            raise
        
        # Step 6: Apply guardrails to LLM response (before wrapping)
        safe_answer = check_guardrails(llm_response.text)
        
        # Step 7: Wrap response into CopilotResponse with citations
        citations = self._extract_citations(
            intent_type=intent_type,
            extracted_exception_ids=extracted_exception_ids,
            context_data=context_data,
        )
        
        # Extract trace ID from raw LLM response if available
        raw_llm_trace_id = None
        if llm_response.raw:
            raw_llm_trace_id = llm_response.raw.get("trace_id") or llm_response.raw.get("id")
        
        response = CopilotResponse(
            answer=safe_answer,
            answer_type=intent_type,
            citations=citations,
            raw_llm_trace_id=raw_llm_trace_id,
        )
        
        logger.info(
            f"Copilot response generated: tenant_id={request.tenant_id}, "
            f"domain={request.domain}, answer_type={response.answer_type}, "
            f"citations_count={len(citations)}, "
            f"guardrails_applied={safe_answer != llm_response.text}"
        )
        
        return response
    
    async def _gather_context(
        self,
        request: CopilotRequest,
        intent_type: IntentType,
        extracted_exception_ids: list[str],
        session=None,
    ) -> dict:
        """
        Gather relevant context data based on intent.
        
        Args:
            request: CopilotRequest
            intent_type: Classified intent type
            extracted_exception_ids: List of exception IDs extracted from message
            
        Returns:
            Dictionary with gathered context data
        """
        context_data = {}
        
        try:
            if intent_type == "EXPLANATION":
                # For EXPLANATION, retrieve exception details and timeline
                if extracted_exception_ids and session:
                    # Get first exception (for now, support single exception)
                    exception_id = extracted_exception_ids[0]
                    exception_data = await get_exception_by_id(
                        session=session,
                        tenant_id=request.tenant_id,
                        domain=request.domain,
                        exception_id=exception_id,
                    )
                    if exception_data:
                        context_data["exception"] = exception_data
                    
                    # Get exception timeline
                    timeline = await get_exception_timeline(
                        session=session,
                        tenant_id=request.tenant_id,
                        domain=request.domain,
                        exception_id=exception_id,
                    )
                    if timeline:
                        context_data["exceptionTimeline"] = timeline
                    
                    # Get similar exceptions for context
                    similar = await get_similar_exceptions(
                        session=session,
                        tenant_id=request.tenant_id,
                        domain=request.domain,
                        exception_type=exception_data.get("exceptionType") if exception_data else None,
                        limit=5,
                    )
                    if similar:
                        context_data["similarExceptions"] = similar
                elif session:
                    # No exception ID found, try to get recent exceptions
                    recent = await get_recent_exceptions(
                        session=session,
                        tenant_id=request.tenant_id,
                        domain=request.domain,
                        limit=5,
                    )
                    if recent:
                        context_data["recentExceptions"] = recent
            
            elif intent_type == "SUMMARY":
                # For SUMMARY, retrieve recent exceptions
                if session:
                    recent = await get_recent_exceptions(
                        session=session,
                        tenant_id=request.tenant_id,
                        domain=request.domain,
                        limit=10,
                    )
                    if recent:
                        context_data["recentExceptions"] = recent
                    
                    # Also get imminent SLA breaches for summary
                    sla_breaches = await get_imminent_sla_breaches(
                        session=session,
                        tenant_id=request.tenant_id,
                        within_minutes=60,
                        limit=10,
                    )
                    if sla_breaches:
                        context_data["imminentSlaBreaches"] = sla_breaches
            
            elif intent_type == "POLICY_HINT":
                # For POLICY_HINT, retrieve domain pack and policy pack summaries
                domain_summary = get_domain_pack_summary(
                    tenant_id=request.tenant_id,
                    domain=request.domain,
                )
                if domain_summary:
                    context_data["domainPack"] = domain_summary
                
                policy_summary = get_policy_pack_summary(
                    tenant_id=request.tenant_id,
                )
                if policy_summary:
                    context_data["policyPack"] = policy_summary
            
            # Always include domain pack summary if available (useful context)
            if "domainPack" not in context_data:
                domain_summary = get_domain_pack_summary(
                    tenant_id=request.tenant_id,
                    domain=request.domain,
                )
                if domain_summary:
                    context_data["domainPack"] = domain_summary
        
        except Exception as e:
            logger.warning(f"Error gathering context: {e}", exc_info=True)
            # Continue with partial context
        
        return context_data
    
    def _build_rich_context(
        self,
        request: CopilotRequest,
        intent_type: IntentType,
        context_data: dict,
    ) -> dict:
        """
        Build rich context dictionary for LLM consumption.
        
        Creates a structured context dict with statistics, sample exceptions,
        and other relevant data that helps DummyLLMClient generate useful responses.
        
        Args:
            request: CopilotRequest
            intent_type: Classified intent type
            context_data: Gathered context data from _gather_context
            
        Returns:
            Dictionary with rich context for LLM
        """
        rich_context = {
            "tenant_id": request.tenant_id,
            "domain": request.domain,
            "intent_type": intent_type,
        }
        
        # Add request context if available
        if request.context:
            rich_context.update(request.context)
        
        # Build exceptions statistics and samples
        exceptions_stats = {
            "total": 0,
            "by_severity": {
                "CRITICAL": 0,
                "HIGH": 0,
                "MEDIUM": 0,
                "LOW": 0,
            },
        }
        sample_exceptions = []
        
        # Extract exceptions from context_data based on intent
        exceptions_list = []
        if intent_type == "SUMMARY" and "recentExceptions" in context_data:
            exceptions_list = context_data["recentExceptions"]
        elif intent_type == "EXPLANATION" and "exception" in context_data:
            # For EXPLANATION, include the specific exception
            exceptions_list = [context_data["exception"]]
        elif intent_type == "EXPLANATION" and "recentExceptions" in context_data:
            exceptions_list = context_data["recentExceptions"]
        
        # Compute statistics and create sample exceptions
        if exceptions_list:
            exceptions_stats["total"] = len(exceptions_list)
            
            # Count by severity
            for exc in exceptions_list:
                severity = exc.get("severity")
                if severity:
                    # Handle both enum and string values
                    if hasattr(severity, "value"):
                        severity_str = severity.value
                    else:
                        severity_str = str(severity).upper()
                    
                    if severity_str in exceptions_stats["by_severity"]:
                        exceptions_stats["by_severity"][severity_str] += 1
            
            # Create sample exceptions (limit to 5, include key fields only)
            for exc in exceptions_list[:5]:
                # Get normalized context (camelCase from model_dump)
                normalized_context = exc.get("normalizedContext") or exc.get("normalized_context") or {}
                
                sample = {
                    "id": exc.get("exceptionId") or exc.get("exception_id"),
                    "type": exc.get("exceptionType") or exc.get("exception_type"),
                    "severity": exc.get("severity"),
                    "entity": normalized_context.get("entity"),
                }
                
                # Convert severity enum to string if needed
                if sample["severity"]:
                    if hasattr(sample["severity"], "value"):
                        sample["severity"] = sample["severity"].value
                    else:
                        sample["severity"] = str(sample["severity"]).upper()
                
                # Remove None values for cleaner output
                sample = {k: v for k, v in sample.items() if v is not None}
                if sample:
                    sample_exceptions.append(sample)
        
        rich_context["exceptions_stats"] = exceptions_stats
        if sample_exceptions:
            rich_context["sample_exceptions"] = sample_exceptions
        
        # Add policies for POLICY_HINT intent
        if intent_type == "POLICY_HINT":
            policies = []
            
            if "domainPack" in context_data:
                domain_pack = context_data["domainPack"]
                # Extract exception types as policies
                exception_types = domain_pack.get("exceptionTypes", [])
                for et in exception_types:
                    policies.append({
                        "type": "exception_type",
                        "name": et.get("name"),
                        "description": et.get("description"),
                    })
            
            if "policyPack" in context_data:
                policy_pack = context_data["policyPack"]
                # Extract approved tools as policies
                approved_tools = policy_pack.get("approvedToolsPreview", [])
                for tool in approved_tools:
                    policies.append({
                        "type": "approved_tool",
                        "name": tool,
                    })
            
            if policies:
                rich_context["policies"] = policies
        
        return rich_context
    
    def _build_prompt(
        self,
        request: CopilotRequest,
        intent_type: IntentType,
        context_data: dict,
    ) -> str:
        """
        Build read-only safety prompt with context.
        
        Uses the prompt template from docs/phase5-copilot-mvp.md Section 7.
        
        Args:
            request: CopilotRequest
            intent_type: Classified intent type
            context_data: Gathered context data
            
        Returns:
            Formatted prompt string
        """
        # Base safety prompt (from docs §7)
        prompt_parts = [
            "You are the read-only AI Co-Pilot of the SentinAI Exception Platform.",
            "You NEVER perform actions.",
            "You NEVER approve, escalate, resolve, update, or modify state.",
            "You ONLY summarize, describe, classify, explain, or highlight patterns.",
            "If asked to perform an action, politely decline and explain the restriction.",
            "Always use factual grounded data from retrieved context.",
            "",
            f"Tenant: {request.tenant_id}",
            f"Domain: {request.domain}",
            "",
            "User Query:",
            request.message,
            "",
        ]
        
        # Add context if available
        if context_data:
            prompt_parts.append("Context:")
            # Format context as JSON for readability
            try:
                context_json = json.dumps(context_data, indent=2, default=str)
                prompt_parts.append(context_json)
            except Exception as e:
                logger.warning(f"Error formatting context as JSON: {e}")
                prompt_parts.append(str(context_data))
        else:
            prompt_parts.append("Context: (No additional context available)")
        
        return "\n".join(prompt_parts)
    
    def _extract_citations(
        self,
        intent_type: IntentType,
        extracted_exception_ids: list[str],
        context_data: dict,
    ) -> list[CopilotCitation]:
        """
        Extract citations from context data.
        
        Args:
            intent_type: Classified intent type
            extracted_exception_ids: List of exception IDs extracted from message
            context_data: Gathered context data
            
        Returns:
            List of CopilotCitation objects
        """
        citations = []
        
        # Add exception citations
        if extracted_exception_ids:
            for exception_id in extracted_exception_ids:
                citations.append(
                    CopilotCitation(
                        type="exception",
                        id=exception_id,
                    )
                )
        
        # Add domain pack citation if available
        if "domainPack" in context_data:
            domain_name = context_data["domainPack"].get("domainName")
            if domain_name:
                citations.append(
                    CopilotCitation(
                        type="domain",
                        id=domain_name,
                    )
                )
        
        # Add policy pack citation if available
        if "policyPack" in context_data:
            tenant_id = context_data["policyPack"].get("tenantId")
            if tenant_id:
                citations.append(
                    CopilotCitation(
                        type="policy",
                        id=tenant_id,
                    )
                )
        
        return citations

