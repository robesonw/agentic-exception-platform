"""
Unit tests for Playbook Matching Service.

Tests playbook matching logic, condition evaluation, and tenant isolation.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock

from src.infrastructure.db.models import Playbook
from src.infrastructure.repositories.playbook_repository import PlaybookRepository
from src.models.exception_record import ExceptionRecord, Severity
from src.models.tenant_policy import TenantPolicyPack
from src.playbooks.matching_service import PlaybookMatchingService, MatchingResult


@pytest.fixture
def mock_playbook_repository():
    """Create a mock PlaybookRepository."""
    return AsyncMock(spec=PlaybookRepository)


@pytest.fixture
def matching_service(mock_playbook_repository):
    """Create a PlaybookMatchingService instance."""
    return PlaybookMatchingService(playbook_repository=mock_playbook_repository)


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
            "sla_deadline": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
        },
    )


@pytest.fixture
def sample_playbook():
    """Create a sample Playbook for testing."""
    playbook = MagicMock(spec=Playbook)
    playbook.playbook_id = 1
    playbook.tenant_id = "tenant_001"
    playbook.name = "Settlement Retry Playbook"
    playbook.version = 1
    playbook.conditions = {
        "match": {
            "domain": "Finance",
            "exception_type": "Trade Settlement Failure",
            "severity_in": ["high", "critical"],
            "sla_minutes_remaining_lt": 60,
        },
        "priority": 100,
    }
    return playbook


class TestPlaybookMatchingService:
    """Test suite for PlaybookMatchingService."""
    
    @pytest.mark.asyncio
    async def test_match_playbook_no_candidates(self, matching_service, sample_exception):
        """Test matching when no playbooks exist."""
        matching_service.playbook_repository.get_candidate_playbooks.return_value = []
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
        assert "No playbooks found" in result.reasoning
        matching_service.playbook_repository.get_candidate_playbooks.assert_called_once_with("tenant_001")
    
    @pytest.mark.asyncio
    async def test_match_playbook_tenant_isolation(self, matching_service, sample_exception):
        """Test that tenant isolation is enforced."""
        with pytest.raises(ValueError, match="Tenant ID mismatch"):
            await matching_service.match_playbook(
                tenant_id="tenant_002",  # Different tenant
                exception=sample_exception,  # tenant_001
            )
    
    @pytest.mark.asyncio
    async def test_match_playbook_domain_match(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test matching by domain."""
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook == sample_playbook
        assert "domain" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_match_playbook_domain_mismatch(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that domain mismatch prevents matching."""
        # Change exception domain
        sample_exception.normalized_context["domain"] = "Healthcare"
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
        assert "No playbooks matched" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_match_playbook_exception_type_match(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test matching by exception type."""
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook == sample_playbook
    
    @pytest.mark.asyncio
    async def test_match_playbook_exception_type_mismatch(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that exception type mismatch prevents matching."""
        sample_exception.exception_type = "Different Exception Type"
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
    
    @pytest.mark.asyncio
    async def test_match_playbook_severity_in_match(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test matching by severity_in array."""
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook == sample_playbook
    
    @pytest.mark.asyncio
    async def test_match_playbook_severity_in_mismatch(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that severity mismatch prevents matching."""
        sample_exception.severity = Severity.LOW
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
    
    @pytest.mark.asyncio
    async def test_match_playbook_sla_condition_match(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test matching by SLA window condition."""
        # Set SLA deadline to 30 minutes from now (less than 60)
        sla_deadline = datetime.now(timezone.utc) + timedelta(minutes=30)
        sample_exception.normalized_context["sla_deadline"] = sla_deadline.isoformat()
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook == sample_playbook
    
    @pytest.mark.asyncio
    async def test_match_playbook_sla_condition_mismatch(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that SLA condition mismatch prevents matching."""
        # Set SLA deadline to 90 minutes from now (more than 60)
        sla_deadline = datetime.now(timezone.utc) + timedelta(minutes=90)
        sample_exception.normalized_context["sla_deadline"] = sla_deadline.isoformat()
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
    
    @pytest.mark.asyncio
    async def test_match_playbook_policy_tags_match(
        self, matching_service, sample_exception
    ):
        """Test matching by policy tags."""
        # Create a playbook with policy_tags condition
        # Note: Using a simple object instead of MagicMock to avoid attribute access issues
        class SimplePlaybook:
            def __init__(self):
                self.playbook_id = 3
                self.tenant_id = "tenant_001"
                self.name = "Policy Tags Playbook"
                self.version = 1
                self.conditions = {
                    "match": {
                        "domain": "Finance",
                        "exception_type": "Trade Settlement Failure",
                        "policy_tags": ["margin_call", "reg_report"],
                    },
                    "priority": 100,
                }
        
        playbook_with_tags = SimplePlaybook()
        
        # Add policy_tags to exception
        sample_exception.normalized_context["policy_tags"] = ["margin_call", "reg_report", "other"]
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [playbook_with_tags]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook == playbook_with_tags
        assert "matched" in result.reasoning.lower() or "policy" in result.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_match_playbook_policy_tags_mismatch(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that missing policy tags prevent matching."""
        sample_playbook.conditions["match"]["policy_tags"] = ["margin_call", "reg_report"]
        sample_exception.normalized_context["policy_tags"] = ["other_tag"]
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
    
    @pytest.mark.asyncio
    async def test_match_playbook_priority_ranking(
        self, matching_service, sample_exception
    ):
        """Test that playbooks are ranked by priority."""
        playbook1 = MagicMock(spec=Playbook)
        playbook1.playbook_id = 1
        playbook1.tenant_id = "tenant_001"
        playbook1.name = "Low Priority Playbook"
        playbook1.version = 1
        playbook1.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
            },
            "priority": 50,
        }
        
        playbook2 = MagicMock(spec=Playbook)
        playbook2.playbook_id = 2
        playbook2.tenant_id = "tenant_001"
        playbook2.name = "High Priority Playbook"
        playbook2.version = 1
        playbook2.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
            },
            "priority": 100,
        }
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [
            playbook1,
            playbook2,
        ]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        # Should select playbook2 (higher priority)
        assert result.playbook == playbook2
        assert "priority=100" in result.reasoning
    
    @pytest.mark.asyncio
    async def test_match_playbook_tie_breaking_by_id(
        self, matching_service, sample_exception
    ):
        """Test that playbooks with same priority are ranked by playbook_id."""
        playbook1 = MagicMock(spec=Playbook)
        playbook1.playbook_id = 1
        playbook1.tenant_id = "tenant_001"
        playbook1.name = "Older Playbook"
        playbook1.version = 1
        playbook1.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
            },
            "priority": 100,
        }
        
        playbook2 = MagicMock(spec=Playbook)
        playbook2.playbook_id = 2
        playbook2.tenant_id = "tenant_001"
        playbook2.name = "Newer Playbook"
        playbook2.version = 1
        playbook2.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
            },
            "priority": 100,
        }
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [
            playbook1,
            playbook2,
        ]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        # Should select playbook2 (higher playbook_id when priority is equal)
        assert result.playbook == playbook2
    
    @pytest.mark.asyncio
    async def test_match_playbook_no_sla_deadline(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that missing SLA deadline prevents matching when SLA condition is required."""
        # Remove SLA deadline
        sample_exception.normalized_context.pop("sla_deadline", None)
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook is None
    
    @pytest.mark.asyncio
    async def test_match_playbook_conditions_at_root(
        self, matching_service, sample_exception
    ):
        """Test that conditions can be at root level (not nested under 'match')."""
        playbook = MagicMock(spec=Playbook)
        playbook.playbook_id = 1
        playbook.tenant_id = "tenant_001"
        playbook.name = "Root Conditions Playbook"
        playbook.version = 1
        playbook.conditions = {
            "domain": "Finance",
            "exception_type": "Trade Settlement Failure",
            "priority": 100,
        }
        
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [playbook]
        
        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )
        
        assert result.playbook == playbook
    
    @pytest.mark.asyncio
    async def test_match_playbook_idempotent(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test that matching is idempotent (can be called multiple times with same result)."""
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]

        result1 = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        result2 = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        assert result1.playbook == result2.playbook
        assert result1.reasoning == result2.reasoning

    @pytest.mark.asyncio
    async def test_match_playbook_idempotent_multiple_calls(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test idempotency with multiple consecutive calls."""
        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]

        results = []
        for _ in range(5):
            result = await matching_service.match_playbook(
                tenant_id="tenant_001",
                exception=sample_exception,
            )
            results.append(result)

        # All results should be identical
        assert all(r.playbook == results[0].playbook for r in results)
        assert all(r.reasoning == results[0].reasoning for r in results)

    @pytest.mark.asyncio
    async def test_match_playbook_no_matches_all_conditions_fail(
        self, matching_service, sample_exception
    ):
        """Test no matches when all playbooks fail conditions."""
        playbook1 = MagicMock(spec=Playbook)
        playbook1.playbook_id = 1
        playbook1.tenant_id = "tenant_001"
        playbook1.name = "Wrong Domain Playbook"
        playbook1.version = 1
        playbook1.conditions = {
            "match": {"domain": "Healthcare"},  # Wrong domain
        }

        playbook2 = MagicMock(spec=Playbook)
        playbook2.playbook_id = 2
        playbook2.tenant_id = "tenant_001"
        playbook2.name = "Wrong Type Playbook"
        playbook2.version = 1
        playbook2.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Different Type",  # Wrong type
            },
        }

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [
            playbook1,
            playbook2,
        ]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        assert result.playbook is None
        assert "No playbooks matched" in result.reasoning

    @pytest.mark.asyncio
    async def test_match_playbook_multiple_matches_priority_ranking(
        self, matching_service, sample_exception
    ):
        """Test multiple matches are ranked by priority."""
        playbook1 = MagicMock(spec=Playbook)
        playbook1.playbook_id = 1
        playbook1.tenant_id = "tenant_001"
        playbook1.name = "Low Priority"
        playbook1.version = 1
        playbook1.conditions = {
            "match": {"domain": "Finance", "exception_type": "Trade Settlement Failure"},
            "priority": 50,
        }

        playbook2 = MagicMock(spec=Playbook)
        playbook2.playbook_id = 2
        playbook2.tenant_id = "tenant_001"
        playbook2.name = "Medium Priority"
        playbook2.version = 1
        playbook2.conditions = {
            "match": {"domain": "Finance", "exception_type": "Trade Settlement Failure"},
            "priority": 100,
        }

        playbook3 = MagicMock(spec=Playbook)
        playbook3.playbook_id = 3
        playbook3.tenant_id = "tenant_001"
        playbook3.name = "High Priority"
        playbook3.version = 1
        playbook3.conditions = {
            "match": {"domain": "Finance", "exception_type": "Trade Settlement Failure"},
            "priority": 200,
        }

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [
            playbook1,
            playbook2,
            playbook3,
        ]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        # Should select playbook3 (highest priority)
        assert result.playbook == playbook3
        assert "priority=200" in result.reasoning
        assert "evaluated 3 matching playbooks" in result.reasoning

    @pytest.mark.asyncio
    async def test_match_playbook_multiple_matches_tie_breaking(
        self, matching_service, sample_exception
    ):
        """Test tie-breaking when multiple playbooks have same priority."""
        playbook1 = MagicMock(spec=Playbook)
        playbook1.playbook_id = 1
        playbook1.tenant_id = "tenant_001"
        playbook1.name = "Older Playbook"
        playbook1.version = 1
        playbook1.conditions = {
            "match": {"domain": "Finance", "exception_type": "Trade Settlement Failure"},
            "priority": 100,
        }

        playbook2 = MagicMock(spec=Playbook)
        playbook2.playbook_id = 2
        playbook2.tenant_id = "tenant_001"
        playbook2.name = "Newer Playbook"
        playbook2.version = 1
        playbook2.conditions = {
            "match": {"domain": "Finance", "exception_type": "Trade Settlement Failure"},
            "priority": 100,
        }

        playbook3 = MagicMock(spec=Playbook)
        playbook3.playbook_id = 3
        playbook3.tenant_id = "tenant_001"
        playbook3.name = "Newest Playbook"
        playbook3.version = 1
        playbook3.conditions = {
            "match": {"domain": "Finance", "exception_type": "Trade Settlement Failure"},
            "priority": 100,
        }

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [
            playbook1,
            playbook2,
            playbook3,
        ]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        # Should select playbook3 (highest playbook_id when priority is equal)
        assert result.playbook == playbook3
        assert "evaluated 3 matching playbooks" in result.reasoning

    @pytest.mark.asyncio
    async def test_match_playbook_exception_type_exact_match_only(
        self, matching_service, sample_exception
    ):
        """Test that exception_type matching is exact (no pattern support in matching_service)."""
        # Note: matching_service doesn't support pattern matching, only exact match
        playbook = MagicMock(spec=Playbook)
        playbook.playbook_id = 1
        playbook.tenant_id = "tenant_001"
        playbook.name = "Pattern Playbook"
        playbook.version = 1
        playbook.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "*Settlement*",  # Pattern - should NOT match
            },
        }

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        # Should not match because matching_service doesn't support patterns
        assert result.playbook is None

    @pytest.mark.asyncio
    async def test_match_playbook_sla_deadline_string_format(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test SLA deadline parsing from ISO string format."""
        sla_deadline = datetime.now(timezone.utc) + timedelta(minutes=30)
        sample_exception.normalized_context["sla_deadline"] = sla_deadline.isoformat()

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        assert result.playbook == sample_playbook

    @pytest.mark.asyncio
    async def test_match_playbook_sla_deadline_datetime_object(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test SLA deadline when provided as datetime object."""
        sla_deadline = datetime.now(timezone.utc) + timedelta(minutes=30)
        sample_exception.normalized_context["sla_deadline"] = sla_deadline

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        assert result.playbook == sample_playbook

    @pytest.mark.asyncio
    async def test_match_playbook_sla_deadline_invalid_format(
        self, matching_service, sample_exception, sample_playbook
    ):
        """Test SLA deadline with invalid format (should be handled gracefully)."""
        sample_exception.normalized_context["sla_deadline"] = "invalid-date-format"

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [sample_playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        # Should not match because SLA deadline couldn't be parsed
        assert result.playbook is None

    @pytest.mark.asyncio
    async def test_match_playbook_policy_tags_from_tenant_policy(
        self, matching_service, sample_exception
    ):
        """Test policy tags extraction from tenant_policy when not in normalized_context."""
        class SimplePlaybook:
            def __init__(self):
                self.playbook_id = 4
                self.tenant_id = "tenant_001"
                self.name = "Tenant Policy Tags Playbook"
                self.version = 1
                self.conditions = {
                    "match": {
                        "domain": "Finance",
                        "exception_type": "Trade Settlement Failure",
                        "policy_tags": ["margin_call"],
                    },
                    "priority": 100,
                }

        playbook = SimplePlaybook()

        # Exception has no policy_tags in normalized_context
        sample_exception.normalized_context.pop("policy_tags", None)

        # Create mock tenant_policy with tags
        class MockTenantPolicy:
            tags = ["margin_call", "reg_report"]

        tenant_policy = MockTenantPolicy()

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
            tenant_policy=tenant_policy,
        )

        # Should match because tenant_policy has the required tags
        assert result.playbook == playbook

    @pytest.mark.asyncio
    async def test_match_playbook_severity_single_value(
        self, matching_service, sample_exception
    ):
        """Test matching with single severity value (not severity_in array)."""
        playbook = MagicMock(spec=Playbook)
        playbook.playbook_id = 1
        playbook.tenant_id = "tenant_001"
        playbook.name = "Single Severity Playbook"
        playbook.version = 1
        playbook.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
                "severity": "high",  # Single value, not array
            },
        }

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        assert result.playbook == playbook

    @pytest.mark.asyncio
    async def test_match_playbook_severity_single_value_mismatch(
        self, matching_service, sample_exception
    ):
        """Test that single severity value mismatch prevents matching."""
        playbook = MagicMock(spec=Playbook)
        playbook.playbook_id = 1
        playbook.tenant_id = "tenant_001"
        playbook.name = "Single Severity Playbook"
        playbook.version = 1
        playbook.conditions = {
            "match": {
                "domain": "Finance",
                "exception_type": "Trade Settlement Failure",
                "severity": "critical",  # Different severity
            },
        }

        matching_service.playbook_repository.get_candidate_playbooks.return_value = [playbook]

        result = await matching_service.match_playbook(
            tenant_id="tenant_001",
            exception=sample_exception,
        )

        assert result.playbook is None

