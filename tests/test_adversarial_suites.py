"""
Tests for Synthetic Adversarial Test Suites (P3-23).

Tests domain-specific adversarial suites for finance (FINRA) and healthcare (HIPAA).
"""

import pytest

from src.models.exception_record import ExceptionRecord, Severity
from src.redteam.adversarial_suites import (
    build_finance_adversarial_suite,
    build_healthcare_adversarial_suite,
    get_adversarial_suite_by_domain,
)
from src.redteam.data_generators import (
    generate_exception_from_dict,
    generate_finance_exception_edge_cases,
    generate_healthcare_exception_edge_cases,
)
from src.redteam.harness import AttackType, ExpectedOutcome, RedTeamHarness, RedTeamScenario


class TestFinanceAdversarialSuite:
    """Tests for finance domain adversarial suite."""

    def test_build_finance_suite(self):
        """Test that finance suite is built with expected scenarios."""
        scenarios = build_finance_adversarial_suite()
        
        assert len(scenarios) > 0
        assert all(isinstance(s, RedTeamScenario) for s in scenarios)
        
        # Check that all scenarios are tagged with finance domain
        for scenario in scenarios:
            assert scenario.metadata.get("domain") == "finance"
            assert scenario.metadata.get("regulation") == "FINRA"
            assert "regulatory_requirement" in scenario.metadata

    def test_finance_suite_scenario_types(self):
        """Test that finance suite includes various attack types."""
        scenarios = build_finance_adversarial_suite()
        
        attack_types = {s.attack_type for s in scenarios}
        assert AttackType.SAFETY_BYPASS in attack_types
        assert AttackType.INSTRUCTION_OVERRIDE in attack_types
        assert AttackType.PROMPT_INJECTION in attack_types
        assert AttackType.TOOL_ALLOWLIST_BYPASS in attack_types

    def test_finance_suite_regulatory_focus(self):
        """Test that finance scenarios focus on FINRA regulatory requirements."""
        scenarios = build_finance_adversarial_suite()
        
        # Check for regulatory reporting scenarios
        reg_scenarios = [
            s for s in scenarios
            if "regulatory" in s.name.lower() or "reg_report" in s.id.lower()
        ]
        assert len(reg_scenarios) > 0
        
        # Check for position break scenarios
        pos_scenarios = [
            s for s in scenarios
            if "position" in s.name.lower() or "pos_break" in s.id.lower()
        ]
        assert len(pos_scenarios) > 0
        
        # Check for settlement scenarios
        settle_scenarios = [
            s for s in scenarios
            if "settlement" in s.name.lower() or "settle" in s.id.lower()
        ]
        assert len(settle_scenarios) > 0

    def test_finance_suite_expected_outcomes(self):
        """Test that finance scenarios have correct expected outcomes."""
        scenarios = build_finance_adversarial_suite()
        
        # All adversarial scenarios should expect to be blocked
        for scenario in scenarios:
            assert scenario.expected_outcome == ExpectedOutcome.SHOULD_BLOCK


class TestHealthcareAdversarialSuite:
    """Tests for healthcare domain adversarial suite."""

    def test_build_healthcare_suite(self):
        """Test that healthcare suite is built with expected scenarios."""
        scenarios = build_healthcare_adversarial_suite()
        
        assert len(scenarios) > 0
        assert all(isinstance(s, RedTeamScenario) for s in scenarios)
        
        # Check that all scenarios are tagged with healthcare domain
        for scenario in scenarios:
            assert scenario.metadata.get("domain") == "healthcare"
            assert scenario.metadata.get("regulation") == "HIPAA"
            assert "regulatory_requirement" in scenario.metadata

    def test_healthcare_suite_scenario_types(self):
        """Test that healthcare suite includes various attack types."""
        scenarios = build_healthcare_adversarial_suite()
        
        attack_types = {s.attack_type for s in scenarios}
        assert AttackType.SAFETY_BYPASS in attack_types
        assert AttackType.INSTRUCTION_OVERRIDE in attack_types
        assert AttackType.PROMPT_INJECTION in attack_types
        assert AttackType.TOOL_ALLOWLIST_BYPASS in attack_types

    def test_healthcare_suite_phi_focus(self):
        """Test that healthcare scenarios focus on PHI and HIPAA compliance."""
        scenarios = build_healthcare_adversarial_suite()
        
        # Check for PHI-related scenarios
        phi_scenarios = [
            s for s in scenarios
            if "phi" in s.name.lower() or "phi" in s.id.lower()
        ]
        assert len(phi_scenarios) > 0
        
        # Check for medication safety scenarios
        med_scenarios = [
            s for s in scenarios
            if "medication" in s.name.lower() or "med" in s.id.lower() or "therapy" in s.name.lower()
        ]
        assert len(med_scenarios) > 0
        
        # Check for patient privacy scenarios
        privacy_scenarios = [
            s for s in scenarios
            if "patient" in s.name.lower() or "privacy" in s.name.lower() or "demo" in s.id.lower()
        ]
        assert len(privacy_scenarios) > 0

    def test_healthcare_suite_expected_outcomes(self):
        """Test that healthcare scenarios have correct expected outcomes."""
        scenarios = build_healthcare_adversarial_suite()
        
        # All adversarial scenarios should expect to be blocked
        for scenario in scenarios:
            assert scenario.expected_outcome == ExpectedOutcome.SHOULD_BLOCK


class TestAdversarialSuiteByDomain:
    """Tests for get_adversarial_suite_by_domain function."""

    def test_get_finance_suite(self):
        """Test getting finance suite."""
        scenarios = get_adversarial_suite_by_domain("finance")
        
        assert len(scenarios) > 0
        assert all(s.metadata.get("domain") == "finance" for s in scenarios)

    def test_get_healthcare_suite(self):
        """Test getting healthcare suite."""
        scenarios = get_adversarial_suite_by_domain("healthcare")
        
        assert len(scenarios) > 0
        assert all(s.metadata.get("domain") == "healthcare" for s in scenarios)

    def test_get_all_suites(self):
        """Test getting all suites."""
        scenarios = get_adversarial_suite_by_domain("all")
        
        assert len(scenarios) > 0
        
        finance_count = sum(1 for s in scenarios if s.metadata.get("domain") == "finance")
        healthcare_count = sum(1 for s in scenarios if s.metadata.get("domain") == "healthcare")
        
        assert finance_count > 0
        assert healthcare_count > 0
        assert len(scenarios) == finance_count + healthcare_count

    def test_get_invalid_domain(self):
        """Test that invalid domain raises ValueError."""
        with pytest.raises(ValueError, match="Unknown domain"):
            get_adversarial_suite_by_domain("invalid_domain")


class TestDataGenerators:
    """Tests for synthetic data generators."""

    def test_generate_finance_exceptions(self):
        """Test generating finance exception edge cases."""
        exceptions = generate_finance_exception_edge_cases()
        
        assert len(exceptions) > 0
        
        # Check that exceptions have required fields
        for exc_dict in exceptions:
            assert "exceptionId" in exc_dict
            assert "tenantId" in exc_dict
            assert "exceptionType" in exc_dict
            assert "severity" in exc_dict
            assert "rawPayload" in exc_dict
            assert "normalizedContext" in exc_dict
            
            # Check domain context
            assert exc_dict["normalizedContext"].get("domain") == "CapitalMarketsTrading"

    def test_generate_finance_exceptions_types(self):
        """Test that finance exceptions include various exception types."""
        exceptions = generate_finance_exception_edge_cases()
        
        exception_types = {exc["exceptionType"] for exc in exceptions}
        
        # Should include key finance exception types
        assert "POSITION_BREAK" in exception_types or any("POSITION" in et for et in exception_types)
        assert "CASH_BREAK" in exception_types or any("CASH" in et for et in exception_types)
        assert "SETTLEMENT_FAIL" in exception_types or any("SETTLEMENT" in et for et in exception_types)

    def test_generate_healthcare_exceptions(self):
        """Test generating healthcare exception edge cases."""
        exceptions = generate_healthcare_exception_edge_cases()
        
        assert len(exceptions) > 0
        
        # Check that exceptions have required fields
        for exc_dict in exceptions:
            assert "exceptionId" in exc_dict
            assert "tenantId" in exc_dict
            assert "exceptionType" in exc_dict
            assert "severity" in exc_dict
            assert "rawPayload" in exc_dict
            assert "normalizedContext" in exc_dict
            
            # Check domain context
            assert exc_dict["normalizedContext"].get("domain") == "HealthcareClaimsAndCareOps"

    def test_generate_healthcare_exceptions_types(self):
        """Test that healthcare exceptions include various exception types."""
        exceptions = generate_healthcare_exception_edge_cases()
        
        exception_types = {exc["exceptionType"] for exc in exceptions}
        
        # Should include key healthcare exception types
        assert "PHARMACY_DUPLICATE_THERAPY" in exception_types or any("PHARMACY" in et for et in exception_types)
        assert "CLAIM_MISSING_AUTH" in exception_types or any("CLAIM" in et for et in exception_types)
        assert "PROVIDER_CREDENTIAL_EXPIRED" in exception_types or any("PROVIDER" in et for et in exception_types)

    def test_generate_exception_from_dict(self):
        """Test converting exception dictionary to ExceptionRecord."""
        exc_dict = {
            "exceptionId": "TEST_001",
            "tenantId": "TENANT_TEST",
            "exceptionType": "TEST_TYPE",
            "severity": "HIGH",
            "timestamp": "2024-01-01T00:00:00Z",
            "rawPayload": {"test": "data"},
            "normalizedContext": {"domain": "TestDomain"},
            "sourceSystem": "TestSystem",
        }
        
        exception = generate_exception_from_dict(exc_dict)
        
        assert isinstance(exception, ExceptionRecord)
        assert exception.exception_id == "TEST_001"
        assert exception.tenant_id == "TENANT_TEST"
        assert exception.exception_type == "TEST_TYPE"
        assert exception.severity == Severity.HIGH
        assert exception.raw_payload == {"test": "data"}

    def test_generate_exception_from_dict_defaults(self):
        """Test that missing fields get defaults."""
        exc_dict = {
            "exceptionId": "TEST_002",
            "tenantId": "TENANT_TEST",
            "exceptionType": "TEST_TYPE",
            "rawPayload": {},
        }
        
        exception = generate_exception_from_dict(exc_dict)
        
        assert exception.severity == Severity.MEDIUM  # Default
        assert exception.resolution_status == "OPEN"  # Default
        assert exception.source_system == "unknown"  # Default


class TestAdversarialSuiteIntegration:
    """Integration tests for adversarial suites with red-team harness."""

    def test_finance_suite_with_harness(self):
        """Test running finance suite with stubbed harness."""
        from unittest.mock import Mock
        
        scenarios = build_finance_adversarial_suite()
        
        # Create a mock harness
        mock_harness = Mock(spec=RedTeamHarness)
        mock_harness.run_suite.return_value = []
        
        # Verify scenarios can be passed to harness
        results = mock_harness.run_suite(scenarios)
        
        mock_harness.run_suite.assert_called_once_with(scenarios)
        assert isinstance(results, list)

    def test_healthcare_suite_with_harness(self):
        """Test running healthcare suite with stubbed harness."""
        from unittest.mock import Mock
        
        scenarios = build_healthcare_adversarial_suite()
        
        # Create a mock harness
        mock_harness = Mock(spec=RedTeamHarness)
        mock_harness.run_suite.return_value = []
        
        # Verify scenarios can be passed to harness
        results = mock_harness.run_suite(scenarios)
        
        mock_harness.run_suite.assert_called_once_with(scenarios)
        assert isinstance(results, list)

    def test_scenario_metadata_completeness(self):
        """Test that all scenarios have complete metadata."""
        finance_scenarios = build_finance_adversarial_suite()
        healthcare_scenarios = build_healthcare_adversarial_suite()
        
        all_scenarios = finance_scenarios + healthcare_scenarios
        
        for scenario in all_scenarios:
            # Check required metadata fields
            assert "domain" in scenario.metadata
            assert "regulation" in scenario.metadata
            assert "regulatory_requirement" in scenario.metadata
            
            # Check domain is valid
            assert scenario.metadata["domain"] in ["finance", "healthcare"]
            
            # Check regulation matches domain
            if scenario.metadata["domain"] == "finance":
                assert scenario.metadata["regulation"] == "FINRA"
            elif scenario.metadata["domain"] == "healthcare":
                assert scenario.metadata["regulation"] == "HIPAA"

    def test_scenario_prompt_generation(self):
        """Test that scenarios can generate adversarial prompts."""
        finance_scenarios = build_finance_adversarial_suite()
        healthcare_scenarios = build_healthcare_adversarial_suite()
        
        all_scenarios = finance_scenarios + healthcare_scenarios
        
        for scenario in all_scenarios:
            prompt = scenario.build_adversarial_prompt()
            
            assert isinstance(prompt, str)
            assert len(prompt) > 0
            assert scenario.prompt_template in prompt
            assert scenario.attack_pattern in prompt

