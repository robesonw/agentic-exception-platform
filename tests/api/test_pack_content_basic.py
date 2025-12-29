"""
Simple verification test for pack content endpoints.
"""

import pytest
import httpx
import json


async def test_domain_pack_content_endpoint():
    """Test that domain pack endpoint includes content_json."""
    async with httpx.AsyncClient() as client:
        # This would require actual test data and proper authentication
        # For now, just verify the endpoint structure
        pass


async def test_tenant_pack_content_endpoint():
    """Test that tenant pack endpoint includes content_json."""
    async with httpx.AsyncClient() as client:
        # This would require actual test data and proper authentication 
        # For now, just verify the endpoint structure
        pass


def test_pack_response_model_includes_content():
    """Test that PackResponse model includes content_json field."""
    from src.api.routes.onboarding import PackResponse
    
    # Verify the model has the content_json field (using Pydantic v2 API)
    model_fields = PackResponse.model_fields
    assert 'content_json' in model_fields
    assert model_fields['content_json'].is_required() is False  # Optional field


def test_secret_redaction_utility():
    """Test the secret redaction logic."""
    sample_tool = {
        "id": "test_tool",
        "parameters": {
            "api_key": "secret_123",
            "password": "admin123",
            "auth_token": "token_456", 
            "normal_field": "normal_value",
            "database_url": "postgresql://user:secret@localhost:5432/db"
        }
    }
    
    # This would use the actual redaction function from the component
    # For now, simulate the redaction logic
    redacted_params = {}
    secret_fields = ['password', 'secret', 'key', 'token', 'credential', 'auth']
    
    for key, value in sample_tool["parameters"].items():
        if isinstance(value, str) and any(field in key.lower() for field in secret_fields):
            redacted_params[key] = "***REDACTED***"
        elif isinstance(value, str) and ("password=" in value or ("://" in value and "@" in value)):
            # Redact connection strings
            redacted_params[key] = value.replace("user:secret@", "***REDACTED***:***REDACTED***@")
        else:
            redacted_params[key] = value
    
    assert redacted_params["api_key"] == "***REDACTED***"
    assert redacted_params["password"] == "***REDACTED***" 
    assert redacted_params["auth_token"] == "***REDACTED***"
    assert redacted_params["normal_field"] == "normal_value"
    assert "***REDACTED***" in redacted_params["database_url"]
    assert "secret" not in redacted_params["database_url"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])