"""
Unit tests for retry policy configuration.
"""

import pytest

from src.messaging.retry_policy import RetryPolicy, RetryPolicyRegistry


class TestRetryPolicy:
    """Test RetryPolicy."""
    
    def test_default_policy(self):
        """Test default retry policy values."""
        policy = RetryPolicy()
        
        assert policy.max_retries == 3
        assert policy.initial_delay_seconds == 1.0
        assert policy.max_delay_seconds == 300.0
        assert policy.backoff_multiplier == 2.0
        assert policy.jitter is True
    
    def test_calculate_delay_exponential_backoff(self):
        """Test exponential backoff delay calculation."""
        policy = RetryPolicy(
            initial_delay_seconds=1.0,
            backoff_multiplier=2.0,
            max_delay_seconds=100.0,
            jitter=False,
        )
        
        # Attempt 1: 1.0 * (2.0 ^ 0) = 1.0
        delay1 = policy.calculate_delay(1)
        assert delay1 == 1.0
        
        # Attempt 2: 1.0 * (2.0 ^ 1) = 2.0
        delay2 = policy.calculate_delay(2)
        assert delay2 == 2.0
        
        # Attempt 3: 1.0 * (2.0 ^ 2) = 4.0
        delay3 = policy.calculate_delay(3)
        assert delay3 == 4.0
        
        # Attempt 4: 1.0 * (2.0 ^ 3) = 8.0
        delay4 = policy.calculate_delay(4)
        assert delay4 == 8.0
    
    def test_calculate_delay_max_cap(self):
        """Test delay calculation respects max delay cap."""
        policy = RetryPolicy(
            initial_delay_seconds=10.0,
            backoff_multiplier=2.0,
            max_delay_seconds=50.0,
            jitter=False,
        )
        
        # Attempt 1: 10.0
        delay1 = policy.calculate_delay(1)
        assert delay1 == 10.0
        
        # Attempt 2: 20.0
        delay2 = policy.calculate_delay(2)
        assert delay2 == 20.0
        
        # Attempt 3: 40.0
        delay3 = policy.calculate_delay(3)
        assert delay3 == 40.0
        
        # Attempt 4: 80.0 -> capped at 50.0
        delay4 = policy.calculate_delay(4)
        assert delay4 == 50.0
    
    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter."""
        policy = RetryPolicy(
            initial_delay_seconds=10.0,
            backoff_multiplier=2.0,
            max_delay_seconds=100.0,
            jitter=True,
        )
        
        # Calculate multiple times to verify jitter variation
        delays = [policy.calculate_delay(1) for _ in range(10)]
        
        # All delays should be within jitter range (10.0 to 12.0, 20% jitter)
        for delay in delays:
            assert 10.0 <= delay <= 12.0


class TestRetryPolicyRegistry:
    """Test RetryPolicyRegistry."""
    
    def test_default_policy(self):
        """Test default policy for unknown event type."""
        registry = RetryPolicyRegistry()
        
        policy = registry.get_policy("UnknownEvent")
        assert policy.max_retries == 3
        assert policy.initial_delay_seconds == 1.0
    
    def test_event_specific_policy(self):
        """Test event-specific policy configuration."""
        registry = RetryPolicyRegistry()
        
        # Check default policies
        exception_policy = registry.get_policy("ExceptionIngested")
        assert exception_policy.max_retries == 5
        assert exception_policy.initial_delay_seconds == 2.0
        
        tool_policy = registry.get_policy("ToolExecutionRequested")
        assert tool_policy.max_retries == 3
        
        feedback_policy = registry.get_policy("FeedbackCaptured")
        assert feedback_policy.max_retries == 2
    
    def test_set_policy(self):
        """Test setting custom policy for event type."""
        registry = RetryPolicyRegistry()
        
        custom_policy = RetryPolicy(
            max_retries=10,
            initial_delay_seconds=5.0,
        )
        
        registry.set_policy("CustomEvent", custom_policy)
        
        retrieved_policy = registry.get_policy("CustomEvent")
        assert retrieved_policy.max_retries == 10
        assert retrieved_policy.initial_delay_seconds == 5.0
    
    def test_get_max_retries(self):
        """Test getting max retries for event type."""
        registry = RetryPolicyRegistry()
        
        assert registry.get_max_retries("ExceptionIngested") == 5
        assert registry.get_max_retries("ToolExecutionRequested") == 3
        assert registry.get_max_retries("UnknownEvent") == 3  # Default
    
    def test_calculate_delay(self):
        """Test calculating delay for event type."""
        registry = RetryPolicyRegistry()
        
        # Use a policy without jitter for predictable results
        custom_policy = RetryPolicy(
            initial_delay_seconds=2.0,
            backoff_multiplier=2.0,
            max_delay_seconds=100.0,
            jitter=False,
        )
        registry.set_policy("TestEvent", custom_policy)
        
        delay1 = registry.calculate_delay("TestEvent", 1)
        assert delay1 == 2.0
        
        delay2 = registry.calculate_delay("TestEvent", 2)
        assert delay2 == 4.0
        
        delay3 = registry.calculate_delay("TestEvent", 3)
        assert delay3 == 8.0



