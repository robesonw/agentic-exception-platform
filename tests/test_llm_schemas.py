"""
Tests for LLM output schemas.

Tests Pydantic models for agent LLM outputs:
- TriageLLMOutput
- PolicyLLMOutput
- ResolutionLLMOutput
- SupervisorLLMOutput
- Base classes and utilities
"""

import pytest
from pydantic import ValidationError

from src.llm.schemas import (
    BaseAgentLLMOutput,
    EvidenceReference,
    PolicyLLMOutput,
    ReasoningStep,
    ResolutionLLMOutput,
    SCHEMA_REGISTRY,
    SupervisorLLMOutput,
    TriageLLMOutput,
    get_schema_model,
)


class TestReasoningStep:
    """Tests for ReasoningStep model."""

    def test_valid_reasoning_step(self):
        """Test creating a valid ReasoningStep."""
        step = ReasoningStep(
            step_number=1,
            description="Analyzed exception type",
            evidence_used=["RAG result 1", "Rule match"],
            conclusion="Exception is DataQualityFailure",
        )
        
        assert step.step_number == 1
        assert step.description == "Analyzed exception type"
        assert len(step.evidence_used) == 2
        assert step.conclusion == "Exception is DataQualityFailure"

    def test_reasoning_step_minimal(self):
        """Test ReasoningStep with minimal required fields."""
        step = ReasoningStep(
            step_number=1,
            description="Step description",
        )
        
        assert step.step_number == 1
        assert step.evidence_used == []
        assert step.conclusion is None

    def test_reasoning_step_invalid_step_number(self):
        """Test ReasoningStep with invalid step_number."""
        with pytest.raises(ValidationError):
            ReasoningStep(
                step_number=0,  # Must be >= 1
                description="Test",
            )


class TestEvidenceReference:
    """Tests for EvidenceReference model."""

    def test_valid_evidence_reference(self):
        """Test creating a valid EvidenceReference."""
        ref = EvidenceReference(
            source="RAG",
            reference_id="rag_001",
            relevance_score=0.92,
            description="Similar exception found in history",
        )
        
        assert ref.source == "RAG"
        assert ref.reference_id == "rag_001"
        assert ref.relevance_score == 0.92
        assert ref.description == "Similar exception found in history"

    def test_evidence_reference_minimal(self):
        """Test EvidenceReference with minimal required fields."""
        ref = EvidenceReference(
            source="Policy",
            description="Policy rule applied",
        )
        
        assert ref.source == "Policy"
        assert ref.reference_id is None
        assert ref.relevance_score is None

    def test_evidence_reference_invalid_relevance_score(self):
        """Test EvidenceReference with invalid relevance_score."""
        with pytest.raises(ValidationError):
            EvidenceReference(
                source="RAG",
                description="Test",
                relevance_score=1.5,  # Must be <= 1.0
            )


class TestBaseAgentLLMOutput:
    """Tests for BaseAgentLLMOutput model."""

    def test_base_output_validation(self):
        """Test BaseAgentLLMOutput validation."""
        # Base class should not be instantiated directly (abstract)
        # But we can test via subclasses
        pass


class TestTriageLLMOutput:
    """Tests for TriageLLMOutput model."""

    def test_valid_triage_output(self):
        """Test creating a valid TriageLLMOutput."""
        output = TriageLLMOutput(
            predicted_exception_type="DataQualityFailure",
            predicted_severity="HIGH",
            severity_confidence=0.85,
            classification_confidence=0.90,
            root_cause_hypothesis="Invalid data format",
            matched_rules=["rule_1", "rule_2"],
            diagnostic_summary="Exception classified as DataQualityFailure",
            reasoning_steps=[
                ReasoningStep(
                    step_number=1,
                    description="Analyzed exception type",
                )
            ],
            evidence_references=[
                EvidenceReference(
                    source="RAG",
                    description="Similar exception found",
                )
            ],
            confidence=0.87,
            natural_language_summary="This exception was classified as a data quality failure.",
        )
        
        assert output.predicted_exception_type == "DataQualityFailure"
        assert output.predicted_severity == "HIGH"
        assert output.severity_confidence == 0.85
        assert output.classification_confidence == 0.90
        assert output.confidence == 0.87
        assert len(output.reasoning_steps) == 1
        assert len(output.evidence_references) == 1

    def test_triage_output_minimal(self):
        """Test TriageLLMOutput with minimal required fields."""
        output = TriageLLMOutput(
            predicted_exception_type="DataQualityFailure",
            predicted_severity="LOW",
            severity_confidence=0.65,
            classification_confidence=0.70,
            diagnostic_summary="Test diagnostic",
            confidence=0.67,
            natural_language_summary="Test summary",
        )
        
        assert output.predicted_exception_type == "DataQualityFailure"
        assert output.matched_rules == []
        assert output.root_cause_hypothesis is None

    def test_triage_output_invalid_confidence(self):
        """Test TriageLLMOutput with invalid confidence values."""
        with pytest.raises(ValidationError):
            TriageLLMOutput(
                predicted_exception_type="DataQualityFailure",
                predicted_severity="HIGH",
                severity_confidence=1.5,  # Must be <= 1.0
                classification_confidence=0.90,
                diagnostic_summary="Test",
                confidence=0.87,
                natural_language_summary="Test",
            )


class TestPolicyLLMOutput:
    """Tests for PolicyLLMOutput model."""

    def test_valid_policy_output(self):
        """Test creating a valid PolicyLLMOutput."""
        output = PolicyLLMOutput(
            policy_decision="APPROVED",
            applied_guardrails=["guardrail_1", "guardrail_2"],
            violated_rules=[],
            approval_required=False,
            policy_violation_report=None,
            tenant_policy_influence="Tenant policy allowed this",
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.95,
            natural_language_summary="Action approved based on guardrails",
        )
        
        assert output.policy_decision == "APPROVED"
        assert output.approval_required is False
        assert len(output.applied_guardrails) == 2
        assert output.confidence == 0.95

    def test_policy_output_blocked(self):
        """Test PolicyLLMOutput with blocked decision."""
        output = PolicyLLMOutput(
            policy_decision="BLOCKED",
            applied_guardrails=["guardrail_1"],
            violated_rules=["rule_1"],
            approval_required=True,
            approval_reason="Action violates tenant policy",
            policy_violation_report="Action blocked due to policy violation",
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.90,
            natural_language_summary="Action blocked",
        )
        
        assert output.policy_decision == "BLOCKED"
        assert output.approval_required is True
        assert len(output.violated_rules) == 1


class TestResolutionLLMOutput:
    """Tests for ResolutionLLMOutput model."""

    def test_valid_resolution_output(self):
        """Test creating a valid ResolutionLLMOutput."""
        output = ResolutionLLMOutput(
            selected_playbook_id="playbook_001",
            playbook_selection_rationale="This playbook matches the exception type",
            rejected_playbooks=[{"id": "playbook_002", "reason": "Not applicable"}],
            action_rationale="Retry with exponential backoff",
            tool_execution_plan=[
                {"tool": "retry_tool", "order": 1, "parameters": {}}
            ],
            expected_outcome="Exception resolved",
            resolution_status="RESOLVED",
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.88,
            natural_language_summary="Selected playbook for resolution",
        )
        
        assert output.selected_playbook_id == "playbook_001"
        assert output.resolution_status == "RESOLVED"
        assert len(output.rejected_playbooks) == 1
        assert len(output.tool_execution_plan) == 1

    def test_resolution_output_partial(self):
        """Test ResolutionLLMOutput with partial resolution."""
        output = ResolutionLLMOutput(
            selected_playbook_id="playbook_001",
            playbook_selection_rationale="Test rationale",
            action_rationale="Test action",
            resolution_status="PARTIAL",
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.75,
            natural_language_summary="Partial resolution",
        )
        
        assert output.resolution_status == "PARTIAL"
        assert output.selected_playbook_id == "playbook_001"


class TestSupervisorLLMOutput:
    """Tests for SupervisorLLMOutput model."""

    def test_valid_supervisor_output(self):
        """Test creating a valid SupervisorLLMOutput."""
        output = SupervisorLLMOutput(
            oversight_decision="APPROVED_FLOW",
            intervention_reason=None,
            anomaly_detected=False,
            anomaly_description=None,
            agent_chain_review={"triage": "OK", "policy": "OK"},
            recommended_action=None,
            escalation_reason=None,
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.92,
            natural_language_summary="Agent chain approved",
        )
        
        assert output.oversight_decision == "APPROVED_FLOW"
        assert output.anomaly_detected is False
        assert "triage" in output.agent_chain_review

    def test_supervisor_output_intervened(self):
        """Test SupervisorLLMOutput with intervention."""
        output = SupervisorLLMOutput(
            oversight_decision="INTERVENED",
            intervention_reason="Low confidence chain detected",
            anomaly_detected=True,
            anomaly_description="Confidence scores below threshold",
            agent_chain_review={"triage": "LOW_CONFIDENCE", "policy": "OK"},
            recommended_action="Escalate to human review",
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.85,
            natural_language_summary="Intervention required",
        )
        
        assert output.oversight_decision == "INTERVENED"
        assert output.anomaly_detected is True
        assert output.intervention_reason is not None


class TestSchemaRegistry:
    """Tests for schema registry and utilities."""

    def test_schema_registry_contains_all_schemas(self):
        """Test that SCHEMA_REGISTRY contains all expected schemas."""
        assert "triage" in SCHEMA_REGISTRY
        assert "policy" in SCHEMA_REGISTRY
        assert "resolution" in SCHEMA_REGISTRY
        assert "supervisor" in SCHEMA_REGISTRY
        
        assert SCHEMA_REGISTRY["triage"] == TriageLLMOutput
        assert SCHEMA_REGISTRY["policy"] == PolicyLLMOutput
        assert SCHEMA_REGISTRY["resolution"] == ResolutionLLMOutput
        assert SCHEMA_REGISTRY["supervisor"] == SupervisorLLMOutput

    def test_get_schema_model_valid(self):
        """Test get_schema_model() with valid schema names."""
        assert get_schema_model("triage") == TriageLLMOutput
        assert get_schema_model("policy") == PolicyLLMOutput
        assert get_schema_model("resolution") == ResolutionLLMOutput
        assert get_schema_model("supervisor") == SupervisorLLMOutput
        
        # Test case-insensitive
        assert get_schema_model("TRIAGE") == TriageLLMOutput
        assert get_schema_model("Policy") == PolicyLLMOutput

    def test_get_schema_model_invalid(self):
        """Test get_schema_model() with invalid schema name."""
        with pytest.raises(ValueError, match="Unknown schema name"):
            get_schema_model("invalid_schema")

    def test_schema_models_inherit_from_base(self):
        """Test that all schema models inherit from BaseAgentLLMOutput."""
        assert issubclass(TriageLLMOutput, BaseAgentLLMOutput)
        assert issubclass(PolicyLLMOutput, BaseAgentLLMOutput)
        assert issubclass(ResolutionLLMOutput, BaseAgentLLMOutput)
        assert issubclass(SupervisorLLMOutput, BaseAgentLLMOutput)

    def test_schema_models_have_common_fields(self):
        """Test that all schema models have common base fields."""
        triage = TriageLLMOutput(
            predicted_exception_type="Test",
            predicted_severity="LOW",
            severity_confidence=0.5,
            classification_confidence=0.5,
            diagnostic_summary="Test",
            confidence=0.5,
            natural_language_summary="Test",
        )
        
        # All should have these base fields
        assert hasattr(triage, "reasoning_steps")
        assert hasattr(triage, "evidence_references")
        assert hasattr(triage, "confidence")
        assert hasattr(triage, "natural_language_summary")

    def test_schema_models_json_serialization(self):
        """Test that schema models can be serialized to JSON."""
        output = TriageLLMOutput(
            predicted_exception_type="DataQualityFailure",
            predicted_severity="HIGH",
            severity_confidence=0.85,
            classification_confidence=0.90,
            diagnostic_summary="Test diagnostic",
            reasoning_steps=[],
            evidence_references=[],
            confidence=0.87,
            natural_language_summary="Test summary",
        )
        
        # Test model_dump()
        dict_output = output.model_dump()
        assert isinstance(dict_output, dict)
        assert dict_output["predicted_exception_type"] == "DataQualityFailure"
        
        # Test model_dump_json()
        json_output = output.model_dump_json()
        assert isinstance(json_output, str)
        assert "DataQualityFailure" in json_output

