"""
Unit tests for CopilotSafetyService.

Tests the safety evaluation and enforcement capabilities for Copilot responses,
ensuring read-only behavior and blocking unsafe actions.
"""

import pytest
from unittest.mock import MagicMock

from src.services.copilot.safety.safety_service import (
    CopilotSafetyService,
    SafetyEvaluation
)


class TestSafetyEvaluation:
    """Test SafetyEvaluation dataclass."""
    
    def test_safety_evaluation_defaults(self):
        """Test safety evaluation with default values."""
        evaluation = SafetyEvaluation(is_safe=True)
        
        assert evaluation.is_safe is True
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        assert evaluation.modified_answer is None
        assert evaluation.redacted_content is False
        assert evaluation.violations == []
        assert evaluation.warnings == []
    
    def test_safety_evaluation_with_values(self):
        """Test safety evaluation with explicit values."""
        evaluation = SafetyEvaluation(
            is_safe=False,
            modified_answer="Modified response",
            redacted_content=True,
            violations=["Violation 1"],
            warnings=["Warning 1"]
        )
        
        assert evaluation.is_safe is False
        assert evaluation.mode == "READ_ONLY"  # Always READ_ONLY
        assert evaluation.actions_allowed == []
        assert evaluation.modified_answer == "Modified response"
        assert evaluation.redacted_content is True
        assert evaluation.violations == ["Violation 1"]
        assert evaluation.warnings == ["Warning 1"]


class TestCopilotSafetyService:
    """Test CopilotSafetyService functionality."""
    
    @pytest.fixture
    def safety_service(self):
        """Create CopilotSafetyService instance."""
        return CopilotSafetyService()
    
    @pytest.fixture
    def safe_response_payload(self):
        """Create a safe response payload."""
        return {
            "answer": "Based on the available evidence, this appears to be a known issue. Please review the documentation for guidance.",
            "bullets": [
                "Review policy documentation",
                "Check similar historical cases",
                "Consider consulting with domain experts"
            ],
            "citations": [],
            "recommended_playbook": None,
            "safety": {
                "mode": "READ_ONLY",
                "actions_allowed": []
            }
        }
    
    @pytest.fixture
    def unsafe_response_payload(self):
        """Create an unsafe response payload with action language."""
        return {
            "answer": "Execute the fix script immediately. Modify the configuration file and restart the service to resolve this issue.",
            "bullets": [
                "Run the automated fix tool",
                "Update database records",
                "Delete corrupted files"
            ],
            "citations": [],
            "recommended_playbook": None,
            "safety": {
                "mode": "READ_ONLY",
                "actions_allowed": []
            }
        }
    
    @pytest.fixture
    def sensitive_response_payload(self):
        """Create response payload with sensitive information."""
        return {
            "answer": "Check the API key: abc123def456ghi789 and use Bearer token xyz789abc123def for authentication.",
            "bullets": ["Configure api_key=secret123password"],
            "citations": [],
            "recommended_playbook": None,
            "safety": {
                "mode": "READ_ONLY",
                "actions_allowed": []
            }
        }
    
    def test_read_only_always_default(self, safety_service, safe_response_payload):
        """Test that READ_ONLY is always the default safety mode."""
        evaluation = safety_service.evaluate("summary", safe_response_payload)
        
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        assert evaluation.is_safe is True
    
    def test_safe_response_evaluation(self, safety_service, safe_response_payload):
        """Test evaluation of a safe response."""
        evaluation = safety_service.evaluate("explain", safe_response_payload)
        
        assert evaluation.is_safe is True
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        assert evaluation.modified_answer is None
        assert evaluation.redacted_content is False
        assert len(evaluation.violations) == 0
        assert len(evaluation.warnings) == 0
    
    def test_unsafe_language_detection(self, safety_service, unsafe_response_payload):
        """Test detection of unsafe language that implies actions."""
        evaluation = safety_service.evaluate("recommend", unsafe_response_payload)
        
        assert len(evaluation.violations) > 0
        assert evaluation.modified_answer is not None
        assert "consider" in evaluation.modified_answer.lower() or "review" in evaluation.modified_answer.lower()
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
    
    def test_unsafe_action_patterns_detection(self, safety_service):
        """Test detection of various unsafe action patterns."""
        test_cases = [
            ("Execute this script to fix the issue", True),
            ("Run the command to restart the service", True),
            ("Modify the configuration file manually", True),
            ("Delete the corrupted database entries", True),
            ("Create a new user account with admin rights", True),
            ("Install the latest security patch", True),
            ("Please review the documentation", False),
            ("Consider checking the logs", False),
            ("You might want to consult with your team", False),
        ]
        
        for answer, should_be_unsafe in test_cases:
            response = {
                "answer": answer,
                "safety": {"mode": "READ_ONLY", "actions_allowed": []}
            }
            evaluation = safety_service.evaluate("test", response)
            
            if should_be_unsafe:
                assert len(evaluation.violations) > 0, f"Should detect unsafe language in: '{answer}'"
                assert evaluation.modified_answer is not None, f"Should modify unsafe answer: '{answer}'"
            else:
                assert len(evaluation.violations) == 0, f"Should not flag safe language: '{answer}'"
    
    def test_sensitive_content_redaction(self, safety_service, sensitive_response_payload):
        """Test redaction of sensitive information."""
        evaluation = safety_service.evaluate("explain", sensitive_response_payload)
        
        assert evaluation.redacted_content is True
        assert evaluation.modified_answer is not None
        assert "[REDACTED" in evaluation.modified_answer
        assert "abc123def456ghi789" not in evaluation.modified_answer
        assert len(evaluation.warnings) > 0
    
    def test_sensitive_patterns_detection(self, safety_service):
        """Test detection and redaction of various sensitive patterns."""
        test_cases = [
            ("api_key: abc123def456789", "[REDACTED_API_KEY]"),
            ("Bearer abc123def456789xyz", "[REDACTED]"),
            ("password=mysecret123", "[REDACTED]"),
            ("client_secret=xyz789abc123", "[REDACTED]"),
            ("access_token: def456ghi789abc", "[REDACTED_API_KEY]"),
        ]
        
        for sensitive_text, _ in test_cases:
            response = {
                "answer": f"Please use this credential: {sensitive_text}",
                "safety": {"mode": "READ_ONLY", "actions_allowed": []}
            }
            evaluation = safety_service.evaluate("test", response)
            
            assert evaluation.redacted_content is True, f"Should redact: '{sensitive_text}'"
            assert sensitive_text not in evaluation.modified_answer, f"Original text should be removed: '{sensitive_text}'"
    
    def test_advisory_language_replacement(self, safety_service):
        """Test replacement of imperative language with advisory language."""
        unsafe_answer = "Execute the script and modify the configuration file. Delete old records and restart the service."
        
        response = {
            "answer": unsafe_answer,
            "safety": {"mode": "READ_ONLY", "actions_allowed": []}
        }
        
        evaluation = safety_service.evaluate("recommend", response)
        
        assert evaluation.modified_answer is not None
        modified = evaluation.modified_answer.lower()
        
        # Should contain advisory language
        assert any(word in modified for word in ['consider', 'review', 'advisory'])
        
        # Should not contain imperative language
        assert "execute the script" not in modified
        assert "modify the configuration" not in modified
        assert "delete old records" not in modified
    
    def test_tenant_policy_application(self, safety_service, safe_response_payload):
        """Test application of tenant-specific safety policies."""
        tenant_policy = {
            "blocked_terms": ["sensitive", "confidential"],
            "safety_level": "high",
            "allowed_actions": []
        }
        
        # Test with blocked term
        unsafe_response = safe_response_payload.copy()
        unsafe_response["answer"] = "This contains sensitive information about the system."
        
        evaluation = safety_service.evaluate("explain", unsafe_response, tenant_policy)
        
        assert len(evaluation.violations) > 0
        assert evaluation.modified_answer is not None
        assert "sensitive" not in evaluation.modified_answer
        assert "[BLOCKED_TERM]" in evaluation.modified_answer
    
    def test_read_only_enforcement(self, safety_service):
        """Test enforcement of read-only mode in all cases."""
        response_with_actions = {
            "answer": "Test response",
            "safety": {
                "mode": "WRITE",  # Invalid mode
                "actions_allowed": ["execute_tool"]  # Invalid actions
            }
        }
        
        evaluation = safety_service.evaluate("test", response_with_actions)
        
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        assert len(evaluation.violations) > 0  # Should detect invalid safety config
    
    def test_apply_safety_modifications(self, safety_service, unsafe_response_payload):
        """Test applying safety modifications to response payload."""
        evaluation = safety_service.evaluate("recommend", unsafe_response_payload)
        
        modified_payload = safety_service.apply_safety_modifications(
            unsafe_response_payload, evaluation
        )
        
        assert modified_payload["safety"]["mode"] == "READ_ONLY"
        assert modified_payload["safety"]["actions_allowed"] == []
        
        if evaluation.modified_answer:
            assert modified_payload["answer"] == evaluation.modified_answer
        
        if evaluation.violations or evaluation.warnings:
            assert "_safety_meta" in modified_payload
            assert "violations" in modified_payload["_safety_meta"]
            assert "warnings" in modified_payload["_safety_meta"]
    
    def test_error_handling(self, safety_service):
        """Test error handling in safety evaluation."""
        # Test with invalid response payload
        invalid_payload = None
        
        evaluation = safety_service.evaluate("test", invalid_payload)
        
        assert evaluation.is_safe is False
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        assert len(evaluation.violations) > 0
        assert evaluation.modified_answer is not None
        assert "cannot provide a safe response" in evaluation.modified_answer.lower()
    
    @pytest.mark.parametrize("intent", ["summary", "explain", "similar", "recommend", "unknown"])
    def test_all_intents_remain_read_only(self, safety_service, intent, safe_response_payload):
        """Test that all intents maintain READ_ONLY safety mode."""
        evaluation = safety_service.evaluate(intent, safe_response_payload)
        
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
    
    def test_bullet_points_safety_checking(self, safety_service):
        """Test safety checking of bullet points for action-oriented language."""
        response_with_action_bullets = {
            "answer": "Here's what you can do:",
            "bullets": [
                "Review the documentation",  # Safe
                "Execute the fix script",     # Unsafe
                "Consider checking logs",     # Safe
                "Delete corrupted files",     # Unsafe
            ],
            "safety": {"mode": "READ_ONLY", "actions_allowed": []}
        }
        
        evaluation = safety_service.evaluate("recommend", response_with_action_bullets)
        
        # Should detect action-oriented language in bullets
        assert len(evaluation.warnings) > 0
        bullet_warnings = [w for w in evaluation.warnings if "bullet" in w.lower()]
        assert len(bullet_warnings) > 0
    
    def test_high_security_tenant_policy(self, safety_service, safe_response_payload):
        """Test enhanced safety for high-security tenants."""
        high_security_policy = {
            "safety_level": "high",
            "blocked_terms": [],
            "allowed_actions": []
        }
        
        evaluation = safety_service.evaluate("explain", safe_response_payload, high_security_policy)
        
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        # Should have additional warnings for high security mode
        security_warnings = [w for w in evaluation.warnings if "high security" in w.lower()]
        assert len(security_warnings) > 0
    
    def test_complex_unsafe_scenario(self, safety_service):
        """Test complex scenario with multiple safety issues."""
        complex_unsafe_response = {
            "answer": "Execute this command: curl -H 'Authorization: Bearer abc123xyz789' -X DELETE https://api.example.com/users. Then modify the api_key=secret123 in the config and restart the service.",
            "bullets": [
                "Run the deletion script",
                "Update configuration files", 
                "Install security patches"
            ],
            "safety": {
                "mode": "EXECUTE",  # Wrong mode
                "actions_allowed": ["delete_users", "modify_config"]  # Wrong actions
            }
        }
        
        evaluation = safety_service.evaluate("recommend", complex_unsafe_response)
        
        # Should detect multiple violations
        assert len(evaluation.violations) > 0
        assert evaluation.redacted_content is True
        assert evaluation.modified_answer is not None
        assert evaluation.mode == "READ_ONLY"
        assert evaluation.actions_allowed == []
        
        # Should redact sensitive info
        assert "abc123xyz789" not in evaluation.modified_answer
        assert "secret123" not in evaluation.modified_answer
        
        # Should rewrite to advisory language
        modified = evaluation.modified_answer.lower()
        assert any(word in modified for word in ['consider', 'review', 'advisory'])
    
    def test_safety_metadata_in_applied_modifications(self, safety_service, unsafe_response_payload):
        """Test that safety metadata is properly included in modifications."""
        evaluation = safety_service.evaluate("recommend", unsafe_response_payload)
        modified_payload = safety_service.apply_safety_modifications(unsafe_response_payload, evaluation)
        
        if evaluation.violations or evaluation.warnings:
            assert "_safety_meta" in modified_payload
            meta = modified_payload["_safety_meta"]
            assert "violations" in meta
            assert "warnings" in meta
            assert "redacted_content" in meta
            assert meta["violations"] == evaluation.violations
            assert meta["warnings"] == evaluation.warnings
            assert meta["redacted_content"] == evaluation.redacted_content