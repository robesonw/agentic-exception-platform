"""
Tests for Intent Detection Router

Validates intent classification accuracy for various user message patterns
and contextual scenarios.
"""

import pytest
from datetime import datetime, timedelta
from src.services.copilot.router.intent_router import (
    IntentDetectionRouter,
    LLMAssistedRouter,
    IntentType,
    IntentResult
)


class TestIntentDetectionRouter:
    """Test the core intent detection functionality."""
    
    @pytest.fixture
    def router(self):
        """Create router instance for testing."""
        return IntentDetectionRouter()
        
    def test_summary_intents(self, router):
        """Test detection of summary-related intents."""
        test_cases = [
            ("Summarize today's exceptions", IntentType.SUMMARY),
            ("Show me today's exceptions", IntentType.SUMMARY),
            ("What's the status of recent issues?", IntentType.SUMMARY),
            ("Give me an overview of this week's errors", IntentType.SUMMARY),
            ("Dashboard view for critical exceptions", IntentType.SUMMARY),
            ("Report on yesterday's incidents", IntentType.SUMMARY),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            assert result.confidence > 0.5
            assert 'date_range' in result.extracted_params or 'severity_filters' in result.extracted_params
            
    def test_explain_intents(self, router):
        """Test detection of explanation-related intents."""
        test_cases = [
            ("Why was EX-123 classified as high?", IntentType.EXPLAIN),
            ("Explain what happened with exception EX-456", IntentType.EXPLAIN),
            ("Tell me why this was categorized as critical", IntentType.EXPLAIN),
            ("What caused EX-789?", IntentType.EXPLAIN),
            ("How come this exception triggered the alert?", IntentType.EXPLAIN),
            ("Give me details about why this failed", IntentType.EXPLAIN),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            assert result.confidence > 0.5
            
    def test_similar_cases_intents(self, router):
        """Test detection of similar case finding intents."""
        test_cases = [
            ("Find similar to EX-123", IntentType.SIMILAR_CASES),
            ("Show me related exceptions to this one", IntentType.SIMILAR_CASES),
            ("Are there other cases like EX-456?", IntentType.SIMILAR_CASES),
            ("Find comparable issues from this month", IntentType.SIMILAR_CASES),
            ("Has this happened before?", IntentType.SIMILAR_CASES),
            ("Show similar exceptions with same error", IntentType.SIMILAR_CASES),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            assert result.confidence > 0.5
            
    def test_recommend_playbook_intents(self, router):
        """Test detection of playbook recommendation intents."""
        test_cases = [
            ("Recommend playbook for this", IntentType.RECOMMEND_PLAYBOOK),
            ("What should I do to fix this exception?", IntentType.RECOMMEND_PLAYBOOK),
            ("Suggest a runbook for EX-789", IntentType.RECOMMEND_PLAYBOOK),
            ("How to resolve this issue?", IntentType.RECOMMEND_PLAYBOOK),
            ("What are the next steps for this?", IntentType.RECOMMEND_PLAYBOOK),
            ("Help me handle this exception", IntentType.RECOMMEND_PLAYBOOK),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            assert result.confidence > 0.5
            
    def test_draft_response_intents(self, router):
        """Test detection of response drafting intents."""
        test_cases = [
            ("Draft response for customer about EX-123", IntentType.DRAFT_RESPONSE),
            ("Help me write an email about this outage", IntentType.DRAFT_RESPONSE),
            ("Generate message template for this issue", IntentType.DRAFT_RESPONSE),
            ("What should I tell the user about EX-456?", IntentType.DRAFT_RESPONSE),
            ("Compose a reply for this exception", IntentType.DRAFT_RESPONSE),
            ("Write customer notification for this incident", IntentType.DRAFT_RESPONSE),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            assert result.confidence > 0.5
            
    def test_workflow_view_intents(self, router):
        """Test detection of workflow viewing intents."""
        test_cases = [
            ("Show workflow for this exception", IntentType.WORKFLOW_VIEW),
            ("What's the process for handling this?", IntentType.WORKFLOW_VIEW),
            ("Display the workflow steps", IntentType.WORKFLOW_VIEW),
            ("How does this process flow work?", IntentType.WORKFLOW_VIEW),
            ("Show me the sequence for EX-123", IntentType.WORKFLOW_VIEW),
            ("What's the pipeline for this exception type?", IntentType.WORKFLOW_VIEW),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            assert result.confidence > 0.5
            
    def test_other_intents(self, router):
        """Test detection of unclassifiable or edge case intents."""
        test_cases = [
            ("Hello, how are you?", IntentType.OTHER),
            ("Random text that doesn't match patterns", IntentType.OTHER),
            ("Testing 123", IntentType.OTHER),
            ("", IntentType.OTHER),
        ]
        
        for message, expected_intent in test_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_intent
            # OTHER intent should have neutral/moderate confidence
            assert 0.3 <= result.confidence <= 0.7

    def test_exception_id_extraction(self, router):
        """Test extraction of exception IDs from messages."""
        test_cases = [
            ("Why was EX-123 classified as high?", ["EX-123"]),
            ("Find similar to EX-456 and EX-789", ["EX-456", "EX-789"]),
            ("Exception 2024-1120 needs review", ["2024-1120"]),
            ("No exception mentioned here", []),
        ]
        
        for message, expected_exceptions in test_cases:
            result = router.detect_intent(message)
            mentioned = result.extracted_params.get('mentioned_exceptions', [])
            assert mentioned == expected_exceptions
            
    def test_date_range_extraction(self, router):
        """Test extraction of date ranges from messages."""
        test_cases = [
            ("Summarize today's exceptions", "today"),
            ("Show yesterday's issues", "yesterday"),
            ("This week's error summary", "this_week"),
            ("Last 24 hours incidents", "last_24h"),
            ("No date mentioned", None),
        ]
        
        for message, expected_range in test_cases:
            result = router.detect_intent(message)
            extracted_range = result.extracted_params.get('date_range')
            assert extracted_range == expected_range
            
    def test_severity_extraction(self, router):
        """Test extraction of severity filters from messages."""
        test_cases = [
            ("Show critical exceptions today", ["critical"]),
            ("High severity issues this week", ["high"]),
            ("Critical and urgent problems", ["critical", "urgent"]),
            ("Medium priority exceptions", ["medium"]),
            ("No severity mentioned", []),
        ]
        
        for message, expected_severities in test_cases:
            result = router.detect_intent(message)
            severities = result.extracted_params.get('severity_filters', [])
            assert set(severities) == set(expected_severities)
            
    def test_contextual_boosting(self, router):
        """Test contextual boosting based on parameters."""
        # Exception ID context should boost SIMILAR_CASES
        result1 = router.detect_intent("Find similar", exception_id="EX-123")
        result2 = router.detect_intent("Find similar")
        
        # With exception context, should be more confident about SIMILAR_CASES
        assert result1.intent_type == IntentType.SIMILAR_CASES
        assert result2.intent_type == IntentType.SIMILAR_CASES
        assert result1.confidence >= result2.confidence
        
    def test_confidence_scoring(self, router):
        """Test that confidence scores are reasonable and consistent."""
        # Strong matches should have high confidence
        strong_match = router.detect_intent("Summarize today's exceptions")
        assert strong_match.confidence > 0.7
        
        # Weak matches should have lower confidence
        weak_match = router.detect_intent("Maybe show some stuff")
        assert weak_match.confidence < 0.5
        
        # Ambiguous messages should fall back to OTHER
        ambiguous = router.detect_intent("This could be anything")
        assert ambiguous.intent_type == IntentType.OTHER
        
    def test_processing_metadata(self, router):
        """Test that processing metadata is included in results."""
        result = router.detect_intent("Summarize today's exceptions")
        
        metadata = result.processing_metadata
        assert 'scores' in metadata
        assert 'pattern_matches' in metadata
        assert 'contextual_boosts_applied' in metadata
        
        # Should have scores for all intent types
        assert len(metadata['scores']) == len(IntentType)
        
    def test_complex_messages(self, router):
        """Test complex messages with multiple potential intents."""
        complex_cases = [
            # Should prioritize primary intent
            ("Explain why EX-123 was critical and find similar cases", IntentType.EXPLAIN),
            ("Summarize today's issues and recommend next steps", IntentType.SUMMARY),
            ("Find similar to EX-456 and draft response for customer", IntentType.SIMILAR_CASES),
        ]
        
        for message, expected_primary in complex_cases:
            result = router.detect_intent(message)
            assert result.intent_type == expected_primary
            assert result.confidence > 0.5


class TestLLMAssistedRouter:
    """Test the LLM-assisted router extension point."""
    
    def test_llm_router_fallback(self):
        """Test that LLM router falls back to heuristics for MVP."""
        router = LLMAssistedRouter(use_llm=False)
        
        message = "Summarize today's exceptions"
        heuristic_result = router.detect_intent(message)
        
        # For MVP, LLM method should return same result as heuristic
        # (since it falls back to heuristic implementation)
        assert heuristic_result.intent_type == IntentType.SUMMARY
        assert heuristic_result.confidence > 0.5
        
    def test_llm_router_interface(self):
        """Test that LLM router maintains same interface."""
        router = LLMAssistedRouter()
        
        # Should have same interface as base router
        result = router.detect_intent("Test message")
        assert isinstance(result, IntentResult)
        assert isinstance(result.intent_type, IntentType)
        assert 0.0 <= result.confidence <= 1.0


class TestIntentResultStructure:
    """Test the IntentResult structure and data integrity."""
    
    def test_intent_result_completeness(self):
        """Test that IntentResult contains all required fields."""
        router = IntentDetectionRouter()
        result = router.detect_intent("Summarize today's exceptions")
        
        # Check all required fields
        assert hasattr(result, 'intent_type')
        assert hasattr(result, 'confidence')
        assert hasattr(result, 'extracted_params')
        assert hasattr(result, 'raw_message')
        assert hasattr(result, 'processing_metadata')
        
        # Check types
        assert isinstance(result.intent_type, IntentType)
        assert isinstance(result.confidence, float)
        assert isinstance(result.extracted_params, dict)
        assert isinstance(result.raw_message, str)
        assert isinstance(result.processing_metadata, dict)
        
    def test_confidence_bounds(self):
        """Test that confidence is always within valid bounds."""
        router = IntentDetectionRouter()
        
        test_messages = [
            "Summarize today's exceptions",
            "Why was EX-123 classified as high?", 
            "Find similar to EX-456",
            "Random text with no clear intent",
            "",
            "Very long message with multiple keywords summarize explain similar playbook draft workflow"
        ]
        
        for message in test_messages:
            result = router.detect_intent(message)
            assert 0.0 <= result.confidence <= 1.0
            
    def test_extracted_params_structure(self):
        """Test structure and types of extracted parameters."""
        router = IntentDetectionRouter()
        result = router.detect_intent(
            "Summarize today's critical exceptions EX-123", 
            exception_id="EX-456",
            tenant_id="tenant-1",
            domain="finance"
        )
        
        params = result.extracted_params
        
        # Test context preservation
        assert params.get('tenant_id') == "tenant-1"
        assert params.get('domain') == "finance"
        
        # Test extraction from message
        assert 'mentioned_exceptions' in params
        assert 'date_range' in params
        assert 'severity_filters' in params
        
        # Test types
        if 'mentioned_exceptions' in params:
            assert isinstance(params['mentioned_exceptions'], list)
        if 'severity_filters' in params:
            assert isinstance(params['severity_filters'], list)
            
    def test_enum_coverage(self):
        """Test that all IntentType enum values are covered."""
        router = IntentDetectionRouter()
        
        # Test messages that should trigger each intent type
        intent_examples = {
            IntentType.SUMMARY: "Summarize today's exceptions",
            IntentType.EXPLAIN: "Why was EX-123 classified as high?",
            IntentType.SIMILAR_CASES: "Find similar to EX-123",
            IntentType.RECOMMEND_PLAYBOOK: "Recommend playbook for this",
            IntentType.DRAFT_RESPONSE: "Draft response for customer",
            IntentType.WORKFLOW_VIEW: "Show workflow for this exception",
            IntentType.OTHER: "Random unrelated text"
        }
        
        detected_intents = set()
        for expected_intent, message in intent_examples.items():
            result = router.detect_intent(message)
            detected_intents.add(result.intent_type)
            
        # Verify we can detect all intent types
        assert detected_intents == set(IntentType)