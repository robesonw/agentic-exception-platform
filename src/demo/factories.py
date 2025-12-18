"""
Data factories for generating realistic demo data.

Uses Faker for realistic data generation with deterministic seeds.
"""

import random
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from faker import Faker

from src.demo.templates import (
    AGENT_ACTORS,
    EVENT_TYPES,
    FINANCE_ENTITIES,
    FINANCE_EXCEPTION_TYPES,
    FINANCE_PLAYBOOK_NAMES,
    FINANCE_SOURCE_SYSTEMS,
    FINANCE_TOOL_NAMES,
    get_finance_playbook_conditions,
    get_healthcare_playbook_conditions,
    get_playbook_steps,
    HEALTHCARE_ENTITIES,
    HEALTHCARE_EXCEPTION_TYPES,
    HEALTHCARE_PLAYBOOK_NAMES,
    HEALTHCARE_SOURCE_SYSTEMS,
    HEALTHCARE_TOOL_NAMES,
    SYSTEM_ACTORS,
    USER_ACTORS,
)
from src.infrastructure.db.models import (
    ActorType,
    ExceptionSeverity,
    ExceptionStatus,
    TenantStatus,
    ToolExecutionStatus,
)

fake = Faker()


class DemoDataFactory:
    """Factory for generating realistic demo data."""

    def __init__(self, seed: int | None = None):
        """
        Initialize factory with optional seed for determinism.
        
        Args:
            seed: Random seed for deterministic generation
        """
        if seed is not None:
            random.seed(seed)
            Faker.seed(seed)
            fake.seed_instance(seed)

    def generate_exception_id(self, tenant_id: str, index: int) -> str:
        """Generate a realistic exception ID."""
        domain_prefix = "FIN" if "FINANCE" in tenant_id.upper() else "HLTH"
        return f"EXC-{domain_prefix}-{datetime.now().strftime('%Y%m%d')}-{index:05d}"

    def generate_exception_type(self, domain: str) -> str:
        """Generate exception type based on domain."""
        if domain == "CapitalMarketsTrading":
            return random.choice(FINANCE_EXCEPTION_TYPES)
        elif domain == "HealthcareClaimsAndCareOps":
            return random.choice(HEALTHCARE_EXCEPTION_TYPES)
        return "UNKNOWN_EXCEPTION"

    def generate_severity(self, exception_type: str) -> ExceptionSeverity:
        """Generate severity based on exception type."""
        # Critical exceptions
        if any(x in exception_type for x in ["PHARMACY_DUPLICATE_THERAPY", "SETTLEMENT_FAILURE"]):
            return ExceptionSeverity.CRITICAL
        
        # High severity
        if any(x in exception_type for x in ["CLAIM_MISSING_AUTH", "PROVIDER_CREDENTIAL", "ALLOCATION"]):
            return ExceptionSeverity.HIGH
        
        # Medium severity
        if any(x in exception_type for x in ["CLAIM_CODE", "POSITION", "REG_REPORT"]):
            return ExceptionSeverity.MEDIUM
        
        # Low severity (default)
        return ExceptionSeverity.LOW

    def generate_status(self) -> ExceptionStatus:
        """Generate exception status."""
        weights = [0.4, 0.3, 0.2, 0.1]  # open, analyzing, resolved, escalated
        return random.choices(
            [ExceptionStatus.OPEN, ExceptionStatus.ANALYZING, ExceptionStatus.RESOLVED, ExceptionStatus.ESCALATED],
            weights=weights,
        )[0]

    def generate_created_at(self, days_back: int = 7) -> datetime:
        """Generate created_at timestamp within last N days."""
        now = datetime.now(timezone.utc)
        days_ago = random.randint(0, days_back)
        hours_ago = random.randint(0, 23)
        minutes_ago = random.randint(0, 59)
        
        return now - timedelta(days=days_ago, hours=hours_ago, minutes=minutes_ago)

    def generate_sla_deadline(self, created_at: datetime, severity: ExceptionSeverity) -> datetime | None:
        """Generate SLA deadline based on severity."""
        if random.random() < 0.3:  # 30% have no SLA
            return None
        
        # SLA windows based on severity
        sla_hours = {
            ExceptionSeverity.CRITICAL: 2,
            ExceptionSeverity.HIGH: 8,
            ExceptionSeverity.MEDIUM: 24,
            ExceptionSeverity.LOW: 72,
        }
        
        hours = sla_hours.get(severity, 24)
        # Add some variance
        hours += random.randint(-2, 4)
        
        deadline = created_at + timedelta(hours=hours)
        
        # Some deadlines are in the past (breached or near breach)
        if random.random() < 0.2:
            deadline = datetime.now(timezone.utc) - timedelta(minutes=random.randint(0, 120))
        
        return deadline

    def generate_amount(self, domain: str) -> Decimal | None:
        """Generate amount based on domain."""
        if random.random() < 0.3:  # 30% have no amount
            return None
        
        if domain == "CapitalMarketsTrading":
            # Finance: larger amounts
            amount = random.uniform(1000.0, 1000000.0)
        else:
            # Healthcare: smaller amounts
            amount = random.uniform(100.0, 50000.0)
        
        return Decimal(str(round(amount, 2)))

    def generate_entity(self, domain: str) -> str | None:
        """Generate entity identifier."""
        if random.random() < 0.2:  # 20% have no entity
            return None
        
        if domain == "CapitalMarketsTrading":
            return random.choice(FINANCE_ENTITIES)
        else:
            return random.choice(HEALTHCARE_ENTITIES)

    def generate_source_system(self, domain: str) -> str:
        """Generate source system name."""
        if domain == "CapitalMarketsTrading":
            return random.choice(FINANCE_SOURCE_SYSTEMS)
        else:
            return random.choice(HEALTHCARE_SOURCE_SYSTEMS)

    def generate_owner(self, status: ExceptionStatus) -> str | None:
        """Generate owner based on status."""
        if status == ExceptionStatus.RESOLVED:
            return random.choice(AGENT_ACTORS + USER_ACTORS)
        elif status == ExceptionStatus.ANALYZING:
            return random.choice(AGENT_ACTORS)
        elif status == ExceptionStatus.ESCALATED:
            return random.choice(USER_ACTORS)
        return None

    def generate_raw_payload(self, domain: str, exception_type: str, entity: str | None) -> dict[str, Any]:
        """Generate realistic raw payload."""
        payload: dict[str, Any] = {
            "source": "demo_seeder",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if domain == "CapitalMarketsTrading":
            payload.update({
                "orderId": f"ORD-{random.randint(10000, 99999)}",
                "tradeDate": fake.date().isoformat(),
                "counterparty": entity or "UNKNOWN",
                "amount": str(self.generate_amount(domain)),
            })
        else:
            payload.update({
                "claimId": f"CLM-{random.randint(10000, 99999)}",
                "patientId": entity or "UNKNOWN",
                "serviceDate": fake.date().isoformat(),
                "amount": str(self.generate_amount(domain)),
            })
        
        return payload

    def generate_normalized_context(self, domain: str, exception_type: str) -> dict[str, Any]:
        """Generate normalized context."""
        return {
            "domain": domain,
            "exceptionType": exception_type,
            "normalizedAt": datetime.now(timezone.utc).isoformat(),
        }

    def generate_playbook_conditions(self, domain: str, exception_type: str, severity: ExceptionSeverity) -> dict[str, Any]:
        """Generate playbook matching conditions."""
        if domain == "CapitalMarketsTrading":
            return get_finance_playbook_conditions(exception_type, severity.value)
        else:
            return get_healthcare_playbook_conditions(exception_type, severity.value)

    def generate_playbook_steps(self, include_tool: bool = True) -> list[dict[str, Any]]:
        """Generate playbook steps."""
        action_types = ["notify", "assign_owner", "set_status"]
        
        if random.random() < 0.5:
            action_types.append("add_comment")
        
        if include_tool and random.random() < 0.7:
            action_types.append("call_tool")
        
        if random.random() < 0.3:
            action_types.append("escalate")
        
        return get_playbook_steps(action_types)

    def generate_tool_config(self, tool_name: str, tool_type: str, is_global: bool = False) -> dict[str, Any]:
        """Generate tool configuration."""
        config: dict[str, Any] = {
            "type": tool_type,
            "description": f"Demo tool: {tool_name}",
        }
        
        if tool_type == "http" or tool_type == "rest":
            # Use localhost dummy endpoint for demo
            config.update({
                "endpoint": f"http://localhost:8000/demo/tools/{tool_name}",
                "method": "POST",
                "auth": {
                    "type": "apiKey",
                    "header": "X-API-Key",
                    "value": "demo-key-12345",  # Masked in logs
                },
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "orderId": {"type": "string", "description": "Order identifier"},
                        "params": {"type": "object", "description": "Additional parameters"},
                    },
                    "required": ["orderId"],
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "success": {"type": "boolean"},
                        "data": {"type": "object"},
                        "message": {"type": "string"},
                    },
                },
            })
        elif tool_type == "dummy":
            config.update({
                "provider": "dummy",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "input": {"type": "string"},
                    },
                },
                "output_schema": {
                    "type": "object",
                    "properties": {
                        "output": {"type": "string"},
                    },
                },
            })
        else:
            config.update({
                "endpoint": f"http://localhost:8000/demo/tools/{tool_name}",
            })
        
        return config

    def generate_event_payload(self, event_type: str, exception_id: str, **kwargs: Any) -> dict[str, Any]:
        """Generate event payload."""
        payload: dict[str, Any] = {
            "eventType": event_type,
            "exceptionId": exception_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        if event_type == "TriageCompleted":
            payload["suggestedPlaybookId"] = kwargs.get("playbook_id")
            payload["confidence"] = round(random.uniform(0.7, 0.95), 2)
        
        elif event_type == "PolicyEvaluated":
            payload["selectedPlaybookId"] = kwargs.get("playbook_id")
            payload["reasoning"] = "Playbook matched based on exception type and severity"
            payload["confidence"] = round(random.uniform(0.75, 0.98), 2)
        
        elif event_type == "PlaybookStepCompleted":
            payload["stepOrder"] = kwargs.get("step_order", 1)
            payload["stepName"] = kwargs.get("step_name", "Step")
            payload["actionType"] = kwargs.get("action_type", "notify")
        
        elif event_type in ["ToolExecutionRequested", "ToolExecutionCompleted", "ToolExecutionFailed"]:
            payload["toolId"] = kwargs.get("tool_id")
            payload["toolName"] = kwargs.get("tool_name", "unknown")
            if event_type == "ToolExecutionCompleted":
                payload["output"] = {"success": True, "data": {"result": "demo_result"}}
            elif event_type == "ToolExecutionFailed":
                payload["error"] = "Demo error message"
        
        elif event_type == "ResolutionSuggested":
            payload["resolution"] = "Exception resolved via playbook execution"
            payload["confidence"] = round(random.uniform(0.8, 0.95), 2)
        
        elif event_type == "FeedbackCaptured":
            payload["feedback"] = kwargs.get("feedback", "positive")
            payload["rating"] = random.randint(1, 5)
        
        return payload

    def generate_actor(self, event_type: str) -> tuple[ActorType, str]:
        """Generate actor type and ID based on event type."""
        if event_type in ["ExceptionIngested", "ExceptionCreated"]:
            return ActorType.SYSTEM, random.choice(SYSTEM_ACTORS)
        elif event_type in ["TriageCompleted", "PolicyEvaluated", "ResolutionSuggested"]:
            return ActorType.AGENT, random.choice(AGENT_ACTORS)
        elif event_type in ["PlaybookStarted", "PlaybookStepCompleted", "ToolExecutionRequested"]:
            return ActorType.AGENT, random.choice(AGENT_ACTORS)
        elif event_type == "FeedbackCaptured":
            return ActorType.USER, random.choice(USER_ACTORS)
        else:
            return ActorType.SYSTEM, random.choice(SYSTEM_ACTORS)

    def generate_tool_execution_input(self, tool_name: str) -> dict[str, Any]:
        """Generate tool execution input payload."""
        return {
            "tool": tool_name,
            "params": {
                "orderId": f"ORD-{random.randint(10000, 99999)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

    def generate_tool_execution_output(self, success: bool = True) -> dict[str, Any] | None:
        """Generate tool execution output payload."""
        if not success:
            return None
        
        return {
            "success": True,
            "data": {
                "result": "demo_execution_result",
                "processedAt": datetime.now(timezone.utc).isoformat(),
            },
            "message": "Tool execution completed successfully",
        }





