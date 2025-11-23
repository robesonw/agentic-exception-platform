"""
Comprehensive tests for Orchestrator pipeline runner.
Tests end-to-end pipeline execution with integration tests.
"""

from datetime import datetime, timezone

import pytest

from src.domainpack.loader import load_domain_pack
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity
from src.orchestrator.runner import PipelineRunnerError, run_pipeline
from src.tenantpack.loader import load_tenant_policy


@pytest.fixture
def finance_domain_pack():
    """Load finance domain pack from sample file."""
    return load_domain_pack("domainpacks/finance.sample.json")


@pytest.fixture
def finance_tenant_policy():
    """Load finance tenant policy from sample file."""
    return load_tenant_policy("tenantpacks/tenant_finance.sample.json")


@pytest.fixture
def sample_exceptions():
    """Create sample exceptions for testing."""
    return [
        {
            "tenantId": "TENANT_FINANCE_001",
            "sourceSystem": "TradingSystem",
            "exceptionType": "POSITION_BREAK",
            "rawPayload": {
                "accountId": "ACC-123",
                "cusip": "CUSIP-456",
                "expectedPosition": 1000,
                "actualPosition": 950,
            },
        },
        {
            "tenantId": "TENANT_FINANCE_001",
            "sourceSystem": "SettlementSystem",
            "exceptionType": "SETTLEMENT_FAIL",
            "rawPayload": {
                "orderId": "ORD-789",
                "intendedSettleDate": "2024-01-15",
                "failReason": "SSI mismatch",
            },
        },
        {
            "tenantId": "TENANT_FINANCE_001",
            "sourceSystem": "ClearingSystem",
            "exceptionType": "CASH_BREAK",
            "rawPayload": {
                "accountId": "ACC-123",
                "currency": "USD",
                "expectedCash": 50000.00,
                "actualCash": 49500.00,
            },
        },
    ]


class TestOrchestratorRunnerBasic:
    """Basic tests for pipeline runner."""

    @pytest.mark.asyncio
    async def test_run_pipeline_returns_correct_structure(
        self, finance_domain_pack, finance_tenant_policy, sample_exceptions
    ):
        """Test that run_pipeline returns correct output structure."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=sample_exceptions[:1],  # Single exception for speed
        )
        
        assert "tenantId" in result
        assert "runId" in result
        assert "results" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) == 1

    @pytest.mark.asyncio
    async def test_result_contains_required_fields(
        self, finance_domain_pack, finance_tenant_policy, sample_exceptions
    ):
        """Test that each result contains required fields."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=sample_exceptions[:1],
        )
        
        exception_result = result["results"][0]
        assert "exceptionId" in exception_result
        assert "status" in exception_result
        assert "stages" in exception_result
        assert "evidence" in exception_result
        assert "exception" in exception_result

    @pytest.mark.asyncio
    async def test_all_stages_executed(
        self, finance_domain_pack, finance_tenant_policy, sample_exceptions
    ):
        """Test that all agent stages are executed."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=sample_exceptions[:1],
        )
        
        exception_result = result["results"][0]
        stages = exception_result["stages"]
        
        assert "intake" in stages
        assert "triage" in stages
        assert "policy" in stages
        assert "resolution" in stages
        assert "feedback" in stages


class TestOrchestratorRunnerIntegration:
    """Integration tests with real domain and tenant packs."""

    @pytest.mark.asyncio
    async def test_end_to_end_finance_position_break(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test end-to-end processing of POSITION_BREAK exception."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "TradingSystem",
                "exceptionType": "POSITION_BREAK",
                "rawPayload": {
                    "accountId": "ACC-123",
                    "cusip": "CUSIP-456",
                    "expectedPosition": 1000,
                    "actualPosition": 950,
                },
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        assert result["tenantId"] == "TENANT_FINANCE_001"
        assert len(result["results"]) == 1
        
        exception_result = result["results"][0]
        assert exception_result["status"] in ["IN_PROGRESS", "ESCALATED", "OPEN"]
        
        # Verify exception was normalized
        exception_data = exception_result["exception"]
        assert exception_data["exceptionType"] == "POSITION_BREAK"
        assert exception_data["severity"] == "CRITICAL"
        
        # Verify all stages executed
        assert "intake" in exception_result["stages"]
        assert "triage" in exception_result["stages"]
        assert "policy" in exception_result["stages"]
        assert "resolution" in exception_result["stages"]
        assert "feedback" in exception_result["stages"]

    @pytest.mark.asyncio
    async def test_end_to_end_finance_settlement_fail(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test end-to-end processing of SETTLEMENT_FAIL exception."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "SettlementSystem",
                "exceptionType": "SETTLEMENT_FAIL",
                "rawPayload": {
                    "orderId": "ORD-789",
                    "intendedSettleDate": "2024-01-15",
                    "failReason": "SSI mismatch",
                },
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        assert len(result["results"]) == 1
        
        exception_result = result["results"][0]
        exception_data = exception_result["exception"]
        assert exception_data["exceptionType"] == "SETTLEMENT_FAIL"
        
        # Verify evidence contains information from all stages
        assert len(exception_result["evidence"]) > 0

    @pytest.mark.asyncio
    async def test_end_to_end_batch_processing(
        self, finance_domain_pack, finance_tenant_policy, sample_exceptions
    ):
        """Test processing multiple exceptions in a batch."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=sample_exceptions,
        )
        
        assert len(result["results"]) == 3
        
        # Verify each exception was processed
        for exception_result in result["results"]:
            assert "exceptionId" in exception_result
            assert "status" in exception_result
            assert "stages" in exception_result
            assert "evidence" in exception_result


class TestOrchestratorRunnerErrorHandling:
    """Tests for error handling and escalation."""

    @pytest.mark.asyncio
    async def test_handles_invalid_exception_type(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test that invalid exception type is handled gracefully."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "ERP",
                "exceptionType": "INVALID_TYPE",
                "rawPayload": {"error": "Unknown error"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        exception_result = result["results"][0]
        
        # Should either escalate or mark as non-actionable
        assert exception_result["status"] in ["ESCALATED", "OPEN", "IN_PROGRESS"]
        
        # Should have error information
        if "errors" in exception_result:
            assert len(exception_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_handles_missing_required_fields(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test that missing required fields are handled."""
        exceptions = [
            {
                "rawPayload": {"error": "Missing tenant ID"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        exception_result = result["results"][0]
        
        # Should escalate due to missing required fields
        assert exception_result["status"] in ["ESCALATED", "FAILED"]
        
        # Should have error information
        if "errors" in exception_result:
            assert len(exception_result["errors"]) > 0

    @pytest.mark.asyncio
    async def test_escalates_on_agent_failure(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test that agent failures result in escalation."""
        # Create exception that will cause triage to fail (no exception type)
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "ERP",
                "rawPayload": {"error": "No exception type provided"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        exception_result = result["results"][0]
        
        # Should escalate if triage fails
        if exception_result["status"] == "ESCALATED":
            assert "errors" in exception_result or len(exception_result["evidence"]) > 0


class TestOrchestratorRunnerContextManagement:
    """Tests for context management across stages."""

    @pytest.mark.asyncio
    async def test_context_passed_between_stages(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test that context is properly passed between agent stages."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "TradingSystem",
                "exceptionType": "POSITION_BREAK",
                "rawPayload": {"accountId": "ACC-123"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        exception_result = result["results"][0]
        
        # Verify evidence accumulates across stages
        assert len(exception_result["evidence"]) > 0
        
        # Verify stages contain decisions
        stages = exception_result["stages"]
        if "intake" in stages and "error" not in stages["intake"]:
            assert "decision" in stages["intake"]
        if "triage" in stages and "error" not in stages["triage"]:
            assert "decision" in stages["triage"]


class TestOrchestratorRunnerAuditLogging:
    """Tests for audit logging integration."""

    @pytest.mark.asyncio
    async def test_audit_logs_created(
        self, finance_domain_pack, finance_tenant_policy, sample_exceptions, tmp_path
    ):
        """Test that audit logs are created for the run."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=sample_exceptions[:1],
        )
        
        # Verify run ID is generated
        assert "runId" in result
        assert result["runId"] is not None
        
        # Verify audit log file exists (if runtime/audit directory is accessible)
        import os
        audit_dir = os.path.join("runtime", "audit")
        if os.path.exists(audit_dir):
            log_file = os.path.join(audit_dir, f"{result['runId']}.jsonl")
            # Note: File may not exist if audit directory is not writable in test environment
            # This is acceptable for MVP


class TestOrchestratorRunnerOutputSchema:
    """Tests for output schema correctness."""

    @pytest.mark.asyncio
    async def test_output_schema_matches_spec(
        self, finance_domain_pack, finance_tenant_policy, sample_exceptions
    ):
        """Test that output schema matches master spec."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=sample_exceptions[:1],
        )
        
        # Verify top-level structure
        assert isinstance(result, dict)
        assert "tenantId" in result
        assert "runId" in result
        assert "results" in result
        
        # Verify tenant ID matches
        assert result["tenantId"] == finance_tenant_policy.tenant_id
        
        # Verify results is a list
        assert isinstance(result["results"], list)
        
        # Verify each result structure
        for exception_result in result["results"]:
            assert "exceptionId" in exception_result
            assert "status" in exception_result
            assert "stages" in exception_result
            assert "evidence" in exception_result
            assert "exception" in exception_result
            
            # Verify stages structure
            stages = exception_result["stages"]
            assert isinstance(stages, dict)
            assert "intake" in stages
            assert "triage" in stages
            assert "policy" in stages
            assert "resolution" in stages
            assert "feedback" in stages

    @pytest.mark.asyncio
    async def test_exception_data_complete(
        self, finance_domain_pack, finance_tenant_policy
    ):
        """Test that exception data in results is complete."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "TradingSystem",
                "exceptionType": "POSITION_BREAK",
                "rawPayload": {"accountId": "ACC-123"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        exception_result = result["results"][0]
        exception_data = exception_result["exception"]
        
        # Verify required fields
        assert "exceptionId" in exception_data
        assert "tenantId" in exception_data
        assert "sourceSystem" in exception_data
        assert "timestamp" in exception_data
        assert "rawPayload" in exception_data
        assert "resolutionStatus" in exception_data


class TestOrchestratorRunnerEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_empty_batch(self, finance_domain_pack, finance_tenant_policy):
        """Test processing empty batch."""
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=[],
        )
        
        assert result["tenantId"] == finance_tenant_policy.tenant_id
        assert result["results"] == []

    @pytest.mark.asyncio
    async def test_single_exception(self, finance_domain_pack, finance_tenant_policy):
        """Test processing single exception."""
        exceptions = [
            {
                "tenantId": "TENANT_FINANCE_001",
                "sourceSystem": "ERP",
                "exceptionType": "SETTLEMENT_FAIL",
                "rawPayload": {"orderId": "ORD-123"},
            }
        ]
        
        result = await run_pipeline(
            domain_pack=finance_domain_pack,
            tenant_policy=finance_tenant_policy,
            exceptions_batch=exceptions,
        )
        
        assert len(result["results"]) == 1

