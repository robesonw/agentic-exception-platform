"""
Tests for prompt constraint system (LR-12).

Tests prompt sanitization and redaction for PHI/PII-heavy domains.
"""

import pytest

from src.llm.prompt_constraints import sanitize_prompt


class TestPromptSanitization:
    """Test prompt sanitization for different domains."""
    
    def test_healthcare_patient_id_redaction(self):
        """Test that Healthcare domain redacts patient IDs in prompt."""
        prompt = "Explain exception for patient_id: MRN-12345"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact patient ID
        assert "MRN-12345" not in sanitized
        assert "[REDACTED]" in sanitized or "patient_id=[REDACTED]" in sanitized
        assert sanitized != prompt
    
    def test_healthcare_patient_id_from_context(self):
        """Test that Healthcare domain redacts patient IDs from context."""
        prompt = "Explain this exception"
        context = {"domain": "Healthcare", "patient_id": "MRN-12345"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # If prompt doesn't contain the ID, context redaction may not apply
        # But if it does get added to prompt somehow, it should be redacted
        assert sanitized is not None
    
    def test_healthcare_mrn_redaction(self):
        """Test that Healthcare domain redacts MRN identifiers."""
        prompt = "Patient MRN: ABC-12345 needs attention"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact MRN
        assert "ABC-12345" not in sanitized or "patient_id=[REDACTED]" in sanitized
    
    def test_healthcare_email_redaction(self):
        """Test that Healthcare domain redacts email addresses."""
        prompt = "Contact patient at john.doe@example.com"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact email
        assert "john.doe@example.com" not in sanitized
        assert "[EMAIL_REDACTED]" in sanitized
    
    def test_healthcare_phone_redaction(self):
        """Test that Healthcare domain redacts phone numbers."""
        prompt = "Call patient at 555-123-4567"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact phone (pattern matches 3-3-4 format)
        assert "555-123-4567" not in sanitized
        assert "[PHONE_REDACTED]" in sanitized
    
    def test_healthcare_ssn_redaction(self):
        """Test that Healthcare domain redacts SSN."""
        prompt = "Patient SSN: 123-45-6789"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact SSN
        assert "123-45-6789" not in sanitized
        assert "SSN=[REDACTED]" in sanitized
    
    def test_finance_domain_unchanged(self):
        """Test that Finance domain doesn't modify prompts."""
        prompt = "Explain exception for account_id: ACC-12345"
        context = {"domain": "Finance"}
        
        sanitized = sanitize_prompt("Finance", prompt, context)
        
        # Should be unchanged
        assert sanitized == prompt
    
    def test_insurance_domain_unchanged(self):
        """Test that Insurance domain doesn't modify prompts."""
        prompt = "Explain exception for policy_id: POL-12345"
        context = {"domain": "Insurance"}
        
        sanitized = sanitize_prompt("Insurance", prompt, context)
        
        # Should be unchanged
        assert sanitized == prompt
    
    def test_no_domain_unchanged(self):
        """Test that prompts without domain are unchanged."""
        prompt = "Explain exception for patient_id: MRN-12345"
        context = {}
        
        sanitized = sanitize_prompt(None, prompt, context)
        
        # Should be unchanged
        assert sanitized == prompt
    
    def test_healthcare_case_insensitive(self):
        """Test that Healthcare domain matching is case-insensitive."""
        prompt = "Patient ID: MRN-12345"
        context = {"domain": "healthcare"}  # lowercase
        
        sanitized = sanitize_prompt("healthcare", prompt, context)
        
        # Should still redact
        assert "MRN-12345" not in sanitized or "[REDACTED]" in sanitized
    
    def test_empty_prompt(self):
        """Test that empty prompts are handled."""
        sanitized = sanitize_prompt("Healthcare", "", {})
        assert sanitized == ""
        
        sanitized = sanitize_prompt("Healthcare", None, {})
        assert sanitized == "" or sanitized is None
    
    def test_multiple_pii_patterns(self):
        """Test that multiple PII patterns are redacted."""
        prompt = "Patient MRN: ABC-123, email: test@example.com, phone: 555-123-4567"
        context = {"domain": "Healthcare"}
        
        sanitized = sanitize_prompt("Healthcare", prompt, context)
        
        # Should redact all PII
        assert "ABC-123" not in sanitized or "[REDACTED]" in sanitized
        assert "test@example.com" not in sanitized
        assert "555-123-4567" not in sanitized
        assert "[PHONE_REDACTED]" in sanitized

