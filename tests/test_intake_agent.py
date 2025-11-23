"""
Comprehensive tests for IntakeAgent.
Tests normalization, validation, and logging.
"""

from datetime import datetime, timezone

import pytest

from src.agents.intake import IntakeAgent, IntakeAgentError
from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition
from src.models.exception_record import ExceptionRecord, ResolutionStatus


@pytest.fixture
def sample_domain_pack():
    """Create a sample domain pack for testing."""
    return DomainPack(
        domainName="TestDomain",
        exceptionTypes={
            "DataQualityFailure": ExceptionTypeDefinition(
                description="Data quality issue",
                detectionRules=["rule1"],
            ),
            "WorkflowFailure": ExceptionTypeDefinition(
                description="Workflow issue",
                detectionRules=["rule2"],
            ),
        },
    )


@pytest.fixture
def sample_audit_logger(tmp_path, monkeypatch):
    """Create a sample audit logger with temp directory."""
    audit_dir = tmp_path / "runtime" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    # Patch methods to use temp directory
    def patched_get_log_file(self):
        if self._log_file is None:
            self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file
    
    def patched_ensure_dir(self):
        audit_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(AuditLogger, "_get_log_file", patched_get_log_file)
    monkeypatch.setattr(AuditLogger, "_ensure_audit_directory", patched_ensure_dir)
    
    return AuditLogger(run_id="test_run", tenant_id="tenant_001")


class TestIntakeAgentNormalization:
    """Tests for exception normalization."""

    @pytest.mark.asyncio
    async def test_normalize_minimal_raw_exception(self):
        """Test normalizing minimal raw exception."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {"error": "Test error"},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert isinstance(normalized, ExceptionRecord)
        assert normalized.tenant_id == "tenant_001"
        assert normalized.source_system == "ERP"
        assert normalized.raw_payload == {"error": "Test error"}
        assert normalized.resolution_status == ResolutionStatus.OPEN

    @pytest.mark.asyncio
    async def test_normalize_with_exception_type(self):
        """Test normalizing exception with exception type."""
        agent = IntakeAgent()
        raw_exception = {
            "exceptionId": "exc_001",
            "tenantId": "tenant_001",
            "sourceSystem": "CRM",
            "exceptionType": "DataQualityFailure",
            "rawPayload": {"error": "Invalid data"},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_id == "exc_001"
        assert normalized.exception_type == "DataQualityFailure"
        assert "DataQualityFailure" in decision.decision

    @pytest.mark.asyncio
    async def test_normalize_generates_exception_id(self):
        """Test that exception ID is generated if not provided."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_id is not None
        assert len(normalized.exception_id) > 0

    @pytest.mark.asyncio
    async def test_normalize_extracts_timestamp(self):
        """Test timestamp extraction from raw exception."""
        agent = IntakeAgent()
        test_timestamp = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "timestamp": test_timestamp.isoformat(),
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.timestamp == test_timestamp

    @pytest.mark.asyncio
    async def test_normalize_uses_current_time_if_no_timestamp(self):
        """Test that current time is used if no timestamp provided."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        before = datetime.now(timezone.utc)
        normalized, decision = await agent.process(raw_exception)
        after = datetime.now(timezone.utc)
        
        assert before <= normalized.timestamp <= after

    @pytest.mark.asyncio
    async def test_normalize_with_tenant_id_parameter(self):
        """Test that tenant_id parameter overrides raw exception."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception, tenant_id="tenant_002")
        
        assert normalized.tenant_id == "tenant_002"

    @pytest.mark.asyncio
    async def test_normalize_with_pipeline_id(self):
        """Test that pipeline_id is included in normalized context."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception, pipeline_id="pipeline_001")
        
        assert "pipelineId" in normalized.normalized_context
        assert normalized.normalized_context["pipelineId"] == "pipeline_001"

    @pytest.mark.asyncio
    async def test_normalize_generates_pipeline_id(self):
        """Test that pipeline_id is generated if not provided."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert "pipelineId" in normalized.normalized_context
        assert normalized.normalized_context["pipelineId"] is not None

    @pytest.mark.asyncio
    async def test_normalize_exception_record_input(self):
        """Test processing an already-normalized ExceptionRecord."""
        agent = IntakeAgent()
        existing = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "test"},
        )
        
        normalized, decision = await agent.process(existing)
        
        assert normalized.exception_id == "exc_001"
        assert normalized.tenant_id == "tenant_001"


class TestIntakeAgentValidation:
    """Tests for domain pack validation."""

    @pytest.mark.asyncio
    async def test_validate_valid_exception_type(self, sample_domain_pack):
        """Test validation with valid exception type."""
        agent = IntakeAgent(domain_pack=sample_domain_pack)
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "exceptionType": "DataQualityFailure",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_type == "DataQualityFailure"
        assert decision.confidence == 1.0
        assert "validation errors" not in decision.decision.lower()

    @pytest.mark.asyncio
    async def test_validate_invalid_exception_type(self, sample_domain_pack):
        """Test validation with invalid exception type."""
        agent = IntakeAgent(domain_pack=sample_domain_pack)
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "exceptionType": "InvalidExceptionType",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_type == "InvalidExceptionType"
        assert decision.confidence < 1.0
        assert "validation errors" in decision.decision.lower() or "invalid" in decision.decision.lower()
        # Check if InvalidExceptionType is mentioned in evidence (may be in any evidence item)
        evidence_str = " ".join(decision.evidence)
        assert "InvalidExceptionType" in evidence_str or "validation" in evidence_str.lower()

    @pytest.mark.asyncio
    async def test_validate_no_exception_type(self, sample_domain_pack):
        """Test validation without exception type."""
        agent = IntakeAgent(domain_pack=sample_domain_pack)
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_type is None
        assert decision.confidence == 0.8
        # Check if message about triage inference is in evidence (may be in any evidence item)
        evidence_str = " ".join(decision.evidence).lower()
        assert "triage" in evidence_str or "inferred" in evidence_str or "will be" in evidence_str

    @pytest.mark.asyncio
    async def test_validate_without_domain_pack(self):
        """Test validation without domain pack."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "exceptionType": "SomeException",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_type == "SomeException"
        # Check if message about domain pack is in evidence (may be in any evidence item)
        evidence_str = " ".join(decision.evidence)
        assert "domain pack" in evidence_str.lower() or "domain" in evidence_str.lower()


class TestIntakeAgentDecision:
    """Tests for agent decision creation."""

    @pytest.mark.asyncio
    async def test_decision_contains_required_fields(self):
        """Test that decision contains all required fields."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert decision.decision is not None
        assert 0.0 <= decision.confidence <= 1.0
        assert isinstance(decision.evidence, list)
        assert decision.next_step == "ProceedToTriage"

    @pytest.mark.asyncio
    async def test_decision_evidence_includes_extracted_fields(self):
        """Test that decision evidence includes extracted fields."""
        agent = IntakeAgent()
        raw_exception = {
            "exceptionId": "exc_001",
            "tenantId": "tenant_001",
            "sourceSystem": "CRM",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        evidence_text = " ".join(decision.evidence)
        assert "exc_001" in evidence_text
        assert "tenant_001" in evidence_text
        assert "CRM" in evidence_text

    @pytest.mark.asyncio
    async def test_decision_next_step_is_triage(self):
        """Test that next step is always ProceedToTriage."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert decision.next_step == "ProceedToTriage"


class TestIntakeAgentAuditLogging:
    """Tests for audit logging integration."""

    @pytest.mark.asyncio
    async def test_logs_agent_event(self, sample_audit_logger):
        """Test that agent events are logged."""
        agent = IntakeAgent(audit_logger=sample_audit_logger)
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        normalized, decision = await agent.process(raw_exception)
        sample_audit_logger.close()
        
        # Verify log file was created
        log_file = sample_audit_logger._get_log_file()
        assert log_file.exists()
        
        # Verify log contains agent event
        import json
        with open(log_file, "r", encoding="utf-8") as f:
            line = f.readline()
            entry = json.loads(line)
        
        assert entry["event_type"] == "agent_event"
        assert entry["data"]["agent_name"] == "IntakeAgent"

    @pytest.mark.asyncio
    async def test_logs_without_audit_logger(self):
        """Test that agent works without audit logger."""
        agent = IntakeAgent()
        raw_exception = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        # Should not raise
        normalized, decision = await agent.process(raw_exception)


class TestIntakeAgentSampleExceptions:
    """Tests using sample finance and healthcare exceptions."""

    @pytest.mark.asyncio
    async def test_finance_exception_normalization(self, sample_domain_pack):
        """Test normalizing a finance domain exception."""
        agent = IntakeAgent(domain_pack=sample_domain_pack)
        
        # Sample finance exception
        raw_exception = {
            "exceptionId": "FIN-EXC-001",
            "tenantId": "TENANT_FINANCE_001",
            "sourceSystem": "TradingSystem",
            "exceptionType": "DataQualityFailure",
            "timestamp": "2024-01-15T10:30:00Z",
            "rawPayload": {
                "orderId": "ORD-12345",
                "error": "Price mismatch detected",
                "expectedPrice": 100.50,
                "actualPrice": 100.75,
            },
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_id == "FIN-EXC-001"
        assert normalized.tenant_id == "TENANT_FINANCE_001"
        assert normalized.source_system == "TradingSystem"
        assert normalized.exception_type == "DataQualityFailure"
        assert "orderId" in normalized.raw_payload

    @pytest.mark.asyncio
    async def test_healthcare_exception_normalization(self, sample_domain_pack):
        """Test normalizing a healthcare domain exception."""
        agent = IntakeAgent(domain_pack=sample_domain_pack)
        
        # Sample healthcare exception
        raw_exception = {
            "exceptionId": "HC-EXC-001",
            "tenantId": "TENANT_HEALTHCARE_042",
            "sourceSystem": "ClaimsSystem",
            "exceptionType": "WorkflowFailure",
            "timestamp": "2024-01-15T14:20:00Z",
            "rawPayload": {
                "claimId": "CLM-67890",
                "error": "Missing authorization",
                "patientId": "PAT-12345",
                "procedureCode": "CPT-99213",
            },
        }
        
        normalized, decision = await agent.process(raw_exception)
        
        assert normalized.exception_id == "HC-EXC-001"
        assert normalized.tenant_id == "TENANT_HEALTHCARE_042"
        assert normalized.source_system == "ClaimsSystem"
        assert normalized.exception_type == "WorkflowFailure"
        assert "claimId" in normalized.raw_payload

    @pytest.mark.asyncio
    async def test_exception_with_various_timestamp_formats(self):
        """Test handling various timestamp formats."""
        agent = IntakeAgent()
        
        # Test ISO format with Z
        raw1 = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "timestamp": "2024-01-15T10:30:00Z",
            "rawPayload": {},
        }
        normalized1, _ = await agent.process(raw1)
        assert normalized1.timestamp.year == 2024
        
        # Test ISO format with timezone
        raw2 = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "timestamp": "2024-01-15T10:30:00+00:00",
            "rawPayload": {},
        }
        normalized2, _ = await agent.process(raw2)
        assert normalized2.timestamp.year == 2024
        
        # Test datetime object
        raw3 = {
            "tenantId": "tenant_001",
            "sourceSystem": "ERP",
            "timestamp": datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
            "rawPayload": {},
        }
        normalized3, _ = await agent.process(raw3)
        assert normalized3.timestamp.year == 2024


class TestIntakeAgentErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_missing_required_fields(self):
        """Test handling missing required fields."""
        agent = IntakeAgent()
        
        # Missing tenantId
        raw_exception = {
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        # Should raise error
        with pytest.raises(IntakeAgentError) as exc_info:
            await agent.process(raw_exception)
        assert "tenant_id is required" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_invalid_exception_record_creation(self):
        """Test handling invalid exception data."""
        agent = IntakeAgent()
        
        # Invalid data that can't create ExceptionRecord
        raw_exception = {
            "tenantId": "",  # Empty string should fail validation
            "sourceSystem": "ERP",
            "rawPayload": {},
        }
        
        with pytest.raises((IntakeAgentError, Exception)):
            await agent.process(raw_exception)

