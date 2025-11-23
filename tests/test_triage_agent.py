"""
Comprehensive tests for TriageAgent.
Tests classification, severity assignment, and logging.
"""

from datetime import datetime, timezone

import pytest

from src.agents.triage import TriageAgent, TriageAgentError
from src.audit.logger import AuditLogger
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition, SeverityRule
from src.models.exception_record import ExceptionRecord, ResolutionStatus, Severity


@pytest.fixture
def finance_domain_pack():
    """Create finance domain pack with severity rules."""
    return DomainPack(
        domainName="CapitalMarketsTrading",
        exceptionTypes={
            "POSITION_BREAK": ExceptionTypeDefinition(
                description="Position quantity does not reconcile",
                detectionRules=[],
            ),
            "CASH_BREAK": ExceptionTypeDefinition(
                description="Cash ledger mismatch",
                detectionRules=[],
            ),
            "SETTLEMENT_FAIL": ExceptionTypeDefinition(
                description="Trade failed to settle",
                detectionRules=[],
            ),
            "MISMATCHED_TRADE_DETAILS": ExceptionTypeDefinition(
                description="Execution details mismatch",
                detectionRules=[],
            ),
        },
        severityRules=[
            SeverityRule(condition="exceptionType == 'POSITION_BREAK'", severity="CRITICAL"),
            SeverityRule(condition="exceptionType == 'CASH_BREAK'", severity="HIGH"),
            SeverityRule(condition="exceptionType == 'SETTLEMENT_FAIL'", severity="HIGH"),
        ],
    )


@pytest.fixture
def healthcare_domain_pack():
    """Create healthcare domain pack with severity rules."""
    return DomainPack(
        domainName="HealthcareClaimsAndCareOps",
        exceptionTypes={
            "PHARMACY_DUPLICATE_THERAPY": ExceptionTypeDefinition(
                description="Medication order duplicates active therapy",
                detectionRules=[],
            ),
            "CLAIM_MISSING_AUTH": ExceptionTypeDefinition(
                description="Claim without authorization",
                detectionRules=[],
            ),
            "PROVIDER_CREDENTIAL_EXPIRED": ExceptionTypeDefinition(
                description="Provider credential expired",
                detectionRules=[],
            ),
        },
        severityRules=[
            SeverityRule(condition="exceptionType == 'PHARMACY_DUPLICATE_THERAPY'", severity="CRITICAL"),
            SeverityRule(condition="exceptionType == 'CLAIM_MISSING_AUTH'", severity="HIGH"),
        ],
    )


@pytest.fixture
def sample_audit_logger(tmp_path, monkeypatch):
    """Create a sample audit logger with temp directory."""
    audit_dir = tmp_path / "runtime" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    
    def patched_get_log_file(self):
        if self._log_file is None:
            self._log_file = audit_dir / f"{self.run_id}.jsonl"
        return self._log_file
    
    def patched_ensure_dir(self):
        audit_dir.mkdir(parents=True, exist_ok=True)
    
    monkeypatch.setattr(AuditLogger, "_get_log_file", patched_get_log_file)
    monkeypatch.setattr(AuditLogger, "_ensure_audit_directory", patched_ensure_dir)
    
    return AuditLogger(run_id="test_run", tenant_id="tenant_001")


class TestTriageAgentClassification:
    """Tests for exception type classification."""

    @pytest.mark.asyncio
    async def test_classify_with_existing_exception_type(self, finance_domain_pack):
        """Test classification when exception type is already set."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "Position mismatch"},
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "POSITION_BREAK"
        assert "POSITION_BREAK" in decision.decision

    @pytest.mark.asyncio
    async def test_classify_invalid_exception_type(self, finance_domain_pack):
        """Test classification fails with invalid exception type."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="INVALID_TYPE",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        with pytest.raises(TriageAgentError) as exc_info:
            await agent.process(exception)
        assert "not found in domain pack" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_classify_from_raw_payload(self, finance_domain_pack):
        """Test classification from raw payload."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "exceptionType": "CASH_BREAK",
                "error": "Cash mismatch detected",
            },
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "CASH_BREAK"
        assert "CASH_BREAK" in decision.decision

    @pytest.mark.asyncio
    async def test_classify_fails_when_no_match(self, finance_domain_pack):
        """Test classification fails when no exception type can be determined."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            timestamp=datetime.now(timezone.utc),
            rawPayload={"error": "Unknown error"},
        )
        
        with pytest.raises(TriageAgentError) as exc_info:
            await agent.process(exception)
        assert "Could not classify" in str(exc_info.value)


class TestTriageAgentSeverity:
    """Tests for severity assignment."""

    @pytest.mark.asyncio
    async def test_severity_from_rule(self, finance_domain_pack):
        """Test severity assignment from matching rule."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        assert exception.severity == Severity.CRITICAL
        assert "CRITICAL" in decision.decision

    @pytest.mark.asyncio
    async def test_severity_highest_rule_wins(self, finance_domain_pack):
        """Test that highest severity wins when multiple rules match."""
        # Add multiple rules for same exception type
        finance_domain_pack.severity_rules.append(
            SeverityRule(condition="exceptionType == 'POSITION_BREAK'", severity="HIGH")
        )
        
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Should use CRITICAL (highest)
        assert exception.severity == Severity.CRITICAL

    @pytest.mark.asyncio
    async def test_severity_fallback_when_no_rules_match(self, finance_domain_pack):
        """Test severity fallback when no rules match."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="MISMATCHED_TRADE_DETAILS",  # No rule for this
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        # Should use fallback (MEDIUM or inferred)
        assert exception.severity is not None
        assert exception.severity in [Severity.LOW, Severity.MEDIUM, Severity.HIGH, Severity.CRITICAL]

    @pytest.mark.asyncio
    async def test_severity_with_condition_and_payload(self, finance_domain_pack):
        """Test severity rule with condition checking rawPayload."""
        # Add rule that checks rawPayload
        finance_domain_pack.severity_rules.append(
            SeverityRule(
                condition="exceptionType == 'MISMATCHED_TRADE_DETAILS' && rawPayload.impact == 'ECONOMIC'",
                severity="HIGH",
            )
        )
        
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="MISMATCHED_TRADE_DETAILS",
            timestamp=datetime.now(timezone.utc),
            rawPayload={"impact": "ECONOMIC"},
        )
        
        decision = await agent.process(exception)
        
        assert exception.severity == Severity.HIGH


class TestTriageAgentDecision:
    """Tests for agent decision creation."""

    @pytest.mark.asyncio
    async def test_decision_contains_required_fields(self, finance_domain_pack):
        """Test that decision contains all required fields."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="CASH_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        assert decision.decision is not None
        assert 0.0 <= decision.confidence <= 1.0
        assert isinstance(decision.evidence, list)
        assert decision.next_step == "ProceedToPolicy"

    @pytest.mark.asyncio
    async def test_decision_format(self, finance_domain_pack):
        """Test decision format matches template."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        assert "Triaged" in decision.decision
        assert "POSITION_BREAK" in decision.decision
        assert "CRITICAL" in decision.decision

    @pytest.mark.asyncio
    async def test_decision_evidence_includes_classification(self, finance_domain_pack):
        """Test that decision evidence includes classification details."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="CASH_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
        
        evidence_text = " ".join(decision.evidence)
        assert "CASH_BREAK" in evidence_text
        assert "HIGH" in evidence_text or "Severity" in evidence_text


class TestTriageAgentAuditLogging:
    """Tests for audit logging integration."""

    @pytest.mark.asyncio
    async def test_logs_agent_event(self, finance_domain_pack, sample_audit_logger):
        """Test that agent events are logged."""
        agent = TriageAgent(domain_pack=finance_domain_pack, audit_logger=sample_audit_logger)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        decision = await agent.process(exception)
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
        assert entry["data"]["agent_name"] == "TriageAgent"

    @pytest.mark.asyncio
    async def test_logs_without_audit_logger(self, finance_domain_pack):
        """Test that agent works without audit logger."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            exceptionType="CASH_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        # Should not raise
        decision = await agent.process(exception)


class TestTriageAgentFinanceSamples:
    """Tests using finance domain samples."""

    @pytest.mark.asyncio
    async def test_finance_position_break_critical(self, finance_domain_pack):
        """Test finance POSITION_BREAK -> CRITICAL."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-001",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="TradingSystem",
            exceptionType="POSITION_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "accountId": "ACC-123",
                "cusip": "CUSIP-456",
                "expectedPosition": 1000,
                "actualPosition": 950,
            },
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "POSITION_BREAK"
        assert exception.severity == Severity.CRITICAL
        assert "CRITICAL" in decision.decision
        assert "POSITION_BREAK" in decision.decision

    @pytest.mark.asyncio
    async def test_finance_cash_break_high(self, finance_domain_pack):
        """Test finance CASH_BREAK -> HIGH."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-002",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="ClearingSystem",
            exceptionType="CASH_BREAK",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "accountId": "ACC-123",
                "currency": "USD",
                "expectedCash": 50000.00,
                "actualCash": 49500.00,
            },
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "CASH_BREAK"
        assert exception.severity == Severity.HIGH
        assert "HIGH" in decision.decision

    @pytest.mark.asyncio
    async def test_finance_settlement_fail_high(self, finance_domain_pack):
        """Test finance SETTLEMENT_FAIL -> HIGH."""
        agent = TriageAgent(domain_pack=finance_domain_pack)
        exception = ExceptionRecord(
            exceptionId="FIN-EXC-003",
            tenantId="TENANT_FINANCE_001",
            sourceSystem="SettlementSystem",
            exceptionType="SETTLEMENT_FAIL",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "orderId": "ORD-789",
                "intendedSettleDate": "2024-01-15",
                "actualSettleDate": None,
                "failReason": "SSI mismatch",
            },
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "SETTLEMENT_FAIL"
        assert exception.severity == Severity.HIGH
        assert "HIGH" in decision.decision


class TestTriageAgentHealthcareSamples:
    """Tests using healthcare domain samples."""

    @pytest.mark.asyncio
    async def test_healthcare_pharmacy_duplicate_therapy_critical(self, healthcare_domain_pack):
        """Test healthcare PHARMACY_DUPLICATE_THERAPY -> CRITICAL."""
        agent = TriageAgent(domain_pack=healthcare_domain_pack)
        exception = ExceptionRecord(
            exceptionId="HC-EXC-001",
            tenantId="TENANT_HEALTHCARE_042",
            sourceSystem="PharmacySystem",
            exceptionType="PHARMACY_DUPLICATE_THERAPY",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "orderId": "ORD-123",
                "patientId": "PAT-456",
                "ndc": "12345-678-90",
                "activeTherapies": ["12345-678-90", "98765-432-10"],
            },
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "PHARMACY_DUPLICATE_THERAPY"
        assert exception.severity == Severity.CRITICAL
        assert "CRITICAL" in decision.decision
        assert "PHARMACY_DUPLICATE_THERAPY" in decision.decision

    @pytest.mark.asyncio
    async def test_healthcare_claim_missing_auth_high(self, healthcare_domain_pack):
        """Test healthcare CLAIM_MISSING_AUTH -> HIGH."""
        agent = TriageAgent(domain_pack=healthcare_domain_pack)
        exception = ExceptionRecord(
            exceptionId="HC-EXC-002",
            tenantId="TENANT_HEALTHCARE_042",
            sourceSystem="ClaimsSystem",
            exceptionType="CLAIM_MISSING_AUTH",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "claimId": "CLM-789",
                "patientId": "PAT-456",
                "procedureCodes": ["CPT-99213"],
                "authId": None,
            },
        )
        
        decision = await agent.process(exception)
        
        assert exception.exception_type == "CLAIM_MISSING_AUTH"
        assert exception.severity == Severity.HIGH
        assert "HIGH" in decision.decision


class TestTriageAgentErrorHandling:
    """Tests for error handling."""

    @pytest.mark.asyncio
    async def test_missing_domain_pack(self):
        """Test that domain pack is required."""
        # This should be caught at initialization, but test anyway
        with pytest.raises((TypeError, AttributeError)):
            agent = TriageAgent(domain_pack=None)
            exception = ExceptionRecord(
                exceptionId="exc_001",
                tenantId="tenant_001",
                sourceSystem="ERP",
                timestamp=datetime.now(timezone.utc),
                rawPayload={},
            )
            await agent.process(exception)

    @pytest.mark.asyncio
    async def test_empty_domain_pack(self):
        """Test handling empty domain pack."""
        empty_pack = DomainPack(domainName="EmptyDomain", exceptionTypes={})
        agent = TriageAgent(domain_pack=empty_pack)
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="ERP",
            exceptionType="SomeType",
            timestamp=datetime.now(timezone.utc),
            rawPayload={},
        )
        
        with pytest.raises(TriageAgentError):
            await agent.process(exception)


class TestTriageAgentIntegration:
    """Integration tests for complete triage workflow."""

    @pytest.mark.asyncio
    async def test_complete_triage_workflow(self, finance_domain_pack, sample_audit_logger):
        """Test complete triage workflow with classification and severity."""
        agent = TriageAgent(domain_pack=finance_domain_pack, audit_logger=sample_audit_logger)
        
        # Exception without pre-set type
        exception = ExceptionRecord(
            exceptionId="exc_001",
            tenantId="tenant_001",
            sourceSystem="TradingSystem",
            timestamp=datetime.now(timezone.utc),
            rawPayload={
                "exceptionType": "POSITION_BREAK",
                "error": "Position mismatch",
            },
        )
        
        decision = await agent.process(exception)
        sample_audit_logger.close()
        
        # Verify classification
        assert exception.exception_type == "POSITION_BREAK"
        
        # Verify severity assignment
        assert exception.severity == Severity.CRITICAL
        
        # Verify decision
        assert decision.next_step == "ProceedToPolicy"
        assert "POSITION_BREAK" in decision.decision
        assert "CRITICAL" in decision.decision
        assert decision.confidence > 0.0

