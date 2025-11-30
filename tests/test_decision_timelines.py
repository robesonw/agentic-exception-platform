"""
Tests for Decision Timelines (P3-28).

Tests timeline building, event ordering, and export functionality.
"""

import json
import pytest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.explainability.timelines import (
    DecisionTimeline,
    TimelineBuilder,
    TimelineEvent,
    build_timeline_for_exception,
    export_timeline_markdown,
    write_timeline_to_file,
)
from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore


class TestTimelineEvent:
    """Tests for TimelineEvent model."""

    def test_timeline_event_creation(self):
        """Test creating a timeline event."""
        event = TimelineEvent(
            timestamp=datetime.now(timezone.utc),
            stage_name="triage",
            agent_name="TriageAgent",
            summary="Classified exception as DataQualityFailure",
            evidence_ids=["ev_001", "ev_002"],
            reasoning_excerpt="Based on RAG similarity and rule matching",
            decision="Classified as DataQualityFailure",
            confidence=0.85,
            next_step="ProceedToPolicy",
        )
        
        assert event.stage_name == "triage"
        assert event.agent_name == "TriageAgent"
        assert len(event.evidence_ids) == 2
        assert event.confidence == 0.85


class TestDecisionTimeline:
    """Tests for DecisionTimeline model."""

    def test_decision_timeline_creation(self):
        """Test creating a decision timeline."""
        events = [
            TimelineEvent(
                timestamp=datetime.now(timezone.utc),
                stage_name="intake",
                agent_name="IntakeAgent",
                summary="Normalized exception",
            ),
            TimelineEvent(
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=5),
                stage_name="triage",
                agent_name="TriageAgent",
                summary="Classified exception",
            ),
        ]
        
        timeline = DecisionTimeline(
            exception_id="exc_001",
            tenant_id="tenant_001",
            events=events,
        )
        
        assert timeline.exception_id == "exc_001"
        assert timeline.tenant_id == "tenant_001"
        assert len(timeline.events) == 2


class TestTimelineBuilder:
    """Tests for TimelineBuilder."""

    def test_build_timeline_from_pipeline_result(self):
        """Test building timeline from pipeline result."""
        # Create exception
        exception = ExceptionRecord(
            exception_id="exc_001",
            tenant_id="tenant_001",
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "test"},
            normalized_context={},
        )
        
        # Create pipeline result with stages
        pipeline_result = {
            "stages": {
                "intake": {
                    "decision": "Normalized exception",
                    "confidence": 1.0,
                    "nextStep": "ProceedToTriage",
                    "evidence": ["Normalized exception ID: exc_001"],
                },
                "triage": {
                    "decision": "Classified as DataQualityFailure",
                    "confidence": 0.85,
                    "nextStep": "ProceedToPolicy",
                    "evidence": ["Rule matched: invalid_format", "RAG similarity: 0.92"],
                    "natural_language_summary": "Exception matches known pattern",
                },
            },
            "context": {
                "evidence": [],
            },
        }
        
        # Create exception store and add exception
        store = ExceptionStore()
        store.store_exception(exception, pipeline_result)
        
        # Build timeline
        builder = TimelineBuilder(exception_store=store)
        timeline = builder.build_timeline_for_exception("exc_001", "tenant_001")
        
        assert timeline.exception_id == "exc_001"
        assert len(timeline.events) >= 2
        
        # Check events are ordered
        timestamps = [e.timestamp for e in timeline.events]
        assert timestamps == sorted(timestamps)
        
        # Check intake event
        intake_events = [e for e in timeline.events if e.stage_name == "intake"]
        assert len(intake_events) > 0
        assert intake_events[0].agent_name == "IntakeAgent"
        assert intake_events[0].decision == "Normalized exception"
        
        # Check triage event
        triage_events = [e for e in timeline.events if e.stage_name == "triage"]
        assert len(triage_events) > 0
        assert triage_events[0].agent_name == "TriageAgent"
        assert triage_events[0].reasoning_excerpt == "Exception matches known pattern"

    def test_build_timeline_from_audit_trail(self, tmp_path):
        """Test building timeline from audit trail."""
        # Create audit directory structure
        audit_dir = tmp_path / "audit" / "tenant_001"
        audit_dir.mkdir(parents=True)
        
        # Create audit log file
        audit_file = audit_dir / "run_001.jsonl"
        
        # Write audit entries
        base_time = datetime.now(timezone.utc)
        audit_entries = [
            {
                "timestamp": (base_time + timedelta(seconds=1)).isoformat(),
                "run_id": "run_001",
                "tenant_id": "tenant_001",
                "event_type": "agent_event",
                "data": {
                    "agent_name": "IntakeAgent",
                    "exception_id": "exc_001",
                    "decision": {
                        "decision": "Normalized exception",
                        "confidence": 1.0,
                    },
                },
            },
            {
                "timestamp": (base_time + timedelta(seconds=3)).isoformat(),
                "run_id": "run_001",
                "tenant_id": "tenant_001",
                "event_type": "agent_event",
                "data": {
                    "agent_name": "TriageAgent",
                    "exception_id": "exc_001",
                    "decision": {
                        "decision": "Classified as DataQualityFailure",
                        "confidence": 0.85,
                    },
                },
            },
        ]
        
        with open(audit_file, "w", encoding="utf-8") as f:
            for entry in audit_entries:
                f.write(json.dumps(entry) + "\n")
        
        # Build timeline
        builder = TimelineBuilder(audit_dir=str(tmp_path / "audit"))
        timeline = builder.build_timeline_for_exception("exc_001", "tenant_001")
        
        assert timeline.exception_id == "exc_001"
        assert len(timeline.events) >= 2

    def test_event_ordering(self):
        """Test that events are ordered by timestamp."""
        events = [
            TimelineEvent(
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=10),
                stage_name="triage",
                agent_name="TriageAgent",
                summary="Triage completed",
            ),
            TimelineEvent(
                timestamp=datetime.now(timezone.utc),
                stage_name="intake",
                agent_name="IntakeAgent",
                summary="Intake completed",
            ),
            TimelineEvent(
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=5),
                stage_name="policy",
                agent_name="PolicyAgent",
                summary="Policy check completed",
            ),
        ]
        
        timeline = DecisionTimeline(
            exception_id="exc_001",
            tenant_id="tenant_001",
            events=events,
        )
        
        # Events should be sorted by timestamp
        timestamps = [e.timestamp for e in timeline.events]
        assert timestamps == sorted(timestamps)
        
        # First event should be intake
        assert timeline.events[0].stage_name == "intake"
        # Last event should be triage
        assert timeline.events[-1].stage_name == "triage"

    def test_evidence_ids_extraction(self):
        """Test that evidence IDs are extracted correctly."""
        exception = ExceptionRecord(
            exception_id="exc_001",
            tenant_id="tenant_001",
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "test"},
            normalized_context={},
        )
        
        pipeline_result = {
            "stages": {
                "triage": {
                    "decision": "Classified exception",
                    "evidence": [
                        "Evidence ID: ev_001",
                        "RAG result ID: ev_002",
                        "Rule match: invalid_format",
                    ],
                },
            },
            "context": {},
        }
        
        store = ExceptionStore()
        store.store_exception(exception, pipeline_result)
        
        builder = TimelineBuilder(exception_store=store)
        timeline = builder.build_timeline_for_exception("exc_001", "tenant_001")
        
        triage_events = [e for e in timeline.events if e.stage_name == "triage"]
        assert len(triage_events) > 0
        
        # Should extract evidence IDs from evidence strings
        evidence_ids = triage_events[0].evidence_ids
        assert len(evidence_ids) > 0

    def test_reasoning_excerpt_inclusion(self):
        """Test that reasoning excerpts are included."""
        exception = ExceptionRecord(
            exception_id="exc_001",
            tenant_id="tenant_001",
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "test"},
            normalized_context={},
        )
        
        pipeline_result = {
            "stages": {
                "triage": {
                    "decision": "Classified exception",
                    "natural_language_summary": "Based on similarity analysis, this exception matches known patterns",
                    "reasoning": "RAG similarity score: 0.92, Rule match: invalid_format",
                },
            },
            "context": {},
        }
        
        store = ExceptionStore()
        store.store_exception(exception, pipeline_result)
        
        builder = TimelineBuilder(exception_store=store)
        timeline = builder.build_timeline_for_exception("exc_001", "tenant_001")
        
        triage_events = [e for e in timeline.events if e.stage_name == "triage"]
        assert len(triage_events) > 0
        assert triage_events[0].reasoning_excerpt is not None
        assert "similarity analysis" in triage_events[0].reasoning_excerpt


class TestTimelineExport:
    """Tests for timeline export functionality."""

    def test_export_timeline_markdown(self):
        """Test exporting timeline to Markdown."""
        events = [
            TimelineEvent(
                timestamp=datetime.now(timezone.utc),
                stage_name="intake",
                agent_name="IntakeAgent",
                summary="Normalized exception",
                decision="Normalized exception",
                confidence=1.0,
                next_step="ProceedToTriage",
            ),
            TimelineEvent(
                timestamp=datetime.now(timezone.utc) + timedelta(seconds=5),
                stage_name="triage",
                agent_name="TriageAgent",
                summary="Classified exception",
                decision="Classified as DataQualityFailure",
                confidence=0.85,
                reasoning_excerpt="Based on RAG similarity",
                evidence_ids=["ev_001", "ev_002"],
            ),
        ]
        
        timeline = DecisionTimeline(
            exception_id="exc_001",
            tenant_id="tenant_001",
            events=events,
        )
        
        markdown = export_timeline_markdown(timeline)
        
        assert "# Decision Timeline" in markdown
        assert "exc_001" in markdown
        assert "IntakeAgent" in markdown
        assert "TriageAgent" in markdown
        assert "Classified as DataQualityFailure" in markdown
        assert "ev_001" in markdown
        assert "Based on RAG similarity" in markdown

    def test_write_timeline_to_file(self, tmp_path):
        """Test writing timeline to file."""
        events = [
            TimelineEvent(
                timestamp=datetime.now(timezone.utc),
                stage_name="intake",
                agent_name="IntakeAgent",
                summary="Normalized exception",
            ),
        ]
        
        timeline = DecisionTimeline(
            exception_id="exc_001",
            tenant_id="tenant_001",
            events=events,
        )
        
        output_file = write_timeline_to_file(timeline, output_dir=str(tmp_path))
        
        assert output_file.exists()
        assert output_file.name == "exc_001.md"
        
        # Verify content
        content = output_file.read_text(encoding="utf-8")
        assert "exc_001" in content
        assert "IntakeAgent" in content


class TestTimelineIntegration:
    """Tests for timeline integration functions."""

    def test_build_timeline_for_exception_function(self):
        """Test convenience function for building timelines."""
        exception = ExceptionRecord(
            exception_id="exc_001",
            tenant_id="tenant_001",
            source_system="test_system",
            timestamp=datetime.now(timezone.utc),
            raw_payload={"error": "test"},
            normalized_context={},
        )
        
        pipeline_result = {
            "stages": {
                "intake": {
                    "decision": "Normalized exception",
                    "confidence": 1.0,
                },
            },
            "context": {},
        }
        
        store = ExceptionStore()
        store.store_exception(exception, pipeline_result)
        
        timeline = build_timeline_for_exception("exc_001", "tenant_001", exception_store=store)
        
        assert timeline.exception_id == "exc_001"
        assert len(timeline.events) > 0

