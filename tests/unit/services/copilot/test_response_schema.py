"""
JSON Schema validation tests for CopilotResponseGenerator.

Ensures the response format exactly matches the contract specification
from docs/phase13-copilot-intelligence-mvp.md Section 6.
"""

import pytest
import json
from jsonschema import validate, ValidationError

from src.services.copilot.response.response_generator import CopilotResponseGenerator
from src.services.copilot.retrieval.retrieval_service import EvidenceItem
from src.services.copilot.playbooks.playbook_recommender import RecommendedPlaybook


# JSON Schema for the Copilot response contract
COPILOT_RESPONSE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "type": "object",
    "properties": {
        "answer": {
            "type": "string",
            "description": "The main answer text"
        },
        "bullets": {
            "type": "array",
            "items": {
                "type": "string"
            },
            "description": "List of actionable bullet points"
        },
        "citations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "source_type": {
                        "type": "string",
                        "description": "Type of source (policy_doc, exception, audit_event, tool_registry)"
                    },
                    "source_id": {
                        "type": "string",
                        "description": "Identifier of the source document"
                    },
                    "title": {
                        "type": "string",
                        "description": "Human-readable title of the source"
                    },
                    "snippet": {
                        "type": "string",
                        "description": "Relevant excerpt from the source"
                    },
                    "url": {
                        "type": ["string", "null"],
                        "description": "Deep link to the source (optional)"
                    }
                },
                "required": ["source_type", "source_id", "title", "snippet", "url"],
                "additionalProperties": False
            },
            "description": "List of source citations"
        },
        "recommended_playbook": {
            "oneOf": [
                {
                    "type": "null"
                },
                {
                    "type": "object",
                    "properties": {
                        "playbook_id": {
                            "type": "string",
                            "description": "Identifier of the recommended playbook"
                        },
                        "confidence": {
                            "type": "number",
                            "minimum": 0,
                            "maximum": 1,
                            "description": "Confidence score (0-1)"
                        },
                        "steps": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "step": {
                                        "type": "integer",
                                        "description": "Step number"
                                    },
                                    "text": {
                                        "type": "string",
                                        "description": "Step description"
                                    }
                                },
                                "required": ["step", "text"],
                                "additionalProperties": True
                            },
                            "description": "List of playbook steps"
                        }
                    },
                    "required": ["playbook_id", "confidence", "steps"],
                    "additionalProperties": True
                }
            ],
            "description": "Recommended playbook (optional)"
        },
        "safety": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["READ_ONLY"],
                    "description": "Safety mode (must be READ_ONLY)"
                },
                "actions_allowed": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "List of allowed actions (empty for read-only)"
                }
            },
            "required": ["mode", "actions_allowed"],
            "additionalProperties": False
        }
    },
    "required": ["answer", "bullets", "citations", "recommended_playbook", "safety"],
    "additionalProperties": False
}


class TestCopilotResponseSchema:
    """Test JSON schema validation for Copilot responses."""
    
    @pytest.fixture
    def generator(self):
        """Create CopilotResponseGenerator instance."""
        return CopilotResponseGenerator()
    
    @pytest.fixture
    def sample_evidence_items(self):
        """Create sample evidence items for testing."""
        return [
            EvidenceItem(
                source_type="policy_doc",
                source_id="SOP-FIN-001",
                source_version="v1.2",
                title="Financial Exception Handling",
                snippet="In case of payment failures, escalate to finance team.",
                url="/policies/SOP-FIN-001",
                similarity_score=0.92,
                chunk_text="Full policy text..."
            )
        ]
    
    @pytest.fixture
    def sample_playbook_reco(self):
        """Create sample playbook recommendation."""
        return RecommendedPlaybook(
            playbook_id="PB-FIN-001",
            confidence=0.85,
            steps=[
                {"step": 1, "text": "Check payment processor status"},
                {"step": 2, "text": "Verify gateway configuration"}
            ],
            rationale="High confidence match",
            matched_fields=["exception_types", "domain"]
        )
    
    def test_response_schema_validation_full_response(self, generator, sample_evidence_items, sample_playbook_reco):
        """Test schema validation for complete response."""
        response = generator.generate_response(
            intent="recommend",
            user_query="How to handle payment failure?",
            evidence_items=sample_evidence_items,
            playbook_reco=sample_playbook_reco
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
    
    def test_response_schema_validation_minimal_response(self, generator):
        """Test schema validation for minimal response."""
        response = generator.generate_response(
            intent="explain",
            user_query="Test query"
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
    
    def test_response_schema_validation_with_citations(self, generator, sample_evidence_items):
        """Test schema validation for response with citations."""
        response = generator.generate_response(
            intent="explain",
            user_query="Explain this issue",
            evidence_items=sample_evidence_items
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Verify citations structure
        assert len(response["citations"]) > 0
        for citation in response["citations"]:
            assert "source_type" in citation
            assert "source_id" in citation
            assert "title" in citation
            assert "snippet" in citation
            assert "url" in citation  # Can be None
    
    def test_response_schema_validation_safety_constraints(self, generator):
        """Test schema validation for safety constraints."""
        response = generator.generate_response(
            intent="summary",
            user_query="Summarize exceptions"
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Verify safety structure
        assert response["safety"]["mode"] == "READ_ONLY"
        assert isinstance(response["safety"]["actions_allowed"], list)
    
    def test_response_schema_validation_playbook_recommendation(self, generator, sample_playbook_reco):
        """Test schema validation for playbook recommendations."""
        response = generator.generate_response(
            intent="recommend",
            user_query="Recommend a playbook",
            playbook_reco=sample_playbook_reco
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Verify playbook structure
        playbook = response["recommended_playbook"]
        assert playbook is not None
        assert "playbook_id" in playbook
        assert "confidence" in playbook
        assert "steps" in playbook
        assert 0 <= playbook["confidence"] <= 1
    
    def test_response_schema_validation_null_playbook(self, generator):
        """Test schema validation with null playbook recommendation."""
        response = generator.generate_response(
            intent="explain",
            user_query="Explain something"
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Verify null playbook is valid
        assert response["recommended_playbook"] is None
    
    @pytest.mark.parametrize("intent", ["summary", "explain", "similar", "recommend", "unknown"])
    def test_response_schema_validation_all_intents(self, generator, intent):
        """Test schema validation for all intent types."""
        response = generator.generate_response(
            intent=intent,
            user_query=f"Test query for {intent}"
        )
        
        # Should not raise ValidationError for any intent
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
    
    def test_response_json_serializable(self, generator, sample_evidence_items, sample_playbook_reco):
        """Test that response is JSON serializable."""
        response = generator.generate_response(
            intent="recommend",
            user_query="Handle this error",
            evidence_items=sample_evidence_items,
            playbook_reco=sample_playbook_reco
        )
        
        # Should be able to serialize and deserialize
        json_str = json.dumps(response)
        parsed_response = json.loads(json_str)
        
        # Parsed response should still validate
        validate(instance=parsed_response, schema=COPILOT_RESPONSE_SCHEMA)
    
    def test_citation_schema_compliance(self, generator):
        """Test that individual citations comply with schema."""
        evidence = EvidenceItem(
            source_type="audit_event",
            source_id="AUDIT-123",
            source_version="v1.0",
            title="System Configuration Change",
            snippet="User admin@example.com modified tenant settings",
            url="/audit/AUDIT-123",
            similarity_score=0.95,
            chunk_text="Full audit log..."
        )
        
        response = generator.generate_response(
            intent="explain",
            user_query="What changed?",
            evidence_items=[evidence]
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Check specific citation fields
        citation = response["citations"][0]
        assert citation["source_type"] == "audit_event"
        assert citation["source_id"] == "AUDIT-123"
        assert citation["title"] == "System Configuration Change"
        assert "admin@example.com" in citation["snippet"]
        assert citation["url"] == "/audit/AUDIT-123"
    
    def test_playbook_steps_schema_compliance(self, generator):
        """Test that playbook steps comply with schema."""
        playbook = RecommendedPlaybook(
            playbook_id="PB-TEST-001",
            confidence=0.75,
            steps=[
                {"step": 1, "text": "First action", "detail": "Extra info"},
                {"step": 2, "text": "Second action"}
            ],
            rationale="Test rationale",
            matched_fields=["type"]
        )
        
        response = generator.generate_response(
            intent="recommend",
            user_query="Follow this playbook",
            playbook_reco=playbook
        )
        
        # Should not raise ValidationError
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Check playbook steps structure
        steps = response["recommended_playbook"]["steps"]
        assert len(steps) == 2
        assert steps[0]["step"] == 1
        assert steps[0]["text"] == "First action"
        assert steps[1]["step"] == 2
        assert steps[1]["text"] == "Second action"
    
    def test_response_contract_enforcement(self, generator):
        """Test that all responses enforce the contract exactly."""
        response = generator.generate_response(
            intent="summary",
            user_query="Basic test"
        )
        
        # Validate against schema
        validate(instance=response, schema=COPILOT_RESPONSE_SCHEMA)
        
        # Ensure no extra fields are present
        expected_keys = {"answer", "bullets", "citations", "recommended_playbook", "safety"}
        assert set(response.keys()) == expected_keys
        
        # Ensure safety has no extra fields
        safety_keys = {"mode", "actions_allowed"}
        assert set(response["safety"].keys()) == safety_keys