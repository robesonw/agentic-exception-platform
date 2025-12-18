"""
Tests for PII redaction service (P9-24).

Tests verify:
- PII fields are redacted at ingestion
- Tenant-configurable PII fields
- Redaction metadata is stored
- Secrets never logged
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch

from src.security.pii_redaction import PIIRedactionService, PIIRedactionError


class TestPIIRedactionService:
    """Tests for PIIRedactionService."""

    @pytest.fixture
    def default_service(self):
        """Create PIIRedactionService with default configuration."""
        return PIIRedactionService()

    @pytest.fixture
    def custom_service(self):
        """Create PIIRedactionService with custom tenant configuration."""
        return PIIRedactionService(
            default_pii_fields=["email", "phone", "ssn"],
            tenant_pii_fields={
                "TENANT_001": ["custom_field", "internal_id"],
                "TENANT_002": ["patient_id", "medical_record"],
            },
        )

    def test_redact_email(self, default_service):
        """Test that email addresses are redacted."""
        data = {
            "error": "Test error",
            "email": "user@example.com",
            "message": "Something went wrong",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["email"] == "[REDACTED]"
        assert redacted["error"] == "Test error"  # Not redacted
        assert "email" in metadata["redacted_fields"]
        assert metadata["redaction_count"] == 1

    def test_redact_phone(self, default_service):
        """Test that phone numbers are redacted."""
        data = {
            "error": "Test error",
            "phone": "555-1234",
            "phone_number": "555-5678",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["phone"] == "[REDACTED]"
        assert redacted["phone_number"] == "[REDACTED]"
        assert metadata["redaction_count"] == 2

    def test_redact_ssn(self, default_service):
        """Test that SSN is redacted."""
        data = {
            "error": "Test error",
            "ssn": "123-45-6789",
            "social_security_number": "987-65-4321",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["ssn"] == "[REDACTED]"
        assert redacted["social_security_number"] == "[REDACTED]"
        assert metadata["redaction_count"] == 2

    def test_redact_nested_fields(self, default_service):
        """Test that nested PII fields are redacted."""
        data = {
            "error": "Test error",
            "user": {
                "name": "John Doe",
                "email": "john@example.com",
                "address": {
                    "street": "123 Main St",
                    "city": "Anytown",
                },
            },
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["user"]["email"] == "[REDACTED]"
        assert redacted["user"]["address"]["street"] == "[REDACTED]"
        assert "user.email" in metadata["redacted_fields"]
        assert "user.address.street" in metadata["redacted_fields"]
        assert metadata["redaction_count"] >= 2

    def test_tenant_custom_pii_fields(self, custom_service):
        """Test that tenant-specific PII fields are redacted."""
        data = {
            "error": "Test error",
            "custom_field": "sensitive_value",
            "internal_id": "12345",
        }
        
        # TENANT_001 has custom_field and internal_id in PII fields
        redacted, metadata = custom_service.redact_pii(data, "TENANT_001")
        
        assert redacted["custom_field"] == "[REDACTED]"
        assert redacted["internal_id"] == "[REDACTED]"
        assert metadata["redaction_count"] == 2
        
        # TENANT_002 doesn't have these fields, but has patient_id
        data2 = {
            "error": "Test error",
            "custom_field": "not_redacted",
            "patient_id": "P12345",
        }
        
        redacted2, metadata2 = custom_service.redact_pii(data2, "TENANT_002")
        
        assert redacted2["custom_field"] == "not_redacted"  # Not in TENANT_002's PII fields
        assert redacted2["patient_id"] == "[REDACTED"]  # In TENANT_002's PII fields

    def test_redaction_metadata_structure(self, default_service):
        """Test that redaction metadata has correct structure."""
        data = {
            "email": "user@example.com",
            "phone": "555-1234",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert "redacted_fields" in metadata
        assert "redaction_count" in metadata
        assert "tenant_id" in metadata
        assert "redaction_placeholder" in metadata
        assert metadata["tenant_id"] == "TENANT_001"
        assert metadata["redaction_placeholder"] == "[REDACTED]"
        assert isinstance(metadata["redacted_fields"], list)
        assert metadata["redaction_count"] == len(metadata["redacted_fields"])

    def test_no_pii_no_redaction(self, default_service):
        """Test that data without PII is not redacted."""
        data = {
            "error": "Test error",
            "message": "Something went wrong",
            "status": "failed",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted == data  # No changes
        assert metadata["redaction_count"] == 0
        assert len(metadata["redacted_fields"]) == 0

    def test_ensure_secrets_never_logged(self, default_service):
        """Test that secrets are redacted for logging."""
        data = {
            "error": "Test error",
            "api_key": "secret_key_12345",
            "password": "mypassword",
            "token": "bearer_token_abc123",
        }
        
        redacted = default_service.ensure_secrets_never_logged(data, "TENANT_001")
        
        # Secrets should be redacted
        assert redacted["api_key"] == "[REDACTED]"
        assert redacted["password"] == "[REDACTED]"
        assert redacted["token"] == "[REDACTED]"
        # Non-secret fields should remain
        assert redacted["error"] == "Test error"

    def test_redact_list_items(self, default_service):
        """Test that PII in list items is redacted."""
        data = {
            "users": [
                {"name": "John", "email": "john@example.com"},
                {"name": "Jane", "email": "jane@example.com"},
            ],
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["users"][0]["email"] == "[REDACTED]"
        assert redacted["users"][1]["email"] == "[REDACTED]"
        assert "users[0].email" in metadata["redacted_fields"]
        assert "users[1].email" in metadata["redacted_fields"]

    def test_custom_redaction_placeholder(self):
        """Test that custom redaction placeholder is used."""
        service = PIIRedactionService(redaction_placeholder="***REDACTED***")
        
        data = {"email": "user@example.com"}
        
        redacted, metadata = service.redact_pii(data, "TENANT_001")
        
        assert redacted["email"] == "***REDACTED***"
        assert metadata["redaction_placeholder"] == "***REDACTED***"

    def test_redact_credit_card(self, default_service):
        """Test that credit card numbers are redacted."""
        data = {
            "error": "Test error",
            "credit_card": "4111-1111-1111-1111",
            "card_number": "5555-5555-5555-5555",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["credit_card"] == "[REDACTED]"
        assert redacted["card_number"] == "[REDACTED]"
        assert metadata["redaction_count"] == 2

    def test_redact_address_fields(self, default_service):
        """Test that address fields are redacted."""
        data = {
            "error": "Test error",
            "address": "123 Main St",
            "street": "456 Oak Ave",
            "zip_code": "12345",
        }
        
        redacted, metadata = default_service.redact_pii(data, "TENANT_001")
        
        assert redacted["address"] == "[REDACTED]"
        assert redacted["street"] == "[REDACTED]"
        assert redacted["zip_code"] == "[REDACTED]"
        assert metadata["redaction_count"] == 3



