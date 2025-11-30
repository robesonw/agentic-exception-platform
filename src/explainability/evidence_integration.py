"""
Evidence Integration Hooks (P3-29).

Integrates evidence tracking with:
- RAG service (records RAG results)
- ToolExecutionEngine (records tool outputs)
- PolicyAgent (records applied rules and guardrails)
"""

import logging
from typing import Any, Optional

from src.explainability.evidence import (
    EvidenceInfluence,
    EvidenceType,
    get_evidence_tracker,
    link_evidence_to_decision,
    record_evidence_item,
)

logger = logging.getLogger(__name__)


def record_rag_evidence(
    exception_id: str,
    tenant_id: str,
    search_results: list[tuple[Any, float]],
    agent_name: str = "TriageAgent",
    stage_name: str = "triage",
) -> list[str]:
    """
    Record RAG search results as evidence items.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        search_results: List of (ExceptionMemoryEntry, similarity_score) tuples
        agent_name: Agent name using the evidence
        stage_name: Pipeline stage name
        
    Returns:
        List of evidence IDs created
    """
    tracker = get_evidence_tracker()
    evidence_ids = []
    
    for entry, similarity_score in search_results:
        try:
            # Extract source information
            source_id = entry.exception_id if hasattr(entry, "exception_id") else str(entry)
            description = (
                f"Similar exception found: {entry.exception_id} "
                f"(similarity: {similarity_score:.3f})"
            )
            
            if hasattr(entry, "resolution_summary"):
                description += f" - Resolution: {entry.resolution_summary[:100]}"
            
            # Record evidence item
            evidence = tracker.record_evidence_item(
                evidence_type=EvidenceType.RAG,
                source_id=source_id,
                description=description,
                tenant_id=tenant_id,
                exception_id=exception_id,
                similarity_score=similarity_score,
                metadata={
                    "entry_exception_id": entry.exception_id if hasattr(entry, "exception_id") else None,
                    "similarity_score": similarity_score,
                },
            )
            
            evidence_ids.append(evidence.id)
            
            # Link evidence to decision
            tracker.link_evidence_to_decision(
                exception_id=exception_id,
                agent_name=agent_name,
                stage_name=stage_name,
                evidence_id=evidence.id,
                influence=EvidenceInfluence.SUPPORT if similarity_score > 0.7 else EvidenceInfluence.CONTEXTUAL,
            )
            
        except Exception as e:
            logger.warning(f"Failed to record RAG evidence: {e}")
            continue
    
    if evidence_ids:
        logger.debug(
            f"Recorded {len(evidence_ids)} RAG evidence items for exception {exception_id}"
        )
    
    return evidence_ids


def record_tool_evidence(
    exception_id: str,
    tenant_id: str,
    tool_name: str,
    tool_result: dict[str, Any],
    agent_name: str = "ResolutionAgent",
    stage_name: str = "resolution",
) -> str:
    """
    Record tool execution result as evidence item.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        tool_name: Name of tool executed
        tool_result: Tool execution result dictionary
        agent_name: Agent name using the evidence
        stage_name: Pipeline stage name
        
    Returns:
        Evidence ID created
    """
    tracker = get_evidence_tracker()
    
    try:
        # Extract result information
        status = tool_result.get("status", "unknown")
        description = f"Tool {tool_name} executed with status: {status}"
        
        if "response" in tool_result:
            response_summary = str(tool_result["response"])[:200]
            description += f" - Response: {response_summary}"
        
        # Record evidence item
        evidence = tracker.record_evidence_item(
            evidence_type=EvidenceType.TOOL,
            source_id=tool_name,
            description=description,
            tenant_id=tenant_id,
            exception_id=exception_id,
            payload_ref=None,  # Could store full result in separate file
            metadata={
                "tool_name": tool_name,
                "status": status,
                "http_status": tool_result.get("http_status"),
                "result_summary": str(tool_result.get("response", ""))[:500],
            },
        )
        
        # Link evidence to decision
        influence = (
            EvidenceInfluence.SUPPORT
            if status == "success"
            else EvidenceInfluence.CONTRADICT
        )
        
        tracker.link_evidence_to_decision(
            exception_id=exception_id,
            agent_name=agent_name,
            stage_name=stage_name,
            evidence_id=evidence.id,
            influence=influence,
        )
        
        logger.debug(
            f"Recorded tool evidence {evidence.id} for tool {tool_name} "
            f"(exception={exception_id})"
        )
        
        return evidence.id
        
    except Exception as e:
        logger.warning(f"Failed to record tool evidence: {e}")
        return ""


def record_policy_evidence(
    exception_id: str,
    tenant_id: str,
    rule_id: str,
    rule_description: str,
    applied: bool,
    agent_name: str = "PolicyAgent",
    stage_name: str = "policy",
) -> str:
    """
    Record policy rule or guardrail as evidence item.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        rule_id: Rule or guardrail identifier
        rule_description: Human-readable description of the rule
        applied: Whether the rule was applied (True) or violated (False)
        agent_name: Agent name using the evidence
        stage_name: Pipeline stage name
        
    Returns:
        Evidence ID created
    """
    tracker = get_evidence_tracker()
    
    try:
        description = f"Policy rule {rule_id}: {rule_description}"
        if not applied:
            description += " (VIOLATED)"
        
        # Record evidence item
        evidence = tracker.record_evidence_item(
            evidence_type=EvidenceType.POLICY,
            source_id=rule_id,
            description=description,
            tenant_id=tenant_id,
            exception_id=exception_id,
            metadata={
                "rule_id": rule_id,
                "applied": applied,
                "rule_description": rule_description,
            },
        )
        
        # Link evidence to decision
        influence = (
            EvidenceInfluence.SUPPORT if applied else EvidenceInfluence.CONTRADICT
        )
        
        tracker.link_evidence_to_decision(
            exception_id=exception_id,
            agent_name=agent_name,
            stage_name=stage_name,
            evidence_id=evidence.id,
            influence=influence,
        )
        
        logger.debug(
            f"Recorded policy evidence {evidence.id} for rule {rule_id} "
            f"(exception={exception_id}, applied={applied})"
        )
        
        return evidence.id
        
    except Exception as e:
        logger.warning(f"Failed to record policy evidence: {e}")
        return ""

