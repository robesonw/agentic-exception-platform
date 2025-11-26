"""
Tests for Domain Pack Test Suite Execution.

Tests:
- Test case execution through orchestrator
- Expected playbook ID validation
- Expected exception type/severity validation
- Pass/fail report generation
- API endpoint integration
"""

import asyncio
from dataclasses import asdict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domainpack.test_runner import (
    DomainPackTestRunner,
    TestResult,
    TestSuiteReport,
    get_test_runner,
)
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, TestCase
from src.models.tenant_policy import TenantPolicyPack


@pytest.fixture
def sample_domain_pack():
    """Sample domain pack with test suites."""
    return DomainPack(
        domain_name="TestDomain",
        exception_types={
            "TEST_EXCEPTION": ExceptionTypeDefinition(description="Test exception type"),
        },
        playbooks=[],
        test_suites=[
            TestCase(
                input={
                    "exceptionType": "TEST_EXCEPTION",
                    "rawPayload": {"test": "data"},
                },
                expected_output={
                    "expectedPlaybookId": "test_playbook_1",
                    "expectedExceptionType": "TEST_EXCEPTION",
                },
            ),
            TestCase(
                input={
                    "exceptionType": "TEST_EXCEPTION",
                    "rawPayload": {"test": "data2"},
                },
                expected_output={
                    "expectedPlaybookId": "test_playbook_2",
                },
            ),
        ],
    )


@pytest.fixture
def sample_tenant_policy():
    """Sample tenant policy pack."""
    return TenantPolicyPack(
        tenant_id="TENANT_TEST",
        domain_name="TestDomain",
        approved_tools=[],
    )


@pytest.fixture
def mock_orchestrator():
    """Mock orchestrator that returns predictable results."""
    async def mock_run_pipeline(domain_pack, tenant_policy, exceptions_batch, **kwargs):
        # Return mock pipeline result
        return {
            "tenantId": tenant_policy.tenant_id,
            "runId": "test_run_123",
            "results": [
                {
                    "exceptionId": f"exc_{idx}",
                    "status": "completed",
                    "stages": {
                        "intake": {"decision": "PROCESS", "confidence": 0.9},
                        "triage": {"decision": "CLASSIFIED", "confidence": 0.85},
                        "policy": {"decision": "APPROVED", "confidence": 0.8},
                        "resolution": {
                            "decision": "RESOLVED",
                            "confidence": 0.9,
                            "evidence": ["Selected playbook: test_playbook_1"],
                            "details": {"playbookId": "test_playbook_1"},
                        },
                        "feedback": {"decision": "LEARNED", "confidence": 0.85},
                    },
                    "exception": {
                        "exception_type": "TEST_EXCEPTION",
                        "severity": "MEDIUM",
                        "domain_name": "TestDomain",
                        "tenant_id": "TENANT_TEST",
                    },
                }
                for idx, _ in enumerate(exceptions_batch)
            ],
        }
    
    return mock_run_pipeline


class TestDomainPackTestRunner:
    """Tests for DomainPackTestRunner."""

    def test_init(self):
        """Test initialization."""
        runner = DomainPackTestRunner()
        assert runner is not None

    def test_get_test_runner(self):
        """Test getting global test runner instance."""
        runner1 = get_test_runner()
        runner2 = get_test_runner()
        assert runner1 is runner2

    @pytest.mark.asyncio
    async def test_run_test_suites_success(self, sample_domain_pack, sample_tenant_policy, mock_orchestrator):
        """Test running test suites successfully."""
        runner = DomainPackTestRunner()
        
        report = await runner.run_test_suites(
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            orchestrator=mock_orchestrator,
        )
        
        assert report.domain_name == "TestDomain"
        assert report.tenant_id == "TENANT_TEST"
        assert report.total_tests == 2
        assert report.execution_time_seconds >= 0

    @pytest.mark.asyncio
    async def test_run_test_case_playbook_validation_pass(self, sample_domain_pack, sample_tenant_policy, mock_orchestrator):
        """Test playbook ID validation passes when correct."""
        runner = DomainPackTestRunner()
        
        test_case = TestCase(
            input={"exceptionType": "TEST_EXCEPTION", "rawPayload": {}},
            expected_output={"expectedPlaybookId": "test_playbook_1"},
        )
        
        result = await runner._run_test_case(
            test_case=test_case,
            test_index=0,
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            orchestrator=mock_orchestrator,
        )
        
        assert result.passed is True
        assert result.error_message is None
        assert "playbookId_match" in result.validation_details

    @pytest.mark.asyncio
    async def test_run_test_case_playbook_validation_fail(self, sample_domain_pack, sample_tenant_policy):
        """Test playbook ID validation fails when incorrect."""
        runner = DomainPackTestRunner()
        
        # Mock orchestrator that returns wrong playbook ID
        async def mock_wrong_playbook(domain_pack, tenant_policy, exceptions_batch, **kwargs):
            return {
                "tenantId": tenant_policy.tenant_id,
                "runId": "test_run",
                "results": [
                    {
                        "exceptionId": "exc_0",
                        "stages": {
                            "resolution": {
                                "decision": "RESOLVED",
                                "details": {"playbookId": "wrong_playbook"},
                            },
                        },
                        "exception": {
                            "exception_type": "TEST_EXCEPTION",
                        },
                    }
                ],
            }
        
        test_case = TestCase(
            input={"exceptionType": "TEST_EXCEPTION", "rawPayload": {}},
            expected_output={"expectedPlaybookId": "test_playbook_1"},
        )
        
        result = await runner._run_test_case(
            test_case=test_case,
            test_index=0,
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            orchestrator=mock_wrong_playbook,
        )
        
        assert result.passed is False
        assert "playbook" in result.error_message.lower()
        assert "playbookId_mismatch" in result.validation_details

    @pytest.mark.asyncio
    async def test_validate_output_exception_type(self):
        """Test exception type validation."""
        runner = DomainPackTestRunner()
        
        actual_output = {
            "exception": {
                "exception_type": "TEST_EXCEPTION",
            },
        }
        expected_output = {
            "expectedExceptionType": "TEST_EXCEPTION",
        }
        
        result = runner._validate_output(actual_output, expected_output, DomainPack(domain_name="Test"))
        
        assert result["passed"] is True
        assert "exceptionType_match" in result["details"]

    @pytest.mark.asyncio
    async def test_validate_output_severity(self):
        """Test severity validation."""
        runner = DomainPackTestRunner()
        
        actual_output = {
            "exception": {
                "severity": "HIGH",
            },
        }
        expected_output = {
            "expectedSeverity": "HIGH",
        }
        
        result = runner._validate_output(actual_output, expected_output, DomainPack(domain_name="Test"))
        
        assert result["passed"] is True
        assert "severity_match" in result["details"]

    @pytest.mark.asyncio
    async def test_validate_output_stage_decision(self):
        """Test stage decision validation."""
        runner = DomainPackTestRunner()
        
        actual_output = {
            "stages": {
                "triage": {
                    "decision": "CLASSIFIED",
                },
            },
        }
        expected_output = {
            "expectedStages": {
                "triage": {
                    "decision": "CLASSIFIED",
                },
            },
        }
        
        result = runner._validate_output(actual_output, expected_output, DomainPack(domain_name="Test"))
        
        assert result["passed"] is True
        assert "stage_triage_match" in result["details"]

    @pytest.mark.asyncio
    async def test_extract_output_from_pipeline_result(self):
        """Test output extraction from pipeline result."""
        runner = DomainPackTestRunner()
        
        pipeline_result = {
            "results": [
                {
                    "exceptionId": "exc_123",
                    "stages": {
                        "resolution": {
                            "decision": "RESOLVED",
                            "details": {"playbookId": "test_playbook"},
                        },
                    },
                    "exception": {
                        "exception_type": "TEST_EXCEPTION",
                        "severity": "MEDIUM",
                    },
                }
            ],
        }
        
        output = runner._extract_output_from_pipeline_result(pipeline_result)
        
        assert output["exceptionId"] == "exc_123"
        assert output["playbookId"] == "test_playbook"
        assert output["exception"]["exception_type"] == "TEST_EXCEPTION"

    @pytest.mark.asyncio
    async def test_run_test_suites_empty_test_suites(self, sample_tenant_policy):
        """Test running test suites with no test cases."""
        domain_pack = DomainPack(
            domain_name="TestDomain",
            test_suites=[],
        )
        
        runner = DomainPackTestRunner()
        
        report = await runner.run_test_suites(
            domain_pack=domain_pack,
            tenant_policy=sample_tenant_policy,
        )
        
        assert report.total_tests == 0
        assert report.passed_tests == 0
        assert report.failed_tests == 0

    @pytest.mark.asyncio
    async def test_run_test_case_pipeline_error(self, sample_domain_pack, sample_tenant_policy):
        """Test handling of pipeline execution errors."""
        runner = DomainPackTestRunner()
        
        # Mock orchestrator that raises exception
        async def mock_error(domain_pack, tenant_policy, exceptions_batch, **kwargs):
            raise Exception("Pipeline execution failed")
        
        test_case = TestCase(
            input={"exceptionType": "TEST_EXCEPTION", "rawPayload": {}},
            expected_output={},
        )
        
        result = await runner._run_test_case(
            test_case=test_case,
            test_index=0,
            domain_pack=sample_domain_pack,
            tenant_policy=sample_tenant_policy,
            orchestrator=mock_error,
        )
        
        assert result.passed is False
        assert "Pipeline execution failed" in result.error_message

    def test_get_nested_value(self):
        """Test nested value extraction."""
        runner = DomainPackTestRunner()
        
        data = {
            "stages": {
                "resolution": {
                    "decision": "RESOLVED",
                },
            },
        }
        
        value = runner._get_nested_value(data, "stages.resolution.decision")
        assert value == "RESOLVED"
        
        value = runner._get_nested_value(data, "stages.nonexistent")
        assert value is None

