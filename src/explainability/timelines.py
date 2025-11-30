"""
Human-Readable Decision Timelines (P3-28).

Builds timeline representations for exceptions showing:
- Which agents ran and when
- What evidence was used
- Why actions/playbooks were chosen/rejected
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

logger = logging.getLogger(__name__)


class TimelineEvent(BaseModel):
    """
    A single event in the decision timeline.
    
    Represents an agent decision, tool execution, or system action.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(
        default_factory=lambda: str(uuid.uuid4()), description="Unique event identifier"
    )
    timestamp: datetime = Field(..., description="Event timestamp")
    stage_name: str = Field(..., description="Pipeline stage name (e.g., 'intake', 'triage')")
    agent_name: str = Field(..., description="Agent name (e.g., 'IntakeAgent', 'TriageAgent')")
    summary: str = Field(..., description="Human-readable summary of the event")
    evidence_ids: list[str] = Field(
        default_factory=list, description="IDs of evidence items referenced"
    )
    reasoning_excerpt: Optional[str] = Field(
        None, description="Excerpt from agent reasoning (if available)"
    )
    decision: Optional[str] = Field(None, description="Agent decision text")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score")
    next_step: Optional[str] = Field(None, description="Next step in workflow")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional event metadata"
    )


class DecisionTimeline(BaseModel):
    """
    Complete decision timeline for an exception.
    
    Contains all events in chronological order showing the decision-making process.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    exception_id: str = Field(..., alias="exceptionId", description="Exception identifier")
    tenant_id: str = Field(..., alias="tenantId", description="Tenant identifier")
    events: list[TimelineEvent] = Field(
        default_factory=list, description="Timeline events in chronological order"
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        alias="createdAt",
        description="Timeline creation timestamp",
    )


class TimelineBuilder:
    """
    Builds decision timelines from audit trails and agent outputs.
    
    Aggregates data from:
    - Audit trail events
    - Agent decisions stored in pipeline results
    - Evidence tracking
    """

    def __init__(
        self,
        exception_store: Optional[Any] = None,
        audit_dir: str = "./runtime/audit",
    ):
        """
        Initialize timeline builder.
        
        Args:
            exception_store: Optional ExceptionStore instance
            audit_dir: Directory containing audit logs
        """
        self.exception_store = exception_store
        self.audit_dir = Path(audit_dir)

    def build_timeline_for_exception(
        self, exception_id: str, tenant_id: str
    ) -> DecisionTimeline:
        """
        Build decision timeline for an exception.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            DecisionTimeline instance
        """
        events: list[TimelineEvent] = []

        # Get exception and pipeline result from store
        if self.exception_store:
            result = self.exception_store.get_exception(tenant_id, exception_id)
            if result:
                exception, pipeline_result = result
                # Extract events from pipeline result
                events.extend(self._extract_events_from_pipeline(exception, pipeline_result))

        # Extract events from audit trail
        audit_events = self._extract_events_from_audit(exception_id, tenant_id)
        events.extend(audit_events)

        # Sort events by timestamp
        events.sort(key=lambda e: e.timestamp)

        # Remove duplicates (same timestamp + stage_name)
        unique_events = self._deduplicate_events(events)

        return DecisionTimeline(
            exception_id=exception_id,
            tenant_id=tenant_id,
            events=unique_events,
        )

    def _extract_events_from_pipeline(
        self, exception: Any, pipeline_result: dict[str, Any]
    ) -> list[TimelineEvent]:
        """
        Extract timeline events from pipeline result.
        
        Args:
            exception: ExceptionRecord instance
            pipeline_result: Pipeline processing result dictionary
            
        Returns:
            List of TimelineEvent instances
        """
        events: list[TimelineEvent] = []

        # Extract stages from pipeline result
        stages = pipeline_result.get("stages", {})
        context = pipeline_result.get("context", {})
        evidence = context.get("evidence", [])

        # Map stage names to agent names
        stage_to_agent = {
            "intake": "IntakeAgent",
            "triage": "TriageAgent",
            "policy": "PolicyAgent",
            "supervisor_post_policy": "SupervisorAgent",
            "resolution": "ResolutionAgent",
            "supervisor_post_resolution": "SupervisorAgent",
            "feedback": "FeedbackAgent",
        }

        # Process each stage
        for stage_name, stage_data in stages.items():
            agent_name = stage_to_agent.get(stage_name, "UnknownAgent")

            # Extract decision information
            if isinstance(stage_data, dict):
                decision_text = stage_data.get("decision", "")
                confidence = stage_data.get("confidence")
                next_step = stage_data.get("nextStep") or stage_data.get("next_step")
                evidence_list = stage_data.get("evidence", [])
                summary = stage_data.get("summary", decision_text)
                reasoning = stage_data.get("reasoning") or stage_data.get("natural_language_summary")
            else:
                # Try to get attributes if it's an AgentDecision object
                decision_text = getattr(stage_data, "decision", "")
                confidence = getattr(stage_data, "confidence", None)
                next_step = getattr(stage_data, "next_step", None)
                evidence_list = getattr(stage_data, "evidence", [])
                summary = getattr(stage_data, "summary", decision_text)
                reasoning = getattr(stage_data, "natural_language_summary", None)

            # Extract evidence IDs from evidence list
            evidence_ids = []
            for ev in evidence_list:
                if isinstance(ev, dict) and "id" in ev:
                    evidence_ids.append(ev["id"])
                elif isinstance(ev, str):
                    # Try to extract ID from evidence string
                    # Format: "Evidence ID: ev_123" or similar
                    if "ID:" in ev or "id:" in ev:
                        parts = ev.split(":")
                        if len(parts) > 1:
                            evidence_ids.append(parts[-1].strip())

            # Use exception timestamp as base, adjust for stage order
            base_timestamp = exception.timestamp if hasattr(exception, "timestamp") else datetime.now(timezone.utc)
            
            # Estimate timestamp based on stage order (for MVP)
            stage_order = ["intake", "triage", "policy", "supervisor_post_policy", "resolution", "supervisor_post_resolution", "feedback"]
            stage_index = stage_order.index(stage_name) if stage_name in stage_order else 0
            estimated_timestamp = base_timestamp.replace(
                second=base_timestamp.second + stage_index * 2  # 2 seconds per stage estimate
            )

            event = TimelineEvent(
                timestamp=estimated_timestamp,
                stage_name=stage_name,
                agent_name=agent_name,
                summary=summary or decision_text or f"{agent_name} completed {stage_name}",
                evidence_ids=evidence_ids,
                reasoning_excerpt=reasoning,
                decision=decision_text,
                confidence=confidence,
                next_step=next_step,
                metadata={
                    "stage": stage_name,
                    "agent": agent_name,
                },
            )
            events.append(event)

        return events

    def _extract_events_from_audit(
        self, exception_id: str, tenant_id: str
    ) -> list[TimelineEvent]:
        """
        Extract timeline events from audit trail.
        
        Args:
            exception_id: Exception identifier
            tenant_id: Tenant identifier
            
        Returns:
            List of TimelineEvent instances
        """
        events: list[TimelineEvent] = []

        # Look for audit files for this tenant
        tenant_audit_dir = self.audit_dir / tenant_id
        audit_files = []
        
        if tenant_audit_dir.exists():
            audit_files = list(tenant_audit_dir.glob("*.jsonl"))
        else:
            # Fallback to root audit directory
            audit_files = list(self.audit_dir.glob("*.jsonl"))

        for audit_file in audit_files:
            try:
                with open(audit_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                            
                            # Check if this entry is related to our exception
                            data = entry.get("data", {})
                            if exception_id not in json.dumps(data):
                                continue
                            
                            # Extract event information
                            event_type = entry.get("event_type", "")
                            timestamp_str = entry.get("timestamp", "")
                            
                            if timestamp_str:
                                try:
                                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                except Exception:
                                    timestamp = datetime.now(timezone.utc)
                            else:
                                timestamp = datetime.now(timezone.utc)
                            
                            # Map event types to stages
                            event_type_to_stage = {
                                "agent_event": data.get("agent_name", "unknown").lower().replace("agent", ""),
                                "tool_call": "tool_execution",
                                "decision": "decision",
                            }
                            
                            stage_name = event_type_to_stage.get(event_type, event_type)
                            agent_name = data.get("agent_name", "System")
                            
                            # Extract summary
                            if event_type == "agent_event":
                                decision = data.get("decision", {})
                                if isinstance(decision, dict):
                                    summary = decision.get("decision", f"{agent_name} processed exception")
                                else:
                                    summary = str(decision)
                            elif event_type == "tool_call":
                                summary = f"Tool {data.get('tool_name', 'unknown')} executed"
                            else:
                                summary = f"{event_type} event"
                            
                            event = TimelineEvent(
                                timestamp=timestamp,
                                stage_name=stage_name,
                                agent_name=agent_name,
                                summary=summary,
                                evidence_ids=[],
                                metadata={"event_type": event_type, "audit_entry": entry},
                            )
                            events.append(event)
                            
                        except json.JSONDecodeError:
                            continue
                        except Exception as e:
                            logger.warning(f"Failed to parse audit entry: {e}")
                            continue
            except Exception as e:
                logger.warning(f"Failed to read audit file {audit_file}: {e}")

        return events

    def _deduplicate_events(self, events: list[TimelineEvent]) -> list[TimelineEvent]:
        """
        Remove duplicate events (same timestamp + stage_name).
        
        Args:
            events: List of timeline events
            
        Returns:
            Deduplicated list of events
        """
        seen = set()
        unique_events = []
        
        for event in events:
            key = (event.timestamp.isoformat(), event.stage_name)
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
        
        return unique_events


def export_timeline_markdown(timeline: DecisionTimeline) -> str:
    """
    Export timeline to Markdown format.
    
    Args:
        timeline: DecisionTimeline instance
        
    Returns:
        Markdown string representation
    """
    lines = []
    
    # Header
    lines.append(f"# Decision Timeline for Exception {timeline.exception_id}")
    lines.append("")
    lines.append(f"**Tenant:** {timeline.tenant_id}")
    lines.append(f"**Created:** {timeline.created_at.isoformat()}")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    # Events
    if not timeline.events:
        lines.append("*No events recorded.*")
    else:
        lines.append("## Timeline Events")
        lines.append("")
        
        for idx, event in enumerate(timeline.events, start=1):
            lines.append(f"### Event {idx}: {event.agent_name} - {event.stage_name}")
            lines.append("")
            lines.append(f"**Timestamp:** {event.timestamp.isoformat()}")
            lines.append(f"**Summary:** {event.summary}")
            lines.append("")
            
            if event.decision:
                lines.append(f"**Decision:** {event.decision}")
                lines.append("")
            
            if event.confidence is not None:
                lines.append(f"**Confidence:** {event.confidence:.2%}")
                lines.append("")
            
            if event.next_step:
                lines.append(f"**Next Step:** {event.next_step}")
                lines.append("")
            
            if event.reasoning_excerpt:
                lines.append("**Reasoning:**")
                lines.append("")
                lines.append(f"> {event.reasoning_excerpt}")
                lines.append("")
            
            if event.evidence_ids:
                lines.append("**Evidence IDs:**")
                for ev_id in event.evidence_ids:
                    lines.append(f"- {ev_id}")
                lines.append("")
            
            if event.metadata:
                lines.append("**Metadata:**")
                for key, value in event.metadata.items():
                    if key not in ["stage", "agent"]:  # Skip redundant fields
                        lines.append(f"- {key}: {value}")
                lines.append("")
            
            lines.append("---")
            lines.append("")
    
    return "\n".join(lines)


def write_timeline_to_file(timeline: DecisionTimeline, output_dir: str = "./runtime/timelines") -> Path:
    """
    Write timeline to Markdown file.
    
    Args:
        timeline: DecisionTimeline instance
        output_dir: Output directory for timeline files
        
    Returns:
        Path to written file
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    timeline_file = output_path / f"{timeline.exception_id}.md"
    
    markdown = export_timeline_markdown(timeline)
    
    with open(timeline_file, "w", encoding="utf-8") as f:
        f.write(markdown)
    
    logger.info(f"Wrote timeline to {timeline_file}")
    
    return timeline_file


# Global builder instance
_timeline_builder: Optional[TimelineBuilder] = None


def get_timeline_builder(exception_store: Optional[Any] = None) -> TimelineBuilder:
    """
    Get global timeline builder instance.
    
    Args:
        exception_store: Optional ExceptionStore instance
        
    Returns:
        TimelineBuilder instance
    """
    global _timeline_builder
    if _timeline_builder is None:
        _timeline_builder = TimelineBuilder(exception_store=exception_store)
    return _timeline_builder


def build_timeline_for_exception(
    exception_id: str, tenant_id: str, exception_store: Optional[Any] = None
) -> DecisionTimeline:
    """
    Build decision timeline for an exception.
    
    Convenience function for integration.
    
    Args:
        exception_id: Exception identifier
        tenant_id: Tenant identifier
        exception_store: Optional ExceptionStore instance
        
    Returns:
        DecisionTimeline instance
    """
    builder = get_timeline_builder(exception_store=exception_store)
    return builder.build_timeline_for_exception(exception_id, tenant_id)

