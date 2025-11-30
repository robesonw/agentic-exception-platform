"""
Explainability module for Phase 3.

Provides human-readable decision timelines, evidence tracking, and explainability features.
"""

from src.explainability.evidence import (
    EvidenceInfluence,
    EvidenceItem,
    EvidenceLink,
    EvidenceTracker,
    EvidenceType,
    get_evidence_for_exception,
    get_evidence_links_for_exception,
    get_evidence_tracker,
    link_evidence_to_decision,
    record_evidence_item,
)
from src.explainability.evidence_integration import (
    record_policy_evidence,
    record_rag_evidence,
    record_tool_evidence,
)
from src.explainability.timelines import (
    DecisionTimeline,
    TimelineBuilder,
    TimelineEvent,
    build_timeline_for_exception,
    export_timeline_markdown,
    get_timeline_builder,
    write_timeline_to_file,
)

__all__ = [
    # Timelines
    "DecisionTimeline",
    "TimelineBuilder",
    "TimelineEvent",
    "build_timeline_for_exception",
    "export_timeline_markdown",
    "get_timeline_builder",
    "write_timeline_to_file",
    # Evidence Tracking
    "EvidenceInfluence",
    "EvidenceItem",
    "EvidenceLink",
    "EvidenceTracker",
    "EvidenceType",
    "get_evidence_for_exception",
    "get_evidence_links_for_exception",
    "get_evidence_tracker",
    "link_evidence_to_decision",
    "record_evidence_item",
    # Evidence Integration
    "record_policy_evidence",
    "record_rag_evidence",
    "record_tool_evidence",
]

