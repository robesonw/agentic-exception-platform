"""
IntakeAgent implementation for MVP.
Normalizes raw exception payloads to canonical ExceptionRecord schema.
Matches specification from docs/04-agent-templates.md
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from src.audit.logger import AuditLogger
from src.models.agent_contracts import AgentDecision
from src.models.domain_pack import DomainPack
from src.models.exception_record import ExceptionRecord, ResolutionStatus

logger = logging.getLogger(__name__)


class IntakeAgentError(Exception):
    """Raised when IntakeAgent operations fail."""

    pass


class IntakeAgent:
    """
    IntakeAgent normalizes raw exception payloads to canonical schema.
    
    Responsibilities:
    - Normalize raw exception into ExceptionRecord model
    - Validate domainPack.exceptionTypes contains the given exceptionType
    - Assign initial metadata: timestamp, tenantId, pipelineId
    - Produce structured AgentDecision with normalized exception
    - Log all operations via AuditLogger
    """

    def __init__(
        self,
        domain_pack: Optional[DomainPack] = None,
        audit_logger: Optional[AuditLogger] = None,
    ):
        """
        Initialize IntakeAgent.
        
        Args:
            domain_pack: Optional Domain Pack for validation
            audit_logger: Optional AuditLogger for logging
        """
        self.domain_pack = domain_pack
        self.audit_logger = audit_logger

    async def process(
        self,
        raw_exception: dict[str, Any] | ExceptionRecord,
        tenant_id: Optional[str] = None,
        pipeline_id: Optional[str] = None,
    ) -> tuple[ExceptionRecord, AgentDecision]:
        """
        Normalize raw exception to canonical schema.
        
        Args:
            raw_exception: Raw exception dict or partial ExceptionRecord
            tenant_id: Optional tenant identifier (extracted from raw_exception if not provided)
            pipeline_id: Optional pipeline identifier (generated if not provided)
            
        Returns:
            Tuple of (normalized ExceptionRecord, AgentDecision)
            
        Raises:
            IntakeAgentError: If normalization or validation fails
        """
        # Extract or create normalized exception
        if isinstance(raw_exception, ExceptionRecord):
            normalized = raw_exception
        else:
            normalized = self._normalize_raw_exception(raw_exception, tenant_id, pipeline_id)

        # Validate against domain pack if available
        validation_results = self._validate_exception(normalized)

        # Create agent decision
        decision = self._create_decision(normalized, validation_results)

        # Log the event
        if self.audit_logger:
            # P8-14: Redact secrets from raw_exception before logging
            from src.tools.security import redact_secrets_from_dict
            raw_exception_dict = raw_exception if isinstance(raw_exception, dict) else raw_exception.model_dump()
            redacted_raw_exception = redact_secrets_from_dict(raw_exception_dict) if isinstance(raw_exception_dict, dict) else raw_exception_dict
            
            input_data = {
                "raw_exception": redacted_raw_exception,  # P8-14: Use redacted version
                "tenant_id": tenant_id,
                "pipeline_id": pipeline_id,
            }
            self.audit_logger.log_agent_event("IntakeAgent", input_data, decision, normalized.tenant_id)

        return normalized, decision

    def _normalize_raw_exception(
        self, raw_exception: dict[str, Any], tenant_id: Optional[str], pipeline_id: Optional[str]
    ) -> ExceptionRecord:
        """
        Normalize raw exception dict to ExceptionRecord.
        
        Args:
            raw_exception: Raw exception dictionary
            tenant_id: Optional tenant identifier
            pipeline_id: Optional pipeline identifier
            
        Returns:
            Normalized ExceptionRecord
        """
        # Extract required fields
        exception_id = raw_exception.get("exceptionId") or raw_exception.get("exception_id") or str(uuid.uuid4())
        extracted_tenant_id = tenant_id or raw_exception.get("tenantId") or raw_exception.get("tenant_id")
        if not extracted_tenant_id:
            raise IntakeAgentError("tenant_id is required but not provided in raw exception or parameters")
        
        source_system = raw_exception.get("sourceSystem") or raw_exception.get("source_system") or "UNKNOWN"
        
        # Extract timestamp
        timestamp = self._extract_timestamp(raw_exception)
        
        # Extract raw payload (everything else goes here)
        raw_payload = raw_exception.get("rawPayload") or raw_exception.get("raw_payload") or raw_exception.copy()
        
        # Extract optional fields
        # IMPORTANT: exceptionType may be in raw_exception OR in raw_payload (from Kafka event structure)
        exception_type = (
            raw_exception.get("exceptionType") 
            or raw_exception.get("exception_type")
            or (raw_payload.get("exceptionType") if isinstance(raw_payload, dict) else None)
            or (raw_payload.get("exception_type") if isinstance(raw_payload, dict) else None)
        )
        # Normalize exception type: strip any leading colon(s) and whitespace, then uppercase if all lowercase
        # Handles cases like: ":fin_settlement_fail", ": fin_settlement_fail", "fin_settlement_fail"
        if exception_type:
            # Strip ALL leading colons (handles ":value", "::value", etc.)
            while exception_type.startswith(':'):
                exception_type = exception_type[1:]
            # Strip leading/trailing whitespace
            exception_type = exception_type.strip()
            if exception_type and exception_type.islower():
                exception_type = exception_type.upper()
        
        # Build normalized context from extracted fields
        normalized_context = {
            "pipelineId": pipeline_id or str(uuid.uuid4()),
            "normalizedAt": datetime.now(timezone.utc).isoformat(),
        }
        
        # Add any additional context from raw exception
        if "context" in raw_exception:
            normalized_context.update(raw_exception["context"])

        # Create ExceptionRecord
        try:
            normalized = ExceptionRecord(
                exceptionId=exception_id,
                tenantId=extracted_tenant_id,
                sourceSystem=source_system,
                exceptionType=exception_type,
                timestamp=timestamp,
                rawPayload=raw_payload,
                normalizedContext=normalized_context,
                resolutionStatus=ResolutionStatus.OPEN,
            )
        except Exception as e:
            raise IntakeAgentError(f"Failed to create ExceptionRecord: {e}") from e

        return normalized

    def _extract_timestamp(self, raw_exception: dict[str, Any]) -> datetime:
        """
        Extract timestamp from raw exception.
        
        Args:
            raw_exception: Raw exception dictionary
            
        Returns:
            Datetime object
        """
        # Try various timestamp fields
        timestamp_str = (
            raw_exception.get("timestamp")
            or raw_exception.get("time")
            or raw_exception.get("createdAt")
            or raw_exception.get("created_at")
            or raw_exception.get("eventTime")
            or raw_exception.get("event_time")
        )
        
        if timestamp_str:
            if isinstance(timestamp_str, datetime):
                return timestamp_str
            try:
                # Try parsing ISO format
                if isinstance(timestamp_str, str):
                    # Handle timezone-aware strings
                    if timestamp_str.endswith("Z"):
                        timestamp_str = timestamp_str.replace("Z", "+00:00")
                    return datetime.fromisoformat(timestamp_str)
            except (ValueError, AttributeError):
                pass
        
        # Default to current time
        return datetime.now(timezone.utc)

    def _validate_exception(self, exception: ExceptionRecord) -> dict[str, Any]:
        """
        Validate exception against domain pack.
        
        Args:
            exception: ExceptionRecord to validate
            
        Returns:
            Dictionary with validation results
        """
        validation_results = {
            "valid": True,
            "errors": [],
            "warnings": [],
        }
        
        if self.domain_pack is None:
            validation_results["warnings"].append("No domain pack provided for validation")
            return validation_results
        
        # Validate exception type if provided
        if exception.exception_type:
            if exception.exception_type not in self.domain_pack.exception_types:
                validation_results["valid"] = False
                validation_results["errors"].append(
                    f"Exception type '{exception.exception_type}' not found in domain pack. "
                    f"Valid types: {sorted(self.domain_pack.exception_types.keys())}"
                )
            else:
                validation_results["warnings"].append(
                    f"Exception type '{exception.exception_type}' validated against domain pack"
                )
        else:
            validation_results["warnings"].append("No exception type provided (will be inferred in triage)")

        return validation_results

    def _create_decision(
        self, normalized: ExceptionRecord, validation_results: dict[str, Any]
    ) -> AgentDecision:
        """
        Create agent decision from normalization results.
        
        Args:
            normalized: Normalized ExceptionRecord
            validation_results: Validation results dictionary
            
        Returns:
            AgentDecision
        """
        # Build evidence list
        evidence = []
        evidence.append(f"Normalized exception ID: {normalized.exception_id}")
        evidence.append(f"Tenant ID: {normalized.tenant_id}")
        evidence.append(f"Source system: {normalized.source_system}")
        
        if normalized.exception_type:
            evidence.append(f"Exception type: {normalized.exception_type}")
        
        if validation_results["warnings"]:
            evidence.extend([f"Warning: {w}" for w in validation_results["warnings"]])
        
        if validation_results["errors"]:
            evidence.extend([f"Error: {e}" for e in validation_results["errors"]])

        # Calculate confidence based on validation
        if validation_results["valid"]:
            confidence = 1.0 if normalized.exception_type else 0.8
        else:
            confidence = 0.5  # Lower confidence if validation failed

        decision_text = "Normalized"
        if normalized.exception_type:
            decision_text += f" as {normalized.exception_type}"
        if not validation_results["valid"]:
            decision_text += " (validation errors)"

        return AgentDecision(
            decision=decision_text,
            confidence=confidence,
            evidence=evidence,
            nextStep="ProceedToTriage",
        )
