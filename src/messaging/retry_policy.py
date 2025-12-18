"""
Retry policy configuration per event type.

Reference: docs/phase9-async-scale-mvp.md Section 7.3
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class RetryPolicy:
    """
    Retry policy configuration for an event type.
    
    Attributes:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay_seconds: Initial delay before first retry (default: 1.0)
        max_delay_seconds: Maximum delay between retries (default: 300.0)
        backoff_multiplier: Exponential backoff multiplier (default: 2.0)
        jitter: Whether to add random jitter to delays (default: True)
    """
    
    max_retries: int = 3
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 300.0
    backoff_multiplier: float = 2.0
    jitter: bool = True
    
    def calculate_delay(self, attempt_number: int) -> float:
        """
        Calculate delay for a given retry attempt using exponential backoff.
        
        Args:
            attempt_number: The retry attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff: initial_delay * (multiplier ^ (attempt - 1))
        delay = self.initial_delay_seconds * (self.backoff_multiplier ** (attempt_number - 1))
        
        # Cap at max_delay
        delay = min(delay, self.max_delay_seconds)
        
        # Add jitter if enabled (random variation up to 20% of delay)
        if self.jitter:
            import random
            jitter_amount = delay * 0.2 * random.random()
            delay = delay + jitter_amount
        
        return delay


class RetryPolicyRegistry:
    """
    Registry for retry policies per event type.
    
    Provides default policies and allows per-event-type customization.
    """
    
    def __init__(self):
        """Initialize retry policy registry with defaults."""
        # Default policy
        self._default_policy = RetryPolicy()
        
        # Per-event-type policies
        self._policies: dict[str, RetryPolicy] = {}
        
        # Set up default policies for common event types
        self._setup_default_policies()
    
    def _setup_default_policies(self) -> None:
        """Set up default policies for common event types."""
        # Critical events: more retries, longer delays
        self._policies["ExceptionIngested"] = RetryPolicy(
            max_retries=5,
            initial_delay_seconds=2.0,
            max_delay_seconds=600.0,
            backoff_multiplier=2.0,
        )
        
        # Tool execution: moderate retries
        self._policies["ToolExecutionRequested"] = RetryPolicy(
            max_retries=3,
            initial_delay_seconds=1.0,
            max_delay_seconds=300.0,
            backoff_multiplier=2.0,
        )
        
        # Feedback events: fewer retries (non-critical)
        self._policies["FeedbackCaptured"] = RetryPolicy(
            max_retries=2,
            initial_delay_seconds=0.5,
            max_delay_seconds=60.0,
            backoff_multiplier=2.0,
        )
    
    def get_policy(self, event_type: str) -> RetryPolicy:
        """
        Get retry policy for an event type.
        
        Args:
            event_type: Event type string
            
        Returns:
            RetryPolicy instance (default if not configured)
        """
        return self._policies.get(event_type, self._default_policy)
    
    def set_policy(self, event_type: str, policy: RetryPolicy) -> None:
        """
        Set retry policy for an event type.
        
        Args:
            event_type: Event type string
            policy: RetryPolicy instance
        """
        self._policies[event_type] = policy
    
    def get_max_retries(self, event_type: str) -> int:
        """
        Get maximum retries for an event type.
        
        Args:
            event_type: Event type string
            
        Returns:
            Maximum number of retries
        """
        return self.get_policy(event_type).max_retries
    
    def calculate_delay(self, event_type: str, attempt_number: int) -> float:
        """
        Calculate retry delay for an event type and attempt number.
        
        Args:
            event_type: Event type string
            attempt_number: Retry attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        policy = self.get_policy(event_type)
        return policy.calculate_delay(attempt_number)



