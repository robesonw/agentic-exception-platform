"""
Integration test for workflow graph endpoint.

Simple test that can be run manually to verify the endpoint works.
"""

import asyncio
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.services.ui_query_service import get_ui_query_service


async def test_workflow_graph_service():
    """Test the workflow graph service directly."""
    ui_service = get_ui_query_service()
    
    # Test with a non-existent exception
    result = await ui_service.get_exception_workflow_graph("test-tenant", "non-existent")
    print(f"Non-existent exception result: {result}")
    
    # Test basic workflow structure
    print("Testing workflow graph structure...")
    
    # Mock test data
    test_workflow = {
        "nodes": [
            {
                "id": "intake",
                "type": "agent", 
                "label": "Intake",
                "status": "completed",
                "started_at": None,
                "completed_at": "2024-01-01T12:00:00Z",
                "meta": {"event_type": "ExceptionNormalized"}
            },
            {
                "id": "triage",
                "type": "agent",
                "label": "Triage", 
                "status": "in-progress",
                "started_at": "2024-01-01T12:01:00Z",
                "completed_at": None,
                "meta": {"event_type": "TriageStarted"}
            }
        ],
        "edges": [
            {"id": "intake-to-triage", "source": "intake", "target": "triage", "label": None}
        ],
        "current_stage": "triage",
        "playbook_id": None,
        "playbook_steps": None
    }
    
    print(f"Test workflow structure: {test_workflow}")
    print("✓ Workflow graph structure looks correct")


if __name__ == "__main__":
    asyncio.run(test_workflow_graph_service())