"""
Unit tests for Playbook Condition Evaluation Engine.

Tests condition evaluation logic, edge cases, and error handling.
"""

import pytest
from datetime import datetime, timezone

from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.playbooks.condition_engine import evaluate_conditions


@pytest.fixture
def sample_exception():
    """Create a sample ExceptionRecord for testing."""
    return ExceptionRecord(
        exceptionId="exc_001",
        tenantId="tenant_001",
        sourceSystem="ERP",
        exceptionType="Trade Settlement Failure",
        severity=Severity.HIGH,
        timestamp=datetime.now(timezone.utc),
        rawPayload={"error": "Settlement failed"},
        normalizedContext={
            "domain": "Finance",
            "policy_tags": ["margin_call", "reg_report"],
        },
    )


class TestConditionEngine:
    """Test suite for condition evaluation engine."""
    
    def test_evaluate_conditions_empty_conditions(self, sample_exception):
        """Test that empty conditions return False."""
        result = evaluate_conditions({}, sample_exception)
        
        assert result["matches"] is False
        assert result["priority"] == 0
        assert "No conditions" in result["reason"]
    
    def test_evaluate_conditions_domain_exact_match(self, sample_exception):
        """Test domain exact match."""
        conditions = {
            "match": {"domain": "Finance"},
            "priority": 100,
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
        assert result["priority"] == 100
        assert "domain" in result["checked_conditions"]
    
    def test_evaluate_conditions_domain_mismatch(self, sample_exception):
        """Test domain mismatch."""
        conditions = {
            "match": {"domain": "Healthcare"},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is False
        assert "domain" in result["reason"].lower()
    
    def test_evaluate_conditions_domain_missing(self):
        """Test domain condition when exception has no domain."""
        exception = ExceptionRecord(
            exceptionId="exc_002",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={},  # No domain
        )
        
        conditions = {"match": {"domain": "Finance"}}
        
        result = evaluate_conditions(conditions, exception)
        
        assert result["matches"] is False
        assert "domain" in result["reason"].lower()
    
    def test_evaluate_conditions_exception_type_exact_match(self, sample_exception):
        """Test exception_type exact match."""
        conditions = {
            "match": {"exception_type": "Trade Settlement Failure"},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
        assert "exception_type" in result["checked_conditions"]
    
    def test_evaluate_conditions_exception_type_case_insensitive(self, sample_exception):
        """Test exception_type case-insensitive matching."""
        conditions = {
            "match": {"exception_type": "trade settlement failure"},  # lowercase
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
    
    def test_evaluate_conditions_exception_type_pattern_match(self):
        """Test exception_type pattern matching with wildcards."""
        exception = ExceptionRecord(
            exceptionId="exc_003",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="Trade Settlement Failure",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )
        
        # Pattern: *Settlement* should match
        conditions = {"match": {"exception_type": "*Settlement*"}}
        
        result = evaluate_conditions(conditions, exception)
        
        assert result["matches"] is True
        
        # Pattern: Trade*Failure should match
        conditions2 = {"match": {"exception_type": "Trade*Failure"}}
        result2 = evaluate_conditions(conditions2, exception)
        assert result2["matches"] is True
        
        # Pattern: *Claim* should not match
        conditions3 = {"match": {"exception_type": "*Claim*"}}
        result3 = evaluate_conditions(conditions3, exception)
        assert result3["matches"] is False
    
    def test_evaluate_conditions_exception_type_mismatch(self, sample_exception):
        """Test exception_type mismatch."""
        conditions = {
            "match": {"exception_type": "Duplicate Claim"},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is False
        assert "exception_type" in result["reason"].lower()
    
    def test_evaluate_conditions_exception_type_missing(self):
        """Test exception_type condition when exception has no type."""
        exception = ExceptionRecord(
            exceptionId="exc_004",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )
        
        conditions = {"match": {"exception_type": "Trade Settlement Failure"}}
        
        result = evaluate_conditions(conditions, exception)
        
        assert result["matches"] is False
        assert "exception_type" in result["reason"].lower()
    
    def test_evaluate_conditions_severity_in_match(self, sample_exception):
        """Test severity_in array matching."""
        conditions = {
            "match": {"severity_in": ["high", "critical"]},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
        assert "severity" in result["checked_conditions"]
    
    def test_evaluate_conditions_severity_in_case_insensitive(self, sample_exception):
        """Test severity_in case-insensitive matching."""
        conditions = {
            "match": {"severity_in": ["HIGH", "CRITICAL"]},  # uppercase
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
    
    def test_evaluate_conditions_severity_in_mismatch(self, sample_exception):
        """Test severity_in mismatch."""
        conditions = {
            "match": {"severity_in": ["low", "medium"]},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is False
        assert "severity" in result["reason"].lower()
    
    def test_evaluate_conditions_severity_single_match(self, sample_exception):
        """Test single severity value matching."""
        conditions = {
            "match": {"severity": "high"},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
    
    def test_evaluate_conditions_severity_single_mismatch(self, sample_exception):
        """Test single severity value mismatch."""
        conditions = {
            "match": {"severity": "critical"},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is False
    
    def test_evaluate_conditions_severity_missing(self):
        """Test severity condition when exception has no severity."""
        exception = ExceptionRecord(
            exceptionId="exc_005",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )
        
        conditions = {"match": {"severity_in": ["high", "critical"]}}
        
        result = evaluate_conditions(conditions, exception)
        
        assert result["matches"] is False
        assert "severity" in result["reason"].lower()
    
    def test_evaluate_conditions_sla_condition_match(self, sample_exception):
        """Test SLA window condition match."""
        conditions = {
            "match": {"sla_minutes_remaining_lt": 60},
        }
        
        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=30)
        
        assert result["matches"] is True
        assert "sla_minutes_remaining_lt" in result["checked_conditions"]
    
    def test_evaluate_conditions_sla_condition_mismatch(self, sample_exception):
        """Test SLA window condition mismatch."""
        conditions = {
            "match": {"sla_minutes_remaining_lt": 60},
        }
        
        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=90)
        
        assert result["matches"] is False
        assert "sla" in result["reason"].lower()
    
    def test_evaluate_conditions_sla_condition_missing(self, sample_exception):
        """Test SLA condition when SLA deadline is not available."""
        conditions = {
            "match": {"sla_minutes_remaining_lt": 60},
        }
        
        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=None)
        
        assert result["matches"] is False
        assert "sla" in result["reason"].lower()
    
    def test_evaluate_conditions_policy_tags_match(self, sample_exception):
        """Test policy tags subset match."""
        conditions = {
            "match": {"policy_tags": ["margin_call", "reg_report"]},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
        assert "policy_tags" in result["checked_conditions"]
    
    def test_evaluate_conditions_policy_tags_partial_match(self, sample_exception):
        """Test policy tags when exception has more tags than required."""
        # Exception has: ["margin_call", "reg_report", "other"]
        # Required: ["margin_call"] - should match (subset)
        conditions = {
            "match": {"policy_tags": ["margin_call"]},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
    
    def test_evaluate_conditions_policy_tags_mismatch(self, sample_exception):
        """Test policy tags mismatch (missing required tag)."""
        conditions = {
            "match": {"policy_tags": ["margin_call", "missing_tag"]},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is False
        assert "policy_tags" in result["reason"].lower()
    
    def test_evaluate_conditions_policy_tags_empty_required(self, sample_exception):
        """Test policy tags when required list is empty (no requirements)."""
        conditions = {
            "match": {"policy_tags": []},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True  # Empty list means no requirements
    
    def test_evaluate_conditions_policy_tags_missing(self):
        """Test policy tags condition when exception has no tags."""
        exception = ExceptionRecord(
            exceptionId="exc_006",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )
        
        conditions = {"match": {"policy_tags": ["margin_call"]}}
        
        result = evaluate_conditions(conditions, exception)
        
        assert result["matches"] is False
        assert "policy_tags" in result["reason"].lower()
    
    def test_evaluate_conditions_multiple_conditions_all_match(self, sample_exception):
        """Test multiple conditions all matching."""
        conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
                "severity_in": ["high", "critical"],
                "sla_minutes_remaining_lt": 60,
                "policy_tags": ["margin_call"],
            },
            "priority": 100,
        }
        
        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=30)
        
        assert result["matches"] is True
        assert result["priority"] == 100
        assert len(result["checked_conditions"]) == 5
    
    def test_evaluate_conditions_multiple_conditions_one_fails(self, sample_exception):
        """Test multiple conditions with one failing."""
        conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
                "severity_in": ["low", "medium"],  # This will fail
            },
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is False
        assert "severity" in result["reason"].lower()
    
    def test_evaluate_conditions_priority_extraction(self, sample_exception):
        """Test that priority is extracted correctly."""
        conditions = {
            "match": {"domain": "Finance"},
            "priority": 200,
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["priority"] == 200
    
    def test_evaluate_conditions_priority_default(self, sample_exception):
        """Test that priority defaults to 0 if not specified."""
        conditions = {
            "match": {"domain": "Finance"},
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["priority"] == 0
    
    def test_evaluate_conditions_conditions_at_root(self, sample_exception):
        """Test that conditions can be at root level (not nested under 'match')."""
        conditions = {
            "domain": "Finance",
            "exception_type": "Trade Settlement Failure",
            "priority": 50,
        }
        
        result = evaluate_conditions(conditions, sample_exception)
        
        assert result["matches"] is True
        assert result["priority"] == 50
    
    def test_evaluate_conditions_partial_conditions(self, sample_exception):
        """Test that partial conditions (only some fields) work correctly."""
        # Only domain condition
        conditions = {"match": {"domain": "Finance"}}
        result = evaluate_conditions(conditions, sample_exception)
        assert result["matches"] is True
        
        # Only exception_type condition
        conditions2 = {"match": {"exception_type": "Trade Settlement Failure"}}
        result2 = evaluate_conditions(conditions2, sample_exception)
        assert result2["matches"] is True
    
    def test_evaluate_conditions_invalid_domain_type(self, sample_exception):
        """Test that invalid domain type fails gracefully."""
        conditions = {"match": {"domain": 123}}  # Should be string
        
        result = evaluate_conditions(conditions, sample_exception)
        
        # Should fail gracefully (log warning, but continue)
        assert result["matches"] is False or "domain" in result["checked_conditions"]
    
    def test_evaluate_conditions_invalid_severity_in_type(self, sample_exception):
        """Test that invalid severity_in type fails gracefully."""
        conditions = {"match": {"severity_in": "high"}}  # Should be list
        
        result = evaluate_conditions(conditions, sample_exception)
        
        # Should fail gracefully
        assert result["matches"] is False or "severity" in result["checked_conditions"]
    
    def test_evaluate_conditions_invalid_sla_type(self, sample_exception):
        """Test that invalid SLA type fails gracefully."""
        conditions = {"match": {"sla_minutes_remaining_lt": "60"}}  # Should be number
        
        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=30)
        
        # Should fail gracefully
        assert result["matches"] is False or "sla_minutes_remaining_lt" in result["checked_conditions"]
    
    def test_evaluate_conditions_invalid_policy_tags_type(self, sample_exception):
        """Test that invalid policy_tags type fails gracefully."""
        conditions = {"match": {"policy_tags": "margin_call"}}  # Should be list
        
        result = evaluate_conditions(conditions, sample_exception)
        
        # Should fail gracefully
        assert result["matches"] is False or "policy_tags" in result["checked_conditions"]
    
    def test_evaluate_conditions_no_match_conditions(self, sample_exception):
        """Test that empty match conditions return appropriate result."""
        conditions = {"priority": 100}  # No match conditions

        result = evaluate_conditions(conditions, sample_exception)

        # Should match (no conditions to check)
        assert result["matches"] is True
        assert result["priority"] == 100

    def test_evaluate_conditions_exception_type_pattern_wildcard_start(self):
        """Test exception_type pattern matching with wildcard at start."""
        exception = ExceptionRecord(
            exceptionId="exc_pattern_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="Trade Settlement Failure",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )

        conditions = {"match": {"exception_type": "*Settlement*"}}

        result = evaluate_conditions(conditions, exception)

        assert result["matches"] is True

    def test_evaluate_conditions_exception_type_pattern_wildcard_end(self):
        """Test exception_type pattern matching with wildcard at end."""
        exception = ExceptionRecord(
            exceptionId="exc_pattern_002",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="Trade Settlement Failure",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )

        conditions = {"match": {"exception_type": "Trade*"}}

        result = evaluate_conditions(conditions, exception)

        assert result["matches"] is True

    def test_evaluate_conditions_exception_type_pattern_single_char(self):
        """Test exception_type pattern matching with single char wildcard."""
        exception = ExceptionRecord(
            exceptionId="exc_pattern_003",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="Trade Settlement Failure",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )

        conditions = {"match": {"exception_type": "Trade?Settlement*"}}

        result = evaluate_conditions(conditions, exception)

        assert result["matches"] is True

    def test_evaluate_conditions_exception_type_pattern_case_insensitive(self):
        """Test exception_type pattern matching is case-insensitive."""
        exception = ExceptionRecord(
            exceptionId="exc_pattern_004",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="Trade Settlement Failure",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )

        conditions = {"match": {"exception_type": "*settlement*"}}  # lowercase

        result = evaluate_conditions(conditions, exception)

        assert result["matches"] is True

    def test_evaluate_conditions_sla_condition_exact_boundary(self, sample_exception):
        """Test SLA condition at exact boundary (should fail, as it's < not <=)."""
        conditions = {
            "match": {"sla_minutes_remaining_lt": 60},
        }

        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=60)

        assert result["matches"] is False  # 60 is not < 60

    def test_evaluate_conditions_sla_condition_negative(self, sample_exception):
        """Test SLA condition with negative minutes (past deadline)."""
        conditions = {
            "match": {"sla_minutes_remaining_lt": 60},
        }

        result = evaluate_conditions(conditions, sample_exception, sla_minutes_remaining=-10)

        assert result["matches"] is True  # -10 < 60

    def test_evaluate_conditions_policy_tags_all_required_present(self, sample_exception):
        """Test policy tags when all required tags are present."""
        conditions = {
            "match": {"policy_tags": ["margin_call", "reg_report"]},
        }

        result = evaluate_conditions(conditions, sample_exception)

        assert result["matches"] is True

    def test_evaluate_conditions_policy_tags_extra_tags_ok(self, sample_exception):
        """Test policy tags when exception has extra tags beyond required."""
        # Exception has: ["margin_call", "reg_report", "other"]
        # Required: ["margin_call"] - should match
        conditions = {
            "match": {"policy_tags": ["margin_call"]},
        }

        result = evaluate_conditions(conditions, sample_exception)

        assert result["matches"] is True

    def test_evaluate_conditions_policy_tags_order_independent(self, sample_exception):
        """Test that policy tags order doesn't matter."""
        conditions = {
            "match": {"policy_tags": ["reg_report", "margin_call"]},  # Different order
        }

        result = evaluate_conditions(conditions, sample_exception)

        assert result["matches"] is True

    def test_evaluate_conditions_multiple_conditions_with_priority(self, sample_exception):
        """Test multiple conditions with explicit priority."""
        conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
                "severity_in": ["high", "critical"],
            },
            "priority": 250,
        }

        result = evaluate_conditions(conditions, sample_exception)

        assert result["matches"] is True
        assert result["priority"] == 250
        assert len(result["checked_conditions"]) == 3

    def test_evaluate_conditions_with_policy_pack_tags(self):
        """Test policy tags extraction from policy pack."""
        exception = ExceptionRecord(
            exceptionId="exc_policy_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
            normalizedContext={"domain": "Finance"},
        )

        # Create a mock policy pack with tags
        class MockPolicyPack:
            tags = ["margin_call", "reg_report"]

        policy_pack = MockPolicyPack()

        conditions = {
            "match": {"policy_tags": ["margin_call"]},
        }

        # Exception has no policy_tags in normalized_context, but policy_pack has them
        result = evaluate_conditions(conditions, exception, policy_pack=policy_pack)

        # Should match because policy_pack.tags are used
        assert result["matches"] is True

