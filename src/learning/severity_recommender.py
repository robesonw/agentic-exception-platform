"""
Severity Rule Recommendation Engine for Phase 3.

Analyzes historical exceptions, triage decisions, and human overrides to suggest
new severity rules for Domain Packs.

Safety:
- Suggestions only, never auto-edit domain packs
- All suggestions require human review and approval

Matches specification from phase3-mvp-issues.md P3-8.
"""

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, Field

from src.models.domain_pack import SeverityRule
from src.models.exception_record import ExceptionRecord, Severity

logger = logging.getLogger(__name__)


class SeverityRuleSuggestion(BaseModel):
    """
    Severity rule suggestion generated from pattern analysis.
    
    Safety: These are suggestions only, never auto-applied.
    """

    candidate_rule: SeverityRule = Field(..., description="Domain-pack-compatible severity rule structure")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the suggested rule")
    example_exceptions: list[str] = Field(..., description="List of exception IDs that motivated this rule")
    pattern_description: str = Field(..., description="Description of the pattern detected")
    supporting_metrics: dict[str, Any] = Field(default_factory=dict, description="Supporting metrics for the suggestion")


class SeverityRecommenderError(Exception):
    """Raised when severity recommender operations fail."""

    pass


class SeverityRecommender:
    """
    Severity rule recommendation engine.
    
    Analyzes historical exceptions, triage decisions, and human overrides
    to identify patterns and suggest new severity rules.
    
    Responsibilities:
    - Analyze historical exception data
    - Identify severity patterns (attributes/fields correlating with escalated cases)
    - Generate severity rule suggestions (not auto-applied)
    - Store suggestions per tenant/domain
    """

    def __init__(self, storage_dir: str = "./runtime/learning"):
        """
        Initialize SeverityRecommender.
        
        Args:
            storage_dir: Directory for storing learning artifacts
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def analyze_severity_patterns(
        self,
        tenant_id: str,
        domain_name: str,
        historical_exceptions: Optional[list[ExceptionRecord]] = None,
        triage_decisions: Optional[list[dict[str, Any]]] = None,
        human_overrides: Optional[list[dict[str, Any]]] = None,
    ) -> list[SeverityRuleSuggestion]:
        """
        Analyze severity patterns and generate rule suggestions.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            historical_exceptions: Optional list of historical exception records
            triage_decisions: Optional list of triage decision dictionaries
            human_overrides: Optional list of human override dictionaries
            
        Returns:
            List of severity rule suggestions (not auto-applied)
        """
        suggestions = []
        
        # Load historical data if not provided
        if historical_exceptions is None:
            historical_exceptions = self._load_historical_exceptions(tenant_id, domain_name)
        
        if not historical_exceptions:
            logger.debug(f"No historical exceptions found for tenant {tenant_id}, domain {domain_name}")
            return suggestions
        
        # Analyze patterns
        # Pattern 1: Attributes/fields correlating with escalated cases
        escalation_patterns = self._analyze_escalation_patterns(historical_exceptions, triage_decisions)
        suggestions.extend(escalation_patterns)
        
        # Pattern 2: Combinations that should be HIGH instead of MEDIUM
        severity_upgrade_patterns = self._analyze_severity_upgrade_patterns(
            historical_exceptions, human_overrides
        )
        suggestions.extend(severity_upgrade_patterns)
        
        # Pattern 3: Attributes correlating with CRITICAL severity
        critical_patterns = self._analyze_critical_patterns(historical_exceptions, triage_decisions)
        suggestions.extend(critical_patterns)
        
        # Pattern 4: Human override patterns (severity changes)
        override_patterns = self._analyze_override_patterns(historical_exceptions, human_overrides)
        suggestions.extend(override_patterns)
        
        # Sort by confidence (highest first)
        suggestions.sort(key=lambda s: s.confidence_score, reverse=True)
        
        # Persist suggestions
        self._persist_suggestions(tenant_id, domain_name, suggestions)
        
        logger.info(
            f"Generated {len(suggestions)} severity rule suggestions for tenant {tenant_id}, "
            f"domain {domain_name}"
        )
        
        return suggestions

    def _load_historical_exceptions(
        self, tenant_id: str, domain_name: str
    ) -> list[ExceptionRecord]:
        """
        Load historical exceptions from feedback data.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            
        Returns:
            List of historical exception records
        """
        # Load from feedback JSONL file (same storage as policy learning)
        feedback_file = self.storage_dir / f"{tenant_id}.jsonl"
        if not feedback_file.exists():
            return []
        
        exceptions = []
        
        try:
            with open(feedback_file, "r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    feedback_record = json.loads(line)
                    
                    # Extract exception data from feedback record
                    exception_data = feedback_record.get("context", {})
                    if exception_data:
                        # Try to reconstruct ExceptionRecord from feedback context
                        # This is a simplified reconstruction - in production, would use full exception store
                        try:
                            exception = ExceptionRecord(
                                exception_id=feedback_record.get("exceptionId", ""),
                                tenant_id=tenant_id,
                                source_system=exception_data.get("sourceSystem", "UNKNOWN"),
                                exception_type=feedback_record.get("exceptionType"),
                                severity=Severity(feedback_record["severity"])
                                if feedback_record.get("severity")
                                else None,
                                timestamp=datetime.fromisoformat(
                                    feedback_record.get("timestamp", datetime.now(timezone.utc).isoformat())
                                ),
                                raw_payload=exception_data.get("rawPayload", {}),
                                normalized_context=exception_data.get("normalizedContext", {}),
                            )
                            exceptions.append(exception)
                        except Exception as e:
                            logger.debug(f"Failed to reconstruct exception from feedback: {e}")
        except Exception as e:
            logger.warning(f"Failed to load historical exceptions for tenant {tenant_id}: {e}")
        
        return exceptions

    def _analyze_escalation_patterns(
        self,
        exceptions: list[ExceptionRecord],
        triage_decisions: Optional[list[dict[str, Any]]],
    ) -> list[SeverityRuleSuggestion]:
        """
        Analyze patterns in escalated exceptions.
        
        Identifies attributes/fields that correlate with escalated cases.
        
        Args:
            exceptions: List of exception records
            triage_decisions: Optional list of triage decision dictionaries
            
        Returns:
            List of severity rule suggestions
        """
        suggestions = []
        
        # Group exceptions by escalation status
        escalated = [e for e in exceptions if e.resolution_status.value == "ESCALATED"]
        non_escalated = [e for e in exceptions if e.resolution_status.value != "ESCALATED"]
        
        if len(escalated) < 3:  # Need at least 3 escalated cases
            return suggestions
        
        # Analyze raw_payload fields for patterns
        escalated_payloads = [e.raw_payload for e in escalated]
        non_escalated_payloads = [e.raw_payload for e in non_escalated]
        
        # Find fields that appear more frequently in escalated cases
        escalated_field_counts = defaultdict(int)
        non_escalated_field_counts = defaultdict(int)
        
        for payload in escalated_payloads:
            for key, value in payload.items():
                escalated_field_counts[f"{key}={str(value)}"] += 1
        
        for payload in non_escalated_payloads:
            for key, value in payload.items():
                non_escalated_field_counts[f"{key}={str(value)}"] += 1
        
        # Find fields with high correlation to escalation
        total_escalated = len(escalated)
        total_non_escalated = len(non_escalated)
        
        for field_value, escalated_count in escalated_field_counts.items():
            non_escalated_count = non_escalated_field_counts.get(field_value, 0)
            total_count = escalated_count + non_escalated_count
            
            if total_count < 3:  # Need at least 3 occurrences
                continue
            
            # Calculate escalation rate
            escalation_rate = escalated_count / total_count if total_count > 0 else 0
            
            # If escalation rate is high (>50%), suggest a severity rule
            if escalation_rate > 0.5 and escalated_count >= 3:
                # Extract field name and value
                if "=" in field_value:
                    field_name, field_value_str = field_value.split("=", 1)
                    
                    # Generate condition
                    condition = f"rawPayload.{field_name} == '{field_value_str}'"
                    
                    # Determine suggested severity (escalated cases often need HIGH or CRITICAL)
                    suggested_severity = "HIGH" if escalation_rate < 0.8 else "CRITICAL"
                    
                    # Find example exceptions
                    example_ids = [
                        e.exception_id
                        for e in escalated
                        if str(e.raw_payload.get(field_name)) == field_value_str
                    ][:5]  # Limit to 5 examples
                    
                    confidence = min(0.9, 0.6 + (escalation_rate - 0.5) * 0.6)
                    
                    suggestions.append(
                        SeverityRuleSuggestion(
                            candidate_rule=SeverityRule(
                                condition=condition,
                                severity=suggested_severity,
                            ),
                            confidence_score=confidence,
                            example_exceptions=example_ids,
                            pattern_description=(
                                f"Field '{field_name}' with value '{field_value_str}' "
                                f"correlates with {escalation_rate:.1%} escalation rate "
                                f"({escalated_count}/{total_count} cases)"
                            ),
                            supporting_metrics={
                                "escalation_rate": escalation_rate,
                                "escalated_count": escalated_count,
                                "total_count": total_count,
                                "field_name": field_name,
                                "field_value": field_value_str,
                            },
                        )
                    )
        
        return suggestions

    def _analyze_severity_upgrade_patterns(
        self,
        exceptions: list[ExceptionRecord],
        human_overrides: Optional[list[dict[str, Any]]],
    ) -> list[SeverityRuleSuggestion]:
        """
        Analyze patterns where severity should be upgraded (e.g., MEDIUM -> HIGH).
        
        Args:
            exceptions: List of exception records
            human_overrides: Optional list of human override dictionaries
            
        Returns:
            List of severity rule suggestions
        """
        suggestions = []
        
        if not human_overrides:
            return suggestions
        
        # Find overrides where severity was increased
        severity_upgrades = []
        for override in human_overrides:
            if override.get("type") == "severity_change":
                old_severity = override.get("oldSeverity")
                new_severity = override.get("newSeverity")
                
                # Check if severity was upgraded
                severity_levels = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}
                if (
                    old_severity
                    and new_severity
                    and severity_levels.get(new_severity, 0) > severity_levels.get(old_severity, 0)
                ):
                    severity_upgrades.append(override)
        
        if len(severity_upgrades) < 3:  # Need at least 3 upgrades
            return suggestions
        
        # Analyze patterns in upgraded exceptions
        # Group by exception type and attributes
        upgrade_patterns = defaultdict(list)
        
        for override in severity_upgrades:
            exception_id = override.get("exceptionId")
            exception = next((e for e in exceptions if e.exception_id == exception_id), None)
            
            if exception:
                # Create pattern key from exception attributes
                pattern_key = f"{exception.exception_type}:{exception.source_system}"
                upgrade_patterns[pattern_key].append((exception, override))
        
        # Generate suggestions for patterns with multiple upgrades
        for pattern_key, pattern_exceptions in upgrade_patterns.items():
            if len(pattern_exceptions) >= 3:
                exception_type, source_system = pattern_key.split(":", 1)
                
                # Find most common new severity
                new_severities = [override.get("newSeverity") for _, override in pattern_exceptions]
                most_common_severity = max(set(new_severities), key=new_severities.count)
                
                # Generate condition
                condition = f"exceptionType == '{exception_type}' && sourceSystem == '{source_system}'"
                
                # Get example exception IDs
                example_ids = [e.exception_id for e, _ in pattern_exceptions[:5]]
                
                confidence = min(0.9, 0.6 + (len(pattern_exceptions) / 10) * 0.3)
                
                suggestions.append(
                    SeverityRuleSuggestion(
                        candidate_rule=SeverityRule(
                            condition=condition,
                            severity=most_common_severity,
                        ),
                        confidence_score=confidence,
                        example_exceptions=example_ids,
                        pattern_description=(
                            f"Exception type '{exception_type}' from '{source_system}' "
                            f"was upgraded to {most_common_severity} severity "
                            f"in {len(pattern_exceptions)} cases"
                        ),
                        supporting_metrics={
                            "upgrade_count": len(pattern_exceptions),
                            "exception_type": exception_type,
                            "source_system": source_system,
                            "suggested_severity": most_common_severity,
                        },
                    )
                )
        
        return suggestions

    def _analyze_critical_patterns(
        self,
        exceptions: list[ExceptionRecord],
        triage_decisions: Optional[list[dict[str, Any]]],
    ) -> list[SeverityRuleSuggestion]:
        """
        Analyze patterns in CRITICAL severity exceptions.
        
        Identifies attributes that correlate with CRITICAL severity.
        
        Args:
            exceptions: List of exception records
            triage_decisions: Optional list of triage decision dictionaries
            
        Returns:
            List of severity rule suggestions
        """
        suggestions = []
        
        # Group exceptions by severity
        critical = [e for e in exceptions if e.severity == Severity.CRITICAL]
        non_critical = [e for e in exceptions if e.severity != Severity.CRITICAL]
        
        if len(critical) < 3:  # Need at least 3 CRITICAL cases
            return suggestions
        
        # Analyze normalized_context fields for patterns
        critical_contexts = [e.normalized_context for e in critical]
        non_critical_contexts = [e.normalized_context for e in non_critical]
        
        # Find fields that appear more frequently in CRITICAL cases
        critical_field_counts = defaultdict(int)
        non_critical_field_counts = defaultdict(int)
        
        for context in critical_contexts:
            for key, value in context.items():
                critical_field_counts[f"{key}={str(value)}"] += 1
        
        for context in non_critical_contexts:
            for key, value in context.items():
                non_critical_field_counts[f"{key}={str(value)}"] += 1
        
        # Find fields with high correlation to CRITICAL
        total_critical = len(critical)
        total_non_critical = len(non_critical)
        
        for field_value, critical_count in critical_field_counts.items():
            non_critical_count = non_critical_field_counts.get(field_value, 0)
            total_count = critical_count + non_critical_count
            
            if total_count < 3:  # Need at least 3 occurrences
                continue
            
            # Calculate CRITICAL rate
            critical_rate = critical_count / total_count if total_count > 0 else 0
            
            # If CRITICAL rate is high (>60%), suggest a severity rule
            if critical_rate > 0.6 and critical_count >= 3:
                # Extract field name and value
                if "=" in field_value:
                    field_name, field_value_str = field_value.split("=", 1)
                    
                    # Generate condition
                    condition = f"normalizedContext.{field_name} == '{field_value_str}'"
                    
                    # Find example exceptions
                    example_ids = [
                        e.exception_id
                        for e in critical
                        if str(e.normalized_context.get(field_name)) == field_value_str
                    ][:5]  # Limit to 5 examples
                    
                    confidence = min(0.9, 0.7 + (critical_rate - 0.6) * 0.5)
                    
                    suggestions.append(
                        SeverityRuleSuggestion(
                            candidate_rule=SeverityRule(
                                condition=condition,
                                severity="CRITICAL",
                            ),
                            confidence_score=confidence,
                            example_exceptions=example_ids,
                            pattern_description=(
                                f"Context field '{field_name}' with value '{field_value_str}' "
                                f"correlates with {critical_rate:.1%} CRITICAL rate "
                                f"({critical_count}/{total_count} cases)"
                            ),
                            supporting_metrics={
                                "critical_rate": critical_rate,
                                "critical_count": critical_count,
                                "total_count": total_count,
                                "field_name": field_name,
                                "field_value": field_value_str,
                            },
                        )
                    )
        
        return suggestions

    def _analyze_override_patterns(
        self,
        exceptions: list[ExceptionRecord],
        human_overrides: Optional[list[dict[str, Any]]],
    ) -> list[SeverityRuleSuggestion]:
        """
        Analyze patterns in human severity overrides.
        
        Identifies cases where humans consistently change severity, suggesting
        a rule should be added or updated.
        
        Args:
            exceptions: List of exception records
            human_overrides: Optional list of human override dictionaries
            
        Returns:
            List of severity rule suggestions
        """
        suggestions = []
        
        if not human_overrides:
            return suggestions
        
        # Group overrides by exception attributes
        override_patterns = defaultdict(list)
        
        for override in human_overrides:
            if override.get("type") == "severity_change":
                exception_id = override.get("exceptionId")
                exception = next((e for e in exceptions if e.exception_id == exception_id), None)
                
                if exception:
                    # Create pattern key from exception attributes
                    pattern_key = (
                        f"{exception.exception_type}:"
                        f"{exception.source_system}:"
                        f"{override.get('newSeverity')}"
                    )
                    override_patterns[pattern_key].append((exception, override))
        
        # Generate suggestions for patterns with multiple overrides
        for pattern_key, pattern_overrides in override_patterns.items():
            if len(pattern_overrides) >= 3:
                parts = pattern_key.split(":")
                exception_type = parts[0]
                source_system = parts[1]
                new_severity = parts[2]
                
                # Generate condition
                condition = f"exceptionType == '{exception_type}' && sourceSystem == '{source_system}'"
                
                # Get example exception IDs
                example_ids = [e.exception_id for e, _ in pattern_overrides[:5]]
                
                confidence = min(0.85, 0.6 + (len(pattern_overrides) / 10) * 0.25)
                
                suggestions.append(
                    SeverityRuleSuggestion(
                        candidate_rule=SeverityRule(
                            condition=condition,
                            severity=new_severity,
                        ),
                        confidence_score=confidence,
                        example_exceptions=example_ids,
                        pattern_description=(
                            f"Exception type '{exception_type}' from '{source_system}' "
                            f"was manually set to {new_severity} severity "
                            f"in {len(pattern_overrides)} cases"
                        ),
                        supporting_metrics={
                            "override_count": len(pattern_overrides),
                            "exception_type": exception_type,
                            "source_system": source_system,
                            "suggested_severity": new_severity,
                        },
                    )
                )
        
        return suggestions

    def _persist_suggestions(
        self,
        tenant_id: str,
        domain_name: str,
        suggestions: list[SeverityRuleSuggestion],
    ) -> None:
        """
        Persist severity rule suggestions to tenant/domain-specific JSONL file.
        
        Args:
            tenant_id: Tenant identifier
            domain_name: Domain name identifier
            suggestions: List of suggestions to persist
        """
        suggestions_file = self.storage_dir / f"{tenant_id}_{domain_name}_severity_suggestions.jsonl"
        
        # Append each suggestion as a JSONL line
        with open(suggestions_file, "a", encoding="utf-8") as f:
            for suggestion in suggestions:
                suggestion_dict = suggestion.model_dump()
                suggestion_dict["timestamp"] = datetime.now(timezone.utc).isoformat()
                f.write(json.dumps(suggestion_dict, default=str) + "\n")
        
        logger.debug(
            f"Persisted {len(suggestions)} severity rule suggestions to {suggestions_file}"
        )

