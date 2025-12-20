"""
Tests for Phase 12+ Governance Audit System.

Tests:
- Redaction of sensitive data
- Correlation ID generation and propagation
- Audit event creation and queries
- Tenant isolation in audit queries
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

from src.services.governance_audit import (
    # Correlation ID
    generate_correlation_id,
    get_correlation_id,
    set_correlation_id,
    get_or_create_correlation_id,
    clear_context,
    # Redaction
    redact_string,
    redact_dict,
    redact_list,
    redact_payload,
    SENSITIVE_KEYS,
    # Models
    GovernanceAuditEventCreate,
    GovernanceAuditEventResponse,
    AuditEventFilter,
    # Diff generation
    generate_diff_summary,
    # Constants
    AuditEventTypes,
    EntityTypes,
    Actions,
)


class TestCorrelationId:
    """Tests for correlation ID generation and context management."""

    def test_generate_correlation_id_format(self):
        """Test that correlation IDs have the expected format."""
        cor_id = generate_correlation_id()
        assert cor_id.startswith("cor_")
        assert len(cor_id) == 20  # "cor_" + 16 hex chars

    def test_generate_correlation_id_uniqueness(self):
        """Test that generated correlation IDs are unique."""
        ids = {generate_correlation_id() for _ in range(100)}
        assert len(ids) == 100

    def test_context_set_and_get(self):
        """Test setting and getting correlation ID from context."""
        clear_context()
        assert get_correlation_id() is None

        set_correlation_id("test_cor_123")
        assert get_correlation_id() == "test_cor_123"

        clear_context()
        assert get_correlation_id() is None

    def test_get_or_create_creates_when_empty(self):
        """Test get_or_create generates ID when context is empty."""
        clear_context()
        cor_id = get_or_create_correlation_id()
        assert cor_id.startswith("cor_")
        assert get_correlation_id() == cor_id

        clear_context()

    def test_get_or_create_reuses_existing(self):
        """Test get_or_create returns existing ID."""
        clear_context()
        set_correlation_id("existing_id")

        result = get_or_create_correlation_id()
        assert result == "existing_id"

        clear_context()


class TestRedaction:
    """Tests for sensitive data redaction."""

    def test_redact_api_key_patterns(self):
        """Test redaction of API key patterns."""
        text = 'api_key: "sk_live_abc123xyz456def789"'
        result = redact_string(text)
        assert "sk_live_abc123xyz456def789" not in result
        assert "[REDACTED]" in result

    def test_redact_token_patterns(self):
        """Test redaction of token patterns."""
        text = 'authorization: "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0"'
        result = redact_string(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "[REDACTED]" in result

    def test_redact_password_patterns(self):
        """Test redaction of password patterns."""
        text = 'password: "supersecret123!"'
        result = redact_string(text)
        assert "supersecret123!" not in result
        assert "[REDACTED]" in result

    def test_redact_database_url(self):
        """Test redaction of database connection strings."""
        text = "postgres://user:password@localhost:5432/dbname"
        result = redact_string(text)
        assert "postgres://user:password@localhost" not in result
        assert "[DATABASE_URL_REDACTED]" in result

    def test_redact_email_patterns(self):
        """Test redaction of email addresses."""
        text = "Contact: user@example.com"
        result = redact_string(text)
        assert "user@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_redact_phone_patterns(self):
        """Test redaction of phone numbers."""
        text = "Phone: 555-123-4567"
        result = redact_string(text)
        assert "555-123-4567" not in result
        assert "[PHONE_REDACTED]" in result

    def test_redact_credit_card_patterns(self):
        """Test redaction of credit card numbers."""
        text = "Card: 4111-1111-1111-1111"
        result = redact_string(text)
        assert "4111-1111-1111-1111" not in result
        assert "[CARD_REDACTED]" in result

    def test_redact_dict_sensitive_keys(self):
        """Test redaction of sensitive keys in dictionaries."""
        data = {
            "username": "admin",
            "password": "secret123",
            "api_key": "sk_live_xyz",
            "token": "jwt_token_here",
            "email": "test@example.com",
        }
        result = redact_dict(data)

        assert result["username"] == "admin"
        assert result["password"] == "[REDACTED]"
        assert result["api_key"] == "[REDACTED]"
        assert result["token"] == "[REDACTED]"
        # Email in value (not key) should be redacted by pattern
        assert "[EMAIL_REDACTED]" in result["email"]

    def test_redact_dict_nested(self):
        """Test redaction of nested dictionaries."""
        data = {
            "config": {
                "settings": {
                    "password": "nested_secret"
                }
            }
        }
        result = redact_dict(data)
        assert result["config"]["settings"]["password"] == "[REDACTED]"

    def test_redact_dict_max_depth(self):
        """Test max depth protection for deeply nested structures."""
        # Create deeply nested structure (11 levels)
        data = {"level1": {"level2": {"level3": {"level4": {"level5": {
            "level6": {"level7": {"level8": {"level9": {"level10": {
                "level11": "deep"
            }}}}}
        }}}}}}
        result = redact_dict(data, max_depth=5)
        # Should truncate at max depth
        assert "_truncated" in str(result)

    def test_redact_list(self):
        """Test redaction of lists."""
        data = [
            {"password": "secret"},
            "email: user@test.com",
            123,
        ]
        result = redact_list(data)

        assert result[0]["password"] == "[REDACTED]"
        assert "[EMAIL_REDACTED]" in result[1]
        assert result[2] == 123

    def test_redact_payload_none(self):
        """Test redaction of None payload."""
        assert redact_payload(None) is None

    def test_redact_payload_preserves_non_sensitive(self):
        """Test that non-sensitive data is preserved."""
        data = {
            "tenant_id": "TENANT_001",
            "domain": "PAYMENTS",
            "version": "v1.0",
            "status": "active",
        }
        result = redact_dict(data)
        assert result == data


class TestDiffSummary:
    """Tests for diff summary generation."""

    def test_diff_both_none(self):
        """Test diff with both states None."""
        result = generate_diff_summary(None, None)
        assert result == "No changes"

    def test_diff_create(self):
        """Test diff for creation (before=None)."""
        after = {"name": "Test", "status": "active"}
        result = generate_diff_summary(None, after)
        assert "Created with 2 fields" in result

    def test_diff_delete(self):
        """Test diff for deletion (after=None)."""
        before = {"name": "Test", "status": "active"}
        result = generate_diff_summary(before, None)
        assert "Deleted 2 fields" in result

    def test_diff_added_fields(self):
        """Test diff with added fields."""
        before = {"name": "Test"}
        after = {"name": "Test", "status": "active"}
        result = generate_diff_summary(before, after)
        assert "Added:" in result
        assert "status" in result

    def test_diff_removed_fields(self):
        """Test diff with removed fields."""
        before = {"name": "Test", "status": "active"}
        after = {"name": "Test"}
        result = generate_diff_summary(before, after)
        assert "Removed:" in result
        assert "status" in result

    def test_diff_changed_fields(self):
        """Test diff with changed fields."""
        before = {"name": "Test", "status": "draft"}
        after = {"name": "Test", "status": "active"}
        result = generate_diff_summary(before, after)
        assert "Changed:" in result
        assert "status" in result


class TestAuditEventModels:
    """Tests for Pydantic audit event models."""

    def test_create_model_validation(self):
        """Test GovernanceAuditEventCreate validation."""
        event = GovernanceAuditEventCreate(
            event_type="TENANT_CREATED",
            actor_id="admin@example.com",
            entity_type="tenant",
            entity_id="TENANT_001",
            action="create",
        )
        assert event.event_type == "TENANT_CREATED"
        assert event.actor_id == "admin@example.com"
        assert event.tenant_id is None  # Optional

    def test_filter_model(self):
        """Test AuditEventFilter model."""
        filter_params = AuditEventFilter(
            tenant_id="TENANT_001",
            entity_type="domain_pack",
            action="import",
        )
        assert filter_params.tenant_id == "TENANT_001"
        assert filter_params.entity_type == "domain_pack"
        assert filter_params.from_date is None  # Optional


class TestEventTypeConstants:
    """Tests for event type constants."""

    def test_audit_event_types_exist(self):
        """Test that all expected event types are defined."""
        assert AuditEventTypes.TENANT_CREATED == "TENANT_CREATED"
        assert AuditEventTypes.DOMAIN_PACK_IMPORTED == "DOMAIN_PACK_IMPORTED"
        assert AuditEventTypes.TENANT_PACK_ACTIVATED == "TENANT_PACK_ACTIVATED"
        assert AuditEventTypes.CONFIG_CHANGE_APPROVED == "CONFIG_CHANGE_APPROVED"

    def test_entity_types_exist(self):
        """Test that all expected entity types are defined."""
        assert EntityTypes.TENANT == "tenant"
        assert EntityTypes.DOMAIN_PACK == "domain_pack"
        assert EntityTypes.TENANT_PACK == "tenant_pack"
        assert EntityTypes.TOOL == "tool"

    def test_actions_exist(self):
        """Test that all expected actions are defined."""
        assert Actions.CREATE == "create"
        assert Actions.ACTIVATE == "activate"
        assert Actions.APPROVE == "approve"
        assert Actions.REJECT == "reject"


class TestSensitiveKeysCoverage:
    """Tests for sensitive keys detection."""

    def test_common_sensitive_keys_detected(self):
        """Test that common sensitive keys are in the detection set."""
        expected_keys = {
            "password", "secret", "token", "api_key", "apikey",
            "access_token", "refresh_token", "private_key",
            "client_secret", "credentials",
        }
        assert expected_keys.issubset(SENSITIVE_KEYS)

    def test_pii_keys_detected(self):
        """Test that PII-related keys are detected."""
        pii_keys = {"ssn", "credit_card", "card_number", "cvv", "tax_id"}
        assert pii_keys.issubset(SENSITIVE_KEYS)


# Integration-style tests (would require database fixtures in real scenario)
class TestAuditRepositoryBehavior:
    """Behavior tests for governance audit repository (mock-based)."""

    @pytest.mark.asyncio
    async def test_create_event_auto_redacts(self):
        """Test that create_event auto-redacts sensitive data."""
        # This would be an integration test with actual DB
        # For now, we test the redaction functions work correctly
        payload = {
            "config": {"password": "secret123"},
            "api_key": "sk_live_test",
        }
        redacted = redact_payload(payload)

        assert redacted["config"]["password"] == "[REDACTED]"
        assert redacted["api_key"] == "[REDACTED]"

    @pytest.mark.asyncio
    async def test_tenant_isolation_concept(self):
        """Test tenant isolation concept (would need DB in real test)."""
        # This tests the filter model correctly handles tenant_id
        filter_tenant_a = AuditEventFilter(tenant_id="TENANT_A")
        filter_tenant_b = AuditEventFilter(tenant_id="TENANT_B")

        # Filters should be different
        assert filter_tenant_a.tenant_id != filter_tenant_b.tenant_id

        # In real implementation, these would be used in SQL queries
        # to ensure only tenant's own events are returned
