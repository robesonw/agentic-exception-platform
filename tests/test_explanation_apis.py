"""
Tests for Explanation API Endpoints (P3-30).

Tests explanation retrieval, search, timeline, and evidence endpoints.
"""

import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient

from src.api.main import app
from src.explainability.evidence import EvidenceType, record_evidence_item
from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.store import ExceptionStore, get_exception_store


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_exception():
    """Create a sample exception record."""
    return ExceptionRecord(
        exception_id="exc_001",
        tenant_id="tenant_001",
        exception_type="DataQualityFailure",
        severity=Severity.HIGH,
        resolution_status=ResolutionStatus.OPEN,
        source_system="test_system",
        timestamp=datetime.now(timezone.utc),
        raw_payload={"error": "test error"},
        normalized_context={"domain": "TestDomain"},
    )


@pytest.fixture
def sample_pipeline_result():
    """Create a sample pipeline result."""
    return {
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
            "policy": {
                "decision": "ALLOW",
                "confidence": 0.9,
                "nextStep": "ProceedToResolution",
                "evidence": ["Playbook approved", "Guardrails passed"],
            },
        },
        "context": {
            "evidence": [],
        },
    }


@pytest.fixture
def setup_exception_store(sample_exception, sample_pipeline_result):
    """Set up exception store with sample data."""
    store = get_exception_store()
    store.store_exception(sample_exception, sample_pipeline_result)
    yield store
    store.clear_all()


@pytest.fixture
def setup_evidence(sample_exception):
    """Set up evidence for sample exception."""
    # Record some evidence items
    record_evidence_item(
        evidence_type=EvidenceType.RAG,
        source_id="doc_001",
        description="Similar exception found",
        tenant_id=sample_exception.tenant_id,
        exception_id=sample_exception.exception_id,
        similarity_score=0.92,
    )
    
    record_evidence_item(
        evidence_type=EvidenceType.TOOL,
        source_id="tool_001",
        description="Tool execution result",
        tenant_id=sample_exception.tenant_id,
        exception_id=sample_exception.exception_id,
    )


class TestGetExplanation:
    """Tests for GET /explanations/{exception_id} endpoint."""

    def test_get_explanation_json_format(self, client, setup_exception_store):
        """Test getting explanation in JSON format."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "json"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exceptionId"] == "exc_001"
        assert data["format"] == "json"
        assert "explanation" in data
        assert "timeline" in data["explanation"]
        assert "evidence_items" in data["explanation"]
        assert "agent_decisions" in data["explanation"]
        assert "version" in data

    def test_get_explanation_text_format(self, client, setup_exception_store):
        """Test getting explanation in text format."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "text"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exceptionId"] == "exc_001"
        assert data["format"] == "text"
        assert isinstance(data["explanation"], str)
        assert "Exception exc_001" in data["explanation"]
        assert "Decision Timeline" in data["explanation"]

    def test_get_explanation_structured_format(self, client, setup_exception_store):
        """Test getting explanation in structured format."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "structured"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exceptionId"] == "exc_001"
        assert data["format"] == "structured"
        assert "explanation" in data
        explanation = data["explanation"]
        assert "exception" in explanation
        assert "timeline" in explanation
        assert "evidence" in explanation
        assert "decisions" in explanation

    def test_get_explanation_invalid_format(self, client, setup_exception_store):
        """Test getting explanation with invalid format."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "invalid"},
        )
        
        assert response.status_code == 400
        assert "Invalid format" in response.json()["detail"]

    def test_get_explanation_not_found(self, client):
        """Test getting explanation for non-existent exception."""
        response = client.get(
            "/explanations/nonexistent",
            params={"tenant_id": "tenant_001", "format": "json"},
        )
        
        assert response.status_code == 404


class TestSearchExplanations:
    """Tests for GET /explanations/search endpoint."""

    def test_search_explanations_basic(self, client, setup_exception_store):
        """Test basic explanation search."""
        response = client.get(
            "/explanations/search",
            params={"tenant_id": "tenant_001"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert "items" in data
        assert "total" in data
        assert "page" in data
        assert "pageSize" in data
        assert "totalPages" in data
        assert isinstance(data["items"], list)

    def test_search_explanations_by_agent(self, client, setup_exception_store):
        """Test searching explanations by agent name."""
        response = client.get(
            "/explanations/search",
            params={"tenant_id": "tenant_001", "agent_name": "TriageAgent"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All results should be from TriageAgent
        for item in data["items"]:
            assert item["agentName"] == "TriageAgent"

    def test_search_explanations_by_decision_type(self, client, setup_exception_store):
        """Test searching explanations by decision type."""
        response = client.get(
            "/explanations/search",
            params={"tenant_id": "tenant_001", "decision_type": "ALLOW"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All results should contain "ALLOW" in decision type
        for item in data["items"]:
            if item["decisionType"]:
                assert "ALLOW" in item["decisionType"].upper()

    def test_search_explanations_by_text(self, client, setup_exception_store):
        """Test searching explanations by text."""
        response = client.get(
            "/explanations/search",
            params={"tenant_id": "tenant_001", "text": "DataQuality"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Results should contain "DataQuality" in searchable text
        assert len(data["items"]) > 0

    def test_search_explanations_pagination(self, client, setup_exception_store):
        """Test explanation search pagination."""
        response = client.get(
            "/explanations/search",
            params={"tenant_id": "tenant_001", "page": 1, "page_size": 10},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["page"] == 1
        assert data["pageSize"] == 10
        assert len(data["items"]) <= 10

    def test_search_explanations_timestamp_filter(self, client, setup_exception_store):
        """Test searching explanations with timestamp filters."""
        from_ts = datetime.now(timezone.utc) - timedelta(days=1)
        to_ts = datetime.now(timezone.utc) + timedelta(days=1)
        
        response = client.get(
            "/explanations/search",
            params={
                "tenant_id": "tenant_001",
                "from_ts": from_ts.isoformat(),
                "to_ts": to_ts.isoformat(),
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # All results should be within timestamp range
        for item in data["items"]:
            item_ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            assert from_ts <= item_ts <= to_ts


class TestGetTimeline:
    """Tests for GET /explanations/{exception_id}/timeline endpoint."""

    def test_get_timeline(self, client, setup_exception_store):
        """Test getting decision timeline."""
        response = client.get(
            "/explanations/exc_001/timeline",
            params={"tenant_id": "tenant_001"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exceptionId"] == "exc_001"
        assert "events" in data
        assert isinstance(data["events"], list)
        
        # Verify event structure
        if data["events"]:
            event = data["events"][0]
            assert "timestamp" in event
            assert "stage_name" in event
            assert "agent_name" in event
            assert "summary" in event

    def test_get_timeline_not_found(self, client):
        """Test getting timeline for non-existent exception."""
        response = client.get(
            "/explanations/nonexistent/timeline",
            params={"tenant_id": "tenant_001"},
        )
        
        assert response.status_code == 404


class TestGetEvidence:
    """Tests for GET /explanations/{exception_id}/evidence endpoint."""

    def test_get_evidence(self, client, setup_exception_store, setup_evidence):
        """Test getting evidence graph."""
        response = client.get(
            "/explanations/exc_001/evidence",
            params={"tenant_id": "tenant_001"},
        )
        
        assert response.status_code == 200
        data = response.json()
        
        assert data["exception_id"] == "exc_001"
        assert "evidence_items" in data
        assert "evidence_links" in data
        assert "graph" in data
        
        # Verify graph structure
        graph = data["graph"]
        assert "nodes" in graph
        assert "edges" in graph
        assert isinstance(graph["nodes"], list)
        assert isinstance(graph["edges"], list)
        
        # Verify evidence items structure
        if data["evidence_items"]:
            item = data["evidence_items"][0]
            assert "id" in item
            assert "type" in item
            assert "description" in item

    def test_get_evidence_not_found(self, client):
        """Test getting evidence for non-existent exception."""
        response = client.get(
            "/explanations/nonexistent/evidence",
            params={"tenant_id": "tenant_001"},
        )
        
        assert response.status_code == 404


class TestExplanationFormats:
    """Tests for different explanation formats."""

    def test_json_format_structure(self, client, setup_exception_store):
        """Test JSON format has correct structure."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "json"},
        )
        
        assert response.status_code == 200
        explanation = response.json()["explanation"]
        
        assert "exception_id" in explanation
        assert "timeline" in explanation
        assert "evidence_items" in explanation
        assert "agent_decisions" in explanation

    def test_text_format_content(self, client, setup_exception_store):
        """Test text format has expected content."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "text"},
        )
        
        assert response.status_code == 200
        explanation = response.json()["explanation"]
        
        assert isinstance(explanation, str)
        assert "Exception exc_001" in explanation
        assert "Decision Timeline" in explanation

    def test_structured_format_grouping(self, client, setup_exception_store, setup_evidence):
        """Test structured format groups evidence correctly."""
        response = client.get(
            "/explanations/exc_001",
            params={"tenant_id": "tenant_001", "format": "structured"},
        )
        
        assert response.status_code == 200
        explanation = response.json()["explanation"]
        
        assert "evidence" in explanation
        evidence = explanation["evidence"]
        assert "by_type" in evidence
        assert "links_by_agent" in evidence

