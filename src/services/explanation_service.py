"""
Explanation Service for Phase 3 (P3-30).

Provides explanation generation and retrieval using:
- Decision timelines (P3-28)
- Evidence tracking (P3-29)
- Agent reasoning outputs
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

from src.audit.logger import AuditLogger
from src.explainability.evidence import (
    EvidenceItem,
    EvidenceLink,
    get_evidence_for_exception,
    get_evidence_links_for_exception,
)
from src.explainability.quality import generate_explanation_hash, score_explanation
from src.explainability.timelines import (
    DecisionTimeline,
    build_timeline_for_exception,
)
from src.models.agent_contracts import AgentDecision
from src.observability.metrics import MetricsCollector, get_metrics_collector
from src.orchestrator.store import ExceptionStore, get_exception_store

logger = logging.getLogger(__name__)


class ExplanationFormat(str, Enum):
    """Supported explanation formats."""

    JSON = "json"
    TEXT = "text"
    STRUCTURED = "structured"


class ExplanationSummary(BaseModel):
    """Summary of an explanation for search results."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    tenant_id: str = Field(..., alias="tenantId", description="Tenant identifier")
    agent_name: Optional[str] = Field(None, alias="agentName", description="Agent name")
    decision_type: Optional[str] = Field(None, alias="decisionType", description="Decision type")
    summary: str = Field(..., description="Brief explanation summary")
    timestamp: datetime = Field(..., description="When the decision was made")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")


class ExplanationVersion(BaseModel):
    """Version information for an explanation."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    version: str = Field(..., description="Version identifier (pipeline run ID)")
    timestamp: datetime = Field(..., description="When this version was created")
    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")


class ExplanationService:
    """
    Service for generating and retrieving explanations.
    
    Combines decision timelines, evidence tracking, and agent reasoning
    to provide comprehensive explanations in multiple formats.
    """

    def __init__(
        self,
        exception_store: Optional[ExceptionStore] = None,
        audit_logger: Optional[AuditLogger] = None,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        """
        Initialize explanation service.
        
        Phase 3: Enhanced with audit and metrics integration (P3-31).
        
        Args:
            exception_store: Optional ExceptionStore instance
            audit_logger: Optional AuditLogger instance
            metrics_collector: Optional MetricsCollector instance
        """
        self.exception_store = exception_store or get_exception_store()
        self.audit_logger = audit_logger
        self.metrics_collector = metrics_collector or get_metrics_collector()

    def get_explanation(
        self,
        exception_id: str,
        tenant_id: str,
        format: ExplanationFormat = ExplanationFormat.JSON,
    ) -> dict[str, Any] | str:
        """
        Get explanation for an exception in the specified format.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            format: Output format (json, text, structured)
            
        Returns:
            Explanation in requested format (dict for json/structured, str for text)
        """
        # Get exception and pipeline result
        result = self.exception_store.get_exception(tenant_id, exception_id)
        if not result:
            raise ValueError(f"Exception {exception_id} not found for tenant {tenant_id}")
        
        exception, pipeline_result = result
        
        # Get timeline
        timeline = build_timeline_for_exception(exception_id, tenant_id, self.exception_store)
        
        # Get evidence
        evidence_items = get_evidence_for_exception(exception_id, tenant_id)
        evidence_links = get_evidence_links_for_exception(exception_id)
        
        # Extract agent decisions from pipeline result
        agent_decisions = {}
        if "stages" in pipeline_result:
            stages = pipeline_result["stages"]
            for stage_name, decision in stages.items():
                if isinstance(decision, dict):
                    agent_decisions[stage_name] = decision
                elif hasattr(decision, "model_dump"):
                    agent_decisions[stage_name] = decision.model_dump(by_alias=True)
        
        # Generate explanation based on format
        import time
        start_time = time.time()
        
        if format == ExplanationFormat.JSON:
            explanation = self._format_json_explanation(
                exception, timeline, evidence_items, evidence_links, agent_decisions
            )
        elif format == ExplanationFormat.TEXT:
            explanation = self._format_text_explanation(
                exception, timeline, evidence_items, evidence_links, agent_decisions
            )
        elif format == ExplanationFormat.STRUCTURED:
            explanation = self._format_structured_explanation(
                exception, timeline, evidence_items, evidence_links, agent_decisions
            )
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        # Phase 3: Calculate quality score and track metrics (P3-31)
        latency_ms = (time.time() - start_time) * 1000
        quality_score = score_explanation(explanation)
        explanation_hash = generate_explanation_hash(explanation)
        
        # Extract agent names from timeline
        agent_names = list(set(event.agent_name for event in timeline.events))
        
        # Record metrics
        self.metrics_collector.record_explanation_generated(
            tenant_id=tenant_id,
            exception_id=exception_id,
            latency_ms=latency_ms,
            quality_score=quality_score,
        )
        
        # Log audit entry
        if self.audit_logger:
            self.audit_logger.log_explanation_generated(
                exception_id=exception_id,
                tenant_id=tenant_id,
                format=format.value,
                agent_names_involved=agent_names,
                explanation_id=explanation_hash,
                explanation_quality_score=quality_score,
                latency_ms=latency_ms,
            )
        
        return explanation

    def search_explanations(
        self,
        tenant_id: str,
        agent_name: Optional[str] = None,
        decision_type: Optional[str] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        text: Optional[str] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> list[ExplanationSummary]:
        """
        Search explanations with filters.
        
        Args:
            tenant_id: Tenant identifier
            agent_name: Optional agent name filter
            decision_type: Optional decision type filter
            from_ts: Optional start timestamp filter
            to_ts: Optional end timestamp filter
            text: Optional text search query
            page: Page number (1-indexed)
            page_size: Number of results per page
            
        Returns:
            List of ExplanationSummary instances
        """
        # Get all exceptions for tenant
        all_exceptions = self.exception_store.get_tenant_exceptions(tenant_id)
        
        summaries = []
        
        for exception, pipeline_result in all_exceptions:
            # Apply timestamp filters
            if from_ts and exception.timestamp < from_ts:
                continue
            if to_ts and exception.timestamp > to_ts:
                continue
            
            # Extract agent decisions
            stages = pipeline_result.get("stages", {})
            
            for stage_name, decision_data in stages.items():
                # Map stage name to agent name
                stage_to_agent = {
                    "intake": "IntakeAgent",
                    "triage": "TriageAgent",
                    "policy": "PolicyAgent",
                    "supervisor_post_policy": "SupervisorAgent",
                    "resolution": "ResolutionAgent",
                    "supervisor_post_resolution": "SupervisorAgent",
                    "feedback": "FeedbackAgent",
                }
                agent = stage_to_agent.get(stage_name, "UnknownAgent")
                
                # Apply agent filter
                if agent_name and agent != agent_name:
                    continue
                
                # Extract decision information
                if isinstance(decision_data, dict):
                    decision_text = decision_data.get("decision", "")
                    confidence = decision_data.get("confidence")
                else:
                    decision_text = getattr(decision_data, "decision", "")
                    confidence = getattr(decision_data, "confidence", None)
                
                # Apply decision type filter (search in decision text)
                if decision_type and decision_type.lower() not in decision_text.lower():
                    continue
                
                # Apply text search
                if text:
                    searchable_text = f"{decision_text} {exception.exception_id} {exception.exception_type or ''}".lower()
                    if text.lower() not in searchable_text:
                        continue
                
                # Create summary
                summary = ExplanationSummary(
                    exception_id=exception.exception_id,
                    tenant_id=tenant_id,
                    agent_name=agent,
                    decision_type=decision_text[:100] if decision_text else None,
                    summary=decision_text[:200] if decision_text else f"{agent} processed exception",
                    timestamp=exception.timestamp,
                    confidence=confidence,
                )
                summaries.append(summary)
        
        # Sort by timestamp (newest first)
        summaries.sort(key=lambda s: s.timestamp, reverse=True)
        
        # Pagination
        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        
        return summaries[start_idx:end_idx]

    def get_timeline(self, exception_id: str, tenant_id: str) -> DecisionTimeline:
        """
        Get decision timeline for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            DecisionTimeline instance
        """
        return build_timeline_for_exception(exception_id, tenant_id, self.exception_store)

    def get_evidence_graph(
        self, exception_id: str, tenant_id: str
    ) -> dict[str, Any]:
        """
        Get evidence graph for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            Dictionary with evidence items and links
        """
        evidence_items = get_evidence_for_exception(exception_id, tenant_id)
        evidence_links = get_evidence_links_for_exception(exception_id)
        
        return {
            "exception_id": exception_id,
            "tenant_id": tenant_id,
            "evidence_items": [item.model_dump(by_alias=True) for item in evidence_items],
            "evidence_links": [link.model_dump(by_alias=True) for link in evidence_links],
            "graph": self._build_evidence_graph(evidence_items, evidence_links),
        }

    def _format_json_explanation(
        self,
        exception: Any,
        timeline: DecisionTimeline,
        evidence_items: list[EvidenceItem],
        evidence_links: list[EvidenceLink],
        agent_decisions: dict[str, Any],
    ) -> dict[str, Any]:
        """Format explanation as JSON."""
        return {
            "exception_id": exception.exception_id,
            "tenant_id": exception.tenant_id,
            "exception_type": exception.exception_type,
            "severity": exception.severity.value if exception.severity else None,
            "resolution_status": exception.resolution_status.value if exception.resolution_status else None,
            "timeline": timeline.model_dump(by_alias=True),
            "evidence_items": [item.model_dump(by_alias=True) for item in evidence_items],
            "evidence_links": [link.model_dump(by_alias=True) for link in evidence_links],
            "agent_decisions": agent_decisions,
            "version": {
                "version": exception.exception_id,  # MVP: use exception_id as version
                "timestamp": exception.timestamp.isoformat(),
            },
        }

    def _format_text_explanation(
        self,
        exception: Any,
        timeline: DecisionTimeline,
        evidence_items: list[EvidenceItem],
        evidence_links: list[EvidenceLink],
        agent_decisions: dict[str, Any],
    ) -> str:
        """Format explanation as natural language text."""
        lines = []
        
        # Header
        lines.append(f"Explanation for Exception {exception.exception_id}")
        lines.append("=" * 60)
        lines.append("")
        
        # Exception summary
        lines.append(f"Exception Type: {exception.exception_type or 'Unknown'}")
        lines.append(f"Severity: {exception.severity.value if exception.severity else 'Unknown'}")
        lines.append(f"Status: {exception.resolution_status.value if exception.resolution_status else 'Unknown'}")
        lines.append(f"Timestamp: {exception.timestamp.isoformat()}")
        lines.append("")
        
        # Timeline summary
        lines.append("Decision Timeline:")
        lines.append("-" * 60)
        for event in timeline.events:
            lines.append(f"  [{event.timestamp.isoformat()}] {event.agent_name} - {event.stage_name}")
            lines.append(f"    Decision: {event.summary}")
            if event.confidence is not None:
                lines.append(f"    Confidence: {event.confidence:.2%}")
            if event.reasoning_excerpt:
                lines.append(f"    Reasoning: {event.reasoning_excerpt[:200]}")
            lines.append("")
        
        # Evidence summary
        if evidence_items:
            lines.append("Evidence:")
            lines.append("-" * 60)
            for item in evidence_items[:10]:  # Top 10 evidence items
                lines.append(f"  [{item.type.value}] {item.description}")
                if item.similarity_score is not None:
                    lines.append(f"    Similarity: {item.similarity_score:.2%}")
            lines.append("")
        
        # Agent decisions summary
        if agent_decisions:
            lines.append("Agent Decisions:")
            lines.append("-" * 60)
            for stage_name, decision in agent_decisions.items():
                if isinstance(decision, dict):
                    decision_text = decision.get("decision", "")
                    confidence = decision.get("confidence")
                else:
                    decision_text = str(decision)
                    confidence = None
                
                lines.append(f"  {stage_name}: {decision_text}")
                if confidence is not None:
                    lines.append(f"    Confidence: {confidence:.2%}")
            lines.append("")
        
        return "\n".join(lines)

    def _format_structured_explanation(
        self,
        exception: Any,
        timeline: DecisionTimeline,
        evidence_items: list[EvidenceItem],
        evidence_links: list[EvidenceLink],
        agent_decisions: dict[str, Any],
    ) -> dict[str, Any]:
        """Format explanation as structured data."""
        # Group evidence by type
        evidence_by_type = {}
        for item in evidence_items:
            evidence_type = item.type.value
            if evidence_type not in evidence_by_type:
                evidence_by_type[evidence_type] = []
            evidence_by_type[evidence_type].append(item.model_dump(by_alias=True))
        
        # Group links by agent
        links_by_agent = {}
        for link in evidence_links:
            agent = link.agent_name
            if agent not in links_by_agent:
                links_by_agent[agent] = []
            links_by_agent[agent].append(link.model_dump(by_alias=True))
        
        return {
            "exception": {
                "id": exception.exception_id,
                "type": exception.exception_type,
                "severity": exception.severity.value if exception.severity else None,
                "status": exception.resolution_status.value if exception.resolution_status else None,
                "timestamp": exception.timestamp.isoformat(),
            },
            "timeline": {
                "events_count": len(timeline.events),
                "events": [event.model_dump(by_alias=True) for event in timeline.events],
            },
            "evidence": {
                "total_items": len(evidence_items),
                "by_type": evidence_by_type,
                "links_by_agent": links_by_agent,
            },
            "decisions": {
                "stages": list(agent_decisions.keys()),
                "details": agent_decisions,
            },
            "version": {
                "version": exception.exception_id,
                "timestamp": exception.timestamp.isoformat(),
            },
        }

    def _build_evidence_graph(
        self, evidence_items: list[EvidenceItem], evidence_links: list[EvidenceLink]
    ) -> dict[str, Any]:
        """Build evidence graph structure."""
        # Create nodes (evidence items)
        nodes = []
        for item in evidence_items:
            nodes.append(
                {
                    "id": item.id,
                    "type": item.type.value,
                    "label": item.description[:100],
                    "source_id": item.source_id,
                    "similarity_score": item.similarity_score,
                }
            )
        
        # Create edges (evidence links)
        edges = []
        for link in evidence_links:
            edges.append(
                {
                    "from": link.evidence_id,
                    "to": f"{link.agent_name}_{link.stage_name}",
                    "influence": link.influence.value,
                    "agent": link.agent_name,
                    "stage": link.stage_name,
                }
            )
        
        return {"nodes": nodes, "edges": edges}


# Global service instance
_explanation_service: Optional[ExplanationService] = None


def get_explanation_service() -> ExplanationService:
    """
    Get global explanation service instance.
    
    Returns:
        ExplanationService instance
    """
    global _explanation_service
    if _explanation_service is None:
        _explanation_service = ExplanationService()
    return _explanation_service

