"""
Base agent class and interfaces.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.models.agent_contracts import AgentDecision
from src.models.exception_record import ExceptionRecord


class BaseAgent(ABC):
    """
    Base class for all agents.
    All agents must implement the process method.
    """

    @abstractmethod
    async def process(
        self, exception: ExceptionRecord, context: Optional[Dict[str, Any]] = None
    ) -> AgentDecision:
        """
        Process an exception and return agent response.
        
        Args:
            exception: Canonical exception to process
            context: Additional context from previous agents
            
        Returns:
            AgentResponse with decision, confidence, evidence, and next step
        """
        pass

