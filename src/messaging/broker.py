"""
Message broker abstraction interface.

Defines the contract for message broker implementations (Kafka, Azure Event Hubs,
AWS MSK, RabbitMQ, etc.).
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Optional


class Broker(ABC):
    """
    Abstract base class for message broker implementations.
    
    Provides a pluggable interface for different message broker backends,
    allowing the platform to support Kafka, Azure Event Hubs, AWS MSK,
    RabbitMQ, and other messaging systems.
    """

    @abstractmethod
    def publish(
        self,
        topic: str,
        key: Optional[str],
        value: bytes | str | dict[str, Any],
    ) -> None:
        """
        Publish a message to a topic.
        
        Args:
            topic: The topic name to publish to
            key: Optional partition key (for Kafka, this determines partition)
            value: Message payload (bytes, string, or dict that will be serialized)
            
        Raises:
            BrokerError: If publishing fails after retries
        """
        pass

    @abstractmethod
    def subscribe(
        self,
        topics: list[str],
        group_id: str,
        handler: Callable[[str, Optional[str], bytes], None],
    ) -> None:
        """
        Subscribe to one or more topics and process messages with a handler.
        
        Args:
            topics: List of topic names to subscribe to
            group_id: Consumer group ID (for Kafka, enables load balancing)
            handler: Callback function that processes messages.
                    Signature: handler(topic: str, key: Optional[str], value: bytes) -> None
                    
        Note:
            This method should block and process messages until interrupted.
            For async implementations, consider using asyncio or threading.
        """
        pass

    @abstractmethod
    def health(self) -> dict[str, Any]:
        """
        Check broker health and connection status.
        
        Returns:
            Dictionary with health information:
            - status: "healthy" | "unhealthy" | "degraded"
            - details: Additional information about broker state
            - connected: Boolean indicating if broker is reachable
            
        Raises:
            BrokerError: If health check fails
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Close broker connections and clean up resources.
        
        Should be called during graceful shutdown.
        """
        pass


class BrokerError(Exception):
    """Base exception for broker-related errors."""
    pass


class BrokerConnectionError(BrokerError):
    """Raised when broker connection fails."""
    pass


class BrokerPublishError(BrokerError):
    """Raised when message publishing fails."""
    pass


class BrokerSubscribeError(BrokerError):
    """Raised when subscription fails."""
    pass


def get_broker() -> "Broker":
    """
    Get broker instance (factory function).
    
    This is a convenience function that can be overridden by implementations.
    Default implementation raises NotImplementedError.
    
    Returns:
        Broker instance
        
    Raises:
        NotImplementedError: If not implemented by concrete broker module
    """
    raise NotImplementedError(
        "get_broker() must be implemented by concrete broker module. "
        "Use src.messaging.get_broker() instead."
    )


