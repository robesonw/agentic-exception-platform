"""
Unit tests for Phase 12 pack validation service.

Tests:
- PackValidationService.validate_domain_pack
- PackValidationService.validate_tenant_pack
"""

import pytest

from src.infrastructure.repositories.pack_validation_service import (
    PackValidationService,
    ValidationResult,
)
from src.models.domain_pack import DomainPack


def test_validate_domain_pack_valid():
    """Test validating a valid domain pack."""
    service = PackValidationService()
    
    pack_data = {
        "domainName": "Finance",
        "exceptionTypes": {
            "DataQualityFailure": {
                "description": "Data quality issue",
                "detectionRules": ["rule1"],
            }
        },
        "severityRules": [],
        "tools": {
            "retryTool": {
                "description": "Retry tool",
                "endpoint": "http://example.com/retry",
                "parameters": {},
            }
        },
        "playbooks": [
            {
                "exceptionType": "DataQualityFailure",
                "steps": [
                    {
                        "action": "invokeTool('retryTool')",
                        "parameters": {},
                    }
                ],
            }
        ],
        "guardrails": {},
    }
    
    result = service.validate_domain_pack(pack_data)
    
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_domain_pack_missing_required_fields():
    """Test validating domain pack with missing required fields."""
    service = PackValidationService()
    
    pack_data = {
        "domainName": "",
        "exceptionTypes": {},
    }
    
    result = service.validate_domain_pack(pack_data)
    
    assert result.is_valid is False
    assert len(result.errors) > 0
    assert any("domainName" in error.lower() or "exceptionTypes" in error.lower() for error in result.errors)


def test_validate_domain_pack_invalid_playbook_reference():
    """Test validating domain pack with invalid playbook exception type reference."""
    service = PackValidationService()
    
    pack_data = {
        "domainName": "Finance",
        "exceptionTypes": {
            "ValidType": {
                "description": "Valid type",
                "detectionRules": [],
            }
        },
        "severityRules": [],
        "tools": {},
        "playbooks": [
            {
                "exceptionType": "InvalidType",  # Not in exceptionTypes
                "steps": [],
            }
        ],
        "guardrails": {},
    }
    
    result = service.validate_domain_pack(pack_data)
    
    assert result.is_valid is False
    assert any("InvalidType" in error for error in result.errors)


def test_validate_tenant_pack_valid():
    """Test validating a valid tenant pack."""
    service = PackValidationService()
    
    domain_pack = DomainPack.model_validate({
        "domainName": "Finance",
        "exceptionTypes": {
            "DataQualityFailure": {
                "description": "Data quality issue",
                "detectionRules": [],
            }
        },
        "severityRules": [],
        "tools": {
            "retryTool": {
                "description": "Retry tool",
                "endpoint": "http://example.com/retry",
                "parameters": {},
            }
        },
        "playbooks": [],
        "guardrails": {},
    })
    
    tenant_pack_data = {
        "tenantId": "TENANT_001",
        "domainName": "Finance",
        "approvedTools": ["retryTool"],
        "customPlaybooks": [],
        "customSeverityOverrides": [],
    }
    
    result = service.validate_tenant_pack(tenant_pack_data, domain_pack)
    
    assert result.is_valid is True
    assert len(result.errors) == 0


def test_validate_tenant_pack_invalid_tool_reference():
    """Test validating tenant pack with invalid tool reference."""
    service = PackValidationService()
    
    domain_pack = DomainPack.model_validate({
        "domainName": "Finance",
        "exceptionTypes": {},
        "severityRules": [],
        "tools": {
            "validTool": {
                "description": "Valid tool",
                "endpoint": "http://example.com",
                "parameters": {},
            }
        },
        "playbooks": [],
        "guardrails": {},
    })
    
    tenant_pack_data = {
        "tenantId": "TENANT_001",
        "domainName": "Finance",
        "approvedTools": ["invalidTool"],  # Not in domain pack
        "customPlaybooks": [],
        "customSeverityOverrides": [],
    }
    
    result = service.validate_tenant_pack(tenant_pack_data, domain_pack)
    
    assert result.is_valid is False
    assert any("invalidTool" in error for error in result.errors)

