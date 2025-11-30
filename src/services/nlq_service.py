"""
Natural Language Query (NLQ) Service for Phase 3.

Allows operators to ask questions about exceptions in natural language
and get answers based on explainability data + LLM summarization.

Safety:
- Tenant isolation enforced
- All questions and answers are logged/audited
- Answers grounded in provided context only

Matches specification from phase3-mvp-issues.md P3-13.
"""

import json
import logging
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.llm.provider import LLMClient, LLMProviderError
from src.models.agent_contracts import AgentDecision
from src.orchestrator.store import ExceptionStore, get_exception_store
from src.services.ui_query_service import UIQueryService, get_ui_query_service

logger = logging.getLogger(__name__)


class NLQServiceError(Exception):
    """Raised when NLQ operations fail."""

    pass


class NLQService:
    """
    Natural Language Query service for answering operator questions.
    
    Responsibilities:
    - Fetch exception, decisions, evidence, timelines from stores
    - Build compact context bundle
    - Generate LLM prompt with question and context
    - Use LLM to answer questions grounded in context
    - Return answer with references to evidence/decisions used
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        ui_query_service: Optional[UIQueryService] = None,
        exception_store: Optional[ExceptionStore] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize NLQ Service.
        
        Args:
            llm_client: Optional LLMClient instance
            ui_query_service: Optional UIQueryService instance
            exception_store: Optional ExceptionStore instance
            audit_logger: Optional AuditLogger instance
        """
        self.llm_client = llm_client
        self.ui_query_service = ui_query_service or get_ui_query_service()
        self.exception_store = exception_store or get_exception_store()
        self.audit_logger = audit_logger

    async def answer_question(
        self,
        tenant_id: str,
        exception_id: str,
        question: str,
    ) -> dict[str, Any]:
        """
        Answer a natural language question about an exception.
        
        Steps:
        1. Fetch exception, decisions, evidence, timelines from stores
        2. Build compact "context bundle" (only relevant facts)
        3. Build LLM prompt with question and structured context
        4. Use LLMClient to generate answer
        5. Return answer + references (ids of evidence/decisions used)
        
        Args:
            tenant_id: Tenant identifier (enforced for isolation)
            exception_id: Exception identifier
            question: Natural language question
            
        Returns:
            Dictionary with:
            {
                "answer": str,
                "answer_sources": list[str],  # Evidence/decision IDs
                "agent_context_used": list[str],  # Agent names
                "confidence": float,
                "supporting_evidence": list[str],
            }
            
        Raises:
            NLQServiceError: If question cannot be answered
        """
        # Step 1: Fetch exception and related data
        exception_detail = self.ui_query_service.get_exception_detail(tenant_id, exception_id)
        if not exception_detail:
            raise NLQServiceError(f"Exception {exception_id} not found for tenant {tenant_id}")
        
        # Verify tenant isolation
        exception = exception_detail["exception"]
        if exception.get("tenant_id") != tenant_id:
            raise NLQServiceError(f"Tenant isolation violation: exception belongs to different tenant")
        
        # Fetch evidence
        evidence = self.ui_query_service.get_exception_evidence(tenant_id, exception_id)
        
        # Fetch audit events
        audit_events = self.ui_query_service.get_exception_audit(tenant_id, exception_id)
        
        # Step 2: Build compact context bundle
        context_bundle = self._build_context_bundle(exception_detail, evidence, audit_events)
        
        # Step 3: Build LLM prompt
        prompt = self._build_nlq_prompt(question, context_bundle)
        
        # Step 4: Use LLM to generate answer
        if self.llm_client:
            try:
                # Use LLM with NLQAnswer schema (extended schema, not agent schema)
                # Note: LLMClient.generate_json uses get_extended_schema_model internally
                llm_response = await self.llm_client.generate_json(
                    prompt=prompt,
                    schema_name="nlq_answer",
                    tenant_id=tenant_id,
                    agent_name="NLQService",
                    audit_logger=self.audit_logger,
                )
                
                # Extract answer from LLM response
                # LLM response is already validated against NLQAnswer schema
                answer = llm_response.get("answer", "Unable to generate answer from available context.")
                answer_sources = llm_response.get("answer_sources", [])
                agent_context_used = llm_response.get("agent_context_used", [])
                confidence = llm_response.get("confidence", 0.5)
                # Note: NLQAnswer schema has "reasoning" not "supporting_evidence", but we'll extract from reasoning
                reasoning = llm_response.get("reasoning", "")
                supporting_evidence = [reasoning] if reasoning else []
            except LLMProviderError as e:
                logger.warning(f"LLM generation failed for NLQ: {e}. Falling back to simple answer.")
                # Fallback: generate simple answer from context
                answer, answer_sources, agent_context_used, confidence, supporting_evidence = (
                    self._generate_fallback_answer(question, context_bundle)
                )
        else:
            # No LLM client: generate simple answer from context
            answer, answer_sources, agent_context_used, confidence, supporting_evidence = (
                self._generate_fallback_answer(question, context_bundle)
            )
        
        # Step 5: Log question and answer for audit
        if self.audit_logger:
            try:
                self.audit_logger.log_decision(
                    stage="nlq",
                    decision_json={
                        "question": question,
                        "answer": answer,
                        "exception_id": exception_id,
                        "answer_sources": answer_sources,
                        "agent_context_used": agent_context_used,
                        "confidence": confidence,
                    },
                    tenant_id=tenant_id,
                )
            except Exception as audit_e:
                logger.warning(f"Failed to log NLQ to audit: {audit_e}")
        
        return {
            "answer": answer,
            "answer_sources": answer_sources,
            "agent_context_used": agent_context_used,
            "confidence": confidence,
            "supporting_evidence": supporting_evidence,
        }

    def _build_context_bundle(
        self,
        exception_detail: dict[str, Any],
        evidence: Optional[dict[str, Any]],
        audit_events: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        Build compact context bundle from exception data.
        
        Args:
            exception_detail: Exception detail from UIQueryService
            evidence: Evidence from UIQueryService
            audit_events: Audit events from UIQueryService
            
        Returns:
            Compact context bundle dictionary
        """
        exception = exception_detail.get("exception", {})
        agent_decisions = exception_detail.get("agent_decisions", {})
        
        # Extract key information from exception
        exception_summary = {
            "exception_id": exception.get("exception_id"),
            "exception_type": exception.get("exception_type"),
            "severity": exception.get("severity"),
            "resolution_status": exception.get("resolution_status"),
            "source_system": exception.get("source_system"),
            "timestamp": exception.get("timestamp"),
        }
        
        # Extract agent decisions (compact format)
        decisions_summary = {}
        for agent_name, decision in agent_decisions.items():
            if isinstance(decision, dict):
                decisions_summary[agent_name] = {
                    "decision": decision.get("decision", ""),
                    "confidence": decision.get("confidence", 0.0),
                    "evidence": decision.get("evidence", [])[:5],  # Limit to 5 evidence items
                    "next_step": decision.get("next_step", ""),
                }
            elif hasattr(decision, "model_dump"):
                decision_dict = decision.model_dump()
                decisions_summary[agent_name] = {
                    "decision": decision_dict.get("decision", ""),
                    "confidence": decision_dict.get("confidence", 0.0),
                    "evidence": decision_dict.get("evidence", [])[:5],
                    "next_step": decision_dict.get("next_step", ""),
                }
        
        # Extract evidence (compact format)
        evidence_summary = {
            "rag_results": evidence.get("rag_results", [])[:3] if evidence else [],  # Limit to 3
            "tool_outputs": evidence.get("tool_outputs", [])[:5] if evidence else [],  # Limit to 5
            "agent_evidence": evidence.get("agent_evidence", []) if evidence else [],
        }
        
        # Extract key audit events (recent ones)
        recent_audit_events = audit_events[-10:] if audit_events else []  # Last 10 events
        
        return {
            "exception": exception_summary,
            "agent_decisions": decisions_summary,
            "evidence": evidence_summary,
            "recent_audit_events": recent_audit_events,
        }

    def _build_nlq_prompt(self, question: str, context_bundle: dict[str, Any]) -> str:
        """
        Build LLM prompt with question and structured context.
        
        Args:
            question: Natural language question
            context_bundle: Compact context bundle
            
        Returns:
            Prompt string for LLM
        """
        prompt_parts = [
            "You are an assistant helping operators understand exception processing decisions.",
            "",
            "Question:",
            question,
            "",
            "Context (Exception Processing Details):",
            "",
            "Exception:",
            json.dumps(context_bundle["exception"], indent=2, default=str),
            "",
            "Agent Decisions:",
            json.dumps(context_bundle["agent_decisions"], indent=2, default=str),
            "",
            "Evidence:",
            json.dumps(context_bundle["evidence"], indent=2, default=str),
            "",
            "Recent Audit Events:",
            json.dumps(context_bundle["recent_audit_events"], indent=2, default=str),
            "",
            "Instructions:",
            "1. Answer the question based ONLY on the provided context.",
            "2. If the context does not contain enough information, say so clearly.",
            "3. Reference specific agents, decisions, or evidence when relevant.",
            "4. Provide a clear, concise answer.",
            "5. Include confidence score (0.0-1.0) based on how well the context supports the answer.",
            "6. List the evidence/decision IDs that support your answer in answer_sources.",
            "7. List the agent names whose context was used in agent_context_used.",
            "",
            "Return your answer in the following JSON format:",
            "{",
            '  "answer": "Your answer here",',
            '  "answer_sources": ["evidence_id_1", "decision_id_2"],',
            '  "agent_context_used": ["TriageAgent", "PolicyAgent"],',
            '  "confidence": 0.85,',
            '  "supporting_evidence": ["Evidence snippet 1", "Evidence snippet 2"]',
            "}",
        ]
        
        return "\n".join(prompt_parts)

    def _generate_fallback_answer(
        self, question: str, context_bundle: dict[str, Any]
    ) -> tuple[str, list[str], list[str], float, list[str]]:
        """
        Generate a simple fallback answer when LLM is unavailable.
        
        Args:
            question: Natural language question
            context_bundle: Compact context bundle
            
        Returns:
            Tuple of (answer, answer_sources, agent_context_used, confidence, supporting_evidence)
        """
        # Simple keyword-based answer generation
        question_lower = question.lower()
        
        # Extract agent decisions
        agent_decisions = context_bundle.get("agent_decisions", {})
        agent_names = list(agent_decisions.keys())
        
        # Try to answer based on question keywords
        answer = "Based on the available context: "
        answer_sources = []
        supporting_evidence = []
        
        if "why" in question_lower and "block" in question_lower:
            # Question about blocking
            if "policy" in agent_decisions:
                policy_decision = agent_decisions["policy"]
                answer += f"PolicyAgent decision: {policy_decision.get('decision', 'N/A')}. "
                answer += f"Evidence: {', '.join(policy_decision.get('evidence', [])[:3])}"
                answer_sources.append("policy_decision")
                supporting_evidence.extend(policy_decision.get("evidence", [])[:3])
                agent_names = ["PolicyAgent"]
        elif "evidence" in question_lower and "triage" in question_lower:
            # Question about TriageAgent evidence
            if "triage" in agent_decisions:
                triage_decision = agent_decisions["triage"]
                answer += f"TriageAgent used the following evidence: {', '.join(triage_decision.get('evidence', []))}"
                answer_sources.append("triage_decision")
                supporting_evidence.extend(triage_decision.get("evidence", []))
                agent_names = ["TriageAgent"]
        elif "alternative" in question_lower or "possible" in question_lower:
            # Question about alternatives
            answer += "Alternative actions would depend on the specific exception type and available playbooks. "
            answer += "Check the resolution agent decision for details on selected playbooks."
            if "resolution" in agent_decisions:
                answer_sources.append("resolution_decision")
                agent_names = ["ResolutionAgent"]
        else:
            # Generic answer
            answer += "Please review the agent decisions and evidence provided in the context for details."
            answer_sources = list(agent_decisions.keys())
        
        confidence = 0.6  # Lower confidence for fallback answers
        
        return answer, answer_sources, agent_names, confidence, supporting_evidence


# Global singleton instance
_nlq_service: Optional[NLQService] = None


def get_nlq_service() -> NLQService:
    """
    Get the global NLQ service instance.
    
    Returns:
        NLQService instance
    """
    global _nlq_service
    if _nlq_service is None:
        _nlq_service = NLQService()
    return _nlq_service
