"""
Tests for Evidence Tracking and Attribution (P3-29).

Tests evidence item recording, linking, and retrieval.
"""

import json
import pytest
from datetime import datetime, timezone
from pathlib import Path

from src.explainability.evidence import (
    EvidenceInfluence,
    EvidenceItem,
    EvidenceLink,
    EvidenceTracker,
    EvidenceType,
    get_evidence_for_exception,
    get_evidence_links_for_exception,
    link_evidence_to_decision,
    record_evidence_item,
)
from src.explainability.evidence_integration import (
    record_policy_evidence,
    record_rag_evidence,
    record_tool_evidence,
)


class TestEvidenceItem:
    """Tests for EvidenceItem model."""

    def test_evidence_item_creation(self):
        """Test creating an evidence item."""
        evidence = EvidenceItem(
            type=EvidenceType.RAG,
            source_id="doc_001",
            description="Similar exception found",
            similarity_score=0.92,
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        assert evidence.type == EvidenceType.RAG
        assert evidence.source_id == "doc_001"
        assert evidence.similarity_score == 0.92
        assert evidence.tenant_id == "tenant_001"
        assert evidence.exception_id == "exc_001"


class TestEvidenceLink:
    """Tests for EvidenceLink model."""

    def test_evidence_link_creation(self):
        """Test creating an evidence link."""
        link = EvidenceLink(
            exception_id="exc_001",
            agent_name="TriageAgent",
            stage_name="triage",
            evidence_id="ev_001",
            influence=EvidenceInfluence.SUPPORT,
        )
        
        assert link.exception_id == "exc_001"
        assert link.agent_name == "TriageAgent"
        assert link.evidence_id == "ev_001"
        assert link.influence == EvidenceInfluence.SUPPORT


class TestEvidenceTracker:
    """Tests for EvidenceTracker."""

    def test_record_evidence_item(self, tmp_path):
        """Test recording an evidence item."""
        tracker = EvidenceTracker(storage_dir=str(tmp_path))
        
        evidence = tracker.record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_001",
            description="Similar exception found",
            tenant_id="tenant_001",
            exception_id="exc_001",
            similarity_score=0.92,
        )
        
        assert evidence.type == EvidenceType.RAG
        assert evidence.source_id == "doc_001"
        assert evidence.similarity_score == 0.92
        
        # Verify persistence
        evidence_file = tmp_path / "tenant_001_exc_001_evidence.jsonl"
        assert evidence_file.exists()

    def test_link_evidence_to_decision(self, tmp_path):
        """Test linking evidence to a decision."""
        tracker = EvidenceTracker(storage_dir=str(tmp_path))
        
        # First record evidence
        evidence = tracker.record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_001",
            description="Similar exception found",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        # Then link it
        link = tracker.link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="TriageAgent",
            stage_name="triage",
            evidence_id=evidence.id,
            influence=EvidenceInfluence.SUPPORT,
        )
        
        assert link.evidence_id == evidence.id
        assert link.agent_name == "TriageAgent"
        assert link.influence == EvidenceInfluence.SUPPORT

    def test_get_evidence_for_exception(self, tmp_path):
        """Test retrieving evidence for an exception."""
        tracker = EvidenceTracker(storage_dir=str(tmp_path))
        
        # Record multiple evidence items
        ev1 = tracker.record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_001",
            description="RAG result 1",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        ev2 = tracker.record_evidence_item(
            evidence_type=EvidenceType.TOOL,
            source_id="tool_001",
            description="Tool execution result",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        ev3 = tracker.record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_002",
            description="RAG result 2",
            tenant_id="tenant_001",
            exception_id="exc_002",  # Different exception
        )
        
        # Get evidence for exc_001
        evidence_items = tracker.get_evidence_for_exception("exc_001", "tenant_001")
        
        assert len(evidence_items) == 2
        assert ev1.id in [e.id for e in evidence_items]
        assert ev2.id in [e.id for e in evidence_items]
        assert ev3.id not in [e.id for e in evidence_items]

    def test_get_evidence_links_for_exception(self, tmp_path):
        """Test retrieving evidence links for an exception."""
        tracker = EvidenceTracker(storage_dir=str(tmp_path))
        
        # Record evidence and create links
        evidence = tracker.record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_001",
            description="RAG result",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        link1 = tracker.link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="TriageAgent",
            stage_name="triage",
            evidence_id=evidence.id,
        )
        
        link2 = tracker.link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="PolicyAgent",
            stage_name="policy",
            evidence_id=evidence.id,
        )
        
        # Get links for exc_001
        links = tracker.get_evidence_links_for_exception("exc_001")
        
        assert len(links) == 2
        assert link1.id in [l.id for l in links]
        assert link2.id in [l.id for l in links]
        
        # Get links for specific stage
        triage_links = tracker.get_evidence_links_for_exception("exc_001", stage_name="triage")
        assert len(triage_links) == 1
        assert triage_links[0].stage_name == "triage"


class TestEvidenceIntegration:
    """Tests for evidence integration functions."""

    def test_record_rag_evidence(self, tmp_path):
        """Test recording RAG evidence."""
        # Create mock search results
        from dataclasses import dataclass
        
        @dataclass
        class MockEntry:
            exception_id: str
            resolution_summary: str
        
        search_results = [
            (MockEntry("exc_prev_001", "Resolved by retry"), 0.92),
            (MockEntry("exc_prev_002", "Resolved by manual fix"), 0.85),
        ]
        
        evidence_ids = record_rag_evidence(
            exception_id="exc_001",
            tenant_id="tenant_001",
            search_results=search_results,
            agent_name="TriageAgent",
            stage_name="triage",
        )
        
        assert len(evidence_ids) == 2
        
        # Verify evidence items were created
        evidence_items = get_evidence_for_exception("exc_001", "tenant_001")
        rag_evidence = [e for e in evidence_items if e.type == EvidenceType.RAG]
        assert len(rag_evidence) == 2
        assert all(e.similarity_score is not None for e in rag_evidence)
        
        # Verify links were created
        links = get_evidence_links_for_exception("exc_001", stage_name="triage")
        assert len(links) == 2

    def test_record_tool_evidence(self, tmp_path):
        """Test recording tool evidence."""
        tool_result = {
            "status": "success",
            "http_status": 200,
            "response": {"result": "Operation completed"},
        }
        
        evidence_id = record_tool_evidence(
            exception_id="exc_001",
            tenant_id="tenant_001",
            tool_name="test_tool",
            tool_result=tool_result,
            agent_name="ResolutionAgent",
            stage_name="resolution",
        )
        
        assert evidence_id != ""
        
        # Verify evidence item was created
        evidence_items = get_evidence_for_exception("exc_001", "tenant_001")
        tool_evidence = [e for e in evidence_items if e.type == EvidenceType.TOOL]
        assert len(tool_evidence) == 1
        assert tool_evidence[0].source_id == "test_tool"
        
        # Verify link was created
        links = get_evidence_links_for_exception("exc_001", stage_name="resolution")
        assert len(links) == 1
        assert links[0].influence == EvidenceInfluence.SUPPORT  # Success = support

    def test_record_tool_evidence_failure(self, tmp_path):
        """Test recording tool evidence for failed execution."""
        tool_result = {
            "status": "failure",
            "http_status": 500,
            "response": {"error": "Internal server error"},
        }
        
        evidence_id = record_tool_evidence(
            exception_id="exc_001",
            tenant_id="tenant_001",
            tool_name="test_tool",
            tool_result=tool_result,
        )
        
        # Verify link has contradict influence for failure
        links = get_evidence_links_for_exception("exc_001")
        tool_links = [l for l in links if l.evidence_id == evidence_id]
        assert len(tool_links) == 1
        assert tool_links[0].influence == EvidenceInfluence.CONTRADICT  # Failure = contradict

    def test_record_policy_evidence(self, tmp_path):
        """Test recording policy evidence."""
        evidence_id = record_policy_evidence(
            exception_id="exc_001",
            tenant_id="tenant_001",
            rule_id="rule_001",
            rule_description="Human approval required for CRITICAL severity",
            applied=True,
            agent_name="PolicyAgent",
            stage_name="policy",
        )
        
        assert evidence_id != ""
        
        # Verify evidence item was created
        evidence_items = get_evidence_for_exception("exc_001", "tenant_001")
        policy_evidence = [e for e in evidence_items if e.type == EvidenceType.POLICY]
        assert len(policy_evidence) == 1
        assert policy_evidence[0].source_id == "rule_001"
        assert "CRITICAL" in policy_evidence[0].description
        
        # Verify link was created with SUPPORT influence (applied=True)
        links = get_evidence_links_for_exception("exc_001", stage_name="policy")
        assert len(links) == 1
        assert links[0].influence == EvidenceInfluence.SUPPORT

    def test_record_policy_evidence_violation(self, tmp_path):
        """Test recording policy evidence for violated rules."""
        evidence_id = record_policy_evidence(
            exception_id="exc_001",
            tenant_id="tenant_001",
            rule_id="rule_002",
            rule_description="No approved playbook available",
            applied=False,  # Violated
            agent_name="PolicyAgent",
            stage_name="policy",
        )
        
        # Verify link has CONTRADICT influence (applied=False)
        links = get_evidence_links_for_exception("exc_001", stage_name="policy")
        violation_links = [l for l in links if l.evidence_id == evidence_id]
        assert len(violation_links) == 1
        assert violation_links[0].influence == EvidenceInfluence.CONTRADICT

    def test_evidence_influence_types(self, tmp_path):
        """Test that influence types are respected."""
        tracker = EvidenceTracker(storage_dir=str(tmp_path))
        
        # Record evidence
        evidence = tracker.record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_001",
            description="RAG result",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        # Create links with different influence types
        link_support = tracker.link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="TriageAgent",
            stage_name="triage",
            evidence_id=evidence.id,
            influence=EvidenceInfluence.SUPPORT,
        )
        
        link_contradict = tracker.link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="PolicyAgent",
            stage_name="policy",
            evidence_id=evidence.id,
            influence=EvidenceInfluence.CONTRADICT,
        )
        
        link_contextual = tracker.link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="SupervisorAgent",
            stage_name="supervisor",
            evidence_id=evidence.id,
            influence=EvidenceInfluence.CONTEXTUAL,
        )
        
        # Verify influence types are preserved
        links = tracker.get_evidence_links_for_exception("exc_001")
        assert len(links) == 3
        
        support_links = [l for l in links if l.influence == EvidenceInfluence.SUPPORT]
        contradict_links = [l for l in links if l.influence == EvidenceInfluence.CONTRADICT]
        contextual_links = [l for l in links if l.influence == EvidenceInfluence.CONTEXTUAL]
        
        assert len(support_links) == 1
        assert len(contradict_links) == 1
        assert len(contextual_links) == 1


class TestEvidenceRetrieval:
    """Tests for evidence retrieval functions."""

    def test_get_evidence_for_exception_function(self, tmp_path):
        """Test convenience function for getting evidence."""
        # Record evidence
        record_evidence_item(
            evidence_type=EvidenceType.RAG,
            source_id="doc_001",
            description="RAG result",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        # Retrieve evidence
        evidence_items = get_evidence_for_exception("exc_001", "tenant_001")
        
        assert len(evidence_items) == 1
        assert evidence_items[0].type == EvidenceType.RAG

    def test_get_evidence_links_for_exception_function(self, tmp_path):
        """Test convenience function for getting evidence links."""
        # Record evidence and link
        evidence = record_evidence_item(
            evidence_type=EvidenceType.TOOL,
            source_id="tool_001",
            description="Tool result",
            tenant_id="tenant_001",
            exception_id="exc_001",
        )
        
        link_evidence_to_decision(
            exception_id="exc_001",
            agent_name="ResolutionAgent",
            stage_name="resolution",
            evidence_id=evidence.id,
        )
        
        # Retrieve links
        links = get_evidence_links_for_exception("exc_001")
        
        assert len(links) == 1
        assert links[0].agent_name == "ResolutionAgent"

