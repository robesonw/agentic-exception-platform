"""
Tests for Tools API routes.
Tests tool invocation endpoint.
"""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


class TestToolsAPI:
    """Tests for Tools API endpoints."""

    def test_invoke_tool_endpoint_exists(self):
        """Test that invoke tool endpoint exists."""
        # Endpoint is a TODO in MVP, but should return appropriate response
        response = client.post(
            "/tools/TENANT_001/tool1",
            headers={"X-API-KEY": "test_api_key_tenant_001"},
            json={},
        )
        
        # Should not be 404 (endpoint exists)
        # May be 501 (not implemented) or 400 (validation error)
        assert response.status_code != 404

    def test_tools_endpoint_requires_auth(self):
        """Test that tools endpoint requires authentication."""
        response = client.post("/tools/TENANT_001/tool1", json={})
        
        # Should require authentication
        assert response.status_code == 401

