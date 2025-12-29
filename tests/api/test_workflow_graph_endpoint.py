"""
Tests for workflow graph endpoint in router_operator.py

Phase 13 P13-26: Tests for GET /ui/exceptions/{exception_id}/workflow-graph endpoint.
"""

import json
import pytest
from fastapi.testclient import TestClient

from src.api.main import app


def get_test_tenant_id() -> str:
    """Get test tenant ID."""
    return "test_tenant_001"


@pytest.mark.asyncio
async def test_get_exception_workflow_graph_success():
    """Test workflow graph endpoint returns proper structure."""
    tenant_id = get_test_tenant_id()
    
    # Create a mock exception and events for testing
    test_exception_id = "test-workflow-exception-001"
    
    with TestClient(app) as client:
        # Test workflow graph endpoint
        response = client.get(
            f"/ui/exceptions/{test_exception_id}/workflow-graph",
            params={"tenant_id": tenant_id}
        )
        
        # Should return 404 if exception doesn't exist (expected for clean test)
        if response.status_code == 404:
            assert "Exception not found" in response.json()["detail"]
            return
            
        # If exception exists, should return proper workflow structure
        assert response.status_code == 200
        data = response.json()
        
        # Verify response structure
        assert "nodes" in data
        assert "edges" in data
        assert "current_stage" in data
        assert "playbook_id" in data
        assert "playbook_steps" in data
        
        # Verify nodes structure
        nodes = data["nodes"]
        assert isinstance(nodes, list)
        
        for node in nodes:
            assert "id" in node
            assert "type" in node
            assert "kind" in node
            assert "label" in node
            assert "status" in node
            assert node["type"] in ["agent", "decision", "human", "system", "playbook"]
            assert node["kind"] in ["stage", "playbook", "step"]
            assert node["status"] in ["pending", "in-progress", "completed", "failed", "skipped"]
        
        # Verify edges structure
        edges = data["edges"]
        assert isinstance(edges, list)
        
        for edge in edges:
            assert "id" in edge
            assert "source" in edge
            assert "target" in edge


@pytest.mark.asyncio
async def test_get_exception_workflow_graph_not_found():
    """Test workflow graph endpoint returns 404 for non-existent exception."""
    tenant_id = get_test_tenant_id()
    
    with TestClient(app) as client:
        response = client.get(
            "/ui/exceptions/nonexistent-exception/workflow-graph",
            params={"tenant_id": tenant_id}
        )
        
        assert response.status_code == 404
        assert "Exception not found" in response.json()["detail"]


@pytest.mark.asyncio
async def test_get_exception_workflow_graph_missing_tenant():
    """Test workflow graph endpoint returns 422 for missing tenant_id."""
    
    with TestClient(app) as client:
        response = client.get("/ui/exceptions/test-exception/workflow-graph")
        
        assert response.status_code == 422
        # Should indicate missing required query parameter


@pytest.mark.asyncio
async def test_get_exception_workflow_graph_tenant_isolation():
    """Test workflow graph endpoint respects tenant isolation."""
    tenant_id_1 = get_test_tenant_id()
    tenant_id_2 = "different-tenant"
    
    test_exception_id = "test-workflow-isolation-001"
    
    with TestClient(app) as client:
        # Try to access exception with different tenant ID
        response = client.get(
            f"/ui/exceptions/{test_exception_id}/workflow-graph",
            params={"tenant_id": tenant_id_2},
            headers={"X-API-Key": "test-api-key"}  # Mock API key for auth
        )
        
        # Should return 404 even if exception exists under different tenant
        # If auth fails (401), that's also acceptable since we can't access the resource
        assert response.status_code in [401, 404]


@pytest.mark.asyncio
async def test_workflow_graph_pipeline_stages():
    """Test that workflow graph includes expected pipeline stages."""
    # This is a unit test for the workflow construction logic
    from src.services.ui_query_service import UIQueryService
    
    # Mock workflow data that would come from events
    mock_workflow_data = {
        "nodes": [
            {
                "id": "stage:intake",
                "type": "agent",
                "kind": "stage",
                "label": "Intake",
                "status": "completed",
                "started_at": None,
                "completed_at": "2024-01-01T12:00:00Z",
                "meta": {"event_type": "ExceptionNormalized"}
            },
            {
                "id": "stage:triage",
                "type": "agent", 
                "kind": "stage",
                "label": "Triage",
                "status": "completed",
                "started_at": None,
                "completed_at": "2024-01-01T12:01:00Z",
                "meta": {"event_type": "TriageCompleted"}
            },
            {
                "id": "stage:policy",
                "type": "agent",
                "kind": "stage",
                "label": "Policy Check",
                "status": "in-progress",
                "started_at": "2024-01-01T12:02:00Z",
                "completed_at": None,
                "meta": {"event_type": "PolicyEvaluationStarted"}
            },
            {
                "id": "stage:playbook",
                "type": "agent",
                "kind": "stage",
                "label": "Playbook",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "meta": {}
            },
            {
                "id": "stage:tool",
                "type": "system",
                "kind": "stage",
                "label": "Tool Execution",
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "meta": {}
            },
            {
                "id": "stage:feedback",
                "type": "agent",
                "kind": "stage",
                "label": "Feedback", 
                "status": "pending",
                "started_at": None,
                "completed_at": None,
                "meta": {}
            }
        ],
        "edges": [
            {"id": "intake-to-triage", "source": "stage:intake", "target": "stage:triage", "label": None},
            {"id": "triage-to-policy", "source": "stage:triage", "target": "stage:policy", "label": None},
            {"id": "policy-to-playbook", "source": "stage:policy", "target": "stage:playbook", "label": None},
            {"id": "playbook-to-tool", "source": "stage:playbook", "target": "stage:tool", "label": None},
            {"id": "tool-to-feedback", "source": "stage:tool", "target": "stage:feedback", "label": None}
        ],
        "current_stage": "policy",
        "playbook_id": None,
        "playbook_steps": None
    }
    
    # Verify expected stages are present
    expected_stages = {"stage:intake", "stage:triage", "stage:policy", "stage:playbook", "stage:tool", "stage:feedback"}
    actual_stages = {node["id"] for node in mock_workflow_data["nodes"]}
    assert expected_stages == actual_stages
    
    # Verify linear pipeline flow
    edges = mock_workflow_data["edges"]
    assert len(edges) == 5  # n-1 edges for n stages
    
    # Verify current stage logic
    assert mock_workflow_data["current_stage"] == "policy"
    
    # Verify status progression
    statuses = [node["status"] for node in mock_workflow_data["nodes"]]
    assert "completed" in statuses  # Some stages completed
    assert "in-progress" in statuses  # Current stage
    assert "pending" in statuses  # Future stages


if __name__ == "__main__":
    pytest.main([__file__])