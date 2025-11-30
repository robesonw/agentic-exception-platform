"""
Policy Violation and Unauthorized Tool Usage Detection.

Phase 3: Detects when decisions violate tenant/domain policies or when tools
are used outside allow-lists. Provides real-time alerts and automatic blocking.

Matches specification from phase3-mvp-issues.md P3-22.
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field, ConfigDict

from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, Guardrails, ToolDefinition
from src.models.exception_record import ExceptionRecord
from src.models.tenant_policy import TenantPolicyPack
from src.notify.service import NotificationService
from src.observability.metrics import MetricsCollector

logger = logging.getLogger(__name__)


class ViolationSeverity(str, Enum):
    """Severity levels for violations."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class PolicyViolation(BaseModel):
    """Policy violation record."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique violation identifier")
    tenant_id: str = Field(..., alias="tenantId", min_length=1, description="Tenant identifier")
    exception_id: str = Field(..., alias="exceptionId", min_length=1, description="Exception identifier")
    agent_name: str = Field(..., alias="agentName", min_length=1, description="Agent that triggered the violation")
    rule_id: Optional[str] = Field(None, alias="ruleId", description="Policy rule identifier that was violated")
    description: str = Field(..., min_length=1, description="Human-readable violation description")
    severity: ViolationSeverity = Field(..., description="Violation severity level")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Violation timestamp"
    )
    decision_summary: Optional[dict[str, Any]] = Field(
        None, alias="decisionSummary", description="Summary of the decision that triggered the violation"
    )


class ToolViolation(BaseModel):
    """Tool usage violation record."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
        populate_by_name=True,
    )

    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique violation identifier")
    tenant_id: str = Field(..., alias="tenantId", min_length=1, description="Tenant identifier")
    exception_id: str = Field(..., alias="exceptionId", min_length=1, description="Exception identifier")
    tool_name: str = Field(..., alias="toolName", min_length=1, description="Tool that triggered the violation")
    description: str = Field(..., min_length=1, description="Human-readable violation description")
    severity: ViolationSeverity = Field(..., description="Violation severity level")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="Violation timestamp"
    )
    tool_call_request: Optional[dict[str, Any]] = Field(
        None, alias="toolCallRequest", description="Tool call request that triggered the violation"
    )


class ViolationDetector:
    """
    Detects policy violations and unauthorized tool usage.
    
    Responsibilities:
    - Check policy decisions against tenant/domain guardrails
    - Check tool calls against allow-lists
    - Record violations and trigger alerts
    - Integrate with metrics and notification services
    """

    def __init__(
        self,
        storage_dir: Optional[Path] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        notification_service: Optional[NotificationService] = None,
    ):
        """
        Initialize violation detector.
        
        Args:
            storage_dir: Directory for storing violation records (default: ./runtime/violations)
            metrics_collector: Optional metrics collector for tracking violations
            notification_service: Optional notification service for alerts
        """
        self.storage_dir = storage_dir or Path("./runtime/violations")
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        self.metrics_collector = metrics_collector
        self.notification_service = notification_service

    def check_policy_decision(
        self,
        tenant_id: str,
        exception_record: ExceptionRecord,
        triage_result: Optional[AgentDecision],
        policy_decision: AgentDecision,
        tenant_policy: TenantPolicyPack,
        domain_pack: Optional[DomainPack] = None,
    ) -> list[PolicyViolation]:
        """
        Check if a policy decision violates tenant/domain policies.
        
        Args:
            tenant_id: Tenant identifier
            exception_record: Exception record being processed
            triage_result: Optional triage agent decision
            policy_decision: Policy agent decision to check
            tenant_policy: Tenant policy pack
            domain_pack: Optional domain pack for guardrails
            
        Returns:
            List of detected policy violations (empty if none)
        """
        violations: list[PolicyViolation] = []
        
        # Get effective guardrails (tenant custom guardrails override domain guardrails)
        guardrails = tenant_policy.custom_guardrails
        if not guardrails and domain_pack:
            guardrails = domain_pack.guardrails
        
        # Check if decision violates guardrails
        if guardrails:
            # Check block lists
            if guardrails.block_lists:
                decision_str = str(policy_decision.decision).upper()
                for blocked_item in guardrails.block_lists:
                    if blocked_item.upper() in decision_str:
                        violation = PolicyViolation(
                            tenant_id=tenant_id,
                            exception_id=exception_record.exception_id,
                            agent_name="PolicyAgent",
                            rule_id=f"block_list_{blocked_item}",
                            description=f"Policy decision violates block list: {blocked_item}",
                            severity=ViolationSeverity.HIGH,
                            decision_summary={
                                "decision": policy_decision.decision,
                                "blocked_item": blocked_item,
                            },
                        )
                        violations.append(violation)
            
            # Check human approval threshold
            if policy_decision.confidence is not None:
                if policy_decision.confidence < guardrails.human_approval_threshold:
                    # If confidence is below threshold but decision is ALLOW without approval
                    if policy_decision.decision == "ALLOW" and "REQUIRE_APPROVAL" not in str(policy_decision.next_step):
                        violation = PolicyViolation(
                            tenant_id=tenant_id,
                            exception_id=exception_record.exception_id,
                            agent_name="PolicyAgent",
                            rule_id="human_approval_threshold",
                            description=f"Decision ALLOW with confidence {policy_decision.confidence:.2f} below threshold {guardrails.human_approval_threshold:.2f} without requiring approval",
                            severity=ViolationSeverity.MEDIUM,
                            decision_summary={
                                "decision": policy_decision.decision,
                                "confidence": policy_decision.confidence,
                                "threshold": guardrails.human_approval_threshold,
                            },
                        )
                        violations.append(violation)
        
        # Check human approval rules
        if tenant_policy.human_approval_rules and triage_result:
            exception_severity = exception_record.severity
            if exception_severity:
                severity_str = exception_severity.value
                for rule in tenant_policy.human_approval_rules:
                    if rule.severity.upper() == severity_str.upper() and rule.require_approval:
                        # Check if decision requires approval
                        if policy_decision.decision == "ALLOW" and "REQUIRE_APPROVAL" not in str(policy_decision.next_step):
                            violation = PolicyViolation(
                                tenant_id=tenant_id,
                                exception_id=exception_record.exception_id,
                                agent_name="PolicyAgent",
                                rule_id=f"human_approval_rule_{rule.severity}",
                                description=f"Severity {severity_str} requires approval but decision is ALLOW without approval",
                                severity=ViolationSeverity.HIGH,
                                decision_summary={
                                    "decision": policy_decision.decision,
                                    "severity": severity_str,
                                    "rule": rule.model_dump(),
                                },
                            )
                            violations.append(violation)
        
        # Check for CRITICAL severity auto-action (should require approval)
        if exception_record.severity and exception_record.severity.value == "CRITICAL":
            if policy_decision.decision == "ALLOW" and "REQUIRE_APPROVAL" not in str(policy_decision.next_step):
                violation = PolicyViolation(
                    tenant_id=tenant_id,
                    exception_id=exception_record.exception_id,
                    agent_name="PolicyAgent",
                    rule_id="critical_severity_auto_action",
                    description="CRITICAL severity exception allowed without approval",
                    severity=ViolationSeverity.CRITICAL,
                    decision_summary={
                        "decision": policy_decision.decision,
                        "severity": "CRITICAL",
                    },
                )
                violations.append(violation)
        
        # Record violations
        for violation in violations:
            self.record_violation(violation)
        
        return violations

    def check_tool_call(
        self,
        tenant_id: str,
        tool_def: ToolDefinition,
        tool_call_request: dict[str, Any],
        tenant_policy: TenantPolicyPack,
        domain_pack: Optional[DomainPack] = None,
        exception_id: Optional[str] = None,
    ) -> Optional[ToolViolation]:
        """
        Check if a tool call is authorized.
        
        Args:
            tenant_id: Tenant identifier
            exception_id: Exception identifier
            tool_def: Tool definition
            tool_call_request: Tool call request (tool_name, args, etc.)
            tenant_policy: Tenant policy pack
            domain_pack: Optional domain pack for guardrails
            
        Returns:
            ToolViolation if unauthorized, None otherwise
        """
        tool_name = tool_def.name
        # Use placeholder if exception_id not provided
        effective_exception_id = exception_id or "unknown"
        
        # Check if tool is in approved tools list
        if tenant_policy.approved_tools:
            if tool_name not in tenant_policy.approved_tools:
                violation = ToolViolation(
                    tenant_id=tenant_id,
                    exception_id=effective_exception_id,
                    tool_name=tool_name,
                    description=f"Tool '{tool_name}' is not in approved tools list",
                    severity=ViolationSeverity.HIGH,
                    tool_call_request=tool_call_request,
                )
                self.record_violation(violation)
                return violation
        
        # Check custom guardrails
        if tenant_policy.custom_guardrails:
            # Check block lists
            if tool_name in tenant_policy.custom_guardrails.block_lists:
                violation = ToolViolation(
                    tenant_id=tenant_id,
                    exception_id=effective_exception_id,
                    tool_name=tool_name,
                    description=f"Tool '{tool_name}' is in block list",
                    severity=ViolationSeverity.CRITICAL,
                    tool_call_request=tool_call_request,
                )
                self.record_violation(violation)
                return violation
            
            # Check allow lists (if present, only allow-listed tools are permitted)
            if tenant_policy.custom_guardrails.allow_lists:
                if tool_name not in tenant_policy.custom_guardrails.allow_lists:
                    violation = ToolViolation(
                        tenant_id=tenant_id,
                        exception_id=effective_exception_id,
                        tool_name=tool_name,
                        description=f"Tool '{tool_name}' is not in allow list",
                        severity=ViolationSeverity.HIGH,
                        tool_call_request=tool_call_request,
                    )
                    self.record_violation(violation)
                    return violation
        
        # Check domain pack guardrails if no tenant custom guardrails
        if not tenant_policy.custom_guardrails and domain_pack and domain_pack.guardrails:
            guardrails = domain_pack.guardrails
            # Check block lists
            if tool_name in guardrails.block_lists:
                violation = ToolViolation(
                    tenant_id=tenant_id,
                    exception_id=effective_exception_id,
                    tool_name=tool_name,
                    description=f"Tool '{tool_name}' is in domain block list",
                    severity=ViolationSeverity.HIGH,
                    tool_call_request=tool_call_request,
                )
                self.record_violation(violation)
                return violation
        
        # No violation detected
        return None

    def record_violation(self, violation: PolicyViolation | ToolViolation) -> None:
        """
        Record a violation to storage, metrics, and notifications.
        
        Args:
            violation: PolicyViolation or ToolViolation to record
        """
        # Write to JSONL file
        violation_file = self.storage_dir / f"{violation.tenant_id}_violations.jsonl"
        with open(violation_file, "a", encoding="utf-8") as f:
            violation_dict = violation.model_dump(by_alias=True, mode="json")
            f.write(json.dumps(violation_dict) + "\n")
        
        logger.warning(
            f"Violation detected: {violation.__class__.__name__} "
            f"(tenant={violation.tenant_id}, exception={violation.exception_id}, severity={violation.severity.value})"
        )
        
        # Emit metrics
        if self.metrics_collector:
            violation_type = "policy" if isinstance(violation, PolicyViolation) else "tool"
            self.metrics_collector.record_violation(
                tenant_id=violation.tenant_id,
                violation_type=violation_type,
                severity=violation.severity.value,
            )
        
        # Send notification for high/critical severity
        if self.notification_service and violation.severity in [
            ViolationSeverity.HIGH,
            ViolationSeverity.CRITICAL,
        ]:
            try:
                # Get notification policies from tenant (would need to be passed in)
                # For MVP, send to default group
                subject = f"Security Violation Alert: {violation.__class__.__name__}"
                message = (
                    f"Violation detected:\n"
                    f"Type: {violation.__class__.__name__}\n"
                    f"Severity: {violation.severity.value}\n"
                    f"Tenant: {violation.tenant_id}\n"
                    f"Exception: {violation.exception_id}\n"
                    f"Description: {violation.description}\n"
                )
                
                # Note: In production, we'd need to pass notification_policies
                # For MVP, we'll just log that notification would be sent
                logger.info(f"Would send violation notification: {subject}")
            except Exception as e:
                logger.error(f"Failed to send violation notification: {e}")

