"""
Basic structure tests to verify scaffolding is in place.
"""

import pytest


def test_imports():
    """Test that all main modules can be imported."""
    from src.api.main import app
    from src.models.exception_record import ExceptionRecord, Severity, ResolutionStatus
    from src.models.agent_contracts import AgentDecision
    from src.models.domain_pack import DomainPack
    from src.models.tenant_policy import TenantPolicyPack
    from src.agents.base import BaseAgent
    from src.agents.intake import IntakeAgent
    from src.agents.triage import TriageAgent
    from src.agents.policy import PolicyAgent
    from src.agents.resolution import ResolutionAgent
    from src.agents.feedback import FeedbackAgent
    from src.orchestrator.pipeline import AgentOrchestrator
    from src.tools.registry import ToolRegistry
    from src.tools.invoker import ToolInvoker
    from src.domainpack.loader import DomainPackLoader
    from src.tenantpack.loader import TenantPackLoader
    from src.audit.logger import AuditLogger
    from src.audit.metrics import MetricsCollector

    assert app is not None
    assert ExceptionRecord is not None
    assert AgentDecision is not None


def test_fastapi_app_exists():
    """Test that FastAPI app is configured."""
    from src.api.main import app

    assert app.title == "Agentic Exception Processing Platform"
    assert app.version == "0.1.0"

