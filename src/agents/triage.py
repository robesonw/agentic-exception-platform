"""
TriageAgent implementation for MVP.
Classifies exceptions and assigns severity using domain pack rules.
Matches specification from docs/04-agent-templates.md
"""

import logging
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack, ExceptionTypeDefinition
from src.models.exception_record import ExceptionRecord, Severity
from src.memory.index import MemoryIndexRegistry


class TriageAgentError(Exception):
    """Raised when TriageAgent operations fail."""

    pass


# Severity priority mapping for comparison
SEVERITY_PRIORITY = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 4,
}


class TriageAgent:
    """
    TriageAgent classifies exceptions and assigns severity.
    
    Responsibilities:
    - Classify exceptionType using domain pack taxonomy
    - Score severity using severityRules from domain pack
    - Select highest matching severity or use defaultSeverity
    - Produce AgentDecision with classification, severity, next stage = "policy"
    - Log triage decision with AuditLogger
    """

    def __init__(
        self,
        domain_pack: DomainPack,
        audit_logger: Optional[AuditLogger] = None,
        memory_index: Optional[MemoryIndexRegistry] = None,
    ):
        """
        Initialize TriageAgent.
        
        Args:
            domain_pack: Domain Pack containing exception types and severity rules
            audit_logger: Optional AuditLogger for logging
            memory_index: Optional MemoryIndexRegistry for RAG similarity search
        """
        self.domain_pack = domain_pack
        self.audit_logger = audit_logger
        self.memory_index = memory_index

    async def process(
        self,
        exception: ExceptionRecord,
        context: Optional[dict[str, Any]] = None,
    ) -> AgentDecision:
        """
        Classify exception, score severity, and generate diagnostic summary.
        
        Args:
            exception: Normalized ExceptionRecord from IntakeAgent
            context: Optional context from previous agents
            
        Returns:
            AgentDecision with triage results
            
        Raises:
            TriageAgentError: If classification fails
        """
        # Classify exception type if not already set
        classified_type = self._classify_exception_type(exception)
        
        # Optional: Search similar exceptions via RAG (if memory index available)
        similar_exceptions = []
        if self.memory_index:
            try:
                similar_exceptions = self.memory_index.search_similar(exception.tenant_id, exception, k=5)
                if similar_exceptions:
                    # Use similar exceptions to help with classification if needed
                    # For MVP, we just log that similar exceptions were found
                    logger.debug(f"Found {len(similar_exceptions)} similar exceptions for classification")
            except Exception as e:
                # Gracefully handle RAG search failures
                logger.warning(f"RAG search failed: {e}, continuing without similarity search")
        
        # Evaluate severity rules
        severity = self._evaluate_severity(exception, classified_type)
        
        # Update exception with classification and severity
        exception.exception_type = classified_type
        exception.severity = severity
        
        # Create agent decision
        decision = self._create_decision(exception, classified_type, severity)
        
        # Log the event
        if self.audit_logger:
            input_data = {
                "exception": exception.model_dump(),
                "context": context or {},
            }
            self.audit_logger.log_agent_event("TriageAgent", input_data, decision, exception.tenant_id)
        
        return decision

    def _classify_exception_type(self, exception: ExceptionRecord) -> str:
        """
        Classify exception type from domain pack taxonomy.
        
        If exception type is already set, validates it exists in domain pack.
        Otherwise, attempts to infer from raw payload or uses first available type.
        
        Args:
            exception: ExceptionRecord to classify
            
        Returns:
            Classified exception type name
            
        Raises:
            TriageAgentError: If classification fails
        """
        # If exception type is already set, validate it exists
        if exception.exception_type:
            if exception.exception_type in self.domain_pack.exception_types:
                return exception.exception_type
            else:
                raise TriageAgentError(
                    f"Exception type '{exception.exception_type}' not found in domain pack. "
                    f"Valid types: {sorted(self.domain_pack.exception_types.keys())}"
                )
        
        # Try to infer from raw payload
        # Look for common fields that might indicate exception type
        raw_payload = exception.raw_payload
        
        # Check for explicit exception type in payload
        payload_type = raw_payload.get("exceptionType") or raw_payload.get("exception_type")
        if payload_type and payload_type in self.domain_pack.exception_types:
            return payload_type
        
        # Check for error messages or codes that might match exception type descriptions
        error_msg = str(raw_payload.get("error", "")).upper()
        error_code = str(raw_payload.get("errorCode", "")).upper()
        
        # Try to match against exception type names
        for exc_type, exc_def in self.domain_pack.exception_types.items():
            if exc_type.upper() in error_msg or exc_type.upper() in error_code:
                return exc_type
        
        # If no match found, raise error (cannot proceed without classification)
        raise TriageAgentError(
            f"Could not classify exception type. Available types: {sorted(self.domain_pack.exception_types.keys())}"
        )

    def _evaluate_severity(
        self, exception: ExceptionRecord, exception_type: str
    ) -> Severity:
        """
        Evaluate severity using domain pack severity rules.
        
        Selects the highest matching severity from rules, or falls back to
        defaultSeverity from exception type definition.
        
        Args:
            exception: ExceptionRecord to evaluate
            exception_type: Classified exception type
            
        Returns:
            Severity enum value
        """
        matching_severities = []
        
        # Evaluate each severity rule
        for rule in self.domain_pack.severity_rules:
            if self._evaluate_rule_condition(rule.condition, exception, exception_type):
                matching_severities.append(rule.severity)
        
        # Select highest severity from matching rules
        if matching_severities:
            highest = max(matching_severities, key=lambda s: SEVERITY_PRIORITY.get(s.upper(), 0))
            return Severity(highest.upper())
        
        # Fall back to defaultSeverity from exception type definition
        # Note: The sample JSON files have defaultSeverity, but our model doesn't capture it yet
        # For MVP, we'll use a severity priority mapping based on common patterns
        # or default to MEDIUM if no rules match
        
        # Try to infer from exception type name patterns
        exc_type_upper = exception_type.upper()
        if "CRITICAL" in exc_type_upper or "BREAK" in exc_type_upper:
            return Severity.CRITICAL
        elif "HIGH" in exc_type_upper or "FAIL" in exc_type_upper:
            return Severity.HIGH
        elif "LOW" in exc_type_upper or "MISMATCH" in exc_type_upper:
            return Severity.LOW
        
        # Default fallback
        return Severity.MEDIUM

    def _evaluate_rule_condition(
        self, condition: str, exception: ExceptionRecord, exception_type: str
    ) -> bool:
        """
        Evaluate a severity rule condition.
        
        Supports simple conditions like:
        - exceptionType == "SomeType"
        - exceptionType == "SomeType" && rawPayload.field == value
        
        Args:
            condition: Condition string to evaluate (may use "if" format from samples)
            exception: ExceptionRecord to evaluate against
            exception_type: Classified exception type
            
        Returns:
            True if condition matches, False otherwise
        """
        # Handle "if" format from sample files (e.g., "if: exceptionType == 'X'")
        # Extract the actual condition if it starts with "if:"
        if condition.strip().startswith("if:"):
            condition = condition.strip()[3:].strip()
        
        # Simple condition evaluation
        # Handle common patterns from sample files
        
        # Handle simple equality checks with exceptionType
        if "exceptionType" in condition and "==" in condition:
            # Pattern: exceptionType == "SomeType"
            parts = condition.split("==")
            if len(parts) == 2:
                right = parts[1].strip().strip('"').strip("'")
                return exception_type == right
        
        # Handle && (AND) conditions
        if "&&" in condition:
            parts = condition.split("&&")
            return all(self._evaluate_rule_condition(p.strip(), exception, exception_type) for p in parts)
        
        # Handle || (OR) conditions
        if "||" in condition:
            parts = condition.split("||")
            return any(self._evaluate_rule_condition(p.strip(), exception, exception_type) for p in parts)
        
        # Handle rawPayload field access (e.g., rawPayload.impact == 'ECONOMIC')
        if "rawPayload" in condition and "==" in condition:
            # Extract field path and value
            # Pattern: rawPayload.field == value
            if "rawPayload." in condition:
                field_part = condition.split("rawPayload.")[1].split("==")[0].strip()
                value_part = condition.split("==")[1].strip().strip('"').strip("'")
                field_value = exception.raw_payload.get(field_part)
                return str(field_value) == value_part
        
        # Default: try simple string matching
        return exception_type in condition

    def _create_decision(
        self, exception: ExceptionRecord, exception_type: str, severity: Severity
    ) -> AgentDecision:
        """
        Create agent decision from triage results.
        
        Args:
            exception: ExceptionRecord with classification and severity
            exception_type: Classified exception type
            severity: Assigned severity
            
        Returns:
            AgentDecision
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Classified as: {exception_type}")
        evidence.append(f"Severity: {severity.value}")
        
        # Add exception type description if available
        exc_type_def = self.domain_pack.exception_types.get(exception_type)
        if exc_type_def:
            evidence.append(f"Description: {exc_type_def.description}")
        
        # Add matched severity rules
        matched_rules = []
        for rule in self.domain_pack.severity_rules:
            if self._evaluate_rule_condition(rule.condition, exception, exception_type):
                matched_rules.append(f"{rule.condition} -> {rule.severity}")
        
        if matched_rules:
            evidence.append(f"Matched severity rules: {len(matched_rules)}")
            evidence.extend(matched_rules)
        else:
            evidence.append("No severity rules matched (using default)")
        
        # Add similar exceptions info if available (from RAG search)
        # Note: This would be populated in process() method if memory_index is available
        # For now, we'll add it as a placeholder in evidence if needed

        # Calculate confidence
        # Higher confidence if exception type was already set and severity rules matched
        if exception.exception_type == exception_type and matched_rules:
            confidence = 0.9
        elif matched_rules:
            confidence = 0.85
        elif exception.exception_type == exception_type:
            confidence = 0.8
        else:
            confidence = 0.7  # Lower if we had to infer type

        decision_text = f"Triaged {exception_type} {severity.value}"

        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep="ProceedToPolicy",
        )
